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
- `README.md`, `CLAUDE.md`, `AGENTS.md`, and `docs/agent-state.md` are committed and pushed to GitHub.
- `.gitattributes` exists to normalize line endings.
- Server access is expected later this week.
- Server has Ubuntu 24 and 8x H200 NVL, but the repo has not yet recorded an environment snapshot from it.
- Working tree is clean; branch is up to date with `origin/main`.

---

## Important project docs

Read these before making non-trivial changes:

- `docs/ROADMAP_v_1_0.md` - current scope, phases, and definition of done.
- `docs/infrastructure_v_1_0.md` - machine roles and workflow.
- `docs/server-first-session.md` - runbook for the first server session (env snapshot + vLLM setup decision).
- `docs/reading-list.md` - papers by phase.
- `docs/nvidia_self_paced_courses.md` - optional NVIDIA courses.
- `AGENTS.md` - Codex-specific repo instructions.
- `CLAUDE.md` - Claude Code-specific repo instructions.

Do not rewrite the roadmap/scope document unless explicitly asked.

---

## Current technical direction

Do not start vLLM setup until the server environment is captured.

Immediate milestone:

1. README and agent coordination docs are committed and pushed (done).
2. Laptop-safe scaffolding for the first server session is committed:
   `docs/server-first-session.md`, `scripts/__init__.py`, `scripts/_client.py`,
   `scripts/_metrics.py`, `scripts/request_once.py`,
   `scripts/measure_ttft_once.py`, `scripts/run_sequential_benchmark.py`
   plus tests with httpx.MockTransport (done).
3. run `uv run python -m scripts.check_server_env` on the server when available,
4. commit `results/raw/server_env_snapshot.json` from the server if it is small and useful,
5. decide vLLM setup path: Docker vs uv/native (follow `docs/server-first-session.md`),
6. once vLLM is up:
   `uv run python -m scripts.request_once` ->
   `uv run python -m scripts.measure_ttft_once` ->
   `uv run python -m scripts.run_sequential_benchmark`.

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
uv run python -m scripts.check_server_env
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

Most recent local validation (2026-05-03, laptop, after D1-D4 + review fixes):

```text
uv sync --extra dev     OK
uv run ruff check .     OK, all checks passed
uv run pytest           OK, 32 passed
```

Module-execution smoke-checked locally with `python -m scripts.<name> --help`
for every entry-point script.

---

## Handoff log

### 2026-05-03 - bootstrap state

- Local repo was initialized and pushed to GitHub.
- Codex bootstrap created repo configuration.
- `.gitattributes` was added after LF/CRLF warnings.
- `scripts/check_server_env.py` exists for the first H200 server environment snapshot. (Run as `python -m scripts.check_server_env` after the review-fix entry made the `scripts/` package importable.)

### 2026-05-03 - README and shared agent state

- `README.md` was added with project overview, local workflow, repo layout, and suggested GitHub description.
- `CLAUDE.md` was added as the Claude Code entrypoint.
- `docs/agent-state.md` was verified and updated as the shared handoff file for Codex, Claude Code, and human work.
- `AGENTS.md` and `CLAUDE.md` now require updating `docs/agent-state.md` after meaningful work and before commit/push handoff.

### 2026-05-03 - coordination docs committed and pushed

- `README.md`, `CLAUDE.md`, `AGENTS.md`, and `docs/agent-state.md` are now committed to the repo and pushed to GitHub (`origin/main`).
- Working tree clean on branch `claude/vigorous-margulis-ac5191`.
- Local validation re-run on laptop: `uv sync --extra dev` OK, `uv run ruff check .` OK, `uv run pytest` OK (1 passed).
- Next recommended action: when the server is available, run `uv run python -m scripts.check_server_env` and capture `results/raw/server_env_snapshot.json`. (Module-execution form was introduced in the later "review fixes" entry; the older path-based form `python scripts/check_server_env.py` is no longer the canonical invocation.)

### 2026-05-03 - first-server-session scaffolding (D1-D4)

Four laptop-safe artifacts added across four commits, all pushed to `origin/main`:

- D1 `docs/server-first-session.md` - strict runbook for the first H200 slot
  (clone -> uv sync -> env snapshot -> commit -> Docker vs uv/native decision).
  No vLLM install, no model downloads, no observability stack in that session.
- D2 `scripts/_client.py` + `scripts/request_once.py` - shared HTTP client for
  the OpenAI-compatible vLLM endpoint and a single non-streaming smoke script.
- D3 `scripts/_metrics.py` + `scripts/measure_ttft_once.py` - Benchmark
  Contract record shape (`RunControls`, `summarize`, `percentile`) and a
  one-shot streaming TTFT/E2E measurement that writes
  `results/raw/first_ttft.json`. TTFT is anchored on the first chunk with
  non-empty `delta.content`, so role-only chunks don't pollute the metric.
- D4 `scripts/run_sequential_benchmark.py` - 1 warmup + N measured sequential
  streaming requests, JSONL of every run + `summary.json` with p50/p95/min/max/
  mean for TTFT and E2E. Errors are captured per-run and don't abort the loop.

Test coverage: 30 tests total, all using `httpx.MockTransport` so the laptop
gate (`uv run ruff check .` + `uv run pytest`) covers request shaping,
streaming SSE parsing, percentile math, JSONL/summary write paths, and the
CLI entry points. No real network or GPU dependency on laptop.

Validation (laptop, 2026-05-03):

```text
uv run ruff check .     OK, all checks passed
uv run pytest           OK, 30 passed
```

Next recommended action: when the server is available, work through
`docs/server-first-session.md` step-by-step.

### 2026-05-03 - review fixes (CLI import + JSON strictness)

Two laptop-safe corrections before the first H200 server slot:

- `scripts/__init__.py` added so `scripts._client` and `scripts._metrics`
  are importable as a real package. All entry-point scripts are now
  invoked via module execution (`uv run python -m scripts.<name>`) in
  `README.md`, `docs/server-first-session.md`, every script docstring,
  and the "Standard commands" block above. This avoids brittle path
  invocations that break the relative imports.
- `scripts/_metrics.py` no longer emits `float('nan')` from
  `percentile()` / `summarize()`; empty input now returns `None`
  (serializes as JSON `null`). `RunRow.e2e_seconds` for errored runs is
  also `None`. JSON writers in `measure_ttft_once.py` and
  `run_sequential_benchmark.py` now use `allow_nan=False` so any future
  regression that reintroduces NaN raises at write time instead of
  silently producing invalid JSON.

New tests cover strict-JSON round-trip for empty summaries and for
errored-run JSONL rows. Module-execution paths smoke-checked locally
with `python -m scripts.<name> --help`.

Validation (laptop, 2026-05-03, after fixes):

```text
uv sync --extra dev     OK
uv run ruff check .     OK, all checks passed
uv run pytest           OK, 32 passed
```
