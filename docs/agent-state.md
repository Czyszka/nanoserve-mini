# Agent State - nanoserve-mini

This file is the repo-tracked handoff state for Claude Code, Codex, and human work.

Keep it concise and current. Update it after meaningful repo changes, especially before
committing, pushing, or handing work to another agent.

The `sync-state` routine (see `docs/templates/sync-state-agent.md`) appends to
this file. The `tidy-docs` routine (see `docs/templates/tidy-docs-agent.md`)
compacts it in place. Git is the archive — no separate handoff archive directory.

---

## Summary cursor

- Last summarized commit: `1ba9cc6`
- Last summarized at: 2026-05-06

The `sync-state` routine reads this block to find the diff window. Update only
via the routine.

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

**Phase 1 - first vLLM run completed; first interactive serving available.**

Server is up, environment snapshot is committed, Docker vLLM image is installed,
Kimi-K2.6 is downloaded and served successfully through vLLM with TP=8.
OpenWebUI is running on the server and connected to the vLLM OpenAI-compatible endpoint.

---

## Current known status

- GitHub repo exists: `https://github.com/Czyszka/nanoserve-mini.git`
- Local Windows laptop bootstrap is done.
- Python workflow uses `uv`.
- `ruff` and `pytest` are configured and pass locally.
- `README.md`, `CLAUDE.md`, `AGENTS.md`, and `docs/agent-state.md` are committed and pushed to GitHub.
- `.gitattributes` exists to normalize line endings.
- Local research PDFs are kept outside Git in ignored `docs/papers/`.
- **Server is available**: ubuntusrv2 (Ubuntu 24.04, 8x H200 NVL 143 GB, CUDA 13.2, driver 595.58.03).
- **`results/raw/server_env_snapshot.json` committed** (2026-05-06); generated
  with `scripts/check_server_env.py` on ubuntusrv2 and records Ubuntu 24.04.2,
  Python 3.12.11, uv 0.11.8, Docker 28.5.0 / Compose v2.39.4, 8x H200 NVL,
  driver 595.58.03, CUDA 13.2.
- **vLLM Docker image installed** on the server (`vllm/vllm-openai:v0.20.0-cu130`).
- **Kimi-K2.6 model download completed** in named volume `nanoserve-hf-cache`.
- **Kimi-K2.6 serves successfully through `vllm serve` with TP=8.**
- **Single-node DEP attempt did not work** for this run; current working path is TP=8.
- **Speculative decoding works correctly** with the Eagle3 speculative head
  (`lightseekorg/kimi-k2.6-eagle3-mla`).
- **OpenWebUI container is running on the server** and connected to `vllm serve`;
  Kimi-K2.6 is visible in OpenWebUI and answers requests.
- Current Kimi-K2.6 launch parameters still need tuning, especially GPU memory
  reservation/utilization, so a second smaller model can fit on the same server.
- Compose file currently tracked for the earlier DEP attempt:
  `infra/compose/docker-compose.kimi-k2.6.yml`.
- `.claude/` remains untracked locally.

---

## Important project docs

Read these before making non-trivial changes:

- `docs/ROADMAP_v_1_0.md` - current scope, phases, and definition of done.
- `docs/infrastructure_v_1_0.md` - machine roles and workflow.
- `docs/runbooks/server-env-bootstrap.md` - reusable runbook for GPU server env bootstrap (env snapshot + vLLM setup decision).
- `docs/reading-list.md` - papers by phase.
- `docs/nvidia_self_paced_courses.md` - optional NVIDIA courses.
- `AGENTS.md` - Codex-specific repo instructions.
- `CLAUDE.md` - Claude Code-specific repo instructions.

Do not rewrite the roadmap/scope document unless explicitly asked.

---

## Current technical direction

Server is active. vLLM Docker is installed. Kimi-K2.6 is serving successfully with TP=8.
OpenWebUI is connected and can be used for interactive checks.

Immediate next steps (in order):

1. Record the exact working TP=8 `vllm serve` command and runtime parameters
   in `infra/compose/README.md` or a dedicated TP=8 compose/runbook file.
2. Tune launch parameters, especially GPU memory utilization/reservation, to
   leave room for a second smaller model.
