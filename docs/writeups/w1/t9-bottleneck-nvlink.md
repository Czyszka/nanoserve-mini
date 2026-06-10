# T9 — What actually limits decode on this node, and would NVLink 4-way pay off?

Mode: investigation + decision analysis. **Status: in progress** — evidence
through 2026-06-10; closing measurements planned in
`docs/plans/2026-06-10-bottleneck-followup-session.md`, goal tracked in
[#50](https://github.com/Czyszka/nanoserve-mini/issues/50).

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
labeled assumption from NCCL/NVLink gen4 small-message figures (cannot be
measured without the hardware).

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

| Result | Verdict |
|---|---|
| TPOT rises monotonically TP1→2→4→8; nop2p degrades it further | PCIe round-latency tax confirmed causally (L2); size = TPOT deltas |
| Kimi trace: comms ≥ ~40% of step span at c=1 | Kimi TP=8 decode comms-bound directly (L2) |
| Kimi trace: gaps/other dominate, comms small | per-step floor dominates — PCIe hypothesis revised, NVLink gain estimates cut accordingly |
| TP2 ≈ TP1 TPOT and nop2p changes nothing | comms cheap — investigate the floor instead |

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
