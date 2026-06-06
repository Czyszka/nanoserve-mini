# T1 — Bringing up Kimi-K2.6 on a single 8×H200 node

Mode: investigation.

## Symptom

The first bring-up attempt for Kimi-K2.6 used **data + expert parallelism**
(`--data-parallel-size 8 --enable-expert-parallel`, "DEP"), at
`--gpu-memory-utilization 0.6` — a cap chosen so Kimi could **share the node with
the co-resident DeepSeek-V4-Flash** service (`vllm-small` on `:8004`, itself at
`gpu-memory-utilization 0.2`, ~29 GiB/GPU), which was running throughout the
attempt (`session/docker_ps_start.txt`, `session/nvidia_smi_start.txt`). The container **exited 1** during startup
(`t1_dep/dep_state.txt`). It was a clean crash, not a hang: **all eight
engine-core processes raised the same exception** and the process group tore down
(`t1_dep/dep_startup.log`, `EngineCore_DP{0..7}` tracebacks).

## What was attempted

The captured launch command (`t1_dep/dep_engine_cmd.json`) is the DEP path:

```
--model moonshotai/Kimi-K2.6 --enable-expert-parallel
--data-parallel-size 8 --gpu-memory-utilization 0.6
--max-num-seqs 1 --max-model-len 131072 ...
```

The two parallelism shapes differ in what each GPU has to hold. **Tensor
parallelism (TP) shards every weight tensor across the GPUs**, so each GPU holds
a *slice* of the whole model and all eight cooperate on each request. **Data
parallelism (DP) replicates the model** — *every* weight (embeddings, attention,
and, without EP, the experts too) — and runs independent copies, each serving its
own request stream. **Expert parallelism (EP)** then shards the MoE experts across
ranks, so under DP+EP only the **non-expert (dense/attention) path is replicated**
while the experts are split 1/8 per rank.

Concretely for Kimi-K2.6, what lands on each GPU under this DEP config:

| Component | What it is | Under DEP |
|---|---|---|
| embeddings + lm_head | token tables | **replicated** (every rank) |
| per-layer: MLA attention + norms + router/gate + shared/dense FFN | the dense, always-on backbone (log: `FLASH_ATTN_MLA`) | **replicated** (~22 GiB/GPU) |
| per-layer: 384 routed experts | the sparse MoE bulk | **EP-sharded**, 48/rank (~66.6 GiB/GPU) |

The EP split is explicit in the log: `[EP Rank 0/8] … Local/global number of
experts: 48/384`, placement strategy `linear`, with rank 0 owning experts 0–47
(`layer.py:408`). The intent was a DP-for-MoE recipe; this thread is why that
shape did not fit our concrete single-node hardware.

## Evidence — weights loaded, the KV budget went negative

vLLM does not ask "do the weights fit on the GPU"; it asks "after loading weights
and profiling activations, is anything left **inside my `gpu-memory-utilization`
ceiling** for the KV cache?" Startup got **past** weight loading and failed in
KV-cache sizing after a successful load (`t1_dep/dep_full.log`,
`t1_dep/dep_startup.log`). The per-GPU arithmetic:

```
budget   = 0.6 × 140.40 GiB (total = 143771 MiB)          =  84.24 GiB
− weights (DEP)                                            =  88.44 GiB   [gpu_model_runner.py:4879]
− CUDA-graph (measured)                                    =   0.13 GiB   [gpu_model_runner.py:6042]
− activation peak (8192-tok prefill) + non-torch (resid.)  ≈  14.75 GiB
──────────────────────────────────────────────────────────────────────
= Available KV cache memory                                = −19.08 GiB   [gpu_worker.py:440]
```

Consequently all eight `EngineCore_DP{0..7}` raised the identical error in
`_check_enough_kv_cache_memory`:

```
ValueError: No available memory for the cache blocks. Try increasing
`gpu_memory_utilization` when initializing the engine.
```

### What fits, and what does not

This is the crux, and the two ceilings are easy to conflate:

- **The weights fit the GPU.** The checkpoint loaded successfully
  (`Model loading took 88.44 GiB memory`). Even with DeepSeek (~29 GiB/GPU, at
  its own `gpu-memory-utilization 0.2`) co-resident, total physical use
  (~29 + 88.44 + ~15 ≈ 132 GiB) stayed under the 140.40 GiB card. Loading is
  **not** where it failed.
