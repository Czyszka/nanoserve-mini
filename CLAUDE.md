# CLAUDE.md

Project entrypoint for Claude Code.

## Working principles

- State assumptions explicitly; if a choice is unclear or a GPU slot is at
  stake, ask before acting rather than guessing silently.
- Simplicity first: minimum change that solves the task; nothing speculative.
  Treat scope creep as the default failure mode, not the exception.
- Surgical edits: touch only what the task needs; clean up only the mess your
  own change introduced — never silently rewrite unrelated or shared work.

## Project

`nanoserve-mini` — 12-week LLM inference performance lab. vLLM serving
baseline, observability, benchmark harness, workload + KV/prefix cache
analysis, one Triton kernel, technical write-ups, final decision doc.
Standalone portfolio artifact and a decision gate for a possible full
`nanoserve` follow-up.

## Required reading at session start

Before proposing or making changes, read:

1. `docs/operations/agent-state.md` — current phase, status, next steps, open blockers.
2. `docs/project/roadmap.md` — scope, definition of done, phase plan, decision points.
3. `docs/operations/infrastructure.md` — machine roles, workflow, secrets policy.
4. `AGENTS.md` — Codex entrypoint (may carry recent operational rules shared across agents).

Then summarise the current state in 3-5 bullets before proposing work.

## Machines

- **Windows 11 laptop** — dev, docs, analysis, benchmark script preparation.
  `rg` (ripgrep) is installed and on `PATH` (PowerShell and cmd).
- **Ubuntu 24 server, 8×H200 NVL** — primary GPU execution environment.
- **Optional GPU cloud** — support buffer for off-hours tests; not the primary path.

## Python workflow

- Use `uv` on both laptop and server.
- Prefer `uv run …` over global Python.
- Do not install global Python packages.
- Do not add GPU-heavy dependencies to the laptop environment.

## Standard validation

**Code changes** (`benchmarks/scripts/`, `benchmarks/scripts_tests/`, any `.py`):

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

**Config / infra changes** (`.gitignore`, `*.yml`, `*.yaml`, `*.json` compose or
provisioning files, `pyproject.toml`, `Dockerfile`): `git diff --check` is
sufficient. No `ruff` / `pytest` needed unless the change also touches `.py` files.

**Documentation-only changes** (`docs/`, `*.md`, `serving/runbooks/`):
`git status` + `git diff --check` only. Add `ruff` / `pytest` only when the
change also touches executable examples, test fixtures, or generated artefacts.

## Repository layout

```text
benchmarks/scripts/         CLI benchmark + metrics producers and shared library.
benchmarks/scripts_tests/   Pytest suite for the above (mocked, runs on laptop).
serving/compose/            Docker Compose: vLLM, OpenWebUI, LiteLLM Proxy, Prometheus, Grafana.
serving/runbooks/           Operational instructions.
results/raw/                Raw snapshots (metric dumps, env snapshots).
results/runs/               Per-run benchmark artifacts (JSON/JSONL/CSV/MD — commit small files).
results/summaries/          Cross-run aggregated summaries.
docs/{project,operations,learning,plans,templates,weekly}/
```

## Scope boundaries

The roadmap (`docs/project/roadmap.md`) is authoritative on scope. Two
sections matter most:

- **"W scope dzięki projektowi firmowemu"** — multi-GPU / TP scaling,
  MoE serving, FP8 quantization, multi-tenant routing are *in scope as
  synthesis material* measured on the company H200 stack. Do not stand
  up new experiments for these on the private project, but expect
  results and write-ups to reference them.
- **"Świadomie poza scope"** — own inference engine, full PagedAttention
  reimplementation, Kubernetes / Helm / GPU Operator, fused attention as
  the first kernel, TensorRT-LLM / SGLang, speculative decoding beyond
  the documented Kimi Eagle3 baseline, disaggregated serving, production
  HA / autoscaling / multi-region, full prefix-cache reimplementation.
  Do not add or implement these unless the user explicitly asks.

Do not rewrite `docs/project/roadmap.md` unless explicitly asked.

## Immediate project state

For current phase, status, decisions, and the next concrete step, see
`docs/operations/agent-state.md`. Do not duplicate that content here.

## Agent state protocol

`docs/operations/agent-state.md` is the shared, repo-tracked memory for
all coding agents.

File roles:

- `CLAUDE.md` — stable instructions for Claude Code (this file).
- `AGENTS.md` — stable instructions for Codex.
- `docs/operations/agent-state.md` — pointer + "In flight" live status; NOT a task
  list. Update at end of every meaningful task.
- `docs/project/roadmap.md` — project scope.
- **GitHub issues** — *what* and *why*; acceptance criteria; durable across sessions.
  Open = active, closed = done. Source of record for decisions and rationale.
- **`docs/plans/<date>-<slug>.md`** — *how* and *when* for one session (commands,
  order, time budget). Lifecycle: draft → active → closed. Freezes after a session as
  a status record; never restates issue rationale — references by issue number instead.

Division of labour: issue answers "what and why", plan answers "how and when",
`agent-state.md` answers "where are we right now".

Procedure:

- **At the start of a task**: read `agent-state.md`, verify it matches the
  current repo state, and avoid duplicating stale assumptions.
- **At the end of a meaningful task**: update `agent-state.md` with what
  changed, commands run, validation results, new decisions, the next
  recommended action, and any open blockers — before committing or
  handing work over.

Keep `agent-state.md` concise — handoff document, not a diary. For
periodic compaction use `docs/templates/tidy-docs-agent.md`.

## Results and secrets policy

Never commit:

- `.env`, API keys, Hugging Face tokens, GitHub / W&B / cloud tokens,
- model weights, Hugging Face cache,
- large logs, full Nsight traces (`*.ncu-rep`, `*.nsys-rep`),
- database dumps, large benchmark artefacts.

Do commit:

- `.env.example` (no real values),
- small JSON / JSONL / CSV results when useful,
- short text snapshots, summaries (Markdown / CSV),
- benchmark configs and the commands used to run them,
- scripts,
- Markdown write-ups,
- reproducibility metadata (e.g. `record_environment.json` per run).

If a result is large, commit only the summary, run identifier / git
hash, local path, and instructions to reproduce.

If a secret leaks, rotate it (HF / GitHub / W&B / cloud) and audit git
history for further exposure.

## Git rules

Before editing:

```bash
git status
```

Before finishing any change, run validation matching the change type —
see **Standard validation** above. For config and doc-only changes
`git diff --check` is sufficient; `ruff` / `pytest` only for `.py` changes.

Use small commits. Preferred prefixes:

- `docs:`, `feat:`, `fix:`, `bench:`, `infra:`, `chore:`, `refactor:`.

Do not push secrets or machine-local files.

## Communication style

Be concise and operational. When reporting work, include:

1. files changed,
2. commands run,
3. checks passed / failed,
4. next step.
