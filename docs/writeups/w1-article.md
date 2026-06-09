# W1 — vLLM + LiteLLM Proxy on 8×H200: a multi-model serving baseline from zero to first measurement

> **Setup:** 8×H200 NVL 143 GB/GPU · vLLM v0.20.0 · CUDA 13.2 · driver 595.58.03
> **Models:** Kimi-K2.6 (~1T MoE) + DeepSeek-V4-Flash, co-resident
> **Stack:** vLLM + LiteLLM Proxy · Prometheus + Grafana
> **Evidence:** `results/runs/2026-06-05_w1_evidence/` (commit `d0bb634`)
>
> Detailed thread files with full evidence tables: [`docs/writeups/w1/`](w1/)

---

## Why getting to a first number is harder than it looks

Benchmarking a served LLM looks simple: start the engine, send a request, measure
the latency. In practice, the first number you get is often wrong — not because
the timer is broken, but because three invisible problems come before it:

1. The engine might not start at all (KV-cache budget underflows).
2. The metric you're measuring might not be what you think (TTFT for a reasoning
   model has at least two defensible definitions that diverge by 3×).
3. The baseline you're comparing against might be measuring a different thing
   than the production path (the proxy changes streaming semantics, not just latency).

This write-up follows the path from an empty 8×H200 node to a first TTFT/E2E
measurement — and focuses on what had to be true before that number meant anything.

---

## The stack

The serving configuration is two co-resident vLLM instances behind a LiteLLM
Proxy, all defined in one Docker Compose file
(`serving/compose/docker-compose.kimi-k2.6.yml`):

```
port :8000  vllm        — Kimi-K2.6   TP=8, gpu-mem-util 0.60, Eagle3 ON
port :8004  vllm-small  — DeepSeek-V4-Flash  TP=8, gpu-mem-util 0.20, FP8 MLA
port :4000  litellm     — routes {model: "kimi-k2.6"} → :8000,
                                 {model: "DeepSeek-V4-Flash"} → :8004
port :9090  prometheus
port :3001  grafana
```

The proxy's job is narrow: expose one OpenAI-compatible endpoint so the
benchmark client can change models by varying the `model` field rather than
the base URL. There is no content-aware routing, no per-user key management, no
structured per-request logging. Those are later additions; the W1 question is
whether this minimal boundary is sufficient to trust the first measurement.

Each model runs under a `--gpu-memory-utilization` cap that reserves a share of
each GPU for the co-tenant. Choosing those caps correctly is what this write-up
is mostly about.

---

## The first wall: negative KV-cache budget

### Attempt 1 — Kimi with data + expert parallelism

The first Kimi-K2.6 bringup used **data + expert parallelism** (DEP:
`--data-parallel-size 8 --enable-expert-parallel`) at `gpu-memory-utilization
0.6`. All eight `EngineCore_DP{0..7}` processes crashed with the same error:

```
ValueError: No available memory for the cache blocks. Try increasing
`gpu_memory_utilization` when initializing the engine.
```

vLLM's budget arithmetic at this point (`dep_full.log`, `gpu_worker.py:440`):

```
budget  = 0.6 × 140.40 GiB  =  84.24 GiB
− weights (DEP)             =  88.44 GiB
− CUDA graph                =   0.13 GiB
− activation peak           ≈  14.75 GiB
─────────────────────────────────────────
  Available KV cache        = −19.08 GiB   ← engine refuses to start
```

The **weights loaded successfully** — vLLM's `gpu_memory_utilization` cap is not
a load-time allocation limit. It is applied ~2 minutes later when vLLM computes
how much of the capped budget remains for KV blocks after subtracting the
measured non-KV footprint. Only then does the negative number appear.

