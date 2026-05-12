# Agent State - nanoserve-mini

This file is the repo-tracked handoff state for Claude Code, Codex, and human work.

Keep it concise and current. Update it after meaningful repo changes, especially before committing, pushing, or handing work to another agent.

The `sync-state` routine (see `docs/templates/sync-state-agent.md`) appends to this file. The `tidy-docs` routine (see `docs/templates/tidy-docs-agent.md`) compacts it in place. Git is the archive — no separate handoff archive directory.

---

## Summary cursor

- Last summarized commit: `46e2129`
- Last summarized at: 2026-05-11

The `sync-state` routine reads this block to find the diff window. Update only via the routine.

---

## Canonical file roles

- `CLAUDE.md` - stable instructions for Claude Code.
- `AGENTS.md` - stable instructions for Codex.
- `docs/agent-state.md` - current project state, decisions, next step, and blockers.
- `ROADMAP.md` - project scope; do not change it without an explicit decision.

Note: the current roadmap content in this repo is stored as `docs/project/roadmap.md`. Treat it as the current scope document unless a root `ROADMAP.md` is added later.

---

## Current phase

**Phase 1 - first vLLM run completed; benchmark harness normalization + dashboard-ready schema completed; server-metrics scripts landed; Kimi/OpenWebUI compose capture in progress.**

Server is up, environment snapshot is committed, Docker vLLM image is installed, Kimi-K2.6 is downloaded and served successfully through vLLM with TP=8.

OpenWebUI is running on the server and connected to the vLLM OpenAI-compatible endpoint.

The repo now has:

- MLPerf-inspired lite output layout for the first benchmark scripts.
- Token-level metrics in benchmark output: TPOT, prompt/completion tokens, output tokens/s (via `stream_options.include_usage=true`).
- Structured `controls.workload_spec`, explicit `controls.concurrency`, unique `run_uuid` per execution, and a `server_metrics` block populated by `scripts/collect_metrics_snapshot.py` and `scripts/sample_gpu_metrics.py`.
- Shared schema/mode/methodology constants in `scripts/_schemas.py`.
- Tightened synthetic coding-agent task specifications for PowerShell, Python, C++, and C#.
- MLPerf-inspired-lite compliance disclaimer in `docs/benchmark-methodology.md`.
- A server work plan for MiniMax-M2.7 / coding-agent / dual-model evaluation.
- A first tracked Docker Compose/runbook capture for Kimi-K2.6, OpenWebUI, and an experimental smaller-model service.
- Human-reported server work that is not yet pushed: DeepSeek-V4-Flash benchmark outputs and the latest compose need to be imported at the start of the next session.

---

## Current known status

- GitHub repo exists: `https://github.com/Czyszka/nanoserve-mini.git`
- Local Windows laptop bootstrap is done.
- Python workflow uses `uv`.
- `ruff` and `pytest` are configured.
- `.gitattributes` exists to normalize line endings.
- Local research PDFs are kept outside Git in ignored `docs/learning/papers/`.
- **Server is available**: ubuntusrv2 (Ubuntu 24.04, 8x H200 NVL 143 GB, CUDA 13.2, driver 595.58.03).
- **`results/raw/server_env_snapshot.json` committed** (2026-05-06); generated with `scripts/check_server_env.py` on ubuntusrv2 and records Ubuntu 24.04.2, Python 3.12.11, uv 0.11.8, Docker 28.5.0 / Compose v2.39.4, 8x H200 NVL, driver 595.58.03, CUDA 13.2.
- **vLLM Docker image installed** on the server (`vllm/vllm-openai:v0.20.0-cu130`).
- **Kimi-K2.6 model download completed** in named volume `nanoserve-hf-cache`.
- **Kimi-K2.6 serves successfully through `vllm serve` with TP=8.**
- **Single-node DEP attempt did not work** for this run; current working path is TP=8.
- **Speculative decoding works correctly** with Eagle3 speculative head (`lightseekorg/kimi-k2.6-eagle3-mla`).
- **OpenWebUI container is running on the server** and connected to `vllm serve`; Kimi-K2.6 is visible in OpenWebUI and answers requests.
- Current Kimi-K2.6 launch parameters still need tuning, especially GPU memory reservation/utilization, so a second smaller model can fit on the same server.
- `infra/compose/docker-compose.kimi-k2.6.yml` now tracks a Docker Compose setup for Kimi-K2.6 + OpenWebUI plus experimental `vllm-small` on port 8004 using `deepseek-ai/DeepSeek-V4-Flash`.
- `docs/operations/runbooks/vllm-kimi_k2_6-dockercompose.yaml` records a smaller Kimi/OpenWebUI compose reference, but it may not match the latest compose command exactly.
- Human report from 2026-05-11 server session: latest server-side changes were not pushed; DeepSeek-V4-Flash completed `request_once`, TTFT, and repeated benchmark tests; latest compose has large model + small model + OpenWebUI, with the small model capped at 20% VRAM across 8 GPUs so remaining VRAM can be reserved for the large model.
- `.claude/` remains untracked locally.
- **Task specs 01-04 are tightened on `main`:**
  - Task 01 PowerShell export/environment backup.
  - Task 02 Python OpenAI-compatible streaming probe.
  - Task 03 C++ TokenBuffer correctness/safety/hot path.
  - Task 04 C# allocation-aware parser refactor.
