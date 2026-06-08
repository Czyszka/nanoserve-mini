# T6 — Why Eagle3, and what it costs

Mode: justification + measurement.

## Question

Kimi-K2.6 is served with Eagle3 speculative decoding enabled. Does that
configuration earn its place in the Phase 1 baseline — and what, specifically,
does it buy and cost on this 8×H200 node? The decision must rest on a controlled
ON/OFF comparison on our own stack, not on the upstream model card's claims.

## Decision

Keep Eagle3 speculative decoding ON for Kimi-K2.6 in the Phase 1 baseline. On a
single-stream workload it delivers a robust **~2.0× p50 TTFT and ~1.9× decode
throughput** at temperature 0, with **no first-token penalty** and no observed
correctness anomaly. The draft model is accepted **~59–72%** of the time
(per-step it yields ~2.8–3.1 tokens for one target forward pass), and its cost —
the rejected drafts — is paid out of compute the GPU was leaving idle anyway. Its
memory cost is small and now measured: **≈0.76 GiB/GPU** of extra draft weights
(~1% of the target), because the EAGLE-3 head shares the target's embedding table.
The benefit is real but bounded; the sections below state exactly which number to
trust and which not to.

## How speculative decoding works (the one-pass idea)

Plain autoregressive decoding is **memory-bound**: to emit one token the engine
reads the entire model's weights from HBM and does very little arithmetic per
byte (T5 measured the symptom directly — 100% GPU-util at only ~180–240 W of
600 W). The compute units sit mostly idle, waiting on memory.

Speculative decoding exploits that idle compute. A cheap *drafter* proposes the
next *N* tokens; the expensive *target* model then verifies all *N* in a **single
forward pass** instead of running *N* times. Accepted tokens are kept; the first
rejected token is corrected from the target's own distribution. Crucially this is
**lossless**: rejection sampling makes the output distribution identical to the
target's, so quality is preserved by construction — speculation only changes
*how fast* tokens are produced, not *which* distribution they are drawn from.

The win is amortization: one weight-read from HBM now produces several accepted
tokens instead of one. Because the bottleneck was memory, the extra draft compute
is nearly free — it consumes the compute headroom T5 showed was being wasted.
This is why speculation pays off most on large, memory-bound models.

## The method landscape — and why Eagle3 for Kimi

