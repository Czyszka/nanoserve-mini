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
  result. Runs after attention and after the FFN/MoE block → ~2 per layer per
  forward pass. It is *synchronous*: no rank continues until it completes.
- **all-to-all** — the collective behind EP routing: each rank sends a
  different chunk to each other rank (token dispatch to experts, then combine
  back).
- **NCCL** — NVIDIA Collective Communications Library; the library vLLM/PyTorch
  use to implement all-reduce/all-to-all on NVLink or PCIe. "NCCL kernels" in a
  profiler trace = time spent communicating (or waiting for the slowest rank).
- **P2P (peer-to-peer)** — GPUs exchanging data directly over PCIe without
  bouncing through CPU RAM. `NCCL_P2P_DISABLE=1` forces the slower
  through-host path — our dose-response lever.
- **small-message regime** — at batch 1 an all-reduce carries only ~14 KB, so
  its duration is set by fixed per-operation latency (launch + protocol +
  link round-trips), not by link bandwidth. That is why a *latency*-bound link
  can look idle in *throughput* counters.

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
- **N_rounds** — how many synchronous communication rounds one step performs
  (~2 all-reduces × ~61 layers ≈ 122+ for Kimi).
- **r(link, ranks)** — the latency of one such round; depends on the link type
  (PCIe vs NVLink vs UPI path) and how many ranks participate.
- **W_silicon** — time the GPU actually works per step: HBM weight/KV reads +
  arithmetic. Measured to be small here (~1–2 ms for Kimi).
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

NVLink-relevant derived quantities: the comms share `s` per scenario
(Amdahl bound `1/(1−s)`), and `capture` per topology fit (TP≤4 in one
island = 1.0; TP=8 hierarchical ≈ 0.75). `r_NVL4 ≈ 20–30 µs` remains a
labeled assumption (cloud NVLink rental rejected 2026-06-10); the verdict
below does not depend on its exact value inside that range.

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

Method notes: client metrics from `vllm bench serve` (SWE-bench custom
dataset, 256-out, ignore-eos; random 64/512 for c=1 floor benches); DCGM
windows tagged per bench with epoch files; traces via `--profiler-config`
overlay, copied outside the repo (`/home/working/nanoserve-tracing`), only
rank-0 summaries committed; profiler-overhead controls on every trace; noise
band calibrated from 3 independent TP2 starts (c=1 step ±0.4 ms, c=64 TPOT
±0.5 ms).

## 7. Results

**Qwen TP-curve** (full tables:
`results/summaries/2026-06-11-qwen-tp-curve.md`):

| TP (c=1) | TPOT med (ms) | step comms tax vs TP1 |
|---|---:|---:|
| 1 | 3.68 | — |
| 2 | 3.65 | +0.15 ms (≈ noise) |
| 2 cross-socket (0,4) | 3.51 | no UPI tax |
| 4 | 4.00 | +1.56 ms |
| 8 | 5.12 | +5.18 ms |

| TP (c=64) | out tok/s | per-GPU power / SMACT | PCIe RX |
|---|---:|---|---:|
| 1 | 1202 | 436 W / 0.665 | ~0 |
| 2 | **1404** | 265 W / 0.40 | 5.8–6.7 GB/s |
| 4 | 680 | ~108 W / 0.06 | 2.9 GB/s |
| 8 | 257 | 111 W / 0.053 | 7.18 GB/s |

**Qwen TP8 ramp (Q1):** c=4 → 365 tok/s (RX 4.39), c=16 → 437 (RX 6.83),
c=64 → 257 (RX 7.18): peak at c≈16, collapse exactly when RX hits the
ceiling; SMACT flat 0.05–0.07 throughout.

**nop2p dose (TP2, c=64):** 1396 vs 1404 tok/s — null effect.

**Kimi TP8 ramp (K1)** + traces (K2 and the 06-11 c=1 trace; summaries:
`2026-06-11-kimi-tp8-profile.md`, `2026-06-11-nvlink-boundary-verdict.md`):

