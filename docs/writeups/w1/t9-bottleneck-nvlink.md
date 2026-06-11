# T9 — What actually limits decode on this node, and would NVLink 4-way pay off?

Mode: investigation + decision analysis. **Status: in progress** — evidence
through 2026-06-10; closing measurements planned in
`docs/plans/2026-06-10-bottleneck-followup-session.md`, goal tracked in
[#50](https://github.com/Czyszka/nanoserve-mini/issues/50).

## Target structure of the final note

The finished T9 should read in this order (restructure pass once the
2026-06-11 session data is in; mapping to today's sections in parentheses):

1. Problem (→ Question)
2. Observation of the problem + the automotive analogy (→ delivery-run analogy)
3. Glossary (→ Glossary)
4. Hardware infrastructure (→ topology facts, now scattered; pull together)
5. Mechanisms under investigation (→ The decision model, mechanism list)
6. Methodology — step by step / scenarios (→ session plans, summarised here)
7. Results (→ Established so far + 06-11 session results)
8. Calculations + causal-path analysis (→ per-step comms tax, Amdahl bounds,
   trace splits)
9. Conclusions from the results
10. Summary table: possible decisions per situation (→ When NVLink makes
    sense — and when it does not)
11. Justification per scenario
12. Verdict
13. Evidence references (→ Evidence)

Editorial rules for the restructure:

- In point 7, keep only result *tables* with links to `results/runs/...` —
  raw numbers live in the repo; duplicating them here will drift (point 13
  closes the loop).
- Keep points 8 and 9 from blending: 8 = the causal chain with numbers
  (e.g. "PCIe RX ceiling 7.7 GB/s → NCCL 84% of span → Amdahl ≤6.2×"),
  9 = what that means in plain language, no new numbers.

## Question

Two questions, both of which must end with numbers rather than adjectives:

1. **What is the current bottleneck of decode on this PCIe-only 8×H200 node?**
   A named mechanism at L2 (one-lever counterfactual or direct kernel-level
   attribution) — not a correlation.
2. **Would buying NVLink 4-way bridges pay off — for which TP configurations
   (1/2/4/8), and by roughly how much?** A calibrated per-config estimate good
   enough to support a purchase decision.

## Scope boundary with W2

T9 is the **engineering record** of the bottleneck attribution and the NVLink
decision model. The full TP-scaling study (sweet spot across model classes,
throughput curves, the W2 roadmap article) will *synthesize from* this thread,
not re-run it. T9 ends when the two questions above have calibrated answers;
everything beyond that belongs to W2.

## Glossary (terms as used in this thread)

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

## Working mental model: the delivery-run analogy

*(Deliberately informal — a learning aid for reading every number in this
thread. Each claim maps to a measurement.)*

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
- **Why heavy traffic (c=64) flips the story:** pack 64 parcels into one run
  and the paperwork cost is split 64 ways — the floor stops mattering. But
  the roundabouts now jam (collective payloads grow with batch), so comms
  dominates: TP8 c=64 spends ≥85% of the step in the jam, vans at near-idle
  power (111 W vs 70 W parked).
- **The floor investigation (F-series)** asks *what exactly* the driver
  waits on: the waybill ritual (speculative orchestration — spec-off dose),
  restarting the engine per leg (launch overhead — eager dose), or a
  dispatcher stuck in power-saving mode (CPU governor dose); the TP1 CPU
  trace is the dashboard camera showing what the driver does in the pauses.

## Established so far (evidence through 2026-06-10)

**1. HBM-bandwidth-bound is refuted.** The 2026-06-10 DCGM capture (T5 / W1
article Investigation 5) shows, under load, `DRAM_ACTIVE` at **0.093** (c=1)
and **0.070** (c=64) with tensor pipes at 0.012–0.064 and power at
169–199 W of 600 W. The memory system idles >90% while the node serves at
full tilt.

**2. Nothing is saturated — the latency/serialization signature.** SMs ~20%
busy (against nvidia-smi's misleading "100% util"), PCIe links at 6–8 GB/s ≈
10–13% of Gen5 x16. When every bandwidth resource idles while throughput
stalls, the step time is spent in many small synchronous rounds, each priced
by latency. On TP=8 the standing suspect is the per-layer all-reduce ladder
(~61 layers × 2 ≈ 122+ rounds/token for Kimi; EP all-to-all and Eagle3 draft
passes add more).

**3. The TP lever shows a large comms tax — and a comms-independent floor.**
Qwen3.6-35B-A3B, same engine command, only TP varies (active-sample means):

| Window | power/GPU | SMACT | DRAMA | PCIe TX/RX per GPU | client |
|---|---:|---:|---:|---:|---|
| TP1 c=64 (zero comms) | **443 W** | **0.68** | 0.39 | ~0 | 1202–1563 tok/s |
| TP2 c=64 | 265 W | 0.40 | 0.18 | **5.8 / 6.7 GB/s** | missing (errata) |
| TP1 c=1 | 272 W | 0.47 | 0.29 | ~0 | TPOT 3.68 ms, ~9 ms/step |

One added PCIe rank halves per-GPU activity (the comms tax is real and
large), yet TP1 at c=1 — with **zero** communication — still idles ~50% at
~9 ms/step: a **per-step host/launch floor exists independently of PCIe**.
For Kimi TP=8 (16.55 ms/step spec-OFF) the open question is the split between
the all-reduce ladder and that floor.

**4. Topology raises the stakes (datasheet + env snapshot).** The platform
(Supermicro SYS-521GE-TNRT) is **dual-root PCIe**: 2× Xeon Gold 6530, GPUs in
four 2-GPU switch pairs (`1D/1E`, `40/41`, `AA/AB`, `BB/BC`), GPU0–3 under
CPU0 and GPU4–7 under CPU1 (presumed; `topo -m` pending). Three link classes
follow — same-switch pair < same-socket < **cross-socket via UPI** — and TP=8
crosses UPI by construction. The datasheet lists **"GPU-GPU interconnect:
NVIDIA NVLink Bridge, optional"**, so the purchase path is officially
supported; bridges must pair within sockets (4+4 islands). Full map:
`docs/operations/infrastructure.md` (Topologia GPU/CPU).

## The decision model

Per decode step:

```text
T(tp, link) = F_host + N_rounds × r(link, ranks) + W_silicon
```

Anchors: Kimi TP=8 T ≈ 16.5 ms, W_silicon ≈ 1–2 ms (from `DRAM_ACTIVE`),
N_rounds ≥ 122; Qwen TP1 gives F_host + W ≈ 9 ms at zero comms (model-specific
floor). Unknowns to measure: `r_PCIe(2/4/8)` annotated by link class, the
comms share of Kimi's step, `F_host`, `N_rounds`. `r_NVL4 ≈ 20–30 µs` is a
labeled assumption from NCCL/NVLink gen4 small-message figures — it cannot be
measured without the hardware, and renting NVLink in the cloud was considered
and **rejected** (decision 2026-06-10), so it stays an assumption. To keep the
verdict honest despite that: the calibrated table is computed at **both ends
of the range (20 µs and 30 µs)**, and the GO/NO-GO verdict counts only if it
is identical across the whole range. If the verdict flips inside 20–30 µs, the
output of this thread is "decision-sensitive to `r_NVL4` — obtain a vendor
figure before buying", not a guess.

First-pass estimates (BEFORE calibration; assumptions in #50):

| Config after 2× NVL4 islands (4+4) | Comms path | Est. step/TPOT gain |
|---|---|---|
| TP=1 | none | **1.0× (none)** |
| TP=2 in-island | all NVLink | ~1.3–2× |
| TP=4 in-island (70–200B class, DeepSeek, Qwen) | all NVLink | **~1.6–2.5×** |
| TP=8 hierarchical (**Kimi's only option**) | NVLink intra + PCIe inter-island | **~1.2–1.5× (modest)** |

Hard constraint: **Kimi-K2.6 cannot run TP=4** (554.30 GiB / 4 ≈ 138.6 GiB/GPU
weights alone vs 140.40 GiB board) — its NVLink benefit is capped at the
hierarchical-TP8 case. If the profiler shows the host floor (not comms)
dominating Kimi's step, that gain shrinks further. The purchase
recommendation therefore waits for calibration.

## Remaining measurements (planned, next slot)

Per `docs/plans/2026-06-10-bottleneck-followup-session.md`:

- **Qwen TP curve, full re-run**: TP=2 (replaces the defective 2026-06-10
  capture), TP=8 (rank-count anchor matching Kimi), TP=4; stretch A4 = TP=2 on
  GPU{0,4} — a direct UPI-tax measurement (same ranks, only link class moves).
- **Kimi TP=8 torch-profiler trace** (`VLLM_TORCH_PROFILER_DIR` +
  `/start_profile`): NCCL share vs compute vs gaps per decode step — the only
  method that closes Kimi attribution, since the TP lever is impossible for it.
- **NCCL dose-response**: Qwen TP=2 with `NCCL_P2P_DISABLE=1` — causal check
  that per-round latency drives TPOT.
- Topology confirmation: `nvidia-smi topo -m` matrix.

## Decision criteria

### Reading the measurements

| Result | Verdict |
|---|---|
| TPOT rises monotonically TP1→2→4→8; nop2p degrades it further | PCIe round-latency tax confirmed causally (L2); size = TPOT deltas |
| Kimi trace: comms ≥ ~40% of step span at c=1 | Kimi TP=8 decode comms-bound directly (L2) |
| Kimi trace: gaps/other dominate, comms small | per-step floor dominates — PCIe hypothesis revised, NVLink gain estimates cut accordingly |
| TP2 ≈ TP1 TPOT and nop2p changes nothing | comms cheap — investigate the floor instead |

### When NVLink makes sense — and when it does not

The ceiling on any interconnect upgrade is an **Amdahl bound**: if comms is a
share `s` of the step, then even an *infinitely fast* link caps the speedup at
`1 / (1 − s)`. With `s = 0.3` the best possible gain is 1.43×; with `s = 0.6`
it is 2.5×. The profiler gives `s` per config; NVLink then realizes *most* of
that bound for traffic that stays inside an island (r drops ~5–10×) and only
*part* of it for hierarchical TP=8 (the inter-island PCIe hop survives).

**GO** (recommend the bridges) when both hold:

1. the calibrated gain is **≥ ~1.5× for at least one config the node will
   actually serve** — in practice: measured `s ≥ ~0.4` on a TP=2/TP=4
   workload (in-island traffic realizes most of the Amdahl bound), or the
   hierarchical-TP=8 estimate for Kimi clears 1.5× despite the PCIe hop;
2. such TP≤4 workloads are actually planned (W2-class 70–200B models,
   DeepSeek, Qwen) — not just hypothetical.

**NO-GO** (keep PCIe, spend effort elsewhere) when any of:

- the Kimi trace shows the **floor dominating** (`s < ~0.25`): the Amdahl
  bound is then ≤ 1.33× even with perfect interconnect, and the floor work
  below is the cheaper fix;
- the node remains **Kimi-only** in practice: Kimi cannot use an island fully
  (TP=4 does not fit), so it collects only the modest hierarchical gain;
- the TP curve comes back flat (TP2 ≈ TP1) — comms was never the binding term.

**Boundary of this thread:** T9 delivers the *performance* half of the
cost-benefit — calibrated `s`, the per-config gain table, and the GO/NO-GO
verdict against the thresholds above. The *money* half (bridge price,
installation downtime, warranty) is a company-side input outside this repo;
the thresholds are set so that the verdict composes with any price tag.

### Addendum: if the floor dominates — investigating F_host

Conditional follow-up (only triggered by the floor-dominant outcome), kept
short because it is a different investigation:

1. **Decompose the gaps** from the same trace: host-side Python/scheduler time
   vs sampler CPU↔GPU syncs vs kernel-launch spacing — the trace already
   contains this; no new capture needed.
2. **Cheap levers to A/B** (one restart each): CUDA-graph mode (vLLM
   `cudagraph_mode` full vs piecewise — fewer launch gaps), speculation OFF
   (removes draft bookkeeping from the step), CPU/NUMA pinning of the engine
   process (dual-socket node — scheduler threads bouncing across sockets
   inflate sync latency).
3. **Engine version**: vLLM v0.20 is the pinned baseline; release notes for
   newer versions list scheduler/step-loop optimizations — an upgrade A/B is
   the last cheap lever before accepting the floor as structural.

## Evidence

| Claim | Source |
|---|---|
| `DRAM_ACTIVE` 0.093/0.070, SMACT ~0.20, PCIe 6–8 GB/s under load (HBM-bound refuted) | `results/runs/2026-06-10_w1_article_evidence/p0_gpu_counters/` |
| Kimi TP=8 step 16.55 ms (spec OFF), 6.92 ms/tok TPOT-any (ON) | T6, `results/runs/2026-06-05_kimi-k2-6_run-05_eagle3-off-paired/`, `…run-04_eagle3-on/` |
| Qwen TP1/TP2 counters + TP1 bench (443 W vs 265 W/GPU; TPOT 3.68 ms c=1) | `results/runs/2026-06-10_extra/` (TP1 from commit `6a3cdbf`, TP2 counters from `2d20b6a`) |
| Errata of the TP2 capture (wrong log, missing bench JSONs, appended tail) | `docs/operations/agent-state.md` (In flight, Bottleneck follow-up) |
| Dual-root PCIe, switch pairs, NVLink Bridge optional | `docs/operations/sys-521ge-tnrt.md`; `results/raw/server_env_snapshot.json`; `docs/operations/infrastructure.md` |
| Goal, parametric model, first-pass NVLink table | [#50](https://github.com/Czyszka/nanoserve-mini/issues/50) |
| Closing session plan (A/B/C + A4, decision criteria) | `docs/plans/2026-06-10-bottleneck-followup-session.md` |
