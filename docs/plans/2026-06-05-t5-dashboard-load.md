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

Driver runs from inside the vLLM container (CLI ships with the image). Drive
**direct :8000** (Kimi) — bypasses the LiteLLM reasoning-strip and keeps metrics
clean. `--dataset-name random` needs no external file → reproducible.

```bash
# exec into the running vllm service
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml exec vllm bash
```

Inside the container, run the phased ramp (≈12 min total, screen-worthy):

```bash
# warmup (not screenshotted)
vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 --dataset-name random \
  --random-input-len 1024 --random-output-len 256 \
  --num-prompts 32 --max-concurrency 4

# phase A — light
vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 --dataset-name random \
  --random-input-len 1024 --random-output-len 256 \
  --num-prompts 120 --max-concurrency 4

# phase B — medium
vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 --dataset-name random \
  --random-input-len 1024 --random-output-len 256 \
  --num-prompts 300 --max-concurrency 16

# phase C — saturate (fills the waiting-queue panel)
vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 --dataset-name random \
  --random-input-len 1024 --random-output-len 256 \
  --num-prompts 600 --max-concurrency 64
```

Run A→B→C back-to-back (no long gaps) so the 15-min window shows a clean ramp.
Adjust `--max-concurrency` upward if phase C never makes `num_requests_waiting`
leave zero (that means you haven't hit `max_num_seqs` yet).

Fallback if `vllm bench serve` is unavailable in this image:
`python -m vllm.entrypoints.cli.main bench serve ...` or the older
`vllm/benchmarks/benchmark_serving.py`.

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
