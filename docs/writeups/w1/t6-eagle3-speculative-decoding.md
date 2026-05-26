# T6 — Why Eagle3, and what it costs

<!-- TODO: justification + measurement segment. Kimi with Eagle3
speculative decoding on vs off: TTFT, TPOT, throughput.

Evidence (planned 2026-05-27 server session, see docs/plans/2026-05-27-server-session.md Cz. C+F):
- results/runs/2026-05-27_w1_evidence/t6_eagle3/bench_on.log
- results/runs/2026-05-27_w1_evidence/t6_eagle3/bench_off.log
- results/runs/2026-05-27_w1_evidence/t6_eagle3/kimi_log_eagle3_{on,off}.txt
- results/runs/2026-05-27_kimi-k2.6_eagle3-on/ (auto-id, run_bench_suite)
- results/runs/2026-05-27_kimi-k2.6_eagle3-off/ (auto-id, run_bench_suite)
-->

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
