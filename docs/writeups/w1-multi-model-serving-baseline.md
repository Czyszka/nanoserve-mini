# W1 — vLLM + LiteLLM Proxy on 8×H200: a multi-model serving baseline from zero to first measurement

> Status: modular draft. Thread working files live in `docs/writeups/w1/`.
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
| **T1** | How to bring up Kimi-K2 (~1T MoE) on a single 8×H200 node? DEP failed to start → TP=8 | investigation | placeholder; DEP failure evidence missing | [`w1/t1-kimi-bringup.md`](w1/t1-kimi-bringup.md) |
| **T2** | Why does `measure_ttft_once.py` return `TTFT: n/a`? → reasoning deltas → parser fix (#31) | investigation | done | [`w1/t2-reasoning-ttft.md`](w1/t2-reasoning-ttft.md) |
| **T3** | Why DeepSeek at 20% VRAM, not 25%/15%? | justification with numbers | partial; needs clean 0.15/0.20/0.25 sweep | [`w1/t3-deepseek-vram-budget.md`](w1/t3-deepseek-vram-budget.md) |
| **T4** | Why LiteLLM Proxy and not the alternatives? | justification + rejected alternatives | partial; rejected alternatives need deeper rationale | [`w1/t4-litellm-proxy.md`](w1/t4-litellm-proxy.md) |
| **T5** | What do vLLM metrics and GPU telemetry actually tell us? Useful vs misleading signals. | investigation/measurement | partial; dashboard validation under load still missing (#34) | [`w1/t5-observability.md`](w1/t5-observability.md) |
| **T6** | Why Eagle3 and what does it cost? SC on vs off. | justification + measurement | placeholder; ON/OFF benchmark missing | [`w1/t6-eagle3-speculative-decoding.md`](w1/t6-eagle3-speculative-decoding.md) |
| **T7** | Why runtime data lives in host directories, not Docker volumes? | justification | done | [`w1/t7-host-directories.md`](w1/t7-host-directories.md) |
| **T8** | Does LiteLLM Proxy add measurable overhead? | measurement | designed; full R1-R8 program intentionally deferred (#44) | [`w1/t8-litellm-overhead.md`](w1/t8-litellm-overhead.md) |

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

<!-- TODO: first run_bench_suite.py figures through LiteLLM (TTFT p50/p95,
TPOT, E2E, throughput) with full control snapshot; explicit limits —
single-stream, warmup=1, no concurrency sweep → sanity baseline, not a
performance claim. -->

---

## Evidence quality after 2026-05-27

| Thread | Status | Missing |
|---|---|---|
| T1 bring-up | placeholder | DEP failure evidence |
| T2 reasoning TTFT | done | - |
| T3 DeepSeek VRAM | partial | clean 0.15/0.20/0.25 sweep |
| T4 LiteLLM Proxy | partial | deeper rejected-alternatives rationale |
| T5 observability | partial | dashboard validation under load (#34) |
| T6 Eagle3 | placeholder | ON/OFF benchmark |
| T7 host directories | done | - |
| T8 proxy overhead | designed | full R1-R8 program (#44), intentionally deferred |
| INDEX | partial | baseline table TODO still empty |

The write-up intentionally distinguishes completed evidence from partial or
missing evidence. This avoids overclaiming and keeps W1 useful as an engineering
record, not just a success narrative.

## W1 close-out path A

This is the shortest path to close W1 without expanding scope.

**Done now**

- T2 is fully written.
- T7 is written as the host-directory justification.
- T8 is designed and counts as closed for now; the full R1-R8 program is tracked
  separately in #44.

**Next GPU slot**

- T1 DEP failure capture.
- T3 clean DeepSeek VRAM sweep at 0.15, 0.20, and 0.25.
- T6 Kimi Eagle3 ON/OFF benchmark.

The 2026-06-03 server-session plan is intended to cover this exact GPU block.
After the slot, the laptop work is to turn the new evidence into the T1/T3/T6
thread files.

**Laptop-only**

- Deepen the T4 LiteLLM Proxy justification and rejected alternatives.
- Fill the INDEX baseline table after evidence lands.
- Keep T5 to minimal dashboard validation for path A; the fuller dashboard work
  remains under #34.

**Intentionally deferred**

- Full T8 proxy-overhead program (#44).
- Full T5 dashboard validation (#34), beyond the minimal W1 check.

Conclusion: W1 still needs one server slot for T1/T3/T6 evidence and roughly a
half-day laptop pass for T4, the baseline table, and the post-evidence write-up
updates.

## Follow-up work

1. Re-run DeepSeek VRAM sweep with explicit `0.15`, `0.20`, and `0.25` caps and filenames matching runtime configuration.
2. Capture Kimi DEP startup failure evidence.
3. Run controlled Kimi Eagle3 ON/OFF benchmark.
4. Deepen the LiteLLM Proxy rejected-alternatives rationale.
5. Fill the baseline table once the missing evidence lands.
6. Validate Grafana dashboard panels under live load, minimally for W1 and more fully under #34.

---

## References

[1] X. Miao, G. Oliaro, Z. Zhang, X. Cheng, H. Jin, T. Chen, and Z. Jia,
"Towards Efficient Generative Large Language Model Serving: A Survey from
Algorithms to Systems," *ACM Computing Surveys*, 2025. arXiv:2312.15234.
Local note: `docs/learning/paper-notes/efficient-llm-serving-survey.md`.
