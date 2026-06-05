# 2026-06-05 W1 evidence server session

Single-day 8×H200 server slot. This was the most productive W1 evidence
session so far: it closed the previously-missing **T3 clean VRAM sweep**,
**T6 Eagle3 ON/OFF paired A/B**, and **T1 DEP startup-failure capture**, and
produced concrete paired evidence for the **T8/T4 LiteLLM `delta.reasoning`
strip**. It also collected T5 dashboard/metrics material and two Grafana
screenshots.

This note is the human-readable, audited summary. The machine inventory is in
`session/artifact_manifest.txt`. A cross-session view is in
`results/summaries/w1-evidence-cross-session.md`.

## Executive summary

| Thread | Planned | Result |
|---|---|---|
| T3 — DeepSeek VRAM cap sweep | 0.15 / 0.20 / 0.25 with filenames matching runtime | **Done, clean** (0.15 hard-fails, 0.20 & 0.25 OK) |
| T6 — Kimi Eagle3 ON vs OFF | paired A/B, fair config | **Done** (5×5 paired pair recovered; see integrity note) |
| T1 — Kimi DEP startup failure | deterministic capture | **Done** (`exited 1`, clean crash) |
| T8/T4 — LiteLLM proxy vs direct | paired Kimi reasoning stream | **Done** (proxy strips `delta.reasoning`) |
| T5 — dashboard/metrics under load | metric-name validation + load | **Partial** (metric inventory + 2 screenshots; full load-panel validation still owed) |
| DeepSeek direct baselines | smoke/throughput at new cap | **Done** (throughput not meaningful, `completion≈3`) |
| C4 — restore Kimi to Eagle3-ON | restore + smoke | **Done** |

The headline result is the **T6 Eagle3 paired A/B**: with this single short
prompt, Eagle3 gives **~3.8× single-shot E2E** and **~2.4× TPOT(any-token)**,
and **~2× repeated-p50 TTFT**, while **not** helping first-token latency
(TTFT-any ≈ 204 ms in both arms, as expected — speculative decoding accelerates
the decode loop, not prefill).

## Data integrity — READ THIS BEFORE QUOTING NUMBERS

The final session commit **`fc97700` ("results od 202600605 server session")**
**re-ran several benchmarks at the end of the slot and overwrote earlier
results in the same run directories**. The bench stdout logs
(`t6_eagle3/bench_off.log`, committed earlier in `ec3df59`) were **not**
regenerated, so after `fc97700` the committed JSON disagreed with the logs and
with the agent-state handoff.

Dirs overwritten by `fc97700`: `kimi run-05` (OFF), `deepseek run-01`,
`deepseek run-02` (latency + repeated). Clean / never overwritten:
`kimi run-04` (ON), `kimi run-01` (T8 proxy), `kimi run-03` (T8 direct).

### T6 OFF had two generations

The Eagle3-OFF benchmark exists in two executions that both landed in the
auto-id `run-05` directory:

| Generation | Time (UTC) | measured | single-shot TTFT(content) | chunks | repeated p50 TTFT | Where |
|---|---|---:|---:|---:|---:|---|
| **paired** (orig, `ec3df59`) | 09:17 | 5 | 2489 ms | 143 | 1675 ms | recovered → `run-05_eagle3-off-paired` |
| **rerun** (`fc97700`) | 10:02 | 10 | 1365 ms | 62 | 1650 ms | `run-05_eagle3-off-rerun` |

The **paired** generation (09:17, 5 runs) is the correct A/B partner for ON
(`run-04`, 09:01, 5 runs): same session phase, same `measured_runs`. The
**rerun** (10:02, 10 runs) is an unpaired, warmer re-execution that happened to
reuse the `run-05` directory. The earlier "ON 5 vs OFF 10 runs" asymmetry was an
artifact of this overwrite — the original paired bench was **5 vs 5**.

Both generations are preserved (recovered from `ec3df59` via `git checkout`).
**Use `run-05_eagle3-off-paired` for the T6 A/B.** The rerun is a useful
single-shot sensitivity check: Kimi at `temperature=0` is non-deterministic
(MoE routing + speculative), so single-shot E2E moves between ~2.1× (warm
rerun) and ~3.8× (paired). **The repeated A/B (~2× p50 TTFT) is robust across
both generations and is the number to lead with.**

## Run-directory map (auto-id → semantic alias)

`run_bench_suite.py` did not honor a semantic `--run-id`, so dirs came out as
plain auto-ids. They were renamed with `git mv`, keeping the original run-id as
a prefix (the embedded `controls.run_id` inside each JSON is unchanged and still
reads the original auto-id, e.g. `..._run-05`).

| Semantic alias | Orig auto-id | Path / model | Meaning |
|---|---|---|---|
| `run-01_t8-proxy` | run-01 | kimi :4000 | T8/T4 proxy path (3 chunks, TTFT null) |
| `run-03_t8-direct` | run-03 | kimi :8000 | T8/T4 direct path (26 chunks, 242 reasoning_chars) |
| `run-04_eagle3-on` | run-04 | kimi :8000 | **T6 Eagle3 ON** |
| `run-05_eagle3-off-paired` | run-05 | kimi :8000 | **T6 Eagle3 OFF — paired (use this)** |
| `run-05_eagle3-off-rerun` | run-05 | kimi :8000 | T6 Eagle3 OFF — end-of-session rerun |
| `run-01_baseline` | run-01 | deepseek :8004 | DeepSeek direct baseline |
| `run-02_baseline` | run-02 | deepseek :8004 | DeepSeek direct baseline |

(There is no `kimi run-02`: the auto-id sequence skipped from 01 to 03.)

