# nanoserve-mini

12-week LLM inference performance lab. vLLM serving baseline,
observability, benchmark harness, workload + KV/prefix cache analysis,
one Triton kernel, technical write-ups, final decision document.

Standalone portfolio artifact that also acts as a decision gate for a
possible full `nanoserve` follow-up.

## Status

**Phase 1** — Kimi-K2.6 is served on the 8×H200 NVL server via `vllm serve`
with TP=8 + Eagle3 speculative decoding, OpenWebUI is connected to the
OpenAI-compatible endpoint, and the local benchmark/metrics harness
(`benchmarks/scripts/`) is in place. Current next steps and blockers live
in [`docs/operations/agent-state.md`](docs/operations/agent-state.md).

Laptop is for code, docs, analysis, benchmark preparation. The 8×H200
server is the primary GPU runtime.

## Repository layout

```text
benchmarks/
  scripts/          Benchmark + metrics producers (CLI):
                      request_once, measure_ttft_once,
                      run_sequential_benchmark,
                      collect_metrics_snapshot, sample_gpu_metrics,
                      check_server_env
                    plus shared library:
                      _client, _metrics, _schemas, _server_metrics
  scripts_tests/    Pytest suite (mocked httpx / subprocess; no GPU needed).

serving/
  compose/          Docker Compose for vLLM + OpenWebUI on the server.
  runbooks/         Operational instructions (env bootstrap, vLLM launch).

results/
  raw/              Raw artifacts kept in Git (env snapshots, small inputs).
  runs/             Per-run benchmark/metrics output under <run_id>/<mode>/.
  summaries/        Aggregated text/CSV/Markdown summaries.

docs/
  project/          Roadmap and long-term scope.
  operations/       agent-state, benchmark methodology, infrastructure.
  learning/         Reading list, NVIDIA courses, paper notes.
  plans/            Time-bound session plans.
  templates/        Markdown + agent-routine templates.
  weekly/           Weekly progress notes.
```

Quick map: code lives in `benchmarks/`, operations in `serving/`, outputs
in `results/`, everything else in `docs/`.

## Scope

See [`docs/project/roadmap.md`](docs/project/roadmap.md) for the full
definition of done, phase plan, decision points, and the section on
material brought into scope via the parallel company H200 project
(TP scaling, MoE serving, FP8, multi-tenant — measured at work, written
up here).

Phase 1 deliverables still owed: LiteLLM Proxy, Prometheus + Grafana
dashboard, write-up W1.

## Local development

Requirements: Windows 11 or Linux, Python 3.12, `uv`, Git.

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

Local validation helper (Windows):

```powershell
.\benchmarks\scripts\check_local.ps1
```

## GPU server

Record an environment snapshot to `results/raw/server_env_snapshot.json`:

```bash
uv run python -m benchmarks.scripts.check_server_env
```

Compose stack and runbooks: [`serving/compose/`](serving/compose/),
[`serving/runbooks/`](serving/runbooks/).

Results / secrets policy: never commit `.env`, API keys, HF / W&B / cloud
tokens, model weights, HF cache, large logs, full Nsight traces
(`*.ncu-rep`, `*.nsys-rep`), or large benchmark artifacts. See
[`docs/operations/infrastructure.md`](docs/operations/infrastructure.md)
for the full list and rotation procedure if a secret leaks.

## Key docs

- [Documentation map](docs/README.md)
- [Roadmap](docs/project/roadmap.md)
- [Agent state (current work)](docs/operations/agent-state.md)
- [Benchmark methodology](docs/operations/benchmark-methodology.md)
- [Infrastructure and workflow](docs/operations/infrastructure.md)
- [Reading list](docs/learning/reading-list.md)
