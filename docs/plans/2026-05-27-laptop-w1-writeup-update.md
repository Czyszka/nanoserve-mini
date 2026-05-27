# 2026-05-27 Laptop Plan — W1 write-up update after server evidence

## Goal

Update `docs/writeups/w1-multi-model-serving-baseline.md` using the evidence captured during the 2026-05-27 server session.

This is a laptop-side analysis and documentation session. Do not run models. Do not start new GPU experiments. The purpose is to turn the committed server artifacts into clear W1 write-up material.

Primary threads:

- T8 — LiteLLM Proxy overhead: main usable evidence from the session.
- T3 — DeepSeek VRAM baseline: partial evidence only, with an important filename/runtime-cap caveat.
- T1 — DEP startup failure: missing evidence.
- T6 — Eagle3 ON/OFF: missing evidence.
- T5 — dashboard/Prometheus: not completed. The only attempted proxy-side capture (`litellm_metrics_post.txt`) is a 22-byte HTTP 404; T8 has no proxy-side cross-check from this dataset either.

The W1 write-up should become more complete after this session, but it should not claim that W1 is fully closed.

---

## 0. Start and repo hygiene

```bash
git status
git fetch origin
git log --oneline -8
```

If you intend to work directly on `main`:

```bash
git checkout main
git pull --ff-only origin main
```

If W1 should go through review, work on a feature branch instead and
open a PR at the end:

```bash
git checkout -b docs/w1-2026-05-27-evidence
```

The 2026-05-27 run directory is already at the correct path
(`results/runs/2026-05-27_w1_evidence`) — the earlier `w1_evidence`
typo was fixed by a prior `git mv` commit. No rename step is needed
in this session.

For this session, keep the focus on W1 analysis and documentation.

---

## 1. Read the source artifacts

Read these files before editing W1:

```text
results/runs/2026-05-27_w1_evidence/session/session_notes.md
results/runs/2026-05-27_w1_evidence/session/artifact_manifest.txt
docs/operations/agent-state.md
docs/writeups/w1-multi-model-serving-baseline.md
docs/writeups/w1/t8-litellm-overhead.md
docs/writeups/w1/t3-deepseek-vram-budget.md
docs/writeups/w1/t1-kimi-bringup.md
docs/writeups/w1/t6-eagle3-speculative-decoding.md
docs/writeups/w1/t5-observability.md
```

Note: since commit `eb21323`, `w1-multi-model-serving-baseline.md` is
the top-level **index** for W1. Per-thread content lives in
`docs/writeups/w1/t*-*.md`. Read the relevant per-thread file before
editing — that is where T8/T3/T1/T6/T5 content actually goes.

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
results/runs/2026-05-27_w1_evidence/t8_proxy_overhead/kimi_*_A_direct.json
results/runs/2026-05-27_w1_evidence/t8_proxy_overhead/kimi_*_B_proxy.json
results/runs/2026-05-27_w1_evidence/t8_proxy_overhead/ds_*_A_direct.json
results/runs/2026-05-27_w1_evidence/t8_proxy_overhead/ds_*_B_proxy.json
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
- median `output_tokens_per_second` for direct and proxy **for Kimi only** — for DeepSeek this metric is not meaningful in this dataset because `completion_tokens` median is ~2 (the "OK" output). Either skip it for DeepSeek, or report it with the `completion_tokens` column right next to it so readers see why the value is noisy.

Fields to parse:

```text
metrics.ttft_seconds
metrics.ttft_any_token_seconds
metrics.e2e_seconds
metrics.output_tokens_per_second
metrics.completion_tokens
metrics.output_chars
metrics.reasoning_chars
metrics.completed
error
```

`completion_tokens` is required to detect short-output workloads
(DeepSeek `OK` returns 2 tokens); `output_chars`/`reasoning_chars`
are needed for Kimi to show that the proxy delivers
`reasoning_chars=0` while direct delivers a real reasoning stream
(typical example: ~189 chars), even though the *final-answer*
character count is identical.

Important Kimi caveat:

Kimi direct and Kimi proxy expose reasoning chunks very differently. For Kimi, analyze both:

- final-answer TTFT: `ttft_seconds`,
- any-token TTFT: `ttft_any_token_seconds`.

Expected pattern from the 2026-05-27 dataset:

