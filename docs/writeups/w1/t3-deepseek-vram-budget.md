# T3 — Why DeepSeek runs at 20% VRAM

<!-- TODO: justification segment. Numbers from Kimi + DeepSeek weight-load
logs across a few DeepSeek VRAM-cap values.

Evidence (planned 2026-05-27 server session, see docs/plans/2026-05-27-server-session.md Cz. B; sweep limited to 0.15/0.25 around the chosen 0.20):
- results/runs/2026-05-27_w1_evidence/t3_deepseek_vram/log_cap020_baseline.txt
- results/runs/2026-05-27_w1_evidence/t3_deepseek_vram/log_cap015.txt
- results/runs/2026-05-27_w1_evidence/t3_deepseek_vram/log_cap025.txt
- results/runs/2026-05-27_w1_evidence/t3_deepseek_vram/ttft_cap{015,020,025}.json
-->

## Planned shape

Mode: justification with numbers.

Expected structure:

1. Decision — run DeepSeek with a 20% VRAM cap in the multi-model baseline.
2. Rejected alternatives — 25%, 15%, and auto/unbounded allocation.
3. Reasoning — leave enough headroom for Kimi, runtime memory, KV cache, and stability.
4. Evidence — model load logs and memory snapshots across a few candidate caps.
5. Limit — this is a Phase 1 stability decision, not a global optimal configuration.

## Evidence needed

- Kimi memory footprint after load.
- DeepSeek memory footprint at 15%, 20%, 25%, and/or auto.
- vLLM startup args.
- GPU memory snapshots before and after each service starts.
- Any failure or instability logs for rejected caps.
