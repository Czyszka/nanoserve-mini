# W1 — vLLM + LiteLLM Proxy on 8×H200: a multi-model serving baseline from zero to first measurement

> Status: all eight threads written from committed 2026-06-05 evidence
> (commit `d0bb634`); modular form retained (index + `docs/writeups/w1/`).
> Methodology and the cross-write-up writing guide live in issue #37.

## Framing

The backbone of this write-up is a **bring-up**: the path from an empty
8×H200 node to a multi-model serving stack (vLLM + LiteLLM Proxy) that
returns a first benchmark number. The subject, however, is not the stack
itself. It is **trust in the first measurement** — how much work is
required before the first TTFT/E2E figure means anything at all.

The measurement philosophy in this write-up is explicitly anchored in the
LLM serving taxonomy from Miao et al. [1]. I use the survey as a taxonomy,
not as numeric evidence: it frames LLM serving performance as an
interaction between request scheduling, prefill/decode dynamics, KV-cache
memory management, batching policy, workload shape, network/API path, and
GPU hardware behavior. W1 follows that taxonomy to decide which controls
and metrics must be captured before a first TTFT/E2E number can be
trusted. The local reading note for the paper is
`docs/learning/paper-notes/efficient-llm-serving-survey.md`.

The narrative is assembled from eight threads. During drafting, each
thread has its own working file under `docs/writeups/w1/`. The top-level
file is the publication draft / index: framing, thread map, links,
baseline caveats, and references.

Each thread is written in one mode:

- **śledztwo** (investigation) — symptom → hypothesis → evidence → redirect → source;
- **uzasadnienie** (justification) — decision ← because ← because ← evidence, anchored by a named rejected alternative;
- **pomiar** (measurement) — question → data → pattern, with baseline, controls, and an explicit statement of what the number does *not* show.

## Thread map

