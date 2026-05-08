# Agent State - nanoserve-mini

This file is the repo-tracked handoff state for Claude Code, Codex, and human work.

Keep it concise and current. Update it after meaningful repo changes, especially before committing, pushing, or handing work to another agent.

The `sync-state` routine (see `docs/templates/sync-state-agent.md`) appends to this file. The `tidy-docs` routine (see `docs/templates/tidy-docs-agent.md`) compacts it in place. Git is the archive — no separate handoff archive directory.

---

## Summary cursor

- Last summarized commit: `f83ef7a`
- Last summarized at: 2026-05-08

The `sync-state` routine reads this block to find the diff window. Update only via the routine.

---

## Canonical file roles

- `CLAUDE.md` - stable instructions for Claude Code.
- `AGENTS.md` - stable instructions for Codex.
- `docs/agent-state.md` - current project state, decisions, next step, and blockers.
- `ROADMAP.md` - project scope; do not change it without an explicit decision.

Note: the current roadmap content in this repo is stored as `docs/ROADMAP_v_1_0.md`. Treat it as the current scope document unless a root `ROADMAP.md` is added later.

---

## Current phase

**Phase 1 - first vLLM run completed; benchmark harness normalization completed; coding-agent task specs tightened.**

Server is up, environment snapshot is committed, Docker vLLM image is installed, Kimi-K2.6 is downloaded and served successfully through vLLM with TP=8.

OpenWebUI is running on the server and connected to the vLLM OpenAI-compatible endpoint.

The repo now has:

- MLPerf-inspired lite output layout for the first benchmark scripts.
- Tightened synthetic coding-agent task specifications for PowerShell, Python, C++, and C#.
- A server work plan for MiniMax-M2.7 / coding-agent / dual-model evaluation.

---

## Current known status

- GitHub repo exists: `https://github.com/Czyszka/nanoserve-mini.git`
- Local Windows laptop bootstrap is done.
- Python workflow uses `uv`.
- `ruff` and `pytest` are configured.
- `.gitattributes` exists to normalize line endings.
- Local research PDFs are kept outside Git in ignored `docs/papers/`.
- **Server is available**: ubuntusrv2 (Ubuntu 24.04, 8x H200 NVL 143 GB, CUDA 13.2, driver 595.58.03).
- **`results/raw/server_env_snapshot.json` committed** (2026-05-06); generated with `scripts/check_server_env.py` on ubuntusrv2 and records Ubuntu 24.04.2, Python 3.12.11, uv 0.11.8, Docker 28.5.0 / Compose v2.39.4, 8x H200 NVL, driver 595.58.03, CUDA 13.2.
- **vLLM Docker image installed** on the server (`vllm/vllm-openai:v0.20.0-cu130`).
- **Kimi-K2.6 model download completed** in named volume `nanoserve-hf-cache`.
- **Kimi-K2.6 serves successfully through `vllm serve` with TP=8.**
- **Single-node DEP attempt did not work** for this run; current working path is TP=8.
- **Speculative decoding works correctly** with Eagle3 speculative head (`lightseekorg/kimi-k2.6-eagle3-mla`).
- **OpenWebUI container is running on the server** and connected to `vllm serve`; Kimi-K2.6 is visible in OpenWebUI and answers requests.
- Current Kimi-K2.6 launch parameters still need tuning, especially GPU memory reservation/utilization, so a second smaller model can fit on the same server.
- Compose file currently tracked for the earlier DEP attempt: `infra/compose/docker-compose.kimi-k2.6.yml`.
- `.claude/` remains untracked locally.
- **Task specs 01-04 are now tightened on `main`:**
  - Task 01 PowerShell export/environment backup.
  - Task 02 Python OpenAI-compatible streaming probe.
  - Task 03 C++ TokenBuffer correctness/safety/hot path.
  - Task 04 C# allocation-aware parser refactor.

---

## Important project docs

Read these before making non-trivial changes:

- `docs/ROADMAP_v_1_0.md` - current scope, phases, and definition of done.
- `docs/infrastructure_v_1_0.md` - machine roles and workflow.
- `docs/runbooks/server-env-bootstrap.md` - reusable runbook for GPU server env bootstrap (env snapshot + vLLM setup decision).
- `docs/benchmark-methodology.md` - MLPerf-inspired lite benchmark modes and `--run-id` layout.
- `docs/plans/2026-05-11-server-work-plan.md` - Monday server work plan: MiniMax-M2.7, coding agent check, dual-model benchmarks.
- `benchmarks/coding-agent-tasks/README.md` - synthetic coding-agent task suite overview.
- `docs/reading-list.md` - papers by phase.
- `docs/nvidia_self_paced_courses.md` - optional NVIDIA courses.
- `AGENTS.md` - Codex-specific repo instructions.
- `CLAUDE.md` - Claude Code-specific repo instructions.

Do not rewrite the roadmap/scope document unless explicitly asked.

---

## Current technical direction

Server is active. vLLM Docker is installed. Kimi-K2.6 is serving successfully with TP=8. OpenWebUI is connected and can be used for interactive checks.

The benchmark scripts use these MLPerf-inspired lite modes:

