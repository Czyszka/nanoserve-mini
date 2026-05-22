# T4 — Why LiteLLM Proxy

<!-- TODO: justification segment. Rejected alternatives — two vLLM ports
exposed directly, nginx — each named with the reason it was dropped. -->

## Planned shape

Mode: justification + rejected alternatives.

## Decision

Use LiteLLM Proxy as the Phase 1 multi-model access layer.

## Reasoning to develop

LiteLLM Proxy solves the immediate operational problem for W1: one
OpenAI-compatible endpoint in front of multiple model backends. It lets
the benchmark harness switch models through the `model` field while
keeping client code stable.

## Rejected alternatives

| Alternative | Why rejected for W1 |
|---|---|
| Expose each vLLM backend directly | Simple, but pushes routing into every client script and makes proxy-path overhead impossible to isolate later. |
| nginx reverse proxy | Useful for HTTP routing, but it does not provide model-aware OpenAI-compatible routing semantics. |
| vLLM Semantic Router | Relevant to W4/F3, but too much scope for the W1 baseline. W1 needs explicit model routing first. |

## Future link

Semantic routing and model-selection research are tracked separately in issue #39 and should not block W1.
