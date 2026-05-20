# Agent State - nanoserve-mini

This file is the repo-tracked handoff state for Claude Code, Codex, and human work.

Keep it concise and current. Update it after meaningful repo changes, especially before committing, pushing, or handing work to another agent.

The `sync-state` routine (see `docs/templates/sync-state-agent.md`) appends to this file. The `tidy-docs` routine (see `docs/templates/tidy-docs-agent.md`) compacts it in place. Git is the archive — no separate handoff archive directory.

---

## Summary cursor

- Last summarized commit before this refresh: `e3eaf0c`
- Last summarized at: 2026-05-19
- Manual refresh 2026-05-19: updated after the server session that synced compose, ran LiteLLM smoke, ran proxy bench suites for Kimi/DeepSeek, collected Kimi stream-debug data, and started Prometheus/Grafana.

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

Phase 1 is now past the minimum proxy/benchmark milestone, but not fully complete because the real Grafana dashboard and W1 write-up are still missing.

Live state:

- Kimi-K2.6 runs on the 8×H200 NVL server through Docker Compose as service `vllm`, exposed on port 8000, using TP=8 + Eagle3 speculative decoding.
- DeepSeek-V4-Flash runs alongside Kimi as service `vllm-small`, exposed on port 8004, capped around 20% VRAM in the compose configuration.
- OpenWebUI is running and communicates with the vLLM services.
- LiteLLM Proxy runs on port 4000 and routes by `model` to Kimi and DeepSeek. Smoke tests through proxy passed for both upstreams.
- `run_bench_suite.py` has been run through LiteLLM Proxy for both Kimi K2.6 and DeepSeek-V4-Flash; results are committed.
- Prometheus + Grafana configuration exists under `serving/compose/` and containers have been started. Observability is partially validated, but the actual dashboard/panels are not yet a finished artifact.
- Kimi K2.6 TTFT/TPOT parsing fixed (issue #31): `measure_ttft_once.py` now records a separate `ttft_any_token_seconds` / `tpot_any_token_seconds` covering reasoning-trace text (`delta.reasoning` / `delta.reasoning_content`) while `ttft_seconds` stays final-answer-only. Verified against the committed stream-debug artifacts.

Phase 1 deliverables still owed:

- **Prometheus + Grafana dashboard** showing useful live vLLM metrics during load — stack exists and containers run, but dashboard/panels still need to be built from the real metric names.
- **W1 write-up** — not started; should be drafted after observability/dashboard is coherent enough to describe.

---

## Current known status

- GitHub repo exists: `https://github.com/Czyszka/nanoserve-mini.git`.
- Local Windows laptop bootstrap is done; Python workflow uses `uv`; `ruff` + `pytest` configured; `.gitattributes` normalises line endings.
- Local research PDFs and Claude/Codex worktrees stay outside Git (`docs/**/papers/`, `.claude/worktrees/`, `.uv-cache-codex/`).
- **Server**: ubuntusrv2 (Ubuntu 24.04, 8×H200 NVL 143 GB, CUDA 13.2, driver 595.58.03).
- **Kimi + DeepSeek + OpenWebUI + LiteLLM compose**: canonical compose lives at `serving/compose/docker-compose.kimi-k2.6.yml`.
- **Observability compose**: `serving/compose/docker-compose.observability.yml` plus:
  - `serving/compose/prometheus/prometheus.yml`
  - `serving/compose/grafana/provisioning/datasources/prometheus.yml`
- Observability runtime data should live in explicit host directories, not opaque Docker named volumes, when local control is needed.
- Benchmark/metrics producer scripts on `main`:
  - `benchmarks/scripts/request_once.py`
  - `benchmarks/scripts/measure_ttft_once.py`
  - `benchmarks/scripts/run_sequential_benchmark.py`
  - `benchmarks/scripts/collect_metrics_snapshot.py`
  - `benchmarks/scripts/sample_gpu_metrics.py`
  - `benchmarks/scripts/run_bench_suite.py`

Recent committed work from 2026-05-19:

- `bench: resalts of benchmarks of kimi k2.6 from 11.05` — recovered earlier benchmark artifacts.
- `fix: compose fix TP instead of DP for kimi` — reconciled server compose and corrected Kimi strategy.
- `bench: add compose smoke results for kimi and deepseek`.
- `bench: collect kimi stream debug artifacts`.
- `bench: run litellm proxy suite for kimi and deepseek`.
- Prometheus/Grafana compose and provisioning commits.
- `docs: mark 2026-05-19 server plan progress`.

---

## Important project docs

Read these before making non-trivial changes:

- `docs/project/roadmap.md` - current scope, phases, and Definition of Done.
- `docs/operations/infrastructure.md` - machine roles and workflow.
- `docs/operations/benchmark-methodology.md` - MLPerf-inspired lite benchmark modes, result schema contract, `--run-id` layout.
- `docs/plans/2026-05-19-server-work-plan.md` - current server-session checklist and status.
- `docs/plans/2026-05-11-server-work-plan.md` - older server-session context, now superseded by the 2026-05-19 close-out work.
- `serving/compose/` - vLLM/OpenWebUI/LiteLLM/observability compose files.
- `serving/runbooks/` - operational instructions.
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
| `benchmarks/scripts/run_bench_suite.py` | suite manifest | `nanoserve-mini.bench-suite.v1` |

`benchmarks/scripts/run_bench_suite.py` is the one-command Phase 1 launcher. It generates `YYYY-MM-DD_<model-slug>_run-NN`, runs `snapshot_pre -> request_once -> measure_ttft_once -> run_sequential_benchmark -> snapshot_post`, sends requests through LiteLLM Proxy when `--base-url http://127.0.0.1:4000` is used, and writes `results/runs/<run_id>/bench_suite/summary.json`.

Expected run layout:

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

---

## Immediate next steps

Prioritise laptop-side cleanup first; do not burn GPU/server time on documentation or repo hygiene.

1. **Issue #32 — fix `.gitignore` rules for benchmark run artifacts on laptop.** Make small structured `results/runs/**/*.json|jsonl|csv|md` trackable while keeping logs, model caches, Nsight traces and secrets ignored.
2. **Issue #33 — write 2026-05-19 server session summary** as `docs/plans/2026-05-19-server-session-summary.md` or fold into weekly notes.
3. **Build the actual Grafana dashboard.** Use real vLLM metric names from `/metrics` / Prometheus instead of guessed names. First dashboard should show at least target health, running/waiting requests, token throughput if available, TTFT/TPOT histograms if exposed, and KV/GPU cache metrics if exposed.
4. **Capture/commit observability metric-name inventory** if not already committed. Commit small `*.metric-names.txt`; avoid large raw metrics dumps if noisy.
5. **Draft W1** only after the proxy benchmark + observability story is coherent.
6. **Install `rg` (ripgrep) on the server** so laptop and server share the same tooling. `rg` is already installed on the laptop; `check_server_env.py` now probes for it (`rg_version`). On Ubuntu: `sudo apt-get install -y ripgrep`. Quick task — fold into the next server session, do not open a dedicated GPU slot for it.
7. Optional later: add GPU sampling back into `run_bench_suite.py` after the basic proxy benchmark path and dashboard are stable.
8. Later: implement fact-table aggregator (`benchmarks/scripts/aggregate_runs.py`, Wave C) for dashboard/dataframe consumption.

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

LiteLLM proxy benchmark examples:

```bash
uv run python -m benchmarks.scripts.run_bench_suite \
  --base-url http://127.0.0.1:4000 \
  --metrics-base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 \
  --api-key "$LITELLM_MASTER_KEY" \
  --warmup 1 \
  --runs 3

uv run python -m benchmarks.scripts.run_bench_suite \
  --base-url http://127.0.0.1:4000 \
  --metrics-base-url http://127.0.0.1:8004 \
  --model DeepSeek-V4-Flash \
  --api-key "$LITELLM_MASTER_KEY" \
  --warmup 1 \
  --runs 3
```

Observability checks:

```bash
docker compose -f serving/compose/docker-compose.observability.yml ps
curl -fsS http://127.0.0.1:9090/-/healthy && echo "prometheus OK"
curl -fsS http://127.0.0.1:3001/api/health && echo "grafana OK"
curl -s http://127.0.0.1:9090/api/v1/targets \
  | jq '.data.activeTargets[] | {job: .labels.job, health: .health, scrapeUrl: .scrapeUrl, lastError: .lastError}'
```

---

## Current decisions

| Area | Decision |
|---|---|
| Central sync | GitHub repo |
| Laptop role | dev, docs, analysis, parser fixes, repo hygiene |
| Server role | primary GPU execution; avoid docs-only work during server slots |
| Optional cloud | backup GPU access only |
| Python workflow | `uv` on laptop and server |
| Heavy GPU deps | not in laptop base config |
| Repo layout | code under `benchmarks/scripts/`; ops under `serving/`; outputs under `results/`; docs under `docs/` |
| vLLM setup | Docker Compose using `vllm/vllm-openai:v0.20.0-cu130-ubuntu2404` |
| vLLM strategy | Kimi uses TP=8 + Eagle3 speculative decoding; single-node DEP did not work |
| Primary model | `moonshotai/Kimi-K2.6` served as `kimi-k2.6` |
| Small-model experiment | `deepseek-ai/DeepSeek-V4-Flash` served as `DeepSeek-V4-Flash`, capped at ~20% VRAM across 8 GPUs |
| Compose file | `serving/compose/docker-compose.kimi-k2.6.yml` is the canonical Kimi/DeepSeek/OpenWebUI/LiteLLM compose |
| Interactive UI | OpenWebUI remains working with current stack; no urgent need to force it behind LiteLLM |
| Multi-model proxy | LiteLLM Proxy is in compose and smoke-tested; benchmark suite ran through it for both models |
| Observability | Prometheus/Grafana compose exists; runtime data should use explicit host paths when local control matters |
| Benchmark methodology | MLPerf-inspired lite, not official MLPerf; first modes are SingleStream-lite correctness/latency/repeated |
| Benchmark output | `results/runs/<run_id>/<benchmark_mode>/` + `results/runs/<run_id>/server_metrics/` |
| Agent memory | `docs/operations/agent-state.md` is repo-tracked shared handoff |
| Claude Code entrypoint | root `CLAUDE.md` |
| Codex entrypoint | root `AGENTS.md` |
| State updates | Codex and Claude Code must update `docs/operations/agent-state.md` after meaningful work and before commit/push handoff |
| Local papers | Stored in ignored `docs/**/papers/`; commit summaries separately if useful |
| Coding-agent benchmarks | Archived 2026-05-17 to `archive/coding-agent-tasks` branch; not part of Phase 1 DoD |

---

## Open questions / blockers

- [ ] `.gitignore` / benchmark results policy needs cleanup so normal `git add` works for small structured artifacts. Tracked by issue #32.
- [ ] Which exact vLLM metric names should drive the first Grafana dashboard? Need inventory from live `/metrics` and/or Prometheus.
- [ ] Should `sample_gpu_metrics` be integrated into `run_bench_suite.py`, or stay as a separate explicit tool?
- [ ] Which Kimi-K2.6 memory parameters are stable enough for long runs while DeepSeek stays up beside it?
- [ ] When to implement `benchmarks/scripts/aggregate_runs.py` (Wave C)?

Closed since last refresh:

- [x] Issue #31 — Kimi K2.6 TTFT/TPOT reasoning-stream parsing fixed on laptop.
- [x] Import unpushed server-side compose and benchmark results.
- [x] Smoke LiteLLM Proxy on server.
- [x] Run `run_bench_suite.py` for both Kimi and DeepSeek through LiteLLM Proxy.
- [x] Start Prometheus + Grafana containers.

---

## Last validation

2026-05-20 laptop validation (issue #31):

```text
uv run ruff check .     OK, all checks passed
uv run pytest -q        OK, 121 passed
```

Parser also smoke-checked against the committed Kimi stream-debug artifacts:
reasoning-only `stream_short_prompt` now reports `completed` with
`ttft_any_token_seconds` set (was `TTFT: n/a`); `stream_exact_ok` and
`stream_reasoning_prompt` report both content and any-token TTFT.

2026-05-19 server validation:

- Kimi and DeepSeek endpoints responded directly.
- OpenWebUI communicated with the running vLLM services.
- LiteLLM Proxy responded to `/v1/models` and `/v1/chat/completions` for both upstream models.
- `run_bench_suite.py` completed for both `kimi-k2.6` and `DeepSeek-V4-Flash` through LiteLLM Proxy.
- Prometheus and Grafana containers were started. Target/dashboard quality still needs follow-up.

Most recent laptop validation before server work:

```text
uv run ruff check .     OK, all checks passed
uv run pytest -q        OK, 113 passed
```

---

## Handoff log

Newest entry first. Appended by the `sync-state` routine (`docs/templates/sync-state-agent.md`); compacted in place by the `tidy-docs` routine (`docs/templates/tidy-docs-agent.md`). Git is the archive.

### 2026-05-20 - Issue #31: Kimi K2.6 TTFT/TPOT reasoning-stream parsing

- Why: `measure_ttft_once.py` reported `TTFT: n/a` / `TPOT: n/a` for Kimi K2.6
  because the parser only counted `delta.content`; Kimi streams its
  chain-of-thought via `delta.reasoning`.
- Did:
  - Added `extract_stream_reasoning_text` to `_client.py` (handles
    `delta.reasoning` and DeepSeek-style `delta.reasoning_content`).
  - `measure_stream` now records `ttft_any_token_seconds` (first content *or*
    reasoning token) and `reasoning_chars` alongside the unchanged final-answer
    `ttft_seconds`; `build_record` adds `tpot_any_token_seconds`.
  - A reasoning-only response (max_tokens spent before the final answer) now
    counts as `completed`; non-reasoning models are unaffected.
  - Metrics additions are additive — schema stays `nanoserve-mini.ttft-once.v2`.
  - Added/updated tests in `test_client.py` and `test_measure_ttft_once.py`.
- Validation: `uv run ruff check .` clean; `uv run pytest -q` = 121 passed;
  parser smoke-checked against committed stream-debug artifacts.
- Next: issue #32 (`.gitignore` for benchmark artifacts), then issue #33.

### 2026-05-19 - Phase 1 server close-out: compose, proxy, bench, observability bootstrap

- Why: close the Phase 1 server/proxy minimum using the 8×H200 server slot.
- Did:
  - Recovered/pushed prior 2026-05-11 benchmark artifacts.
  - Reconciled live server compose into `serving/compose/docker-compose.kimi-k2.6.yml`; corrected Kimi setup to tensor parallelism rather than the earlier DP mistake.
  - Confirmed `vllm`, `vllm-small`, and OpenWebUI are running and communicating.
  - Ran compose smoke results for Kimi and DeepSeek and pushed them.
  - Collected raw Kimi stream-debug artifacts after `measure_ttft_once.py` showed `TTFT: n/a` / `TPOT: n/a`; created issue #31 for laptop-side parser fix.
  - Created issue #32 for `.gitignore` / benchmark artifact tracking cleanup.
  - Started LiteLLM Proxy, ran smoke through proxy, then ran `run_bench_suite.py` through LiteLLM Proxy for Kimi and DeepSeek; pushed results.
  - Added Prometheus/Grafana compose/provisioning and started containers.
  - Created issue #33 to write the session summary later on laptop.
  - Updated `docs/plans/2026-05-19-server-work-plan.md` with completed/partial/remaining status.
- Validation:
  - Direct vLLM endpoints worked.
  - LiteLLM Proxy worked for both upstream models.
  - Bench suite completed for both upstream models through proxy.
  - Observability containers started; dashboard still pending.
- Next:
  - Laptop: issue #31, issue #32, issue #33.
  - Server/laptop: finish Grafana dashboard from real metric names.
  - Then W1 write-up.

### 2026-05-17 - Bench suite launcher for LiteLLM proxy runs

- Added `benchmarks/scripts/run_bench_suite.py` with `snapshot_pre -> request_once -> measure_ttft_once -> run_sequential_benchmark -> snapshot_post`, auto-generated run IDs, strict JSON suite summary, and `--api-key` support.
- Validation: `uv run ruff check .` clean; `uv run pytest -q` = 113 passed.
- Outcome on 2026-05-19: validated live through LiteLLM Proxy for Kimi and DeepSeek.

### 2026-05-17 - LiteLLM Proxy + image pinning (laptop prep)

- Added `litellm` service, `litellm-config.yaml`, `.env.example` keys, image pinning, and compose docs.
- Outcome on 2026-05-19: LiteLLM smoke and proxy benchmark suites passed on the server.

### 2026-05-17 - Repo layout consolidation + off-roadmap archive

- Consolidated layout: `benchmarks/scripts/`, `serving/`, `results/`, `docs/`.
- Archived off-roadmap coding-agent eval work to branch `archive/coding-agent-tasks`.
- Validation: `uv run ruff check .` clean; `uv run pytest -q` = 102 passed.

### 2026-05-13 .. 2026-05-16 - Coding-agent eval harness exploration (archived)

A week of work on a synthetic coding-agent evaluation harness. Outcome: off-roadmap for Phase 1 and archived to branch `archive/coding-agent-tasks`.

### 2026-05-11 - Compose capture + DeepSeek small-model experiment

- Added Kimi/OpenWebUI compose work and experimental DeepSeek `vllm-small` service.
- Human note at the time: DeepSeek was benchmarked on the server and artifacts still needed to be pushed.
- Outcome on 2026-05-19: artifacts and corrected compose were pushed.

### 2026-05-08 - PR #7 review follow-up + server-metrics scripts

- Added server metrics parsing/snapshot/sampling scripts and strict failure records for `measure_ttft_once.py`.
- Added MLPerf compliance-status section to `docs/operations/benchmark-methodology.md`.
- Validation: `uv run ruff check .`; `uv run pytest -q` = 102 passed.

### 2026-05-07/08 - Benchmark normalisation + coding-agent task specs

- Normalised benchmark result schema, run-id layout, token-level metrics, workload spec, and strict JSON output.
- Later coding-agent task-spec work was archived with the off-roadmap branch.

### 2026-05-06 - Server bootstrap + Kimi-K2.6 first serve

- Captured server environment and got Kimi-K2.6 serving on 8×H200 via TP=8 + Eagle3 speculative decoding.
- Single-node DEP did not work for this run.
- OpenWebUI was stood up and verified.

> Pre-2026-05-06 handoff entries compacted. Source: `90d3fcdf8767baa09f53f537a686b165466786fc`.
> Full history: `git show 90d3fcdf8767baa09f53f537a686b165466786fc:docs/agent-state.md`.
