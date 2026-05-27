# 2026-05-27 W1 evidence server session

## Executive summary

This server session produced useful W1 evidence for **T8 — LiteLLM Proxy overhead** and a partial baseline for **T3 — DeepSeek VRAM configuration**, but it did **not** complete the full planned W1 evidence set.

The strongest output is the paired direct-vs-proxy measurement set for both served models:

- Kimi-K2.6 direct `:8000` vs LiteLLM Proxy `:4000`.
- DeepSeek-V4-Flash direct `:8004` vs LiteLLM Proxy `:4000`.

These artifacts are suitable for a laptop-side paired-delta analysis and for a W1 segment about proxy overhead, with clear limitations: single prompt, single-stream, short output, no concurrency sweep.

An important caveat for Kimi: the proxy materially changes streaming semantics, not just adds network overhead. Median `ttft_any_token_seconds` rises from ~0.21 s on the direct path to ~0.61 s on the proxy path (~3× regression, paired delta ~+0.40 s), because LiteLLM does not forward `delta.reasoning` / `delta.reasoning_content` chunks separately — proxy clients see the first emitted token only when the final-answer text starts. The pure network/routing overhead, visible in `ttft_seconds` (final-answer) and `e2e_seconds`, is on the order of tens of milliseconds. The two effects should be reported separately in W1 and tied to T2 (reasoning parser).

Median Kimi `output_tokens_per_second` also drops by ~5.6 % under the proxy path (79.1 → 74.7) in this single-stream workload. For DeepSeek, `output_tokens_per_second` is not meaningful here because median `completion_tokens` is ~2 (the "OK" sample); throughput numbers for DeepSeek should be excluded or annotated with their completion length.

The DeepSeek VRAM evidence is only a baseline, not a sweep. A key caveat is that files were named as if they represented `cap020`, but the runtime log records `gpu_memory_utilization: 0.25`. For W1, these artifacts should be treated as a `0.25` baseline unless independently proven otherwise.

The planned Kimi Eagle3 ON/OFF comparison and Kimi DEP startup failure capture were not completed. Dashboard/Prometheus work remained mostly untouched, which is acceptable because it was stretch-only for this session.

## Original session plan

The planned 2026-05-27 server session was intended to collect W1 evidence for these threads:

| Thread | Planned work | Result |
|---|---|---|
| T8 | LiteLLM Proxy overhead, paired A/B direct/proxy measurements for Kimi and DeepSeek | **Completed** |
| T3 | DeepSeek VRAM cap justification, including `0.15` and `0.25` sweep around the chosen cap | **Partial only** |
| T6 | Kimi Eagle3 ON/OFF benchmark | **Not completed** |
| T1 | Kimi DEP startup failure capture | **Not completed** |
| T5 | Prometheus/Grafana validation under live load | **Stretch only; not completed** |

## What was completed

### 1. Session start snapshot

The session captured basic starting state:

- `session/start_commit.txt`
- `session/docker_ps_start.txt`
- `session/nvidia_smi_start.txt`

The Docker snapshot showed:

- `vllm` running and healthy on `:8000`.
- `litellm-proxy` running and healthy on `:4000`.
- `prometheus` and `grafana` running.
- `open-webui` running but unhealthy.
- `vllm-small` running but still in `health: starting` at snapshot time.

The GPU snapshot showed the expected 8×H200 NVL server, driver `595.58.03`, CUDA `13.2`, and high VRAM occupancy from Kimi/vLLM workers.

### 2. T8 — LiteLLM Proxy overhead

This is the cleanest evidence from the session.

Captured paired direct/proxy measurements for both models:

- Kimi-K2.6:
  - direct path: `http://127.0.0.1:8000`
  - proxy path: `http://127.0.0.1:4000`
  - 10 direct files and 10 proxy files.
- DeepSeek-V4-Flash:
  - direct path: `http://127.0.0.1:8004`
  - proxy path: `http://127.0.0.1:4000`
  - 10 direct files and 10 proxy files.

Artifacts:

- `t8_proxy_overhead/kimi_1_A_direct.json` ... `kimi_10_A_direct.json`
- `t8_proxy_overhead/kimi_1_B_proxy.json` ... `kimi_10_B_proxy.json`
- `t8_proxy_overhead/ds_1_A_direct.json` ... `ds_10_A_direct.json`
- `t8_proxy_overhead/ds_1_B_proxy.json` ... `ds_10_B_proxy.json`
- `t8_proxy_overhead/litellm_metrics_post.txt`

Representative sample values:

