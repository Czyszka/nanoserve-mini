# T6 — Why Eagle3, and what it costs

<!-- TODO: justification + measurement segment. Kimi with Eagle3
speculative decoding on vs off: TTFT, TPOT, throughput. -->

## Planned shape

Mode: justification + measurement.

Expected structure:

1. Decision — evaluate Eagle3 speculative decoding for Kimi in a controlled A/B.
2. Hypothesis — draft-model speculation can improve generation throughput or TPOT when acceptance is high enough.
3. Cost model — extra memory, extra compute, more configuration complexity, and possible lower benefit on some prompts.
4. Measurement — compare speculative decoding on vs off under the same prompt set and server controls.
5. Conclusion — keep only if measured benefit justifies the operational cost.

## Metrics

- client TTFT / TTFT any token,
- TPOT / ITL,
- E2E latency,
- prompt and generation tokens/s,
- GPU utilization / VRAM / power,
- request outcomes and errors.

## Non-goals

Do not mix T6 with the W1 baseline until the baseline is stable and measured without speculative decoding.
