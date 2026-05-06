# AGENTS.md

## Project context

This repository is `nanoserve-mini`: a 12-week LLM inference performance lab.

The project focuses on:

- vLLM serving baseline,
- observability,
- benchmark harness,
- workload and cache analysis,
- one Triton kernel later in the project,
- technical write-ups.

## Current phase

For current phase, status, decisions, and next step, see `docs/agent-state.md`.
Do not duplicate that content here.

## Local laptop environment

Primary local development happens on a Windows 11 laptop.

Use these tools and assumptions for local work:

- Shell: PowerShell.
- Python environment and dependency manager: `uv`.
- Python version: Python 3.12.
- Run Python through the project environment with `uv run python`, not as a global laptop
  interpreter.
- Run Python tools through `uv run <tool>` so dependencies stay local to this project.
- Version control: `git`.
- GitHub CLI: `gh`.
- Windows package manager for system tools: `winget`.
- Default Git branch: `main`.
- Local validation script: `scripts/check_local.ps1`.
- Preferred validation commands:
  - `uv sync --extra dev`
  - `uv run ruff check .`
  - `uv run pytest`

The laptop is for editing code, writing documentation, preparing benchmark scripts, analysing
results, and syncing with GitHub. Do not install or configure GPU runtime dependencies on this
Windows laptop unless explicitly requested.

## Scope boundaries

Do not add the following unless explicitly requested:

- custom inference engine,
- TensorRT-LLM,
- SGLang integration,
- Kubernetes,
- multi-GPU / tensor parallelism,
- FP8 quantization,
- MoE,
- speculative decoding,
- production HA/autoscaling,
- large cloud infrastructure.

## Working rules

- Keep changes small and reviewable.
- Prefer simple Python scripts over complex frameworks.
- Use Python 3.12 and `uv`.
- Do not add heavy GPU dependencies on the Windows laptop.
- Do not commit secrets.
- Do not commit model weights, Hugging Face cache, large logs, or Nsight traces.
- Keep documentation in Markdown.
- Keep raw benchmark results small; commit summaries when raw data is large.
- When modifying benchmark logic, preserve reproducibility metadata.
- Do not rewrite `ROADMAP.md` unless explicitly asked.
- Do not change project scope unless explicitly asked.

## Shared project state

Use `docs/agent-state.md` as the single repo-tracked handoff/status file shared by
Codex, Claude Code, and human work.

File roles:

- `AGENTS.md` - stable instructions for Codex.
- `CLAUDE.md` - stable instructions for Claude Code.
- `docs/agent-state.md` - current project state, decisions, next step, and blockers.
- `ROADMAP.md` - project scope; do not change it without an explicit decision.

At the beginning of non-trivial work, read `docs/agent-state.md` and verify that it
matches the repo state.

After meaningful changes, update `docs/agent-state.md` with:

- what changed,
- commands run,
- validation results,
- new decisions,
- next recommended action,
- open blockers.

Always update `docs/agent-state.md` before committing, pushing, or handing work to
another agent when the task changed the repository state.

## Validation

After Python/config changes, try to run:

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

If a command fails because the environment is not ready, report the exact error and do not hide it.

## Response format

When you finish, report:

1. files created/changed,
2. commands run,
3. checks passed/failed,
4. next recommended command for the user.