- **Benchmark/metrics producer scripts are on `main`:**
  - `scripts/request_once.py`
  - `scripts/measure_ttft_once.py`
  - `scripts/run_sequential_benchmark.py`
  - `scripts/collect_metrics_snapshot.py`
  - `scripts/sample_gpu_metrics.py`

---

## Important project docs

Read these before making non-trivial changes:

- `docs/project/roadmap.md` - current scope, phases, and definition of done.
- `docs/operations/infrastructure.md` - machine roles and workflow.
- `docs/operations/runbooks/server-env-bootstrap.md` - reusable runbook for GPU server env bootstrap (env snapshot + vLLM setup decision).
- `docs/benchmark-methodology.md` - MLPerf-inspired lite benchmark modes, result schema contract, compliance disclaimer, `--run-id` layout, and server metrics.
- `docs/plans/2026-05-11-server-work-plan.md` - Monday server work plan: MiniMax-M2.7, coding agent check, dual-model benchmarks.
- `benchmarks/coding-agent-tasks/README.md` - synthetic coding-agent task suite overview.
- `docs/reading-list.md` - papers by phase.
- `docs/learning/nvidia-self-paced-courses.md` - optional NVIDIA courses.
- `AGENTS.md` - Codex-specific repo instructions.
- `CLAUDE.md` - Claude Code-specific repo instructions.

Do not rewrite the roadmap/scope document unless explicitly asked.

---

## Current technical direction

Server is active. vLLM Docker is installed. Kimi-K2.6 is serving successfully with TP=8. OpenWebUI is connected and can be used for interactive checks. Today's repo changes moved from loose launch notes toward a tracked Compose setup, but the repo is behind the latest server work: DeepSeek-V4-Flash benchmark results and the final compose from the server session still need to be brought back into Git.

The benchmark scripts use these MLPerf-inspired lite modes:

| Script | Benchmark mode | Schema |
|---|---|---|
| `scripts/request_once.py` | `singlestream_lite_correctness` | `nanoserve-mini.request-once.v2` |
| `scripts/measure_ttft_once.py` | `singlestream_lite_latency` | `nanoserve-mini.ttft-once.v2` |
| `scripts/run_sequential_benchmark.py` summary | `singlestream_lite_repeated` | `nanoserve-mini.sequential-bench.v3` |
| `scripts/run_sequential_benchmark.py` row | `singlestream_lite_repeated` | `nanoserve-mini.sequential-bench-row.v3` |
| `scripts/collect_metrics_snapshot.py` | `server_metrics` | `nanoserve-mini.server-metrics-snapshot.v1` |
| `scripts/sample_gpu_metrics.py` | `server_metrics` | `nanoserve-mini.gpu-samples-meta.v1` |

