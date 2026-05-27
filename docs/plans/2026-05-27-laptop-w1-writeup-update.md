# 2026-05-27 Laptop Plan — W1 write-up update after server evidence

## Goal

Update `docs/writeups/w1-multi-model-serving-baseline.md` using the evidence captured during the 2026-05-27 server session.

This is a laptop-side analysis and documentation session. Do not run models. Do not start new GPU experiments. The purpose is to turn the committed server artifacts into clear W1 write-up material.

Primary threads:

- T8 — LiteLLM Proxy overhead: main usable evidence from the session.
- T3 — DeepSeek VRAM baseline: partial evidence only, with an important filename/runtime-cap caveat.
- T1 — DEP startup failure: missing evidence.
- T6 — Eagle3 ON/OFF: missing evidence.
- T5 — dashboard/Prometheus: not completed beyond a LiteLLM metrics snapshot.

The W1 write-up should become more complete after this session, but it should not claim that W1 is fully closed.

---

## 0. Start and repo hygiene

```bash
git pull --ff-only origin main
git status
git log --oneline -8
```

Expected recent commits should include:

```text
docs: expand 2026-05-27 server session notes
docs: update agent state after 2026-05-27 server session
docs: add 2026-05-27 artifact manifest
docs: add 2026-05-27 server session notes
2026-05-27 server session
```

Do not mix the write-up update with the run-directory rename. The typo cleanup can be a separate commit:

```bash
git mv results/runs/2026-05-27_w1_ewidence results/runs/2026-05-27_w1_evidence
git commit -m "chore: fix 2026-05-27 evidence run path typo"
```

For this session, keep the focus on W1 analysis and documentation.

---

## 1. Read the source artifacts

Read these files before editing W1:

```text
results/runs/2026-05-27_w1_ewidence/session/session_notes.md
results/runs/2026-05-27_w1_ewidence/session/artifact_manifest.txt
docs/operations/agent-state.md
docs/writeups/w1-multi-model-serving-baseline.md
```

Purpose:

- understand what evidence exists,
- avoid overclaiming,
- reuse `session_notes.md` as the authoritative session summary,
- keep W1 aligned with `agent-state.md`.

---

## 2. Analyze T8 direct vs proxy overhead

This is the most important technical task in the session.

Input files:

```text
results/runs/2026-05-27_w1_ewidence/t8_proxy_overhead/kimi_*_A_direct.json
results/runs/2026-05-27_w1_ewidence/t8_proxy_overhead/kimi_*_B_proxy.json
results/runs/2026-05-27_w1_ewidence/t8_proxy_overhead/ds_*_A_direct.json
results/runs/2026-05-27_w1_ewidence/t8_proxy_overhead/ds_*_B_proxy.json
```

For Kimi and DeepSeek separately, compute:

- number of completed requests,
- number of errored requests,
- direct median `ttft_seconds`,
- proxy median `ttft_seconds`,
- paired median delta: `proxy - direct`,
- direct median `ttft_any_token_seconds`,
- proxy median `ttft_any_token_seconds`,
- paired median any-token delta,
- direct median `e2e_seconds`,
- proxy median `e2e_seconds`,
- paired median E2E delta,
- min/max paired deltas,
- median `output_tokens_per_second` for direct and proxy.

Fields to parse:

```text
metrics.ttft_seconds
metrics.ttft_any_token_seconds
metrics.e2e_seconds
metrics.output_tokens_per_second
metrics.completed
error
```

Important Kimi caveat:

Kimi direct and Kimi proxy may expose reasoning chunks differently. For Kimi, analyze both:

- final-answer TTFT: `ttft_seconds`,
- any-token TTFT: `ttft_any_token_seconds`.

Do not compare only one TTFT field without mentioning why.

---

## 3. Create a T8 summary artifact

Create:

```text
results/runs/2026-05-27_w1_ewidence/t8_proxy_overhead/summary.md
```

Suggested structure:

```md
# T8 LiteLLM Proxy Overhead Summary

## Scope

## Method

## Results

| Model | Path | n | median TTFT | median any-token TTFT | median E2E | median output tok/s |
|---|---:|---:|---:|---:|---:|---:|

## Paired deltas

| Model | Metric | median proxy-direct delta | min | max |
|---|---:|---:|---:|---:|

## Interpretation

## Limitations
```

Required limitations:

- single prompt,
- single-stream,
- short output,
- no concurrency,
- no production traffic,
- Kimi reasoning stream handling differs between direct and proxy.

This file should be a stable artifact that W1 can reference.

---

## 4. Update W1 — T8 section

Edit:

```text
docs/writeups/w1-multi-model-serving-baseline.md
```

Add or update the T8 section:

```md
### T8 — LiteLLM Proxy overhead

The 2026-05-27 server session captured paired direct-vs-proxy measurements for both served models.

For Kimi-K2.6, requests were sent directly to vLLM on `:8000` and through LiteLLM Proxy on `:4000`.
For DeepSeek-V4-Flash, requests were sent directly to vLLM-small on `:8004` and through LiteLLM Proxy on `:4000`.

This was a single-stream, short-prompt smoke-style overhead check, not a production concurrency benchmark.
```

