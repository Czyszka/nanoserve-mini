# T9 — What actually limits decode on this node, and would NVLink 4-way pay off?

Mode: investigation + decision analysis. **Status: COMPLETE** — measurements
closed 2026-06-12, verdict delivered; goal tracked in
[#50](https://github.com/Czyszka/nanoserve-mini/issues/50). Structure follows
the project's 13-point technical-note template (problem → evidence →
analysis → decision).

**Scope boundary with W2:** T9 is the engineering record of the bottleneck
attribution and the NVLink decision. The full TP-scaling study (sweet spot
across model classes, throughput curves, the W2 roadmap article) will
*synthesize from* this thread, not re-run it.

## 1. Problem

Two questions, both of which must end with numbers rather than adjectives:

1. **What is the current bottleneck of decode on this PCIe-only 8×H200 node?**
   A named mechanism at L2 (one-lever counterfactual or direct kernel-level
   attribution) — not a correlation.
2. **Would buying NVLink 4-way bridges pay off — for which TP configurations
   (1/2/4/8) and workload shapes (interactive c=1 vs batched), and by roughly
   how much?** A calibrated per-scenario estimate good enough to support a
   purchase decision.

## 2. Observation of the problem + the delivery-run analogy

The opening observation (2026-06-10, DCGM counters under load): the node
serves at full tilt while **every hardware resource idles** — `DRAM_ACTIVE`
0.07–0.09, SMs ~20% busy (against nvidia-smi's misleading "100% util"), PCIe
at 6–8 GB/s ≈ 10–13% of Gen5 x16, power 169–199 W of 600 W. Throughput
stalls, yet nothing is saturated. That is the latency/serialization
signature: the step time is spent in many small synchronous rounds and fixed
per-step costs, not in any bandwidth limit.

*(The analogy below is deliberately informal — a learning aid for reading
every number in this thread. Each claim maps to a measurement.)*

One decode step = **one delivery run** of a courier van.

1. **Driving** = the GPU doing math (compute kernels, `SM_ACTIVE`).
2. **Cargo swaps at roundabouts** = inter-GPU communication. Under TP the
   vans drive in convoy and *must* stop together at ~2 roundabouts per layer
   (all-reduce) to merge partial loads; with MoE/EP they also re-sort parcels
   between vans (all-to-all). Roads = PCIe today; NVLink = a private highway.
3. **Paperwork before the wheels turn** = the **per-step floor** (`F_host`):
   taking the order, the dispatcher deciding what goes into this run
   (scheduler step, Python), starting the engine for each leg (kernel
   launches), the speculative-decoding ritual (draft parcels, then check
   which ones the customer accepts), signing the receipt (sampling,
   detokenize, stream out). This cost is paid **once per run, regardless of
   engine power or road quality**.

How the measurements read in this language:

- **Kimi TP8, one user (c=1):** the run takes ~50 ms; the engine works ~9%
  of it, roundabouts ~22%, and **63% is standing with the engine off**,
  waiting for paperwork (trace 2026-06-11: gaps 63 / NCCL 22.5 / compute 9).
  That is "floor-bound".
- **Why NVLink barely helps here:** a highway only shortens the roundabout
  part (~22%). Even a teleporter caps the gain at ~1.3× when most of the run
  is paperwork.
- **Why more GPUs made one user *slower* (TP1→TP8 c=1):** add vans to the
  convoy and each carries a smaller parcel (driving shrinks), but the
  waybill is still issued once per run at the same speed — and you added
  roundabouts. Measured: step 9.0 → 14.2 ms.
- **Why heavy traffic flips the story:** pack 64 parcels into one run and the
  paperwork cost is split 64 ways — the floor stops mattering. But the
  roundabouts now jam (collective payloads grow with batch), so comms
  dominates: Kimi TP8 batched spends **84% of the wall in NCCL**
  (trace @c=16), vans at near-idle power.
- **The floor investigation (F-series)** asked *what exactly* the driver
  waits on — and answered it with doses: the waybill ritual (speculative
  orchestration: **40% of the floor**), restarting the engine per leg
  (launch overhead: cudagraphs already mask ~46 ms/step of it), while the
  dispatcher's power-saving mode (CPU governor) was **exonerated**.

## 3. Glossary (terms as used in this thread)

**Parallelism and communication**

- **rank** — one GPU's worker process in a distributed job. TP=8 means 8 ranks,
  one per GPU, cooperating on every forward pass.
- **TP (tensor parallelism)** — every weight matrix is split across all ranks;
  each GPU computes a slice of every layer, so the slices must be merged after
  (almost) every layer. That merging is communication.
- **EP (expert parallelism)** — only the MoE experts are split across ranks;
  tokens are *routed* to whichever rank owns the chosen expert and the results
  routed back.
- **comms** — shorthand for all inter-GPU communication (all-reduce,
  all-to-all, …) as opposed to computation or memory reads.
- **all-reduce** — the collective operation that merges TP partial results:
  every rank contributes its piece and every rank ends up with the same summed
  result. In the Megatron-style TP model this creates ~2 forward reduction
  points per decoder layer (attention output + FFN/MoE output). For Kimi this
  is an architecture estimate, not a counted NCCL-op measurement: MoE/EP can
  add all-to-all traffic, and runtime fusion can change the exact operation
  count. It is *synchronous*: no rank continues until it completes.
- **all-to-all** — the collective behind EP routing: each rank sends a
  different chunk to each other rank (token dispatch to experts, then combine
  back).
- **NCCL** — NVIDIA Collective Communications Library; the library vLLM/PyTorch
  use to implement all-reduce/all-to-all on NVLink or PCIe. "NCCL kernels" in a
  profiler trace = time spent communicating (or waiting for the slowest rank).
- **P2P (peer-to-peer)** — GPUs exchanging data directly over PCIe without
  bouncing through CPU RAM. `NCCL_P2P_DISABLE=1` forces the slower
  through-host path — our dose-response lever.
- **small-message regime** — at batch 1 the payload used in this model is only
  ~14 KiB for one hidden-state vector (`hidden_size 7168 × BF16 2 B =
  14,336 B`), before protocol overhead and any fusion. This is a
  public-config-derived estimate, not a local measurement, so its duration is
  set by fixed per-operation latency (launch + protocol + link round-trips),
  not by link bandwidth. That is why a *latency*-bound link can look idle in
  *throughput* counters.

**Time accounting (the model's terms)**

- **decode step** — one forward pass of the whole model during generation.
  Without speculation 1 step = 1 token; with speculation (Eagle3/MTP) one
  verify step can emit ~2–3 tokens.
- **TPOT / ITL** — time per output token / inter-token latency. With
  speculation, ITL ≈ time per *step* (tokens arrive in bursts), while TPOT
  divides by all tokens.
- **F_host, the per-step "floor" ("podłoga")** — the fixed cost every step
  pays regardless of communication: the engine's scheduler iteration, sampler,
  CPU↔GPU synchronization, kernel-launch gaps, speculative-draft bookkeeping.
  We know it exists because Qwen at TP=1 — with *zero* comms — still takes
  ~9 ms/step while the GPU idles half the time.
- **N_rounds** — how many synchronous communication rounds one step performs.
  For Kimi this is a config/literature-derived estimate: public Kimi K2 config
  has 61 decoder layers, and Megatron-style TP has ~2 forward all-reduce
  points per layer → ~122 TP reduction points before MoE/EP collectives and
  runtime fusions. It is not a measured NCCL operation count.
- **r(link, ranks)** — the latency of one such round; depends on the link type
  (PCIe vs NVLink vs UPI path) and how many ranks participate.
- **W_silicon** — time the GPU actually works per step: HBM weight/KV reads +
  arithmetic. Measured small as a share of the traces (Kimi c=1 compute 9.1%,
  ~4.6 ms/step; Kimi c=16 compute 4.6% of span), not the earlier rough
  1–2 ms shortcut.
- **X-bound (bandwidth-/latency-/compute-bound)** — "the step time is limited
  by X": making X faster makes the step faster, making anything else faster
  does not.
- **capture** — the fraction of the comms cost that an NVLink island can
  actually absorb: 1.0 when all ranks fit one island (TP≤4), ≈0.75 for TP=8
  split 4+4 (inter-island ring legs stay on PCIe/UPI).

**Hardware paths on this server**

- **PCIe root complex / PCIe switch** — the root is the CPU's PCIe controller;
  a switch fans one x16 link out to several devices. Here: 4 switches, 2 GPUs
  each, 2 switches per CPU.
- **UPI** — Ultra Path Interconnect, the link *between the two CPU sockets*.
  A GPU0↔GPU4 transfer crosses it: GPU→switch→CPU0→UPI→CPU1→switch→GPU.
- **NUMA / SNC** — memory locality domains; SNC-2 splits each socket into two
  NUMA nodes (4 total here). Matters for CPU-side placement, secondary for
  GPU↔GPU.
- **NVLink bridge / island** — a physical connector joining 2 or 4 adjacent
  GPUs with a direct GPU↔GPU link (~10× lower latency, ~10× higher bandwidth
  than PCIe). 4-way bridges would create two 4-GPU "islands"; traffic *inside*
  an island avoids PCIe entirely.
- **hierarchical all-reduce** — how an 8-rank all-reduce runs on 2 islands:
  reduce inside each island over NVLink, exchange between islands over PCIe,
  broadcast back inside. The inter-island PCIe hop is why NVLink helps TP=8
  only partially.

**Measurement vocabulary**

- **DCGM / `dcgmi`** — NVIDIA's datacenter GPU telemetry; our counters:
  `SM_ACTIVE` (fraction of time the compute units have work resident),
  `PIPE_TENSOR_ACTIVE` (tensor cores busy), `DRAM_ACTIVE` (HBM memory system
  busy), `PCIE_TX/RX` (bytes/s on the PCIe link).
- **kernel / gap** — a kernel is one GPU program execution; a gap is wall time
  with *no* kernel resident (the GPU waits for the host or for a dependency).
  The profiler trace splits a step into NCCL kernels / compute kernels / gaps.
- **torch profiler trace** — a timeline of every kernel and host event,
  captured via the `--profiler-config` engine flag + `/start_profile`
  (vLLM ≥0.20; the older `VLLM_TORCH_PROFILER_DIR` env was removed upstream —
  lesson from 2026-06-11); our direct attribution tool.
- **dose-response** — a causal test: deliberately worsen the suspected cause
  (e.g. disable P2P so every comm round gets slower) and check the effect
  moves proportionally.

## 4. Hardware infrastructure

The platform (Supermicro SYS-521GE-TNRT) is **dual-root PCIe, no NVLink, no
NVSwitch** (confirmed by vLLM logs: custom all-reduce *"not supported on more
than two PCIe-only GPUs"*): 2× Xeon Gold 6530 (128 CPUs, governor
`schedutil`, NUMA=4/SNC-2), 8×H200 NVL 143 GB. GPUs sit in four 2-GPU PCIe
switch pairs ({0,1} {2,3} {4,5} {6,7} = PIX), GPU0–3 under CPU0 and GPU4–7
under CPU1 (NODE), cross-socket pairs traverse UPI (SYS). Three link classes
follow — same-switch pair < same-socket < cross-socket via UPI — and TP=8
crosses UPI by construction. The datasheet lists **"GPU-GPU interconnect:
NVIDIA NVLink Bridge, optional"**, so the purchase path is officially
supported; 4-way bridges must pair within sockets → two 4-GPU islands.
Full map: `docs/operations/infrastructure.md` (Topologia GPU/CPU).

Hard model constraint: **Kimi-K2.6 cannot run TP=4** (554.30 GiB / 4 ≈
138.6 GiB/GPU weights alone vs 140.40 GiB board) — TP=8 hierarchical is its
only NVLink configuration.

## 5. Mechanisms under investigation

Per decode step:

```text
T(tp, link) = F_host + N_rounds × r(link, ranks) + W_silicon
```

Three candidate mechanisms, each with its own falsifiable signature:

1. **HBM bandwidth** (`W_silicon` dominated by memory reads) — signature:
   `DRAM_ACTIVE` high under load. *Refuted on day one* (0.07–0.09).
2. **Comms tax** (`N_rounds × r` dominates) — signatures: TPOT grows with
   rank count; NCCL share of the trace span large; PCIe counters pinned at a
   ceiling while silicon idles; dose-response on link quality.
3. **Per-step floor** (`F_host` dominates) — signatures: step time invariant
   to comms levers; gaps dominate the trace; decomposable by doses
   (speculation off, eager mode, CPU governor).

Model anchors available before the closing sessions, with post-audit labels
for estimates: Kimi TP=8 step ≈16.55 ms spec-OFF (T6), `W_silicon`
constrained by traces rather than `DRAM_ACTIVE` alone (~4.6 ms/step compute at
Kimi c=1; 4.6% span at batched c16), `N_rounds` ≥ 122 as a
config/literature-derived estimate (61 layers × ~2 TP reduction points, not a
local NCCL count); Qwen TP1 gives `F_host + W ≈ 9 ms` at zero comms
(model-specific floor).

NVLink-relevant derived quantities: the comms share `s` per scenario, and
`capture` per topology fit (TP≤4 in one island = 1.0; TP=8 hierarchical
≈ 0.75). The ceiling on any interconnect upgrade is an **Amdahl bound**: if
comms is a share `s` of the step, even an *infinitely fast* link caps the
speedup at `1/(1−s)` — with `s = 0.3` the best possible gain is 1.43×, with
`s = 0.6` it is 2.5×. NVLink then realizes *most* of that bound for traffic
inside an island (r drops ~5–10×) and only `capture` of it for hierarchical
TP=8. `r_NVL4 ≈ 20–30 µs` remains a labeled assumption (cloud NVLink rental
was considered and rejected 2026-06-10); the verdict below does not depend
on its exact value inside that range.

**First-pass estimates (pre-registered BEFORE calibration, #50):** kept here
verbatim as the predict→measure record — see §8 for how they fared:

| Config after 2× NVL4 islands (4+4) | Comms path | Predicted gain |
|---|---|---|
| TP=1 | none | 1.0× (none) |
| TP=2 in-island | all NVLink | ~1.3–2× |
| TP=4 in-island (70–200B class) | all NVLink | ~1.6–2.5× |
| TP=8 hierarchical (Kimi's only option) | NVLink intra + PCIe inter | ~1.2–1.5× (modest) |

The prediction's main blind spot, visible already in the table: it carried
**no workload-shape axis** — one number per TP config, no c=1 vs batched
split. The measurements forced that axis in (it turned out to be the
decisive one).

## 6. Methodology — sessions and scenarios

Three executed server sessions, each with a frozen plan (commands, fail-fast
verifies, artifact layout):

1. `docs/plans/2026-06-10-server-session.md` — P0 DCGM counter windows
   (idle / c=1 / c=64) on the production Kimi stack. Opened the question.
2. `docs/plans/2026-06-10-bottleneck-followup-session.md` (executed
   2026-06-11) — **the TP lever + direct attribution**: Qwen3.6-35B-A3B
   TP-curve (TP1/2/4/8, c=1 and c=64, DCGM windows per bench), A4
   cross-socket TP2 placement (`CUDA_VISIBLE_DEVICES=0,4` — link-class dose),
   nop2p (`NCCL_P2P_DISABLE=1` at TP2 — causal comms dose), Kimi TP8 c=1
   torch-profiler trace. Artifacts: `results/runs/2026-06-11_bottleneck/`.
3. `docs/plans/2026-06-11-nvlink-boundary-session.md` (executed 2026-06-11/12)
   — **boundary conditions for the verdict**: K1 Kimi batched ramp
   (c=1/8/16/32 + reproducibility repeat), K2 Kimi trace at batch (c=16),
   Q1 Qwen TP8 ramp (c=4/16 → saturation threshold), Q3 TP4 cross-island
   placement (0,1,4,5 — capture coefficient), Q4 Qwen TP4 trace at batch
   (c=64), F-series floor doses (base / spec-off / eager / governor + TP1
   trace). Artifacts: `results/runs/2026-06-11_nvlink_boundary/`.

Method notes (the controls that make the numbers trustworthy):

- **Client metrics** from `vllm bench serve` (SWE-bench custom dataset,
  256-out, `--ignore-eos`, 2 warmups; `random` 64-in/512-out for c=1 floor
  benches). Bench JSONs report median/mean TTFT, TPOT, ITL, output
  throughput, completion counts.
- **DCGM windows** (`dcgmi dmon -e 155,1002,1004,1005,1009,1010`, 1 s
  cadence) tagged per bench with start/end epoch files; per-GPU means
  computed only over the window; **activity filter** (power > 110 W) used
  where idle tails contaminated a window (TP1 errata of 2026-06-10).
- **Fail-fast verifies before every bench**: requested TP grepped from the
  *full* engine log (`tensor_parallel_size=N`), placement from the
  container env (`CUDA_VISIBLE_DEVICES`), profiler arming from
  `docker inspect … .Config.Cmd` — three real mismatches were caught this
  way during the sessions instead of contaminating results.
- **Traces** via the `--profiler-config` engine flag in a compose command
  override (vLLM v0.20 removed the old env mechanism), short windows
  (1–64 prompts) to keep 4–8-rank traces digestible, copied outside the
  repo (`/home/working/nanoserve-tracing`); only rank-0 text summaries are
  committed. Bucketing: kernel names → `comms` (nccl/all-reduce/all-gather/
  all-to-all) / `compute` (gemm/attn/moe/norm/quant…) / `other`; `gaps` =
  span minus kernel time.
- **Profiler-overhead control on every trace**: the same bench/request with
  and without the profiler — overheads came out ~5% (Kimi c=1), ~2% (Kimi
  c=16), ~8% on ITL (Qwen TP4 c=64), so the timelines reflect real behavior.
- **Reproducibility**: the anomalous Kimi c=16 point was re-run end-to-end
  (fresh engine recreate) before profiling it — ITL med 512 → 525 ms (±3%).
- **Speculation accounting**: Eagle3/MTP acceptance parsed from engine
  `SpecDecoding metrics` log lines, token-weighted, matched to bench epoch
  windows (engine log timestamps are **UTC** — an off-by-timezone bug was
  caught and fixed during analysis). Kimi acceptance ~2.67 in *every* K1
  window → the c=16 anomaly is not speculation-related.
- **Noise band** calibrated from 3 independent TP2 engine starts: c=1 step
  ±0.4 ms, c=64 TPOT ±0.5 ms. TP4/TP8 effects are 4×/13× that band.

## 7. Results

**Qwen TP-curve** (full tables:
`results/summaries/2026-06-11-qwen-tp-curve.md`):

The experiment: Qwen3.6-35B-A3B **fits on a single GPU**, so it can run the
same engine command at TP=1/2/4/8 with *nothing changing except the number
of ranks*. Every millisecond TP adds versus TP1 is therefore pure
parallelization overhead — dominated by the all-reduce ladder — measured on
real serving, not a microbenchmark. TP1 is the comms-free anchor; this
lever is impossible for Kimi (must run TP=8), which is why Qwen carries the
curve and Kimi is profiled directly.

*Interactive (c=1):* one request at a time, so each decode step is laid
bare — no batching to hide latency. With MTP speculation a step emits ~2.6
tokens, so **ITL ≈ time per step** while TPOT = step ÷ accepted tokens. The
comms tax is read off the *step* column (TPOT shrinks it by the acceptance
factor, which is why the tax is not visible as TPOT differences):

| TP (c=1) | step / ITL med (ms) | TPOT med (ms) | step comms tax vs TP1 |
|---|---:|---:|---:|
| 1 | 8.98 | 3.68 | — (comms-free anchor) |
| 2 | 9.91 | 3.65 | +0.93 ms |
| 2 cross-socket (0,4) | 9.13 | 3.51 | +0.15 ms → no UPI tax (cross ≤ same-switch) |
| 4 | 10.54 | 4.00 | +1.56 ms (4× noise band ±0.4) |
| 8 | 14.16 | 5.12 | +5.18 ms (13× noise) |

At c=1 an all-reduce carries only KB-scale payloads (Kimi estimate: ~14 KiB
per hidden-state vector before overhead/fusion), so this tax is the *per-round
fixed cost × number of rounds* — and it grows superlinearly with rank count
(2→4 ranks: +0.6 ms; 4→8 ranks: +3.6 ms), because every round must
synchronize more participants. Note the cross-socket TP2 run came out
*cheaper* than same-switch TP2 (9.13 vs 9.91) — both within ~2× the noise
band of each other, which is precisely the "no UPI tax" finding: if link
class mattered, cross-socket had to be the expensive one.

*Batched (c=64):* 64 concurrent requests amortize the per-step floor and
grow the collective payloads — this is the throughput regime. **Scaling
efficiency** here = measured throughput ÷ (TP1 throughput × GPU count),
i.e. "what fraction of the added silicon turns into output":

| TP (c=64) | out tok/s | scaling eff. | per-GPU power / SMACT | PCIe RX |
|---|---:|---:|---|---:|
| 1 | 1202 | 100% (def.) | 436 W / 0.665 | ~0 |
| 2 | **1404** | 1404/(1202×2) = **58%** | 255 W / 0.359 | 6.25 GB/s |
| 4 | 680 | 680/(1202×4) = **14%** | 142 W / 0.118 | 5.65 GB/s |
| 8 | 257 | 257/(1202×8) = **2.7%** | 111 W / 0.053 | 7.18 GB/s |

How to read it: TP2 still *wins absolutely* (+17% total throughput, the
serving optimum), but already burns 42% of the second GPU on coordination.
TP4 and TP8 are **absolutely slower than a single GPU** — 8 GPUs deliver
0.21× of what 1 GPU does. The counters say why: per-GPU power falls from
436 W toward the ~70–99 W idle floor and SMACT collapses 0.665 → 0.053 as
ranks are added — the GPUs are not working harder on smaller slices, they
are *waiting* (in synchronous collectives) for most of every step. Note
also TP4's RX (5.65 GB/s) still sits below TP8's (7.18): TP4 c=64 is hurt by
sync/coordination before the transport ceiling even comes into play,
whereas TP8 slams into the ceiling outright. (TP1 counters re-aggregated
with the activity filter after the idle-tail errata.)

**Qwen TP8 ramp (Q1):** c=4 → 365 tok/s (RX 4.39), c=16 → 437 (RX 6.83),
c=64 → 257 (RX 7.18): peak at c≈16, collapse exactly when RX hits the
ceiling; SMACT flat 0.05–0.07 throughout; TTFT med grows 177 → 342 ms
(c=4 → c=16) before queueing dominates at c=64.

**nop2p dose (TP2, c=64):** `NCCL_P2P_DISABLE=1` forces every transfer
through host memory — if per-round link latency priced the step, this had
to hurt. Measured: 1396 vs 1404 tok/s, c=1 step unchanged — **null effect**,
comms at 2 ranks is not even latency-sensitive. (Bonus: the three engine
restarts this required calibrated the noise band in §6.)

**Kimi TP8 ramp (K1)** + traces (K2 and the 06-11 c=1 trace; summaries:
`2026-06-11-kimi-tp8-profile.md`, `2026-06-11-nvlink-boundary-verdict.md`):

| c | TPOT med (ms) | ITL med (ms) | out tok/s | power / SMACT | PCIe RX |
|---:|---:|---:|---:|---|---:|
| 1 | 8.7 | — (step ~50 ms profiled) | 75 | — | — |
| 8 | 78.5 | 191 | 86 | 135 W / 0.093 | 7.20 GB/s |
| 16 | 190.5 | 512 | 73 | 123 W / 0.068 | 7.85 GB/s |
| 16 (repeat) | 197.3 | 525 | 67 | 126 W / 0.074 | 7.66 GB/s |
| 32 | 94.1 | 127 | 285 | 185 W / 0.179 | 7.79 GB/s |

Eagle3 acceptance is ~2.67 in every window (token-weighted from engine
logs) — the c=16 anomaly is not a speculation effect. Note c=16 draws *less*
power at *lower* SMACT than c=8 while delivering worse latency and
throughput: the engine does less per second, yet the transport stays pinned.

| trace (rank 0) | gaps | NCCL | compute | window |
|---|---:|---:|---:|---|
| Kimi TP8 **c=1** | **63%** | 22.5% | 9.1% | 1 request, span 5.06 s, overhead control ~5% |
| Kimi TP8 **c=16** | 10% | **83.9%** | 4.6% | 16 prompts, span 67 s, ITL 535 vs 525 unprofiled (~2%) |
| Qwen TP4 **c=64** | 33% | **53.3%** | 5.6% | 64 prompts, span 55 s, ITL 49.6 vs 53.7 unprofiled |

Trace caveats, stated once: NCCL kernel time includes in-kernel peer-wait
(an *upper* bound on pure transfer); rank 0 carries extra driver work but is
representative for symmetric collectives; the batched windows include the
prefill burst (Q4: TTFT med 21.8 s of a 45 s bench), so the *pure-decode*
comms share is likely higher than the quoted span share.

**Cross-island placement (Q3, TP4 on 0,1,4,5 vs 0–3):** the dose that
isolates link class — same rank count, same model, only the topology of the
4 GPUs moves (two PIX pairs on *different* sockets vs all four under one
socket):

| | intra (0–3) | cross-island (0,1,4,5) |
|---|---:|---:|
| c=1 TPOT / ITL med (ms) | 4.00 / 10.54 | 3.99 / 10.37 |
| c=64 ITL med (ms) / out tok/s | 53.7 / 680 | 48.3 / **716** |

**Zero island/UPI penalty** — cross is ~5% *better* at c=64 (plausibly NUMA
spread of host work across both sockets). Together with A4 (cross-socket
TP2 ≈ same-switch TP2) this kills the link-class hypothesis at both rank
counts where it could be tested.

**Floor doses (F-series, Qwen TP1 c=1, random 64/512):**

| dose | step/ITL med (ms) | TPOT med (ms) | power / SMACT |
|---|---:|---:|---|
| base (MTP + cudagraphs) | 8.93 | 3.39 | 94 W / 0.052 |
| spec OFF | 5.36 | 5.36 | 92 W / 0.053 |
| enforce-eager (spec ON) | 55.1 | 19.6 | 78 W / **0.009** |
| governor `performance` | 9.86 | 3.70 | — |

Reading the doses: with spec OFF every step emits exactly 1 token, so
ITL = step time — the *step* gets 3.57 ms cheaper without MTP, yet MTP still
wins on TPOT (3.39 vs 5.36) because acceptance ~2.6 amortizes the costlier
step across ~2.6 tokens. The eager dose removes cudagraphs only: the step
explodes 8.93 → 55.1 ms with SMACT collapsing to 0.009 — pure kernel-launch
overhead, normally hidden by graph replay. The governor dose came out
*worse* than base (9.86 vs 8.93, outside the ±0.4 ms band) — `schedutil`
exonerated, restored and documented after the test.

(The TP1 c=1 trace exists — `floor/trace_summary_tp1_c1.txt` — but is
contaminated by first-request torch.compile: the bench ran without warmups,
so dynamo/inductor compile chains ~0.77 s dominate the cpu_op ranking and
gaps 73% include one-time compilation. Used qualitatively only: zero NCCL
at TP1, host Python/dispatch fills the pauses. The quantitative floor
attribution rests on the doses above, which are clean.)

## 8. Calculations and the causal path

**Interactive (c=1) chain:** TP1 with zero comms already takes 8.93 ms/step
at SMACT 0.05 → a floor exists independent of any link. Doses split it:
8.93 − 5.36 = **3.57 ms/step (40%) is MTP orchestration**; the eager dose
(55.1 ms, SMACT 0.009) shows cudagraphs already mask ~46 ms/step of kernel
launch overhead — the floor is host/launch by nature; governor exonerated
(9.86 ≥ 8.93). Adding ranks adds a comms tax on top (+0.15/+1.56/+5.18 ms
for 2/4/8 ranks), but A4 + Q3 show **link class does not matter** (no UPI
tax at either c) and nop2p shows the 2-rank tax is not even
latency-sensitive.

Kimi TP8 c=1 closes the chain at the 8-rank end, with the step arithmetic
made explicit: 189 output tokens / ~2.6 accepted per verify ≈ **73 decode
steps**; the profiled request spends ~3.8 s in decode (e2e 5.21 s minus
TTFT 1.44 s) → **~50 ms/step**. Applying the trace's span shares, a step is
roughly ~32 ms GPU idle (gaps), ~11 ms NCCL kernels, ~4.6 ms compute. Amdahl bound for a
perfect interconnect: `1/(1−0.225) ≈ 1.3×` — and part of the NCCL time is
peer-wait a faster link does not remove, so the realistic interactive gain
is below even that.

**A wrong hypothesis, kept on the record:** mid-investigation the TP4→TP8
cliff was attributed to the *link class* — TP=8 is forced to cross UPI,
TP4 is not, so UPI looked like the culprit. Two placement doses falsified
it: A4 (TP2 on GPU{0,4}, pure cross-socket: 3.51 ms ≈ same-switch 3.65 ms)
and Q3 (TP4 split 2+2 across sockets: *better* than intra at c=64). The
dose is the **rank count and the shared transport ceiling**, not where the
traffic flows. This matters for the purchase: it says NVLink's value is in
replacing PCIe as transport (bandwidth/contention), not in shortening any
particular unlucky path.

**Batched chain:** payloads grow with batch → comms flips from latency-priced
to transport-priced. PCIe RX pins at **7.2–7.9 GB/s for every Kimi c≥8 and
for Qwen TP8 c≥16** — a model-independent ceiling; throughput collapses
exactly when a config hits it (Qwen TP8: 437 → 257 tok/s). Traces quantify
the share: Kimi TP8 @c16 **s = 0.839**, Qwen TP4 @c64 **s = 0.533** — the
latter independently confirmed by the TP2→TP4 throughput drop
(1404 → 680 tok/s ≈ 52% lost: removing the 53.3% comms share would lift
680 back to ≈1456 ≈ TP2's 1404; two methods, one number). Q3 fixes
`capture`: 1.0 for TP≤4 (one island), ≈0.75 for TP=8 (6 of 8 ring legs
intra-island). Gains:

```text
TP4  batched:  1 / (1 − 0.533 × 1.00) ≈ 2.1×
TP8  batched:  1 / (1 − 0.839 × 0.75) ≈ 2.7×   (ceiling at capture=1: 6.2×)
TP8  c=1:      1 / (1 − 0.225 × 0.75) ≈ 1.2×
```

**Anomaly note:** Kimi c=16 is a pathological operating point (ITL 512 ms,
reproduced at 525 ms ±3%; Eagle3 acceptance stable ~2.67 → not
speculation-related; c=32 is 4× better on the same hardware) — a
scheduler-shaped software suspect. The s=0.839 measurement lives inside that
pathology; the c=32 share is extrapolated from identical counter signatures
(RX ceiling, SMACT 0.18), not traced.

**Predictions vs measurements** (closing the loop on the §5 table):

| Config | Predicted | Measured | Where the prediction failed |
|---|---|---|---|
| TP=1 | 1.0× | 1.0× | — |
| TP=2 in-island | ~1.3–2× | **≈ 0 gain** (any c) | comms at 2 ranks is ~free on PCIe; nothing to remove |
| TP=4 in-island | ~1.6–2.5× | ≈0 at c=1; **~2.1× batched** | missing workload-shape axis; range right for batched only |
| TP=8 hierarchical | ~1.2–1.5× | ~1.2× at c=1; **~2.7× batched** | *under*-predicted batched: payload growth at batch was not modeled |

The pre-calibration model over-valued NVLink at low rank counts (where the
floor rules) and under-valued it in exactly the regime it is built for
(batched transport saturation). Calibration changed the *shape* of the
answer, not just the numbers — which is the argument for having measured.

## 9. Conclusions from the results

- The node has **two different bottlenecks depending on workload shape**,
  and neither is the one originally suspected (HBM).
- **One user at a time:** the limit is software — the engine's fixed
  per-step cost (speculative-decoding bookkeeping is its single largest
  named piece), with kernel-launch overhead already absorbed by cudagraphs.
  Faster links cannot buy back meaningful latency here.
- **Many users at once on many GPUs:** the limit is the PCIe transport
  itself — every config that spans ranks eventually hits the same ~7–8 GB/s
  receive ceiling, and the GPUs then spend most of the wall communicating
  instead of computing. This is exactly the regime a faster interconnect is
  built for.
- **Where the traffic flows does not matter on this node — only how many
  ranks share the road.** Crossing sockets costs nothing measurable; the
  4-GPU islands NVLink would create are therefore a clean fit for TP4 and a
  partial fit for TP8.
- Some of the batched pain is **recoverable in software first** (the c=16
  scheduling pathology disappears at c=32 for free).
- The floor itself has named, addressable components, in cheapness order:
  (a) the Kimi c=16-style scheduler pathology — operating-point/config fix;
  (b) MTP/Eagle3 orchestration (40% of the TP1 floor) — engine-version A/B,
  draft-length tuning; (c) cudagraph mode (full vs piecewise) and CPU/NUMA
  pinning of the engine process on this dual-socket node; (d) vLLM upgrade —
  v0.20 is the pinned baseline and newer releases list scheduler/step-loop
  optimizations. None of these costs hardware money.

## 10. Decision table — what to do in which situation

The reading criteria were **pre-registered in the session plans before the
measurements ran** (so the verdict could not be fitted to the data):

| Pre-registered result pattern | Pre-registered verdict | What happened |
|---|---|---|
| TPOT rises TP1→2→4→8 and nop2p degrades it further | PCIe round-latency tax confirmed causally | half-confirmed: TPOT rises, but nop2p was **null** → latency tax rejected at 2 ranks |
| Kimi trace: comms ≥ ~40% of span at c=1 | Kimi TP8 comms-bound directly | **not met** (22.5%) → floor-bound at c=1 |
| Kimi trace: gaps dominate, comms small | floor dominates; NVLink estimates cut | **met at c=1** (63% gaps) |
| TP2 ≈ TP1 and nop2p null | comms cheap — investigate the floor | **met** → F-series executed |
| comms-signature at batch (power low, SMACT low, RX high, TPOT degrades) | profile at batch before verdict | **met** → K2/Q4 traces added the batched axis |

| Scenario | NVLink 4-way verdict | Estimated gain | Evidence level |
|---|---|---|---|
| Model fits 1–2 GPUs (Qwen-class), any c | **NO-GO** | ≈ 0 | L2 causal (nop2p null, tax ≈ noise) |
| Running TP≥4 for a model that fits on fewer | **NO-GO** (config error, not hardware) | TP8 peak 437 vs TP2 1404 tok/s | L2 |
| Model requires TP=4, interactive c=1 | **NO-GO** | ≤ −28% TPOT theoretical, realistically less | L2 (tax measured) |
| Model requires TP=4, **batched** | **conditional GO** | **~2.1×** (s=0.533, capture 1.0) | L2 (trace + converging efficiency calc) |
| Kimi-class TP=8, interactive c=1 | **NO-GO** | ≤ 1.2–1.3× | L2 (trace) |
| Kimi-class TP=8, **batched** | **GO** | **~2.7×** (s=0.839 @c16, capture 0.75; ceiling 6.2×) | L2 (trace) + counters for c≥8 |

## 11. Justification per scenario

- **Fits on 1–2 GPUs:** TP2 is the measured serving optimum (1404 tok/s,
  +17% over TP1); its comms tax sits inside the noise band and worsening the
  link (nop2p) changes nothing — there is no cost for a better link to
  remove. Buying interconnect for this scenario purchases 0.
- **TP≥4 where unnecessary:** the cure is configuration (run TP2), free and
  ~3–5× better than what NVLink could recover on TP8.
- **TP=4 required, interactive:** the comms tax is +1.56 ms on a ~10.5 ms
  step; even removing all of it (impossible — part is sync) is a moderate
  latency win, not a purchase driver.
- **TP=4 required, batched:** the strongest *hardware fit* — the whole job
  lives in one island (capture 1.0) and the measured share says half the
  wall is on the wire. ~2.1× is a lower-mid estimate (the trace window mixes
  in prefill; pure-decode share is likely higher). Conditional on actually
  planning TP4-class models (W2 question).
- **Kimi interactive:** floor-bound — 63% of the wall is engine-off
  paperwork; the Amdahl ceiling of ~1.3× cannot justify hardware. The
  cheaper lever is software (MTP orchestration = 40% of the floor).
- **Kimi batched:** the strongest *evidence* — 84% of the wall in NCCL with
  the transport pinned at its ceiling for every c≥8. Even with the
  inter-island hop surviving (capture 0.75), ~2.7× of serving throughput is
  the one regime where bridges pay for themselves. Caveats: the share was
  traced inside the c=16 pathology; part of NCCL time is peer-wait; exhaust
  the software lever (scheduler/config — c=32 already 4× better) before
  attributing everything to the link.

## 12. Verdict

**Buy NVLink 4-way bridges only if the node's mission is batched/throughput
serving of models that genuinely require TP≥4** (Kimi-class MoE at TP=8, or
70–200B-class models at TP=4): measured expectation **2–3×** serving
throughput, ceiling 6×. **Do not buy them for interactive latency or for
anything that fits on 1–2 GPUs** — those regimes are floor-bound or
comms-free, and the measured ceiling there (≤1.3×) cannot justify hardware.
The purchase decision is therefore a question about the workload roadmap,
not about the hardware: it composes with any price tag via the 2–3× number.
Before any purchase, exhaust the free software levers this investigation
exposed: the Kimi c=16 scheduling pathology (4× recoverable by operating
point alone) and the MTP orchestration share of the floor.

**Boundary of this thread:** T9 delivers the *performance* half of the
cost-benefit — calibrated shares, the per-scenario gain table, and the
GO/NO-GO verdict. The *money* half (bridge price, installation downtime,
warranty) is a company-side input outside this repo; the thresholds are set
so the verdict composes with any price tag.

**Open residuals** (would sharpen, not change, the verdict): a Kimi c=32
trace (the GO estimate's share is traced at c=16, extrapolated to c=32 from
counters); the root cause of the c=16 scheduler pathology; a clean
(warmed-up) TP1 CPU-timeline to itemize the remaining 5.36 ms of floor.

## 13. Evidence

| Claim | Source |
|---|---|
| `DRAM_ACTIVE` 0.093/0.070, SMACT ~0.20, PCIe 6–8 GB/s under load (HBM-bound refuted) | `results/runs/2026-06-10_w1_article_evidence/p0_gpu_counters/` |
| Qwen TP-curve TP1/2/4/8 + A4 cross-socket + nop2p (tables, errata, noise band) | `results/runs/2026-06-11_bottleneck/qwen_tp_curve/`; analysis `results/summaries/2026-06-11-qwen-tp-curve.md` |
| Kimi TP8 c=1 trace: gaps 63 / NCCL 22.5 / compute 9.1, overhead control ~5% | `results/runs/2026-06-11_bottleneck/kimi_profiler/`; analysis `results/summaries/2026-06-11-kimi-tp8-profile.md` |
| K1 ramp, c=16 anomaly + repeat, K2 trace @c16 (NCCL 83.9%), Q1 ramp, Q3 zero UPI tax, Q4 trace @c64 (NCCL 53.3%), F doses + governor exoneration | `results/runs/2026-06-11_nvlink_boundary/`; analysis `results/summaries/2026-06-11-nvlink-boundary-verdict.md` |
| Raw profiler traces (not committed — repo policy) | `/home/working/nanoserve-tracing` on ubuntusrv2 |
| Dual-root PCIe, switch pairs, NVLink Bridge optional, Kimi TP4 does-not-fit arithmetic | `docs/operations/sys-521ge-tnrt.md`; `docs/operations/infrastructure.md`; T1 |
| Kimi TP=8 step 16.55 ms (spec OFF), 6.92 ms/tok TPOT-any (ON) | T6, `results/runs/2026-06-05_kimi-k2-6_run-05_eagle3-off-paired/`, `…run-04_eagle3-on/` |
| External support for architecture estimates only: `~14 KiB` payload (`hidden_size=7168`, BF16), 61 decoder layers, and ~2 Megatron-style forward TP reductions/layer | [Hugging Face Kimi K2 config](https://huggingface.co/moonshotai/Kimi-K2-Instruct-0905/resolve/main/config.json); [Megatron-LM TP paper](https://ar5iv.labs.arxiv.org/html/1909.08053); [vLLM DeepSeek/Kimi-style source](https://github.com/vllm-project/vllm/blob/v0.20.0/vllm/model_executor/models/deepseek_v2.py) |
| Goal, parametric model, first-pass NVLink table | [#50](https://github.com/Czyszka/nanoserve-mini/issues/50) |
| Executed session plans (methodology of record) | `docs/plans/2026-06-10-server-session.md`, `docs/plans/2026-06-10-bottleneck-followup-session.md`, `docs/plans/2026-06-11-nvlink-boundary-session.md` |

## Appendix: operational lessons (paid for in session time)

Engineering-record items that cost real debugging during the three sessions
and are now codified in the plans:

- **vLLM v0.20 removed `VLLM_TORCH_PROFILER_DIR`** silently (log:
  "unknown vllm env"); `/start_profile` 404s unless the engine starts with
  `--profiler-config='{"profiler":"torch","torch_profiler_dir":…}'`.
- **A compose overlay replaces the whole `command`** — you cannot append one
  flag; the overlay must carry the full canonical command. Corollary: env
  interpolation inside an overlay inherits whatever the shell has exported —
  a leftover `QWEN_TP=4` silently started the "TP1" profile at TP4 once.
  Hard-code the parameters that define the experiment; verify from
  `docker inspect … .Config.Cmd` + the engine log, never from the overlay
  file.
- **`sudo docker compose` strips the exported env** (use `sudo -E`) — the
  original cause of a whole aborted session (TP MISMATCH).
- **`docker compose cp <dir>` nests a subdirectory**; copy `dir/.` and use a
  recursive `find` when verifying.
- **No `set -e` / no bare `exit` in interactive SSH sessions** — one `exit 1`
  in a pasted block logs the operator out and destroys session variables and
  history. Echo warnings + conditional execution instead.
- The vLLM container ships **`python3` only** (no `python` alias); benches
  need `pip install pandas datasets` after every recreate (`/tmp` and pip
  state do not survive).
- **Engine log timestamps are UTC**; bench windows must be matched via
  epoch files, not local-time assumptions.
- **TP≥4 traces flush minutes after `/stop_profile`** (8 ranks writing
  large gzipped JSONs) — wait for file count > 0 *and* stable sizes before
  copying.
- **Raw env dumps leak secrets** (`HUGGING_FACE_HUB_TOKEN`) — capture
  container env through a redaction filter; raw traces stay outside the
  repo (size + policy).
- **Profile after warmup** — the F3 trace burned its window on torch.compile
  because the bench ran cold (the one methodology slip of the series, left
  visible in §7 as a worked example of why warmups matter).
