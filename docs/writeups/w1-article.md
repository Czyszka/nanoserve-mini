# W1 — Five numbers that lied: getting to a trustworthy first measurement on 8×H200

> **Setup:** 8×H200 NVL 143 GB/GPU · vLLM v0.20.0 · CUDA 13.2 · driver 595.58.03
> **Models:** Kimi-K2.6 (~1T MoE, Eagle3) + DeepSeek-V4-Flash (FP8 MLA, MTP), co-resident
> **Stack:** vLLM ×2 + LiteLLM Proxy · Prometheus + Grafana
> **Evidence:** `results/runs/2026-06-05_w1_evidence/` (commit `d0bb634`) · `results/runs/2026-06-10_w1_article_evidence/` (GPU counters + hop attribution)
>
> Per-investigation thread files with full evidence tables: [`docs/writeups/w1/`](w1/)

## The thesis: a first number is a claim about its preconditions

Benchmarking a served LLM looks like three steps: start the engine, send a
request, read the latency. In practice the first number you get back is usually
wrong — and not because the timer is broken. It is wrong because **every
measurement silently assumes a set of preconditions, and the number lies
whenever one of them does not hold.** The engineering is not in reading the
clock. It is in knowing *which* precondition a given number depends on, and
*how* to check it before you trust the figure.

This write-up is five investigations on one 8×H200 node, and they share a
single shape. Each begins with a number that looked final — `crash`, `n/a`,
`completed: false`, `3.8×`, `100%` — and each turned out to be reporting an
effect while hiding its cause. The recurring move is the same every time:

> **observe the number → distrust it → separate symptom from cause → prove the
> mechanism from logs or source → scope exactly what can now be claimed.**

That last step is load-bearing, so it has an explicit grammar. I borrow a small
evidence ladder from the observability work (Investigation 5) and apply it to
every claim in the document:

| Level | Name | Meaning |
|---|---|---|
| **L0** | Observation | Read directly from a captured artifact. |
| **L1** | Diagnostic hypothesis | Best mechanistic reading of correlated signals — not yet tested. |
| **L2** | Supported causal claim | Survived a controlled, one-lever counterfactual. |
| **L3** | Robust claim | Repeated across workloads, windows, or configurations. |

W1 is deliberately an **L0–L1 project**: short GPU slots, single-stream
workloads, and very few controlled counterfactuals. Knowing that — and saying
so where a number stops being provable — is part of the craft, not a disclaimer
bolted on at the end. Each investigation therefore closes with a **claim
ledger**: what the evidence supports, at what level, and what would promote it.

The serving layers a request passes through give the map for *where* a
precondition can hide — client/proxy → scheduler → prefill → decode → KV cache →
hardware — following the serving taxonomy of Miao et al. [1]. The stack that
realizes them is two co-resident vLLM instances behind one LiteLLM Proxy
(`serving/compose/docker-compose.kimi-k2.6.yml`):

```
:8000  vllm        Kimi-K2.6        TP=8, gpu-mem-util 0.60, Eagle3 ON
:8004  vllm-small  DeepSeek-V4-Flash TP=8, gpu-mem-util 0.20, FP8 MLA + MTP, --enforce-eager
:4000  litellm     routes {model:"kimi-k2.6"}→:8000, {model:"DeepSeek-V4-Flash"}→:8004
:9090  prometheus      :3001  grafana
```

The proxy's job is intentionally narrow: one OpenAI-compatible surface so the
benchmark client switches models by changing the `model` field, not the base
URL — no content-aware routing, no per-user keys (the routing decision is
[T4](w1/t4-litellm-proxy.md); whether the hop is *transparent* is Investigation
3). And because one finite board (143,771 MiB = **140.40 GiB/GPU**) is shared by
two models, every `--gpu-memory-utilization` value is really a decision about
how to partition that board. That partition is where the first number lied.

## Investigation 1 — The engine that crashed after the weights fit

**The number.** The first Kimi-K2.6 bring-up used data + expert parallelism
(DEP: `--data-parallel-size 8 --enable-expert-parallel`) at
`gpu-memory-utilization 0.6`. All eight engine-core processes died identically
during startup with:

```
ValueError: No available memory for the cache blocks. Try increasing
`gpu_memory_utilization` when initializing the engine.
```

**The trap.** The error message *tells you the fix*: raise
`gpu_memory_utilization`. Most of the time you would take the hint, bump the cap,
and move on. That treats the symptom. The symptom here was an effect of
something the message does not name.

**The tell.** The crash came **after the weights had loaded successfully** —
`Model loading took 88.44 GiB memory`, ~2 minutes before the failure. If the
weights fit, why does the engine refuse to start? Because
`gpu-memory-utilization` is **not a load-time allocation cap.** vLLM does not ask
"do the weights fit on the card?" It asks a different question, later: "after
loading weights and profiling activations, is anything left *inside my
self-imposed ceiling* for the KV cache?"

**The mechanism (cause → effect).** The per-GPU arithmetic, read straight from
`dep_full.log`:

