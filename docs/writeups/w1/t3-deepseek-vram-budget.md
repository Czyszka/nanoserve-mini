# T3 — DeepSeek VRAM budget in the multi-model baseline

## Question

What VRAM cap should DeepSeek-V4-Flash run under while sharing the 8×H200 node
with Kimi-K2.6, and what evidence supports that choice?

## Planned shape

Mode: justification with numbers.

Expected structure:

1. Decision — run DeepSeek with a bounded VRAM cap in the multi-model baseline.
2. Rejected alternatives — 25%, 15%, and auto/unbounded allocation.
3. Reasoning — leave enough headroom for Kimi, runtime memory, KV cache, and stability.
4. Evidence — model load logs and memory snapshots across candidate caps.
5. Limit — Phase 1 stability decision, not a global optimal configuration.

## 2026-05-27 evidence — partial baseline only

The 2026-05-27 session captured a DeepSeek-V4-Flash startup/runtime log and one
direct TTFT smoke result. This is useful as a runtime baseline, but it does
**not** complete the planned VRAM sweep.

> **Important caveat.** The artifact filename says `cap020`, but the vLLM
> runtime log records `gpu_memory_utilization: 0.25`
> (`t3_deepseek_vram/log_cap020_baseline.txt` line 8). Therefore this evidence
> is treated as a **0.25 runtime baseline** until proven otherwise.

Recorded runtime facts (from `log_cap020_baseline.txt`):

- vLLM `0.20.0`,
- model `deepseek-ai/DeepSeek-V4-Flash`, `quantization=deepseek_v4_fp8`,
- TP=8, `dtype=torch.bfloat16`,
- FP8 KV cache (`fp8_ds_mla` format),
- MTP speculative config with `num_speculative_tokens=1`,
- `max_model_len=65536`,
- `max_num_seqs=2`,
- `max_num_batched_tokens=2048` (vLLM warned this may be suboptimal with the
  speculative settings; `max_num_scheduled_tokens` pinned to 2048),
- `block_size=256`,
- `enforce_eager=True` (numbers are eager-mode, no CUDA graph capture),
- available KV cache memory: ~13.5 GiB,
- GPU KV cache size: 10,996 tokens,
- short direct TTFT request completed (`ttft_cap020.json`: `ttft_seconds`
  ~0.328 s, `e2e_seconds` ~0.521 s, `completion_tokens` 2).

## Conclusion

This evidence supports that DeepSeek could start and serve a short request under
the recorded configuration, but it does **not** yet justify the final VRAM cap
choice — and it does not validate the previously committed 0.20 default that the
same compose file (`serving/compose/docker-compose.kimi-k2.6.yml`)
simultaneously moved to 0.25.

## Evidence still needed

- Explicit `DEEPSEEK_GPU_MEM_UTIL=0.15` / `0.20` / `0.25` runs with filenames
  matching the actual runtime cap.
- Kimi memory footprint after load (co-resident headroom).
- GPU memory snapshots before/after each service starts.
- Any failure/instability logs for rejected caps.