## Headline numbers

### T6 — Eagle3 ON vs OFF (paired, 5×5, single short prompt)

Single-shot (`measure_ttft_once`):

| Metric | ON (`run-04`) | OFF paired (`run-05_..paired`) | Eagle3 gain |
|---|---:|---:|---:|
| TTFT content | 652 ms | 2489 ms | 3.8× |
| TTFT any-token | 204 ms | 203 ms | ≈1× (no help) |
| E2E | 674 ms | 2536 ms | 3.8× |
| TPOT any-token | 6.92 ms/tok | 16.55 ms/tok | 2.4× |
| chunks / reasoning_chars | 24 / 240 | 143 / 546 | — |

Repeated (sequential, p50/p95 TTFT):

| | ON (5 runs) | OFF paired (5 runs) | OFF rerun (10 runs) |
|---|---:|---:|---:|
| p50 TTFT | 837 ms | 1675 ms | 1650 ms |
| p95 TTFT | 1694 ms | 4426 ms | 2501 ms |

Net: **~2× p50 TTFT (robust)**; single-shot E2E 2.1×–3.8× (variance-sensitive).

### T8/T4 — LiteLLM proxy vs direct (Kimi K2.6, single-shot)

| Path | TTFT content | TTFT any | chunks | reasoning_chars |
|---|---:|---:|---:|---:|
| proxy `:4000` (`run-01_t8-proxy`) | null | null | 3 | 0 |
| direct `:8000` (`run-03_t8-direct`) | null | 0.214 s | 26 | 242 |

LiteLLM `main-v1.66.0-stable` strips Kimi's `delta.reasoning` field: the proxy
client sees only the final-answer chunks (TTFT-any null, 0 reasoning_chars).
Direct vLLM preserves the reasoning stream. Parser fix #31 is verified correct
direct. **Proxy is unusable as the sole driver for Kimi reasoning streams in
this LiteLLM version.** (max_tokens=64 here is intentionally small; not a
latency-fair comparison, the point is the streaming-semantics difference.)

### T3 — DeepSeek VRAM cap sweep

| Cap | Result | TTFT | E2E |
|---|---|---:|---:|
| 0.15 | **hard-fail** (engine-core init OOM traceback, `log_cap015_FAILED.txt`) | — | — |
| 0.20 | OK (`verify_cap020.txt`, `ttft_cap020.json`) | 15.2 s | 21.7 s |
| 0.25 | OK (`verify_cap025.txt`, `ttft_cap025.json`) | 15.2 s | 21.7 s |

Filenames finally match runtime caps (the 2026-05-27 cap020/cap025 mismatch is
resolved). Compose default lowered 0.25 → 0.20. The high TTFT/E2E here reflect
the cap-probe workload, not steady-state serving.

### DeepSeek direct baselines

`run-01_baseline` TTFT 1.51 s / E2E 2.24 s; `run-02_baseline` TTFT 1.29 s /
E2E 2.47 s. `completion_tokens ≈ 3` ("OK"-length output) — throughput numbers
are **not meaningful** at this length and should be excluded from any tok/s
claim.

### T1 — Kimi DEP startup failure

`dep_state.txt = exited 1` — deterministic clean startup crash (not a hang).
Full `dep_full.log` + `dep_startup.log` + `dep_engine_cmd.json` captured.
Confirms "single-node DEP does not work" with a reproducible artifact.

### C4 — restore

Kimi restored to Eagle3-ON: `session/restore_engine_cmd.json` shows
`speculative-config` present; `session/restore_smoke.json` `completed=True`
(TTFT-any 1.26 s, 19 chunks, 183 reasoning_chars).

## T5 — observability material (partial)

- `t5_metrics/full-load/` — full `/metrics` dumps for Kimi and DeepSeek.
- `t5_metrics/prometheus_summary.txt` — batched-run metric summary.
- `t5_metrics/eagle3-{on,off}/` — 12×10 s side snapshots of
  `vllm:num_requests_*`, `kv_cache_usage_perc`, generation-rate during the T6
  benches.
- Two Grafana screenshots at the run root:
  `2026-06-05_grafana_dashboard-max_num_seqs_{1,32}.png`.

All 18 dashboard panels were validated against these live metric names
(vLLM v0.20.0, label `model_name`); `spec_decode_*` present only under
Eagle3-ON. **Still owed:** full panel validation under sustained concurrent
load via `vllm bench serve` (runbook: `serving/runbooks/load-test-and-grafana.md`).

## Scope-creep note (resolved: keep)

`results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl` (300
SWE-bench Lite prompts) entered in `ec3df59`. It is not part of the W1 plan or
the Phase 1 DoD, but is **kept intentionally** as the offline workload dataset
for the #34 `vllm bench serve` load test (re-creatable via
`benchmarks/scripts/download_swe_bench_lite.py`).

## Unresolved

- `results/raw/first_ttft.json` — a standalone Kimi TTFT probe (direct :8000,
  10:00 UTC, TTFT 1.22 s) added in `fc97700` between the OFF reruns. Thread
  ownership unclear; left in place, to clarify at the next slot.

## Next recommended work (laptop)

W1 thread write-ups using these numbers, in order:
1. **T6** — paired 5×5 A/B; lead with repeated ~2× p50, report single-shot range
   with the non-determinism caveat; cross-ref #48 methodology.
2. **T1** — DEP `exited 1`.
3. **T3** — clean sweep (0.15 fail / 0.20 / 0.25), default now 0.20.
4. **T8/T4** — LiteLLM `delta.reasoning` strip (paired proxy vs direct).
5. **T5** — only then, dashboard validation under live load.
