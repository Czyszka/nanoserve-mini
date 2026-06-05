# W1 evidence — cross-session summary

One entry point to the W1 (multi-model serving baseline) evidence collected
across server slots. Per-session detail lives in each run dir's
`session/session_notes.md`; this file tracks **which session produced usable
evidence for which thread**, so the write-up doesn't have to re-derive it.

Last updated: 2026-06-05 (laptop post-session organization).

## Evidence by thread

| Thread | Status | Authoritative source |
|---|---|---|
| T1 — Kimi DEP startup failure | ✅ done | `2026-06-05.../t1_dep/` (`dep_state.txt = exited 1`) |
| T2 — reasoning TTFT semantics | ✅ done | parser #31 + `2026-05-27.../t8_proxy_overhead/` |
| T3 — DeepSeek VRAM cap sweep | ✅ done (clean) | `2026-06-05.../t3_deepseek_vram/` (0.15 fail, 0.20/0.25 OK) |
| T4 — LiteLLM proxy role | ✅ done | `2026-06-05` paired proxy/direct + write-up |
| T5 — observability dashboard | ⚠️ partial | `2026-06-05.../t5_metrics/` + 2 screenshots; load validation owed |
| T6 — Eagle3 ON/OFF | ✅ done | `2026-06-05` run-04_eagle3-on vs run-05_eagle3-off-paired |
| T7 — host directories | ✅ done | compose + write-up |
| T8 — LiteLLM overhead / reasoning strip | ✅ done | `2026-05-27` paired set + `2026-06-05` run-01/03 |

## Session timeline

### 2026-05-27 — `results/runs/2026-05-27_w1_evidence/`
First real W1 slot. **T8 paired proxy-vs-direct** for Kimi + DeepSeek (clean,
40 JSON). **T3 partial** — single baseline with a filename/runtime-cap mismatch
(file says cap020, log says 0.25). T1/T6/T5 not attempted. Key finding: proxy
changes Kimi streaming semantics (~3× any-token TTFT), not just adds overhead.

### 2026-06-03 — `results/runs/2026-06-03_w1_evidence/`
**Failed T3 attempt** — both cap020 and cap025 runs hard-failed
(`log_cap0*_FAILED.txt`); no usable VRAM evidence. Session/start-end snapshots
captured. Superseded by 2026-06-05.

### 2026-06-05 — `results/runs/2026-06-05_w1_evidence/` + auto-id run dirs
Most productive slot. **T3 clean sweep** (0.15 hard-fail, 0.20 & 0.25 OK;
default lowered to 0.20). **T6 Eagle3 ON/OFF paired A/B** (~2× repeated p50
TTFT, ~3.8× single-shot E2E paired). **T1 DEP** `exited 1`. **T8/T4** LiteLLM
`delta.reasoning` strip proven paired. **T5** metric inventory + 2 screenshots.

⚠️ **Integrity caveat:** final commit `fc97700` re-ran and overwrote some
run-05/deepseek results in place; T6 OFF has a recovered **paired** generation
(`run-05_eagle3-off-paired`, use this) and an end-of-session **rerun**
(`run-05_eagle3-off-rerun`). Full detail:
`results/runs/2026-06-05_w1_evidence/session/session_notes.md`.

## Headline numbers (lead-with values)

- **Eagle3 (T6, paired):** ~2× repeated-p50 TTFT (837 → 1675 ms); ~2.4×
  TPOT(any); ~3.8× single-shot E2E; no first-token benefit (TTFT-any ≈ 204 ms
  both arms). Single-shot E2E ranges 2.1×–3.8× due to temp=0 non-determinism.
- **LiteLLM (T4/T8):** `main-v1.66.0-stable` strips Kimi `delta.reasoning`;
  proxy unusable as sole driver for Kimi reasoning streams. Direct vLLM clean.
- **DeepSeek VRAM (T3):** 0.15 OOM-fails engine init; 0.20 and 0.25 healthy;
  default = 0.20.
- **DEP (T1):** single-node DEP `exited 1` deterministically.
