# AGENTS.md

This file is the project entrypoint for Codex.

## Project

`nanoserve-mini` is a 12-week LLM inference performance lab (vLLM serving baseline,
observability, benchmarks, workload/cache analysis, one Triton kernel, write-ups).
See `README.md` and `docs/project/roadmap.md` for details.

## Current phase

For current phase, status, decisions, and next step, see
`docs/operations/agent-state.md`.

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

All shared rules - scope boundaries, file roles, agent state protocol,
secrets/results policy, commit conventions, validation - live in `CLAUDE.md`.
Read it before non-trivial work.

Do not commit secrets, model weights, Hugging Face caches, large benchmark artifacts,
large logs, Nsight traces, database dumps, or unrelated local files. Commit only
small reproducibility artifacts, summaries, scripts, documentation, and sanitized
configuration examples.

## Human + Codex collaboration workflow

GitHub is the single source of truth for project work. The intended collaboration
flow is:

1. The human works primarily from the Windows 11 laptop.
2. The human discusses task design, scope, risks, and acceptance criteria with
   ChatGPT before implementation.
3. ChatGPT helps turn the agreed task into a small, scoped GitHub issue.
4. Codex App implements one scoped issue on a dedicated branch.
5. Codex App opens a pull request with a concise summary and validation results.
6. The human reviews the pull request manually.
7. The human requests a second-pass review with Codex PR review when the PR is
   ready for another automated check.
8. The human merges only after validation and review are acceptable.

Good Codex-sized tasks include updating one document, adding one small script,
adding or adjusting tests, improving benchmark metadata logging, making a small
scoped refactor, or updating docs after a repository structure change.

Bad Codex-sized tasks include improving the whole architecture, optimizing
everything, rewriting the benchmark system, cleaning up the whole repo, or doing
work that requires GPU access unless the GPU session is explicitly prepared.

## Response format

When you finish, report:

1. files created/changed,
2. commands run,
3. checks passed/failed,
4. next recommended command for the user.