```
budget   = 0.6 × 140.40 GiB                       =  84.24 GiB
− weights (DEP)                                   =  88.44 GiB   gpu_model_runner.py:4879
− CUDA-graph (measured)                           =   0.13 GiB   gpu_model_runner.py:6042
− activation peak (8192-tok prefill) + non-torch  ≈  14.75 GiB
────────────────────────────────────────────────────────────────
= Available KV cache memory                       = −19.08 GiB   gpu_worker.py:440
```

The causal chain: `cap is a post-load ceiling` → `the loader allocates against
the GPU's actual free memory (~111 GiB), so the 88.44 GiB load completes` → `KV
sizing then computes budget − measured-non-KV` → `Kimi's own non-KV footprint
(103.32 GiB) already exceeds its 84.24 GiB ceiling` → `KV budget goes negative` →
`engine refuses`. The weights fit the *card*; they do not fit the *budget*.
Raising the cap would size a positive KV pool without changing anything
physical — which is exactly why the error message's advice is about the symptom.

*Why DEP specifically?* The parallelism shape decides what each GPU must hold.
The checkpoint is **554.30 GiB** (experts quantized to 4-bit Marlin WNA16),
decomposing per GPU as:

| Weight class | Whole model | DEP /GPU | TP=8 /GPU |
|---|---:|---:|---:|
| 384 routed experts (4-bit, EP-sharded 1/8) | ~532 GiB | 66.6 | 66.6 |
| non-experts: MLA attn, norms, router, embeddings (**replicated under DEP**) | ~22 GiB | 21.9 | 2.7 |
| **total** | 554.30 | **88.44** | **69.3** |

TP shards *every* tensor; DEP replicates the dense backbone on all eight GPUs
while only the experts are EP-sharded. The DEP penalty is the replicated dense
path: `(7/8) × 21.9 ≈ 19.1 GiB/GPU` carried on every GPU that TP would not. That
~19 GiB is what flips the KV budget negative. (It is tempting to equate the
~19.1 GiB replication penalty with the −19.08 GiB deficit — but they are **two
separately computed quantities whose near-equality is a coincidence, not an
identity**: the deficit also folds in activations and the 0.13 GiB graph term.)

**The decision — against the obvious one.** The message says raise the cap; I
switched parallelism instead. The arithmetic shows why the obvious move is a
dead end *here*: to give DEP the KV pool that TP gets at 0.6, the cap would need
`util ≈ 0.6 + 19.1/140.40 ≈ 0.74`. At 0.74 Kimi alone claims ~104 GiB; with the
co-resident DeepSeek at its own 0.2 (~28 GiB), the two reserve ~0.94 of the
140.40 GiB card, leaving ~6% (~8 GiB) for the out-of-budget CUDA/NCCL/NIXL
buffers both engines need — so co-resident DEP at TP-equivalent KV is not merely
wasteful, it is **infeasible**. TP=8 at 0.6, by contrast, leaves ~27 GiB of card
headroom. And DEP's *only* payoff — eight replicas serving eight independent
streams — is worth exactly zero on W1's single-stream baseline. So TP=8, full
stop.

**The same cause, a second time.** The identical failure family reappeared when
choosing DeepSeek's cap. Sweeping it with Kimi co-resident:

| Cap | Available KV | Outcome |
|---|---|---|
| 0.15 | **−0.49 GiB** | `EngineCore failed to start` |
| 0.20 | +6.5 GiB | healthy |
| 0.25 | +13.49 GiB | healthy |

DeepSeek's weights are a constant 20.32 GiB/GPU; the cap only sizes the leftover
KV pool, and at 0.15 that leftover is negative — same arithmetic, same wall.