| Model | Path | Example file | TTFT | Any-token TTFT | E2E | completion_tokens | Notes |
|---|---|---|---:|---:|---:|---:|---|
| Kimi-K2.6 | direct | `kimi_1_A_direct.json` | ~0.625 s | ~0.242 s | ~0.625 s | 46 | Direct vLLM stream includes reasoning text before final answer (`reasoning_chars`=189, `output_chars`=3). |
| Kimi-K2.6 | proxy | `kimi_1_B_proxy.json` | ~0.652 s | ~0.652 s | ~0.666 s | 46 | Proxy collapses reasoning chunks into the final stream (`reasoning_chars`=0, `output_chars`=3). |
| DeepSeek-V4-Flash | direct | `ds_1_A_direct.json` | ~0.278 s | ~0.278 s | ~0.442 s | 2 | Short `OK` output; throughput metrics are not meaningful at this length. |
| DeepSeek-V4-Flash | proxy | `ds_1_B_proxy.json` | ~0.304 s | ~0.304 s | ~0.465 s | 2 | Short `OK` output; throughput metrics are not meaningful at this length. |

Interpretation should be done as paired deltas, not from single examples. The sample values suggest small proxy overhead for short single-stream requests, but the W1 write-up should avoid generalizing beyond this workload.

Recommended laptop-side analysis:

- Parse all 40 T8 JSON files.
- Pair files by model and index.
- Compute `proxy - direct` for:
  - `ttft_seconds`,
  - `ttft_any_token_seconds`,
  - `e2e_seconds`,
  - `output_tokens_per_second`.
- Report median, p90/p95 if meaningful, min/max, and outliers.
- Explicitly state that this is a single-stream smoke-style overhead check, not a production throughput benchmark.

### 3. T3 — DeepSeek VRAM baseline only

Captured:

- `t3_deepseek_vram/log_cap020_baseline.txt`
- `t3_deepseek_vram/ttft_cap020.json`

The TTFT file records a completed DeepSeek direct request against `:8004` with:

- `ttft_seconds`: ~0.328 s
- `e2e_seconds`: ~0.521 s
- `completion_tokens`: 2
- `total_tokens`: 8

However, this is not a full VRAM cap sweep. The planned `0.15` and `0.25` comparison did not complete.

Critical caveat:

The filename says `cap020`, but the committed DeepSeek startup log shows `gpu_memory_utilization: 0.25`. Therefore, for W1 this artifact should be described as a **runtime 0.25 baseline captured under a misleading filename**, unless a later audit proves the actual environment was different.

Additional useful log details:

- vLLM version: `0.20.0`.
- Model: `deepseek-ai/DeepSeek-V4-Flash`.
- Tensor parallelism: `8`.
- KV cache dtype: `fp8`.
- Speculative config: MTP with `num_speculative_tokens=1`.
- `max_model_len`: `65536`.
- `max_num_seqs`: `2`.
- `max_num_batched_tokens`: `2048` (vLLM warned this may be suboptimal given the speculative settings).
- `block_size`: `256`.
- `enforce_eager`: `True` (no CUDA graph capture; runtime numbers are eager-mode).
- Model loading took ~22 s and ~20.32 GiB memory according to the log.
- Available KV cache memory was reported as ~13.5 GiB.
- GPU KV cache size was reported as 10,996 tokens.

These are useful as supporting evidence, but not enough to justify the final DeepSeek cap choice. A clean T3 rerun is still needed.

## What was not completed

### T3 — full VRAM sweep

Not completed:

- Explicit `DEEPSEEK_GPU_MEM_UTIL=0.15` run.
- Explicit `DEEPSEEK_GPU_MEM_UTIL=0.20` run with matching filenames/logs.
- Explicit `DEEPSEEK_GPU_MEM_UTIL=0.25` run with matching filenames/logs.
- Comparative notes explaining which cap is too low, acceptable, or too risky.

### T6 — Kimi Eagle3 ON/OFF

Not completed:

- Kimi benchmark with Eagle3 ON.
- Kimi restart without Eagle3.
- Kimi benchmark with Eagle3 OFF.
- Restore/smoke after returning to Eagle3 ON.

No `t6_eagle3/` artifact set was produced in this session.

### T1 — Kimi DEP startup failure capture

Not completed:

- DEP/DP override run.
- `dep_startup.log`.
- `dep_full.log`.
- `dep_engine_cmd.json`.
- `dep_state.txt`.

No `t1_dep/` artifact set was produced in this session.

### T5 — dashboard / Prometheus validation

Not completed:

- No full dashboard screenshot.
- No Prometheus query snapshots under load.
- No raw Kimi/DeepSeek `/metrics` capture for T5.
- The single attempted proxy-side capture (`t8_proxy_overhead/litellm_metrics_post.txt`) returned a 22-byte HTTP 404 (`{"detail":"Not Found"}`), not a metric snapshot. The LiteLLM Prometheus exporter likely needs `prometheus_callback` enabled in `serving/compose/litellm-config.yaml`, or the scrape used the wrong endpoint. T8 therefore has no proxy-side cross-check from this dataset either.

This is acceptable for this session because T5 was stretch-only, but issue #34 remains open and the LiteLLM exporter configuration needs to be fixed before the next capture attempt.

### End-of-session close-out

Not captured in the original server commit:

