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

### Mechanism: where reasoning sits in the inference path

The key point is that a reasoning phase is not a phase *before*
inference. It happens *inside* inference.

For an autoregressive LLM, serving has two broad phases:

```text
request
  -> prefill / context phase
  -> decode / generation phase
       -> token
       -> token
       -> token
       -> ...
```

During **prefill**, the model processes the prompt and builds the
request state, including the KV cache. During **decode**, the model
generates new tokens autoregressively: each new token is predicted from
the prompt plus all previously generated tokens. From the serving
engine's perspective, a reasoning token and a final-answer token are both
ordinary generated tokens in this decode loop. They both consume GPU
work, output-token budget, scheduler time, and KV-cache growth.

The difference appears one layer above the raw model execution: in the
model-output format and in the OpenAI-compatible API response.

A useful way to view the stack is:

```text
GPU kernels / model forward pass
  -> raw generated token stream
  -> model-specific reasoning parser
  -> OpenAI-compatible response fields
       -> delta.reasoning
       -> delta.reasoning_content
       -> delta.content
  -> benchmark parser / latency metrics
```

The diagram deliberately separates two parser layers.

The **server-side reasoning parser** sits inside the serving stack,
between the raw generated token stream and the OpenAI-compatible response
fields. It does not make the model "reason" and it does not change the
GPU computation. Its job is to interpret the model-specific output
format and split the generated stream into semantic channels such as
`delta.reasoning` and `delta.content`.

The **benchmark/client parser** sits outside the serving engine. It reads
Server-Sent Events, extracts fields from each streamed delta, and decides
which observed event starts a latency timer. The failure investigated in
this thread was in this second layer: vLLM exposed reasoning deltas, but
our benchmark parser treated `delta.content` as the only token channel
worth timing.

For many reasoning models, the model emits an internal scratchpad before
the final answer. In some model families this is delimited by explicit
markers such as:

```text
<think>
... internal reasoning text ...
</think>
final answer text
```

A reasoning parser can then classify the generated text like this:

```text
inside reasoning markers      -> reasoning channel
after reasoning markers       -> final content channel
```

In an OpenAI-compatible streaming response, that split becomes visible as
different delta fields:

```text
delta.reasoning         -> reasoning trace token/text
delta.reasoning_content -> alternative reasoning field used by some APIs/models
delta.content           -> final assistant answer token/text
```

This is why "first token" is ambiguous for a reasoning model. There are
at least two different client-observable events:

```text
first reasoning token      -> the model has started producing reasoning output
first final content token  -> the user-visible final answer has started
```

For a non-reasoning or content-only model, these events often collapse
into the same moment because the first generated token is also
`delta.content`. For a reasoning model, they can diverge by the full
length of the reasoning trace.

That distinction matters for metrics:

| Metric | Starts when | Meaning |
|---|---|---|
| `ttft_any_token_seconds` | first non-empty reasoning or content delta | the model has started producing observable output |
| `ttft_reasoning_seconds` | first non-empty reasoning delta, if tracked separately | the reasoning trace has started |
| `ttft_seconds` / content TTFT | first non-empty `delta.content` | the final answer has started |
| `tpot_any_token_seconds` | consecutive reasoning or content deltas | cadence of all observed generation |
| content-only TPOT | consecutive content deltas only | cadence of the final answer channel |

Strictly speaking, the benchmark does not observe raw model tokens
directly. It observes streamed text deltas after tokenization, decoding,
server-side parsing, and SSE serialization. In this write-up, "token
TTFT" therefore means the first non-empty client-observable generation
delta, not a timestamp taken inside the model executor.

This means that `TTFT: n/a` can be correct under a content-only
definition even when the model is actively generating tokens. If the
completion budget is spent entirely on reasoning and the stream ends with
`finish_reason:"length"`, then no final-answer token exists. In that
case, content TTFT is not slow; it is undefined.

The practical lesson is that a latency script must state which semantic
channel it is timing. A content-only TTFT answers:

```text
When did the final answer start?
```

It does not answer:

```text
When did model generation start?
```

For reasoning models, those are different measurement questions.

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
evidence. That capture failed before normal model execution: the request
sent `stream_options` while also setting `stream:false`.

This is a protocol-level client bug, not an inference result.
`stream_options` describes streaming-specific behavior, for example
extra metadata chunks in a Server-Sent Events stream. With
`stream:false`, there is no SSE stream to configure, so vLLM correctly
rejects the request during OpenAI-compatible request validation. The
artifact is still useful, but only as evidence that the non-streaming
capture path must omit `stream_options`.

### Eliminated explanations

The important part of the investigation was not only finding a matching
field. It was narrowing the failure to a specific layer of the stack.

| Candidate explanation | Evidence | Result |
|---|---|---|
| The timing code was generally broken | The same script returned ordinary TTFT/TPOT values against the DeepSeek-V4-Flash baseline endpoint | rejected |
| Kimi produced no streamed output | The SSE capture contains many non-empty `delta.reasoning` chunks | rejected |
| vLLM failed during the streaming inference path | The streaming captures reached normal terminal states such as `finish_reason:"length"` or `finish_reason:"stop"` | rejected for the streaming path |
| The non-streaming capture proved model behavior | That request was invalid at validation time because it sent `stream_options` with `stream:false` | rejected as behavioral evidence |
| The client-side metric definition was too narrow | The benchmark watched `delta.content`, while this model first emitted `delta.reasoning` | accepted |

### Redirect

The parser was timing TTFT off the first `delta.content` token only.
Given the evidence, `TTFT: n/a` was the *correct* answer to the question
the parser was asking: in `stream_short_prompt.sse.txt` no content token
exists, so a content-only TTFT is genuinely undefined. The defect was
not the timer and not a missed token — it was the **definition**. A
content-only TTFT silently conflates "no answer was produced" with "the
answer started after a long, unmeasured reasoning phase".

This is the layer boundary that mattered: the server-side reasoning
parser exposed the model's scratchpad as `delta.reasoning`; the
benchmark/client parser then ignored that channel and treated
`delta.content` as the only signal of generation. The stream was healthy
for the question "is the model producing output?" and empty only for the
narrower question "has the final-answer channel started?".

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

For a reasoning model, TTFT is not a single number. From the inference
engine perspective, reasoning tokens and final-answer tokens are both
generated by the same autoregressive decode loop. From the API and
benchmark perspective, however, they are different observable channels.
"First token" therefore forks into a **first reasoning token** and a
**first final-answer token**. The two can differ by the entire length of
the reasoning phase, or the final-answer figure can be undefined while
the model is still producing useful reasoning output. Every TTFT figure
later in this write-up must therefore name which channel it measures.
That naming discipline is the first concrete down-payment on trusting
the baseline.

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
