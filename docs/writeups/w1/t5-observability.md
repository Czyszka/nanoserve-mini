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
Exporter or `nvidia-smi`. For now, the hardware layer is part of the T5
observability plan; the final write-up should mark which GPU signals were
actually collected and which remain planned.

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

## Cleanup found during observability work

The server-metrics helper should be checked against the actual metric
names in the current dump. The useful names are:

```text
vllm:kv_cache_usage_perc
vllm:prefix_cache_hits_total
vllm:prefix_cache_queries_total
```

The aggregate logic should read KV usage directly from
`vllm:kv_cache_usage_perc` and compute prefix-cache hit rate from hits /
queries, preferably using a Prometheus `rate()` in Grafana or a pre/post
snapshot delta in run summaries.

## Decision for W1

For W1, use a small P0 observability contract instead of presenting the
entire `/metrics` surface. The write-up should focus on latency, token
rates, scheduler pressure, KV/cache behavior, request outcomes, and GPU
hardware telemetry. Process/Python metrics, `*_created` gauges,
idle zero-value histograms, speculative-decoding counters before T6, and
miscellaneous cache namespaces should stay secondary diagnostics.

## Reference

[1] X. Miao, G. Oliaro, Z. Zhang, X. Cheng, H. Jin, T. Chen, and Z. Jia,
"Towards Efficient Generative Large Language Model Serving: A Survey from
Algorithms to Systems," *ACM Computing Surveys*, 2025. arXiv:2312.15234.