3. Smoke test API path explicitly: `curl http://localhost:8000/v1/models`
4. First scripted inference: `uv run python -m scripts.request_once`
5. First TTFT measurement: `uv run python -m scripts.measure_ttft_once`
6. Sequential benchmark: `uv run python -m scripts.run_sequential_benchmark`

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
| vLLM setup | **Docker** (`vllm/vllm-openai:v0.20.0-cu130`) |
| vLLM strategy | **Working: `vllm serve` with TP=8 + Eagle3 speculative decoding**; single-node DEP was tried and did not work |
| Model | `moonshotai/Kimi-K2.6` + `lightseekorg/kimi-k2.6-eagle3-mla` |
| HF weights storage | named Docker volume `nanoserve-hf-cache` |
| Compose file | `infra/compose/docker-compose.kimi-k2.6.yml` currently documents the earlier DEP attempt; TP=8 working config still needs to be recorded |
| Interactive UI | OpenWebUI container connected to vLLM OpenAI-compatible endpoint |
| Agent memory | `docs/agent-state.md` is repo-tracked shared handoff |
| Claude Code entrypoint | root `CLAUDE.md` |
| Codex entrypoint | root `AGENTS.md` |
| State updates | Codex and Claude Code must update `docs/agent-state.md` after meaningful work and before commit/push handoff |
| Local papers | Store read scientific papers in ignored `docs/papers/`; commit bibliographic notes/summaries separately if useful |

---

## Open questions

- [ ] Record exact working TP=8 server command/config in repo.
- [ ] Which Kimi-K2.6 `vllm serve` memory parameters allow a second smaller
  model to fit on the same server?
- [ ] Does `uv sync --extra dev` work on the server? (not yet tested, not blocking)
- [ ] Should raw result files be committed directly or summarized after first GPU run?

---

## Last validation

Most recent local validation (2026-05-07, Claude Code):

```text
uv run ruff check .     OK, all checks passed
uv run pytest           OK, 46 passed
```

---

## Handoff log

Newest entry first. Appended by the `sync-state` routine
(`docs/templates/sync-state-agent.md`); compacted in place by the `tidy-docs`
routine (`docs/templates/tidy-docs-agent.md`). Git is the archive.

### 2026-05-07 - Normalize mlperf-lite benchmark outputs

- Why: bring all three benchmark scripts to consistent `methodology`, `benchmark_mode`, `--run-id`, and `git_commit` support per task spec.
- Did: extended `RunControls` in `scripts/_metrics.py` with `run_id`, `script_name`, `git_commit` and added `get_git_commit()` (best-effort) and `resolve_output_path()` helpers; updated `request_once.py` to write JSON (schema `nanoserve-mini.request-once.v1`, mode `singlestream_lite_correctness`) with `--output`/`--run-id` flags; updated `measure_ttft_once.py` to add `methodology`, `benchmark_mode`, `error: null`, `--run-id` and controls fields; updated `run_sequential_benchmark.py` to schema v2 (`sequential-bench.v2` / `sequential-bench-row.v2`), mode `singlestream_lite_repeated`, `--run-id`, wall-clock throughput in summary; updated all tests (46 pass); added `--run-id` output layout section to `docs/benchmark-methodology.md`.
- Commands run: `uv run ruff check .` (pass), `uv run pytest` (46 passed, up from 32).
- Next: run first live benchmark against vLLM endpoint using `--run-id` to verify end-to-end write path on the server.

### 2026-05-06 - Current server state confirmed

- Why: make the live server state explicit before planning further tests.
- Did: recorded that Kimi-K2.6 is downloaded and running via `vllm serve` with TP=8; DEP did not work; OpenWebUI is connected and interactive; `check_server_env.py` output is saved in `results/raw/server_env_snapshot.json`.
- Snapshot: Ubuntu 24.04.2, Python 3.12.11, uv 0.11.8, Docker 28.5.0 / Compose v2.39.4, 8x H200 NVL 143771 MiB, driver 595.58.03, CUDA 13.2.
- Validation: local docs check only; no server benchmark run in this update.
- Next: capture the exact working `vllm serve` command, tune GPU memory settings for a second model, then run smoke/TTFT/sequential benchmark scripts.

### 2026-05-06 - Codex pull review and repo cleanup

- Why: sync local laptop with Claude's latest work and remove obsolete/redundant repo artifacts.
- Did: pulled `origin/main` to `1ba9cc6`, verified tidy-docs/sync-state additions, removed `CODEX_BOOTSTRAP_CONFIG_TASK.md`, removed tracked `docs/handoff-archive/2026-05.md`, and restored current server status to TP=8/OpenWebUI.
- Note: current templates now say Git is the archive; no separate handoff archive
  directory should be recreated. Tracked `.claude/commands/sync-state.md` and
  `.claude/settings.json` remain present; tidy-docs slash command was not tracked.
- Validation: skipped (docs-only cleanup).
- Next: commit the exact working TP=8 launch configuration, then run scripted smoke/TTFT/benchmark commands against the live vLLM endpoint.

> Pre-2026-05-06 handoff entries compacted. Source: `90d3fcdf8767baa09f53f537a686b165466786fc`.
> Full history: `git show 90d3fcdf8767baa09f53f537a686b165466786fc:docs/agent-state.md`.