*And a number that itself lied.* The 0.20 startup prints two KV figures that do
not reconcile: `GPU KV cache size: 5,284 tokens` next to `Maximum concurrency …
6.51x`. Naively, 5,284 ÷ 65,536 = 0.08, not 6.51×. Rather than pick one, I read
vLLM's source: the two figures come from different functions in
`kv_cache_utils.py`. The size line (`_report_kv_cache_config`) is
`num_blocks / number_of_KV_cache_groups × min_block_size` — a per-group display
figure; the concurrency line (`get_max_concurrency_for_kv_cache_config`) is
`num_blocks ÷ blocks_per_max_len_request` — the trustworthy capacity. DeepSeek-V4
carries **more than one KV-cache group** (the `fp8_ds_mla` MLA latent cache plus
a separate FP8 cache for the Lightning Indexer sparse attention), so the
size-line normalization deflates it by a factor that is **identical (80.7×) at
both caps** — systematic, not noise. Real capacity at 0.20 is ~427k tokens
(~6.5 full 64k contexts), not 5,284. This is a known, still-open upstream bug,
[vllm-project/vllm#40691](https://github.com/vllm-project/vllm/issues/40691).
The lesson: a log line is an artifact to be verified, not an oracle.

The cap choice itself is then a partition decision: 0.20 leaves ~26.6 GiB/GPU
free as a stability margin for the latency-critical Kimi co-tenant, where 0.25
would spend ~7 GiB of that headroom to buy concurrency a single-stream baseline
never uses. **0.20** as the Phase 1 default, 0.25 documented for when a real
concurrent DeepSeek workload makes KV the binding resource.

**Claim ledger.**
- **L0:** the −19.08 / −0.49 GiB budgets, the 88.44/20.32 GiB footprints, the
  KV-display discrepancy — all read directly from logs and source.
- **L0:** TP=8 fixes it — observed, it is the config serving every other thread.
- **L1:** that DEP-at-0.74 is *infeasible* under co-residency is calculated, not
  tested (we did not run it). The replication-penalty decomposition assumes
  loaded ≈ on-disk size.
- **Not shown:** any DP-vs-TP *throughput* comparison — DEP never started, so
  whether it would win under real concurrency is a separate, open question.

Full evidence: [T1](w1/t1-kimi-bringup.md), [T3](w1/t3-deepseek-vram-budget.md).

## Investigation 2 — The benchmark that returned `n/a` and was right

**The number.** `measure_ttft_once.py` against Kimi-K2.6 reported `TTFT: n/a`
and `TPOT: n/a`.

**The trap.** A null metric reads as a broken probe — "the timer is broken" or
"the model produced nothing." Either reading sends you debugging the wrong
thing.

**The tell.** The *same script* returned ordinary TTFT/TPOT against
DeepSeek-V4-Flash, so the timer was not generally broken. And the Kimi stream was
full of non-empty chunks — but every one carried `delta.reasoning`, never
`delta.content`. In the captured `stream_short_prompt.sse.txt` the entire
completion was reasoning, ending with `finish_reason: "length"` at 64 tokens.
The content channel never opened.

**Elimination.** Stated as a differential diagnosis, which is what the captures
support:

| Candidate cause | Evidence | Verdict |
|---|---|---|
| Timing code broken | DeepSeek returns normal numbers, same script | rejected |
| Model produced no output | SSE has many non-empty `delta.reasoning` chunks | rejected |
| Streaming path crashed | streams reach `finish_reason: length`/`stop` | rejected |
| The non-stream capture proves it | that request was invalid (`stream_options` + `stream:false`) | rejected as evidence |
| Client metric definition too narrow | parser timed `delta.content` only; model emits `delta.reasoning` first | **accepted** |

**The mechanism (cause → effect).** There are two parser layers, and the bug
lives in the second. `model is a reasoner` → `vLLM's server-side reasoning
parser splits the stream into delta.reasoning / delta.content channels` →
`reasoning streams first, content arrives later or never within the cap` → `the
client benchmark parser was timing the content channel only` → `it correctly
reports n/a for a content-TTFT that genuinely does not exist`. `n/a` was the
right answer to the wrong question. The defect was the *definition*, not the
clock.

So for a reasoning model, "TTFT" is not one number — it is a **(measurement
point, channel) pair**. The fix (#31, commit `cca4022`, additive) added
`ttft_any_token_seconds` (first reasoning *or* content delta) beside the
content-only `ttft_seconds`, and made an all-reasoning response count as
`completed`. The two clocks, on the same stream, diverge:

| Model (direct, n=10) | content TTFT | any-token TTFT | gap |
|---|---:|---:|---:|
| Kimi-K2.6 | 0.592 s | 0.209 s | **2.8×** |
| DeepSeek-V4-Flash | 0.253 s | 0.253 s | 1.0× |

This is also why a client TTFT and vLLM's server-side
`vllm:time_to_first_token_seconds` legitimately disagree for the *same* request,
through four distinct causes — worth separating so the gap is never blamed on
the wrong layer:

1. **Path scope** — the client clock spans transport, proxy, queueing, prefill,
   SSE, and its own parse loop; vLLM's starts inside the engine. Client ≥ server
   by construction.
2. **Channel** — the T2 finding. vLLM counts the first *generated* token
   regardless of label, so its number tracks the *any-token* view (~0.2 s), not
   the content view (~0.59 s).
3. **Component attribution** — what the client sees as one number, vLLM splits
   into queue / prefill / decode / inter-token histograms.
4. **Aggregation** — one wall-clock value per request vs a histogram over a
   scrape window.

Factors 1 and 2 stopped being argument and became measurement on 2026-06-10:
snapshotting vLLM's latency histograms around isolated requests (Δsum/Δcount)
put the server-side TTFT at **p50 93 ms**, while the same requests' client
clocks read 177 ms (any-token) and 1.82 s (content). The engine's number does
track the any-token view — factor 2, confirmed — and the residual ~84 ms
client−server gap is factor 1's path scope, measured on loopback. For a
reasoning model, factor 2 dominates the rest. Every TTFT in W1 therefore
names both its measurement point and its channel — or it means nothing.

**Claim ledger.**
- **L0 → robust:** the channel split is reproduced independently in the
  Investigation-4 captures (any-token ≈ 204 ms while content swings with
  reasoning length) — directly observed, multiple runs.
- **L0 (closed 2026-06-10):** the paired client-vs-server isolation — server
  TTFT p50 93 ms vs client 177 ms any-token / 1.82 s content, n=5 isolated
  requests, direct path
  (`results/runs/2026-06-10_w1_article_evidence/p2_hop_attribution/`). The
  remaining R2–R8 program stays in
  [#44](https://github.com/Czyszka/nanoserve-mini/issues/44).
- **Scope:** specific to this Kimi-K2.6/vLLM build; not a universal claim about
  reasoning models.

Full evidence: [T2](w1/t2-reasoning-ttft.md).

## Investigation 3 — The proxy that returned nothing while generating everything

**The number.** The same prompt at `max_tokens=64`, through the LiteLLM Proxy:
`completed: false`, 3 chunks, `reasoning_chars = 0`, any-token TTFT `null`.

**The trap.** A proxy in front of an engine is "the thing that adds latency," so
the instinct is to measure its overhead in milliseconds. That frames it as a
*speed* problem. It is not.

**The tell.** The direct path, identical request, returned 26 chunks, 242
reasoning characters, any-token TTFT 0.214 s, `completed: true`:

| Path | chunks | reasoning_chars | any-token TTFT | completed |
|---|---:|---:|---:|---|
| direct `:8000` | 26 | 242 | 0.214 s | **true** |
| proxy `:4000` | 3 | 0 | null | **false** |

Both paths **generated the same 64 tokens** server-side, and on both the final
answer never started (`output_chars = 0` — the whole budget went to reasoning, a
Kimi + short-`max_tokens` property, not a proxy effect). Same generation,
opposite client outcome. That pins the difference on delivery, not compute.

**The mechanism (cause → effect).** `LiteLLM main-v1.66.0-stable does not forward
delta.reasoning` → `it collapses the reasoning channel into the final-answer
stream` → `under a finite max_tokens spent entirely on reasoning, the proxy
client receives content-less chunks` → `no any-token TTFT, completed: false — the
client gets effectively nothing`. The cost is not the ~17 ms the c=1 pilot
measured; it is a **usability hazard for reasoning models**: through this proxy
version a reasoning-heavy request can return an empty-looking response. A latency
mindset would have measured the 17 ms, declared the hop cheap, and shipped the
broken path.

**The attribution, measured.** The check this investigation deferred was run on
2026-06-10, using the one clock the proxy cannot touch: vLLM's own latency
histograms, snapshotted before and after each isolated request (Δsum/Δcount;
5 pairs per variant, ABBA-ordered, exactly one request per delta verified on
every pair). At `max_tokens=64`:

| Path (n=5, medians) | server TTFT | server E2E | tokens | client outcome |
|---|---:|---:|---:|---|
| direct `:8000` | 93 ms | 0.576 s | 64 | `completed: true` — 23–24 chunks, ~245 reasoning chars |
| proxy `:4000` | 96 ms | 0.606 s | 64 | `completed: false` — 3 chunks, 0 reasoning chars, **5/5** |

The engine, which cannot see the proxy, did the same work on both paths —
first token within ~3 ms, the same 64 tokens — and the proxy client still
received nothing, in every pair. That closes the loop: the strip is pure
delivery, with the engine as a shared reference clock.

The hop's own price falls out of the same data. `client E2E − server E2E`
isolates everything outside vLLM on each path, and the paired difference puts
the proxy's per-request processing cost at **~37 ms median** — consistent
across both caps (36.8 ms at `max_tokens=64`, 36.5 ms at 1024; per-pair spread
−7…+81 ms). LiteLLM's own `x-litellm-overhead-duration-ms` header self-reports
24.4 ms on a non-streaming request — same order; ours additionally carries the
extra HTTP hop. And where the answer *does* arrive through the proxy
(`max_tokens=1024`), the collapse gets a price tag: the proxy client's first
token lands **~1.7 s after** direct's (paired median) — not because the proxy
is slow, but because it withholds everything until the reasoning trace ends.
That delay scales with reasoning length, which is exactly why it is a semantics
problem and not a latency line-item.

**The decision — against the production default.** The obvious baseline is the
production path (through the proxy, as clients hit it). I measure the baseline
**direct** instead, because the proxy is not *transparent* for reasoning streams
in this version. The proxy stays — it is the right minimal multi-model boundary
for routing — but it cannot be the measurement reference for Kimi. (This is also
the honest boundary on LiteLLM's own published "8 ms P95": that figure is
synthetic — a fake endpoint on a 4 CPU / 8 GB box — and version-dependent, since
aiohttp became the default transport only in v1.72.0, after our pinned image.
Overhead is an empirical question for *our* path, not a vendor number.)

**Claim ledger.**
- **L2 (promoted 2026-06-10):** the strip is delivery, not compute — same
  prompt, same cap, the path as the single lever; server-side work identical
  while the client outcome inverts, 5/5 pairs.
- **L0:** the hop's c=1 processing cost — ~37 ms median paired outside-vLLM
  delta on loopback, stable across `max_tokens` 64/1024; LiteLLM's own header
  reports 24.4 ms. (The earlier pilot's ~17/~26 ms were raw client deltas,
  unattributed.)
- **Deferred:** the concurrency sweep (R2) and workload matrix (R3) in
  [#44](https://github.com/Czyszka/nanoserve-mini/issues/44) — the curve, not
  the point, decides production viability. Note R3's fixed-vs-per-chunk cost
  split cannot be measured through this proxy version at all: it strips the
  stream down to 3–5 chunks regardless of output length.

Full evidence: [T8](w1/t8-litellm-overhead.md), [T4](w1/t4-litellm-proxy.md).

## Investigation 4 — The 3.8× speedup that was partly a lie

**The number.** Eagle3 speculative decoding ON vs OFF for Kimi-K2.6, single shot:
E2E **3.8× faster**, content TTFT 3.8×.

**The trap.** 3.8× is the headline you *want* to report. It is also the one a
careful reader will not believe, and they would be right.

**The tell.** At temperature 0 the two arms generated **different amounts of
output** — OFF produced 142 completion tokens to ON's 69, with a longer reasoning
trace (546 vs 240 chars). A longer generation inflates E2E independently of
decode speed. The "speedup" is partly just OFF having more work to do.

**The mechanism of the confound (cause → effect).** `temperature 0 is not enough
for determinism` → `floating-point reduction order under TP=8 varies run to run`
→ `generations are not token-identical (completion ranged 94–190 ON, 97–285
OFF)` → `single-shot E2E is dominated by length variance, not decode rate`. The
fix is to remove length as a variable: a repeated run where the **median
completion length is identical (97 tokens in both arms)**.

| Metric (repeated, p50) | Eagle3 ON | Eagle3 OFF | ratio |
|---|---:|---:|---:|
| TTFT p50 | **837 ms** | **1675 ms** | **2.0×** |
| TTFT p95 | 1694 ms | 4426 ms | 2.6× |
| E2E p50 | 857 ms | 1724 ms | 2.0× |
| output tok/s | 111.6 | 58.7 | **1.9×** |

The honest headline is **~2.0× p50 TTFT and ~1.9× decode throughput** — not 3.8×.
The single-shot 3.8× belongs to a 2.1×–3.8× band that depends on which
generation length you happen to draw. The non-determinism is itself a finding:
single-shot latency is not a stable comparison unit on this stack.

**Why Eagle3 at all — the design choice, not just the result.** Speculation
helps *because* plain decode pays a full per-step price to emit a single
token: every layer's weight read from HBM plus, on this PCIe-only node, a
synchronous all-reduce ladder — while the compute units idle (Investigation 5
now measures it directly: tensor pipes at 1–6% activity, ~170–200 W of 600 W).
A cheap drafter proposes N tokens; the target verifies all N in one forward
pass; rejection sampling keeps the output distribution identical. One forward
pass — one weight-read, one set of all-reduces — now yields several tokens
instead of one, paid from idle compute. But *which* speculator is decided by
model scale, not by a universal winner:

| Method | Proposes via | Best for |
|---|---|---|
| Draft model | separate small LLM | general; proven, costs VRAM + compute |
| N-gram / lookup | matching recent text | repetitive output, zero VRAM |
| Suffix decoding | CPU suffix tree | code/agentic, high repetition |
| MLP speculator | small multi-head MLP on target | VRAM-efficient 2–3× |
| **EAGLE / EAGLE-3** | transformer head on target's hidden features | large models needing high acceptance |

The scale trend is the argument: on Llama-3.1-**8B** the heuristics win (EAGLE
1.43× chat, Suffix 1.45× code; EAGLE-3 only 1.03×), but on Llama-3.3-**70B** the
learned head dominates (EAGLE-3 1.57× chat, 1.60× code). The bigger the model,
the more idle compute there is to spend on a learned drafter. Kimi-K2.6 is a
~1T-parameter MoE — far past the point where EAGLE-3 already won — so it is the
right family, and our measured 1.9–2.4× lands at or above the 70B numbers, as the
trend predicts.

**Predicting the speedup from the mechanism, then checking it.** The server log
records the speculation internals, so the gain is not a black box:

```
Mean acceptance length: 2.77,  Accepted: 626 / Drafted: 1062,
Per-position acceptance: 0.802, 0.551, 0.415   (quieter windows reach 3.15 / 71.7%)
```

Per-position acceptance **declines with depth** (~0.80 → 0.55 → 0.42): each
deeper draft token is conditioned on the previous ones holding, so it is harder
to guess. Mean acceptance length ≈ 2.8 means one target pass emits ~2.8 tokens,
which sets the *ideal* decode speedup at ≈ 2.8×. Measured TPOT-any improves 2.4×
— **~85% of the ideal**, the missing 15% being draft + verification overhead per
step. The mechanism predicts the number, and the number confirms the mechanism.

**Why the two TTFTs behave differently.** any-token TTFT is unchanged (~204 ms
both arms) because the first token of *any* kind is bounded by prefill, which
Eagle3 does not touch; content TTFT is faster because content arrival = prefill +
decoding the whole reasoning trace, and Eagle3 speeds that decode. *Eagle3 does
not give a faster first token; it gives a faster path through the reasoning trace
to the answer.*

**The cost, controlled.** The A/B has one impurity — `--max-num-batched-tokens`
was 4096 (ON) vs vLLM's 8192 default (OFF) — which I flag rather than hide: at a
15-token prompt and `--max-num-seqs 1` neither cap is ever reached, so it cannot
move the result here, *but it would bind under concurrency or long prompts* and
must be controlled in any follow-up. VRAM cost is small and now measured: ON
loads 71.92 GiB/GPU vs OFF 71.16 → the draft adds **≈0.76 GiB/GPU** (~1% of the
target). It is that cheap because the 5.62 GiB draft checkpoint is TP-sharded
(5.62/8 ≈ 0.70, matching the 0.76 measured) and vLLM **shares the target's
embedding table** with the draft head. Of 1062 drafted tokens, ~41% are
rejected — but that compute comes from the headroom decode was wasting anyway.

**Claim ledger.**
- **L0:** acceptance rates, token counts, VRAM delta — read from the server log
  and per-run JSON.
- **L1, robust within single-stream:** ~2× p50 TTFT / ~1.9× throughput —
  repeated (5 runs, equal-length p50) and consistent across the single-shot and
  repeated regimes.
- **Theoretical, not measured:** "lossless." Rejection sampling guarantees the
  distribution by construction and no anomaly appeared, but no quality eval was
  run — so this is a guarantee plus absence of observed problems, not a measured
  result.
- **Not shown:** concurrent-serving behavior, `num_speculative_tokens` tuning
  (the 3rd position's ~0.42 acceptance suggests 2-vs-3 is worth an A/B).

Full evidence: [T6](w1/t6-eagle3-speculative-decoding.md).

## Investigation 5 — 100% utilization on an idle GPU

**The number.** Under batched load, `nvidia-smi` showed **100% GPU-Util**.

**The trap.** 100% utilization reads as "the GPU is saturated, we are at the
ceiling." It is the most over-trusted number in the stack, and on these cards it
is almost meaningless on its own.

**The tell.** At 100% util the board drew only **~180–240 W of its 600 W**
limit. A saturated GPU does not sit at 40% of its power envelope. Separately, the
scheduler showed `waiting 45 > running 32` while KV cache sat at only **44%** and
**preemptions = 0**:

| Signal (batched, `--max-num-seqs 32`) | Value |
|---|---|
| running / waiting (kimi) | 32 / 45 |
| generation / prompt throughput | 327 / 1039 tok/s |
| KV cache usage | 44% peak |
| TTFT p50 / p95 | 11.2 s / 59.7 s |
| ITL p50 | 0.106 s |
| Eagle3 acceptance | 0.493 |
| preemptions | 0 |

**Two mechanisms, two causes (→ effect).** First, the power gap. The textbook
reading: `decode reads the whole layer's weights from HBM and does little
arithmetic per byte` → `arithmetic intensity is low, tensor cores idle while
the memory system works` → `SMs report "busy" (100% util) but the card is
nowhere near its power/compute ceiling`. That is the **memory-bound decode
signature**, it is invisible to vLLM `/metrics` (engine state, not silicon
state) — and it was the diagnosis recorded here, at L1. Hold that thought: it
is about to be tested, and it will not survive intact.
Second, the queue: `waiting > running with KV at 44% and zero preemptions` →
`the queue forms at the max-num-seqs 32 admission cap, not from KV exhaustion`
(KV exhaustion would instead drive KV → ~100% with preemptions > 0, the engine
evicting and recomputing running requests). The node is **scheduler-bound, not
KV-bound** — and single-stream TTFT of ~0.84 s rising to 11.2 s p50 under load is
queueing time, not slower serving.

**A cheap cross-check.** Two independent signals should corroborate if the
reading is right: 32 streams at ITL p50 0.106 s implies 32 × 1/0.106 ≈ 302 tok/s,
against the 327 tok/s aggregate gauge. The gauge and the histogram agree to
within p50-vs-mean noise — the decode-throughput story is self-consistent.

**Why utilization alone cannot close it.** This node is **PCIe-only — no NVLink,
no NVSwitch** (the engine log is explicit: custom all-reduce *"not supported on
more than two PCIe-only GPUs"*; FlashInfer all-reduce *"expected on GPUs without
NVSwitch"*). So every TP=8 all-reduce crosses PCIe. That means 100% util at low
power has *two* candidate causes — HBM-bandwidth-bound decode **or** PCIe
all-reduce stalls — and utilization percentage cannot distinguish them. Doing so
needs hardware counters vLLM does not expose: DCGM's `DRAM_ACTIVE` vs
`TENSOR_ACTIVE` vs `PCIE_*`
([#34](https://github.com/Czyszka/nanoserve-mini/issues/34)). So a follow-up
slot (2026-06-10) captured exactly those — `dcgmi dmon` at 1 Hz across all
eight GPUs, three windows: idle (models loaded, zero requests), single-stream
(c=1, 64-token prompts, 512-token outputs), batched (c=64, SWE-bench prompts,
256-token outputs, 600 requests).

**The counters came back — and killed the leading hypothesis.**

| DCGM counter (per-GPU mean over active samples) | idle | single c=1 | batched c=64 |
|---|---:|---:|---:|
| power draw | ~99 W | ~169 W | ~199 W (max 260) |
| `SM_ACTIVE` | 0.000 | 0.21 | 0.20 |
| `PIPE_TENSOR_ACTIVE` | 0.000 | 0.012 | 0.064 |
| `DRAM_ACTIVE` | 0.000 | **0.093** | **0.070** |
| PCIe TX / RX per GPU | ~0 | 1.9 / 6.0 GB/s | 6.0 / 8.0 GB/s |

("Active" = samples with `SM_ACTIVE` ≥ 0.10; full 1 Hz series in
`p0_gpu_counters/`. The c=64 window sustained 288 output tok/s, 600/600
requests completed.)

`DRAM_ACTIVE` is the verdict. The memory-bound story predicts HBM controllers
pinned high while compute idles; measured, the memory system is busy **9.3%**
of the time single-stream and **7.0%** under batch — more than 90% idle while
the node serves at full tilt. The "memory-bound decode signature" this
investigation recorded as its L1 is dead on this stack. (Why the textbook
intuition missed: the experts are 4-bit and only a fraction of them activate
per token, so a ~1T MoE reads far fewer bytes per token than the dense-model
arithmetic the signature comes from.) The sixth lying number in this document
is our own earlier diagnosis.

What the counters do show is sharper: **nothing is saturated.** SMs have work
resident ~20% of the time — against nvidia-smi's "100% util", which only says
*some* kernel was resident during each sample — tensor pipes run at 1–6%, HBM
at ≤9%, and the PCIe links carry 6–8 GB/s, roughly 10–13% of a Gen5 x16's
~63 GB/s per direction. A system whose every bandwidth resource sits mostly
idle while throughput stalls is the signature of **latency-bound, serialized
execution**: many small synchronous steps, each waiting on its slowest
dependency. On a PCIe-only TP=8 node the standing suspect is the per-layer
all-reduce. A coarse consistency check, assumption stated: attributing the c=1
window's entire measured TPOT (~22.5 ms/token on that workload) to the
~60-layer × 2-all-reduce ladder prices each synchronization round at
≈0.2 ms — a plausible small-message PCIe all-reduce cost on eight GPUs. The
batching trend agrees: from c=1 to c=64, tensor activity rises ~5× and PCIe TX
~3× while `DRAM_ACTIVE` stays flat — batching buys more compute per step, not
more memory traffic, exactly what amortized weight reads plus fixed per-step
communication predict. Consistent with comms-bound; still not proof — proof
needs a comms-level lever (NCCL-level timing, or a topology counterfactual),
which stays in #34.

One caveat on the c=1 window, stated so its numbers are not misread: random
64-token prompts with `--ignore-eos` draft poorly under Eagle3, so that window
decodes at ~46 tok/s instead of the 112 tok/s natural-prompt baseline — a
slow-decode operating point. It changes nothing about the verdict: a
bandwidth-bound system would show high `DRAM_ACTIVE` regardless of how fast
the tokens come out.

**The forward read — bought with latency.** The one directly evidenced lever is
`--max-num-seqs`: waiting 45 > running 32 at KV 44% means the admission cap, not
memory, holds the batch small, so admitting more of the queue would raise
arithmetic intensity (real FLOPs, real power) and drain the queue. But that is
*throughput bought with latency* — per-token ITL is already ~15× its
single-stream value at batch 32. For a latency-critical reasoning model you may
deliberately leave compute idle to keep ITL low. (Operational aside: observability
runtime data lives in explicit host bind mounts rather than Docker volumes,
precisely so this evidence could be triaged and copied off the server inside a
two-day slot — [T7](w1/t7-host-directories.md).)

**Claim ledger.**
- **L0:** every value in the first table — 3 h Prometheus window
  (`prometheus_summary.txt`); gauges are Kimi-only, TTFT/E2E/ITL percentiles
  over *all* requests. Every value in the counters table — `dcgmi` 1 Hz, all
  eight GPUs, three windows (2026-06-10).
- **Refuted (2026-06-10):** HBM-bandwidth-bound decode — the prediction was
  `DRAM_ACTIVE` high under load; measured ≤9%. A rare clean kill: the
  counterexample is direct.
- **L1, strengthened:** PCIe-comms/serialization-bound — the all-idle
  signature, the PCIe traffic trend, and the ≈0.2 ms/round arithmetic all point
  the same way, but no comms-level lever has been isolated yet.
- **L1, unchanged:** scheduler-bound-not-KV-bound — the queue mechanism is
  untouched by the counters.
- **Still open for L2/L3:** the concurrency sweep at fixed prompt/output
  distribution, and a comms lever (NCCL timing or topology change) for the
  all-reduce attribution.

Full evidence: [T5](w1/t5-observability.md).

## Five numbers, one move

`crash` · `n/a` · `completed: false` · `3.8×` · `100%`. Five numbers that each
looked like an answer and was actually a question about a hidden precondition —
the post-load KV ceiling, the streaming channel, the delivery path, the
generation-length confound, the meaning of utilization itself. The skill on display is
not the measurement. It is the reflex to ask, before trusting any figure, *what
must be true for this number to mean what it appears to mean* — and then to read
the log, the source, or the second signal that confirms or kills it.

That reflex produces the actual W1 baseline — measured **direct** (not through
the proxy), single-stream, repeated, temperature 0:

| Model (direct, single-stream) | TTFT p50 | TTFT p95 | tok/s | completion p50 |
|---|---:|---:|---:|---:|
| Kimi-K2.6, Eagle3 ON `:8000` | **837 ms** | 1694 ms | 111.6 | 97 tok |
| Kimi-K2.6, Eagle3 OFF `:8000` (control) | 1675 ms | 4426 ms | 58.7 | 97 tok |

DeepSeek-V4-Flash (cap 0.20) is intentionally absent: it has only a serviceability
smoke (`"say OK"` → `"OK"`, 2 tokens, cold first-request TTFT 15.2 s per
[T3](w1/t3-deepseek-vram-budget.md)), which is not a comparable latency baseline —
a real DeepSeek generation workload is deferred (below).

**What these numbers do not mean**, stated so they are not misread: this is not a
throughput claim (single-stream, one short prompt — the batched picture is 327
tok/s at 11.2 s TTFT, queue-dominated); DeepSeek is excluded for want of a real
generation workload (a rate from a 2-token smoke is an artifact); the Kimi ratios are length-p50, not
single-shot E2E; and it is one driver/runtime/topology (vLLM v0.20, CUDA 13.2,
PCIe-only).

The honest gaps are exactly the **L1 → L2/L3 promotions** the evidence ladder
demands. Two of them have since been run, in a follow-up slot on 2026-06-10;
two remain named counterfactuals:

- **Hop attribution — done.** The proxy hop is attributed at ~37 ms (c=1,
  loopback, paired against vLLM's own histograms), and the reasoning-strip is
  promoted to L2: same server-side work, opposite client outcome, 5/5. The
  concurrency sweep (R2) — the curve that decides production viability — stays
  open ([#44](https://github.com/Czyszka/nanoserve-mini/issues/44)).
- **HBM-bound vs PCIe-comms-bound — measured, and the favorite lost.** The
  DCGM split came back with `DRAM_ACTIVE` ≤ 9% under load: HBM-bandwidth-bound
  is refuted; comms/serialization-bound stands as the surviving hypothesis,
  awaiting a comms-level lever for the causal close
  ([#34](https://github.com/Czyszka/nanoserve-mini/issues/34)).
- **DeepSeek under real generation** — current baseline is a 2-token smoke.
- **Speculation under load** — the A/B is single-stream; acceptance (0.493
  batched vs 59–72% single-stream) and the `max-num-batched-tokens` confound
  become live.

The follow-up also closed this document's loop in the only way that really
tests a method: by turning the reflex on the document itself. "Memory-bound
decode" read like settled mechanism in the first draft — plausible, textbook,
and wrong by an order of magnitude the moment `DRAM_ACTIVE` was actually read.
The five numbers lied about the system. The sixth lied about us, and the same
move caught it.

Knowing precisely where the provable stops is not the project's weakness. It is
the same discipline that caught the five numbers in the first place.

## References

[1] X. Miao, G. Oliaro, Z. Zhang, X. Cheng, H. Jin, T. Chen, and Z. Jia,
"Towards Efficient Generative Large Language Model Serving: A Survey from
Algorithms to Systems," *ACM Computing Surveys*, 2025. arXiv:2312.15234.

[2] JarvisLabs, "Speculative decoding in vLLM: faster LLM inference,"
<https://jarvislabs.ai/blog/speculative-decoding-vllm-faster-llm-inference>.
Method taxonomy and model-scale trend used in Investigation 4.

[3] vLLM, "[Bug]: KV cache size log is wrong," issue #40691,
<https://github.com/vllm-project/vllm/issues/40691>. The KV-display
discrepancy in Investigation 1.

---

*Per-investigation thread files with full evidence tables and artifact paths:*
*[T1 Kimi bring-up](w1/t1-kimi-bringup.md) · [T2 reasoning TTFT](w1/t2-reasoning-ttft.md) · [T3 DeepSeek VRAM](w1/t3-deepseek-vram-budget.md) · [T4 LiteLLM Proxy](w1/t4-litellm-proxy.md) · [T5 observability](w1/t5-observability.md) · [T6 Eagle3](w1/t6-eagle3-speculative-decoding.md) · [T7 host directories](w1/t7-host-directories.md) · [T8 proxy overhead](w1/t8-litellm-overhead.md)*
