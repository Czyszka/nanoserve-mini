# T8 LiteLLM Proxy Overhead Summary

## Scope

Paired direct-vs-proxy latency measurement for the two served models on the
8×H200 NVL server, captured during the 2026-05-27 server session. This is a
single-stream, short-prompt, smoke-style overhead check — **not** a production
concurrency benchmark.

- Kimi-K2.6: direct vLLM `http://127.0.0.1:8000` vs LiteLLM Proxy `http://127.0.0.1:4000`.
- DeepSeek-V4-Flash: direct vLLM-small `http://127.0.0.1:8004` vs LiteLLM Proxy `http://127.0.0.1:4000`.

10 paired requests per model (`{model}_{1..10}_A_direct.json` /
`{model}_{1..10}_B_proxy.json`). All 40 requests completed; 0 errors on either
path for either model.

## Method

`measure_ttft_once.py` (schema `nanoserve-mini.ttft-once.v2`,
`benchmark_mode=singlestream_lite_latency`), one request per file. For each
model the only difference between path A and path B is `base_url`; the request,
decoding parameters, and client script are identical. Deltas are computed
pairwise (`proxy − direct`) per index, then the median/min/max of the paired
deltas is reported. Medians of the raw direct/proxy distributions are reported
alongside so the paired delta and the distribution shift can be read together.

## Controls

From a representative request (`kimi_1_A_direct.json`); identical across A and B
except `base_url`:

| Control | Value |
|---|---|
| model | `kimi-k2.6` / `DeepSeek-V4-Flash` |
| base_url | direct `:8000`/`:8004` vs proxy `:4000` |
| temperature | `0.0` |
| max_tokens | `64` |
| stream | `true` (streamed TTFT) |
| prompt | `"say OK"` (`single-prompt-smoke`, 6 chars) |
| warmup_runs | `0` |
| measured_runs | `1` per file (10 files per path) |
| concurrency | `1` |
| script | `measure_ttft_once.py` |
| git_commit | `5ce0881` |

## Results

| Model | Path | n | median TTFT (s) | median any-token TTFT (s) | median E2E (s) | median completion_tokens | median output tok/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| Kimi-K2.6 | direct | 10 | 0.592 | 0.209 | 0.611 | 46 | 79.1 |
| Kimi-K2.6 | proxy | 10 | 0.608 | 0.608 | 0.618 | 46 | 74.7 |
| DeepSeek-V4-Flash | direct | 10 | 0.253 | 0.253 | 0.403 | 2 | n/a* |
| DeepSeek-V4-Flash | proxy | 10 | 0.279 | 0.279 | 0.437 | 2 | n/a* |

\* DeepSeek output throughput is not meaningful: median `completion_tokens` is
2 (the `OK` answer). The raw values (direct ~4.97, proxy ~4.58 tok/s) are
dominated by per-request fixed cost at this output length and are excluded from
interpretation.

## Paired deltas

| Model | Metric | median proxy−direct | min | max |
|---|---|---:|---:|---:|
| Kimi-K2.6 | TTFT (s) | +0.017 | +0.005 | +0.038 |
| Kimi-K2.6 | any-token TTFT (s) | +0.398 | +0.388 | +0.410 |
| Kimi-K2.6 | E2E (s) | +0.020 | −0.129 | +0.188 |
| Kimi-K2.6 | output tok/s | −3.86 | −12.53 | +4.09 |
| DeepSeek-V4-Flash | TTFT (s) | +0.026 | +0.025 | +0.062 |
| DeepSeek-V4-Flash | any-token TTFT (s) | +0.026 | +0.025 | +0.062 |
| DeepSeek-V4-Flash | E2E (s) | +0.034 | +0.023 | +0.070 |

The wide Kimi E2E delta range (−0.129 .. +0.188) tracks `completion_tokens`
variation (paired delta min/max −18/+18 tokens) — at `temperature=0` Kimi's
reasoning trace still varies in length between paired requests, so E2E is noisy
relative to the small per-request routing cost.

## Interpretation

### Network/routing overhead

The final-answer TTFT delta is small in this single-stream smoke workload:
median **+17 ms** for Kimi and **+26 ms** for DeepSeek. The E2E delta is the
same order (+20 ms Kimi, +34 ms DeepSeek). This is consistent with keeping
LiteLLM as the multi-model routing layer for W1, but says nothing about (a)
behavior under concurrency, or (b) which hop (client→proxy vs proxy→vLLM)
carries the delta — proxy-side metrics were not captured this session.

### Streaming-semantics caveat (Kimi)

Independently of latency overhead, the proxy materially changes Kimi's
streaming behavior. Median `ttft_any_token_seconds` rises from ~0.21 s direct to
~0.61 s proxy (**~3× regression, paired delta ~+0.40 s**), and the proxy
delivers `reasoning_chars=0` while the direct stream carries the reasoning trace
(`reasoning_chars` ≈ 189 in the sample). This is **not** extra latency — it is
the proxy collapsing `delta.reasoning` / `delta.reasoning_content` into the
final-answer stream, so proxy clients see the first token only when the
final-answer text begins. This directly limits how T2's reasoning-aware TTFT
parser (issue #31) can be read at the proxy boundary — see
[t2-reasoning-ttft.md](../../../docs/writeups/w1/t2-reasoning-ttft.md). Median
Kimi `output_tokens_per_second` also drops ~5.6 % under the proxy path (79.1 →
74.7) in this single-stream workload.

## Limitations

- single prompt (`"say OK"`),
- single-stream, concurrency = 1,
- short output (DeepSeek `completion_tokens` ≈ 2 — DeepSeek throughput metrics
  are not meaningful and are excluded),
- no concurrency sweep,
- no production traffic,
- no proxy-side metric confirmation: `litellm_metrics_post.txt` captured during
  the session is a 22-byte HTTP 404 (`{"detail":"Not Found"}`) — the LiteLLM
  Prometheus exporter was not enabled (`prometheus_callback` missing in
  `serving/compose/litellm-config.yaml`) or scraped at the wrong endpoint.
  Flagged as a follow-up for the next server session.
