# CLAUDE.md

This file is the project entrypoint for Claude Code.

## Project

Repository: `nanoserve-mini`

`nanoserve-mini` is a 12-week LLM inference performance lab. The project is a smaller, finished artifact before any possible full `nanoserve` continuation.

Core scope:

- vLLM serving baseline,
- Prometheus/Grafana observability,
- benchmark harness,
- workload and KV/prefix cache analysis,
- one Triton kernel later in the project,
- technical write-ups,
- final decision document.

## Required reading at session start

Before making changes, read:

1. `ROADMAP.md` or the current roadmap/scope document named in `docs/agent-state.md`
2. the current infrastructure/workflow document named in `docs/agent-state.md`
3. `docs/agent-state.md`
4. `AGENTS.md` if present

Then summarize the current state in 3-5 bullets before proposing work.

## Current workflow

GitHub is the single source of truth.

Machines:

- Windows 11 laptop: dev, docs, analysis, benchmark script preparation.
- Ubuntu 24 server with 8x H200 NVL: primary GPU execution environment.
- Optional GPU cloud: only a support buffer for off-hours GPU tests.

Python workflow:

- Use `uv` on both laptop and server.
- Prefer `uv run ...` over global Python commands.
- Do not install global Python packages.
- Do not add GPU-heavy dependencies to the laptop environment.

Standard local validation:

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

## Scope boundaries

Do not add or implement unless explicitly requested:

- custom inference engine,
- TensorRT-LLM,
- SGLang integration,
- Kubernetes,
- multi-GPU / tensor parallelism experiments,
- FP8 quantization,
- MoE,
- speculative decoding,
- production HA/autoscaling,
- large cloud infrastructure.

Do not rewrite `ROADMAP.md` unless explicitly asked.

## Immediate project state

For current phase, status, decisions, and next step, see `docs/agent-state.md`.
Do not duplicate that content here.

## Agent state protocol

`docs/agent-state.md` is the shared, repo-tracked memory for all coding agents.

File roles:

- `CLAUDE.md` - stable instructions for Claude Code.
- `AGENTS.md` - stable instructions for Codex.
- `docs/agent-state.md` - current project state, decisions, next step, and blockers.
- `ROADMAP.md` - project scope; do not change it without an explicit decision.

At the beginning of a task:

1. read `docs/agent-state.md`,
2. verify whether it matches the current repo state,
3. avoid duplicating stale assumptions.

At the end of a meaningful task, update `docs/agent-state.md` with:

- what changed,
- commands run,
- validation results,
- new decisions,
- next recommended action,
- open blockers.

Always update `docs/agent-state.md` before committing, pushing, or handing work to
another agent when the task changed the repository state.

Keep `docs/agent-state.md` concise. It should be a handoff document, not a full diary.

## Results and secrets policy

Never commit:

- `.env`,
- API keys,
- Hugging Face tokens,
- GitHub tokens,
- model weights,
- Hugging Face cache,
- large logs,
- large Nsight traces,
- large benchmark artifacts.

Commit:

- small JSON/JSONL/CSV results when useful,
- summaries,
- configs,
- scripts,
- markdown write-ups,
- reproducibility metadata.

If a result is large, commit only the summary and the reproduction instructions.

## Git rules

Before editing:

```bash
git status
```

Before finishing:

```bash
uv run ruff check .
uv run pytest
git status
```

Use small commits. Preferred commit prefixes:

- `docs:`
- `feat:`
- `fix:`
- `bench:`
- `infra:`
- `chore:`

Do not push secrets or machine-local files.

## Communication style

Be concise and operational.

When reporting work, include:

1. files changed,
2. commands run,
3. checks passed/failed,
4. next step.
