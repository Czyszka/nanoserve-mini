# AGENTS.md

This file is the project entrypoint for Codex.

## Project

`nanoserve-mini` is a 12-week LLM inference performance lab (vLLM serving baseline,
observability, benchmarks, workload/cache analysis, one Triton kernel, write-ups).
See `README.md` and `ROADMAP.md` for details.

## Current phase

For current phase, status, decisions, and next step, see `docs/agent-state.md`.

## Local laptop environment

Primary local development happens on a Windows 11 laptop.

- Shell: PowerShell.
- Python: 3.12, managed via `uv`. Run tools through `uv run <tool>`; do not use a
  global Python interpreter.
- Version control: `git`. Default branch: `main`.
- GitHub CLI: `gh`.
- Windows package manager for system tools: `winget`.
- Local validation script: `scripts/check_local.ps1`.
- Preferred validation commands:
  - `uv sync --extra dev`
  - `uv run ruff check .`
  - `uv run pytest`

Do not install or configure GPU runtime dependencies on the Windows laptop unless
explicitly requested.

## Shared rules

All shared rules — scope boundaries, file roles, agent state protocol,
secrets/results policy, commit conventions, validation — live in `CLAUDE.md`.
Read it before non-trivial work.

## Response format

When you finish, report:

1. files created/changed,
2. commands run,
3. checks passed/failed,
4. next recommended command for the user.