**Why DEP costs more than TP.** Under tensor parallelism, every weight tensor is
sharded across 8 GPUs — each GPU holds 1/8 of every weight. Under DEP, the
non-expert weights (attention, norms, embeddings, ~22 GiB of dense path) are
**replicated** on every GPU, while only the 384 MoE experts are sharded (48 per
GPU). The resulting per-GPU weight footprint under DEP is 88.44 GiB vs ~69.3 GiB
under TP=8 — a ~19 GiB/GPU overhead that directly matches the −19.08 GiB KV
deficit. DEP buys throughput under concurrency (8 independent request streams)
but costs the node's ability to cache any KV at all on this workload.

**Fix:** switch to TP=8. That shards all weights and restores a positive KV budget
at the same `gpu-memory-utilization 0.6`. Since W1 is single-stream (one request
at a time), DEP's concurrency advantage is zero — no reason to pay the memory cost.

### Attempt 2 — DeepSeek at too low a cap

The same failure appeared independently when sweeping DeepSeek-V4-Flash's
`gpu-memory-utilization` across three values with Kimi co-resident:

| Cap  | Available KV cache | Outcome |
|------|--------------------|---------|
| 0.15 | **−0.49 GiB**      | `EngineCore failed to start` |
| 0.20 | +6.5 GiB           | healthy, 6.51× concurrency at 64k ctx |
| 0.25 | +13.49 GiB         | healthy, 13.54× concurrency |

DeepSeek's weight footprint is fixed at **20.32 GiB/GPU** regardless of cap; the
cap only sizes the KV-block pool left over. At 0.15, that margin goes negative —
the same arithmetic, the same family of crash.

**The W1 choice is 0.20.** For a single-stream baseline, DeepSeek's ~6.5 full
64k-context equivalents of KV room far exceeds demand. 0.25 doubles the KV pool
but spends ~7 GiB/GPU of board headroom that otherwise cushions the co-resident
Kimi service and absorbs load spikes. 0.20 is the conservative point: start safely,
leave margin, raise later when a real concurrent workload makes KV the binding resource.

**The cross-cutting lesson.** Two independent bringup failures are the same
failure: *serving does not fail when the weights don't fit — it fails when nothing
is left for the KV cache.* Both T1 and T3 are KV-budget arithmetic, not weight-size
problems. This is the first thing to check before attempting any measurement.

---

## What "TTFT" actually means for a reasoning model

### The parser returned `TTFT: n/a` — and it was correct

The benchmark script `measure_ttft_once.py` returned `TTFT: n/a` and `TPOT: n/a`
against Kimi-K2.6. The script was timing off the first `delta.content` token. The
stream it received contained many non-empty chunks — but they all carried
`delta.reasoning`, not `delta.content`. In the captured `stream_short_prompt.sse.txt`,
the entire completion was reasoning that ended with `finish_reason: "length"` after
64 tokens. No `delta.content` token ever appeared.

`TTFT: n/a` was the correct answer to the question the parser was asking: it had
simply asked the wrong question.

### Two clocks, four factors

For a reasoning model like Kimi-K2.6, "TTFT" is not one number — it is a
(measurement point, channel) pair:

| Metric | Starts when | What it captures |
|--------|-------------|------------------|
| `ttft_any_token_seconds` | first non-empty reasoning **or** content delta | model started producing output |
| `ttft_seconds` (content TTFT) | first non-empty `delta.content` | the final answer started |

The 2026-05-27 paired pilot (10 requests/model, single-stream, direct path) shows
how far apart these can be:

| Model | content TTFT | any-token TTFT | gap |
|-------|-------------|----------------|-----|
| Kimi-K2.6 | 0.592 s | 0.209 s | **2.8×** |
| DeepSeek-V4-Flash | 0.253 s | 0.253 s | 1.0× |

For Kimi the two TTFTs from the *same stream* diverge by 2.8× — entirely because
Kimi streams a reasoning trace before the answer begins. vLLM's own server-side
TTFT histogram (`vllm:time_to_first_token_seconds`) tracks the any-token view.
Comparing a client content-TTFT against vLLM's server-side number is comparing
different clocks on different channels.

