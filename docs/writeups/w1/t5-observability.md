# T5 — Reading serving bottlenecks from vLLM metrics and GPU telemetry

> Working thesis: the dashboard should not answer "what metrics exist?".
> It should answer "where is the request spending time, and which layer is
> currently limiting serving: client/proxy, scheduler, prefill, decode,
> KV cache, or hardware?"

## Question

A raw `/metrics` dump is not an observability result. Which vLLM metrics
and hardware telemetry signals are decision-useful for Phase 1, which
ones are only diagnostics, and how should the useful ones be read
together with client-side timing?

The title deliberately goes beyond vLLM `/metrics`. vLLM exposes the
serving-engine view: queueing, token rates, request latency, KV cache,
and request outcomes. It does not expose the full hardware state of the
8×H200 node. GPU utilization, VRAM, power, and temperature need DCGM
Exporter or `nvidia-smi`. In W1 the hardware layer was observed only informally
(`nvidia-smi` watched live, not logged); DCGM-based capture remains planned under
#34 — see the load result below.

## Result: dashboard validated under load (2026-06-05)

The dashboard is now validated against live load, which closes T5 for W1
(fuller panel hardening continues under #34). Two things were established.

**Metric names are real.** All Phase 1 dashboard panels resolve against the
live 2026-06-05 `/metrics` dumps (`t5_metrics/full-load/vllm_kimi_metrics.txt`,
`…/vllm_small_metrics.txt`): every query maps to an actual vLLM v0.20.0 series
(label `model_name`), and `spec_decode_*` appears only under Kimi with Eagle3
ON. No dashboard JSON fix was needed. The repeatable procedure is in
`serving/runbooks/load-test-and-grafana.md` (offline SWE-bench Lite workload;
needs `HF_HUB_OFFLINE=1`, `--trust-remote-code`).

**Panels fill under real load.** A batched run (`--max-num-seqs 32`, 3 h
window, `prometheus_summary.txt`) drove the node hard enough to populate the
queue/latency/KV panels that single-stream benches leave flat:

| Signal (batched, max-num-seqs 32) | Peak / value |
|---|---|
| requests running (kimi) | 32 |
| requests waiting (kimi) | 45 |
| generation throughput | 327 tok/s |
| prompt throughput | 1039 tok/s |
| KV cache usage | 44% peak |
| TTFT p50 / p95 | 11.2 s / 59.7 s |
| E2E p50 / p95 | 45.6 s / 90.8 s |
| ITL p50 | 0.106 s |
| Eagle3 draft acceptance | 0.493 |
| preemptions | 0 |

All values are from `prometheus_summary.txt` (3 h Prometheus window). The gauge
peaks — running, waiting, KV, throughput, acceptance, preemptions — are the
`kimi-k2.6` series; the TTFT/E2E/ITL percentiles are over **all** requests in the
window (`all` in that file), so they are not strictly Kimi-only.

Read with the correlation playbook below (still **L0/L1** — one window, no
controlled counterfactual):

- **Scheduler-limited, not KV-limited.** waiting (45) exceeds running (32) while
  KV usage peaks at only 44% and preemptions are 0 — the queue forms from
  concurrency/scheduling capacity (the `max-num-seqs 32` admission cap), not KV
  exhaustion or eviction thrash. A *preemption* is vLLM evicting an already-
  running request when the KV-block pool cannot grow it further, then recomputing
  its KV on reschedule; KV exhaustion would therefore show KV → ~100% with
  preemptions > 0, which is not what we see. TTFT p50 rises to 11.2 s (vs ~0.84 s
  single-stream in T6), consistent with requests sitting in the WAITING phase
  before execution — the "vLLM TTFT high + waiting high" row of the playbook.
  This stays an **L1 diagnostic**: `vllm:request_queue_time_seconds` is
  instrumented but its per-window percentile was not captured in this run (the
  only committed scrape of it, `full-load/vllm_kimi_metrics.txt`, is near-idle —
  15 requests, 0.6 ms total), so the attribution rests on the waiting>running
  gauge, not a measured queue-time breakdown.
- **Eagle3 acceptance is now quantified.** `spec acceptance = 0.493` answers the
  open item flagged in T6: under this batched workload the draft model's tokens
  are accepted ~49% of the time. T6 measured the latency benefit but not
  acceptance; this is the missing number, from the same `spec_decode_*` family.
- **Hardware layer — observed informally, not dashboarded.** During the batched
  run `nvidia-smi` (watched live in a terminal, not logged) showed 100% GPU-Util
  while board power held at only ~180–240 W of the 600 W per-GPU limit. That is
  the memory-bound decode signature: the SMs report busy, but the card is far
  from its power/compute ceiling because decode is bottlenecked on HBM bandwidth,
  not FLOPs — and it is invisible to vLLM `/metrics`, which reports engine state,
  not silicon state. DCGM Exporter was deliberately left out of W1 to keep Phase 1
  scoped (another brick, and no time in this slot); proper hardware telemetry
  (power, SM/DRAM activity, VRAM) is considered necessary going forward and is
  tracked under #34.

The two captured screenshots contrast the regimes:
`2026-06-05_grafana_dashboard-max_num_seqs_1.png` (single-stream — queue panels
flat) and `…max_num_seqs_32.png` (batched — queue/throughput/KV panels live).

**Scope decision.** This is sufficient observability evidence for W1: metric
names validated, panels demonstrably fill under load, and the readings are
labelled diagnostic (L0/L1), not causal. Fuller hardening — DCGM/GPU hardware
panels, the LiteLLM exporter 404 fix, and L2 controlled counterfactuals —
remains under #34, not a W1 blocker.

## Inventory: availability is not evidence

Use `results/raw/observability/vllm-metrics.txt` as a metric availability
snapshot, not as a benchmark result. The dump proves that the endpoint
exposes counters, gauges, and histograms, but an idle or near-idle
snapshot mostly proves instrumentation coverage. It does not prove
throughput, saturation, queueing behavior, or hardware utilization.

Following Miao et al. [1], T5 uses the survey as a taxonomy of serving
layers that must be observable before a benchmark number is meaningful.
The raw `/metrics` dump is therefore treated as layer discovery, not as
performance evidence.

Planned evidence to include:

- raw vLLM `/metrics` dump from `results/raw/observability/`,
- current Grafana dashboard queries from `serving/compose/grafana/`,
- issue #34 notes on metric selection and DCGM Exporter,
- later server-session screenshot or captured dashboard window under load.

## Mechanism: request lifecycle and metric boundaries

A metric is only useful when its clock boundaries are clear. The most
common observability mistake is to compare two metrics with the same name
but different start and stop points. T5 therefore treats every metric as
a measurement over a specific segment of the request lifecycle, not as a
standalone truth.

```text
benchmark client starts timer
  -> HTTP request leaves benchmark client
  -> LiteLLM Proxy receives and routes the request
  -> vLLM OpenAI-compatible server accepts the request
  -> request enters the scheduler queue
  -> prefill processes prompt tokens and builds / extends KV cache
  -> first decode step produces the first generated token
  -> following decode steps produce additional output tokens
  -> vLLM serializes response or SSE stream chunks
  -> LiteLLM Proxy forwards the response stream
  -> client receives the first observable delta
  -> client receives the final chunk / response end
```

| Lifecycle segment | Metric | What it measures |
|---|---|---|
| client start → first client-observed output | client TTFT (`ttft_seconds` / `ttft_any_token_seconds`) | User/client-observed first output latency, including proxy, network, serialization, client parser, and the chosen content-vs-reasoning definition. |
| vLLM request accepted → first generated token | `vllm:time_to_first_token_seconds` | Server-side first-token latency inside the vLLM serving path. |
| waiting before model execution | `vllm:request_queue_time_seconds` | Scheduler/capacity delay before the request can run. |
| prompt/context processing | `vllm:prompt_tokens_total`, request prompt-token histograms | Prefill volume and rate. |
| decode loop | `vllm:inter_token_latency_seconds`, `vllm:generation_tokens_total` | Next-token cadence and generation throughput. |
| full vLLM request lifetime | `vllm:e2e_request_latency_seconds` | Server-side request lifetime as seen by vLLM. |
| client start → response end | `measure_ttft_once.py` `metrics.e2e_seconds` (streaming), `request_once.py` `metrics.e2e_seconds` (non-streaming), `run_sequential_benchmark.py` rows/summary | User/client-observed end-to-end latency through the configured `base_url`; includes LiteLLM Proxy and transport only when the benchmark points at the proxy. |
| KV allocation pressure | `vllm:kv_cache_usage_perc` | Fraction of vLLM KV-cache capacity currently in use. |
| repeated-prefix reuse | `vllm:prefix_cache_hits_total` / `vllm:prefix_cache_queries_total` | Whether prompt tokens are being served from prefix cache rather than recomputed. |
| physical GPU state | DCGM / `nvidia-smi` GPU util, VRAM, power, temperature | Whether the hardware layer is underloaded, saturated, memory-constrained, or thermally/power constrained. |

The client E2E row is already measured by project scripts, not merely
planned. `measure_ttft_once.py` records streaming E2E for a single request,
`request_once.py` records non-streaming E2E for a single request, and
`run_sequential_benchmark.py` records repeated streaming E2E rows and a
summary distribution. The important nuance is the `base_url`: a run
against LiteLLM Proxy measures proxy-path E2E; a run pointed directly at a
vLLM port measures direct-to-vLLM E2E.

## Why these are P0 metrics

The P0 set is selected by diagnostic coverage, not by metric availability.
This criterion follows the systems decomposition in Miao et al. [1]:
serving behavior is shaped by the interaction between scheduling,
prefill/decode dynamics, KV-cache memory management, batching behavior,
workload shape, API/network path, and GPU hardware utilization. The point
is to keep only the signals needed to localize where a request is
spending time or where serving is currently constrained.

```text
client / proxy timing
  -> vLLM request admission and scheduler
  -> prefill token processing
  -> decode token processing
  -> KV cache capacity and prefix reuse
  -> request termination reason
  -> GPU hardware state
```

## Metric semantics

| Group | Metrics | Question answered | Why it is P0 |
|---|---|---|---|
| Latency | TTFT, ITL/TPOT, E2E latency | Where does user-visible time appear? | Latency is the first thing users notice, but each latency metric maps to a different part of the request lifecycle. |
| Token pipeline | prompt tokens/s, generation tokens/s | Is work dominated by prefill or decode? | Prefill and decode stress the system differently; separating them prevents a single throughput number from hiding the bottleneck. |
| Scheduler | running requests, waiting requests, queue time | Is the engine executing or queueing? | Queueing turns model speed into user-visible delay and shows when demand exceeds immediately schedulable capacity. |
| KV/cache | KV usage %, prefix cache hits/queries | Is cache capacity or reuse affecting behavior? | KV pressure can limit scheduling, while prefix reuse can reduce prefill work; both are central to later cache experiments. |
| Outcomes | success by `finished_reason` | Are requests stopping, length-capping, aborting, or erroring? | Latency and throughput are not interpretable if many requests end by `length`, `abort`, or `error`. |
| Hardware | GPU util, VRAM, power, temperature | Is the physical node underloaded, saturated, memory-constrained, or thermally/power constrained? | vLLM metrics describe the engine, not the physical limiters of the 8×H200 node. |

## Correlation playbook

This table is a diagnostic map, not a causal proof. Each pattern should be
read as an operational hypothesis that needs a controlled check before it
becomes a performance conclusion.

| Pattern to explain | Likely interpretation | Why it matters |
|---|---|---|
| client TTFT high, vLLM TTFT normal | overhead or definition mismatch outside vLLM: LiteLLM, network, SSE/client timing, or reasoning-vs-content TTFT | Prevents blaming the engine when the delay is introduced after vLLM or by a different TTFT definition. |
| vLLM TTFT high, queue time high, waiting requests high | scheduler/capacity queueing before execution | Shows that first-token delay is caused before model execution, so tuning decode alone will not fix it. |
| vLLM TTFT high, queue time low, prompt length high | prefill/context processing dominates first token | Points investigation toward input length, prompt tokenization, and prefill throughput rather than scheduler backlog. |
| ITL/TPOT high, generation tokens/s low, GPU util high | decode path is expensive or saturated | Indicates that each next-token step is costly and the GPU is likely doing real decode work. |
| ITL/TPOT high, GPU util low | possible scheduler, CPU/proxy, client, or batching bottleneck rather than raw GPU saturation | Avoids misdiagnosing poor streaming cadence as GPU saturation when hardware is not busy. |
| E2E high, TTFT normal, ITL normal, output tokens high | long completion, not necessarily slow serving | Separates a long answer from a slow server; the fix may be workload/output cap, not engine tuning. |
| generation tokens/s plateaus while ITL or queue time rises | saturation knee under offered load | Marks the point where extra load no longer buys throughput and starts buying latency. |
| KV usage rising with waiting requests | possible KV-capacity scheduling constraint | Connects memory pressure to scheduling behavior; useful for deciding whether context length or concurrency is the limiter. |
| prefix hit rate rising while prefill/TTFT falls on repeated-prefix workload | prefix cache likely helps | Gives a causal check that cache hits are translating into reduced prefill cost, not just appearing as a counter. |
| GPU util low, waiting zero, running low | benchmark is underloading the server | Prevents drawing capacity conclusions from a workload that never stressed the node. |
| GPU util high, power high, temperature stable | hardware is genuinely loaded and behaving normally | Confirms that observed throughput/latency is measured under real hardware load without obvious thermal instability. |

Avoid hard thresholds until a per-model, per-workload baseline exists.
Prefer relative language: sustained rise, step change after load starts,
divergence between client-side and server-side timing, plateau under
increasing offered load.

## Inference protocol: from metric pattern to supported conclusion

T5 is an observability framework. It helps form diagnostic hypotheses, but
metrics alone do not prove causality. A causal claim requires a controlled
change, a prediction about how the relevant metrics should move, and an
explicit support or rejection criterion.

| Level | Name | Meaning |
|---|---|---|
| L0 | Observation | A metric trend or value was observed, without causal interpretation. |
| L1 | Diagnostic hypothesis | The most likely interpretation given the request lifecycle and correlated metrics. |
| L2 | Supported causal claim | The hypothesis survived a controlled counterfactual test. |
| L3 | Robust claim | The result repeated across at least two workloads, windows, or configurations. |

For an L2 claim, the minimum evidence bundle should include:

- same model and server configuration,
- fixed endpoint path: direct vLLM or LiteLLM Proxy,
- fixed prompt-length distribution,
- fixed `max_tokens`, temperature, and sampling parameters,
- fixed concurrency profile,
- fixed Prometheus / telemetry sampling window,
- one changed lever at a time,
- client timings, vLLM metrics, and GPU telemetry from the same time window.

The practical transition is:

```text
observed metric pattern
  -> mechanistic hypothesis
  -> controlled counterfactual change
  -> predicted metric movement
  -> support / rejection criterion
```

Examples:

| Pattern | Hypothesis | Disambiguation test | Support criterion |
|---|---|---|---|
| TTFT high + queue time high + waiting requests high | scheduler queueing dominates first-token delay | lower concurrency while keeping prompt/output distribution fixed | waiting/queue_time fall and TTFT falls; ITL does not need to change materially |
| TTFT high + queue time low + long prompts | prefill dominates first-token delay | reduce prompt length with the same model/output cap/concurrency | prompt tokens fall and TTFT falls while queue_time remains low |
| ITL high + GPU util high | decode path is expensive or saturated | reduce decode pressure by lowering concurrency or output length | ITL improves and GPU util/power fall in the same window |
| client TTFT high + vLLM TTFT normal | overhead or timing-definition mismatch outside vLLM | compare direct vLLM vs LiteLLM Proxy with the same prompt/config | proxy-path client TTFT is higher while vLLM TTFT remains similar |
| prefix hit rate rises while prefill/TTFT falls | prefix cache likely reduces prefill work | compare repeated-prefix workload against non-shared-prefix workload | prefix hits increase and prompt-processing latency/TTFT falls only in the repeated-prefix condition |

## Applied analysis: the 2026-06-05 capture through the playbook

The sections above are the framework; this is it applied to the one batched
capture we have (`prometheus_summary.txt`, `max-num-seqs 32`). It is a single
window with no isolated lever, so every reading below is **L0/L1** — diagnostic,
not causal.

| Observed (batched, max-num-seqs 32) | Playbook row matched | Reading | Level |
|---|---|---|---|
| TTFT p50 11.2 s; waiting 45 > running 32; KV 44%; preemptions 0 | "vLLM TTFT high + queue/waiting high", and the *negation* of "KV usage rising with waiting" | first-token delay forms in the WAITING phase from the `max-num-seqs 32` admission cap, not KV exhaustion | L1 |
| prompt 1039 tok/s vs generation 327 tok/s | Token pipeline (prefill vs decode) | prefill moves ~3× the token rate of decode — expected (prefill is parallel over prompt tokens, decode is sequential); the node's decode ceiling here is ~327 tok/s aggregate | L0 |
| ITL p50 0.106 s across 32 streams | self-consistency check | 32 × 1/0.106 ≈ 302 tok/s ≈ the 327 tok/s aggregate (gap within p50-vs-mean and spec-decode bursting) — the gauge and the histogram corroborate each other | L0 |
| ITL p50 0.106 s vs T6 single-stream TPOT 6.9 ms | "ITL/TPOT high under load" | per-token latency ~15× higher under batch-32 than single-stream — the concurrency throughput-vs-latency trade-off | L1 (confounded) |
| spec acceptance 0.493 | spec-decode family | Eagle3 drafts accepted ~49% under this batched workload (closes T6's open item) | L0 |
| nvidia-smi 100% util, ~180–240 W / 600 W | "ITL/TPOT high + GPU util high" | decode path is busy but the card is far from its power ceiling — memory-bound *or* TP-comms-bound; util% alone cannot tell them apart | L1 (ambiguous; → #34) |

**What the capture supports.** Exactly one L1 diagnosis, taken jointly: beyond
the `max-num-seqs 32` admission cap the node is **scheduler-concurrency-bound,
not KV-bound**, and first-token latency is queue-dominated. The waiting>running
gauge, KV at only 44%, and preemptions 0 all point the same way; KV exhaustion
would instead have shown KV → ~100% with preemptions > 0.

**What it does not support.** No L2/L3 claim. This is one window at one offered
load with no isolated counterfactual: concurrency, prompt mix, and output length
were not varied one lever at a time. Two readings are explicitly weaker than they
look: the ITL-vs-single-stream row is **confounded** (T6 used a 15-token prompt,
this run used SWE-bench Lite, so prompt length and content differ, not just
concurrency), and the single-stream T6 point (TTFT ~0.84 s, no queue) is only
*consistent with* the scheduler-bound reading, not a clean one-lever test.
Promoting any of these to L2 needs the disambiguation tests in the
inference-protocol table — above all a concurrency sweep at fixed prompt/output
distribution, and (for the hardware row) the DCGM-based HBM-vs-comms study in #34.

## Threats to validity

The correlation playbook can overlead if workload and measurement windows
are not controlled. The largest confounders for T5 are prompt length,
output length, sampling parameters, endpoint path, concurrency profile,
server warmup state, batching/scheduler state, CPU/proxy overhead,
telemetry sampling granularity, and whether client metrics and vLLM/GPU
metrics were captured over the same time window.

Therefore, T5 should distinguish language carefully:

- **evidence-backed finding** — directly observed in captured artifacts;
- **diagnostic hypothesis** — likely interpretation of a metric pattern;
- **supported causal claim** — hypothesis that passed a controlled
  counterfactual test;
- **robust claim** — supported causal claim repeated across multiple
  workloads or windows.

## Helper alignment (resolved)

The server-metrics helper was checked against the live dump and already uses the
current names. `benchmarks/scripts/_server_metrics.py` reads KV usage from
`vllm:kv_cache_usage_perc` (the older `vllm:gpu_cache_usage_perc` is kept only as
a version fallback) and computes the prefix-cache hit rate from
`vllm:prefix_cache_hits_total / vllm:prefix_cache_queries_total` — v0.20.0 exposes
no ready-made hit-rate gauge, so it is derived from the counters. No code change
was needed; the module documents these names as verified against the v0.20.0 dump.
For live dashboards the same hit rate is best read with a Prometheus `rate()` over
the two counters, or a pre/post snapshot delta in run summaries.

## Decision for W1

For W1, use a small P0 observability contract instead of presenting the
entire `/metrics` surface. The write-up should focus on latency, token
rates, scheduler pressure, KV/cache behavior, request outcomes, and GPU
hardware telemetry. Process/Python metrics, `*_created` gauges,
idle zero-value histograms, speculative-decoding counters before T6, and
miscellaneous cache namespaces should stay secondary diagnostics.

## Conclusions: which vLLM knobs would raise compute utilization here

The capture's hardware reading — 100% util at only ~180–240 W / 600 W — is the
memory-bound decode signature: each decode step reads the whole layer's weights
from HBM but does little compute per byte, so *arithmetic intensity* is low and
the tensor cores idle while the memory system works. You do not make decode
compute-bound; you raise useful FLOPs per HBM byte (a larger decode batch, or
speculative decoding) or cut the bytes read (quantization). The levers below are
specific to **this project's** config, not generic.

| Knob (current value) | What it changes | Why it should raise compute here | Status / validation |
|---|---|---|---|
| `--max-num-seqs` (Kimi **32**) | decode batch size — how many sequences share each weight read | **directly evidenced**: waiting 45 > running 32 with KV at 44% and preemptions 0, so the admission cap (not memory) holds the batch small; admitting more of the queue raises arithmetic intensity (power/FLOPs) and drains the queue at once | L1 → run the protocol's concurrency sweep at fixed prompt/output; stop when KV → high or preemptions > 0 |
| `--gpu-memory-utilization` (Kimi **0.6**) | size of the KV pool that funds a bigger batch | a larger KV pool lets a larger batch run without preemption; T3 showed ~26.6 GiB/GPU free at DeepSeek 0.2 co-residency → some headroom to enlarge Kimi's pool | coupled to DeepSeek co-residency — raise only within the T3 budget |
| `--max-model-len` (Kimi **131072**) | per-sequence worst-case KV reservation | 128k inflates each sequence's KV footprint and caps how many fit; if real prompts are far shorter, lowering it frees KV to raise `--max-num-seqs` | needs the real prompt-length distribution before changing |
| `--max-num-batched-tokens` (Kimi **4096**) | per-step token budget shared by prefill + decode (chunked prefill) | sized together with `--max-num-seqs`, it keeps decode flowing while prefill chunks compete for the same step | secondary; tune alongside the batch lever |
| `--speculative-config num_speculative_tokens` (Kimi **3**) | draft tokens verified per forward pass | already a compute lever — Eagle3 verifies k tokens against a single weight read, which is *why* it helps memory-bound decode | **already near-tuned**: measured acceptance 0.493 means pushing k > 3 likely spends compute on rejected drafts |
| `--enforce-eager` (DeepSeek **set** → CUDA graphs off) | per-step kernel-launch overhead | DeepSeek at `--max-num-seqs 2` is exactly where launch gaps between tiny decode kernels dominate; dropping it (graphs on, as Kimi already runs) closes those gaps | candidate re-test: confirm DeepSeek-V4 starts with graphs — `--enforce-eager` may have been needed for fp8_ds_mla / Lightning Indexer compatibility |
| expert weight quant (Kimi **4-bit WNA16**) | HBM bytes per weight, and which tensor cores do the matmul | weight-only 4-bit already cuts HBM traffic; an FP8 W8A8 path would also engage the H200 FP8 tensor cores for the matmul itself | bigger change (re-serve + quality trade-off); roadmap **W3** (FP8), out of W1 scope |

**This is throughput you buy with latency.** Compute utilization is not a goal in
itself: every lever above raises FLOPs-per-HBM-byte by enlarging the decode batch,
which raises per-request ITL (already ~15× single-stream at batch 32 — see the
applied analysis). For a latency-critical reasoning model you may deliberately
leave compute idle to keep ITL low. None of these changed W1's single-stream
baseline and they are not meant to; they matter when concurrent throughput is the
target. Only `--max-num-seqs` is supported by this capture — the rest are
hypotheses that need the protocol's one-lever counterfactuals and the #34 DCGM
split (`DRAM_ACTIVE` vs `TENSOR_ACTIVE`) to confirm they raise *compute*, not just
*batch size*.

## Evidence

| Claim | Source |
|---|---|
| Live metric-name validation (panels map to real vLLM v0.20.0 series) | `results/runs/2026-06-05_w1_evidence/t5_metrics/full-load/vllm_kimi_metrics.txt`, `…/vllm_small_metrics.txt` |
| Batched-load summary (running/waiting/throughput/KV/TTFT/E2E/ITL/acceptance/preemptions) | `results/runs/2026-06-05_w1_evidence/t5_metrics/prometheus_summary.txt` |
| Dashboard under load vs idle | `results/runs/2026-06-05_w1_evidence/2026-06-05_grafana_dashboard-max_num_seqs_{1,32}.png` |
| Repeatable load-test + Grafana procedure | `serving/runbooks/load-test-and-grafana.md` |
| Per-arm metric snapshots (Eagle3 on/off side capture) | `results/runs/2026-06-05_w1_evidence/t5_metrics/eagle3-{on,off}/` |
| Fuller validation / DCGM / exporter 404 (deferred) | issue #34 |

2026-06-05 artifacts organized under commit `d0bb634`.

## Reference

[1] X. Miao, G. Oliaro, Z. Zhang, X. Cheng, H. Jin, T. Chen, and Z. Jia,
"Towards Efficient Generative Large Language Model Serving: A Survey from
Algorithms to Systems," *ACM Computing Surveys*, 2025. arXiv:2312.15234.
