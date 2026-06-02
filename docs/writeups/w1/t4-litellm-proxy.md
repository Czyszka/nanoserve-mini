# T4 - LiteLLM Proxy as the Phase 1 multi-model boundary

## Question

What is the smallest access layer that lets the Phase 1 stack expose multiple
vLLM backends through one OpenAI-compatible API surface, while keeping the
benchmark client independent from backend ports?

## Decision

Use LiteLLM Proxy as the Phase 1 multi-model access layer.

This is a scoped baseline decision. It does not claim that LiteLLM is already a
complete production control plane in this repository. It claims that LiteLLM is
the minimal model-aware gateway needed for W1: one endpoint, explicit
model-name routing, and stable client semantics while Kimi-K2.6 and
DeepSeek-V4-Flash run as separate vLLM services.

## Configuration evidence

The compose stack exposes LiteLLM on port 4000 and mounts the proxy
configuration from the repository:

```yaml
    ports:
      - "${LITELLM_HOST_PORT:-4000}:4000"
    volumes:
      - ./litellm-config.yaml:/etc/litellm/config.yaml:ro
    command:
      ["--config", "/etc/litellm/config.yaml", "--port", "4000", "--num_workers", "1"]
```

The model map is explicit. Requests with `model: "kimi-k2.6"` are forwarded to
the Kimi vLLM service:

```yaml
  - model_name: kimi-k2.6
    litellm_params:
      model: openai/kimi-k2.6
      api_base: http://vllm:8000/v1
      api_key: dummy
```

Requests with `model: "DeepSeek-V4-Flash"` are forwarded to the second vLLM
service:

```yaml
  - model_name: DeepSeek-V4-Flash
    litellm_params:
      model: openai/DeepSeek-V4-Flash
      api_base: http://vllm-small:8004/v1
      api_key: dummy
```

The relevant property is not that LiteLLM performs content-aware routing. It
does not, in this setup. The relevant property is that model selection is moved
from client-side base URL selection into one proxy-side mapping. The benchmark
harness can therefore hold `base_url` fixed at `http://127.0.0.1:4000` and vary
only the OpenAI `model` field.

The committed run evidence shows that this boundary worked for both configured
models:

- `results/runs/2026-05-19_litellm-smoke/models.json` lists `kimi-k2.6` and
  `DeepSeek-V4-Flash` from the proxy model endpoint.
- `results/runs/2026-05-19_litellm-smoke/litellm_kimi_smoke.json` and
  `results/runs/2026-05-19_litellm-smoke/litellm_deepseek_smoke.json` are
  successful proxy-path smoke requests.
- `results/runs/2026-05-19_kimi-k2-6_run-01/bench_suite/summary.json` completed
  through `base_url: "http://127.0.0.1:4000"` with `model: "kimi-k2.6"`.
- `results/runs/2026-05-19_deepseek-v4-flash_run-01/bench_suite/summary.json`
  completed through the same proxy URL with `model: "DeepSeek-V4-Flash"`.

The proxy settings are also deliberately conservative for a baseline stack:

```yaml
litellm_settings:
  drop_params: true
  set_verbose: false
  request_timeout: 600

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

`drop_params: true` reduces avoidable client breakage when backend-specific
OpenAI-compatible implementations disagree about accepted optional parameters.
`request_timeout: 600` avoids treating slow first requests from large models as
client failures too early. The master key centralizes access to the proxy, while
the compose file supplies it from the environment:

```yaml
    environment:
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:?set LITELLM_MASTER_KEY in .env}
      LITELLM_LOG: INFO
```

## What this decision proves

For W1, the decision proves only a narrow operational point: one stable
OpenAI-compatible endpoint can front two independently served vLLM backends, and
the existing benchmark scripts can switch models through the request payload
instead of changing client transport configuration.

That is enough for the Phase 1 baseline because the immediate problem is
controlled measurement, not advanced routing policy. Direct vLLM endpoints
remain useful controls, but the proxy path gives the write-up a single
multi-model access surface to evaluate.

## Limits of the current implementation

This repository does not yet implement the fuller control-plane features often
associated with LiteLLM Proxy.

First, API keys are not per user. The current configuration uses one
`LITELLM_MASTER_KEY`. Per-user virtual keys require persistent state for keys,
users, teams, budgets, and usage accounting; in practice that means adding a
DB-backed key-management layer. That is future work, not evidence from the
current compose file.

Second, logging is currently container logging. `LITELLM_LOG: INFO` gives
stdout-level operational logs from the proxy process. It is not structured
per-request logging, spend logging, tracing, or audit logging. LiteLLM can be
extended in those directions through DB/UI logs, external observability sinks,
or callback-based loggers, but none of those paths are enabled in W1.

Third, the proxy introduces another processing hop. The correct claim is not
that this hop is free. The correct claim is that its cost is an empirical
question isolated in T8. Public or synthetic proxy benchmark numbers are not
evidence for this 8xH200 setup, pinned LiteLLM image, prompt mix, streaming
behavior, or concurrency level.

The 2026-05-27 T8 pilot therefore bounds the claim: the proxy path was usable,
and it revealed a real Kimi streaming-semantics difference, but it did not
complete the full overhead study. The full R1-R8 program remains tracked in
issue #44.

## Rejected alternatives

| Alternative | Why rejected for W1 |
|---|---|
| Expose each vLLM backend directly | vLLM already provides OpenAI-compatible endpoints and direct ports are valuable controls. They do not, however, provide one multi-model endpoint. Client scripts would need to encode `model -> base_url` routing themselves, which is exactly the coupling T4 removes. |
| nginx reverse proxy | A generic reverse proxy can route HTTP traffic, but model-aware OpenAI routing requires reading and interpreting the request body or maintaining custom path conventions. That would turn W1 into an ad hoc gateway implementation rather than a serving baseline. |
| vLLM Semantic Router | Semantic Router is relevant when the project asks whether routing should depend on request content, cost, latency, or model capability. W1 only needs explicit routing by the `model` field; content-aware policy belongs to the later routing work. |

## Future link

Issue #39 should treat LiteLLM as the starting thin router, not as a decision to
reopen. The next maturity step is to ask when the project needs DB-backed
per-user keys, structured request logging, governance, and eventually
content-aware routing. That is a transition from baseline model routing to a
managed inference control plane; it is outside the minimum W1 proof.