All benchmark and server-metrics scripts support `--run-id` and write under:

```text
results/runs/<run_id>/
```

Expected live-run layout:

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
```

Immediate next steps, in order:

1. At the start of the next server session, recover and commit the unpushed server-side artifacts:
   - latest Docker Compose with large model + `vllm-small` + OpenWebUI,
   - DeepSeek-V4-Flash `request_once`, TTFT, and repeated benchmark outputs,
   - short summary of launch parameters, including the 20% VRAM cap for the small model across 8 GPUs.
2. Reconcile the latest server compose with `infra/compose/docker-compose.kimi-k2.6.yml` and decide whether TP=8 Kimi, EP/DP Kimi, and small-model services should live in one compose file or separate profiles/files.
3. Pin Docker images to exact versions or digests before collecting comparable benchmark runs.
4. Decide whether OpenWebUI should keep one endpoint, use semicolon-separated `OPENAI_API_BASE_URLS`, or move this routing behind LiteLLM/LLM proxy.
5. Finish DeepSeek-V4-Flash coding-agent/programming tests using the existing synthetic task specs or a clearly documented subset.
6. Download one additional smaller model for comparison, run the same benchmark sequence, and run the same programming tests.
7. Compare DeepSeek-V4-Flash vs the additional small model on latency, output quality for coding tasks, stability, VRAM use, and fit alongside the large model.
8. Validate the metrics scripts live on the server:
   - `scripts/collect_metrics_snapshot.py --phase pre`
   - `scripts/sample_gpu_metrics.py` during a benchmark window
   - `scripts/collect_metrics_snapshot.py --phase post`
9. Run or repeat the normalized benchmark sequence with one shared `--run-id` per model:
   - `uv run python -m scripts.request_once ... --run-id <run_id>`
   - `uv run python -m scripts.measure_ttft_once ... --run-id <run_id>`
   - `uv run python -m scripts.run_sequential_benchmark ... --run-id <run_id>`
10. Inspect the generated `results/runs/<run_id>/` trees and decide whether to commit raw results directly or summarize them first.
11. Check whether already-installed Claude Code CLI can talk to local vLLM; if not, install/use OpenCode fallback.
12. Later: implement fact-table aggregator (`scripts/aggregate_runs.py`, Wave C) for dashboard/dataframe consumption.

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

Benchmark and metrics examples:

```bash
RUN_ID=2026-05-11_kimi_tp8_baseline

uv run python -m scripts.collect_metrics_snapshot \
  --base-url http://127.0.0.1:8000 \
  --run-id "$RUN_ID" \
  --phase pre

uv run python -m scripts.request_once \
  --base-url http://127.0.0.1:8000 \
  --model moonshotai/Kimi-K2.6 \
  --run-id "$RUN_ID"

uv run python -m scripts.measure_ttft_once \
  --base-url http://127.0.0.1:8000 \
  --model moonshotai/Kimi-K2.6 \
  --run-id "$RUN_ID"

uv run python -m scripts.sample_gpu_metrics \
  --run-id "$RUN_ID" \
  --interval-ms 500 \
  --duration-s 60

uv run python -m scripts.run_sequential_benchmark \
  --base-url http://127.0.0.1:8000 \
  --model moonshotai/Kimi-K2.6 \
  --warmup 1 --runs 5 \
  --run-id "$RUN_ID"

