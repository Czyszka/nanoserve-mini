# Paper note: Evaluating Modern GPU Interconnect

Lightweight note based on `docs/learning/paper-reading-guide.md`.

- **Status:** done
- **Date:** 2026-06-13
- **Phase:** Phase 1 follow-up / Phase 2 background
- **Paper:** *Evaluating Modern GPU Interconnect: PCIe, NVLink, NV-SLI, NVSwitch and GPUDirect*
- **Authors / year:** Ang Li, Shuaiwen Leon Song, Jieyang Chen, Jiajia Li, Xu Liu, Nathan Tallent, Kevin Barker; 2019
- **URL / local PDF:** https://arxiv.org/abs/1903.04611; local ignored PDF at `docs/learning/papers/Evaluating Modern GPU Interconnect.pdf`
- **Why now:** The W1 NVLink decision needs a grounded mental model for PCIe/NVLink/NVSwitch topology, NCCL collectives, message size, and placement effects.
- **Verdict:** useful background

## 5-line summary

The paper benchmarks PCIe, NVLink-V1/V2, NVLink-SLI, NVSwitch, and InfiniBand
GPUDirect-RDMA across DGX-1, DGX-2, SummitDev, Summit, and a two-GPU SLI system.
Its main lesson is that faster interconnect is not automatically useful: topology,
message size, placement, routing, and the communication library determine whether
the extra bandwidth is actually visible.
For intra-node collectives, NVLink/NVSwitch mainly help bandwidth, while startup
latency and library behavior can still dominate small or irregular cases.
For `nanoserve-mini`, this supports the current NVLink framing: measure NCCL share,
rank count, placement, PCIe/NVLink counters, and message-size sensitivity before
claiming a serving gain.
Ignore the application-level speedups as direct LLM evidence; the workloads are
older HPC/GPGPU workloads, not vLLM decode loops.

## LLM inference lens

- **Optimizes:** measurement methodology / interconnect-aware scheduling / collective communication
- **Target metric:** throughput, communication latency, bandwidth, utilization; indirectly TPOT/ITL for tensor-parallel decode
- **Bottleneck:** inter-GPU communication is shaped by topology, message size, placement, routing, and NCCL behavior, not by nominal link bandwidth alone.
- **Trade-off:** no model-quality trade-off; the cost is system complexity, topology-specific placement rules, and benchmark fragility.
- **vLLM relationship:** measure-only. vLLM tensor parallelism uses NCCL-style collectives, so the relevant symptoms are NCCL trace share, per-step ITL/TPOT, PCIe/NVLink counters, and placement sensitivity.

The most relevant observations for LLM serving are:

- PCIe, NVLink-V1, and NVLink-V2 can show NUMA effects; NVSwitch and two-GPU NVLink-SLI are much closer to UMA in the tested systems.
- PCIe can show "anti-locality" for bandwidth, where the physically closer path is not always faster.
- NVLink/NVSwitch advantages are stronger for bandwidth than for startup latency.
- Collective bandwidth depends on the number of participating GPUs and the NCCL algorithm; odd or awkward participant counts can behave badly.
- Message size matters: some collective bandwidth curves saturate only at large payloads, so small transfers can fail to benefit from a faster link.
- Application speedups are not guaranteed even when microbenchmarks improve, especially if the programming model remains CPU-master/GPU-slave or communication is not the dominant wall-time component.

## Key measurement results: PCIe vs NVLink

These numbers are background evidence from the paper's P100/V100/DGX-era
platforms, not direct measurements of the current H200 server.

| Measurement | PCIe result | NVLink / NVSwitch result | Why it matters here |
|---|---:|---:|---|
| P2P startup latency across DGX-1 GPU pairs | PCIe latency is roughly uniform across same-switch, same-socket, and QPI paths, about **~18-20 us** from the Figure 5 heatmaps | Direct NVLink neighbors are about **9 us**; routed non-neighbor paths add about **2x** latency on P100-DGX-1 and **3x** on V100-DGX-1 | Faster fabric is not automatically lower-latency for every rank pair; topology and routing matter. |
| Two-GPU SLI test | Remote PCIe access is about **13 us** | NVLink-SLI access is about **8 us**; local access is about **5 us** | Direct NVLink cuts P2P startup latency, but the gain is single-digit microseconds in this setup. |
| NVSwitch P2P latency on DGX-2 | PCIe remains topology-dependent | NVSwitch is close to UMA; one-hop vs two-hop latency difference is reported as almost negligible | A switched fabric reduces placement sensitivity much more than partial NVLink meshes. |
| Intra-node collective startup latency | For most non-all-reduce collectives on DGX-2, PCIe startup latency can be lower than NVSwitch when more than 3 GPUs participate | NVLink/NVSwitch advantage is reported mainly in bandwidth, not startup latency | Interactive decode can still be latency/floor-bound even when the interconnect has higher bandwidth. |
| DGX-1 collective bandwidth vs rank count, 1 GB payload | PCIe collective bandwidth **decreases** as more GPUs participate because of tree-network contention | NVLink collective bandwidth generally **increases** with more GPUs because more links participate in the hypercube mesh | This is the microbenchmark pattern that makes NVLink plausible for high-concurrency TP>=4 workloads. |
| NVLink-V2 vs NVLink-V1 collective bandwidth | N/A | NVLink-V2 is about **1.6x** faster at 4 GPUs and about **2x** faster at 8 GPUs than NVLink-V1 in the reported DGX-1 collective bandwidth test | Link generation and topology both matter; do not use a single "NVLink speedup" constant. |
| Collective bandwidth saturation by message size | PCIe collective bandwidth saturates around **16 MB** messages for 8 GPUs | NVLink collective bandwidth saturates around **256 MB** messages for 8 GPUs | Small all-reduce payloads may not reach nominal bandwidth; message size is a required control. |
| NCCL participant-count pathology | N/A | The paper reports significant NUMA/congestion behavior around **5 GPUs** and recommends avoiding 5-GPU application setups | Rank count can interact with NCCL algorithm choice; powers of two are not just aesthetic. |
| Application-level scale-up | Baseline PCIe paths often remain competitive because many applications use CPU-master/GPU-slave communication and avoid D2D transfers | NVLink microbenchmark gains usually do **not** translate into whole-application speedup; exceptions include CSM and a reported **~6%** latency reduction for GMM after an NCCL-based rewrite | For vLLM, the relevant evidence is not nominal link bandwidth but measured NCCL share in the decode step. |

