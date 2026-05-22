# T3 — Why DeepSeek runs at 20% VRAM

<!-- TODO: justification segment. Numbers from Kimi + DeepSeek weight-load
logs across a few DeepSeek VRAM-cap values. Evidence to be collected on
the next server session. -->

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
