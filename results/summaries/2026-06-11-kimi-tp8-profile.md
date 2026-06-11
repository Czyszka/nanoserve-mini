# Kimi-K2.6 TP8 decode under torch profiler — 2026-06-11 (Cz. B)

Issue #50: NCCL share of the Kimi decode step, measured directly. Primary
source: `results/runs/2026-06-11_bottleneck/kimi_profiler/` (commit
`e5f02a5`). The overhead control and restore check are in
`results/runs/2026-06-11_bottleneck/session/restore_smoke.json` and
`restore_engine_cmd.json`. Raw traces (8 ranks, `.json.gz`) stay outside the
repo at `/home/working/nanoserve-tracing` on ubuntusrv2 (repo policy).

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
| request max_tokens | 256 | 1024 |
| TPOT(any) ms/tok | 20.1 | 19.0 |
| TTFT(any) s | 1.44 | 1.35 |

Same prompt, same day; the restore smoke used a larger `max_tokens` cap, but
both requests naturally stopped at the same output length (189/190 completion
tokens). E2E overhead is 5.6% and TPOT(any) overhead is 5.8%, so the trace
timeline is close enough to real behavior for a coarse attribution. The two
runs produced 72/78 chunks, or ~2.4–2.6 tokens per chunk, consistent with
Eagle3 acceptance from T6.

## Trace split (rank 0, span 5.06 s ≈ the request window)

| bucket | time | share of span | per output token |
|---|---:|---:|---:|
| **gaps (no GPU kernel)** | 3.18 s | **63%** | 16.8 ms |
| comms (NCCL) kernels | 1.14 s | 22.5% | 6.0 ms |
| compute kernels | 0.46 s | 9.1% | 2.4 ms |
| other kernels | 0.28 s | 5.6% | 1.5 ms |

Step framing: the profiled request's decode interval is `e2e - TTFT(any) =
5.208 - 1.436 = 3.77 s`. With 189 output tokens and ~2.6 tokens accepted per
verify, that is ~73 decode steps and **~52 ms/step** (rounded to ~50 ms).
Mapping the rank-0 span shares onto that step frame gives a coarse per-step
reading of ~32 ms GPU idle, ~11 ms NCCL kernel time, and ~4.7 ms compute; this
is a share-based estimate, not a separately isolated per-step slice.

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
