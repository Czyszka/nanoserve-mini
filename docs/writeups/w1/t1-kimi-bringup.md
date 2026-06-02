# T1 — Bringing up Kimi-K2 on a single 8×H200 node

<!-- TODO: investigation segment. DEP/DP startup attempt, captured vLLM
startup logs (engine args, "Loading model weights", KV profiling,
traceback), redirect to TP=8.

Evidence (planned 2026-05-27 server session, see docs/plans/2026-05-27-server-session.md Cz. E):
- results/runs/2026-05-27_w1_evidence/t1_dep/dep_full.log
- results/runs/2026-05-27_w1_evidence/t1_dep/dep_engine_cmd.json
- results/runs/2026-05-27_w1_evidence/t1_dep/dep_state.txt
-->

## 2026-05-27 status

Not completed in the 2026-05-27 session. No DEP startup-failure artifact was
captured (`t1_dep/` was not produced). This remains follow-up evidence for W1 or
a later appendix.

## Planned shape

Mode: investigation.

Expected structure:

1. Symptom — DEP/DP startup attempt failed on the available single-node 8×H200 setup.
2. Hypothesis — the recommended serving strategy did not match our concrete hardware/runtime constraints.
3. Evidence — vLLM startup logs, engine args, loading phase, KV profiling, traceback.
4. Redirect — fall back to TP=8 as the Phase 1 baseline path.
5. Source — commit/run artifact with captured logs.

## Evidence needed

- DEP startup command and exact vLLM args.
- Failure logs.
- TP=8 startup logs.
- Model load and KV profiling summary.
- Final model endpoint status.
