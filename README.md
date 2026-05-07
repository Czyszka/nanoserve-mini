# nanoserve-mini

`nanoserve-mini` is a 12-week LLM inference performance lab focused on practical
serving, measurement, observability, workload analysis, and one small Triton kernel.

The project is intentionally narrow: it uses vLLM as the serving baseline and keeps
the repository focused on reproducible experiments, benchmark scripts, technical
notes, and small result summaries.

## Status

Current phase: Phase 1 — first vLLM run completed. Kimi-K2.6 is served through
`vllm serve` with TP=8 + Eagle3 speculative decoding on the 8×H200 NVL server,
and OpenWebUI is connected to the OpenAI-compatible endpoint. For up-to-date
phase, decisions, and next step, see [`docs/agent-state.md`](docs/agent-state.md).

The local Windows laptop is used for code, documentation, benchmark preparation, and
result analysis. GPU runtime work happens on the GPU server.

## Goals

- Establish a reproducible vLLM serving baseline.
- Capture first TTFT / TPOT / throughput measurements.
- Add observability with Prometheus and Grafana.
- Build a small benchmark harness for workload and cache analysis.
- Analyze prefix / KV cache behavior under different prompt patterns.
- Implement and profile one Triton kernel later in the project.
- Publish concise technical write-ups and a final decision document.

## Out of scope for this mini project

- Custom inference engine.
- TensorRT-LLM or SGLang integration.
- Kubernetes or production autoscaling.
- Multi-GPU / tensor parallelism.
- FP8 quantization, MoE, or speculative decoding.
- Large cloud infrastructure.

## Repository Layout

```text
benchmarks/           Benchmark configs, prompts, and harness code.
docs/                 Roadmap, infrastructure notes, reading list, and weekly notes.
infra/                Lightweight local/server infrastructure files.
results/              Small raw outputs, run metadata, and summaries.
scripts/              Local and server helper scripts.
tests/                Local validation tests.
```

## Local Development

Requirements:

- Windows 11
- Python 3.12
- uv
- Git

Install dependencies:

```powershell
uv sync --extra dev
```

Run local checks:

```powershell
uv run ruff check .
uv run pytest
```

Or run the project validation script:

```powershell
.\scripts\check_local.ps1
```

## GPU Server Preparation

The server environment snapshot script records basic OS, CUDA, NVIDIA, Docker, and
hardware metadata into `results/raw/server_env_snapshot.json`:

```bash
uv run python -m scripts.check_server_env
```

Do not commit secrets, model weights, Hugging Face caches, large logs, Nsight traces,
or large benchmark artifacts.

## Key Docs

- [Roadmap](docs/ROADMAP_v_1_0.md)
- [Infrastructure and workflow](docs/infrastructure_v_1_0.md)
- [Reading list](docs/reading-list.md)
- [NVIDIA self-paced courses](docs/nvidia_self_paced_courses.md)

## Suggested GitHub Description

```text
12-week LLM inference performance lab: vLLM baseline, observability, benchmark harness, workload/cache analysis, and one Triton kernel.
```
