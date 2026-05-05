# Benchmark methodology

This document defines the lightweight benchmark methodology for `nanoserve-mini`.
It is inspired by MLPerf Inference, but it is not an MLPerf implementation,
compliance run, or submission target.

The goal is narrower: build reproducible benchmark discipline around vLLM,
open-weight models, and the project scripts.

## Why MLPerf matters

MLPerf is useful as a methodological reference because it emphasizes:

- clearly defined benchmark scenarios,
- reproducible workload and system controls,
- latency and throughput as separate concerns,
- comparable results across systems.

`nanoserve-mini` borrows the discipline and scenario thinking, not the full
benchmark framework.

## Why full MLPerf is out of scope

Full MLPerf would add too much process and infrastructure for this project phase.
It would shift attention away from the actual learning goal: understanding vLLM
serving behavior.

Out of scope:

- MLPerf LoadGen integration,
- official MLPerf compliance rules,
- official submission packaging,
- large benchmark datasets,
- MLPerf-scale large-model runs,
- quality target replication,
- benchmark-specific model preparation.

This project should remain a focused LLM inference performance lab, not an
MLPerf submission exercise.

## Benchmark modes

The project uses MLPerf-inspired modes with lighter names and lighter machinery.

### 1. Single-request latency / SingleStream-lite

Purpose:

- verify that the vLLM OpenAI-compatible API works,
- measure one request end-to-end,
- capture first TTFT/E2E behavior before load testing.

Current scripts:

- `scripts/request_once.py` — smoke test, one non-streaming request,
- `scripts/measure_ttft_once.py` — one streaming request with TTFT and E2E.

This is not a throughput benchmark. It is the first correctness and latency sanity
check.

### 2. Sequential latency

Purpose:

- measure repeated requests with `concurrency = 1`,
- get p50/p95 latency values before concurrent load,
- separate warmup runs from measured runs,
- verify that result schemas and controls are stable.

Current script:

- `scripts/run_sequential_benchmark.py`

This is still not a realistic serving-load benchmark. It is a controlled baseline
for TTFT and E2E behavior.

### 3. Offline-lite throughput

Purpose:

- estimate maximum throughput for a fixed prompt set,
- send a known workload as fast as possible under controlled concurrency,
- measure request throughput and output throughput.

Future script:

- `scripts/run_offline_benchmark.py`

Expected behavior:

- prompts are known before the run,
- concurrency is configured explicitly,
- all requests are sent without modelling realistic arrival times,
- throughput is interpreted only with workload and controls attached.

### 4. Server-lite arrival process

Purpose:

- approximate production-style request arrival,
- test latency under target QPS,
- observe p95/p99 and timeout behavior under load.

Future script:

- `scripts/run_server_like_benchmark.py`

Expected behavior:

- requests arrive according to a simple stochastic process, preferably Poisson,
- target QPS is configured explicitly,
- server-side metrics are correlated with client-side latency.

## Mapping to current scripts

| Mode | Current status | Script | Notes |
|---|---:|---|---|
| SingleStream-lite smoke | implemented | `scripts/request_once.py` | API correctness check. |
| SingleStream-lite TTFT | implemented | `scripts/measure_ttft_once.py` | One streaming TTFT/E2E record. |
| Sequential latency | implemented | `scripts/run_sequential_benchmark.py` | Warmup + measured runs, `concurrency = 1`. |
| Offline-lite throughput | future | `scripts/run_offline_benchmark.py` | Fixed prompt set, controlled concurrency. |
| Server-lite arrival | future | `scripts/run_server_like_benchmark.py` | Target QPS, arrival process, tail latency. |

## Required metrics

All benchmark modes should align with the roadmap Benchmark Contract.

Minimum metrics:

- TTFT p50/p95,
- TPOT p50/p95 when token-level accounting is available,
- end-to-end latency p50/p95,
- request throughput,
- output throughput tokens/s,
- input tokens per request,
- output tokens per request,
- concurrency,
- GPU memory usage,
- GPU KV cache usage when available,
- prefix cache hit rate when the experiment concerns cache behavior.

For early Phase 1 scripts, TPOT and token throughput may be unavailable. In that
case the benchmark must make the limitation explicit rather than pretending the
metric was measured.

## Required controls

Each result file should preserve enough context to reproduce and interpret the
measurement.

Minimum controls:

- git commit,
- script name and schema version,
- timestamp,
- model name,
- model revision if known,
- base URL,
- dtype / quantization,
- GPU model,
- server environment snapshot path,
- vLLM version when available,
- max model length,
- max number of sequences / batched tokens if configured,
- decoding parameters,
- workload label,
- prompt shape,
- max output tokens,
- number of warmup runs,
- number of measured runs,
- concurrency,
- timeout settings.

A benchmark without workload and server controls is not a benchmark result. It is
only an anecdote.

## Workload definitions

Workloads should be named and repeatable. At minimum, Phase 1 should distinguish:

- `short_prompt_short_output`,
- `medium_prompt_short_output`,
- `long_prompt_short_output`,
- `short_prompt_long_output`,
- `mixed_prompt_lengths`.

Each workload should define:

- prompt source,
- approximate input token range,
- `max_tokens`,
- decoding parameters,
- request count,
- concurrency or arrival pattern,
- whether prompts share prefixes.

## Interpreting early results

Early results should be interpreted conservatively.

Single-request and sequential runs can answer:

- does the server work,
- is streaming parsed correctly,
- what is the rough TTFT/E2E shape,
- do short/medium/long prompts behave differently,
- are controls being recorded correctly.

They cannot answer:

- maximum sustainable throughput,
- production p99 latency,
- scheduler behavior under load,
- prefix cache benefit,
- multi-user serving stability,
- cross-engine comparison.

Those require later Offline-lite, Server-lite, and vLLM `/metrics` work.

## Future extensions

After the first vLLM baseline is stable, add these in order:

1. token accounting and TPOT,
2. vLLM `/metrics` scraping,
3. Offline-lite throughput benchmark,
4. Server-lite arrival benchmark,
5. workload/cache experiment with shared prefixes,
6. plots and benchmark write-up.

Do not add full MLPerf infrastructure unless the final decision after week 12 is to
continue into a larger `nanoserve` project where that scope is justified.
