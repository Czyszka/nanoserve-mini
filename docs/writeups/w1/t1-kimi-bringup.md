# T1 — Bringing up Kimi-K2.6 on a single 8×H200 node

Mode: investigation.

## Symptom

The first bring-up attempt for Kimi-K2.6 used **data + expert parallelism**
(`--data-parallel-size 8 --enable-expert-parallel`, "DEP"). The container
**exited 1** during startup (`t1_dep/dep_state.txt`). It was a clean crash, not
a hang: all eight engine-core processes raised the same exception and the
process group tore down.

## What was attempted

The captured launch command (`t1_dep/dep_engine_cmd.json`) is the DEP path:

```
--model moonshotai/Kimi-K2.6 --enable-expert-parallel
--data-parallel-size 8 --gpu-memory-utilization 0.6
--max-num-seqs 1 --max-model-len 131072 ...
```

DP=8 + EP runs eight data-parallel replicas; expert-parallelism shards the MoE
experts across the eight ranks, but the **dense/attention path is replicated per
DP rank**. The intent was to follow a DP-for-MoE recipe; the question this thread
answers is why that recipe did not fit our concrete single-node hardware.

## Evidence — weights loaded, KV cache went negative

Startup got past weight loading and failed at KV-cache sizing
(`t1_dep/dep_full.log`):

- Checkpoint is **554.30 GiB** on disk (FP8).
- Each worker loaded **88.44 GiB** of weights onto its single H200
  (`gpu_model_runner: "Model loading took 88.44 GiB memory"`).
- At `--gpu-memory-utilization 0.6`, the per-GPU budget is ≈0.6 × 143 GiB ≈
  **86 GiB**. Weights (88.44 GiB) plus runtime/activation overhead overran it,
  so vLLM reported **`Available KV cache memory: -19.08 GiB`** — a negative KV
  budget.
- Consequently all eight `EngineCore_DP{0..7}` raised the identical error in
  `_check_enough_kv_cache_memory`:

  ```
  ValueError: No available memory for the cache blocks. Try increasing
  `gpu_memory_utilization` when initializing the engine.
  ```

The crash point matters: it is **after** a successful model load, in KV-cache
profiling. The model fit; it left no room to serve.

## Reading the failure

This is not a topology incompatibility or a missing feature — it is a memory
budget overflow caused by the parallelism choice:

- **DP=8 + EP replicates the dense/attention weights on every GPU** and shards
  only the experts, so each H200 holds **88.44 GiB**.
- **TP=8 shards *all* weights** (dense, attention, and experts) across the eight
  GPUs, so each GPU holds roughly 554 GiB / 8 ≈ **69 GiB** — about **19 GiB
  less per GPU** than DEP, almost exactly the size of the negative KV budget
  (−19.08 GiB). That replicated dense/attention footprint is what tips KV cache
  from positive to negative at the same `gpu-memory-utilization`.

vLLM's own suggestion ("increase `gpu_memory_utilization`") would likely let DEP
start at a higher cap, but that was not the chosen fix, for two reasons. First,
raising the cap spends stability margin to host weights that TP would not
replicate at all. Second, **DP=8 buys nothing for the W1 baseline**: data
parallelism scales independent request streams, while W1 is a single-stream,
`--max-num-seqs 1` latency baseline. Eight replicas of the dense path is the
wrong shape for that goal.

## Redirect — TP=8 as the Phase 1 path

The bring-up switched to tensor parallelism (`--tensor-parallel-size 8`), which
is the working configuration recorded in `session/restore_engine_cmd.json` and
serves Kimi-K2.6 on `:8000` for every other W1 thread (T2, T4, T6, T8). TP=8
shards the full weight tensor across the node, restores a positive KV-cache
budget at `gpu-memory-utilization 0.6`, and matches the single-node,
low-concurrency baseline that W1 is measuring.

## What this does NOT show

- **Not a claim that DEP/DP is unusable in general.** The evidence is specific:
  DP=8 + EP at `gpu-memory-utilization 0.6` overflows a 143 GiB H200 for this
  ~1T-parameter FP8 checkpoint. A higher cap, fewer DP replicas, or more GPUs
  could change that outcome.
- **No throughput comparison.** This thread explains a startup-time memory
  failure; it does not measure DP vs TP serving throughput under concurrency.
- **One driver/runtime.** vLLM v0.20-series, CUDA 13.2, driver 595.58.03 on
  ubuntusrv2; the memory math is specific to that build and model revision.

## Evidence

| Claim | Source |
|---|---|
| DEP container `exited 1` | `results/runs/2026-06-05_w1_evidence/t1_dep/dep_state.txt` |
| DEP launch command (DP=8 + EP) | `results/runs/2026-06-05_w1_evidence/t1_dep/dep_engine_cmd.json` |
| 88.44 GiB weights/GPU; `Available KV cache memory: -19.08 GiB`; identical `ValueError` on all 8 `EngineCore_DP` | `results/runs/2026-06-05_w1_evidence/t1_dep/dep_full.log` |
| Full captured startup log | `results/runs/2026-06-05_w1_evidence/t1_dep/dep_startup.log` |
| Working TP=8 redirect command | `results/runs/2026-06-05_w1_evidence/session/restore_engine_cmd.json` |

All artifacts organized under commit `d0bb634`. Hardware/driver facts:
`docs/operations/infrastructure.md` (8×H200 NVL 143 GB, CUDA 13.2,
driver 595.58.03).
