# Qwen3.6-35B-A3B TP-curve on PCIe-only 8×H200 — 2026-06-11 session (commit A)

Issue #50 calibration data. Source artifacts:
`results/runs/2026-06-11_bottleneck/qwen_tp_curve/` (TP2/TP4/TP8 + A4, this
session, commit `363b965`) and `results/runs/2026-06-10_extra/p0_gpu_counters/`
(TP1 anchor, 2026-06-10). Same image (`vllm/vllm-openai:v0.20.0-cu130`), same
model + MTP speculative config (`num_speculative_tokens=3`), same workloads:

- **c=1**: `random` 64-in/512-out, 40 prompts, `--ignore-eos`, 3 warmups
- **c=64**: SWE-bench custom dataset, 256-out, 600 prompts, `--ignore-eos`

All runs verified at runtime (`verify_tp*.txt` = `tensor_parallel_size=` from
the engine log; placement from `engine_env_*.txt` + per-GPU dcgmi power).
600/600 and 40/40 requests completed in every run.

## Topology context (`session/nvidia_topo.txt`)

GPU pairs {0,1} {2,3} {4,5} {6,7} share a PCIe switch (PIX); pairs within
{0–3} / {4–7} share a socket (NODE); the two quads talk over UPI (SYS).
Placements measured: TP2 → GPU{0,1} (PIX), TP4 → GPU{0–3} (NODE), TP8 → all
(SYS), A4 → GPU{0,4} (SYS, 2 ranks). Confirmed live: non-participant GPUs
stayed at idle power (~70 W) in every window.

## Client metrics

### c=1 (median; ITL ≈ decode-step time under MTP)

| TP | link class | TTFT ms | TPOT ms | ITL ms | step est. (TPOT×accept) | accept len |
|---|---|---:|---:|---:|---:|---:|
| 1 | — | 35.9 | 3.68 | 8.98 | — | n/a (log capped) |
| 2 | PIX | 42.1 | 3.65 | 9.91 | 9.62 | 2.64 |
| 2 (A4) | **SYS/UPI** | 32.6 | 3.51 | 9.13 | 9.27 | 2.64 |
| 4 | NODE | 54.5 | 4.00 | 10.54 | 10.96 | 2.74 |
| 8 | SYS | 84.9 | 5.12 | 14.16 | 14.13 | 2.76 |

Acceptance length is token-weighted from `SpecDecoding metrics` log lines
matched to the bench epoch windows — stable across TP, so TPOT/ITL deltas are
not a speculation artifact.

### c=64 (600 prompts)

| TP | TPOT med ms | ITL med ms | out tok/s | tok/s/GPU | scaling eff. | TTFT med s | accept len |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 21.6 | 23.1 | 1202 | 1202 | 100% | 6.4 | n/a |
| 2 | 18.1 | 21.0 | **1404** | 702 | 58% | 5.8 | 2.34 |
| 4 | 38.0 | 53.7 | 680 | 170 | 14% | 11.3 | 2.55 |
| 8 | 91.9 | 198.5 | 257 | 32 | 2.7% | 22.0 | 2.81 |

(TTFT at c=64 includes queueing of the 600-request backlog; it tracks
throughput, not pure prefill.)

## GPU counters (dcgmi, mean over participating GPUs per window)

| config | power W | SMACT | TENSO | DRAMA | PCIe RX GB/s |
|---|---:|---:|---:|---:|---:|
| idle (06-11) | 70–73 | — | — | — | — |
| TP1 c1 (active-filtered) | 270 | 0.461 | 0.022 | 0.284 | 0.08 |
| TP1 c64 (active-filtered) | 436 | 0.665 | 0.117 | 0.385 | 0.07 |
| TP2 c1 | 172 | 0.202 | 0.014 | 0.119 | 0.57 |
| TP2 c64 | 255 | 0.359 | 0.054 | 0.171 | 6.25 |
| TP4 c1 | 133 | 0.118 | 0.005 | 0.056 | 2.73 |
| TP4 c64 | 142 | 0.118 | 0.014 | 0.048 | 5.65 |
| TP8 c1 | 117 | 0.076 | 0.004 | 0.023 | 3.52 |
| TP8 c64 | **111** | **0.053** | 0.003 | **0.011** | 7.18 |

TP1 numbers re-aggregated with an activity filter (power > 110 W) because the
06-10 session appended idle tail samples to the window files (documented
errata). 06-11 windows are cut at bench end; their c1 windows carry ~20 s of
bench startup lead-in (slight dilution, direction: underestimates activity).

## Derived: per-step decode comms tax (c=1, latency regime)

Step time ≈ ITL median (MTP emits accepted bursts; both estimators agree
within 0.5 ms). Δstep vs TP1 floor (8.98 ms) is a **lower bound** on comms
cost (per-rank silicon work can only shrink with TP):

| config | step ms | Δ vs TP1 | step share |
|---|---:|---:|---:|
| TP2 PIX | 9.91 | +0.93 | 9% |
| TP2 SYS (A4) | 9.13 | +0.15 | ~2% (within run-to-run noise) |
| TP4 NODE | 10.54 | +1.56 | 15% |
| TP8 SYS | 14.16 | +5.18 | 37% |

At c=64 (bandwidth regime), Δstep vs TP1 (23.1 ms): TP2 **−2.1 ms** (net win —
silicon split outweighs comms at 2 ranks), TP4 **+30.6 ms**, TP8 **+175 ms**.

## Findings