| c | ITL med (ms) | out tok/s | power / SMACT | PCIe RX |
|---:|---:|---:|---|---:|
| 1 | — (step ~50 ms profiled) | 75 | — | — |
| 8 | 191 | 86 | 135 W / 0.093 | 7.20 GB/s |
| 16 | 512 (repeat: 525) | 73 | 123 W / 0.068 | 7.85 GB/s |
| 32 | 127 | 285 | 185 W / 0.179 | 7.79 GB/s |

| trace (rank 0) | gaps | NCCL | compute |
|---|---:|---:|---:|
| Kimi TP8 **c=1** | **63%** | 22.5% | 9.1% |
| Kimi TP8 **c=16** | 10% | **83.9%** | 4.6% |
| Qwen TP4 **c=64** | 33% | **53.3%** | 5.6% |

**Cross-island placement (Q3, TP4 on 0,1,4,5 vs 0–3):** c=1 TPOT 3.99 vs
4.00; c=64 ITL 48.3 vs 53.7, throughput 716 vs 680 tok/s — **zero island/UPI
penalty** (cross is ~5% better, likely NUMA spread of host work).

**Floor doses (F-series, Qwen TP1 c=1, random 64/512):**

| dose | step/ITL med (ms) | TPOT med (ms) | SMACT |
|---|---:|---:|---:|
| base (MTP + cudagraphs) | 8.93 | 3.39 | 0.052 |
| spec OFF | 5.36 | 5.36 | 0.053 |
| enforce-eager | 55.1 | 19.6 | **0.009** |
| governor `performance` | 9.86 | 3.70 | — |

(TP1 c=1 trace exists but is contaminated by first-request torch.compile —
no warmups; qualitative only: zero NCCL at TP1, host/dispatch dominates.)

## 8. Calculations and the causal path

**Interactive (c=1) chain:** TP1 with zero comms already takes 8.93 ms/step
at SMACT 0.05 → a floor exists independent of any link. Doses split it:
8.93 − 5.36 = **3.57 ms/step (40%) is MTP orchestration**; the eager dose
(55.1 ms, SMACT 0.009) shows cudagraphs already mask ~46 ms/step of kernel
launch overhead — the floor is host/launch by nature; governor exonerated
(9.86 ≥ 8.93). Adding ranks adds a comms tax on top (+0.15/+1.56/+5.18 ms
for 2/4/8 ranks), but A4 + Q3 show **link class does not matter** (no UPI
tax at either c) and nop2p shows the 2-rank tax is not even
latency-sensitive. Kimi TP8 c=1 trace confirms the same structure at the
8-rank end: gaps 63%, NCCL 22.5% → Amdahl bound for a perfect interconnect
`1/(1−0.225) ≈ 1.3×`, and part of NCCL time is peer-wait a faster link does
not remove.

**Batched chain:** payloads grow with batch → comms flips from latency-priced
to transport-priced. PCIe RX pins at **7.2–7.9 GB/s for every Kimi c≥8 and
for Qwen TP8 c≥16** — a model-independent ceiling; throughput collapses
exactly when a config hits it (Qwen TP8: 437 → 257 tok/s). Traces quantify
the share: Kimi TP8 @c16 **s = 0.839**, Qwen TP4 @c64 **s = 0.533** — the
latter independently confirmed by the per-GPU efficiency loss TP2→TP4
(702 → 170 tok/s/GPU ≈ 52% lost; two methods, one number). Q3 fixes
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

## 10. Decision table — what to do in which situation

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
| Goal, parametric model, first-pass NVLink table | [#50](https://github.com/Czyszka/nanoserve-mini/issues/50) |
| Executed session plans (methodology of record) | `docs/plans/2026-06-10-server-session.md`, `docs/plans/2026-06-10-bottleneck-followup-session.md`, `docs/plans/2026-06-11-nvlink-boundary-session.md` |
