# Agent State - nanoserve-mini

This file is the repo-tracked handoff state for Claude Code, Codex, and human work.

Keep it concise and current. Update it after meaningful repo changes, especially before committing, pushing, or handing work to another agent.

The `sync-state` routine (see `docs/templates/sync-state-agent.md`) appends to this file. The `tidy-docs` routine (see `docs/templates/tidy-docs-agent.md`) compacts it in place. Git is the archive — no separate handoff archive directory.

---

## Summary cursor

- Last summarized commit: `46e2129`
- Last summarized at: 2026-05-11
- Manual edit 2026-05-17: handoff log compacted by hand outside `sync-state` because the coding-agent eval side-quest (entries 2026-05-13..2026-05-16) was archived to `archive/coding-agent-tasks`. Refresh the cursor on the next `sync-state` run.

---

## Canonical file roles

- `CLAUDE.md` - stable instructions for Claude Code.
- `AGENTS.md` - stable instructions for Codex.
- `docs/operations/agent-state.md` - current project state, decisions, next step, and blockers.
- `docs/project/roadmap.md` - project scope; do not change it without an explicit decision.
- `docs/README.md` - documentation map.

---

## Current phase

**Phase 1 (weeks 1-3 of 12)** — vLLM serving baseline + observability + multi-model proxy.

Live state:

- Kimi-K2.6 is served on the 8×H200 NVL server via `vllm serve` with TP=8 + Eagle3 speculative decoding.
- DeepSeek-V4-Flash was added as a small-model experiment alongside Kimi on the server.
- OpenWebUI is connected to the vLLM OpenAI-compatible endpoint.
- The local benchmark/metrics harness (`benchmarks/scripts/`) is on `main` with MLPerf-inspired lite output, `--run-id` support, token-level metrics (TPOT, prompt/completion tokens, tokens/s), structured `controls.workload_spec`, unique `run_uuid`, and a populated `server_metrics` block (vLLM `/metrics` scrape + `nvidia-smi` aggregate + CSV time series).
- Repository layout consolidated 2026-05-17: `scripts/` → `benchmarks/scripts/`, `infra/` → `serving/`, runbooks moved under `serving/runbooks/`, off-roadmap `benchmarks/coding-agent-tasks/` and `benchmarks/scripts/run_coding_agent_task.py` archived to branch `archive/coding-agent-tasks`.

Phase 1 deliverables still owed (per `docs/project/roadmap.md` Definition of Done):

- **LiteLLM Proxy** in front of vLLM as a single OpenAI-compatible endpoint with per-model routing — **in progress** (laptop prep done in `serving/compose/`; server smoke pending Tuesday).
- **Prometheus + Grafana dashboard** showing live metrics during a load test — not started.
- **W1 write-up** ("vLLM + LiteLLM Proxy on 8×H200: from zero to first measurement") — not started.

Phase 1 is not done; the blockers below are scoped to fixing that, not to expanding to Phase 2.

---

## Current known status

- GitHub repo exists: `https://github.com/Czyszka/nanoserve-mini.git`.
- Local Windows laptop bootstrap is done; Python workflow uses `uv`; `ruff` + `pytest` configured; `.gitattributes` normalises line endings.
- Local research PDFs and Claude/Codex worktrees stay outside Git (`docs/**/papers/`, `.claude/worktrees/`, `.uv-cache-codex/`).
- **Server is available**: ubuntusrv2 (Ubuntu 24.04, 8×H200 NVL 143 GB, CUDA 13.2, driver 595.58.03).
- **`results/raw/server_env_snapshot.json` committed** (2026-05-06); generated with `benchmarks/scripts/check_server_env.py`.
- **vLLM Docker image installed** (`vllm/vllm-openai:v0.20.0-cu130`).
- **Kimi-K2.6 serves with TP=8 + Eagle3 speculative decoding.** Single-node DEP was tried and did not work.
- **OpenWebUI container runs on the server** and answers requests against the vLLM endpoint.
- Kimi-K2.6 launch parameters still need GPU memory tuning so the small model fits next to it.
- `serving/compose/docker-compose.kimi-k2.6.yml` tracks Kimi/OpenWebUI plus experimental `vllm-small` on port 8004 with `deepseek-ai/DeepSeek-V4-Flash`.
- **Human report from 2026-05-11 server session, not yet pushed**: latest compose has large + small model + OpenWebUI, small model capped at 20% VRAM across 8 GPUs; DeepSeek-V4-Flash completed `request_once`, TTFT, and repeated benchmark tests; artifacts are still on the server.
- Benchmark/metrics producer scripts on `main`:
  - `benchmarks/scripts/request_once.py`
  - `benchmarks/scripts/measure_ttft_once.py`
  - `benchmarks/scripts/run_sequential_benchmark.py`
  - `benchmarks/scripts/collect_metrics_snapshot.py`
  - `benchmarks/scripts/sample_gpu_metrics.py`
  - `benchmarks/scripts/run_bench_suite.py`