- `ttft_seconds` delta is on the order of tens of milliseconds → routing overhead.
- `ttft_any_token_seconds` delta is ~+0.40 s (~3×) → proxy collapses `delta.reasoning` chunks. This is a behavioral change in the stream, not a latency overhead, and must be reported as such.

Do not compare only one TTFT field without mentioning why.

LiteLLM-side cross-check — UNAVAILABLE for this dataset:

The captured `litellm_metrics_post.txt` is a 22-byte HTTP 404
(`{"detail":"Not Found"}`), not a Prometheus snapshot. The LiteLLM
Prometheus exporter was either not enabled (`prometheus_callback`
missing in `serving/compose/litellm-config.yaml`) or scraped at the
wrong endpoint. Do not attempt the cross-check in this laptop
session — it requires the live proxy.

For T8 this means there is no independent proxy-side confirmation
of where the ~16 ms Kimi TTFT delta or the ~5.6 % throughput
regression originates (client→proxy hop vs proxy→vLLM hop). Record
this as a missing capture and a follow-up for the next server
session: fix the LiteLLM exporter config, then re-capture against
the running proxy under the same T8 prompts.

---

## 3. Create a T8 summary artifact

Create:

```text
results/runs/2026-05-27_w1_evidence/t8_proxy_overhead/summary.md
```

Suggested structure:

```md
# T8 LiteLLM Proxy Overhead Summary

## Scope

## Method

## Controls

(list every field from `metrics.request` / `metrics.controls`:
`model`, `base_url`, `temperature`, `top_p`, `seed`, `max_tokens`,
`stream`, prompt identifier. Both A and B paths should be identical
for everything except `base_url`.)

## Results

| Model | Path | n | median TTFT | median any-token TTFT | median E2E | median completion_tokens | median output tok/s |
|---|---:|---:|---:|---:|---:|---:|---:|

## Paired deltas

| Model | Metric | median proxy-direct delta | min | max |
|---|---:|---:|---:|---:|

## Interpretation

(split into two sub-headers:)

### Network/routing overhead
### Streaming-semantics caveat (Kimi)

## Limitations
```

Required limitations:

- single prompt,
- single-stream,
- short output (DeepSeek `completion_tokens` ≈ 2 — throughput metrics for DeepSeek are not meaningful),
- no concurrency,
- no production traffic,
- no proxy-side metric confirmation (`litellm_metrics_post.txt` captured during the session is a 404 — LiteLLM Prometheus exporter not enabled / wrong endpoint; flagged as a follow-up for the next server session).

The "Streaming-semantics caveat (Kimi)" subsection is **separate**
from Limitations on purpose: it is a qualitative behavioral change,
not a generalization caveat. It should describe that the proxy
collapses `delta.reasoning` / `delta.reasoning_content` into the
final-answer stream and link to T2.

This file should be a stable artifact that W1 can reference.

---

## 4. Update W1 — T8 thread file

Edit target (per-thread, **not** the top-level index):

```text
docs/writeups/w1/t8-litellm-overhead.md
```

### Migrate the pre-evidence skeleton to a post-evidence document

The current file is a pre-evidence placeholder:

```text
# T8 — Does LiteLLM Proxy add measurable overhead
<!-- TODO: measurement segment. ... evidence (planned ...) ... -->
## Planned shape
## Question
## Measurement design
## Controls
## Expected output
```

Migrate to the post-evidence shape below. Do **not** keep the
planning placeholders alongside the new sections — they become
archeology once the file describes real results.

| Existing section | Action |
|---|---|
| HTML `<!-- TODO ... -->` block at the top | Remove. The artifact paths it lists now live in the file body. |
| `## Planned shape` | Remove. Was a planning marker, not content. |
| `## Question` | Keep. Light refresh if needed to match the actual measurement. |
| `## Measurement design` | Keep. Add concrete ports (Kimi `:8000`/`:4000`, DeepSeek `:8004`/`:4000`) and pair count (10 per model). |
| `## Controls` | Keep. Replace the prose list with the actual `metrics.controls` / `metrics.request` values from one representative JSON (`temperature`, `top_p`, `seed`, `max_tokens`, `stream=true`, model, base_url). |
| `## Expected output` | Remove. Was a placeholder for a future result; replaced by the new `## 2026-05-27 results` and `## Findings` sections below. |

Add (in this order):