The parser fix (issue #31, commit `cca4022`) added `ttft_any_token_seconds` and
made a response consisting entirely of reasoning count as `completed: true`.

### The proxy collapses the reasoning channel

An expected consequence of the channel split is what LiteLLM Proxy does to it.

A paired capture (`run-01_t8-proxy` vs `run-03_t8-direct`, same prompt, same
`max_tokens=64`) shows the proxy stripping the reasoning deltas entirely:

| Path | chunks | reasoning_chars | any-token TTFT | completed |
|------|--------|-----------------|----------------|-----------|
| direct `:8000` | 26 | 242 | 0.214 s | **true** |
| proxy `:4000`  | 3  | 0   | null    | **false** |

Both paths generated the same 64 tokens. On the direct path, those tokens were
reasoning and streamed through — the client received usable output. On the proxy
path, LiteLLM `main-v1.66.0-stable` silently dropped the reasoning channel; the
client saw three content-less chunks and `completed: false` — effectively nothing.

**This is a usability hazard, not just a latency difference.** Under a finite
`max_tokens`, a reasoning-heavy request routed through this LiteLLM version can
return an empty-looking response. The W1 baseline is therefore measured **direct**,
not through the proxy. The proxy is sound for routing; it is not transparent for
reasoning-model streams in this version.

---

## Speculative decoding: Eagle3's cost and payoff

### Why speculation helps a memory-bound model

Plain autoregressive decode is **memory-bound**: to emit one token the engine
reads the entire model's weights from HBM and does very little arithmetic per
byte. T5 observed this directly — 100% GPU-Util at only ~180–240 W of the 600 W
per-GPU limit on these H200s. The compute units sit idle, waiting on memory.

Speculative decoding exploits that idle compute: a cheap *drafter* proposes the
next N tokens; the expensive *target* verifies all N in **one forward pass** instead
of running N separate times. Accepted tokens are kept; the first rejected one is
resampled from the target's own distribution — the output distribution is
**unchanged** by construction. The win is amortization: one weight-read produces
~3 tokens instead of 1.

### The A/B

Kimi-K2.6 runs with the Eagle3 head (`lightseekorg/kimi-k2.6-eagle3-mla`,
`num_speculative_tokens=3`). The ON/OFF A/B ran TP=8, `max-num-seqs 1`,
temperature 0, same prompt.

Single-shot results (1 run, `max_tokens=1024`):

| Metric | Eagle3 ON | Eagle3 OFF | ratio |
|--------|-----------|-----------|-------|
| TTFT (content) | 652 ms | 2489 ms | 3.8× |
| TTFT (any token) | 204 ms | 203 ms | **1.0×** |
| E2E | 674 ms | 2536 ms | 3.8× |
| TPOT (any token) | 6.92 ms/tok | 16.55 ms/tok | 2.4× |
| Completion tokens | 69 | 142 | — (unequal) |

The 3.8× is partly an artifact: at temperature 0 the OFF arm happened to generate
a longer reasoning trace (546 vs 240 chars) and more output tokens (142 vs 69) — a
longer generation inflates E2E independently of decode speed.

The **repeated run** removes this confound: across 5 measured requests the median
completion length equalizes at 97 tokens in both arms, giving stable ratios:

| Metric (p50) | Eagle3 ON | Eagle3 OFF | ratio |
|---|---|---|---|
| TTFT p50 | **837 ms** | **1675 ms** | **2.0×** |
| TTFT p95 | 1694 ms | 4426 ms | 2.6× |
| E2E p50 | 857 ms | 1724 ms | 2.0× |
| tok/s | 111.6 | 58.7 | **1.9×** |

**The robust headline is ~2× p50 TTFT and ~1.9× decode throughput.**

### Why the two TTFTs diverge 3.8× in the single-shot

TTFT-any-token is unchanged (~204 ms) because that is the time to the *first
generated token of any kind* — bounded by prefill, which Eagle3 does not
accelerate. TTFT-content is 3.8× faster because content arrival = prefill +
decoding the entire reasoning trace, and Eagle3 speeds up that decode segment.

**Eagle3 does not give a faster first token. It gives a faster path through the
reasoning trace to the final answer.**

### What it costs

The draft model (`lightseekorg/kimi-k2.6-eagle3-mla`) adds **≈0.76 GiB/GPU** of
resident weights — about 1% of the target footprint. Its checkpoint is only 5.62 GiB
on disk (vs the target's 554.30 GiB) because vLLM shares the target's embedding table
with the draft head. The draft compute is paid from idle GPU headroom — the same
headroom T5 observed sitting unused during decode.

The acceptance rate from the server log: per-position rate of 0.80 / 0.55 / 0.42
across the three drafted positions, mean acceptance length 2.8–3.1 tokens per
target forward pass, 59–72% overall. Under batched SWE-bench load (T5) the
acceptance rate drops to 0.493 — diverse continuations are harder to draft.

**The call:** Eagle3 ON is the production configuration for W1. ~2× p50 TTFT at
~1% VRAM cost, paid out of otherwise-idle compute.

---

## Observability: useful signals vs misleading ones

### What `/metrics` tells you (and doesn't)

vLLM exposes a rich `/metrics` endpoint: queue depths, token rates, KV cache
usage, request histograms, speculative decoding counters. All Phase 1 dashboard
panels were validated against the live 2026-06-05 dump — metric names are real in
vLLM v0.20.0, no dashboard JSON fixes needed.

What `/metrics` **does not** tell you: anything about the physical hardware. GPU
power, DRAM bandwidth, SM/Tensor core activity, NVLink utilization — none of
these are in the vLLM endpoint. They require a DCGM Exporter (tracked in #34).

### The batched load picture

Driving the node under real load (`--max-num-seqs 32`, SWE-bench Lite workload)
populated the queue and latency panels that single-stream benches leave flat:

| Signal | Value |
|--------|-------|
| requests running (kimi) | 32 |
| requests waiting (kimi) | 45 |
| generation throughput | 327 tok/s |
| KV cache usage | 44% peak |
| TTFT p50 / p95 | 11.2 s / 59.7 s |
| Eagle3 draft acceptance | 0.493 |
| preemptions | 0 |

Reading: **waiting (45) exceeds running (32) while KV is at only 44% and
preemptions are 0.** This is the scheduler-bound signature: the `max-num-seqs 32`
admission cap is what forms the queue, not KV exhaustion. KV exhaustion would
show KV → ~100% and preemptions > 0. Single-stream TTFT was ~0.84 s; here it
rises to 11.2 s p50 because requests sit in the WAITING queue before prefill
begins.

Informally, `nvidia-smi` during the load run showed 100% GPU-Util at ~180–240 W /
600 W limit — the memory-bound decode signature. A server running at full reported
utilization can be far from its power/compute ceiling if the bottleneck is HBM
bandwidth, not FLOPs. This is completely invisible to the vLLM dashboard.

**One hardware note:** this node is **PCIe-only** — no NVLink, no NVSwitch. The
vLLM startup log makes it explicit (*"custom all-reduce not supported on more than
two PCIe-only GPUs"*; FlashInfer all-reduce *"expected on GPUs without NVSwitch"*).
Every TP=8 all-reduce traverses PCIe. 100% GPU-Util at low power could mean
HBM-bandwidth-bound decode *or* PCIe all-reduce bottleneck — the two are
indistinguishable from utilization alone. Disambiguating them requires DCGM
`DRAM_ACTIVE` vs `TENSOR_ACTIVE` counters (#34).

---

## Baseline results

The W1 sanity baseline is measured **direct** (not through the proxy), single-stream
(`max-num-seqs 1`), repeated (`singlestream_lite_repeated`: warmup 1 + 5 measured
runs, temperature 0):

| Model (direct, single-stream) | TTFT p50 | TTFT p95 | tok/s | completion p50 |
|---|---:|---:|---:|---:|
| Kimi-K2.6, Eagle3 ON `:8000` | **837 ms** | 1694 ms | 111.6 | 97 tok |
| Kimi-K2.6, Eagle3 OFF `:8000` (control) | 1675 ms | 4426 ms | 58.7 | 97 tok |
| DeepSeek-V4-Flash `:8004` (cap 0.20) | 1.26 s | 1.58 s | — | 3 tok |

**What these numbers do not mean:**

- **Not a throughput claim.** Single-stream, one short prompt, `max-num-seqs 1`.
  The batched picture (327 tok/s, TTFT p50 11.2 s, queue-dominated) is the load
  run, not this table.
- **DeepSeek tok/s is intentionally omitted.** The smoke output is ~3 tokens — a
  throughput rate from 3 tokens is an artifact, not a serving result. A real
  generation workload is needed (#44 R7) before a DeepSeek throughput claim is
  meaningful.
- **Kimi TTFT ratios are length-sensitive.** Even at temperature 0, TP=8 +
  speculative scheduling produces length variance run-to-run. The table uses
  repeated p50 (equal 97-token median), not single-shot E2E.
- **One driver/runtime.** vLLM v0.20-series, CUDA 13.2, driver 595.58.03,
  8×H200 NVL 143 GB, PCIe-only interconnect.

The baseline is deliberately measured direct. The proxy path cannot serve as the
Kimi reasoning-model baseline in LiteLLM `main-v1.66.0-stable` because it
silently strips `delta.reasoning` — returning `completed: false` on
reasoning-heavy requests.

---

## What this write-up does not settle

These are intentional deferrals, not gaps:

1. **Proxy overhead under concurrency** — the 2026-05-27 pilot established a
   single-stream latency delta (~17 ms Kimi, ~26 ms DeepSeek) and the reasoning-strip
   hazard. The full program (hop attribution via vLLM's shared-reference-clock method,
   concurrency sweep, workload matrix) is tracked in issue #44.
2. **GPU hardware telemetry** — DCGM Exporter is not yet in the stack. 100% GPU-Util
   at low power is a hypothesis (memory-bound decode or PCIe comms bottleneck), not
   a measurement. The disambiguation needs `DRAM_ACTIVE` / `TENSOR_ACTIVE` counters
   (#34).
3. **DeepSeek real-generation workload** — the current baseline is a ~3-token smoke
   response. DeepSeek throughput and proxy-relay behavior under real generation are
   unmeasured (#44 R7).
4. **Speculative decoding under concurrency** — the A/B is single-stream. Acceptance
   dynamics and the `--max-num-batched-tokens` confound (4096 ON vs 8192 OFF) become
   relevant under load.

---

## References

[1] X. Miao, G. Oliaro, Z. Zhang, X. Cheng, H. Jin, T. Chen, and Z. Jia,
"Towards Efficient Generative Large Language Model Serving: A Survey from
Algorithms to Systems," *ACM Computing Surveys*, 2025. arXiv:2312.15234.

[2] JarvisLabs, "Speculative decoding in vLLM: faster LLM inference,"
<https://jarvislabs.ai/blog/speculative-decoding-vllm-faster-llm-inference>.
Method taxonomy and scale-trend benchmark used in §Eagle3.

---

*Thread files with full evidence tables and artifact paths:
[T1 Kimi bringup](w1/t1-kimi-bringup.md) · [T2 reasoning TTFT](w1/t2-reasoning-ttft.md) · [T3 DeepSeek VRAM](w1/t3-deepseek-vram-budget.md) · [T4 LiteLLM Proxy](w1/t4-litellm-proxy.md) · [T5 observability](w1/t5-observability.md) · [T6 Eagle3](w1/t6-eagle3-speculative-decoding.md) · [T7 host directories](w1/t7-host-directories.md) · [T8 proxy overhead](w1/t8-litellm-overhead.md)*
