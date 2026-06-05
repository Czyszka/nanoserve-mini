# 2026-06-05 — T5 Grafana dashboard load session (#34)

Status: active. Server slot runbook — *how & when* only; *what & why* live in #34
and `docs/writeups/w1/t5-observability.md`.

Goal: drive concurrent load so the provisioned dashboard
(`serving/compose/grafana/provisioning/dashboards/vllm-phase1.json`,
uid `nanoserve-vllm-phase1`) shows live queue/throughput/latency/KV curves, then
capture a screenshot for W1 T5.

## Pre-flight (already verified, no JSON edits needed)

Dashboard metric names were validated against the live `/metrics` dump in
`results/runs/2026-06-05_w1_evidence/t5_metrics/`. All 18 panels map to real
vLLM v0.20.0 names (label `model_name`). No query fixes required. Notes:

- **Spec Decode** row (panels 17/18) only populates with **Kimi Eagle3 ON**
  (`spec_decode_*` present in `eagle3-on/` dumps, absent in `eagle3-off/`).
  Kimi is currently restored to Eagle3-ON (`restore_engine_cmd.json`), so it
  will fill — good.
- Latency panels use `rate(...[5m])`; they need **≥5–6 min of sustained traffic**
  before p50/p95 are meaningful.
- Queue panels (`num_requests_running`, `num_requests_waiting`) only move with
  **concurrency > 1** — single-stream benches leave them flat.

## 0. Bring-up checks

```bash
docker compose -f serving/compose/docker-compose.observability.yml ps
curl -fsS http://127.0.0.1:9090/-/healthy && echo "prometheus OK"
curl -fsS http://127.0.0.1:3001/api/health && echo "grafana OK"
# all three targets should be health=up:
curl -s http://127.0.0.1:9090/api/v1/targets \
  | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'
# sanity: a live series exists
curl -s 'http://127.0.0.1:9090/api/v1/query?query=vllm:num_requests_running' | jq '.data.result'
```

Grafana UI: open dashboard **vLLM Phase 1 — nanoserve-mini**, set time range to
**Last 15 minutes**, refresh **5s**, pick the Prometheus datasource.

## 1. Load generation — `vllm bench serve` (in-container, no new code)

Flags verified against `results/runs/2026-06-05_w1_evidence/vllm_bench_serve_help.txt`
(this image's `--help=all`). Driver runs inside the vLLM container (CLI ships with
the image). Drive **direct :8000** (Kimi) — bypasses the LiteLLM reasoning-strip
and keeps metrics clean.

**Workload:** the prepared **SWE-bench Lite 300** prompt set
(`results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl`, one
`{"prompt": ...}` per line). Fully **offline** — prompts are baked into the JSONL;
no repo clone, no eval, no internet. Consumed via `--dataset-name custom` (this
dataset reads the `prompt` field directly). `random` stays as the fallback.

```bash
# the JSONL must be visible INSIDE the container; if the repo isn't mounted, copy it in:
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml cp \
  results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl \
  vllm:/tmp/swe_bench_vllm.jsonl

docker compose -f serving/compose/docker-compose.kimi-k2.6.yml exec vllm bash
```

Prerequisites inside the container (this vLLM image ships without bench extras):

```bash
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # use ~/hf_cache, don't phone HF
pip install pandas datasets                        # bench dataset deps (NOT vllm[bench])
```

Do **not** run `pip install vllm[bench]` here — it can reinstall/upgrade vllm+torch
and break the running server. Install only the leaf deps; add `pyarrow`/`pillow` if
a later import complains. These installs are ephemeral (gone on container restart),
which is fine for the T5 session.

Inside the container — phased ramp via `--max-concurrency` (≈12 min total).
`--ignore-eos --custom-output-len 256` forces a fixed 256-token decode per request
→ steady, predictable decode load (without it Kimi may EOS early and the decode
panels go choppy). `--num-warmups 8` uses the built-in warmup. `--save-result`
captures TTFT/TPOT/throughput numbers to pair with the screenshot.