- **The weights do not fit the budget.** Kimi's own non-KV footprint
  (88.44 + 0.13 + 14.75 = **103.32 GiB**) exceeds its self-imposed `0.6` ceiling
  (**84.24 GiB**). After subtracting it, **−19.08 GiB** is left for the KV cache —
  so the engine refuses to start.

Why does the 88.44 GiB load at all if the budget is only 84.24 GiB? Because
`gpu-memory-utilization` is **not** a load-time allocation cap. The loader
allocates weights against the GPU's *actual free* memory (~111 GiB with DeepSeek
resident), so the load completes 100% (`Model loading took 88.44 GiB`, 09:25:32).
The `0.6` ceiling enters only ~2 minutes later, when vLLM sizes the KV pool as
`budget − measured non-KV` (`Available KV cache memory`, 09:27:18) — that is the
only place the cap is applied, and it is where the overshoot becomes a negative
number. The crash is therefore *after* a successful load, not during it; raising
the cap would size a positive KV pool without changing anything physical.

The weights alone (88.44 GiB) already overshoot the budget (84.24 GiB) by 4.2 GiB
*before* activations. (An earlier draft's "≈86 GiB available" conflated GB with
GiB: the ceiling is `0.6 × 140.40 GiB = 84.24 GiB`, not 86.)

**DeepSeek co-residency is context, not the cause.** The −19.08 figure is computed
from Kimi's *own* budget minus Kimi's *own* non-KV memory; DeepSeek's ~29 GiB is
**not** in that number — were it included, the deficit would be ~−48 GiB, not
−19. DeepSeek is why the cap is `0.6` in the first place: headroom for two
co-resident models — DeepSeek itself runs at `0.2`, the cap that is the subject of
T3 — the same budgeting discipline. It did not arithmetically cause this crash.

## Reading the failure — DEP replicates what TP shards

This is a memory-budget overflow created by the parallelism shape: **DEP
replicates the non-expert weights on every GPU, while TP shards them.** The
checkpoint is **554.30 GiB** (`t1_dep/dep_startup.log`), with the MoE experts
quantized to **4-bit** (Marlin `WNA16`, `num_bits=4`,
`compressed_tensors_moe_wna16_marlin.py:87`) and EP splitting them 48/384 = 1/8
per rank. Decomposing the per-GPU weight footprint:

| Weight class | Whole model | DEP /GPU | TP /GPU |
|---|---:|---:|---:|
| experts (4-bit, EP-sharded 1/8) | ~532 GiB | 66.6 | 66.6 |
| non-experts (higher precision, **replicated under DEP**) | ~22 GiB | 21.9 | 2.7 |
| **total** | 554.30 | **88.44** | **69.3** |

The split is derived from the measured 88.44 GiB/GPU against `554.30 / 8`,
assuming loaded ≈ on-disk size; ~532 GiB of 4-bit experts is on the order of ~1 T
expert parameters, consistent with Kimi-K2's ~1T-parameter MoE.

The DEP penalty is the replicated non-expert weights: `(7/8) × 21.9 ≈ 19.1
GiB/GPU` carried on every GPU that TP would not. TP=8 sharding recovers roughly
that ~19 GiB/GPU, which is what flips the KV budget from negative back to positive
at the same `gpu-memory-utilization`. (The near-equality of the ~19.1 GiB
replication penalty and the −19.08 GiB deficit is a coincidence of two
separately-computed quantities, not an identity.)

vLLM's own suggestion ("increase `gpu_memory_utilization`") would likely let DEP
start at a higher cap, but that was not the chosen fix, for two reasons. First,
raising the cap spends co-residency headroom — DeepSeek is on the same GPUs — to
host weights that TP would not replicate at all. Quantitatively: DEP carries
~19.1 GiB/GPU more weights than TP, so matching TP-at-0.6's KV pool would need
`util ≈ 0.6 + 19.1/140.40 ≈ 0.74` (the activation overhead cancels in the match;
this is a *lower* bound, since DEP's replicated dense path also enlarges
activation). At 0.74 Kimi alone claims ~104 GiB; with DeepSeek's `0.2` (~28 GiB)
the two reserve ~0.94 of the 140.40 GiB card, leaving ~6% (~8 GiB) for the
out-of-budget CUDA/NCCL/NIXL buffers both engines need — so co-resident DEP at
TP-equivalent KV is effectively infeasible, not merely wasteful. (TP-at-0.6, by
contrast, leaves ~27 GiB of card headroom.) Second, and decisive for W1,
**DP's payoff is throughput under concurrency**: eight replicas serve eight
independent request streams in parallel, so the gain only materializes when there
*are* concurrent requests. W1's baseline is single-stream (`--max-num-seqs 1`),
where DP replicas add memory cost and buy nothing.