---

## Important project docs

Read these before making non-trivial changes:

- `docs/project/roadmap.md` - current scope, phases, and Definition of Done.
- `docs/operations/infrastructure.md` - machine roles and workflow.
- `serving/runbooks/server-env-bootstrap.md` - reusable runbook for GPU server env bootstrap.
- `docs/operations/benchmark-methodology.md` - MLPerf-inspired lite benchmark modes, result schema contract, `--run-id` layout.
- `docs/plans/2026-05-11-server-work-plan.md` - last server-session work plan and post-session notes.
- `docs/learning/reading-list.md` - papers by phase.
- `docs/README.md` - documentation map.
- `AGENTS.md` / `CLAUDE.md` - agent entrypoints.

Do not rewrite the roadmap/scope document unless explicitly asked.

---

## Current technical direction

The benchmark scripts use these MLPerf-inspired lite modes:

| Script | Benchmark mode | Schema |
|---|---|---|
| `benchmarks/scripts/request_once.py` | `singlestream_lite_correctness` | `nanoserve-mini.request-once.v2` |
| `benchmarks/scripts/measure_ttft_once.py` | `singlestream_lite_latency` | `nanoserve-mini.ttft-once.v2` |
| `benchmarks/scripts/run_sequential_benchmark.py` summary | `singlestream_lite_repeated` | `nanoserve-mini.sequential-bench.v3` |
| `benchmarks/scripts/run_sequential_benchmark.py` row | `singlestream_lite_repeated` | `nanoserve-mini.sequential-bench-row.v3` |
| `benchmarks/scripts/collect_metrics_snapshot.py` | `server_metrics` | `nanoserve-mini.server-metrics-snapshot.v1` |
| `benchmarks/scripts/sample_gpu_metrics.py` | `server_metrics` | `nanoserve-mini.gpu-samples-meta.v1` |

`benchmarks/scripts/run_bench_suite.py` is the one-command Phase 1 launcher.
It generates `YYYY-MM-DD_<model-slug>_run-NN`, runs pre/post snapshots plus
request/TTFT/sequential benchmarks through LiteLLM Proxy, and writes manifest
schema `nanoserve-mini.bench-suite.v1`.

All benchmark and server-metrics scripts support `--run-id` and write under `results/runs/<run_id>/`. Expected layout:

```text
results/runs/<run_id>/
  singlestream_lite_correctness/result.json
  singlestream_lite_latency/result.json
  singlestream_lite_repeated/results.jsonl
  singlestream_lite_repeated/summary.json
  server_metrics/snapshot_pre.json
  server_metrics/snapshot_post.json
  server_metrics/gpu_samples.csv
  server_metrics/gpu_samples_meta.json
  bench_suite/summary.json
```

### Immediate next steps (Phase 1 close-out)

1. **Tuesday server session** — recover unpushed 2026-05-11 artifacts and commit them:
   - latest Docker Compose with Kimi-K2.6 + `vllm-small` + OpenWebUI,
   - DeepSeek-V4-Flash `request_once`, TTFT, and repeated benchmark outputs,
   - short note recording launch parameters incl. the 20% VRAM cap for the small model.