uv run python -m scripts.collect_metrics_snapshot \
  --base-url http://127.0.0.1:8000 \
  --run-id "$RUN_ID" \
  --phase post
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
| Compose file | `infra/compose/docker-compose.kimi-k2.6.yml` is the current tracked compose draft for Kimi/OpenWebUI plus experimental `vllm-small`; verify it against the live server before treating it as canonical |
| Interactive UI | OpenWebUI container connected to vLLM OpenAI-compatible endpoint |
| Compose capture | Use tracked Compose/runbook files for reproducible Kimi/OpenWebUI launch notes, but verify them against the live server command before treating them as canonical |
| Secondary model experiment | DeepSeek-V4-Flash is the current small-model experiment; human-reported server run completed request_once, TTFT, and repeated benchmarks, but artifacts are not yet pushed |
| VRAM split | Current target is small model capped at 20% VRAM across all 8 GPUs, leaving the rest for the large model |
| Image pinning | Current compose still uses floating image tags; pin exact image versions/digests before comparable benchmark runs |
| Coding agent | Check Claude Code CLI with local vLLM first; if blocked, use OpenCode fallback |
| Benchmark methodology | MLPerf-inspired lite, not official MLPerf; first modes are SingleStream-lite correctness/latency/repeated |
| Benchmark output | `results/runs/<run_id>/<benchmark_mode>/` plus `results/runs/<run_id>/server_metrics/` |
| Coding tasks | Synthetic, separate temp repo during evaluation; final result compared by model/agent commit |
| Agent memory | `docs/agent-state.md` is repo-tracked shared handoff |
| Claude Code entrypoint | root `CLAUDE.md` |
| Codex entrypoint | root `AGENTS.md` |
| State updates | Codex and Claude Code must update `docs/agent-state.md` after meaningful work and before commit/push handoff |
| Local papers | Store read scientific papers in ignored `docs/learning/papers/`; commit bibliographic notes/summaries separately if useful |

---

## Open questions

- [ ] Record exact working TP=8 server command/config in repo.
- [ ] Does the latest Kimi compose command actually match the working server launch, or should TP=8 and EP/DP variants be split into separate files?
- [ ] Import unpushed server-side compose and DeepSeek-V4-Flash benchmark results.
- [ ] Did `deepseek-ai/DeepSeek-V4-Flash` coding-agent/programming tests pass, and what failure modes appeared?
- [ ] Which second small model should be downloaded for direct comparison with DeepSeek-V4-Flash?
- [ ] Should OpenWebUI connect only to Kimi on port 8000 or expose both Kimi and the smaller/experimental endpoint?
- [ ] Which exact Docker image tags/digests should replace floating `latest`/`main` tags for reproducible runs?
- [ ] Validate benchmark + metrics scripts end-to-end on the server.
- [ ] Which Kimi-K2.6 `vllm serve` memory parameters allow a second smaller model to fit on the same server?
- [ ] Does `uv sync --extra dev` work on the server? (not yet tested, not blocking)
- [ ] Should raw result files be committed directly or summarized after first GPU run?
- [ ] Does Claude Code CLI work directly with local vLLM in this setup, or do we need OpenCode?
- [ ] When to implement `scripts/aggregate_runs.py` (Wave C)?

---

## Last validation

Local laptop validation on 2026-05-08 after PR #7 review follow-ups (failure-record path in `measure_ttft_once`, `completed=False` on no-content streams, stricter argument guards in `sample_gpu_metrics`) on top of the merged `origin/main`:

```text
uv run ruff check .     OK, all checks passed
uv run pytest           OK, 102 passed
```

Note: after PR #2 review, Claude pushed follow-up fixes for `request_once --raw`, `resolve_output_path(None)`, and measured-only sequential throughput before merge.

The 2026-05-08 task-spec tightening on `main` was documentation-only and was applied through GitHub connector commits; `uv run ruff check .` / `uv run pytest` were not rerun after those documentation changes.

---

## Handoff log

Newest entry first. Appended by the `sync-state` routine (`docs/templates/sync-state-agent.md`); compacted in place by the `tidy-docs` routine (`docs/templates/tidy-docs-agent.md`). Git is the archive.

### 2026-05-11 - Server plan updated after DeepSeek run

- Why: keep `docs/plans/2026-05-11-server-work-plan.md` aligned with the actual post-session state.
- Did: added a top-level update noting unpushed server artifacts, completed DeepSeek-V4-Flash request/TTFT/repeated benchmarks, compose VRAM split, image-pinning TODO, and next-session comparison work.
- Validation: docs-only; no code tests run.
- Next: push the plan update, then start the next server session by importing the missing compose/results artifacts.

### 2026-05-11 - Compose README aligned with YAML