Then insert the result table from `t8_proxy_overhead/summary.md`.

Safe interpretation language:

```md
The evidence suggests that LiteLLM Proxy overhead is measurable but small for this narrow workload. This is sufficient to keep LiteLLM in W1 as the multi-model routing layer, but it is not sufficient to claim production-grade overhead under concurrency.
```

Avoid overclaiming:

```text
LiteLLM overhead is negligible
LiteLLM is production validated
proxy has no performance impact
```

Prefer:

```text
small in this single-stream smoke workload
acceptable for W1 routing experiments
requires concurrency validation later
```

---

## 5. Update W1 — T3 DeepSeek VRAM section

T3 must be written as partial evidence, not as a completed sweep.

Suggested text:

```md
### T3 — DeepSeek VRAM cap baseline

The 2026-05-27 session captured a DeepSeek-V4-Flash startup/runtime log and one direct TTFT smoke result. This is useful as a runtime baseline, but it does not complete the planned VRAM sweep.

Important caveat: the artifact filename says `cap020`, but the vLLM runtime log records `gpu_memory_utilization: 0.25`. Therefore this evidence is treated as a 0.25 runtime baseline until proven otherwise.
```

Facts worth including:

- vLLM `0.20.0`,
- model `deepseek-ai/DeepSeek-V4-Flash`,
- TP=8,
- FP8 KV cache,
- MTP speculative config with `num_speculative_tokens=1`,
- available KV cache memory: about 13.5 GiB,
- GPU KV cache size: 10,996 tokens,
- short direct TTFT request completed.

Safe conclusion:

```md
This evidence supports that DeepSeek could start and serve a short request under the recorded configuration, but it does not yet justify the final VRAM cap choice.
```

---

## 6. Update W1 — T1, T6, and T5 status

Add short, explicit status notes.

### T1 — DEP startup failure capture

```md
Not completed in the 2026-05-27 session. No DEP failure artifact was captured. This remains follow-up evidence for W1 or a later appendix.
```

### T6 — Eagle3 ON/OFF

```md
Not completed in the 2026-05-27 session. Kimi remained configured with Eagle3, but no controlled ON/OFF comparison was captured.
```

### T5 — Dashboard / Prometheus validation

```md
Not completed beyond a LiteLLM metrics snapshot. Prometheus and Grafana were running, but the dashboard was not validated under live load during this session.
```

---

## 7. Add an evidence quality section

Add a section like this to W1:

```md
## Evidence quality after 2026-05-27

| Thread | Evidence quality | Status |
|---|---|---|
| T8 Proxy overhead | Good for single-stream smoke overhead; not concurrency evidence | Usable |
| T3 DeepSeek VRAM | Partial; filename/runtime cap mismatch | Needs rerun |
| T1 DEP | Missing | Needs capture |
| T6 Eagle3 | Missing | Needs controlled experiment |
| T5 Dashboard | Partial infra only | Needs validation |
```

Add a short explanation:

```md
The write-up intentionally distinguishes completed evidence from partial or missing evidence. This avoids overclaiming and keeps W1 useful as an engineering record, not just a success narrative.
```

---

## 8. Update W1 follow-up work

Add or update follow-up list:

```md
## Follow-up work

1. Re-run DeepSeek VRAM sweep with explicit `0.15`, `0.20`, and `0.25` caps and filenames matching runtime configuration.
2. Capture Kimi DEP startup failure evidence.
3. Run controlled Kimi Eagle3 ON/OFF benchmark.
4. Validate Grafana dashboard panels under live load.
5. Run proxy overhead under concurrency after the single-stream baseline.
```

---

## 9. Local validation

After editing:

```bash
git diff --check
```

Optional, if no Python code changed:

```bash
uv run ruff check .
```

Do not run the full test suite unless you commit analysis code.

If you add a reusable Python analysis helper under `benchmarks/scripts/`, then run:

```bash
uv run pytest -q
```

For this session, prefer **no new production script** unless the analysis is likely to be reused. A one-off local snippet plus committed `summary.md` is enough.

---

## 10. Commit

Recommended commit:

```bash
git add docs/writeups/w1-multi-model-serving-baseline.md \
        results/runs/2026-05-27_w1_ewidence/t8_proxy_overhead/summary.md

git commit -m "docs: update W1 write-up with 2026-05-27 evidence"
git push
```

If you also rename the directory, do it separately:

```bash
git mv results/runs/2026-05-27_w1_ewidence results/runs/2026-05-27_w1_evidence
git commit -m "chore: fix 2026-05-27 evidence run path typo"
git push
```

Do not combine the rename with the W1 write-up update.

---

## Definition of done

The session is complete when:

- `t8_proxy_overhead/summary.md` exists and contains computed direct-vs-proxy deltas.
- W1 write-up includes T8 results and interpretation.
- W1 write-up describes T3 as partial evidence with the `cap020` vs `0.25` caveat.
- W1 write-up explicitly marks T1, T6, and T5 as incomplete/deferred.
- W1 write-up includes an evidence quality table.
- The commit is pushed to GitHub.

Non-goals for this session:

- no new server work,
- no model restarts,
- no new benchmarks,
- no claim that W1 is fully complete.
