# W1 — vLLM + LiteLLM Proxy on 8×H200: a multi-model serving baseline from zero to first measurement

> Status: draft. Thread T2 written; remaining threads are placeholders.
> Methodology and the cross-write-up writing guide live in issue #37.

## Framing

The backbone of this write-up is a **bring-up**: the path from an empty
8×H200 node to a multi-model serving stack (vLLM + LiteLLM Proxy) that
returns a first benchmark number. The subject, however, is not the stack
itself. It is **trust in the first measurement** — how much work is
required before the first TTFT/E2E figure means anything at all.

The narrative is assembled from eight threads. Each thread is a single
segment in one mode:

- **śledztwo** (investigation) — symptom → hypothesis → evidence →
  redirect → source;
- **uzasadnienie** (justification) — decision ← because ← because ←
  evidence, anchored by a named rejected alternative;
- **pomiar** (measurement) — question → data → pattern, with baseline,
  controls, and an explicit statement of what the number does *not*
  show.

## Thread map

| Thread | Initial problem | Mode | Evidence status | Location |
|---|---|---|---|---|
| **T1** | How to bring up Kimi-K2 (~1T MoE) on a single 8×H200 node? DEP failed to start → TP=8 | investigation | DEP logs to be reproduced | server |
| **T2** | Why does `measure_ttft_once.py` return `TTFT: n/a`? → reasoning deltas → parser fix (#31) | investigation | **captured** (stream-debug artifacts) | laptop |
| **T3** | Why DeepSeek at 20% VRAM, not 25%/15%? | justification with numbers | to be collected | server |
| **T4** | Why LiteLLM Proxy and not the alternatives? | justification + rejected alternatives | to be written | laptop |
| **T5** | What does vLLM `/metrics` actually expose? Useful vs misleading? | investigation/measurement | partial (data in repo) | laptop + server |
| **T6** | Why Eagle3 and what does it cost? SC on vs off. | justification + measurement | to be measured | server |
| **T7** | Why runtime data in host directories, not Docker volumes? | justification | — | laptop |
| **T8** | Does LiteLLM Proxy add measurable overhead? | measurement | to be measured | server + laptop |

---

## T1 — Bringing up Kimi-K2 on a single 8×H200 node

<!-- TODO: investigation segment. DEP/DP startup attempt, captured vLLM
startup logs (engine args, "Loading model weights", KV profiling,
traceback), redirect to TP=8. Evidence to be reproduced on the next
server session. -->

---

## T2 — Why `measure_ttft_once.py` returned `TTFT: n/a`

### Symptom

The first streaming run of `measure_ttft_once.py` against Kimi-K2.6
(served as `kimi-k2.6`) reported `TTFT: n/a` and `TPOT: n/a`. The same
script against the DeepSeek-V4-Flash baseline endpoint returned ordinary
content TTFT/TPOT numbers, so the timer itself was not obviously broken
— the failure was specific to how this model streamed output.

### Hypothesis

Kimi-K2.6 is a reasoning model. The hypothesis was that it streams an
internal reasoning trace *before* any final-answer token, and that it
carries that trace in a streaming-delta field the parser did not watch.
If true, the script would see a long stream of chunks yet never observe
the field it was timing, and would correctly — but uselessly — conclude
that no token had arrived.

### Evidence

The hypothesis is cheap to settle: the streaming response is
deterministic enough to capture once and inspect offline. Raw
Server-Sent Events were captured on the server session and committed to
`results/runs/2026-05-19_kimi-k2-6_stream-debug/stream_debug/`.

The opening chunk of every stream carries a role marker with an empty
content string:

```
data: {"choices":[{"index":0,"delta":{"role":"assistant","content":""}, ...}]}
```

Every chunk that follows — for a long run — carries text in a
`reasoning` field, never in `content`:

```
data: {"choices":[{"index":0,"delta":{"reasoning":"<non-empty reasoning text>"}, ...}]}
data: {"choices":[{"index":0,"delta":{"reasoning":"<more reasoning text>"}, ...}]}
```

Two artifacts make the consequence concrete:

- `stream_short_prompt.sse.txt` — the entire completion is reasoning.
  The stream ends with `finish_reason:"length"` after 64 completion
  tokens; **not a single `delta.content` token is ever emitted.**
- `stream_exact_ok.sse.txt` — a final answer *does* arrive, but only
  after seven `delta.reasoning` chunks: one `delta.content` chunk
  (`" OK"`) appears last, with `finish_reason:"stop"`.

`stream_reasoning_prompt.sse.txt` shows the same `delta.reasoning`
ordering under a different prompt, showing that the parser issue was not
limited to one input. `models.json` confirms the served model identity.
`nonstream_short_prompt.sse.json` is intentionally not used as behavioral
evidence: that capture returned a vLLM validation error because
`stream_options` was sent with `stream:false`.

### Redirect

The parser was timing TTFT off the first `delta.content` token only.
Given the evidence, `TTFT: n/a` was the *correct* answer to the question
the parser was asking: in `stream_short_prompt.sse.txt` no content token
exists, so a content-only TTFT is genuinely undefined. The defect was
not the timer and not a missed token — it was the **definition**. A
content-only TTFT silently conflates "no answer was produced" with "the
answer started after a long, unmeasured reasoning phase".

### Source

The fix landed as issue #31 (commit `cca4022`). It was kept additive so
that existing fields kept their semantics and the schema identifier stayed
`nanoserve-mini.ttft-once.v2`. The new fields are additive leaf metrics,
and content-emitting models keep the same `ttft_seconds` behavior:

- `_client.py` gained `extract_stream_reasoning_text`, which reads
  `delta.reasoning` and the DeepSeek-style `delta.reasoning_content`.
- `measure_ttft_once.py` now records `ttft_any_token_seconds` — time to
  the first *content or reasoning* token — alongside the existing
  `ttft_seconds`, which is deliberately left as final-answer-only.
  `build_record` adds the matching `tpot_any_token_seconds`.
- A response that is all reasoning now counts as `completed` rather than
  failing silently.
- Tests for both reasoning-field variants were added in
  `test_client.py` and `test_measure_ttft_once.py`.

### Conclusion

For a reasoning model, TTFT is not a single number. "First token" forks
into a **reasoning-token TTFT** and a **final-answer-token TTFT**, and
the two can differ by the entire length of the reasoning phase — or the
final-answer figure can be undefined while the model is still producing
useful output. Every TTFT figure later in this write-up must therefore
name which of the two it measures. That naming discipline is the first
concrete down-payment on trusting the baseline.

---

## T3 — Why DeepSeek runs at 20% VRAM

<!-- TODO: justification segment. Numbers from Kimi + DeepSeek weight-load
logs across a few DeepSeek VRAM-cap values. Evidence to be collected on
the next server session. -->

---

## T4 — Why LiteLLM Proxy

<!-- TODO: justification segment. Rejected alternatives — two vLLM ports
exposed directly, nginx — each named with the reason it was dropped. -->

---

## T5 — What vLLM `/metrics` actually exposes

<!-- TODO: investigation/measurement segment. Metric-name inventory from
results/raw/observability; useful vs misleading metrics; ties into #34. -->

---

## T6 — Why Eagle3, and what it costs

<!-- TODO: justification + measurement segment. Kimi with Eagle3
speculative decoding on vs off: TTFT, TPOT, throughput. -->

---

## T7 — Why runtime data lives in host directories

<!-- TODO: justification segment. Host directories vs Docker named
volumes for observability runtime data; local-control rationale. -->

---

## T8 — Does LiteLLM Proxy add measurable overhead

<!-- TODO: measurement segment. Paired A/B difference (client → proxy:4000
→ vLLM vs client → vLLM:8000), reversed pair order, warmup; cross-check
against LiteLLM's own latency metrics. -->

---

## Baseline table and what the numbers do NOT mean

<!-- TODO: first run_bench_suite.py figures through LiteLLM (TTFT p50/p95,
TPOT, E2E, throughput) with full control snapshot; explicit limits —
single-stream, warmup=1, no concurrency sweep → sanity baseline, not a
performance claim. -->