- Why: remove stale single-node DEP/runbook text from `infra/compose/README.md`.
- Did: rewrote the README around the actual compose services: Kimi on 8000, DeepSeek-V4-Flash `vllm-small` on 8004, and OpenWebUI on 3000.
- Validation: `git diff --check` OK; no code tests run for docs-only change.
- Next: import the unpushed server compose/results, then verify the documented service commands against the live server.

### 2026-05-11 - Human server-session note: unpushed DeepSeek benchmark work

- Why: record server work that was completed but not yet pushed back into the repo.
- Did: DeepSeek-V4-Flash was benchmarked with request_once, TTFT, and repeated runs; latest server compose includes large model, small model, and OpenWebUI, with small model capped at 20% VRAM across 8 GPUs.
- Validation: server-side only; artifacts and exact commands still need to be imported.
- Next: first action next session is to recover/push server artifacts, then finish small-model coding tests and compare against one more downloaded small model.

### 2026-05-11 - Compose capture for Kimi/OpenWebUI and small-model attempt

- Why: capture today's server launch work in repo-tracked infrastructure instead of leaving it only in shell history.
- Did: added a Kimi-K2.6 compose/runbook reference, folded OpenWebUI into compose, and added an experimental `vllm-small` service for `deepseek-ai/DeepSeek-V4-Flash`.
- Range: `b5f0ab7..46e2129` (5 infra/docs commits, plus one prior state-refresh commit skipped)
- Validation: skipped locally; live server behavior must be verified from the GPU host.
- Next: reconcile compose against the exact working server command, then record success/failure for Kimi, OpenWebUI, and the `vllm-small` service.

### 2026-05-08 - Refreshed state after PR #7 merge

- Why: align `agent-state.md` with the final merged state after PR #7 and remove stale "add metrics scripts" next-step wording.
- Did: updated summary cursor to `b5f0ab7`; marked dashboard-ready schema, server-metrics scripts, MLPerf compliance disclaimer, and tightened task specs as landed; changed next steps from "add metrics scripts" to live server validation and benchmark execution; added example command sequence using one shared `RUN_ID`.
- Validation: documentation-only update through GitHub connector; no tests rerun.
- Next: pull latest `main` on the server, validate metrics and benchmark scripts live against Kimi-K2.6 TP=8, then proceed to MiniMax-M2.7 / coding-agent / dual-model work.

### 2026-05-08 - PR #7 review follow-up + merge with main

- Why: PR #7 went `dirty` after the Task 01-04 spec tightening on main; reviewer also flagged three correctness issues in the new code.
- Did:
  - Merged `origin/main` into the PR branch and resolved the only conflict (`docs/agent-state.md`); kept both narratives (server-metrics work + coding-agent task tightening).
  - `scripts/measure_ttft_once.py`: HTTP/transport/stream errors now produce a v2-schema failure record (controls + request + server_metrics stub preserved, `completed=False`, all token-derived metrics `None`, non-null `error` string with type and message). `main()` returns 1 on failure and prints the error to stderr. Helper `_failure_result()` keeps the e2e_seconds field meaningful (elapsed-until-failure).
  - `scripts/measure_ttft_once.measure_stream`: `completed` is now `bool(output_parts)` rather than always True. A role-only stream that ends cleanly returns `completed=False` so dashboards do not count zero-token responses as successful generations.
  - `scripts/sample_gpu_metrics.py`: argparse-side guards added for `--duration-s > 0` and `--samples > 0` when provided; the existing "at least one of them required" rule is preserved.
  - Tests: added `test_measure_stream_handles_empty_stream`, extended the role-only test to assert `completed is False`, added `test_main_writes_failure_record_on_connect_error` and `test_main_writes_failure_record_on_http_5xx` (failure record shape, rc=1, error string contents, strict JSON, server_metrics stub kept, workload_spec kept), added 4 sampler argument-guard tests (zero/negative duration, zero/negative samples). 95 → 102 passing.
- Commands run: `uv run ruff check .` (pass), `uv run pytest -q` (102 passed).
- Next: unchanged — pick from live-run on server, fact-table aggregator (Wave C), or recording the working TP=8 `vllm serve` command.

