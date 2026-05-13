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

1. `docs/project/roadmap.md` or the current roadmap/scope document named in
   `docs/operations/agent-state.md`
2. the current infrastructure/workflow document named in
   `docs/operations/agent-state.md`
3. `docs/operations/agent-state.md`
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

Standard local validation for code changes:

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

For documentation-only changes, do not run `ruff` or `pytest` unless the change
touches executable examples, generated docs, or code-adjacent configuration.
Use documentation-appropriate checks instead, such as `git diff --check`,
Markdown link checks, or rendering checks when relevant.

## Scope boundaries

Do not add or implement unless explicitly requested:

- custom inference engine,
- TensorRT-LLM,
- SGLang integration,
- Kubernetes,
- new multi-GPU / tensor parallelism experiments beyond the documented Kimi TP=8 baseline,
- FP8 quantization,
- MoE,
- new speculative decoding experiments beyond the documented Kimi Eagle3 baseline,
- production HA/autoscaling,
- large cloud infrastructure.

Do not rewrite `docs/project/roadmap.md` unless explicitly asked.

## Immediate project state

For current phase, status, decisions, and next step, see
`docs/operations/agent-state.md`.
Do not duplicate that content here.

## Agent state protocol

`docs/operations/agent-state.md` is the shared, repo-tracked memory for all coding agents.

File roles:

- `CLAUDE.md` - stable instructions for Claude Code.
- `AGENTS.md` - stable instructions for Codex.
- `docs/operations/agent-state.md` - current project state, decisions, next step, and blockers.
- `docs/project/roadmap.md` - project scope; do not change it without an explicit decision.

At the beginning of a task:

1. read `docs/operations/agent-state.md`,
2. verify whether it matches the current repo state,
3. avoid duplicating stale assumptions.

At the end of a meaningful task, update `docs/operations/agent-state.md` with:

- what changed,
- commands run,
- validation results,
- new decisions,
- next recommended action,
- open blockers.

Always update `docs/operations/agent-state.md` before committing, pushing, or handing work
to another agent when the task changed the repository state.

Keep `docs/operations/agent-state.md` concise. It should be a handoff document, not a full
diary.

For periodic documentation hygiene, use `docs/templates/tidy-docs-agent.md`.

## Results and secrets policy

Never commit:

- `.env`,
- API keys,
- Hugging Face tokens,
- GitHub tokens (or W&B / cloud provider credentials),
- model weights,
- Hugging Face cache,
- large logs,
- full Nsight traces (`*.ncu-rep`, `*.nsys-rep`),
- database dumps,
- large benchmark artifacts.

Commit:

- `.env.example` (no real values),
- small JSON/JSONL/CSV results when useful,
- short text snapshots,
- summaries (markdown / CSV),
- benchmark configs and the commands used to run them,
- scripts,
- markdown write-ups,
- reproducibility metadata (e.g. `record_environment.json` per run).

If a result is large, commit only the summary, the run identifier / git hash, the
local path, and instructions to reproduce.

If a secret leaks, rotate it (HF token, GitHub key/token, W&B / cloud token if used)
and audit git history for further exposure.

## Git rules

Before editing:

```bash
git status
```

Before finishing code changes:

```bash
uv run ruff check .
uv run pytest
git status
```

Before finishing documentation-only changes, `git status` and
`git diff --check` are sufficient by default. Run `ruff` and `pytest` only when
the documentation change also affects code, scripts, test fixtures, generated
artifacts, or executable snippets.

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