vLLM supports several speculation strategies. They differ in where the proposal
comes from and what it costs (adapted from the JarvisLabs vLLM speculative-decoding
study, see Reference; method choice is tracked in #48):

| Method | How it proposes tokens | Trade-off | Best suited for |
|---|---|---|---|
| **Draft model** | a separate small LLM predicts, target verifies (rejection sampling) | needs a compatible tokenizer/vocab; draft is extra VRAM + compute | general-purpose; the original, proven approach |
| **N-gram / prompt lookup** | matches recent text against history and reuses continuations | zero VRAM, no model; only helps when text repeats | repetitive / templated output; memory-constrained setups |
| **Suffix decoding** | CPU-side suffix tree (per-request + global), adaptive proposal length | model-free, runs on CPU; depends on repetition | code generation, agentic loops, high-repetition workloads |
| **MLP speculator** | small multi-head MLP on the target predicts 1–3 steps ahead | ~1/10 of a draft model's params; needs two-stage training | production systems wanting VRAM-efficient 2–3× |
| **EAGLE / EAGLE-3** | lightweight transformer head(s) fused from the target's own hidden features | <5% param overhead; EAGLE-3 adds a train-time test to fix inference distribution mismatch | general chat (EAGLE); large models needing maximum accuracy (EAGLE-3) |

The same study shows the choice is decided by **model scale and task**, not by a
universal winner: on Llama-3.1-**8B** the low-overhead heuristics win (EAGLE 1.43×
on chat; Suffix 1.45× on code, where trained heads barely helped — EAGLE-3 only
1.03×), but on Llama-3.3-**70B** the learned head dominates both regimes
(EAGLE-3 1.57× chat, 1.60× code). The reason is exactly the memory-bound argument
above: the bigger the model, the more idle compute there is to spend on a learned
drafter, and the more accurate that drafter needs to be to keep acceptance high.

Kimi-K2.6 is a ~1T-parameter MoE — far beyond the 70B point where EAGLE-3 already
won outright. So the EAGLE3 family is the right call here, and our measured
single-stream **1.9–2.4×** (below) lands at or above the 70B EAGLE-3 numbers, as
the scale trend predicts. (One config difference worth noting: the study runs
EAGLE at `num_speculative_tokens=2`; we run 3 — see "Acceptance economics".)

## A/B setup and its one impurity

Both arms ran against the same Kimi-K2.6 service on `:8000`, TP=8,
`--gpu-memory-utilization 0.6`, `--max-num-seqs 1`, `--max-model-len 131072`,
temperature 0, prompt `"Say hi in one short sentence."`. The captured engine
commands (`t6_eagle3/engine_cmd_eagle3_{on,off}.json`) show the ON arm adds:

```
--max-num-batched-tokens 4096
--speculative-config={"model":"lightseekorg/kimi-k2.6-eagle3-mla",
                      "method":"eagle3","num_speculative_tokens":3,
                      "max_model_len":8192}
```

The intended variable is `--speculative-config`. Honesty requires noting a second
difference — `--max-num-batched-tokens` — and stating it precisely: it is **not**
"ON has the flag, OFF does not". vLLM simply fell back to its **default of 8192**
for the OFF arm (`kimi_log_eagle3_off.txt:13`: *"Chunked prefill is enabled with
max_num_batched_tokens=8192"*), while the ON arm pinned it to **4096**. So the
real confound is **4096 (ON) vs 8192 (OFF)**, not a presence/absence.

**What the parameter does, and why it does not bind here.** Under chunked prefill,
`max_num_batched_tokens` caps the total tokens — prefill chunks *plus* decode
steps — processed in one scheduler step. With a 15-token prompt at
`--max-num-seqs 1`, prefill is a single 15-token chunk and decode is one token
(plus ≤3 draft tokens) per step; both are orders of magnitude below 4096 *and*
8192. Neither cap is ever reached, so the 4096-vs-8192 difference cannot move
TTFT, TPOT, or E2E for this workload — the measured difference stays attributable
to speculation.

**Where it would matter** (flagged so a concurrency/long-prompt study does not
inherit a hidden assumption): with long prompts a smaller cap (4096) splits
prefill into more chunks → more scheduler steps and a different TTFT; under
concurrency the budget is shared across all running sequences, setting the
prefill-vs-decode balance per step; and speculation itself consumes budget for
draft-token slots — vLLM flags exactly this interaction elsewhere
(*"max_num_scheduled_tokens is set to … based on the speculative decoding settings
… Consider increasing max_num_batched_tokens to accommodate the additional draft
token slots"*, seen in the DeepSeek MTP startup,
`t3_deepseek_vram/log_restored_default.txt:158`). Under load the ON arm's smaller
4096 could therefore *throttle* drafting while OFF's 8192 would not — the opposite
of a benign confound, so it must be controlled in any concurrent follow-up.

## Measurement

All figures below are verified against the committed per-run JSON (paths in
Evidence).

### Single-shot (`singlestream_lite_latency`, 1 run, `max_tokens` 1024)

| Metric | Eagle3 ON | Eagle3 OFF | ON/OFF |
|---|---|---|---|
| TTFT — final-answer content | 652 ms | 2489 ms | **3.8× faster** |
| TTFT — any token (incl. reasoning) | 204 ms | 203 ms | ~1.0× (no change) |
| E2E | 674 ms | 2536 ms | 3.8× faster |
| TPOT — any token | 6.92 ms/tok | 16.55 ms/tok | 2.4× faster |
| Output tokens/s | 102.3 | 56.0 | 1.8× |
| Completion tokens | 69 | 142 | — (not equal) |

### Repeated (`singlestream_lite_repeated`, warmup 1 + 5 measured, sequential)

| Metric | Eagle3 ON | Eagle3 OFF | ON/OFF |
|---|---|---|---|
| TTFT p50 | 837 ms | 1675 ms | **2.0× faster** |
| TTFT p95 | 1694 ms | 4426 ms | 2.6× faster |
| E2E p50 | 857 ms | 1724 ms | 2.0× faster |
| Output tokens/s | 111.6 | 58.7 | 1.9× |
| Request throughput | 0.84 req/s | 0.36 req/s | 2.3× |
| Completion tokens p50 | 97 | 97 | equal |

## Reading the numbers — lead with repeated p50, not single-shot

The single-shot **3.8× E2E is partly an artifact of output length**: at
temperature 0 the two arms did not emit the same number of tokens (OFF generated
142 completion tokens, ON 69), and the OFF reasoning trace was longer (546 vs
240 chars). A longer generation inflates OFF's E2E independently of decode speed,
so 3.8× overstates the steady-state gain.

The repeated run removes that confound: across 5 measured requests the **median
completion length is identical (97 tokens in both arms)**, so its p50 ratios
isolate decode behavior. The robust headline is therefore:

- **~2.0× p50 TTFT** (837 vs 1675 ms) and **~1.9× decode throughput**
  (111.6 vs 58.7 tok/s).
- Single-shot E2E lands in a **2.1×–3.8×** band depending on which generation
  length you draw; report it as a range, not a point.

The non-determinism is itself a finding: even at temperature 0, TP=8 +
speculative scheduling does **not** produce token-identical generations
run-to-run (completion tokens ranged 94–190 ON, 97–285 OFF). This variance comes
from floating-point reduction order under TP=8, not from speculation (which is
distribution-preserving); but it means single-shot latency is not a stable
comparison unit here.

## Why the two TTFTs diverge

The single-shot table reports two first-token times that behave completely
differently — 3.8× apart on content, unchanged on any-token. This is not a
contradiction; they measure different clock boundaries (the same content-vs-any
distinction T2 draws):

- **TTFT-any-token (≈204 ms, unchanged)** is the time to the *first token of any
  kind*. That token cannot appear until **prefill** finishes processing the
  prompt and one decode step runs. Eagle3 accelerates the **decode loop, not
  prefill**, so it cannot move the first token — exactly as theory predicts. Both
  arms pay the same ~204 ms.
- **TTFT-content (652 vs 2489 ms, 3.8×)** is the time to the first token of the
  *final answer*. Kimi-K2.6 is a reasoning model: it decodes an entire reasoning
  trace **before** the answer begins. So TTFT-content = prefill + decoding the
  whole reasoning trace, and Eagle3 speeds up that decode segment. The gap is
  then amplified by length: in this single shot OFF happened to reason longer
  (546 vs 240 chars), so it had more trace to decode. That is why the 3.8×
  belongs to the confounded single-shot band, while the robust per-token gain is
  the ~2× from the repeated run.

In one line: **Eagle3 does not give a faster first token; it gives a faster path
through the reasoning trace to the final answer.**

## Acceptance economics — the mechanism behind the speedup

vLLM's server log (`kimi_log_eagle3_on.txt`) records the speculation internals,
so the speedup is not a black box. During the run-04 generation burst (09:01:35):

```
SpecDecoding metrics: Mean acceptance length: 2.77,
Accepted: 626 tokens, Drafted: 1062 tokens,
Per-position acceptance rate: 0.802, 0.551, 0.415,
Avg Draft acceptance rate: 58.9%
```

with quieter windows reaching mean length 3.15 and per-position
`0.950 / 0.650 / 0.550` (avg 71.7%). Reading these:

- **Per-position acceptance declines with depth** — ~0.80 → 0.55 → 0.42 across
  the three drafted positions. Each deeper draft token is conditioned on the
  previous ones being accepted and is progressively harder to guess, so the third
  position is roughly a coin-flip's-worth of saved work.
- **Mean acceptance length ≈ 2.8–3.1** means one target forward pass emits ~2.8–3.1
  tokens instead of 1. That sets the **ideal** decode speedup at ≈ the mean
  acceptance length (~2.8×).
- **Realized vs ideal:** measured TPOT-any improves 2.4× (6.92 vs 16.55 ms/tok),
  i.e. ~85% of the ~2.8× ideal. The missing ~15% is the draft + verification
  overhead per step. The repeated decode-throughput gain (1.9×) is lower still,
  because tokens/s also carries the unaccelerated prefill/TTFT in its denominator.

This also answers the open item T6 previously deferred: acceptance **is**
quantified — ~59–72% single-stream here, versus T5's **0.493** under batched
SWE-bench load. Acceptance is *higher* on this short single-stream prompt than
under diverse concurrent load, which is the expected direction (harder, varied
continuations are harder to draft).

On `num_speculative_tokens`: we run 3 where the JarvisLabs study runs 2. The
third position's ~0.42 acceptance is low-yield — diminishing returns — so 2 vs 3
is a plausible tuning lever, but we did not A/B it here.

## What it costs

- **Wasted draft compute.** Of 1062 drafted tokens, 626 were accepted — ~41% of
  draft forward-compute is thrown away (and the 3rd-position rate of ~0.42 shows
  where). But this is the cheap resource: T5 showed decode leaves the compute
  units idle (memory-bound, ~180–240 W of 600 W), so the rejected drafts are paid
  out of headroom that was otherwise wasted. That is precisely why speculation is
  near-free on a model this large.
- **No first-token penalty.** TTFT-any is ≈204 ms in both arms; Eagle3 adds no
  measurable prefill cost.
- **Draft-model VRAM — measured (2026-06-08).** A dedicated Eagle3-ON startup
  capture closes the gap the 06-05 A/B left open. The ON loading summary reports
  **71.92 GiB/GPU** (`2026-06-08_w1_evidence_extra/t6_eagle/kimi_log_eagle3_on.txt:131`,
  *"Model loading took 71.92 GiB memory"*) against the OFF target baseline of
  **71.16 GiB/GPU** — so the Eagle3 draft adds **≈0.76 GiB/GPU of resident
  weights** at TP=8, about **1% of the target footprint** (consistent with
  EAGLE-3's <5%-param design point). Weight size is independent of
  `--max-num-seqs`, so this delta is clean even though the 06-08 capture ran the
  production `max_num_seqs=32` rather than the A/B's 1.
- **Why the draft is so cheap.** Its checkpoint is only **5.62 GiB on disk**
  (`:122`, vs the target's 554.30 GiB) and is itself TP-sharded across the 8 GPUs
  (5.62/8 ≈ 0.70 GiB/GPU, matching the 0.76 measured). vLLM further **shares the
  target's embedding table with the draft**, keeping only a separate `lm_head`
  (`:107–108`: *"Detected EAGLE model with embed_tokens identical to the target…
  Sharing target model embedding weights"*). That embedding reuse is the reason an
  EAGLE-3 head costs under a GiB per GPU instead of a full small model's worth.
  This also validates T1's TP-vs-DEP math — TP shards the 554.30 GiB checkpoint to
  71.16 GiB/GPU, against the failed DEP attempt's 88.44 GiB/GPU.
- **Second-order KV cost (not cleanly isolated).** Under the fixed
  `--gpu-memory-utilization 0.6` budget the extra draft weights come out of the KV
  pool: ON shows **9.44 GiB Available KV** / 141,504 tokens / 1.08× max concurrency
  at 131 k context (`:174,183`) versus OFF's 9.84 GiB. But the 06-08 ON capture also
  runs the production `max_num_seqs=32`, whose larger CUDA-graph capture (1.46 GiB)
  inflates the non-KV overhead relative to the A/B's `max_num_seqs=1`, so that
  ~0.40 GiB KV drop mixes the draft weights with a bigger graph pool. The clean,
  config-independent number to report is the **0.76 GiB/GPU weight delta**.

## What the numbers do NOT show

- **No correctness *check* was run.** Speculation is lossless on the accepted
  distribution by construction, and no errors or anomalies appeared, but no
  quality eval (accuracy, output comparison) was performed — so "no correctness
  change" is a theoretical guarantee plus the absence of observed problems, not a
  measured quality result.
- **One short prompt, no concurrency.** This is a sanity A/B on a 15-token prompt
  at `--max-num-seqs 1`. It says nothing directly about batched/concurrent
  serving or long-context prefill; the batched acceptance (0.493) comes from T5,
  and a full concurrency study remains follow-up.
- **The `--max-num-batched-tokens` impurity** (4096 ON vs 8192 OFF, above) means
  the A/B is clean only for this non-binding workload.

## Conclusion

Keep Eagle3 ON. On the W1 single-stream baseline it delivers a robust ~2× p50
TTFT and ~1.9× decode-throughput improvement at temperature 0, with no
first-token cost, ~59–72% draft acceptance (~2.8–3.1 tokens per target pass), and
a compute cost paid out of otherwise-idle GPU headroom. That justifies the extra
draft model and configuration complexity for the Phase 1 latency target, and it
matches the model-scale trend that makes EAGLE-3 the right family for a 1T-class
model. Its memory cost is now pinned at ≈0.76 GiB/GPU (~1% of the target), so the
draft model is effectively free on VRAM as well as compute. The claim is
deliberately scoped to single-stream; concurrent-serving behavior and
`num_speculative_tokens` tuning are the remaining follow-up work, not part of this
baseline.

## Evidence

Every figure above maps to a committed artifact (organized under commit
`d0bb634`; **use `run-05_eagle3-off-paired`, not `-rerun`** — the
end-of-session commit `fc97700` overwrote the OFF arm in place and the paired
5×5 generation was recovered from `ec3df59`).

| Claim | Source |
|---|---|
| Fair A/B config + the `max-num-batched-tokens` impurity | `results/runs/2026-06-05_w1_evidence/t6_eagle3/engine_cmd_eagle3_{on,off}.json` |
| Single-shot ON numbers (TTFT 652 ms, E2E 674 ms, 69 tok, 240 reasoning chars) | `results/runs/2026-06-05_kimi-k2-6_run-04_eagle3-on/singlestream_lite_latency/result.json` |
| Single-shot OFF numbers (TTFT 2489 ms, E2E 2536 ms, 142 tok, 546 reasoning chars) | `results/runs/2026-06-05_kimi-k2-6_run-05_eagle3-off-paired/singlestream_lite_latency/result.json` |
| Repeated ON p50/p95 (837/1694 ms, 111.6 tok/s, 97 tok p50) | `results/runs/2026-06-05_kimi-k2-6_run-04_eagle3-on/singlestream_lite_repeated/summary.json` |
| Repeated OFF p50/p95 (1675/4426 ms, 58.7 tok/s, 97 tok p50) | `results/runs/2026-06-05_kimi-k2-6_run-05_eagle3-off-paired/singlestream_lite_repeated/summary.json` |
| Acceptance economics (mean length 2.8–3.1, per-position 0.80/0.55/0.42, avg 59–72%, drafted 1062 / accepted 626) | `results/runs/2026-06-05_w1_evidence/t6_eagle3/kimi_log_eagle3_on.txt` (SpecDecoding metrics, 09:01 window) |
| Batched acceptance cross-check (0.493) | T5 `prometheus_summary.txt` |
| Target weight baseline (OFF: 71.16 GiB weights + 9.84 GiB KV @ TP=8, checkpoint 554.30 GiB) | `results/runs/2026-06-05_w1_evidence/t6_eagle3/kimi_log_eagle3_off.txt:92,95,134` |
| Draft-model VRAM (ON loading 71.92 GiB/GPU − OFF 71.16 = **0.76 GiB/GPU**; draft checkpoint 5.62 GiB, embedding shared with target; ON Available KV 9.44 GiB / 141,504 tok @ `max_num_seqs=32`) | `results/runs/2026-06-08_w1_evidence_extra/t6_eagle/kimi_log_eagle3_on.txt:107,122,131,174,183` |
| Client-side bench logs (run order, no errors) | `results/runs/2026-06-05_w1_evidence/t6_eagle3/bench_{on,off}.log` |
| Server startup config per arm | `results/runs/2026-06-05_w1_evidence/t6_eagle3/kimi_log_eagle3_{on,off}.txt` |
| Integrity / paired-vs-rerun provenance | `results/runs/2026-06-05_w1_evidence/session/session_notes.md` |

## Reference

JarvisLabs, *Speculative decoding in vLLM: faster LLM inference*
(https://jarvislabs.ai/blog/speculative-decoding-vllm-faster-llm-inference) —
method taxonomy and the model-scale/task benchmark trend used above. Methodology
reconciliation against these numbers is tracked in **#48** before the final
cross-thread W1 publication.