### 2026-05-08 - Tightened all coding-agent task specifications

- Why: close the task-spec review loop before moving to metrics scripts and server execution.
- Did: merged PR #3 for Task 01 PowerShell; applied Task 02 Python, Task 03 C++, and Task 04 C# TASK.md updates directly to `main` because their PRs conflicted only on stale `docs/agent-state.md` hunks; closed PRs #4/#5/#6 as superseded after preserving their intended TASK.md changes.
- Commits: `c149c79` Task 01, `69d9f6f` Task 02, `57a5e0b` Task 03, `f83ef7a` Task 04.
- Current repo state: all four synthetic coding-agent task specs are tightened and ready for starter-repo/hidden-test generation later.
- Validation: not rerun after docs-only updates.
- Next: implement metrics snapshot/sampling scripts, then run live `--run-id` benchmark sequence on the server.

### 2026-05-08 - Compliance-status disclaimer in benchmark methodology

- Why: make it impossible to mistake `mlperf_inspired_lite` results for MLPerf-compliant submissions in write-ups, slides, or CV claims, and give a ready-to-use phrasing for that distinction.
- Did: added a "Compliance status" section near the top of `docs/benchmark-methodology.md` (right after the intro, before "Why MLPerf matters") with: a blockquote warning, a side-by-side table of what MLPerf requires vs what this lab provides, what the lab borrows from MLPerf (scenarios, warmup/measured discipline, controls), and a verbatim communication-rule paragraph for portfolio/CV use. The `methodology` label in result files remains `mlperf_inspired_lite` — the doc now reinforces why the `_lite` matters.
- Validation: `uv run ruff check .` (pass), `uv run pytest -q` (95 passed).
- Next: unchanged — pick from live-run on server, aggregator (Wave C), or recording the working TP=8 `vllm serve` command.

### 2026-05-08 - Server metrics scripts (collect_metrics_snapshot, sample_gpu_metrics)

- Why: populate the `server_metrics` null-stub block introduced this morning so benchmark JSON files can report real GPU/KV/prefix-cache numbers; provide interval GPU sampling for time-series GPU charts.
- Did:
  - Added `scripts/_server_metrics.py` with two pure parsers (`parse_prometheus_text`, `parse_nvidia_smi_csv`), an `nvidia-smi` query field set used by both scripts (`NVIDIA_SMI_QUERY_FIELDS`, `NVIDIA_SMI_FIELD_MAP`, `CSV_COLUMNS`), helpers `first_value`, `select_vllm_aggregate`, `total_gpu_memory_used_gb`. NaN/+Inf/-Inf are converted to `None` so strict-JSON output stays valid.
  - Added `scripts/collect_metrics_snapshot.py`: one-shot scrape of vLLM `/metrics` + `nvidia-smi`. Output: `results/runs/<run_id>/server_metrics/snapshot_<phase>.json` with phases `pre`/`mid`/`post`/`adhoc`. Writes `aggregate` block matching the `server_metrics` stub keys (`gpu_memory_used_gb`, `kv_cache_usage`, `prefix_cache_hit_rate`). Best-effort: scrape failures are recorded inline, file is still written. Schema: `nanoserve-mini.server-metrics-snapshot.v1`.
  - Added `scripts/sample_gpu_metrics.py`: interval CSV sampling via repeated `nvidia-smi` calls. Output: `results/runs/<run_id>/server_metrics/gpu_samples.csv` plus sidecar `gpu_samples_meta.json` (schema `nanoserve-mini.gpu-samples-meta.v1`) with `interval_ms`, `duration_s`, `samples`, run_id/run_uuid, summary (ticks, samples_written, errors). Requires `--duration-s` or `--samples`. Loop body, clocks, and runner are injectable for tests.
  - Tests: `tests/test_server_metrics.py` (parsers, NaN/Inf handling, nvidia-smi malformed rows, total-GPU-memory aggregator), `tests/test_collect_metrics_snapshot.py` (mocked httpx for /metrics + mocked subprocess for nvidia-smi; success/5xx/missing-cmd/timeout/nonzero-exit paths; main() with `--run-id` and `--output`; strict JSON), `tests/test_sample_gpu_metrics.py` (sample loop with FakeClock, deadline stop, error-resilient loop, CSV + meta sidecar; CLI guards on interval and stop conditions). 67 → 95 passing.
  - `_schemas.py` gained `SCHEMA_SERVER_METRICS_SNAPSHOT` and `SCHEMA_GPU_SAMPLES_META` constants.
  - `docs/benchmark-methodology.md`: extended `--run-id` layout to include `server_metrics/` directory; new "Server-side metrics" section describing both scripts and the aggregator hook.