```text
## 2026-05-27 results
(table from t8_proxy_overhead/summary.md — Model × Path × n ×
median TTFT × median any-token TTFT × median E2E ×
median completion_tokens × median output tok/s)

## Findings
### Network/routing overhead
### Streaming-semantics change (Kimi)

## Limitations and follow-up
(1:1 from summary.md "Required limitations", including the
proxy-side cross-check 404 caveat)
```

### Body text for the new sections

Opening paragraph (goes above the `## 2026-05-27 results` table, as
a short intro):

```md
The 2026-05-27 server session captured paired direct-vs-proxy measurements for both served models.

For Kimi-K2.6, requests were sent directly to vLLM on `:8000` and through LiteLLM Proxy on `:4000`.
For DeepSeek-V4-Flash, requests were sent directly to vLLM-small on `:8004` and through LiteLLM Proxy on `:4000`.

10 paired requests per model. Single-stream, short-prompt smoke-style overhead check, not a production concurrency benchmark.
```

Safe interpretation language for the `## Findings` subsections —
**two findings, reported separately**:

```md
### Network/routing overhead

Final-answer TTFT delta is small in this single-stream smoke workload
(median ~+16 ms for Kimi, ~+27 ms for DeepSeek). E2E delta is on the
same order (~+7 ms Kimi, ~+35 ms DeepSeek). This is consistent with
keeping LiteLLM as the multi-model routing layer for W1, but it does
not say anything about (a) behavior under concurrency, or (b) which
hop (client→proxy or proxy→vLLM) carries the ~16 ms — proxy-side
metrics were not captured in this session.

### Streaming-semantics change (Kimi)

Independently of the pure latency overhead, the proxy materially
changes Kimi's streaming behavior. Median `ttft_any_token_seconds`
rises from ~0.21 s on the direct path to ~0.61 s on the proxy path
(~3× regression, paired delta ~+0.40 s). The proxy delivers
`reasoning_chars=0` while the direct stream carries the reasoning
trace (`reasoning_chars` ≈ 189 in the sample). This is not extra
latency — it is the proxy collapsing `delta.reasoning` /
`delta.reasoning_content` into the final-answer stream.

> **Cross-reference to T2.** This finding directly limits the
> operational usefulness of T2 ([t2-reasoning-ttft.md](t2-reasoning-ttft.md)).
> The reasoning-trace TTFT parser fixed in issue #31 distinguishes
> `ttft_any_token_seconds` from final-answer `ttft_seconds` against
> the direct vLLM stream, but not against the proxy-mediated stream
> — proxy consumers see `reasoning_chars=0` and an any-token TTFT
> that collapses onto the final-answer TTFT. T2 measurement
> capability and T8 proxy behavior must be read together to avoid
> overclaiming what reasoning-aware TTFT means at the LiteLLM
> boundary.

Median Kimi `output_tokens_per_second` also drops ~5.6 % under the
proxy path in this single-stream workload.
```

Top-level index update (do this too, but **only this**):

In `docs/writeups/w1-multi-model-serving-baseline.md`, edit only
the **Thread map** table — update the "Evidence status" column:

- T8: `to be measured` → `single-stream paired baseline (2026-05-27)`
- T3: `to be collected` → `partial baseline (2026-05-27, cap020 vs 0.25 caveat)`

Do not duplicate the T8 body in the index file. The index stays as
an index.

Avoid overclaiming:

```text
LiteLLM overhead is negligible
LiteLLM is production validated
proxy has no performance impact
proxy is invisible to the client
```

Prefer:

```text
small final-answer TTFT/E2E delta in this single-stream smoke workload
streaming semantics for Kimi reasoning are changed by the proxy
requires concurrency validation later
acceptable for W1 routing experiments
```

---

## 5. Update W1 — T3 DeepSeek VRAM thread file

Edit target: `docs/writeups/w1/t3-deepseek-vram-budget.md`
(per-thread, not the top-level index).

T3 must be written as partial evidence, not as a completed sweep.

Suggested text:

```md
The 2026-05-27 session captured a DeepSeek-V4-Flash startup/runtime log and one direct TTFT smoke result. This is useful as a runtime baseline, but it does not complete the planned VRAM sweep.

Important caveat: the artifact filename says `cap020`, but the vLLM runtime log records `gpu_memory_utilization: 0.25`. Therefore this evidence is treated as a 0.25 runtime baseline until proven otherwise.
```

Facts worth including (all from `log_cap020_baseline.txt` line 8):