- `session/docker_ps_end.txt`
- `session/nvidia_smi_end.txt`
- original `session/artifact_manifest.txt`
- original `session/session_notes.md`

This file and `artifact_manifest.txt` were added later as cleanup documentation.

## Repository hygiene observations

### Run directory typo (resolved)

The run directory was originally committed as
`results/runs/2026-05-27_w1_ewidence` (typo). Resolved by a later
`git mv` commit moving the tree to `results/runs/2026-05-27_w1_evidence`.
All current paths in this document and in `artifact_manifest.txt` reflect
the corrected name.

### Historical 2026-05-19 artifacts included

The same server-session commit also added older DeepSeek benchmark artifacts:

- `results/runs/2026-05-19_deepseek-v4-flash_run-03`
- `results/runs/2026-05-19_deepseek-v4-flash_run-04`
- `results/runs/2026-05-19_deepseek-v4-flash_run-05`
- `results/runs/2026-05-19_deepseek-v4-flash_run-06`

Treat these as recovered historical artifacts, not as work produced during the 2026-05-27 session.

One of these, `run-03`, is a useful negative artifact because it records an invalid URL issue (`http://127.0.0.1:1:4000`). Runs `04..06` are successful DeepSeek bench-suite artifacts from the earlier 2026-05-19 work.

### Compose changed during the server commit

The server commit also modified `serving/compose/docker-compose.kimi-k2.6.yml`:

- Kimi:
  - `--gpu-memory-utilization` changed from `0.7` to `0.65`.
  - `--max-num-seqs 1` added.
  - `--max-model-len 131072` added.
- DeepSeek:
  - `--max-num-batched-tokens` changed from `4096` to `2048`.
  - default `DEEPSEEK_GPU_MEM_UTIL` changed from `0.20` to `0.25`.

This should be reflected carefully in W1. Avoid claiming the session validated a 0.20 DeepSeek cap unless a clean artifact proves it.

## File inventory

### Session files

| File | Purpose |
|---|---|
| `session/start_commit.txt` | Commit SHA at the start of the server session. |
| `session/docker_ps_start.txt` | Starting container state. |
| `session/nvidia_smi_start.txt` | Starting GPU/driver/VRAM/process state. |
| `session/session_notes.md` | Human-readable session summary and caveats. |
| `session/artifact_manifest.txt` | File manifest for the 2026-05-27 run directory. |

### T8 files

| File group | Purpose |
|---|---|
| `t8_proxy_overhead/kimi_*_A_direct.json` | Direct Kimi measurements against vLLM `:8000`. |
| `t8_proxy_overhead/kimi_*_B_proxy.json` | Kimi measurements through LiteLLM Proxy `:4000`. |
| `t8_proxy_overhead/ds_*_A_direct.json` | Direct DeepSeek measurements against vLLM-small `:8004`. |
| `t8_proxy_overhead/ds_*_B_proxy.json` | DeepSeek measurements through LiteLLM Proxy `:4000`. |
| `t8_proxy_overhead/litellm_metrics_post.txt` | HTTP 404 captured after the T8 measurement loop (22 B, `{"detail":"Not Found"}`). LiteLLM Prometheus exporter not reachable from the scrape command used in this session; T8 has no proxy-side cross-check. |

### T3 files

| File | Purpose |
|---|---|
| `t3_deepseek_vram/log_cap020_baseline.txt` | DeepSeek/vLLM-small startup/runtime log; filename says cap020, runtime log shows cap 0.25. |
| `t3_deepseek_vram/ttft_cap020.json` | Single DeepSeek direct TTFT smoke result; filename caveat applies. |

## Assessment against the plan

The session was productive but incomplete.

Useful evidence now exists for:

- T8 paired proxy-overhead analysis.
- A partial DeepSeek runtime/configuration baseline.
- Server state at the start of the run.

Evidence still missing for W1:

- Clean T3 VRAM cap sweep with consistent filenames and runtime config.
- T1 DEP startup failure proof.
- T6 Eagle3 ON/OFF comparison.
- Full T5 dashboard/Prometheus validation.

For W1, the safe wording is:

> The 2026-05-27 server session completed paired direct-vs-proxy measurements for Kimi and DeepSeek. It partially captured DeepSeek runtime evidence, but the VRAM-cap artifact needs cleanup because the filename and runtime configuration disagree. DEP failure and Eagle3 ON/OFF evidence remain to be collected.

## Next recommended work

1. Fix the run-directory typo locally using `git mv`.
2. Analyze the T8 paired direct/proxy deltas on the laptop.
3. Add a small T8 summary table to the W1 write-up.
4. Schedule a follow-up server slot for missing evidence:
   - T3: explicit `0.15`, `0.20`, `0.25` runs with filenames matching actual runtime caps.
   - T1: DEP startup failure capture.
   - T6: Kimi Eagle3 ON/OFF benchmark.
5. Defer full T5 dashboard validation until after the W1 evidence core is coherent.