- Commands run: `uv run ruff check .` (pass after autofix sorted imports in three new test files), `uv run pytest -q` (95 passed).
- Decision: aggregator (planned `scripts/aggregate_runs.py`) deferred to a later session; this session's focus was the producer side.
- Next: pick one of (a) live-run end-to-end on the server, (b) write the fact-table aggregator, (c) record the working TP=8 `vllm serve` command/runbook.

### 2026-05-08 - Benchmark harness review + Wave A+B schema upgrade

- Why: validate yesterday's benchmark scripts against the MLPerf-inspired-lite methodology and against the ROADMAP Benchmark Contract; tighten the JSON output shape so it can feed a future dashboard.
- Did:
  - Added `scripts/_schemas.py` with shared `METHODOLOGY`, mode identifiers, and schema-version constants imported by all three scripts.
  - Extended `RunControls` with `concurrency`, `run_uuid` (unique per execution; `make_run_uuid()` helper), and structured `workload_spec` (built by `build_workload_spec()`); added `null_server_metrics()` stub helper.
  - `_client.py` now injects `stream_options.include_usage=true` by default in `chat_completion_stream` (caller-supplied options win); added `extract_stream_usage`.
  - `measure_ttft_once.py` now records `prompt_tokens`, `completion_tokens`, `total_tokens`, `tpot_seconds` (decode-only: `(e2e - ttft) / max(1, completion_tokens - 1)`), `output_tokens_per_second`, `server_metrics` stub, structured `workload_spec`, `run_uuid`, explicit `concurrency=1`. Schema bumped `ttft-once.v1 → v2`.
  - `run_sequential_benchmark.py` per-row JSONL gains `tpot_seconds`, `prompt_tokens`, `completion_tokens`, `output_tokens_per_second`; summary gains `summary.tpot_seconds`, `summary.prompt_tokens`, `summary.completion_tokens` aggregate blocks and `summary.output_tokens_per_second` (token-level throughput); top-level `server_metrics` stub. Schema bumped `sequential-bench.v2 → v3`, `sequential-bench-row.v2 → v3`.
  - `request_once.py` schema bumped `request-once.v1 → v2`; record now carries `controls.run_uuid`, `controls.concurrency`, `controls.workload_spec`, and `server_metrics` stub.
  - Added `docs/benchmark-methodology.md` "Result schema contract" section documenting the dashboard-facing field/type/units table per mode.
  - Tests updated and extended (49 → 67 passing): new tests for `make_run_uuid`, `null_server_metrics`, `build_workload_spec`, `compute_tpot_seconds`, `compute_output_tokens_per_second`, usage chunk handling in `measure_stream`, `chat_completion_stream` injecting `stream_options.include_usage`, sequential summary token aggregates, and server_metrics stub in summary.
- Commands run: `uv sync --extra dev`, `uv run ruff check .` (pass), `uv run pytest -q` (67 passed).
- Decision: not bumping ROADMAP scope — these are MLPerf-inspired-lite refinements consistent with the existing Benchmark Contract section. Server-side `gpu_memory_used_gb`, `kv_cache_usage`, `prefix_cache_hit_rate` remain `null` until `scripts/collect_metrics_snapshot.py` lands.
- Next: implement `scripts/collect_metrics_snapshot.py` and `scripts/sample_gpu_metrics.py` to populate `server_metrics`; then run the live `--run-id` benchmark sequence on the server.

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