### Bandwidth table

Values below are the paper's reported values when present in the text, and
approximate values read from the figures otherwise. They should be used for
order-of-magnitude reasoning, not as constants for H200/NVLink 4-way.

| Benchmark / platform | PCIe bandwidth | NVLink / NVSwitch bandwidth | Notes |
|---|---:|---:|---|
| P2P unidirectional, DGX-1, large messages | **~10-12 GB/s** | NVLink-V1 one link: **~18-20 GB/s**; NVLink-V2 one link: **~22-25 GB/s**; NVLink-V2 dual-link route: **~45-50 GB/s** | Figure 6 / Figure 15. V100 NVLink-V2 dual-link paths are the relevant contrast to PCIe Gen3. |
| P2P bidirectional, DGX-1, large messages | **~20-24 GB/s** aggregate | NVLink-V1 one link: **~35-40 GB/s**; NVLink-V2 one link: **~45-50 GB/s**; NVLink-V2 dual-link route: **~90-100 GB/s** | Figure 7 / Figure 15. Bidirectional traffic exposes topology differences more clearly than unidirectional traffic. |
| P2P, DGX-2, large messages | PCIe off-diagonal pairs roughly **~16-20 GB/s** | NVSwitch off-diagonal pairs are mostly **>200 GB/s**, with per-GPU fabric paths approaching **~300 GB/s** | Figure 12 / Figure 13 and NVSwitch topology description. NVSwitch is not the same as 4-way NVLink bridges, but it shows the value of UMA fabric. |
| NCCL collective bandwidth, DGX-1, 1 GB payload, 8 GPUs | PCIe is much lower and decreases as GPU count rises | NVLink-V1 reaches roughly **~60 GB/s**; NVLink-V2 roughly **~120 GB/s** | Figure 20. Paper states NVLink-V2 is about **2x** NVLink-V1 at 8 GPUs. |
| NCCL collective bandwidth, DGX-1, 1 GB payload, 4 GPUs | PCIe lower, topology-contended | NVLink-V2 about **1.6x** NVLink-V1 | Figure 20. The paper reports the ratio explicitly; exact values depend on collective primitive. |
| Collective bandwidth saturation, 8 GPUs | Saturates around **16 MB** message size | Saturates around **256 MB** message size | Figure 21. This matters for LLM all-reduce because small messages may be latency/overhead-bound instead of bandwidth-bound. |

## What I can measure in nanoserve-mini

- **Hypothesis:** NVLink 4-way should matter only when the vLLM decode step is dominated by NCCL/all-reduce communication across TP>=4 ranks. If the step is host-floor-bound, kernel-bound, or TP<=2, nominal link bandwidth should not translate into a useful serving gain.
- **Script:** existing `vllm bench serve` runs, torch profiler traces, `dcgmi dmon` PCIe/NVLink counters, and future minimal NCCL/all-reduce microbenchmarks for 2/4/8 ranks and selected GPU placements.
- **Workload:** Kimi TP8 and Qwen TP2/TP4/TP8 under c=1 and high-concurrency decode-heavy load; include same-switch, same-socket, and cross-socket placements where possible.
- **Metrics:** ITL/TPOT, output tokens/s, trace share for NCCL vs compute vs gaps, PCIe TX/RX or NVLink TX/RX, power, SM activity, DRAM activity, GPU placement, rank count, and message-size proxy if available from trace/config.
- **Expected signal:** A real interconnect bottleneck should show high NCCL share, sustained interconnect traffic near the measured ceiling, worsening with more TP ranks, and improvement only when the faster path covers the communication actually used by NCCL.

## Actions created from this paper

- [ ] Use this paper as background evidence when explaining why NVLink benefit must be bounded by measured NCCL share, not by nominal bandwidth.
- [ ] Add a future W2 sanity check for NCCL/all-reduce latency and bandwidth across 2/4/8 ranks and selected GPU placements before making broader TP-scaling claims.
- [ ] In write-ups, separate microbenchmark evidence from application/serving evidence; the paper is strong for topology intuition but not direct evidence for vLLM speedup.

## Potential LinkedIn angle

Nominal GPU interconnect bandwidth is a weak predictor of application speedup; the useful question is whether the measured communication path is large enough, frequent enough, and actually routed over the faster fabric.

## Final takeaway

This paper reinforces the conservative NVLink decision model in `nanoserve-mini`.
The project should not argue from "NVLink is faster" to "serving is faster";
it should argue from measured NCCL share, rank count, placement, message size,
and observed interconnect counters. For LLM serving, the paper is background,
not proof: it tells what to measure and what claims to avoid.
