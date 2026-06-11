# Kimi-K2.6 TP8 decode under torch profiler — 2026-06-11 (Cz. B)

Issue #50: NCCL share of the Kimi decode step, measured directly. Source:
`results/runs/2026-06-11_bottleneck/kimi_profiler/` (commit `e5f02a5`); raw
traces (8 ranks, `.json.gz`) stay outside the repo at
`/home/working/nanoserve-tracing` on ubuntusrv2 (repo policy).

## Setup

vLLM v0.20 removed `VLLM_TORCH_PROFILER_DIR` (the plan's original mechanism;
caused a `/start_profile` 404). Profiler enabled via engine flag
`--profiler-config='{"profiler":"torch","torch_profiler_dir":"/tmp/vllm_profile"}'`
(compose command override, `engine_cmd.json` verified). One c=1 request
(`measure_ttft_once`, max_tokens 256, 15-token prompt) between
`/start_profile` and `/stop_profile`. Production config otherwise: TP=8 +
Eagle3, `--gpu-memory-utilization 0.6`.

## Control: profiler overhead is small

| | profiled request | restore smoke (no profiler) |
|---|---:|---:|
| e2e s | 5.21 | 4.93 |
| completion tokens | 189 | 190 |
| TPOT(any) ms/tok | 20.1 | 19.0 |
| TTFT(any) s | 1.44 | 1.35 |

Same prompt, same day, ~5% overhead → the trace timeline reflects real
behavior. (Both runs: ~73–78 chunks at ~2.6 tok/chunk — Eagle3 acceptance
consistent with T6.)

## Trace split (rank 0, span 5.06 s ≈ the whole request)

| bucket | time | share of span | per output token |
|---|---:|---:|---:|
| **gaps (no GPU kernel)** | 3.18 s | **63%** | 16.8 ms |
| comms (NCCL) kernels | 1.14 s | 22.5% | 6.0 ms |
| compute kernels | 0.46 s | 9.1% | 2.4 ms |
| other kernels | 0.28 s | 5.6% | 1.5 ms |

Step framing: 189 tokens / ~2.6 accept ≈ ~73 decode steps → ~50 ms/step, of
which ~11 ms is NCCL kernel time and ~32 ms is GPU idle.

## Verdict (plan's criteria table, row 3)

**Kimi TP8 decode at c=1 is NOT comms-bound — it is floor-bound.** Comms is
22.5% of wall (below the ~40% threshold for "comms-bound wprost"); gaps
dominate at 63%. The per-step floor (host scheduling, kernel launch, Eagle3
draft orchestration, sampling) is the primary limiter — the same conclusion
the Qwen TP-curve reached independently (TP1 c=1: 9 ms step at SMACT 0.46;
TP8 comms tax 37% of step). Two independent methods, one answer.

Notes:
- NCCL kernel time includes in-kernel peer-wait, so 22.5% is an *upper*
  bound on pure transfer time.
- Compute kernels are only 9% of wall — consistent with the Qwen counters
  story (silicon mostly idle during TP8 decode).
- Rank 0 is the driver (extra host work); cross-rank check not run — minor
  caveat, symmetric collectives make rank 0 representative for comms.

## #50 implication

Amdahl bound for a perfect interconnect on Kimi TP8 interactive (c=1):
**≤ 1/(1−0.225) ≈ 1.3×** — and realistically less, since part of the NCCL
kernel time is peer-sync that a faster link does not remove and NVLink 4-way
still crosses UPI between islands. Combined with the Qwen curve (TP2 optimum,
NVLink gain ≈ 0 at TP≤2, big gains only in regimes one shouldn't run), the
measured data points to **NO-GO for the NVLink purchase if the motivation is
interactive Kimi latency**. The remaining open case is batched Kimi serving
(c≫1), which this session did not profile (stretch c=8 was cut) — Qwen c=64
suggests comms share grows steeply there, but for Kimi it is extrapolation,
not measurement.

The bigger lever per these numbers is the per-step floor (63% of wall):
host/launch/speculative orchestration — software, not cables.

## Session close-out

Restore verified: plain compose force-recreate, no `profiler-config` in Cmd,
smoke test completed=True. Full artifact manifest:
`results/runs/2026-06-11_bottleneck/session/artifact_manifest.txt`.
