# T6 — Why Eagle3, and what it costs

Mode: justification + measurement.

## Question

Kimi-K2.6 is served with Eagle3 speculative decoding enabled. Does that
configuration earn its place in the Phase 1 baseline — and what, specifically,
does it buy on this 8×H200 node? The decision must rest on a controlled
ON/OFF comparison, not on the upstream model card's claims.

## Decision

Keep Eagle3 speculative decoding ON for Kimi-K2.6 in the Phase 1 baseline.
On a single-stream workload it roughly **halves p50 TTFT and doubles decode
throughput** at temperature 0, with no first-token penalty and no measured
correctness change. The benefit is real but bounded; the sections below state
exactly which number to trust and which not to.

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

The intended variable is `--speculative-config`. Honesty requires noting that
the ON arm **also** carries `--max-num-batched-tokens 4096`, which the OFF arm
does not — so the A/B is not single-variable. For this specific workload the
extra flag does not bind: with a 15-token prompt and `--max-num-seqs 1`, prefill
never approaches the batched-token cap, so the measured difference is
attributable to speculation. The confound would matter under concurrency or long
prompts; it is flagged here so a later concurrency study does not inherit a
hidden assumption.

## Measurement

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
run-to-run (completion tokens ranged 94–190 ON, 97–285 OFF). Speculative
decoding is lossless on the *accepted* token distribution, but the observed
length variance means single-shot latency is not a stable comparison unit here.

## What the numbers do NOT show

- **No first-token benefit.** TTFT-any-token is ≈204 ms in both arms. Eagle3
  accelerates the decode loop, not prefill — exactly as expected for speculative
  decoding. The 3.8× "TTFT content" gain is really a *time-to-final-answer* gain
  driven by faster reasoning-trace decode, not a faster first token.
- **Acceptance rate not quantified here.** This client-side single-stream
  capture does not record Eagle3 draft-acceptance length. The `spec_decode_*`
  Prometheus metrics (present only under ON, per the T5 inventory) are the right
  source for that and are left to T5 / #34.
- **One short prompt, no concurrency.** This is a sanity A/B on a 15-token
  prompt at `--max-num-seqs 1`. It says nothing about batched/concurrent serving,
  long-context prefill, or acceptance under realistic workloads.
- **Memory/compute cost not isolated.** Eagle3 loads a draft model and adds
  verification compute; this run does not bound that overhead (server-metric
  fields were null in the capture).

## Conclusion

Keep Eagle3 ON. On the W1 single-stream baseline it delivers a robust ~2× p50
TTFT and ~1.9× decode-throughput improvement at temperature 0 with no first-token
cost and no correctness change, which justifies the extra draft model and
configuration complexity for the Phase 1 latency target. The claim is
deliberately scoped to single-stream; concurrent-serving behavior and
draft-acceptance economics are follow-up work, not part of this baseline.

## Evidence

Every figure above maps to a committed artifact (organized under commit
`d0bb634`; **use `run-05_eagle3-off-paired`, not `-rerun`** — the
end-of-session commit `fc97700` overwrote the OFF arm in place and the paired
5×5 generation was recovered from `ec3df59`).

| Claim | Source |
|---|---|
| Fair A/B config + the `max-num-batched-tokens` impurity | `results/runs/2026-06-05_w1_evidence/t6_eagle3/engine_cmd_eagle3_{on,off}.json` |
| Single-shot ON numbers (TTFT 652 ms, E2E 674 ms, 69 tok) | `results/runs/2026-06-05_kimi-k2-6_run-04_eagle3-on/singlestream_lite_latency/result.json` |
| Single-shot OFF numbers (TTFT 2489 ms, E2E 2536 ms, 142 tok) | `results/runs/2026-06-05_kimi-k2-6_run-05_eagle3-off-paired/singlestream_lite_latency/result.json` |
| Repeated ON p50/p95 (837/1694 ms, 111.6 tok/s, 97 tok p50) | `results/runs/2026-06-05_kimi-k2-6_run-04_eagle3-on/singlestream_lite_repeated/summary.json` |
| Repeated OFF p50/p95 (1675/4426 ms, 58.7 tok/s, 97 tok p50) | `results/runs/2026-06-05_kimi-k2-6_run-05_eagle3-off-paired/singlestream_lite_repeated/summary.json` |
| Client-side bench logs (run order, no errors) | `results/runs/2026-06-05_w1_evidence/t6_eagle3/bench_{on,off}.log` |
| Server startup config per arm | `results/runs/2026-06-05_w1_evidence/t6_eagle3/kimi_log_eagle3_{on,off}.txt` |
| Integrity / paired-vs-rerun provenance | `results/runs/2026-06-05_w1_evidence/session/session_notes.md` |

Methodology note (#48, JarvisLabs speculative-decoding article) should be
reconciled against these numbers before the final cross-thread W1 publication.
