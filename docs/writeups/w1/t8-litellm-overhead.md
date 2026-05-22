# T8 — Does LiteLLM Proxy add measurable overhead

<!-- TODO: measurement segment. Paired A/B difference (client → proxy:4000
→ vLLM vs client → vLLM:8000), reversed pair order, warmup; cross-check
against LiteLLM's own latency metrics. -->

## Planned shape

Mode: measurement.

## Question

Does LiteLLM Proxy add measurable latency over the direct vLLM path under
the same model, prompt, decoding parameters, and client script?

## Measurement design

Compare two paths:

```text
A: benchmark client -> vLLM
B: benchmark client -> LiteLLM Proxy -> vLLM
```

Use paired runs:

1. warmup both paths,
2. run A/B in one order,
3. run B/A in the reverse order,
4. compare client TTFT, TTFT any-token, TPOT, and E2E.

## Controls

- same model,
- same prompt,
- same max tokens and temperature,
- same client host,
- same server state window,
- same streaming mode,
- same client script version.

## Expected output

A small table with direct vs proxy p50/p95 and an explicit statement of
what the measurement does not prove. If the difference is near noise, say
so; if proxy overhead is visible, quantify it.
