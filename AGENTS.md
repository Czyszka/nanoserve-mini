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
- Preferred validation commands for code changes:
  - `uv sync --extra dev`
  - `uv run ruff check .`
  - `uv run pytest`

For documentation-only changes, do not run `ruff` or `pytest` unless the change
touches executable examples, generated docs, or code-adjacent configuration.
Use documentation-appropriate checks instead, such as `git diff --check`,
Markdown link checks, or rendering checks when relevant.

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
5. Codex App opens a draft pull request with a concise summary and validation
   results.
6. Codex App performs its own final PR review. If the ready-for-review gate
   passes, Codex App marks the PR ready for review without waiting for the human
   to do that bookkeeping.
7. The human reviews the pull request manually.
8. The human requests a second-pass review with Codex PR review when the PR is
   ready for another automated check.
9. The human merges only after validation and review are acceptable.

Good Codex-sized tasks include updating one document, adding one small script,
adding or adjusting tests, improving benchmark metadata logging, making a small
scoped refactor, or updating docs after a repository structure change.

Bad Codex-sized tasks include improving the whole architecture, optimizing
everything, rewriting the benchmark system, cleaning up the whole repo, or doing
work that requires GPU access unless the GPU session is explicitly prepared.

## Codex team workflow

Codex can work in two modes:

- **Solo lead mode**: the main Codex agent completes the task directly.
- **Team mode**: the main Codex agent acts as team lead and delegates narrow,
  parallel work to sub-agents.

Start each non-trivial task with a quick triage. Use solo lead mode when the task is
small, linear, limited to one or a few closely related files, and easy to validate
end to end. Use team mode when the task spans multiple independent areas, benefits
from parallel inspection, has meaningful regression risk, or touches multiple
layers such as docs, code, tests, CI, or infrastructure.

The team lead is responsible for:

- defining scope, out-of-scope boundaries, risks, and acceptance criteria,
- inspecting the repo before editing,
- splitting work into independent areas of ownership,
- integrating sub-agent findings or patches,
- keeping the final diff small and aligned with project conventions,
- running the right validation for the change type,
- preparing the commit, push, pull request, and final review status.

Sub-agents should receive concrete, bounded tasks. Good examples include checking
one documentation subtree for stale links, reviewing one module for edge cases,
adding tests for one behavior, or inspecting one failing CI job. Avoid broad
assignments such as "clean up the repo", "improve the architecture", or "optimize
everything".

Sub-agent instructions must specify:

- the exact files, directories, or subsystem owned by that sub-agent,
- whether the sub-agent should inspect only or edit files,
- the expected output format,
- any scope boundaries or files it must not touch.

For inspect-only delegation, sub-agents should report concrete findings in this
format: problem, location, proposed fix. They should not make scope decisions.

For implementation delegation, assign disjoint write areas and tell sub-agents that
other agents may be working in the repo at the same time. They must not revert or
overwrite unrelated changes.

The team lead integrates centrally. Sub-agents improve parallelism and coverage,
but the lead owns final decisions, consistency, validation, and the pull request.

Codex should usually open a draft PR first, then perform a final self-review of the
PR as team lead. Before marking a PR ready for review, the team lead must verify:

- the diff matches the agreed scope,
- validation has passed or skipped checks are explicitly justified,
- the branch is pushed,
- the PR is mergeable or any blocker is clearly documented,
- the PR summary lists changed areas, commands run, and validation results.

If the gate passes, Codex should mark the PR ready for review itself. If the gate
fails, leave the PR as draft and document the blocker in the PR or final response.

## Response format

When you finish, report:

1. files created/changed,
2. commands run,
3. checks passed/failed,
4. next recommended command for the user.
