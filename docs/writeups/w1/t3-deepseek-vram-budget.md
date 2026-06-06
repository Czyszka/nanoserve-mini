# T3 — DeepSeek VRAM budget in the multi-model baseline

Mode: justification with numbers.

## Question

What `--gpu-memory-utilization` cap should DeepSeek-V4-Flash run under while
sharing each 8×H200 GPU with Kimi-K2.6, and what evidence supports that choice
rather than a higher or lower cap?

## Decision

Run DeepSeek at **`DEEPSEEK_GPU_MEM_UTIL=0.20`** as the Phase 1 default.
**0.15 is a hard lower bound — it fails to start.** 0.25 also works and offers
roughly double the KV cache; it remains the documented alternative when DeepSeek
needs more concurrency. 0.20 is chosen as the conservative co-residency point:
enough KV cache for the single-stream baseline while leaving the most board
headroom for the co-resident Kimi service.

## The clean sweep

DeepSeek-V4-Flash launches on `:8004` with the cap supplied from the environment
(`DEEPSEEK_GPU_MEM_UTIL`, compose `vllm-small` service); the 2026-06-05 session
swept three values. Key vLLM serve args for the 0.20 run, from the `non-default
args` line in `log_cap020.txt`:

```
--model deepseek-ai/DeepSeek-V4-Flash --port 8004 --tensor-parallel-size 8
--max-model-len 65536 --gpu-memory-utilization 0.2 --kv-cache-dtype fp8
--block-size 256 --max-num-batched-tokens 2048 --max-num-seqs 2 --enforce-eager
--speculative-config '{"method":"mtp","num_speculative_tokens":1,"max_model_len":8192}'
```

(full arg list in the log; `gpu_memory_utilization: 0.2` there is the runtime
confirmation that the cap took effect.)

DeepSeek's weight footprint is constant at **20.32 GiB per GPU** —
`gpu_model_runner.py:4879` logs `Model loading took 20.32 GiB memory`
(`log_cap020.txt`), identical across all three caps (`deepseek_v4_fp8`
quantization, `fp8_ds_mla` KV-cache format, `max_model_len` 65,536). The cap only
moves the KV-cache budget left after weights and overhead:

| Cap | Available KV cache | GPU KV cache size | Max concurrency @ 64k ctx | Outcome |
|---|---|---|---|---|
| **0.15** | **−0.49 GiB** | — | — | **fails — `EngineCore failed to start`** |
| **0.20** | 6.5 GiB | 5,284 tokens | 6.51× | healthy |
| **0.25** | 13.49 GiB | 10,992 tokens | 13.54× | healthy |

At 0.15 the budget is negative by 0.49 GiB — the same failure family as T1's
DEP attempt: `Available KV cache memory: -0.49 GiB`, then `EngineCore failed to
start`, and `cap015_status.txt` records "did NOT come up healthy (possible OOM /
too low headroom)". The model weights fit; there was simply no room left to
allocate cache blocks once Kimi was already co-resident.

## Reading the vLLM KV-cache numbers

vLLM prints these lines at startup for the 0.20 run (`log_cap020.txt`):

```
[gpu_worker.py:440]    Available KV cache memory: 6.5 GiB
[kv_cache_utils.py:1711] GPU KV cache size: 5,284 tokens
[kv_cache_utils.py:1716] Maximum concurrency for 65,536 tokens per request: 6.51x
```

The first line is the unambiguous budget. The two token figures, however, do
**not** reconcile by naive division —
5,284 tokens ÷ 65,536 = 0.08, not 6.51× — because they come from two different
code paths in vLLM's `kv_cache_utils.py`, and DeepSeek-V4 is exactly the
multi-group case where they diverge.

- **`GPU KV cache size: 5,284 tokens`** (`_report_kv_cache_config`) is
  `(num_blocks / number_of_KV_cache_groups) × min_block_size`: the whole block
  pool divided by the *number* of KV-cache groups, times the *smallest* block
  size across them. It is a per-group display figure, **not** the total token
  capacity.
- **`Maximum concurrency for 65,536 tokens per request: 6.51x`**
  (`get_max_concurrency_for_kv_cache_config`) is
  `num_blocks ÷ blocks_needed_for_one_max_model_len_request`, where the
  per-request cost is the real KV memory summed across all layers/groups. This
  *is* the trustworthy capacity signal: ~6.51 concurrent 65,536-token requests
  fit.

DeepSeek-V4 carries **more than one KV-cache structure** — the `fp8_ds_mla`
MLA latent cache plus a separate FP8 cache for the "Lightning Indexer" sparse
attention (`log_cap020.txt`, `deepseek_v4_attention.py`). With more than one
group, the size-line's `/groups × min_block_size` normalization deflates it,
while the concurrency line accounts for true per-request memory — so the two
part ways. The deflation is systematic, not noise: the factor is identical at
both caps.

| Cap | size line | concurrency × 64k (true ≈) | ratio |
|---|---:|---:|---:|
| 0.20 | 5,284 tok | 6.51 × 65,536 ≈ 426,640 tok | 80.7× |
| 0.25 | 10,992 tok | 13.54 × 65,536 ≈ 887,358 tok | 80.7× |