2. Reconcile the latest server compose with `serving/compose/docker-compose.kimi-k2.6.yml`; decide whether TP=8 Kimi, EP/DP Kimi, and small-model services live in one file or separate profiles.
3. **Smoke LiteLLM Proxy on the server**: `docker compose up litellm`, then `curl -H "Authorization: Bearer $LITELLM_MASTER_KEY" http://localhost:4000/v1/models` and one `/v1/chat/completions` per upstream model. Image tags now pinned (`vllm v0.20.0-cu130-ubuntu2404`, `litellm main-v1.66.0-stable`, `open-webui v0.1.121`).
4. Validate the metrics scripts live on the server end-to-end:
   - `benchmarks/scripts/collect_metrics_snapshot.py --phase pre`
   - `benchmarks/scripts/sample_gpu_metrics.py` during a benchmark window
   - `benchmarks/scripts/collect_metrics_snapshot.py --phase post`
5. Run the normalised benchmark sequence per model with `benchmarks/scripts/run_bench_suite.py`; it auto-generates `run_id`, sends requests through proxy:4000 with `LITELLM_MASTER_KEY`, and sends metrics snapshots directly to the target vLLM `/metrics` endpoint.
6. Optional follow-up: add GPU sampling back into the suite once the basic proxy benchmark is validated on the server.
7. Stand up **Prometheus + Grafana dashboard** scraping vLLM `/metrics` and rendering TTFT/TPOT/throughput/KV-cache during a load test (Phase 1 DoD #4).
8. Draft **write-up W1** in `docs/weekly/` or a new `docs/write-ups/` directory once the dashboard is live.
9. Later: implement fact-table aggregator (`benchmarks/scripts/aggregate_runs.py`, Wave C) for dashboard/dataframe consumption.

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
uv run python -m benchmarks.scripts.check_server_env
```

Benchmark and metrics example:

```bash
RUN_ID=2026-05-11_kimi_tp8_baseline

uv run python -m benchmarks.scripts.collect_metrics_snapshot \
  --base-url http://127.0.0.1:8000 --run-id "$RUN_ID" --phase pre

uv run python -m benchmarks.scripts.request_once \
  --base-url http://127.0.0.1:8000 --model moonshotai/Kimi-K2.6 --run-id "$RUN_ID"

uv run python -m benchmarks.scripts.measure_ttft_once \
  --base-url http://127.0.0.1:8000 --model moonshotai/Kimi-K2.6 --run-id "$RUN_ID"

uv run python -m benchmarks.scripts.sample_gpu_metrics \
  --run-id "$RUN_ID" --interval-ms 500 --duration-s 60

uv run python -m benchmarks.scripts.run_sequential_benchmark \
  --base-url http://127.0.0.1:8000 --model moonshotai/Kimi-K2.6 \
  --warmup 1 --runs 5 --run-id "$RUN_ID"

uv run python -m benchmarks.scripts.collect_metrics_snapshot \
  --base-url http://127.0.0.1:8000 --run-id "$RUN_ID" --phase post
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
| Repo layout | code under `benchmarks/scripts/`; ops under `serving/`; outputs under `results/`; docs under `docs/` |
| vLLM setup | Docker (`vllm/vllm-openai:v0.20.0-cu130`) |
| vLLM strategy | Working: `vllm serve` with TP=8 + Eagle3 speculative decoding; single-node DEP did not work |
| Primary model | `moonshotai/Kimi-K2.6` + `lightseekorg/kimi-k2.6-eagle3-mla` |
| Small-model experiment | `deepseek-ai/DeepSeek-V4-Flash` capped at ~20% VRAM across 8 GPUs |
| HF weights storage | named Docker volume `nanoserve-hf-cache` |
| Compose file | `serving/compose/docker-compose.kimi-k2.6.yml` (draft; verify against the live server before treating as canonical) |
| Interactive UI | OpenWebUI container connected to vLLM OpenAI-compatible endpoint |
| Multi-model proxy | LiteLLM Proxy as a fourth service in compose; routing by `model` field; `LITELLM_MASTER_KEY` from env |
| Image pinning | Pinned to readable version tags 2026-05-17 (vllm `v0.20.0-cu130-ubuntu2404`, litellm `main-v1.66.0-stable`, open-webui `v0.1.121`); bump in YAML + `docker compose pull` |
| Benchmark methodology | MLPerf-inspired lite, not official MLPerf; first modes are SingleStream-lite correctness/latency/repeated |
| Benchmark output | `results/runs/<run_id>/<benchmark_mode>/` + `results/runs/<run_id>/server_metrics/` |
| Agent memory | `docs/operations/agent-state.md` is repo-tracked shared handoff |
| Claude Code entrypoint | root `CLAUDE.md` |
| Codex entrypoint | root `AGENTS.md` |
| State updates | Codex and Claude Code must update `docs/operations/agent-state.md` after meaningful work and before commit/push handoff |
| Local papers | Stored in ignored `docs/**/papers/`; commit summaries separately if useful |
| Coding-agent benchmarks | Archived 2026-05-17 to `archive/coding-agent-tasks` branch; not part of Phase 1 DoD |

---

## Open questions

- [ ] Record the exact working TP=8 server command/config in repo.
- [ ] Should TP=8 Kimi, EP/DP Kimi, and small-model services live in one compose file or separate profiles?
- [ ] Import unpushed server-side compose and DeepSeek-V4-Flash benchmark results (Tuesday session).
- [ ] Should OpenWebUI keep its direct `vllm:8000` link or move behind `litellm:4000`? (LiteLLM is now in compose; UI routing decision deferred until first server smoke.)
- [x] Which exact Docker image tags should replace floating `latest`/`main` tags? — pinned 2026-05-17 to readable version tags (see "Current decisions").
- [ ] Validate benchmark + metrics scripts end-to-end on the server.
- [ ] Which Kimi-K2.6 `vllm serve` memory parameters allow the small model to fit comfortably?
- [ ] Does `uv sync --extra dev` work on the server? (not yet tested, not blocking)
- [ ] Should raw result files be committed directly or summarised after the first GPU run?
- [ ] When to implement `benchmarks/scripts/aggregate_runs.py` (Wave C)?

---

## Last validation

Local laptop validation on 2026-05-17 after adding `run_bench_suite.py`:

```text
uv run ruff check .     OK, all checks passed
uv run pytest -q        OK, 113 passed
```

The earlier 2026-05-08 validation (after PR #7 review follow-ups: failure-record path in `measure_ttft_once`, `completed=False` on no-content streams, stricter argument guards in `sample_gpu_metrics`) also reported `ruff` + `pytest` clean. The 2026-05-08 task-spec tightening on `main` was documentation-only.

---

## Handoff log

Newest entry first. Appended by the `sync-state` routine (`docs/templates/sync-state-agent.md`); compacted in place by the `tidy-docs` routine (`docs/templates/tidy-docs-agent.md`). Git is the archive.

### 2026-05-17 - Bench suite launcher for LiteLLM proxy runs

- Why: server sessions need one simple command that runs the Phase 1 benchmark sequence for one model through LiteLLM Proxy.
- Did:
  - Added `benchmarks/scripts/run_bench_suite.py`: auto-generates `YYYY-MM-DD_<model-slug>_run-NN`, runs `snapshot_pre -> request_once -> measure_ttft_once -> run_sequential_benchmark -> snapshot_post`, and writes `results/runs/<run_id>/bench_suite/summary.json`.
  - Added optional `api_key` support to `_client.CompletionRequest`; request scripts now accept `--api-key` defaulting to `LITELLM_MASTER_KEY`.
  - Kept GPU sampling out of v1 by design; add it later after the basic proxy path is validated on the server.
  - Added tests for auth headers, CLI `--api-key` propagation, run-id generation, suite step ordering, fail-fast plus post-snapshot behavior, and strict JSON manifest output.
- Validation:
  - `uv run ruff check .` - clean.
  - `uv run pytest -q` - 113 passed.
- Next: on the server, run `uv run python -m benchmarks.scripts.run_bench_suite --base-url http://127.0.0.1:4000 --metrics-base-url http://127.0.0.1:8000 --model kimi-k2.6` after setting `LITELLM_MASTER_KEY`.

### 2026-05-17 - LiteLLM Proxy + image pinning (laptop prep)

- Why: Phase 1 DoD #2 (LiteLLM Proxy) not started after week 1; user has server access only on Tuesday, so today's laptop session pre-stages everything that doesn't need a GPU.
- Did:
  - Added `litellm` service to `serving/compose/docker-compose.kimi-k2.6.yml` (port 4000, `depends_on` vllm + vllm-small, healthcheck against `/health/liveliness`, mounts `litellm-config.yaml` read-only).
  - Created `serving/compose/litellm-config.yaml` with `model_list` mapping `kimi-k2.6` → `http://vllm:8000/v1` and `DeepSeek-V4-Flash` → `http://vllm-small:8004/v1`; `master_key` from env.
  - Synced `serving/compose/.env.example`: dropped dead vars (`MODEL_NAME`, `MAX_*`, `GPU_MEMORY_UTILIZATION` — none read by the YAML), added `LITELLM_MASTER_KEY`, `LITELLM_HOST_PORT`.
  - Pinned image tags (readable, not digests, by user request): `vllm/vllm-openai:v0.20.0-cu130-ubuntu2404`, `ghcr.io/berriai/litellm:main-v1.66.0-stable`, `ghcr.io/open-webui/open-webui:v0.1.121`. Latest tags checked via Docker Hub / GHCR Tags APIs.
  - Updated `serving/compose/README.md` with the LiteLLM service table row, new env vars, smoke command (`curl -H "Authorization: Bearer $LITELLM_MASTER_KEY" .../v1/models`), and TODO list refreshed with bench launcher / Grafana / W1.
  - Deferred to a separate session (too big for this PR): `benchmarks/scripts/run_bench_suite.py` launcher + `--api-key` propagation through `_client.py` and the three benchmark scripts. Guidelines captured in step 6 of "Immediate next steps".
- Validation:
  - `python -c "import yaml; yaml.safe_load(open('serving/compose/docker-compose.kimi-k2.6.yml')); yaml.safe_load(open('serving/compose/litellm-config.yaml'))"` — clean.
  - `uv run ruff check .` — clean.
  - `uv run pytest -q` — 102 passed (no Python code changes).
- Next: open PR `feat/litellm-proxy` → `main`; on Tuesday's server session, smoke LiteLLM and start the bench launcher work.

### 2026-05-17 - Repo layout consolidation + off-roadmap archive

- Why: directory layout had drifted — `scripts/` mixed benchmark producers with off-roadmap coding-agent harness; `benchmarks/` held only coding-agent tasks (off-roadmap) plus two empty `.gitkeep` dirs; runbooks were split between `docs/operations/runbooks/` and `infra/`. User reported the structure as opaque and Phase 1 deliverables (LiteLLM Proxy, dashboard, W1 write-up) had not started after a week.
- Did:
  - Archived the entire `benchmarks/coding-agent-tasks/` tree, `benchmarks/scripts/run_coding_agent_task.py`, `tests/test_run_coding_agent_task.py`, and the unused `MODE_CODING_AGENT_EVAL` / `SCHEMA_CODING_AGENT_EVAL_ROW` constants on branch `archive/coding-agent-tasks` (pushed to `origin`); deleted them on `main`.
  - Moved `scripts/` → `benchmarks/scripts/` (git mv) so all benchmark code lives under one parent. Updated every `from scripts.…` import in scripts and tests to `from benchmarks.scripts.…`. Rewrote `scripts.foo` references in docs/CLAUDE/AGENTS to `benchmarks.scripts.foo`.
  - Renamed `infra/` → `serving/`. Moved `docs/operations/runbooks/` → `serving/runbooks/` so operational docs sit next to compose files. Updated references in docs and the compose README.
  - Removed empty `benchmarks/configs/`, `benchmarks/prompts/`, `infra/docker/`, root `infra/.gitkeep`.
  - Untracked `.uv-cache-codex/` via `.gitignore` (added next to `.claude/worktrees/`).
  - Rewrote root `README.md` to match the new layout and the actual scope (no more stale "out of scope: multi-GPU/FP8/MoE" line — those are in scope via the company H200 project per the roadmap).
  - Updated `docs/README.md` map and `docs/templates/sync-state-agent.md` references.
  - Tidied this file: dropped stale "task specs 01-04" notes from `Current known status` / `Current decisions` / `Open questions`; collapsed the 2026-05-13..2026-05-16 handoff entries (all coding-agent eval side-quest) so the log refocuses on Phase 1 close-out.
- Validation:
  - `uv run ruff check .` clean.
  - `uv run pytest -q` = 102 passed (same suite, all imports rewired).
  - `git status` clean apart from the intended renames/deletes.
- Next: open PR `refactor/repo-layout-consolidation` → `main` for review and merge; then on Tuesday's server session, work through the Phase 1 close-out steps listed under "Immediate next steps".

### 2026-05-13 .. 2026-05-16 - Coding-agent eval harness exploration (archived)

A week of work on a synthetic coding-agent evaluation harness — task 01-04 spec tightening, starter scaffolds (PowerShell/Python/C++/C#), a `run_coding_agent_task.py` wrapper, a v1 `coding-agent-eval-row` schema, and follow-up work on task 01 (preflight env check) including stream-json output handling and Bun transport-crash classification.

Outcome: the work is **off-roadmap** (not in Phase 1 DoD, not mapped to any of the 7 planned write-ups) and consumed roughly a week of session budget on environmental friction (Bun runtime panics on Windows, MSYS jq CRLF injection, cp1250 subprocess decoding, slow `nvidia-smi` on a consumer GPU) rather than signal about agent capability.

Archived 2026-05-17 to branch `archive/coding-agent-tasks` (full file history preserved). PR `feat/task01-tests-bash-series` (PR #27) remains open as a draft on the archive branch; close or leave dormant. If the coding-agent eval direction is resurrected later, restore from the archive branch and pull the run_eval / run_series harness back in.

### 2026-05-11 - Compose capture + DeepSeek small-model experiment

- Why: capture server launch work in repo-tracked infrastructure instead of leaving it in shell history.
- Did: added Kimi-K2.6 compose/runbook reference, folded OpenWebUI into compose, added experimental `vllm-small` service for `deepseek-ai/DeepSeek-V4-Flash`. Aligned `infra/compose/README.md` (now `serving/compose/README.md`) with the actual services: Kimi on 8000, DeepSeek on 8004, OpenWebUI on 3000. Updated `docs/plans/2026-05-11-server-work-plan.md` with a top-level note about unpushed server artifacts, the 20% VRAM split, and image-pinning TODO.
- Range: `b5f0ab7..46e2129`.
- Human server-session note: DeepSeek-V4-Flash was benchmarked with `request_once`, TTFT, and repeated runs on the server; latest compose has large model + small model + OpenWebUI with the small model capped at 20% VRAM across 8 GPUs; artifacts not yet pushed.
- Validation: skipped locally (docs/infra only); live server behaviour must be verified from the GPU host.
- Next: import the unpushed compose + DeepSeek results next session, then verify documented service commands against the live server.

### 2026-05-08 - PR #7 review follow-up + server-metrics scripts

- Why: close PR #7 (server-metrics scripts) cleanly after a `main` conflict with the task-spec tightening, and add a compliance disclaimer so `mlperf_inspired_lite` results cannot be mistaken for official MLPerf.
- Did:
  - Merged `origin/main` into the PR branch and resolved the only conflict (`docs/agent-state.md`).
  - `benchmarks/scripts/measure_ttft_once.py`: HTTP/transport/stream errors now produce a v2-schema failure record (`completed=False`, all token-derived metrics `None`, non-null `error` string with type+message). `main()` returns 1 on failure. `measure_stream`: `completed = bool(output_parts)` so role-only streams that end cleanly are not counted as successful generations.
  - `benchmarks/scripts/sample_gpu_metrics.py`: argparse guards for `--duration-s > 0` and `--samples > 0` while keeping the "at least one required" rule.
  - Added `benchmarks/scripts/_server_metrics.py` (parsers for vLLM Prometheus text + nvidia-smi CSV, NaN/Inf → None), `benchmarks/scripts/collect_metrics_snapshot.py` (one-shot scrape, schema `nanoserve-mini.server-metrics-snapshot.v1`), `benchmarks/scripts/sample_gpu_metrics.py` (interval CSV + sidecar `gpu_samples_meta.json`, schema `nanoserve-mini.gpu-samples-meta.v1`). All schemas centralised in `benchmarks/scripts/_schemas.py`.
  - Added MLPerf compliance-status section to `docs/operations/benchmark-methodology.md` (blockquote + side-by-side requirements table + verbatim portfolio-language paragraph).
  - Tests: 67 → 95 → 102 passing across server-metrics parsers, snapshot main(), sampler loop with `FakeClock`, and the failure-record paths in `measure_ttft_once`.
- Commands: `uv run ruff check .` (pass), `uv run pytest -q` (102 passed).
- Next: live-run end-to-end on the server, or write the fact-table aggregator (Wave C), or record the working TP=8 `vllm serve` command in a runbook.

### 2026-05-07/08 - Benchmark normalisation + coding-agent task specs

- Why: bring the three benchmark scripts to consistent `methodology`, `benchmark_mode`, `--run-id`, `git_commit`, and dashboard-ready schema; then settle the four synthetic coding-agent task specs (PowerShell / Python / C++ / C#).
- Did:
  - `benchmarks/scripts/_metrics.py`: extended `RunControls` with `run_id`, `script_name`, `git_commit`, `concurrency`, `run_uuid`, structured `workload_spec`, plus `null_server_metrics()` helper and `get_git_commit()` / `resolve_output_path()` helpers.
  - `benchmarks/scripts/_client.py`: `chat_completion_stream` now injects `stream_options.include_usage=true` by default (caller wins).
  - All three benchmark scripts now write per-mode JSON to `results/runs/<run_id>/<mode>/` with token-level metrics (TPOT, prompt/completion tokens, output tokens/s). Schemas: `request-once.v2`, `ttft-once.v2`, `sequential-bench.v3` (+ `sequential-bench-row.v3`).
  - Tightened all four task specs on `main` (commits `c149c79`, `69d9f6f`, `57a5e0b`, `f83ef7a`) — these were the input to the now-archived coding-agent harness work.
  - Added "Result schema contract" section to `docs/operations/benchmark-methodology.md`.
- Validation: `uv run ruff check .` clean; `uv run pytest -q` = 67 passing after this wave.
- Next: server-metrics scripts (next wave, see 2026-05-08 entry).

### 2026-05-06 - Server bootstrap + Kimi-K2.6 first serve

- Why: get a real vLLM run on the 8×H200 NVL server.
- Did: ran `benchmarks/scripts/check_server_env.py` and committed `results/raw/server_env_snapshot.json` (Ubuntu 24.04.2, Python 3.12.11, uv 0.11.8, Docker 28.5.0 / Compose v2.39.4, 8× H200 NVL 143771 MiB, driver 595.58.03, CUDA 13.2). Installed vLLM Docker image `vllm/vllm-openai:v0.20.0-cu130`. Downloaded Kimi-K2.6 into named volume `nanoserve-hf-cache`. Got Kimi serving via `vllm serve` with TP=8 + Eagle3 speculative decoding (`lightseekorg/kimi-k2.6-eagle3-mla`); single-node DEP attempt did not work for this run. Stood up OpenWebUI alongside, confirmed it answers requests through the OpenAI-compatible endpoint. Pulled `origin/main` to `1ba9cc6` and removed obsolete repo artifacts (`CODEX_BOOTSTRAP_CONFIG_TASK.md`, tracked `docs/handoff-archive/2026-05.md`).
- Validation: docs-only cleanup; server behaviour verified manually.
- Next: commit the exact working TP=8 launch configuration, then run scripted smoke/TTFT/benchmark commands against the live vLLM endpoint.

> Pre-2026-05-06 handoff entries compacted. Source: `90d3fcdf8767baa09f53f537a686b165466786fc`.
> Full history: `git show 90d3fcdf8767baa09f53f537a686b165466786fc:docs/agent-state.md`.