## Redirect — TP=8 as the Phase 1 path

The bring-up switched to tensor parallelism (`--tensor-parallel-size 8`), the
working configuration recorded in `session/restore_engine_cmd.json` that serves
Kimi-K2.6 on `:8000` for every other W1 thread (T2, T4, T6, T8). TP=8 shards the
full weight tensor across the node, restores a positive KV-cache budget at
`gpu-memory-utilization 0.6`, and is the config used both for the single-stream
baselines and for the batched (`--max-num-seqs 32`) load run in T5.

The deficit is independent of the configured `--max-num-seqs`: it is a
**load-time** budget overflow decided before any request is served. The weights
alone (88.44 GiB) exceed the budget, so KV is negative at `--max-num-seqs 1` and
only *more* negative at 32 (a larger profiling batch raises the activation term) —
never positive. DP's concurrency advantage could therefore never be measured in
W1 — the engine never started. Whether DP throughput would beat TP under real
concurrency is a separate, unanswered question that needs a DEP config which
starts first.

## What this does NOT show

- **No throughput comparison.** This thread explains a startup-time memory
  failure; it does not measure DP vs TP serving throughput under concurrency.
- **One driver/runtime.** vLLM v0.20-series, CUDA 13.2, driver 595.58.03 on OS
  Linux Ubuntu 24; the memory math is specific to that build and model revision.

## Evidence

| Claim | Source |
|---|---|
| DEP container `exited 1`; all 8 engine-cores crashed identically | `results/runs/2026-06-05_w1_evidence/t1_dep/dep_state.txt`; `…/dep_startup.log` (`EngineCore_DP{0..7}` tracebacks) |
| DEP launch command (DP=8 + EP, util 0.6, max-num-seqs 1) | `results/runs/2026-06-05_w1_evidence/t1_dep/dep_engine_cmd.json` |
| DeepSeek co-resident during the attempt | `results/runs/2026-06-05_w1_evidence/session/docker_ps_start.txt` (`vllm-small :8004` up); `…/session/nvidia_smi_start.txt` |
| Total GPU 143771 MiB = 140.40 GiB → budget 0.6 × = 84.24 GiB | `results/runs/2026-06-05_w1_evidence/session/nvidia_smi_start.txt`; `…/t1_dep/dep_engine_cmd.json` |
| Weights 88.44 GiB/GPU (load succeeded) | `results/runs/2026-06-05_w1_evidence/t1_dep/dep_full.log` / `dep_startup.log` (`gpu_model_runner.py:4879`) |
| CUDA-graph 0.13 GiB; util 0.6000 ≈ 0.5991 effective (cross-check) | `results/runs/2026-06-05_w1_evidence/t1_dep/dep_full.log` (`gpu_model_runner.py:6042`, `gpu_worker.py:455`) |
| `Available KV cache memory: -19.08 GiB` → `ValueError` in `_check_enough_kv_cache_memory` | `results/runs/2026-06-05_w1_evidence/t1_dep/dep_full.log` (`gpu_worker.py:440`) |
| Checkpoint 554.30 GiB; experts 4-bit Marlin WNA16; EP 48/384, `linear` placement (rank 0 → experts 0–47) | `results/runs/2026-06-05_w1_evidence/t1_dep/dep_startup.log` (`compressed_tensors_moe_wna16_marlin.py:87`; `layer.py:408` EP Rank 0/8) |
| Working TP=8 redirect command | `results/runs/2026-06-05_w1_evidence/session/restore_engine_cmd.json` |

All artifacts organized under commit `d0bb634`. Hardware/driver facts:
`docs/operations/infrastructure.md` (8×H200 NVL, CUDA 13.2, driver 595.58.03).
