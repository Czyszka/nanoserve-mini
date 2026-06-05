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

The 2026-06-05 session ran all three caps with **filenames and `verify_cap*.txt`
confirming the runtime value matches the intent** (`verify_cap020.txt`:
`intended=0.20 runtime=0.2`; `verify_cap025.txt`: `intended=0.25 runtime=0.25`).
This closes the filename↔runtime mismatch that made the 2026-05-27 and
2026-06-03 attempts unusable.

DeepSeek's weight footprint is constant at **20.32 GiB per GPU** (TP=8,
`deepseek_v4_fp8` quantization, `fp8_ds_mla` KV-cache format, `max_model_len`
65,536). The cap only moves the KV-cache budget that is left after weights and
overhead:

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

## Co-residency headroom

`nvidia-smi` per GPU (board total 143,771 MiB ≈ 143.8 GiB, shared with the
co-resident Kimi worker at ~86.8 GiB):

| Cap | Board used | Free headroom |
|---|---|---|
| 0.20 | ~116.3 GiB | ~27 GiB |
| 0.25 | ~123.4 GiB | ~20 GiB |

Raising 0.20 → 0.25 spends ~7 GiB of board per GPU to roughly double DeepSeek's
KV cache (6.5 → 13.49 GiB, 5,284 → 10,992 tokens). For a single-stream W1
baseline, 6.51× concurrency at 64k context is already far more than needed, so
the marginal KV is not worth the ~7 GiB of headroom it takes from Kimi and
stability margin. Hence 0.20.

## Serviceability check

Both healthy caps served an identical smoke request (`"say OK"` →
`"OK"`, 2 tokens) to completion with near-identical latency — `ttft_cap020.json`
15.23 s / E2E 21.66 s, `ttft_cap025.json` 15.18 s / E2E 21.65 s. These are
**cold first-request numbers** (warmup 0, 1 measured run), not a latency claim;
their value here is only that the cap choice does not change whether DeepSeek
serves, and that 0.20 vs 0.25 are indistinguishable on serviceability.

## Limits

- **Phase 1 stability decision, not a global optimum.** The right cap depends on
  the co-resident Kimi footprint, target concurrency, and context length. With a
  different second model or no co-tenant, the budget math changes.
- **No concurrency/throughput sweep.** This justifies *which cap starts and
  leaves headroom*, not DeepSeek's throughput curve. KV-token capacity
  (5,284 vs 10,992) bounds concurrency but was not load-tested here.
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
| Runtime cap == intended cap (mismatch closed) | `verify_cap020.txt`, `verify_cap025.txt` |
| Board memory / co-residency headroom | `nvidia_smi_cap020.txt`, `nvidia_smi_cap025.txt`, `nvidia_smi_cap015_FAILED.txt` |
| Both caps serve a smoke request to completion | `ttft_cap020.json`, `ttft_cap025.json` |
| Default restored to 0.20 after sweep | `log_restored_default.txt`; compose `serving/compose/docker-compose.kimi-k2.6.yml` (`DEEPSEEK_GPU_MEM_UTIL:-0.2`) |
