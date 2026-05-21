# Agent State - nanoserve-mini

Repo-tracked handoff state for Claude Code, Codex, and human work. Keep it concise
and current. Maintained by the `sync-state` / `tidy-docs` routines (see
`docs/templates/`); Git is the archive.

---

## Summary cursor

- Last summarized commit: `a7ce83f`
- Last summarized at: 2026-05-20
- 2026-05-20 sync: laptop follow-up - #31 Kimi parser fix merged, #32 benchmark artifact ignore cleanup closed, #33 server session summary added, #35 Grafana dashboard provisioning merged, `rg` installed on the laptop and wired into env checks.

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
- Prometheus + Grafana configuration exists under `serving/compose/`, including a provisioned Phase 1 dashboard (`grafana/provisioning/dashboards/vllm-phase1.json`). Containers have been started; the dashboard panels still need validation against real metric names with live load.
- Kimi K2.6 TTFT/TPOT parsing fixed (issue #31): `measure_ttft_once.py` now records a separate `ttft_any_token_seconds` / `tpot_any_token_seconds` covering reasoning-trace text (`delta.reasoning` / `delta.reasoning_content`) while `ttft_seconds` stays final-answer-only. Verified against the committed stream-debug artifacts.

Phase 1 deliverables still owed:

- **Prometheus + Grafana dashboard** showing useful live vLLM metrics during load — a provisioned dashboard JSON now exists; remaining work is validating its panels against real metric names with live load.
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

---

## Important project docs

Read these before non-trivial changes:

- `AGENTS.md` / `CLAUDE.md` - agent rules, validation, scope boundaries, secrets/results policy.
- `docs/project/roadmap.md` - durable scope, phases, Definition of Done, and out-of-scope boundaries.
- `docs/operations/infrastructure.md` - machine roles, server/laptop workflow, and environment policy.
- `docs/operations/benchmark-methodology.md` - benchmark modes, result schema contract, and `--run-id` layout.
- `serving/compose/` and `serving/runbooks/` - live stack configuration and operational commands.
- `docs/README.md` - full documentation map when more context is needed.

Do not rewrite the roadmap/scope document unless explicitly asked.

---

## Current technical direction

Benchmark scripts use MLPerf-inspired lite modes. The script ↔ `benchmark_mode` ↔
schema table, the `--run-id` output layout, and the `run_bench_suite.py`
one-command launcher are documented in `docs/operations/benchmark-methodology.md`;
schema identifiers are exported from `benchmarks/scripts/_schemas.py`.

---

## In flight

Active issues and where each stands — the project's live pulse. One line each:
status, not a task list. Update when work moves.

- **#34 — observability/dashboard:** dashboard JSON provisioned; metric-name
  inventory and panel validation under live load still pending.
- **#37 — W1 write-up:** methodology + thread inventory (T1–T8) drafted;
  T2 evidence captured (stream-debug artefacts); T1/T3/T6/T8 await the next
  server session; T4/T5 laptop analysis not started.

---

## Immediate next steps

Detailed tasks live in issues; `docs/plans/2026-05-19-post-server-laptop-plan.md`
sequences them. This section only points at active work — it is not a task list.

- **#34** — observability: TTFT reconciliation, DCGM/GPU hardware metrics, Grafana
  panel validation under live load.
- **#37** — W1 write-up: methodology + thread inventory T1–T8; evidence capture
  split between server and laptop.

**Next concrete step:** build the first Grafana dashboard from a real metric-name
inventory (#34), then start W1 laptop-side analysis (#37 — T2, T4, T5). Server-only
capture (#37 — T1, T3, T6, T8; `rg` install) waits for the next GPU session.

Deferred items (GPU sampling in `run_bench_suite.py`, `aggregate_runs.py` Wave C)
are tracked under "Open questions / blockers" below.

---

## Standard commands

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

- [ ] Which exact vLLM metric names should drive the first Grafana dashboard? Need inventory from live `/metrics` and/or Prometheus.
- [ ] Should `sample_gpu_metrics` be integrated into `run_bench_suite.py`, or stay as a separate explicit tool?
- [ ] Which Kimi-K2.6 memory parameters are stable enough for long runs while DeepSeek stays up beside it?
- [ ] When to implement `benchmarks/scripts/aggregate_runs.py` (Wave C)?

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

---

## Handoff log

Newest entry first. Appended by the `sync-state` routine (`docs/templates/sync-state-agent.md`); compacted in place by the `tidy-docs` routine (`docs/templates/tidy-docs-agent.md`). Git is the archive.

### 2026-05-20 - Phase 1 laptop follow-up: #31 parser fix, Grafana provisioning, tooling

- Why: clear the post-server laptop backlog and align laptop/server tooling.
- Did: merged #31 Kimi reasoning TTFT/TPOT fix (PR #36), closed #32 benchmark artifact ignore cleanup, added #33 server session summary, and merged #35 Grafana dashboard provisioning; installed `rg` on the laptop and wired it into the env checks, with a queued task to install it on the server.
- Range: `e3eaf0c..a7ce83f` plus the #33 summary doc update
- Validation: OK (ruff clean, pytest 121 passed).
- Next: validate the Grafana dashboard against live metrics, add DCGM/GPU hardware metrics under issue #34, then prepare W1.

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
- Next at session end:
  - Laptop follow-ups were issue #31, issue #32, and issue #33; these are now closed/handled.
  - Server/laptop: validate Grafana dashboard from real metric names and add GPU hardware metrics.
  - Then W1 write-up.

### 2026-05-17 - Bench suite launcher for LiteLLM proxy runs

- Added `benchmarks/scripts/run_bench_suite.py` with `snapshot_pre -> request_once -> measure_ttft_once -> run_sequential_benchmark -> snapshot_post`, auto-generated run IDs, strict JSON suite summary, and `--api-key` support.
- Validation: `uv run ruff check .` clean; `uv run pytest -q` = 113 passed.
- Outcome on 2026-05-19: validated live through LiteLLM Proxy for Kimi and DeepSeek.

### 2026-05-17 - LiteLLM Proxy + image pinning (laptop prep)

- Added `litellm` service, `litellm-config.yaml`, `.env.example` keys, image pinning, and compose docs.
- Outcome on 2026-05-19: LiteLLM smoke and proxy benchmark suites passed on the server.

> Pre-2026-05-17 handoff entries compacted. Source: `4d6fac7800047c8c54ee32e4235ab6ce62abcc5d`.
> Full history: `git show 4d6fac7800047c8c54ee32e4235ab6ce62abcc5d:docs/operations/agent-state.md`.