So DeepSeek's real KV capacity at 0.20 is **~427k tokens (~6.5 full 64k
contexts)**, not 5,284 — the latter is a vLLM display artifact. This is a
**known, still-open vLLM bug**: `vllm-project/vllm#40691` — "[Bug]: The KV cache
size log is wrong for Qwen3.5" (Open as of 2026-06-06) — reports exactly this,
that *Maximum concurrency × max_model_len ≠ the reported GPU KV cache size* for
hybrid models with shared tensor pools and varying block sizes. The discrepancy
is upstream in vLLM's logging, not in our capture. Throughout this thread, read
`Available KV cache` (GiB) and `Maximum concurrency` as the real signals and the
tokens line as informational only.

## Co-residency headroom

`nvidia-smi` per GPU (board total 143,771 MiB = 140.40 GiB, shared with the
co-resident Kimi worker at ~84.8 GiB / 86,860 MiB):

| Cap | DeepSeek footprint | Board used | Free headroom |
|---|---|---|---|
| 0.20 | ~28.9 GiB (29,632 MiB) | ~113.8 GiB | ~26.6 GiB |
| 0.25 | ~35.9 GiB (36,806 MiB) | ~120.8 GiB | ~19.6 GiB |

Raising 0.20 → 0.25 spends ~7 GiB of board per GPU (DeepSeek 28.9 → 35.9 GiB) to
roughly double DeepSeek's KV cache (6.5 → 13.49 GiB). For a single-stream W1
baseline the 0.20 KV budget is already far more than needed (~6.5 full 64k
contexts — see "Reading the vLLM KV-cache numbers" above), so the marginal KV is
not worth the ~7 GiB of headroom it takes from
Kimi and stability margin. Hence 0.20.

## Serviceability check

Both healthy caps served an identical smoke request (`"say OK"` →
`"OK"`, 2 tokens) to completion with near-identical latency — `ttft_cap020.json`
15.23 s / E2E 21.66 s, `ttft_cap025.json` 15.18 s / E2E 21.65 s. These are
**cold first-request numbers** (warmup 0, 1 measured run), not a latency claim;
their value here is only that the cap choice does not change whether DeepSeek
serves, and that 0.20 vs 0.25 are indistinguishable on serviceability.

## Why it matters: what 0.20 vs 0.25 gives and takes

The board is fixed (140.40 GiB) and shared by two models, so the cap is not a
tuning nicety — it is the knob that partitions a finite GPU between Kimi's and
DeepSeek's KV pools. The sweep exists to find the safe, sufficient split: too
low (0.15) and DeepSeek will not even start (negative KV, the same wall as T1);
too high and it starves the co-tenant's headroom.

| Cap | What it gives for serving | What it takes |
|---|---|---|
| **0.20** (chosen) | ~6.5 concurrent 64k-context requests of KV room — far above the single-stream W1 need; ~26.6 GiB board left free as a stability/spike margin shared with Kimi | caps DeepSeek's concurrency / long-context ceiling at ~half of 0.25 — binding only once DeepSeek actually serves heavy concurrent or long-context traffic |
| **0.25** | ~13.5 concurrent 64k contexts (2× the KV) — real room for concurrent or longer-context DeepSeek workloads | ~7 GiB more board per GPU → free drops to ~19.6 GiB, eating the margin that protects the latency-critical Kimi reasoning service and absorbs load spikes / fragmentation (higher OOM risk under pressure) |

For W1 the workload is single-stream (client concurrency 1), so DeepSeek's
concurrency demand is ~1 and even 0.20's ~6.5× is far more than used; the extra
KV from 0.25 buys concurrency W1 never exercises while taking headroom from the
latency-critical co-tenant. Hence **0.20 as the Phase 1 default, with 0.25 the
documented switch** for when a real DeepSeek workload — higher concurrency or
longer effective context — makes KV the binding resource rather than board
headroom.

## Limits

- **Phase 1 stability decision, not a global optimum.** The right cap depends on
  the co-resident Kimi footprint, target concurrency, and context length. With a
  different second model or no co-tenant, the budget math changes.
- **No concurrency/throughput sweep.** This justifies *which cap starts and
  leaves headroom*, not DeepSeek's throughput curve. The KV pool implies
  ~6.51× / 13.54× concurrency at 64k (≈427k / 887k tokens; see the reading note
  above), but this was not load-tested here.
- **Single capture per cap.** One startup + one smoke per cap; no repeated
  cold/warm separation.

## Evidence

All artifacts under `results/runs/2026-06-05_w1_evidence/t3_deepseek_vram/`
(organized in commit `d0bb634`):

| Claim | Source |
|---|---|
| 0.15 fails: `Available KV cache memory: -0.49 GiB` → EngineCore crash | `log_cap015_FAILED.txt`, `cap015_status.txt` |
| 0.20 healthy: 6.5 GiB KV, 5,284 tokens, 6.51× | `log_cap020.txt` |
| 0.25 healthy: 13.49 GiB KV, 10,992 tokens, 13.54× | `log_cap025.txt` |
| Runtime cap == intended cap | `verify_cap020.txt`, `verify_cap025.txt`; `log_cap020.txt` `non-default args` |
| Board memory / co-residency headroom | `nvidia_smi_cap020.txt`, `nvidia_smi_cap025.txt`, `nvidia_smi_cap015_FAILED.txt` |
| Both caps serve a smoke request to completion | `ttft_cap020.json`, `ttft_cap025.json` |
| Default restored to 0.20 after sweep | `log_restored_default.txt`; compose `serving/compose/docker-compose.kimi-k2.6.yml` (`DEEPSEEK_GPU_MEM_UTIL:-0.2`) |