| Script | Benchmark mode |
|---|---|
| `scripts/request_once.py` | `singlestream_lite_correctness` |
| `scripts/measure_ttft_once.py` | `singlestream_lite_latency` |
| `scripts/run_sequential_benchmark.py` | `singlestream_lite_repeated` |

All three support `--run-id` and write under:

```text
results/runs/<run_id>/<benchmark_mode>/
```

Immediate next steps, in order:

1. On the server, `git pull` latest `main` and run `uv sync --extra dev` if needed.
2. Record the exact working TP=8 `vllm serve` command and runtime parameters in `infra/compose/README.md` or a dedicated TP=8 compose/runbook file.
3. Add metrics scripts:
   - `scripts/collect_metrics_snapshot.py` for GPU/vLLM/Docker/system snapshots.
   - `scripts/sample_gpu_metrics.py` for interval GPU CSV sampling.
4. Download and test `MiniMaxAI/MiniMax-M2.7` as the primary smaller coding model candidate.
5. Check whether already-installed Claude Code CLI can talk to local vLLM; if not, install/use OpenCode fallback.
6. Run the normalized scripts live against vLLM using `--run-id`:
   - `uv run python -m scripts.request_once ... --run-id <run_id>`
   - `uv run python -m scripts.measure_ttft_once ... --run-id <run_id>`
   - `uv run python -m scripts.run_sequential_benchmark ... --run-id <run_id>`
7. Attempt dual-model serving: Kimi-K2.6 + MiniMax-M2.7, then repeat the benchmark sequence with GPU/vLLM metrics.

---

## Standard commands

Local / laptop:

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

Server:

```bash
git pull
uv sync --extra dev
uv run python -m scripts.check_server_env
```

Benchmark examples:

```bash
uv run python -m scripts.request_once \
  --base-url http://127.0.0.1:8000 \
  --model moonshotai/Kimi-K2.6 \
  --run-id 2026-05-11_kimi_tp8_baseline

uv run python -m scripts.measure_ttft_once \
  --base-url http://127.0.0.1:8000 \
  --model moonshotai/Kimi-K2.6 \
  --run-id 2026-05-11_kimi_tp8_baseline

uv run python -m scripts.run_sequential_benchmark \
  --base-url http://127.0.0.1:8000 \
  --model moonshotai/Kimi-K2.6 \
  --warmup 1 --runs 5 \
  --run-id 2026-05-11_kimi_tp8_baseline
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
| Smaller coding model candidate | Primary: `MiniMaxAI/MiniMax-M2.7`; research: `poolside/Laguna-XS.2`; fallback: `Qwen/Qwen3.6-35B-A3B`; stretch: `deepseek-ai/DeepSeek-V4-Flash` |
| HF weights storage | named Docker volume `nanoserve-hf-cache` |
| Compose file | `infra/compose/docker-compose.kimi-k2.6.yml` currently documents the earlier DEP attempt; TP=8 working config still needs to be recorded |
| Interactive UI | OpenWebUI container connected to vLLM OpenAI-compatible endpoint |
| Coding agent | Check Claude Code CLI with local vLLM first; if blocked, use OpenCode fallback |
| Benchmark methodology | MLPerf-inspired lite, not official MLPerf; first modes are SingleStream-lite correctness/latency/repeated |
| Benchmark output | `results/runs/<run_id>/<benchmark_mode>/` |
| Coding tasks | Synthetic, separate temp repo during evaluation; final result compared by model/agent commit |
| Agent memory | `docs/agent-state.md` is repo-tracked shared handoff |
| Claude Code entrypoint | root `CLAUDE.md` |
| Codex entrypoint | root `AGENTS.md` |
| State updates | Codex and Claude Code must update `docs/agent-state.md` after meaningful work and before commit/push handoff |
| Local papers | Store read scientific papers in ignored `docs/papers/`; commit bibliographic notes/summaries separately if useful |

---

## Open questions

- [ ] Record exact working TP=8 server command/config in repo.
- [ ] Which Kimi-K2.6 `vllm serve` memory parameters allow a second smaller model to fit on the same server?
- [ ] Does `uv sync --extra dev` work on the server? (not yet tested, not blocking)
- [ ] Should raw result files be committed directly or summarized after first GPU run?
- [ ] Does Claude Code CLI work directly with local vLLM in this setup, or do we need OpenCode?

---

## Last validation

Most recent validation reported by Claude Code in PR #2 (2026-05-07):

```text
uv run ruff check .     OK, all checks passed
uv run pytest           OK, tests passed
```

Note: after PR #2 review, Claude pushed follow-up fixes for `request_once --raw`, `resolve_output_path(None)`, and measured-only sequential throughput before merge.

The 2026-05-08 task-spec tightening was documentation-only and was applied through GitHub connector commits; `uv run ruff check .` / `uv run pytest` were not rerun after those documentation changes.

---

## Handoff log

Newest entry first. Appended by the `sync-state` routine (`docs/templates/sync-state-agent.md`); compacted in place by the `tidy-docs` routine (`docs/templates/tidy-docs-agent.md`). Git is the archive.

### 2026-05-08 - Tightened all coding-agent task specifications

- Why: close the task-spec review loop before moving to metrics scripts and server execution.
- Did: merged PR #3 for Task 01 PowerShell; applied Task 02 Python, Task 03 C++, and Task 04 C# TASK.md updates directly to `main` because their PRs conflicted only on stale `docs/agent-state.md` hunks; closed PRs #4/#5/#6 as superseded after preserving their intended TASK.md changes.
- Commits: `c149c79` Task 01, `69d9f6f` Task 02, `57a5e0b` Task 03, `f83ef7a` Task 04.
- Current repo state: all four synthetic coding-agent task specs are tightened and ready for starter-repo/hidden-test generation later.
- Validation: not rerun after docs-only updates.
- Next: implement metrics snapshot/sampling scripts, then run live `--run-id` benchmark sequence on the server.

### 2026-05-07 - End-of-day state after benchmark/task merges

- Why: close the session after merging the coding task specs and benchmark script normalization work.
- Did: merged PR #1 (`bfca83b`) with synthetic coding-agent task specs for Python, C++, and C#; merged PR #2 (`fb9f878`) with normalized MLPerf-inspired lite benchmark outputs and `--run-id` support.
- Current repo state: task specs are complete at the specification level; benchmark scripts are ready for live server validation; metrics scripts are still pending.
- Validation: relied on PR #2 reported `ruff`/`pytest` pass; not rerun by ChatGPT connector after merge.
- Next: implement metrics snapshot/sampling scripts, then run live `--run-id` benchmark sequence on the server.

### 2026-05-07 - Normalize mlperf-lite benchmark outputs

- Why: bring all three benchmark scripts to consistent `methodology`, `benchmark_mode`, `--run-id`, and `git_commit` support per task spec.
- Did: extended `RunControls` in `scripts/_metrics.py` with `run_id`, `script_name`, `git_commit` and added `get_git_commit()` (best-effort) and `resolve_output_path()` helpers; updated `request_once.py` to write JSON (schema `nanoserve-mini.request-once.v1`, mode `singlestream_lite_correctness`) with `--output`/`--run-id` flags; updated `measure_ttft_once.py` to add `methodology`, `benchmark_mode`, `error: null`, `--run-id` and controls fields; updated `run_sequential_benchmark.py` to schema v2 (`sequential-bench.v2` / `sequential-bench-row.v2`), mode `singlestream_lite_repeated`, `--run-id`, measured-only throughput in summary; updated tests; added `--run-id` output layout section to `docs/benchmark-methodology.md`.
- Commands run: reported by Claude Code in PR #2: `uv run ruff check .` (pass), `uv run pytest` (pass).
- Next: run first live benchmark against vLLM endpoint using `--run-id` to verify end-to-end write path on the server.

### 2026-05-07 - Completed coding-agent synthetic task specs

- Why: complete the coding-agent benchmark suite specifications for tasks 02/03/04.
- Did: added TASK.md specs for Python streaming CLI, C++ token buffer hot path, and C# allocation-aware parser refactor under `benchmarks/coding-agent-tasks/`.
- Validation: repo status checked by Codex; lint/tests were unavailable in the Codex environment for the docs-only PR.
- Next: later generate starter task repositories and hidden tests from the specs.

### 2026-05-06 - Current server state confirmed

- Why: make the live server state explicit before planning further tests.
- Did: recorded that Kimi-K2.6 is downloaded and running via `vllm serve` with TP=8; DEP did not work; OpenWebUI is connected and interactive; `check_server_env.py` output is saved in `results/raw/server_env_snapshot.json`.
- Snapshot: Ubuntu 24.04.2, Python 3.12.11, uv 0.11.8, Docker 28.5.0 / Compose v2.39.4, 8x H200 NVL 143771 MiB, driver 595.58.03, CUDA 13.2.
- Validation: local docs check only; no server benchmark run in this update.
- Next: capture the exact working `vllm serve` command, tune GPU memory settings for a second model, then run smoke/TTFT/benchmark scripts.

### 2026-05-06 - Codex pull review and repo cleanup

- Why: sync local laptop with Claude's latest work and remove obsolete/redundant repo artifacts.
- Did: pulled `origin/main` to `1ba9cc6`, verified tidy-docs/sync-state additions, removed `CODEX_BOOTSTRAP_CONFIG_TASK.md`, removed tracked `docs/handoff-archive/2026-05.md`, and restored current server status to TP=8/OpenWebUI.
- Note: current templates now say Git is the archive; no separate handoff archive directory should be recreated. Tracked `.claude/commands/sync-state.md` and `.claude/settings.json` remain present; tidy-docs slash command was not tracked.
- Validation: skipped (docs-only cleanup).
- Next: commit the exact working TP=8 launch configuration, then run scripted smoke/TTFT/benchmark commands against the live vLLM endpoint.

> Pre-2026-05-06 handoff entries compacted. Source: `90d3fcdf8767baa09f53f537a686b165466786fc`.
> Full history: `git show 90d3fcdf8767baa09f53f537a686b165466786fc:docs/agent-state.md`.
