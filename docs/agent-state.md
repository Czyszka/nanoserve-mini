# Agent State - nanoserve-mini

This file is the repo-tracked handoff state for Claude Code, Codex, and human work.

Keep it concise and current. Update it after meaningful repo changes, especially before
committing, pushing, or handing work to another agent.

---

## Canonical file roles

- `CLAUDE.md` - stable instructions for Claude Code.
- `AGENTS.md` - stable instructions for Codex.
- `docs/agent-state.md` - current project state, decisions, next step, and blockers.
- `ROADMAP.md` - project scope; do not change it without an explicit decision.

Note: the current roadmap content in this repo is stored as `docs/ROADMAP_v_1_0.md`.
Treat it as the current scope document unless a root `ROADMAP.md` is added later.

---

## Current phase

Bootstrap / Phase 1 preparation.

The current goal is to keep the repo organized, finish the GitHub-facing description,
and prepare for the first server environment snapshot before the first vLLM run.

---

## Current known status

- GitHub repo exists: `https://github.com/Czyszka/nanoserve-mini.git`
- Local Windows laptop bootstrap is done.
- Python workflow uses `uv`.
- `ruff` and `pytest` are configured and pass locally.
- `README.md` exists with the project overview, local workflow, and suggested GitHub description.
- `CLAUDE.md` exists as the Claude Code entrypoint.
- `AGENTS.md` exists as the Codex instruction file.
- `docs/agent-state.md` is the shared handoff/status file.
- `.gitattributes` exists to normalize line endings.
- Server access is expected later this week.
- Server has Ubuntu 24 and 8x H200 NVL, but the repo has not yet recorded an environment snapshot from it.
- Current uncommitted files include modified `AGENTS.md` plus untracked `README.md`,
  `CLAUDE.md`, `docs/agent-state.md`, and `claude_code_integration_files.zip`.

---

## Important project docs

Read these before making non-trivial changes:

- `docs/ROADMAP_v_1_0.md` - current scope, phases, and definition of done.
- `docs/infrastructure_v_1_0.md` - machine roles and workflow.
- `docs/reading-list.md` - papers by phase.
- `docs/nvidia_self_paced_courses.md` - optional NVIDIA courses.
- `AGENTS.md` - Codex-specific repo instructions.
- `CLAUDE.md` - Claude Code-specific repo instructions.

Do not rewrite the roadmap/scope document unless explicitly asked.

---

## Current technical direction

Do not start vLLM setup until the server environment is captured.

Immediate milestone:

1. commit and push the README / agent coordination docs,
2. run `scripts/check_server_env.py` on the server when available,
3. commit `results/raw/server_env_snapshot.json` from the server if it is small and useful,
4. decide vLLM setup path: Docker vs uv/native.

---

## Standard commands

Local / laptop:

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

Server, once available:

```bash
git clone https://github.com/Czyszka/nanoserve-mini.git
cd nanoserve-mini
uv sync --extra dev
uv run python scripts/check_server_env.py
```

---

## Current decisions

| Area | Decision |
|---|---|
| Central sync | GitHub repo |
| Laptop role | dev, docs, analysis |
| Server role | primary GPU execution |
| Optional cloud | backup GPU access only |
| Python workflow | uv on laptop and server |
| Heavy GPU deps | not in laptop base config |
| vLLM setup | decide after server snapshot |
| Agent memory | `docs/agent-state.md` is repo-tracked shared handoff |
| Claude Code entrypoint | root `CLAUDE.md` |
| Codex entrypoint | root `AGENTS.md` |
| State updates | Codex and Claude Code must update `docs/agent-state.md` after meaningful work and before commit/push handoff |

---

## Open questions

- [ ] Is server Docker installed and usable?
- [ ] Does `nvidia-smi` show all 8x H200 NVL?
- [ ] Which Python version is available on the server?
- [ ] Does `uv sync --extra dev` work on the server?
- [ ] Should vLLM be launched via Docker or uv/native?
- [ ] Should raw result files be committed directly or summarized after first GPU run?
- [ ] Should the roadmap be copied/renamed to root `ROADMAP.md`, or should `docs/ROADMAP_v_1_0.md` remain canonical?

---

## Last validation

Latest known local validation from laptop:

```text
uv sync --extra dev     OK
uv run ruff check .     OK
uv run pytest           OK, 1 passed
```

Most recent focused validation:

```text
uv run ruff check .     OK
uv run pytest           OK, 1 passed
```

---

## Handoff log

### 2026-05-03 - bootstrap state

- Local repo was initialized and pushed to GitHub.
- Codex bootstrap created repo configuration.
- `.gitattributes` was added after LF/CRLF warnings.
- `scripts/check_server_env.py` exists for the first H200 server environment snapshot.

### 2026-05-03 - README and shared agent state

- `README.md` was added with project overview, local workflow, repo layout, and suggested GitHub description.
- `CLAUDE.md` was added as the Claude Code entrypoint.
- `docs/agent-state.md` was verified and updated as the shared handoff file for Codex, Claude Code, and human work.
- `AGENTS.md` and `CLAUDE.md` now require updating `docs/agent-state.md` after meaningful work and before commit/push handoff.
