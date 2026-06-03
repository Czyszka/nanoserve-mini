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
- DeepSeek-V4-Flash runs alongside Kimi as service `vllm-small`, exposed on port 8004; current compose default is `DEEPSEEK_GPU_MEM_UTIL:-0.25` after the 2026-05-27 session, but W1 notes still need to reconcile this with the earlier 0.20 plan.
- OpenWebUI is running in compose, but the 2026-05-27 start snapshot showed it as unhealthy.
- LiteLLM Proxy runs on port 4000 and routes by `model` to Kimi and DeepSeek. Smoke tests through proxy passed for both upstreams.
- `run_bench_suite.py` has been run through LiteLLM Proxy for both Kimi K2.6 and DeepSeek-V4-Flash; results are committed.
- Prometheus + Grafana configuration exists under `serving/compose/`, including a provisioned Phase 1 dashboard (`grafana/provisioning/dashboards/vllm-phase1.json`). Containers have been started; the dashboard panels still need validation against real metric names with live load.
- Kimi K2.6 TTFT/TPOT parsing fixed (issue #31): `measure_ttft_once.py` now records a separate `ttft_any_token_seconds` / `tpot_any_token_seconds` covering reasoning-trace text (`delta.reasoning` / `delta.reasoning_content`) while `ttft_seconds` stays final-answer-only. Verified against the committed stream-debug artifacts.

Phase 1 deliverables still owed:

- **Prometheus + Grafana dashboard** showing useful live vLLM metrics during load — a provisioned dashboard JSON now exists; remaining work is validating its panels against real metric names with live load.
- **W1 write-up** — started, but still blocked on clean interpretation of 2026-05-27 evidence and missing T1/T6/T3 sweep artifacts.

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
  inventory and panel validation under live load still pending; 2026-05-27 only
  captured a LiteLLM metrics snapshot, not full dashboard evidence.
- **#37 — W1 write-up:** 2026-05-27 evidence analyzed and written up on the
  laptop. T4 LiteLLM Proxy and T7 host-directories justifications drafted; T8
  thread file migrated to a post-evidence document (paired direct-vs-proxy
  deltas, `summary.md` artifact added); T3 thread file rewritten as a partial
  0.25 runtime baseline with the `cap020` filename caveat; T1/T6/T5 carry
  explicit "not completed 2026-05-27" status notes; index Thread map +
  evidence-quality tracker + path A close-out list updated. **2026-06-03
  server slot ran only Cz. 0 + Cz. B + Cz. I (short slot): T3 attempted but
  caps 0.25 and 0.20 did NOT come healthy within the 300s healthcheck window
  (logs cut off mid weight-load, not a confirmed OOM — likely too-short
  startup wait); cap 0.15 not attempted; DeepSeek restored to compose default
  via `unset` (`log_restored_default.txt`).** T1 DEP, T6 Eagle3 ON/OFF, clean
  T3 sweep, and T5 dashboard validation still missing — next server slot must
  redo T3 with a longer healthcheck wait before C/H.

---

## Immediate next steps

Detailed tasks live in issues; `docs/plans/2026-05-19-post-server-laptop-plan.md`
sequences them. This section only points at active work — it is not a task list.

- **#37** — schedule a follow-up server slot for missing T1/T6/T3 evidence:
  DEP startup failure capture, Kimi Eagle3 ON/OFF comparison, and explicit
  DeepSeek VRAM cap sweep with filenames matching actual runtime caps.
- **#34** — after W1 evidence is coherent, validate Grafana panels against live
  metric names under load; do not block W1 on DCGM/GPU hardware panels.

**Next concrete step:** redo T3 sweep on the next server slot with a longer
`vllm-small` healthcheck wait (300s was too short — both 0.25 and 0.20
timed out mid weight-load on 2026-06-03), then run C (T6 Eagle3 ON/OFF + T1
DEP) and fix the LiteLLM `prometheus_callback` so T5 dashboard panels and a
T8 proxy-side cross-check can be validated under live load.

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
| Small-model experiment | `deepseek-ai/DeepSeek-V4-Flash` served as `DeepSeek-V4-Flash`, currently tested around 0.25 VRAM cap in the 2026-05-27 artifacts; reconcile before W1 claims |
| Compose file | `serving/compose/docker-compose.kimi-k2.6.yml` is the canonical Kimi/DeepSeek/OpenWebUI/LiteLLM compose |
| Interactive UI | OpenWebUI exists in compose but was unhealthy in the 2026-05-27 start snapshot |
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

2026-06-03 W1 server slot (Cz. 0 + B + CHECKPOINT 1 + I, short slot ~1h):

```text
git diff --check                                       OK
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml ps
  vllm        healthy (Eagle3-ON, 32 min uptime, not restarted)
  vllm-small  healthy (restored to compose default after sweep)
  litellm     healthy; prometheus/grafana up; open-webui unhealthy (known)
```

Artefakty w `results/runs/2026-06-03_w1_evidence/`:
`t3_deepseek_vram/{log_cap025_FAILED.txt, log_cap020_FAILED.txt,
nvidia_smi_cap{025,020}_FAILED.txt, cap{025,020}_status.txt,
log_restored_default.txt}` + `session/{start_commit,docker_ps_{start,end},
nvidia_smi_{start,end},artifact_manifest,artifact_count}.txt`. Cap 0.15 nie
zebrany. Commity: `ce7bd85` (T3) + `4622f5b` (session close-out).

2026-06-02 W1 T4 wording pass:

```text
git diff --check    OK
```

Docs-only change: rewrote T4 in a more formal technical-note style. No `ruff`
or `pytest` run.

2026-06-02 W1 T4 LiteLLM Proxy write-up:

```text
git diff --check    OK
```

Docs-only change: updated the T4 W1 justification, W1 tracker, and this handoff
state. No `ruff` or `pytest` run.

2026-06-02 W1 close-out tracker:

```text
git diff --check    OK
```

Docs-only change: updated the W1 top-level draft tracker and this handoff state.
No `ruff` or `pytest` run.

2026-06-02 W1 T7 host-directories write-up:

```text
git diff --check    OK
```

Docs-only change: updated the T7 W1 justification and this handoff state. No
`ruff` or `pytest` run.

2026-05-27 session documentation cleanup:

```text
GitHub contents API writes only; no local validation run in this environment.
```

Added `session/session_notes.md`, `session/artifact_manifest.txt`, and this agent-state update. No executable code changed. The many-file run-directory rename remains deferred to a local git checkout.

2026-05-26 documentation/config plan hardening:

```text
git diff --check    OK
```

Updated the 2026-05-27 server-session plan only, plus `.env.example`
documentation for `DEEPSEEK_GPU_MEM_UTIL`; no executable code changed.

2026-05-20 laptop validation (issue #31):

```text
uv run ruff check .     OK, all checks passed
uv run pytest -q        OK, 121 passed
```

Parser also smoke-checked against the committed Kimi stream-debug artifacts:
reasoning-only `stream_short_prompt` now reports `completed` with
`ttft_any_token_seconds` set (was `TTFT: n/a`); `stream_exact_ok` and
`stream_reasoning_prompt` report both content and any-token TTFT.

2026-05-21 documentation review:

```text
git diff --check                                      OK
uv run pytest benchmarks\scripts_tests\test_client.py benchmarks\scripts_tests\test_measure_ttft_once.py -q
                                                       OK, 39 passed
```

W1 T2 was tightened against repository evidence: DeepSeek is named as the
content-TTFT control, raw reasoning excerpts were redacted to structural
placeholders, `nonstream_short_prompt.sse.json` is no longer treated as a
behavioral control, and the additive schema wording now distinguishes field
semantics from schema identifier stability.

2026-05-19 server validation:

- Kimi and DeepSeek endpoints responded directly.
- OpenWebUI communicated with the running vLLM services.
- LiteLLM Proxy responded to `/v1/models` and `/v1/chat/completions` for both upstream models.
- `run_bench_suite.py` completed for both `kimi-k2.6` and `DeepSeek-V4-Flash` through LiteLLM Proxy.
- Prometheus and Grafana containers were started. Target/dashboard quality still needs follow-up.

---

## Handoff log

Newest entry first.

### 2026-06-03 - W1 server slot (partial: Cz. 0 + B + I only)

- Why: krótki slot (~1h) zamiast planowanych ~3h; cel ograniczony do
  bezpiecznego startu stacku + T3 sweep + close-out, bez bloku Kimi.
- Did: podniesiono stack (`vllm` + `vllm-small` + `litellm` + observability),
  zebrano snapshoty start/end, próba T3 sweep przez shell `export
  DEEPSEEK_GPU_MEM_UTIL`, recreate `vllm-small` per cap; restore DeepSeeka
  do compose default po sweepie; dwa commity (`ce7bd85`, `4622f5b`).
- Wynik T3: cap **0.25** i **0.20** nie weszły w `healthy` w 300s window
  (logi `log_cap*_FAILED.txt` urywają się na ładowaniu wag —
  `gpu_model_runner.py:4777 Starting to load model`, brak traceback OOM).
  **To prawdopodobnie za krótki timeout startowy, a nie realny OOM** —
  laptop-side trzeba przejrzeć logi pełne, zanim wyciągniemy wnioski.
  **Cap 0.15 nie próbowany.** Plik `log_restored_default.txt` potwierdza,
  że po `unset` DeepSeek wstał na compose default (0.25).
- Skipped: Cz. C (T6 ON/OFF + T1 DEP) i Cz. H (T5 dashboard) — brak czasu;
  zgodnie z planem regułą odcięcia priorytet to czysty stan stacku.
- Stan końcowy: Kimi `vllm` healthy 32 min (Eagle3-ON nietknięty), brak
  shell override capa, `git status` clean.
- Validation: `git diff --check` OK (artefakty + docs); brak `.py`,
  `ruff`/`pytest` niepotrzebne.
- Caveat na commit: message `4622f5b` "T6 Eagle3 ON/OFF, T1 DEP, session
  close-out" jest mylący — commit zawiera **tylko** session close-out
  (docker_ps_end, nvidia_smi_end, artifact_manifest). T6/T1 nie zostały
  wykonane.
- Next: laptop-side rozbiór `log_cap*_FAILED.txt` (czy to timeout startowy
  czy realny problem z capem); kolejny server slot — redo T3 z dłuższym
  healthcheck wait (np. 600s), potem Cz. C (T6 + T1).

### 2026-06-02 - W1 T4 wording pass

- Why: make T4 read less like tool advocacy and more like a scoped technical
  justification.
- Did: rewrote `docs/writeups/w1/t4-litellm-proxy.md` around the question,
  configuration evidence, narrow claim, implementation limits, proxy-hop
  trade-off, and rejected alternatives.
- Validation: `git diff --check` OK.
- Next: review T4 against the final W1 narrative, then continue the T1/T3/T6
  evidence path.

### 2026-06-02 - W1 T4 LiteLLM Proxy justification

- Why: turn the T4 placeholder into a concrete justification for LiteLLM Proxy
  as the Phase 1 multi-model access layer.
- Did: updated `docs/writeups/w1/t4-litellm-proxy.md` with repo config
  evidence, current-scope limits, the T8 overhead trade-off, rejected
  alternatives, and future link #39. Updated the W1 tracker to mark T4 done.
- Validation: `git diff --check` OK.
- Next: continue the path A close-out with the 2026-06-03 server slot for T1,
  T3, and T6, then fill the baseline table after evidence lands.

### 2026-06-02 - W1 close-out tracker

- Why: keep the remaining W1 work visible and grouped by what unblocks it.
- Did: updated `docs/writeups/w1-multi-model-serving-baseline.md` Thread map,
  evidence-quality tracker, path A close-out grouping, and follow-up list. T7 is
  marked done; T8 full R1-R8 remains intentionally deferred under #44.
- Validation: `git diff --check` OK.
- Next: run the 2026-06-03 server slot for T1 DEP, T3 clean VRAM sweep, and T6
  Eagle3 ON/OFF, then do the laptop write-up pass.

### 2026-06-02 - W1 write-up update from 2026-05-27 evidence (laptop)

- Why: turn the committed 2026-05-27 server artifacts into W1 write-up material per `docs/plans/2026-05-27-laptop-w1-writeup-update.md`.
- Did: analyzed all 40 T8 paired JSON files (10/model, 0 errors); added `results/runs/2026-05-27_w1_evidence/t8_proxy_overhead/summary.md`; migrated `w1/t8-litellm-overhead.md` from placeholder to post-evidence (routing overhead vs Kimi streaming-semantics change, T2 cross-ref); rewrote `w1/t3-deepseek-vram-budget.md` as a partial 0.25 baseline with the cap020 caveat; added status notes to `w1/t1-kimi-bringup.md`, `w1/t6-eagle3-speculative-decoding.md`, `w1/t5-observability.md`; updated index Thread map (T3/T8) and added "Evidence quality after 2026-05-27" + "Follow-up work".
- Key numbers: Kimi final-answer TTFT delta median +17 ms, any-token TTFT +0.40 s (~3×, streaming-semantics, not latency), output tok/s −5.6 %; DeepSeek TTFT +26 ms, E2E +34 ms (throughput not meaningful, completion_tokens≈2).
- Validation: `git diff --check` OK (docs-only; no `.py` touched).
- Next: schedule a server slot for T3 clean sweep (0.15/0.20/0.25), T1 DEP capture, T6 Eagle3 ON/OFF, T5 dashboard validation + fix LiteLLM `prometheus_callback`. Appended by the `sync-state` routine (`docs/templates/sync-state-agent.md`); compacted in place by the `tidy-docs` routine (`docs/templates/tidy-docs-agent.md`). Git is the archive.

### 2026-06-02 - W1 T7 host-directory justification

- Why: turn the T7 placeholder into a short justification for storing
  Prometheus/Grafana runtime data in explicit host bind mounts instead of Docker
  named volumes.
- Did: updated `docs/writeups/w1/t7-host-directories.md` with compose evidence,
  project-context rationale, portability/permissions trade-offs, and the
  rejected named-volume alternative.
- Validation: `git diff --check` OK.
- Next: continue #37 by scheduling the remaining T1/T3/T6 server evidence
  capture and T5 dashboard validation.

### 2026-05-27 - Server-session evidence triage and notes

- Why: make the 2026-05-27 server commit usable for W1 by documenting what evidence exists, what is partial, and what is missing.
- Did: added `session/session_notes.md`, added `session/artifact_manifest.txt`, and updated this handoff state. T8 evidence is usable for paired proxy-overhead analysis. T3 is partial and has a filename/runtime-cap mismatch (`cap020` file, runtime log shows `gpu_memory_utilization: 0.25`). T1 DEP and T6 Eagle3 ON/OFF are still missing.
- Validation: GitHub contents API writes only; no local `git diff --check` available here.
- Next: do the many-file run-directory rename from a local checkout, then analyze T8 deltas and schedule a follow-up server slot for T1/T3/T6.

### 2026-05-26 - W1 server-session plan hardening

- Why: reduce avoidable server-slot risk before the 2026-05-27 W1 evidence session.
- Did: made `RUN_DIR` initialization explicit in Cz. 0, made LiteLLM key extraction fail fast, corrected T5 Prometheus snapshots to use `vllm:kv_cache_usage_perc`, replaced ad hoc Python URL quoting with `curl --data-urlencode`, added an artifact manifest step, and documented `DEEPSEEK_GPU_MEM_UTIL` in `.env.example`.
- Validation: `git diff --check` OK.
- Next: run `docs/plans/2026-05-27-server-session.md` on the GPU server and commit the resulting W1 evidence artifacts.

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
