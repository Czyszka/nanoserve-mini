# nanoserve-mini

12-week LLM inference performance lab. vLLM serving baseline,
observability, benchmark harness, workload + KV/prefix cache analysis,
one Triton kernel, technical write-ups, final decision document.

Standalone artifact that also acts as a decision gate for a possible
full `nanoserve` follow-up.

## Status

**Phase 1** — Kimi-K2.6 is served on the 8×H200 NVL server via `vllm serve`
with TP=8 + Eagle3 speculative decoding, OpenWebUI is connected to the
OpenAI-compatible endpoint, and the local benchmark/metrics harness
(`benchmarks/scripts/`) is in place. Next steps and current blockers live in
[`docs/operations/agent-state.md`](docs/operations/agent-state.md).

Laptop is for code, docs, analysis, benchmark preparation. Server is the
primary GPU runtime.

## Repository layout

```text
benchmarks/
  scripts/        Benchmark + metrics producers (run from CLI):
                    request_once, measure_ttft_once, run_sequential_benchmark,
                    collect_metrics_snapshot, sample_gpu_metrics, check_server_env
                  plus shared library: _client, _metrics, _schemas, _server_metrics

serving/
  compose/        Docker Compose definitions for vLLM + OpenWebUI on the server.
  runbooks/       Operational instructions (env bootstrap, vLLM launch).

results/
  raw/            Raw artifacts kept in Git (env snapshots, small inputs).
  runs/           Per-run benchmark/metrics output under <run_id>/<mode>/.
  summaries/      Aggregated text/CSV/Markdown summaries.

docs/
  project/        Roadmap and long-term scope.
  operations/     agent-state, benchmark methodology, infrastructure notes.
  learning/       Reading list, NVIDIA courses, paper notes.
  plans/          Time-bound session plans.
  templates/      Markdown + agent-routine templates.
  weekly/         Weekly progress notes.

benchmarks/scripts_tests/
                  Pytest suite for benchmark + metrics scripts.
```

Quick map: code → `benchmarks/scripts/` and `benchmarks/scripts_tests/`. Operations → `serving/`.
Outputs → `results/`. Everything else lives in `docs/`.

## In scope

- vLLM serving baseline on H200.
- LiteLLM Proxy as a multi-model OpenAI-compatible front door.
- Prometheus/Grafana observability + benchmark harness.
- Workload analysis + KV/prefix cache experiment.
- Triton kernel (RMSNorm or SwiGLU) with correctness + benchmark + profile.
- vLLM Semantic Router experiment vs. manual routing.
- 5-7 technical write-ups + final decision doc.

The roadmap covers areas the company H200 project brings *into* scope as
synthesis material (TP scaling, MoE serving, FP8 quantization, multi-tenant).
See [`docs/project/roadmap.md`](docs/project/roadmap.md) for the full
definition of done and phase plan.

## Explicitly not in scope

Custom inference engine, TensorRT-LLM, SGLang integration, Kubernetes,
production HA/autoscaling, full prefix-cache implementation. See roadmap
"Świadomie poza scope" section.

## Local development

Requirements: Windows 11 or Linux, Python 3.12, `uv`, Git.

```powershell
uv sync --extra dev
uv run ruff check .
uv run pytest
```

Or via the local validation helper:

```powershell
.\benchmarks\scripts\check_local.ps1
```

## GPU server bootstrap

Record an environment snapshot to `results/raw/server_env_snapshot.json`:

```bash
uv run python -m benchmarks.scripts.check_server_env
```

Compose-driven serving lives under [`serving/compose/`](serving/compose/);
operational runbooks are in [`serving/runbooks/`](serving/runbooks/).

Do not commit secrets, model weights, Hugging Face caches, large logs,
Nsight traces, or large benchmark artifacts. See
[`docs/operations/infrastructure.md`](docs/operations/infrastructure.md)
for the full policy.

## Key docs

- [Documentation map](docs/README.md)
- [Roadmap](docs/project/roadmap.md)
- [Agent state (current work)](docs/operations/agent-state.md)
- [Benchmark methodology](docs/operations/benchmark-methodology.md)
- [Infrastructure and workflow](docs/operations/infrastructure.md)
- [Reading list](docs/learning/reading-list.md)