- vLLM `0.20.0`,
- model `deepseek-ai/DeepSeek-V4-Flash`,
- TP=8,
- FP8 KV cache,
- MTP speculative config with `num_speculative_tokens=1`,
- `max_model_len=65536`,
- `max_num_seqs=2`,
- `max_num_batched_tokens=2048` (vLLM warned this may be suboptimal with the speculative settings),
- `block_size=256`,
- `enforce_eager=True` (numbers are eager-mode, no CUDA graph capture),
- available KV cache memory: about 13.5 GiB,
- GPU KV cache size: 10,996 tokens,
- short direct TTFT request completed.

Safe conclusion:

```md
This evidence supports that DeepSeek could start and serve a short request under the recorded configuration, but it does not yet justify the final VRAM cap choice — and it does not validate the previously committed 0.20 default that the same compose file simultaneously moved to 0.25.
```

---

## 6. Update W1 — T1, T6, and T5 status

Edit targets (per-thread, not the top-level index):

```text
docs/writeups/w1/t1-kimi-bringup.md
docs/writeups/w1/t6-eagle3-speculative-decoding.md
docs/writeups/w1/t5-observability.md
```

Add short, explicit status notes in the relevant section of each
file.

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
Not completed. Prometheus and Grafana were running, but dashboard panels were not validated under live load. The single attempted proxy-side capture (`results/runs/2026-05-27_w1_evidence/t8_proxy_overhead/litellm_metrics_post.txt`) returned a 22-byte HTTP 404 (`{"detail":"Not Found"}`); the LiteLLM Prometheus exporter is not currently scraping cleanly. T8 has no proxy-side cross-check from this dataset either. Fix `prometheus_callback` in `serving/compose/litellm-config.yaml` before re-capture.
```

---

## 7. Add an evidence quality section

Add this section to the **top-level index**
(`docs/writeups/w1-multi-model-serving-baseline.md`) — it is a
cross-thread roll-up and belongs in the index, not in any single
thread file:

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

Per `CLAUDE.md` "Standard validation", this is a **docs-only** change.
Required:

```bash
git status
git diff --check
```

`ruff` and `pytest` are **not** required here because no `.py` files
are touched. Only run them if you also add a committed Python helper
under `benchmarks/scripts/` (in which case the full suite applies):

```bash
uv run ruff check .
uv run pytest -q
```

For this session, prefer **no new production script** unless the
analysis is likely to be reused. A one-off local snippet plus
committed `summary.md` is enough.

---

## 10. Commit

Recommended commits (per-thread files, index, and summary artifact):

```bash
git add docs/writeups/w1/t8-litellm-overhead.md \
        docs/writeups/w1/t3-deepseek-vram-budget.md \
        docs/writeups/w1/t1-kimi-bringup.md \
        docs/writeups/w1/t6-eagle3-speculative-decoding.md \
        docs/writeups/w1/t5-observability.md \
        docs/writeups/w1-multi-model-serving-baseline.md \
        results/runs/2026-05-27_w1_evidence/t8_proxy_overhead/summary.md

git commit -m "docs: update W1 thread files with 2026-05-27 evidence"
```

Then refresh `agent-state.md` (required by `CLAUDE.md` "Agent state
protocol" — "At the end of a meaningful task: update
`agent-state.md`"). Either fold it into the same commit, or use a
follow-up:

```bash
git add docs/operations/agent-state.md
git commit -m "docs: refresh agent-state after W1 evidence write-up"
git push -u origin HEAD
```

---

## Definition of done

The session is complete when:

- `t8_proxy_overhead/summary.md` exists and contains computed direct-vs-proxy deltas, with separate sections for routing overhead and Kimi streaming-semantics change, plus a LiteLLM-side cross-check.
- Per-thread W1 files (`docs/writeups/w1/t8-…`, `t3-…`, `t1-…`, `t6-…`, `t5-…`) carry the new evidence/status text.
- Top-level `docs/writeups/w1-multi-model-serving-baseline.md` Thread map "Evidence status" column is updated for T8 and T3, and the cross-thread "Evidence quality after 2026-05-27" section is added there.
- `docs/operations/agent-state.md` handoff log gets a new entry.
- The commit is pushed.

Non-goals for this session:

- no new server work,
- no model restarts,
- no new benchmarks,
- no claim that W1 is fully complete,
- no edits to per-thread W1 bodies in the top-level index file (the index stays an index).