1. **TP2 is the serving optimum for this model on this box.** +17% throughput
   at c=64 vs TP1 and −16% TPOT; everything beyond TP2 is a regression.
2. **Decode at TP≥4 is comms-bound, proven causally** (dose = rank count at
   constant model): TPOT and step time grow monotonically while per-GPU power
   collapses toward the idle floor (TP8 c64: 111 W vs 70–73 W idle, SMACT
   0.053, DRAMA 0.011) with sustained PCIe traffic (RX 5.7–7.2 GB/s). GPUs are
   starved by the interconnect, not busy.
3. **No measurable UPI tax at 2 ranks / small messages (A4).** TP2 on a
   cross-socket pair (SYS) matched — actually slightly beat — the same-switch
   pair (PIX) at c=1 (9.13 vs 9.91 ms step; ≤0.8 ms difference is within
   run-to-run noise). At 2 ranks the per-step floor dominates and link class
   is irrelevant. The TP4→TP8 cliff therefore cannot be attributed to UPI
   alone from this data; rank count (collective fan-out, EP all-to-all width)
   is the stronger dose variable. The Kimi trace (Cz. B) should split
   rounds×latency vs link.
4. **Per-step floor confirmed:** ~9 ms/step at TP1 c=1 with zero comms and
   SMACT 0.46 — i.e. roughly half the step is host/launch/MTP overhead even
   before any TP. This is the `F_host` of the #50 model and caps any
   interconnect upgrade gain at c=1.
5. **Amdahl bounds for an NVLink upgrade (Qwen, this model class):** comms
   share ≥37% of step at TP8 c=1 → ≤1.6× from a perfect interconnect at
   interactive load; ≥85% at TP8 c=64 → up to ~7× there, but the practical
   answer is "don't run this model at TP8 — run TP2". NVLink would have to
   beat TP2-on-PCIe (1404 tok/s), not TP8-on-PCIe (257 tok/s).

## #50 model inputs measured here

- `F_host` ≈ 4.8–9 ms/step at c=1 (9 ms step × SMACT 0.46 silicon split;
  refine with Cz. B trace gaps).
- Net per-step comms tax (c=1): +0.9 ms (2 ranks PIX), +0.2 ms (2 ranks UPI),
  +1.6 ms (4 ranks), +5.2 ms (8 ranks). Per-round `r` division deferred until
  the Kimi trace fixes `N_rounds` per step.
- Scaling efficiency (c=64): 100% / 58% / 14% / 2.7% for TP1/2/4/8.

## Caveats

- TP1 anchor ran 2026-06-10 on the older compose: no explicit
  `--max-num-batched-tokens 8192` (engine default applied) and port 8008;
  decode-side comparison unaffected, prefill batching nominally identical.
- TP1 acceptance length not recoverable (capped log without SpecDecoding
  lines); TP1 step time uses ITL median only.
- c=1 dcgmi windows include ~20 s bench startup lead-in (counters slightly
  underestimate activity; does not affect client metrics).
- Single run per configuration; the A4-vs-TP2 difference (0.8 ms) should be
  read as "no detectable penalty", not "UPI is faster".

## Cz. C addendum — `NCCL_P2P_DISABLE=1` dose-response at TP2: NEGATIVE

Data: `bench_tp2_nop2p/` + `qwen_tp2_nop2p_*_dcgmi.txt` (commit `fab5e0b`).
Verified: `NCCL_P2P_DISABLE=1` in container env **and** acknowledged by NCCL
in the engine log (`verify_nop2p_env.txt`, `verify_nop2p_log.txt`);
`tensor_parallel_size=2` confirmed.

| metric | TP2 (P2P on) | TP2 nop2p | Δ |
|---|---:|---:|---:|
| c1 step (ITL med) ms | 9.91 | 9.54 | −0.4 (noise) |
| c1 TPOT med ms | 3.65 | 3.70 | +0.05 |
| c64 TPOT med ms | 18.09 | 17.09 | −1.0 (noise) |
| c64 out tok/s | 1404 | 1396 | −0.6% |
| c64 power/GPU W / SMACT | 255 / 0.359 | 249 / 0.340 | ≈ |
| accept len c1 / c64 | 2.64 / 2.34 | 2.62 / 2.42 | ≈ |

Forcing the worst comms path (host staging instead of P2P through the shared
PCIe switch) changes **nothing measurable** at TP2, in either regime. This is
the plan's criteria row 4: *at 2 ranks communication is cheap — the limiter is
the per-step floor*, now shown causally (degrading the link doesn't hurt →
upgrading it won't help: **NVLink gain at TP2 ≈ 0, causally supported**). The
TP4/TP8 collapse is therefore about rank-count scaling of collectives (fan-out
hops, EP all-to-all width), not the P2P-vs-host path of a pair.

**Bonus — noise calibration:** three independent TP2 engine starts (tp2,
tp2x04, tp2_nop2p) give run-to-run spread: c1 step ±0.4 ms, c1 TPOT ±0.1 ms,
c64 TPOT ±0.5 ms. On this band: the A4 "SYS faster than PIX" difference is
firmly noise (as assumed), while the TP4 (+1.6 ms) and TP8 (+5.2 ms) c1 step
deltas are ~4× and ~13× the noise band — solidly real.

## Still owed (rest of the session plan)

Cz. B (Kimi TP8 torch profiler → NCCL share + `N_rounds`), Cz. D (restore +
close-out). After B: recompute the #50 NVLink table with measured `r` and
`F_host`.
