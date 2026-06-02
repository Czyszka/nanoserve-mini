# T8 — What does putting LiteLLM Proxy in front of vLLM actually cost?

Mode: measurement. This thread defines the **thesis** and the **measurement
program** needed to settle it. The 2026-05-27 run was a pilot that validated the
rig and surfaced one real finding; it is not the experiment.

> Full measurement program (R1–R8) tracked in
> [Czyszka/nanoserve-mini#44](https://github.com/Czyszka/nanoserve-mini/issues/44).
> This file is the design source of truth.

## Thesis

A routing proxy in front of vLLM does not have *one* overhead number. Its cost
decomposes into three separable effects, and they must be measured separately or
the result is meaningless:

- **(A) Per-request processing cost** — the fixed CPU/event-loop work LiteLLM
  adds per request, independent of payload. Hypothesis: on loopback, single
  request in flight, this is **small and roughly constant** (tens of ms),
  dominated by request setup, not transfer.
- **(B) Streaming-relay behavior** — what the proxy does to the *token stream*,
  not how fast. Hypothesis: the proxy **changes streaming semantics** for
  reasoning models by collapsing `delta.reasoning` chunks into the final-answer
  stream. This is a behavioral change, not latency. *(Already observed — see
  Established finding.)*
- **(C) Scaling under concurrency** — how (A) grows as in-flight requests rise.
  Hypothesis: **this, not (A), decides production viability.** A proxy that adds
  20 ms at c=1 can serialize, queue, or saturate its single worker long before
  vLLM does at c=32/64.

The decision the thread feeds: *is LiteLLM acceptable as the W1 multi-model
routing layer?* The honest answer requires (A) bounded, (B) understood, and (C)
characterized — not a single c=1 latency delta.

## What must be measured to establish the thesis

Each requirement is a sub-experiment: what to vary, what to read, and what
result would confirm or refute the corresponding hypothesis. The first two are
the load-bearing ones.

### R1 — Hop attribution (establishes A)

The core trick: **vLLM does not know a proxy exists.** Its server-side latency
histograms (`vllm:time_to_first_token_seconds`, `vllm:e2e_request_latency_seconds`,
`vllm:request_queue_time_seconds`, `vllm:request_prefill_time_seconds`,
`vllm:request_decode_time_seconds`, `vllm:inter_token_latency_seconds`) measure
the same work whether a request arrives direct or via LiteLLM. So vLLM is a
**shared reference clock**.

- **Method:** snapshot vLLM `/metrics` before and after each *isolated* request
  (single-stream), take `Δsum/Δcount` per histogram → per-request server-side
  latency. Then `outside_vllm = client_observed − server_side` on each path, and
  the paired difference `outside_proxy − outside_direct` isolates the proxy's own
  contribution. Tooling already exists laptop-side:
  [`metrics_delta.py`](../../../benchmarks/scripts/metrics_delta.py).
- **Why it matters:** this attributes the c=1 delta to the proxy *without*
  needing LiteLLM's own exporter — vLLM's metrics suffice. It turns "the client
  saw +16 ms" into "the proxy itself cost X ms."
- **Confirms A if:** `outside_proxy − outside_direct` is small, stable, and
  independent of payload size (R3). **Refutes if:** it scales with output length
  (→ per-chunk relay cost, not fixed).

### R2 — Concurrency sweep (establishes C — the decisive test)

- **Vary:** in-flight requests `c ∈ {1, 4, 16, 64, …}`, identical workload,
  paired direct vs proxy.
- **Read:** TTFT, ITL/TPOT, E2E, and throughput **distributions** (p50/p95/p99),
  per path, per concurrency level.
- **Why it matters:** this is the question that actually decides viability. A
  proxy hop is cheap at c=1 and can become the bottleneck at c=N.
- **Confirms thesis if:** proxy tracks direct up to some concurrency, then
  diverges at a identifiable **knee** (the proxy worker saturating). **Refutes
  "acceptable" if:** the knee arrives well before vLLM's own saturation.
- **Prerequisite:** a concurrent benchmark driver — the current harness is
  single-stream only (`concurrency=1` is hardcoded). Build and test it on the
  laptop *before* a server slot.

### R3 — Workload matrix (separates fixed cost from per-chunk cost)

- **Vary:** prompt length × output length (short / medium / long), both axes.
- **Why it matters:** proxy overhead has two components that a single 6-char
  prompt + 64-token cap cannot separate — a **fixed per-request cost** (dominates
  short requests, high as a %) and a **per-chunk relay cost** (accumulates over
  long streamed outputs). One trivial workload conflates them.
- **Shows:** how overhead scales with prefill size and with chunk count.

### R4 — Per-token metric, not raw E2E

- **Read:** ITL/TPOT (`vllm:inter_token_latency_seconds` server-side; client ITL
  client-side) as the streaming-relay overhead metric.
- **Why it matters:** at `temperature=0` Kimi's reasoning-trace length still
  varies between paired requests, so raw E2E is dominated by output-length
  variance, not proxy cost. Per-token cadence is the clean signal; E2E stays as
  context only.

### R5 — Streaming vs non-streaming

- **Vary:** `stream=true` vs `stream=false`.
- **Why it matters:** in non-stream mode the proxy buffers the full response
  before returning — a different overhead profile (latency-to-full-response,
  memory) than incremental relay. Both must be characterized.

### R6 — Statistics

- `n` large enough for p95/p99; report p50/p95/p99, not just medians.
- **ABBA ordering** of the paired A/B requests (already used in the pilot) to
  cancel slow server-state drift — keep and document it.

### R7 — DeepSeek real generation workload

- **Vary:** force a non-trivial output length for DeepSeek.
- **Why it matters:** in the pilot DeepSeek returned 2 tokens (`OK`), so its
  throughput and decode-relay overhead were unmeasurable. A real generation
  workload is required before any DeepSeek throughput claim.

### R8 — Loopback is intentional scope

Client, proxy, and vLLM run on `127.0.0.1`. This is a **deliberate choice**: at
this stage we study the **server and inference overhead of the proxy**, not the
network. Loopback drives the network term to near-zero so R1's diff-of-diffs
isolates the proxy's *processing* cost. Real-network latency is explicitly out of
scope for W1 and is a separate, later question.

## Established finding (this one is real)

Independently of any latency number, the pilot established a genuine qualitative
result: **the proxy changes Kimi's streaming semantics.** On the direct path the
stream carries the reasoning trace (`reasoning_chars` ≈ 189 in the sample); on
the proxy path it does not (`reasoning_chars = 0`) — LiteLLM collapses
`delta.reasoning` / `delta.reasoning_content` into the final-answer stream. The
consequence: median `ttft_any_token_seconds` goes ~0.21 s (direct) → ~0.61 s
(proxy), a ~3× shift that is **not latency** — it is the proxy delivering the
first token only when the final answer begins.

R1 will make this airtight: if vLLM's server-side TTFT is identical on both paths
while client any-token TTFT differs 3×, the difference is proven to be
proxy-relay behavior, not added compute.

> **Cross-reference to T2.** This bounds the operational meaning of T2
> ([t2-reasoning-ttft.md](t2-reasoning-ttft.md)). The issue #31 parser
> distinguishes `ttft_any_token_seconds` from final-answer `ttft_seconds`
> against the *direct* vLLM stream — but not through the proxy, where consumers
> see `reasoning_chars=0`. T2 measurement capability and T8 proxy behavior must
> be read together.

## Pilot (2026-05-27) — what the rig confirmed

Paired direct-vs-proxy, single-stream, ABBA-ordered, 10 pairs/model, loopback.
Kimi `:8000` vs `:4000`, DeepSeek `:8004` vs `:4000`. 40/40 completed, 0 errors.
Full analysis: [`summary.md`](../../../results/runs/2026-05-27_w1_evidence/t8_proxy_overhead/summary.md).

| Model | Path | n | median TTFT (s) | median any-token TTFT (s) | median E2E (s) |
|---|---:|---:|---:|---:|---:|
| Kimi-K2.6 | direct | 10 | 0.592 | 0.209 | 0.611 |
| Kimi-K2.6 | proxy | 10 | 0.608 | 0.608 | 0.618 |
| DeepSeek-V4-Flash | direct | 10 | 0.253 | 0.253 | 0.403 |
| DeepSeek-V4-Flash | proxy | 10 | 0.279 | 0.279 | 0.437 |

What the pilot **did** establish:

- The ABBA paired-measurement harness works end-to-end against both models.
- A loopback, single-stream **reference point** for (A): final-answer TTFT delta
  ~+16 ms (Kimi) / ~+26 ms (DeepSeek) — a baseline R1 will attribute and R2 will
  stress.
- The streaming-semantics finding above (the real result).

What the pilot is **not**: it is c=1, one prompt, short output, streaming-only,
with no hop attribution. Those gaps are exactly R1–R7 — the pilot's job was to
scope the experiment, and it did.

## Controls (carried into the full program)

From a representative request (`kimi_1_A_direct.json`); identical across A and B
except `base_url`: model, temperature `0.0`, max_tokens `64`, `stream=true`,
prompt `"say OK"`, warmup `0`, measured `1`/file, concurrency `1`, script
`measure_ttft_once.py`, git_commit `5ce0881`. The full program holds all of these
fixed and changes one lever at a time (concurrency in R2, payload in R3, stream
flag in R5).
