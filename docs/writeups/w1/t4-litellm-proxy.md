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
`LITELLM_MASTER_KEY`. Per-user virtual keys are not a stateless add-on:
LiteLLM's docs require a **Postgres database** (`DATABASE_URL`, a master key,
then `/key/generate`) to store keys, users, teams, budgets, and per-request
usage. Reaching the DoD's "API keys per user" therefore means standing up
DB-backed key management, not tuning the current compose file — and on the
pinned `main-v1.66.0-stable` image that enablement warrants migration
smoke-tests, since Prisma migrations can fail and leave silent schema drift
rather than erroring cleanly (see External evidence).

Second, logging is currently container logging. `LITELLM_LOG: INFO` gives
stdout-level operational logs from the proxy process. It is not structured
per-request logging, spend logging, tracing, or audit logging. LiteLLM can be
extended in those directions through DB/UI logs, external observability sinks,
or callback-based loggers, but none of those paths are enabled in W1.

Third, the proxy introduces another processing hop. The correct claim is not
that this hop is free — it is that its cost is an empirical question isolated in
T8. LiteLLM's own published figure (8 ms P95 at 1k RPS) is measured against a
*fake* OpenAI endpoint on a 4 CPU / 8 GB box, and its performance is
version-dependent: aiohttp became the default transport only in v1.72.0, well
after our pinned `main-v1.66.0-stable`. So that number is not evidence for this
8×H200 setup, pinned image, prompt mix, streaming behavior, or concurrency
level. The right method is the one LiteLLM itself supplies — read the
`x-litellm-overhead-duration-ms` header on our own request path — which is what
T8 does.

The 2026-05-27 T8 pilot therefore bounds the claim: the proxy path was usable,
and it revealed a real Kimi streaming-semantics difference, but it did not
complete the full overhead study. The full R1-R8 program remains tracked in
issue #44.

## Rejected alternatives

| Alternative | Why rejected for W1 |
|---|---|
| Expose each vLLM backend directly | vLLM already provides OpenAI-compatible endpoints and direct ports are valuable controls. They do not, however, provide one multi-model endpoint. Client scripts would need to encode `model -> base_url` routing themselves, which is exactly the coupling T4 removes. |
| nginx reverse proxy | A generic reverse proxy can route HTTP traffic, but model-aware OpenAI routing requires reading and interpreting the request body or maintaining custom path conventions. That would turn W1 into an ad hoc gateway implementation rather than a serving baseline. |
| vLLM Semantic Router | Semantic Router is relevant when the project asks whether routing should depend on request content, cost, latency, or model capability. Its reported gains come from the *routing policy*, not from adding or removing a gateway hop — "When to Reason" measures −47.1% latency, −48.5% tokens and +10.2 pp MMLU-Pro accuracy against direct inference (arXiv:2510.08731). W1 only needs explicit routing by the `model` field; content-aware policy belongs to the later routing work. |

## Future link

Issue #39 should treat LiteLLM as the starting thin router, not as a decision to
reopen. The next maturity step is to ask when the project needs DB-backed
per-user keys, structured request logging, governance, and eventually
content-aware routing. That is a transition from baseline model routing to a
managed inference control plane; it is outside the minimum W1 proof.

## External evidence (verified)

The external claims this thread leans on were checked against primary sources
(vendor docs / paper) on 2026-06-06:

| Claim used in T4 | Status | Source |
|---|---|---|
| Per-user virtual keys require a Postgres DB (`DATABASE_URL`, master key, `/key/generate`) | confirmed | [docs.litellm.ai/docs/proxy/virtual_keys](https://docs.litellm.ai/docs/proxy/virtual_keys) |
| LiteLLM's published latency (8 ms P95 @ 1k RPS) is synthetic — fake OpenAI endpoint, 4 CPU / 8 GB | confirmed | [docs.litellm.ai/docs/benchmarks](https://docs.litellm.ai/docs/benchmarks) |
| Each response carries `x-litellm-overhead-duration-ms` (measure overhead on your own path) | confirmed | [docs.litellm.ai/docs/benchmarks](https://docs.litellm.ai/docs/benchmarks) |
| Proxy performance is version-dependent — aiohttp became the default transport in v1.72.0 (≈2× RPS) | confirmed | [release_notes/v1-72-0-stable](https://docs.litellm.ai/release_notes/v1-72-0-stable), [PR #11097](https://github.com/BerriAI/litellm/pull/11097) |
| Semantic routing's gain is from policy, not the hop: −47.1% latency, −48.5% tokens, +10.2 pp MMLU-Pro vs direct inference | confirmed | [arXiv:2510.08731](https://arxiv.org/abs/2510.08731) (NeurIPS 2025) |
| DB key management on a pinned tag needs migration smoke-tests — Prisma migrations can fail and leave schema drift | confirmed (general); specific v1.66.0 `team_member_permissions` issue not located | [docs.litellm.ai/docs/troubleshoot/prisma_migrations](https://docs.litellm.ai/docs/troubleshoot/prisma_migrations), [#14596](https://github.com/BerriAI/litellm/issues/14596) |

## Evidence

| Claim | Source |
|---|---|
| Proxy fronts both vLLM backends; explicit `model`-name routing | `serving/compose/litellm-config.yaml`, `serving/compose/docker-compose.kimi-k2.6.yml` |
| Both models reachable through `:4000` | `results/runs/2026-05-19_litellm-smoke/{models,litellm_kimi_smoke,litellm_deepseek_smoke}.json` |
| Bench completed through the proxy for both models | `results/runs/2026-05-19_kimi-k2-6_run-01/bench_suite/summary.json`, `results/runs/2026-05-19_deepseek-v4-flash_run-01/bench_suite/summary.json` |
| The hop's cost is an open empirical question, not assumed free | T8 + issue #44 |
| Known boundary limit: proxy strips Kimi reasoning deltas (can return `completed:false`) | T8 §2026-06-05; `results/runs/2026-06-05_kimi-k2-6_run-0{1,3}_t8-{proxy,direct}/` |

The reasoning-strip limit means this boundary is sound for routing but **not**
transparent for reasoning-model streams — direct vLLM remains the required path
for those, per T8.