```bash
DS=/tmp/swe_bench_vllm.jsonl
COMMON="--backend vllm --base-url http://127.0.0.1:8000 --model kimi-k2.6 \
  --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
  --dataset-name custom --dataset-path $DS \
  --custom-output-len 256 --ignore-eos \
  --save-result --result-dir /tmp/t5_bench \
  --metadata phase=t5 model=kimi-k2.6 eagle3=on"

# phase A — light
vllm bench serve $COMMON --num-warmups 8 --num-prompts 120 --max-concurrency 4 \
  --result-filename phaseA_c4.json
# phase B — medium
vllm bench serve $COMMON --num-prompts 300 --max-concurrency 16 \
  --result-filename phaseB_c16.json
# phase C — saturate (fills the waiting-queue panel)
vllm bench serve $COMMON --num-prompts 300 --max-concurrency 64 \
  --result-filename phaseC_c64.json
```

Run A→B→C back-to-back (no long gaps) so the 15-min window shows a clean ramp.
Push `--max-concurrency` higher if phase C never makes `num_requests_waiting`
leave zero (you haven't hit `max_num_seqs` yet).

Notes:
- **Kimi needs `--trust-remote-code`** — bench-serve inits a client-side tokenizer
  and Kimi K2.6 ships custom tokenizer code ("contains custom code which must be
  executed"). If it still complains, either point at the cached tokenizer
  (`--tokenizer moonshotai/Kimi-K2.6`, must be in `~/hf_cache`) or skip it
  entirely with `--skip-tokenizer-init` (token metrics still come from vLLM
  `/metrics`, so the T5 dashboard is unaffected).
- 300-prompt file + `--num-prompts 600` (phase C) → vLLM **oversamples** (repeats)
  prompts by default; the repeats also exercise the **prefix-cache hit** panel.
  Add `--no-oversample` if you want strictly unique prompts.
- If Kimi's :8000 doesn't serve `/v1/completions`, switch to chat:
  `--backend openai-chat --endpoint /v1/chat/completions` (the custom dataset
  gets the chat template applied automatically; add `--skip-chat-template` to opt
  out).
- One-command alternative to the manual ramp: a single linear ramp via
  `--ramp-up-strategy linear --ramp-up-start-rps 1 --ramp-up-end-rps 30` (drop
  `--max-concurrency`) — one clean increasing-load curve, nice for a single
  screenshot but a less controlled saturation point.
- Fallback workload (no file needed): `--dataset-name random --random-input-len
  1024 --random-output-len 256` in place of the `custom`/`--dataset-path` flags.

Pull the bench JSONs back for the W1 record:

```bash
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml cp \
  vllm:/tmp/t5_bench \
  results/runs/2026-06-05_w1_evidence/t5_metrics/bench/
```

## 2. What each panel should show at the screenshot moment

| Panel | Expected under phase C |
|---|---|
| Prometheus targets | all UP (green) |
| Requests running | ramps 4 → 16 → toward `max_num_seqs` |
| Requests waiting | **> 0** during saturation (the key "pressure" signal) |
| Generation throughput | non-zero, plateaus at saturation |
| Prompt (prefill) throughput | spikes at each batch admission |
| TTFT / ITL / E2E p50/p95 | rise visibly from phase A → C |
| KV cache usage % | climbs with concurrency |
| Spec decode acceptance | populated (Kimi Eagle3-ON) |

## 3. Screenshot

Take the screenshot **during phase C** (or right after, window = Last 15m so the
full ramp is visible). Save to `results/runs/2026-06-05_w1_evidence/t5_metrics/`
as `grafana_dashboard_load.png` (image stays local / git-ignored if large — commit
only if small, else reference path + reproduce steps per CLAUDE.md results policy).

## 4. Cleanup

No state change to undo — load is read-only traffic. Leave Kimi in Eagle3-ON.
Optionally snapshot the final `/metrics` for the record.

## Next

Feed numbers + screenshot into `docs/writeups/w1/t5-observability.md`; this closes
the last W1 owed item (#34) modulo DCGM/GPU-hardware panels (deferred, not blocking).