| Thread | Initial problem | Mode | Evidence status | Working file |
|---|---|---|---|---|
| **T1** | How to bring up Kimi-K2 (~1T MoE) on a single 8×H200 node? DEP failed to start → TP=8 | investigation | done — DEP negative-KV crash captured | [`w1/t1-kimi-bringup.md`](w1/t1-kimi-bringup.md) |
| **T2** | Why does `measure_ttft_once.py` return `TTFT: n/a`? → reasoning deltas → parser fix (#31) | investigation | done | [`w1/t2-reasoning-ttft.md`](w1/t2-reasoning-ttft.md) |
| **T3** | Why DeepSeek at 20% VRAM, not 25%/15%? | justification with numbers | done — clean 0.15/0.20/0.25 sweep | [`w1/t3-deepseek-vram-budget.md`](w1/t3-deepseek-vram-budget.md) |
| **T4** | Why LiteLLM Proxy and not the alternatives? | justification + rejected alternatives | done | [`w1/t4-litellm-proxy.md`](w1/t4-litellm-proxy.md) |
| **T5** | What do vLLM metrics and GPU telemetry actually tell us? Useful vs misleading signals. | investigation/measurement | done for W1 — validated under load; fuller panels under #34 | [`w1/t5-observability.md`](w1/t5-observability.md) |
| **T6** | Why Eagle3 and what does it cost? SC on vs off. | justification + measurement | done — paired ON/OFF A/B | [`w1/t6-eagle3-speculative-decoding.md`](w1/t6-eagle3-speculative-decoding.md) |
| **T7** | Why runtime data lives in host directories, not Docker volumes? | justification | done | [`w1/t7-host-directories.md`](w1/t7-host-directories.md) |
| **T8** | Does LiteLLM Proxy add measurable overhead? | measurement | designed; full R1-R8 program intentionally deferred (#44) | [`w1/t8-litellm-overhead.md`](w1/t8-litellm-overhead.md) |
| **T9** | What actually limits decode (HBM-bound refuted) — and would NVLink 4-way bridges pay off, for which TP? | investigation + decision analysis | **in progress** — comms-bound is the surviving L1; closing session planned (#50) | [`w1/t9-bottleneck-nvlink.md`](w1/t9-bottleneck-nvlink.md) |

---

## Working thread files

The current source-of-truth for thread drafting is:

- [`w1/t1-kimi-bringup.md`](w1/t1-kimi-bringup.md)
- [`w1/t2-reasoning-ttft.md`](w1/t2-reasoning-ttft.md)
- [`w1/t3-deepseek-vram-budget.md`](w1/t3-deepseek-vram-budget.md)
- [`w1/t4-litellm-proxy.md`](w1/t4-litellm-proxy.md)
- [`w1/t5-observability.md`](w1/t5-observability.md)
- [`w1/t6-eagle3-speculative-decoding.md`](w1/t6-eagle3-speculative-decoding.md)
- [`w1/t7-host-directories.md`](w1/t7-host-directories.md)
- [`w1/t8-litellm-overhead.md`](w1/t8-litellm-overhead.md)
- [`w1/t9-bottleneck-nvlink.md`](w1/t9-bottleneck-nvlink.md) *(in progress)*

The final W1 publication draft should later inline or summarize these
threads once the server-side evidence is complete.

---

## Baseline table and what the numbers do NOT mean

Following Miao et al. [1], this final baseline section should report
controls next to the numbers: serving results are hard to compare unless
model configuration, hardware, workload shape, scheduling policy,
network/API path, and generated output length are controlled. For that
reason, W1 should treat the first single-stream runs as a sanity baseline,
not as a general throughput claim.

**Baseline is measured direct, not through the proxy.** T4/T8 show LiteLLM
`main-v1.66.0-stable` strips Kimi `delta.reasoning`, so the proxy path cannot
serve as the reasoning-model baseline. The W1 sanity baseline is therefore
single-stream **direct vLLM**, `run_bench_suite` `singlestream_lite_repeated`
(warmup 1 + measured runs, `temperature 0`, `max_num_seqs 1`):

| Model (direct, single-stream repeated) | TTFT p50 | TTFT p95 | E2E p50 | tok/s | completion p50 |
|---|---:|---:|---:|---:|---:|
| Kimi-K2.6, Eagle3 ON `:8000` (production config) | 837 ms | 1694 ms | 857 ms | 111.6 | 97 tok |
| Kimi-K2.6, Eagle3 OFF `:8000` (control) | 1675 ms | 4426 ms | 1724 ms | 58.7 | 97 tok |
| DeepSeek-V4-Flash `:8004` (cap 0.20) | 1.26 s | 1.58 s | 1.93 s | n/a | 3 tok |

What these numbers do **not** mean:

- **Not a throughput claim.** Single-stream, `max_num_seqs 1`, one short prompt.
  The batched picture (queueing, 327 tok/s, scheduler-limited TTFT) is T5, not
  this table.
- **DeepSeek tok/s is omitted on purpose.** Its smoke output is ~3 tokens, so a
  rate would be an artifact, not a serving result; a real generation workload is
  owed (T8 R7 / #44).
- **Kimi single-shot ratios are length-sensitive.** At `temperature 0` the arms
  still vary in generated length; the table uses repeated p50 (equal 97-tok
  median) — the robust unit — not single-shot E2E (which T6 reports as a
  2.1×–3.8× band).
- **One node, one driver.** vLLM v0.20-series, CUDA 13.2, driver 595.58.03,
  8×H200 NVL 143 GB.

## Cross-cutting finding: the first wall is KV-cache budget

Two independent bring-up failures (T1 and T3) are the **same failure**, which is
the strongest baseline lesson in W1: serving does not fail when the weights do
not fit — it fails when nothing is left for the KV cache. vLLM reports a
**negative `Available KV cache memory`** and the engine core exits before
serving a single token:

| Thread | Configuration | Available KV cache | Outcome |
|---|---|---:|---|
| T1 | Kimi DP=8 + EP, gpu-mem 0.6 | **−19.08 GiB** | `EngineCore failed to start` |
| T3 | DeepSeek cap 0.15 (co-resident) | **−0.49 GiB** | `EngineCore failed to start` |

This is exactly the KV-cache memory-management layer Miao et al. [1] place at the
center of serving performance: before any TTFT/E2E number exists, the
parallelism strategy (T1) and the co-residency budget (T3) must each leave a
positive KV budget. Both threads are, at root, the same arithmetic.

---

## Evidence quality after 2026-06-05

| Thread | Status | Source / remaining |
|---|---|---|
| T1 bring-up | done | DEP negative-KV crash captured (`t1_dep/`) |
| T2 reasoning TTFT | done | parser #31 + 2026-05-27 paired set |
| T3 DeepSeek VRAM | done | clean 0.15/0.20/0.25 sweep (`t3_deepseek_vram/`) |
| T4 LiteLLM Proxy | done | + reasoning-strip limit wired in |
| T5 observability | done for W1 | validated under load; fuller panels under #34 |
| T6 Eagle3 | done | paired ON/OFF A/B (`run-04` vs `run-05_…-paired`) |
| T7 host directories | done | - |
| T8 proxy overhead | done for W1 | strip proven twice; R1 hop attribution measured 2026-06-10 (~37 ms c=1); R2–R8 deferred (#44) |
| T9 bottleneck + NVLink | **in progress** | HBM-bound refuted (2026-06-10 counters); Qwen TP lever analyzed; closing session + calibration pending (#50) |
| INDEX | done | baseline table + KV-budget synthesis filled |

Every thread now carries a per-file `## Evidence` block mapping each headline
number to its artifact path, run-id, and the organizing commit `d0bb634`
(with the T6 paired-vs-rerun integrity note). The write-up still distinguishes
done-for-W1 from intentionally deferred (#34 fuller panels, #44 proxy program);
this avoids overclaiming and keeps W1 an engineering record, not a success
narrative.

## W1 close-out — complete

All eight threads are written from committed evidence; the baseline table and
the KV-budget synthesis are filled. The 2026-06-05 server slot supplied the
last missing captures (T1 DEP, T3 sweep, T6 paired A/B) and the T5 batched-load
validation; the laptop pass turned them into thread files with `## Evidence`
provenance. No further GPU slot is required to publish W1.

**Intentionally deferred (out of W1 scope, not blocking):**

- Full T8 proxy-overhead program R1–R8 (#44) — concurrency sweep, hop
  attribution, workload matrix.
- Fuller T5 dashboard hardening (#34) — DCGM/GPU hardware panels, LiteLLM
  exporter 404 fix, L2 controlled counterfactuals.

## Follow-up work (post-W1)

1. T8 R1–R8 proxy-overhead program under concurrency (#44).
2. T5 DCGM/GPU-hardware panels and L2 causal checks under load (#34).
3. Reconcile T6 against the #48 speculative-decoding methodology article before
   any cross-thread synthesis publication.
4. DeepSeek real-generation workload so a throughput baseline becomes meaningful
   (currently ~3-token smoke only).
5. T9 close-out: decode-bottleneck attribution at L2 + the calibrated NVLink
   4-way decision table (#50; session plan
   `docs/plans/2026-06-10-bottleneck-followup-session.md`).

---

## References

[1] X. Miao, G. Oliaro, Z. Zhang, X. Cheng, H. Jin, T. Chen, and Z. Jia,
"Towards Efficient Generative Large Language Model Serving: A Survey from
Algorithms to Systems," *ACM Computing Surveys*, 2025. arXiv:2312.15234.
Local note: `docs/learning/paper-notes/efficient-llm-serving-survey.md`.
