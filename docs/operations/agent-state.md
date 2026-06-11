# Agent State - nanoserve-mini

Repo-tracked handoff state for Claude Code, Codex, and human work. Keep it concise
and current. Maintained by the `sync-state` / `tidy-docs` routines (see
`docs/templates/`); Git is the archive.

---

## Summary cursor

- Last summarized commit: `3fd150b`
- Last summarized at: 2026-06-12 (T9 detail + clarity passes, #50 comment posted)
- Note: previous cursor `520d788` is dangling in the current history (laptop-side
  rewrite); fallback used the 2026-06-10 tidy commit `e08f762` as the sync point.
- 2026-06-10 tidy: handoff-log and validation entries older than 2026-06-06
  compacted in place (period summaries + source SHA kept inline); full history
  via `git show 520d788:docs/operations/agent-state.md`.

---

## Current phase

**Phase 1 (weeks 1-3 of 12)** — vLLM serving baseline + observability + multi-model proxy.

Phase 1 minimum milestone met: proxy/benchmark done, W1 write-up complete (all 8 threads, `5fc9648`), Grafana dashboard validated under batched load for W1 (fuller panel hardening continues under #34).

Live state:

- Kimi-K2.6 runs on the 8×H200 NVL server through Docker Compose as service `vllm`, exposed on port 8000, using TP=8 + Eagle3 speculative decoding. Compose defaults updated 2026-06-05 (`6c9db1c`): Kimi `--gpu-memory-utilization 0.6` (was 0.65), added `--max-num-batched-tokens 4096`, speculative-config now carries `"max_model_len":8192`.
- DeepSeek-V4-Flash runs alongside Kimi as service `vllm-small`, exposed on port 8004; current compose default is `DEEPSEEK_GPU_MEM_UTIL:-0.2` after the 2026-06-05 T3 sweep (was 0.25); speculative-config gained `"max_model_len":8192`.
- OpenWebUI is running in compose, but the 2026-05-27 start snapshot showed it as unhealthy.
- LiteLLM Proxy runs on port 4000 and routes by `model` to Kimi and DeepSeek. Smoke tests through proxy passed for both upstreams.
- `run_bench_suite.py` has been run through LiteLLM Proxy for both Kimi K2.6 and DeepSeek-V4-Flash; results are committed.
- Prometheus + Grafana configuration exists under `serving/compose/`, including a provisioned Phase 1 dashboard (`grafana/provisioning/dashboards/vllm-phase1.json`). Containers have been started; the dashboard panels still need validation against real metric names with live load.
- Kimi K2.6 TTFT/TPOT parsing fixed (issue #31): `measure_ttft_once.py` now records a separate `ttft_any_token_seconds` / `tpot_any_token_seconds` covering reasoning-trace text (`delta.reasoning` / `delta.reasoning_content`) while `ttft_seconds` stays final-answer-only. Verified against the committed stream-debug artifacts.

Phase 1 deliverables still owed:

- **Prometheus + Grafana dashboard** showing useful live vLLM metrics during load — a provisioned dashboard JSON now exists; remaining work is validating its panels against real metric names with live load.
- **W1 write-up** — DONE (2026-06-05): all 8 threads written from committed evidence with `## Evidence` provenance; index baseline table + KV-budget synthesis filled (`5fc9648`).

---

## Current known status

- GitHub repo exists: `https://github.com/Czyszka/nanoserve-mini.git`.
- Local Windows laptop bootstrap is done; Python workflow uses `uv`; `ruff` + `pytest` configured; `.gitattributes` normalises line endings.
- Local research PDFs and Claude/Codex worktrees stay outside Git (`docs/**/papers/`, `.claude/worktrees/`, `.uv-cache-codex/`).
- **Server**: ubuntusrv2 (Ubuntu 24.04, 8×H200 NVL 143 GB, CUDA 13.2, driver 595.58.03).
- **Hardware reference**: Supermicro SYS-521GE-TNRT datasheet is mirrored as
  lightweight Markdown at `docs/operations/sys-521ge-tnrt.md`; source PDF kept
  at `docs/operations/sys-521ge-tnrt.pdf`.
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

- **#34 — observability/dashboard:** dashboard JSON provisioned; **metric-name
  inventory now DONE** — all 18 panels validated against the live 2026-06-05
  `/metrics` dump (`t5_metrics/`), every query maps to a real vLLM v0.20.0 name
  (label `model_name`), no JSON fix needed; `spec_decode_*` confirmed present
  only under Kimi Eagle3-ON. Remaining: drive concurrent load (`vllm bench
  serve`) so queue/latency/KV panels fill, then screenshot. Runbook:
  `docs/plans/2026-06-05-t5-dashboard-load.md` — flags verified against the
  committed `vllm_bench_serve_help.txt`; workload is the offline SWE-bench Lite
  300 set (`benchmarking/swe_bench_vllm.jsonl`) via `--dataset-name custom`
  (no internet needed — prompts baked in), `random` as fallback. Repeatable
  procedure now lives in `serving/runbooks/load-test-and-grafana.md` (verified
  2026-06-05: needs `HF_HUB_OFFLINE=1`, `pip install pandas datasets`,
  `--trust-remote-code`; bench ran, panels fill under load). Harness is
  sequential-only, so
  single-stream benches won't light up the queue panels — hence the bench-serve
  ramp.
- **#37 — W1 write-up:** 2026-05-27 evidence analyzed and written up on the
  laptop. T4 LiteLLM Proxy and T7 host-directories justifications drafted; T8
  thread file migrated to a post-evidence document; T1/T5 still pending.
  **2026-06-05 server slot delivered the missing T3 clean sweep + started T6
  Eagle3-ON capture + uncovered a new T8/T4 limit:**
  - **T3 (clean):** cap 0.15 hard-fails on engine init (genuine OOM-style
    traceback, `log_cap015_FAILED.txt`); cap 0.20 and 0.25 both come up
    healthy with matching `verify_cap*.txt` and `ttft_cap*.json`. Filenames
    finally match runtime caps. Compose default lowered to 0.20.
  - **T6 (ON + OFF complete, paired):** `engine_cmd_eagle3_{on,off}.json`
    show the A/B differs by **two** flags — OFF drops `--speculative-config`
    (intended) *and* `--max-num-batched-tokens 4096` (impurity; immaterial for
    this 15-tok prompt at `max-num-seqs 1`, would matter under concurrency).
    Single-shot latency: ON TTFT(content) 652 ms / TPOT(any) 6.92 ms/tok /
    E2E 674 ms / 24 chunks; OFF TTFT(content) 2489 ms / TPOT(any) 16.55
    ms/tok / E2E 2536 ms / 143 chunks. TTFT(any) ≈ 204 ms in both — Eagle3
    does not help the first token (expected). Repeated (5 measured runs):
    ON TTFT p50/p95 = 837/1694 ms, OFF 1675/4426 ms. Net: Eagle3 gives
    ~3.8× E2E and ~2.4× TPOT(any) on single-stream with this prompt.
  - **T1 DEP:** captured — `dep_state.txt` = `exited 1` (clean startup
    crash, not a hang); `dep_engine_cmd.json` + `dep_full.log` +
    `dep_startup.log` saved. Confirms "single-node DEP does not work"
    deterministically.
  - **T5 (side capture):** 12×10s `vllm:num_requests_*` / `kv_cache_usage`
    / generation rate snapshots collected in both ON and OFF benches under
    `t5_metrics/eagle3-{on,off}/`. Free side data, dashboard validation
    still owed (but no longer blocking W1).
  - **C4 restore:** Kimi back in Eagle3-ON config; `restore_engine_cmd.json`
    shows `speculative-config` present; `restore_smoke.json` completed=True
    (TTFT_any 1.26 s, 19 chunks, 183 reasoning_chars).
  - **T4/T8 LiteLLM limit:** paired Kimi K2.6 benches run-01 (proxy :4000)
    vs run-03 (direct :8000), same prompt + max_tokens=64, prove LiteLLM
    `main-v1.66.0-stable` strips `delta.reasoning`: 3 vs 26 chunks,
    `reasoning_chars` 0 vs 242, `ttft_any_token_seconds` null vs 0.214 s.
    Parser fix #31 verified working direct; proxy unusable as the single
    driver for Kimi reasoning streams in this LiteLLM version.
  - **DONE (2026-06-05):** all W1 thread write-ups written from these numbers
    with `## Evidence` provenance (commits `bfe82bf`/`eaa3694`/`77df2f5`/
    `023f691`/`c2be652`/`5fc9648`). T5 closed done-for-W1; fuller panels under
    #34.
  - **2026-06-05 (laptop) organized & audited** — see
    `results/runs/2026-06-05_w1_evidence/session/session_notes.md` +
    `results/summaries/w1-evidence-cross-session.md`. Auto-id run dirs
    renamed to semantic aliases (`run-04_eagle3-on`,
    `run-05_eagle3-off-paired`/`-rerun`, `run-0{1,3}_t8-{proxy,direct}`,
    deepseek `run-0{1,2}_baseline`). **Integrity:** final server commit
    `fc97700` re-ran and overwrote OFF/deepseek results in place; the T6
    OFF **paired 5×5** generation (09:17, single-shot 2489 ms) was recovered
    from `ec3df59` and is the A/B partner for ON — use it, not the unpaired
    `-rerun` (10:02, 10 runs, 1365 ms). Lead T6 with **repeated ~2× p50
    TTFT** (robust); single-shot E2E 2.1×–3.8× is temp=0-variance-sensitive.
    SWE-bench dataset kept intentionally as #34 load workload.
  - **2026-06-06 (laptop) deep-review pass T1–T4** — thread-by-thread
    review hardened the four published threads against vLLM source +
    primary external sources (each commit docs-only, one thread): T1
    `9473660` (−19.08 GiB KV-budget arithmetic + 88.44 GiB DEP weight
    decomposition, EP 48/384 cite, util≈0.74 to match TP@0.6), T2
    `887ebe7` (client-vs-server TTFT mechanism on Kimi/DeepSeek data,
    generic tutorial cut), T3 `6f3474d` (KV size-vs-concurrency lines
    grounded in `kv_cache_utils.py`, open bug #40691, MiB/GiB units,
    0.20-vs-0.25 serving rationale), T4 `0f635d9` (6-row verified
    external-evidence table w/ real URLs). **T5–T8 hardened in the
    2026-06-07 pass (handoff log).** Untracked `docs/writeups/w1/T4-deep-research-report.md`
    (source material, opaque `citeturn` tokens) left out of git pending
    keep-as-appendix vs delete.
- **W1 article deepening (2026-06-09):** critique of `w1-article.md` accepted —
  article is post-hoc only (no predict→measure analysis, no figures, thin stats,
  secondary-only citations). Approved plan:
  `docs/plans/2026-06-09-w1-article-deepening.md` (quantitative boxes, mermaid
  figures, TL;DR, methods + synthesis sections, primary refs; outline approved).
  New evidence narrowed by user decision to **P0 GPU counters + P2 hop
  attribution**; P1 (Eagle3 n=20 clean A/B) and P3 (concurrency sweep)
  **rejected**. Server slot planned: `docs/plans/2026-06-10-server-session.md`
  (zero engine restarts — compose already runs `max-num-seqs 32`).
  **2026-06-10: session executed** (tier-1 `dcgmi`; evidence commits `e8ce1d7`
  P0 + `8b8d457` P2; all P2 deltas `d_count=1`, no repeats needed). **Article
  updated with the results:** HBM-bandwidth-bound **refuted** (`DRAM_ACTIVE`
  0.093 c=1 / 0.070 c=64 — Inv 5 rewritten, comms/serialization-bound is the
  surviving L1), reasoning-strip promoted to **L2** + hop cost ~37 ms median
  c=1 (Inv 3), client-vs-server TTFT isolation closed (server p50 93 ms vs
  client 177 ms any / 1.82 s content — Inv 2), closing gaps list updated.
  Threads T2/T5/T8 do **not** yet carry the new evidence rows.
- **Bottleneck follow-up (2026-06-10):** user's extra Qwen3.6-35B-A3B TP1/TP2
  runs (`results/runs/2026-06-10_extra/`, commits `6a3cdbf`/`2d20b6a`) analyzed
  laptop-side: TP1 c=64 hits 443 W / SMACT 0.68 / DRAMA 0.39 on one GPU (zero
  comms), TP2 c=64 halves per-GPU activity (265 W / 0.40 / 0.18) with
  5.8/6.7 GB/s on PCIe — strong comms-tax signature; TP1 c=1 still only SMACT
  0.47 at ~9 ms/step → per-step overhead floor independent of PCIe.
  **Errata 2026-06-10_extra:** `log_cap_qwen_tp2.txt` is the TP1 container's
  log (wrong container; TP2 config proven only by `engine_cmd.json`); TP2
  bench JSONs missing (recoverable from Prometheus TSDB, window epoch
  1781096733+253 s, `model_name="Qwen3.6"`); TP2 `batched_c64_end_epoch`
  missing; 133 all-idle samples appended to TP1's `batched_c64_dcgmi.txt`.
  Next session planned (user picked A+B+C, D rejected):
  `docs/plans/2026-06-10-bottleneck-followup-session.md` — Qwen TP2/TP4 curve
  + TSDB recovery, Kimi TP8 torch-profiler trace (NCCL share of decode step),
  Qwen TP2 `NCCL_P2P_DISABLE=1` dose-response.
  **Goal formalized as issue #50** (bottleneck at L2 + NVLink 4-way purchase
  decision: parametric model `T = F_host + N_rounds × r(link,ranks) +
  W_silicon`, first-pass per-TP gain estimates — TP=1 none, TP=2/4 in-island
  largest, Kimi capped at hierarchical TP=8 ~1.2–1.5× since TP=4 does not fit;
  session outputs calibrate it). **New hardware fact:** server is dual-socket
  (2× CPU, user-reported); PCIe likely split across sockets → cross-socket
  GPU pairs traverse UPI. Recorded in `infrastructure.md` (hypothesis, to
  verify via `nvidia-smi topo -m` in the session plan).
  **2026-06-10 (PM2): topology largely resolved from the datasheet**
  (`docs/operations/sys-521ge-tnrt.md`: SYS-521GE-TNRT, "Dual-Root PCIe",
  PCIe 5.0 x16 Switch per root, **NVLink Bridge officially optional** for the
  chassis) + env snapshot (2× Xeon Gold 6530, NUMA=4/SNC-2; GPU bus-IDs pair
  as 1D/1E, 40/41, AA/AB, BB/BC → 4 switch pairs, GPU0–3 CPU0 / GPU4–7 CPU1
  presumed) — posted as a #50 comment; `infrastructure.md` updated (incl.
  DCGM host tier-1 as a durable fact). **Session plan v2:** full Qwen re-run
  TP=2 + new TP=8 (rank anchor for Kimi) + TP=4, step-by-step (KROK 1–7),
  stretch A4 = TP=2 on GPU{0,4} via `CUDA_VISIBLE_DEVICES` (direct UPI-tax
  measurement); Kimi stays TP=8-only and is profiled anyway (Cz. B); cut
  order A4 → C → A3. **Prep:** added
  `serving/compose/docker-compose.qwen3.6.yml`, a dedicated Qwen compose that
  keeps service/container/hostname `vllm` and port `8000:8000` so existing
  Prometheus target `vllm:8000` continues to work while Kimi/DeepSeek are down.
  **2026-06-10 (PM4):** session-plan commands hardened before the next server
  slot: Qwen sections now use the dedicated compose instead of an ad-hoc command
  override, health waits fail on timeout, Qwen sampler windows are joined before
  config changes, `NCCL_P2P_DISABLE` is a compose overlay, Kimi profiler startup
  stops Qwen first, and restore force-recreates plain Kimi/DeepSeek/LiteLLM/
  OpenWebUI and checks profiler env removal.
  **2026-06-11: server run aborted on TP MISMATCH (A1/A2/A3)** — root cause:
  the server executed an ad-hoc Qwen compose (`514b412`) with hard-coded
  `--tensor-parallel-size 2` and no `${QWEN_TP}` interpolation, so the exported
  `QWEN_TP` was silently ignored; partial artifacts in
  `results/runs/2026-06-11_bottleneck/` (commit `8ab559b`). Fixed by merging
  the parametrized compose into main (`309e803`); before re-running, pull on
  the server and confirm TP via `docker inspect vllm` Cmd (beware `sudo`
  stripping env). Plan hardened (`3fdf08a`): `engine_env_*` capture now redacts
  secrets (raw dump leaked `HUGGING_FACE_HUB_TOKEN`; audit confirmed no token
  was ever committed) and the TP-mismatch error prints the actual value from
  the log.
  **2026-06-11 (PM): commit A landed and analyzed** (`363b965` data,
  `f7c3573` analysis → `results/summaries/2026-06-11-qwen-tp-curve.md`).
  Verdict: **TP2 is the serving optimum** (c64 1404 tok/s, +17% vs TP1);
  **TP≥4 decode is comms-bound, proven causally** — TP4/TP8 scaling
  efficiency 14%/2.7%, per-GPU power collapses to near-idle (TP8 c64: 111 W,
  SMACT 0.053) with sustained PCIe RX 5.7–7.2 GB/s; **A4: no measurable UPI
  tax at 2 ranks** (cross-socket TP2 ≈ same-switch TP2 at c=1) → the TP4→TP8
  cliff is rank-count-driven, not link-class alone; per-step floor `F_host`
  ~5–9 ms confirmed at TP1 c=1 (SMACT 0.46). #50 inputs recorded in the
  summary; per-round `r` deferred to the Kimi trace (Cz. B fixes `N_rounds`).
  **Cz. C (nop2p, `fab5e0b`): dose-response NEGATIVE** — `NCCL_P2P_DISABLE=1`
  at TP2 changes nothing measurable (c64 1396 vs 1404 tok/s; criteria row 4:
  comms cheap at 2 ranks, limiter = per-step floor; NVLink gain at TP2 ≈ 0
  causally). Bonus: 3 independent TP2 starts calibrate noise (c1 step
  ±0.4 ms) → TP4/TP8 deltas are 4×/13× the noise band. Remaining: Cz. B
  (Kimi profiler), Cz. D (restore).
  **Cz. B + D (`e5f02a5`, analysis `32763d7` →
  `results/summaries/2026-06-11-kimi-tp8-profile.md`): SESSION COMPLETE.**
  Kimi TP8 c=1 trace (rank 0): **gaps 63% of span, NCCL 22.5%, compute 9%**
  → floor-bound, not comms-bound (criteria row 3); control: profiled vs
  unprofiled request differ ~5%, so gaps are real. Amdahl bound for NVLink
  on interactive Kimi ≤1.3× → **NO-GO signal for the interactive-latency
  motivation**; batched-Kimi case unmeasured (stretch c=8 cut). vLLM v0.20
  gotcha recorded in the plan: `VLLM_TORCH_PROFILER_DIR` removed upstream,
  profiler needs `--profiler-config` engine flag. Raw traces:
  `/home/working/nanoserve-tracing` (ubuntusrv2, outside repo). Restore
  verified clean. Next: recompute #50 estimate table from measured values
  and write the recommendation; W2 synthesis material ready.
  **2026-06-11/12: NVLink boundary session COMPLETE — verdict delivered**
  (plan `docs/plans/2026-06-11-nvlink-boundary-session.md`, data commits
  `e13c30d`…`3c11f70`, analysis →
  `results/summaries/2026-06-11-nvlink-boundary-verdict.md`). K1: Kimi TP8
  PCIe RX pinned at 7.2–7.9 GB/s for every c≥8 (model-independent transport
  ceiling); c=16 anomaly REAL (repeat ±3%, ITL 512→525 ms; Eagle3 acceptance
  stable — scheduler-suspect, software). K2 (trace @c16): **NCCL 83.9% of
  span / compute 4.6%** — batched Kimi flips from floor-bound to comms-bound.
  Q1: Qwen TP8 peaks at c≈16 (437 tok/s = 1/3 of TP2) and collapses at the
  RX ceiling. Q3: cross-island TP4 (0,1,4,5) shows **zero UPI tax** (cross
  ~5% better at c64) → capture 1.0 for TP4-in-one-island, ≈0.75 for TP8.
  Q4 (trace TP4 intra @c64): **NCCL 53.3%** — converges with the 52%
  TP2→TP4 per-GPU efficiency loss (two methods, one number). F doses (TP1
  c=1, step 8.93 ms): MTP orchestration 3.57 ms = 40% of the floor (spec
  still wins TPOT 3.39 vs 5.36); eager dose shows cudagraphs mask ~46 ms/step
  launch overhead (SMACT 0.009) — the floor is host/launch by nature; F6
  (governor `schedutil`) untested. **#50 verdict table:** NVLink GO only for
  batched serving of models requiring TP≥4 (TP4 ~2.1×, Kimi TP8 ~2.7×, ceiling
  6.2×); NO-GO for interactive latency (≤1.3×), TP≤2 (≈0 causally), and
  anything that fits on fewer GPUs. Caveats in the summary (c32 share
  extrapolated, NCCL includes peer-wait, c16 penalty may be software-fixable).
  Next: T9 restructure per its 13-point target outline + #50 comment with the
  verdict table; optional F6 + Kimi c=32 profile if another slot opens.
  **2026-06-10 (PM3): investigation promoted to W1 thread T9**
  (`docs/writeups/w1/t9-bottleneck-nvlink.md`, status *in progress*) — the
  engineering record of the bottleneck attribution + NVLink decision model;
  scope boundary stated inside (T9 = record/decision, W2 = TP-scaling
  synthesis). Wired into the W1 index (thread map, files, evidence-quality
  table, follow-up item 5) and the article's gaps list. `infrastructure.md`
  gained the full connection diagram (CPU0/1 ↔ UPI, 4 PCIe switches, GPU
  pairs, link-class examples mapped to expected `topo -m` labels).
- **#48 — speculative decoding methodology:** new research issue tracking a
  JarvisLabs methodology article; laptop follow-up before final T6 write-up.
- **#49 — pin observability images:** Grafana / Prometheus / image-renderer run
  on floating tags (`latest`/`v3`) unlike the pinned serving compose; pin to
  exact versions + digests (config-only, next server touch). Flagged by T7.

---

## Immediate next steps


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
| Small-model experiment | `deepseek-ai/DeepSeek-V4-Flash` served as `DeepSeek-V4-Flash`, default cap lowered to 0.20 after 2026-06-05 clean sweep (0.15 hard-fails, 0.20/0.25 OK) |
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

- [ ] **GPU hardware metrics (DCGM) — HIGH VALUE, elevated 2026-06-05.** vLLM
  `/metrics` has zero GPU-load signal (power, SM/Tensor/DRAM activity, VRAM).
  The 2026-06-05 load test surfaced exactly why this matters: nvidia-smi showed
  100% GPU-Util but only ~180-240 W / 600 W (memory-bound decode) — invisible on
  the current dashboard. Plan: add a `dcgm-exporter` container, a Prometheus
  scrape job for it, and a "GPU hardware" dashboard row
  (`DCGM_FI_DEV_POWER_USAGE`, `DCGM_FI_PROF_SM_ACTIVE`,
  `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE`, `DCGM_FI_PROF_DRAM_ACTIVE`,
  `DCGM_FI_DEV_FB_USED`). Config is laptop-writable prep (no GPU needed to
  author); exporter run needs a server slot. Still under #34 — was "deferred,
  don't block W1"; now the most valuable observability extension. **2026-06-07:**
  added a #34 comment scoping a follow-on study — correlate GPU-util ↔ HBM
  bandwidth and disambiguate HBM-bound vs TP-comms-bound; needs DCGM
  `DRAM_ACTIVE` / `TENSOR_ACTIVE` / `NVLINK_*` / `PCIE_*` counters; maps to W2.
  **2026-06-08 — topology now hard fact, not assumed:** server is **PCIe-only, no
  NVLink, no NVSwitch** (user-confirmed + vLLM log `kimi_log_eagle3_on.txt:67,138`:
  custom all-reduce *"not supported on more than two PCIe-only GPUs"*, FlashInfer
  *"expected on GPUs without NVSwitch… PCIe topologies"*). So all TP=8 all-reduce
  is on PCIe today; the earlier "4-way NVLink = 2 islands of 4" is a *hypothetical
  upgrade*, not the current node. Posted a #34 correction comment; T5 hardware
  layer updated.
- [x] **Why is TP4 (intra-socket, NODE links) already catastrophic at c=64**
  (eff. 14%) when TP2 still wins? **RESOLVED 2026-06-11/12:** rank-count dose
  + shared transport ceiling, not link class. Q4 trace: NCCL 53.3% of span at
  TP4 c64 (matches the 52% efficiency loss); Q3: zero UPI/island tax; K1/Q1:
  PCIe RX saturates at ~7.2–7.9 GB/s regardless of model. See
  `results/summaries/2026-06-11-nvlink-boundary-verdict.md`.
- [ ] Which exact vLLM metric names should drive the first Grafana dashboard? Need inventory from live `/metrics` and/or Prometheus.
- [ ] Should `sample_gpu_metrics` be integrated into `run_bench_suite.py`, or stay as a separate explicit tool?
- [ ] Which Kimi-K2.6 memory parameters are stable enough for long runs while DeepSeek stays up beside it?
- [ ] When to implement `benchmarks/scripts/aggregate_runs.py` (Wave C)?
- [x] **Eagle3 draft-model VRAM — RESOLVED 2026-06-08 (T6).** Dedicated Eagle3-ON
  startup capture (`2026-06-08_w1_evidence_extra/t6_eagle/kimi_log_eagle3_on.txt:131`)
  gives ON loading **71.92 GiB/GPU** vs OFF **71.16 GiB/GPU** → draft adds
  **≈0.76 GiB/GPU** (~1% of target). Cheap by construction: draft checkpoint only
  5.62 GiB on disk (`:122`), TP-sharded, and embedding shared with the target
  (`:107`). KV delta (9.44 vs 9.84) not clean — ON ran production `max_num_seqs=32`.
  T6 "What it costs" updated.

---

## Last validation

2026-06-12 (T9 detail + clarity passes):

```text
git diff --check    OK (docs/md only; no .py touched)
T9 TP-curve step values cross-checked against raw bench JSONs (TP2/A4 swap corrected)    OK
```

2026-06-11/12 (NVLink boundary session analysis + verdict):

```text
git diff --check    OK (docs/md only; no .py touched)
K2/Q4 profiler overhead controls: ITL within ~2-8% of unprofiled    OK
c16 anomaly repeat: 512 vs 525 ms (±3%) — reproducible    OK
Q3 placement check: CUDA_VISIBLE_DEVICES=0,1,4,5 in engine env    OK
cross-method convergence: Q4 NCCL share 53.3% vs 52% efficiency loss    OK
```

2026-06-11 (close-out) Kimi TP8 profile analysis + session wrap:

```text
git diff --check    OK (docs/md only; no .py touched)
profiler control: profiled vs unprofiled request ~5% apart (gaps real)    OK
restore check: no profiler-config in Cmd, smoke completed=True    OK
```

2026-06-11 (PM) Qwen TP-curve analysis (laptop-side, docs/results only):

```text
git diff --check    OK (md only; no .py touched)
runtime verifies: verify_tp{2,4,8,2x04}.txt all match requested TP    OK
placement check: non-participant GPUs at idle power in every window    OK
bench completion: 40/40 (c1) and 600/600 (c64) in every run    OK
```

2026-06-11 TP-mismatch diagnosis + plan secret redaction:

```text
git diff --check    OK (docs-only; no .py touched)
secret audit: no engine_env_* file ever committed; no HF token in results/ or docs/    OK
```

2026-06-10 bottleneck follow-up plan + Qwen compose prep:

```text
git diff --check    OK (docs/config only; no .py touched)
docker compose -f serving/compose/docker-compose.qwen3.6.yml config    OK
docker compose -f serving/compose/docker-compose.qwen3.6.yml -f qwen-nop2p.yml config    OK
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml -f kimi-profiler.yml config    OK
QWEN_TP=2 QWEN_CUDA_VISIBLE_DEVICES=0,4 compose interpolation    OK
```

Note: Kimi compose validation needs dummy `HF_TOKEN` and `LITELLM_MASTER_KEY`
locally because the file intentionally requires them; no GPU commands were run
on the laptop.

2026-06-10 W1 article — 2026-06-10 evidence integrated (P0 + P2):

```text
git diff --check    OK (docs-only; no .py touched)
```

`docs/writeups/w1-article.md` updated from
`results/runs/2026-06-10_w1_article_evidence/` (commits `e8ce1d7`/`8b8d457`):
Inv 5 counters table + HBM-bound refutation, Inv 3 R1 attribution table + ~37 ms
hop cost, Inv 2 client-vs-server isolation closed, Inv 4 rationale rephrased,
closing gaps list + postscript. The commit also carries the previously
uncommitted "five numbers" article rewrite (working tree since 2026-06-09).
No `ruff` / `pytest` (docs-only).

2026-06-09 W1 article deepening plan + 2026-06-10 server session plan:

```text
git diff --check    OK (docs-only; no .py touched)
```

New `docs/plans/2026-06-09-w1-article-deepening.md` (approved critique +
outline + laptop/Etap roadmap) and `docs/plans/2026-06-10-server-session.md`
(P0 GPU counters idle/c1/c64 with tiered dcgmi→exporter→dmon tooling + P2 hop
attribution via `metrics_delta.py`; zero engine restarts). No `ruff` / `pytest`
(docs-only).

2026-06-09 W1 portfolio article written:

```text
git diff --check    OK (docs-only; no .py touched)
```

New file `docs/writeups/w1-article.md` — ~2700-word standalone portfolio article
synthesizing all 8 W1 threads into one readable piece for GitHub. Also added
`results/runs/2026-06-05_w1_evidence/eagle3_horizontal_flow.png` (298 KB).

2026-06-08 T6 Eagle3 VRAM closed + PCIe topology confirmed:

```text
git diff --check    OK (docs-only; no .py touched)
```

New evidence `2026-06-08_w1_evidence_extra/t6_eagle/kimi_log_eagle3_on.txt`
(committed `131d573`) supplied the Eagle3-ON loading phase. Updated T6 (draft VRAM
**0.76 GiB/GPU** measured; embedding-sharing mechanism; KV caveat) and T5 (PCIe-only
interconnect — no NVLink/NVSwitch — as hard evidence). Resolved the Eagle3-VRAM
open question; corrected the #34 topology note + posted a #34 correction comment.
No `ruff` / `pytest` (docs-only).

2026-06-07 W1 deep-review pass (T5–T8) + ops:

```text
git diff --check    OK (docs-only; no .py touched)
```

Docs-only: hardened T5–T8 against committed evidence (commits `8e299ae` T5,
`ac13782` T6, `0db3593` T7, `afd478b` T8); created issue #49 (pin observability
images) and added a #34 research comment (GPU-util↔HBM / NVLink study). No `ruff`
/ `pytest` run.

2026-06-06 W1 deep-review pass (T1–T4):

```text
git diff --check    OK (docs-only; no .py touched)
```

Docs-only: hardened the four published W1 threads against vLLM source + primary
external sources (commits `9473660` T1, `887ebe7` T2, `6f3474d` T3, `0f635d9`
T4). No `ruff` / `pytest` run.

> Pre-2026-06-06 validation entries compacted 2026-06-10. Source: `520d7883127452cc5ef50dca52fecfdb2e62fabf`.
> Full history: `git show 520d7883127452cc5ef50dca52fecfdb2e62fabf:docs/operations/agent-state.md`.
> Summary (2026-05-19 → 2026-06-05): docs/config-only changes validated with
> `git diff --check`; `.py` changes (#31 parser fix, bench-suite launcher)
> with `uv run ruff check .` + `uv run pytest` (113→121 passed); server
> slots validated live (direct endpoints, LiteLLM proxy, bench suite for both
> models, observability bootstrap, 2026-06-05 evidence commits).

---

## Handoff log

Newest entry first.

### 2026-06-12 (cloud) - T9 detail + clarity passes; #50 verdict comment posted

- Why: the user wanted T9 substantially more detailed and the Qwen TP-curve section fully explained; the #50 verdict still had to land on the issue itself.
- Did: T9 detail pass (pre-registered predictions vs measured, method controls, causal step arithmetic, UPI-hypothesis record, ops-lessons appendix) + TP-curve section rewritten for clarity with step values corrected against raw bench JSONs; verdict table posted as a #50 comment; conversational synthesis recorded DP-replicas-over-TP as the Qwen-class recommendation and the NVLink-justified case list (TP4-required batched ~2.1×, Kimi TP8 batched ~2.7×, TP2-required NO with a heavy-dense caveat).
- Range: `5cab895..3fd150b` (3 commits)
- Validation: OK (docs-only)
- Next: user decides on closing #50; W2 synthesizes from T9; optional slot: Kimi c=32 profile, c=16 root cause, 2×TP1-replica co-run to upgrade the DP claim to L2.

### 2026-06-12 (cloud) - session closed (D'), F3/F6 analyzed, T9 restructured to final form

- Why: the user delivered the last artifacts (F3 trace, F6 governor dose, D' restore + manifest `5cab895`) — the research set for the technical note was complete.
- Did: F6 exonerates the governor (`performance` 9.86 vs 8.93 ms base — no gain); F3 trace flagged as cold-start-contaminated (no warmups → torch.compile chains dominate cpu_op; qualitative use only); verdict summary updated with both + D' close-out; **T9 rewritten into the 13-point technical-note structure** (problem → observation+analogy → glossary → hardware → mechanisms → methodology → results → causal analysis → conclusions → decision table → per-scenario justification → verdict → evidence), status COMPLETE.
- Range: `3c11f70..5cab895` (user close-out commit) + cloud docs commits
- Validation: OK (docs-only, `git diff --check`)
- Next: post the verdict table as a #50 comment and close #50; W2 synthesizes from T9; optional future slot: Kimi c=32 profile + scheduler-pathology investigation (the two open caveats).

### 2026-06-11/12 (cloud) - NVLink boundary session: full verdict table for #50

- Why: #50 needed the boundary conditions — when NVLink 4-way pays and when it does not, in the latency/throughput frame.
- Did: analyzed K1/K2/Q1/Q3/Q4/F as they landed (live debugging of the plan along the way: K2 moved to c=16 after the anomaly reproduced, Q1 prereqs made standalone, self-contained Q4 section added); wrote `results/summaries/2026-06-11-nvlink-boundary-verdict.md` with the verdict matrix (GO only for batched TP≥4 serving: TP4 ~2.1×, Kimi TP8 ~2.7×; NO-GO interactive/TP≤2/fits-on-fewer) and the floor ledger (MTP 40% of the TP1 step, cudagraphs already masking ~46 ms launch overhead); T9 gained the target 13-point outline, editorial rules, the executed-plans index, and the delivery-run analogy mapping.
- Range: `32763d7..3c11f70` (mixed: user bench commits + cloud docs commits)
- Validation: OK (docs-only; overhead controls and cross-method convergence in the summary)
- Next: restructure T9 to its target outline with the new numbers; post the verdict table as a #50 comment; optional next slot: F6 governor dose + Kimi c=32 profile to close the two caveats.

### 2026-06-11 (cloud, close-out) - Kimi TP8 profile: floor-bound, NVLink interactive NO-GO signal

- Why: Cz. B trace was the last missing measurement for the #50 NVLink decision.
- Did: rank-0 trace shows gaps 63% / NCCL 22.5% / compute 9% of span with a ~5% profiler-overhead control → Kimi TP8 c=1 is floor-bound, Amdahl bound for NVLink ≤1.3× interactive; summary in results/summaries/2026-06-11-kimi-tp8-profile.md; session restored and complete.
- Range: `342ddf6..32763d7` (5 commits)
- Validation: OK
- Next: recompute the #50 estimate table from measured values and draft the purchase recommendation (laptop-side).

### 2026-06-11 (cloud, PM) - Qwen TP-curve analyzed (commit A of the bottleneck session)

- Why: checkpoint 1 + Cz. C delivered TP2/TP4/TP8 + A4 + nop2p data; #50 needs the measured curve before the NVLink verdict.
- Did: TP2 is the optimum (c64 +17% vs TP1), TP4/TP8 collapse to 14%/2.7% scaling efficiency with GPUs at near-idle power (comms-bound proven causally), A4 shows no UPI tax at 2 ranks, and the nop2p dose-response is negative (comms cheap at TP2; limiter = per-step floor); analysis in results/summaries/2026-06-11-qwen-tp-curve.md.
- Range: `917ee17..342ddf6` (4 commits + merge)
- Validation: OK
- Next: server continues Cz. B (Kimi profiler trace) and D (restore); then recompute the #50 NVLink table.

### 2026-06-11 (cloud) - TP MISMATCH root cause + plan secret redaction

- Why: the 2026-06-11 server run aborted at the TP verify for A1/A2/A3, and the HF token was landing in committed-bound engine_env artifacts.
- Did: traced the mismatch to the server's ad-hoc compose hard-coding TP=2 (QWEN_TP ignored), merged the parametrized compose into main, redacted secrets in the env capture, and made the mismatch error print the actual TP.
- Range: `e08f762..3fdf08a` (3 commits)
- Validation: OK
- Next: pull main on the server, confirm TP via docker inspect, re-run A1/A2/A3.

### 2026-06-10 (laptop, PM5) - plan review pass (Claude) on top of hardening

- Why: pre-session review caught footguns that would cost slot time.
- Did: in `docs/plans/2026-06-10-bottleneck-followup-session.md` — removed
  `set -euo pipefail` (errexit kills the interactive SSH shell on first error;
  fail-fast now explicit `|| return 1` in functions), TP verify greps the FULL
  `docker logs` (tail-500 cuts the config line at TP=8 / NCCL_DEBUG=INFO),
  KROK 6 artifact collection now runs even when a bench fails (06-10 lesson),
  added `engine_env_<tag>.txt` dump + A4 placement check, Cz. 0 removes the
  stopped Kimi `vllm` container (container_name collision), Qwen health wait
  240×5 (TP=8 cudagraph capture), Kimi trace flush wait loop instead of
  `sleep 10`, `${EDITOR:-nano}`, budget table reordered to match section order.
- Validation: `git diff --check` OK; `bash -n` on all concatenated ```bash
  blocks of the plan OK.
- Next: execute on the server; cut order unchanged A4 -> C -> A3.

### 2026-06-10 (laptop, PM) - bottleneck follow-up plan command hardening

- Why: next server slot should execute Qwen TP-curve, NCCL dose-response, and
  Kimi profiler without losing time to compose/health/sampler mistakes.
- Did: updated `docs/plans/2026-06-10-bottleneck-followup-session.md` to use
  `serving/compose/docker-compose.qwen3.6.yml`, fail-fast health helper, robust
  Qwen sampler joins and JSON-count checks, `QWEN_EXTRA_COMPOSE` for no-P2P,
  `QWEN_CUDA_VISIBLE_DEVICES=0,4` for A4, Kimi profiler pre-cleanup, trace-file
  existence check, and force-recreate restore with profiler-env guard.
- Validation: `git diff --check` OK; Docker Compose config OK for Qwen, Qwen
  no-P2P overlay, Kimi profiler overlay, and Qwen TP/CUDA interpolation (dummy
  secret env only; no GPU commands run locally).
- Next: on the server, execute the plan from Cz. 0 using the root `.env`; if
  time is short, keep the documented cut order A4 -> C -> A3.

### 2026-06-10 (laptop, PM) - Qwen compose for bottleneck session

- Why: bottleneck follow-up needs a repeatable Qwen3.6-35B-A3B serving config
  without editing the canonical Kimi/DeepSeek compose; observability should keep
  scraping `vllm:8000`.
- Did: added `serving/compose/docker-compose.qwen3.6.yml` with service/container
  `vllm`, host port `8000`, pinned vLLM image, same HF cache mount and
  `nanoserve-net`, plus env-parametrized `QWEN_TP`, `QWEN_CUDA_VISIBLE_DEVICES`,
  max-length/batching, GPU memory cap, and MTP speculative-token count.
- Validation: YAML parsed with `uv run python`; whitespace check OK; `docker
  compose config` OK via
  `C:\Program Files\Docker\Docker\resources\bin\docker.exe` (Docker CLI is
  installed but not currently on this PowerShell session's `PATH`).

### 2026-06-10 (laptop, PM) - analiza Qwen TP1/TP2 + plan sesji bottleneck

- Why: P0 obaliło HBM-bound, ale "wszystko bezczynne" nie dowodzi jeszcze
  PCIe; user chce domknąć pytanie o wąskie gardło (zakładał PCIe).
- Did: agregacja liczników z `2026-06-10_extra` (per-GPU, active-filter,
  bloby z commitów — plik TP1 batched ma doklejony ogon): TP1 c=64 443 W /
  SMACT 0.68 / DRAMA 0.39 / PCIe ~0; TP2 c=64 265 W / 0.40 / 0.18 / PCIe
  5.8/6.7 GB/s per GPU; TP1 c=1 TPOT 3.68 ms, ITL ~9 ms/krok przy zerowej
  komunikacji → podatek PCIe widoczny + podłoga narzutu per-step. Errata
  integralności capture'u spisana w "In flight". Decyzja usera: eksperymenty
  A (Qwen TP-curve + TSDB recovery), B (Kimi torch profiler), C (NCCL
  dose-response); D odrzucone. Plan:
  `docs/plans/2026-06-10-bottleneck-followup-session.md` (fail-fast verify TP
  w logu przed benchem, traców nie commitujemy — tylko podsumowanie).
- Validation: `git diff --check` OK (docs-only).
- Next: wykonać plan w najbliższym slocie; po wynikach — werdykt do artykułu
  (Inv 5 / sekcja syntezy) wg tabeli "Kryteria rozstrzygnięcia" w planie.

### 2026-06-10 (laptop) - W1 article: integracja wyników sesji P0+P2

- Why: sesja serwerowa 2026-06-10 (plan `2026-06-10-server-session.md`)
  dostarczyła P0 (liczniki GPU, tier-1 `dcgmi`) i P2 (hop attribution, komplet
  5 par × mt∈{64,1024}, wszystkie `d_count=1`); artykuł miał wpiąć wyniki
  (Etap 3 planu deepening).
- Did: analiza artefaktów ad hoc (agregacja dcgmi per okno + parowane delty
  P2). Kluczowe liczby: **P0** — idle 99 W / wszystko 0.000; c=1 SMACT 0.21,
  TENSO 0.012, **DRAMA 0.093**, PCIe 1.9/6.0 GB/s; c=64 (288 tok/s) SMACT
  0.20, TENSO 0.064, **DRAMA 0.070**, PCIe 6.0/8.0 GB/s → hipoteza HBM-bound
  **obalona**, comms/serialization-bound zostaje jako L1 (≈0.2 ms/rundę
  all-reduce z arytmetyki TPOT). **P2** — server TTFT 93 (direct) vs 96 ms
  (proxy), te same 64 tokeny, strip 5/5 → **L2** (delivery, not compute); hop
  ~37 ms median (paired outside-vLLM, stabilny dla obu mt); LiteLLM header
  24.4 ms; przez proxy first token +1.7 s przy mt=1024 (zależny od długości
  reasoning). Artykuł zaktualizowany: Inv 2 (izolacja client-vs-server
  zamknięta), Inv 3 (tabela R1 + koszt hopa + ledger L2), Inv 4 (uzasadnienie
  spekulacji przeformułowane), Inv 5 (sekcja "counters came back", tabela,
  refutacja, ledger), zamknięcie (lista luk + postscript "sixth number").
- Validation: `git diff --check` OK (docs-only). Commit artykułu zawiera też
  wcześniejszy, niecommitowany rewrite "five numbers" z working tree.
- Next: Etap 1 deepening (TL;DR, figury, methods/synteza, statystyka, primary
  refs); opcjonalnie evidence rows 2026-06-10 do T2/T5/T8.

### 2026-06-09 (laptop) - W1 article deepening plan + jutrzejsza sesja serwerowa

- Why: user ocenił `w1-article.md` jako za płytki naukowo-inżyniersko i
  rekrutacyjnie; uzgodniono krytykę i plan pogłębienia.
- Did: krytyka zaakceptowana (artykuł czysto post-hoc — brak predict→measure,
  zero figur, statystyka deklarowana nie praktykowana, brak primary refs, brak
  TL;DR). Zapisany zatwierdzony plan
  `docs/plans/2026-06-09-w1-article-deepening.md` (boxy ilościowe: roofline /
  all-reduce, MLA KV bytes/token, model akceptacji Eagle3, Little's law; figury
  mermaid + embed istniejącego PNG; sekcje TL;DR / Methods / Synthesis;
  literatura pierwotna) oraz plan sesji
  `docs/plans/2026-06-10-server-session.md` — **P0** liczniki GPU
  (idle/c1/c64, tiery dcgmi→dcgm-exporter→nvidia-smi dmon) + **P2** hop
  attribution (R1, ABBA, mt∈{64,1024}, `metrics_delta.py`). Decyzje usera:
  P1 (Eagle3 n=20) i P3 (concurrency sweep) odrzucone; struktura artykułu
  pogłębiana in-place; outline zatwierdzony.
- Validation: `git diff --check` OK (docs-only).
- Next: jutro slot serwerowy wg planu 2026-06-10; równolegle/po nim Etap 1
  (laptop-only) i Etap 3 (integracja) z planu deepening.

### 2026-06-09 (laptop) - W1 portfolio article written

- Why: write-upy wątkowe (w1/) są engineering recordem; brakuje jednego,
  czytelnego portfolio piece do GitHub repo (#37 deliverable).
- Did: stworzył `docs/writeups/w1-article.md` (~2700 słów) — standalone artykuł
  syntetyzujący 8 wątków W1: negative-KV-budget arithmetic (T1+T3 unified),
  TTFT duality for reasoning models (T2+T8), Eagle3 cost/payoff (T6),
  observability signals vs misleading ones (T5+T7), baseline table z caveats,
  conscious deferrals (#44, #34, DeepSeek real workload). Wątki pozostają jako
  engineering appendix; artykuł do nich linkuje.
  Dodano też `results/runs/2026-06-05_w1_evidence/eagle3_horizontal_flow.png`
  (298 KB, wcześniej untracked).
- Validation: `git diff --check` OK (docs-only; no `.py` touched).
- Next: post-W1 — #34 (DCGM/GPU panels), #44 (T8 R1–R8), #48 (T6 methodology),
  DeepSeek real-generation workload.

### 2026-06-07 (laptop) - W1 deep-review pass: T5–T8 hardened + ops

- Why: continue the thread-by-thread review (teoria → dowód w projekcie,
  naukowa skrupulatność) for the remaining four W1 threads, verifying every
  figure against committed artifacts.
- Did (4 docs-only commits, one thread each):
  - `8e299ae` **T5** — dropped the stale 2026-05-27 status; footnoted gauge
    (kimi) vs all-request (TTFT/E2E/ITL) labels; softened "TTFT dominated by
    queue time" to L1 (queue_time histogram present but per-window percentile
    not captured — attribution rests on the waiting>running gauge); added the
    informal hardware reading (100% util at ~180–240 W / 600 W = memory-bound
    decode); marked the metric-helper recommendation resolved
    (`_server_metrics.py` already uses current names); added "Applied analysis"
    (playbook walked over the 06-05 capture with L-levels) and "Conclusions"
    (project-specific vLLM knobs to raise compute, throughput-bought-with-latency).
  - `ac13782` **T6** — rewrote in pedagogical style (one-pass idea + method
    table draft/n-gram/suffix/MLP/EAGLE adapted from JarvisLabs #48, model-scale
    trend); grounded acceptance economics from the server log (per-position
    0.80/0.55/0.42, mean length 2.8–3.1, ideal ~2.8× vs realized TPOT 2.4×);
    explained the two-TTFT divergence (ttft-any prefill-bound, ttft-content =
    prefill + reasoning decode); cost (41% drafts rejected, paid from idle
    compute; VRAM half-measured — OFF 71.16 GiB/GPU TP=8, ON not captured); fixed
    the A/B impurity to 4096 (ON) vs 8192 (OFF default); softened correctness.
  - `0db3593` **T7** — provenance to house style (compose file + lines, Evidence
    table); cross-linked the T5 evidence payoff; grounded the UID/GID risk
    (Grafana non-root, Prometheus nobody; did not materialize 06-05); flagged
    unpinned observability images → **issue #49**.
  - `afd478b` **T8** — corrected Kimi pilot delta to +17 ms; sharpened the
    completed:false hazard (both paths 64 tok of pure reasoning, output_chars 0 —
    only delivery differs); reframed Kimi-vs-DeepSeek asymmetry (dropped
    reasoning phase, visible only where ttft-any < ttft-content; DeepSeek absence
    of symptom ≠ immunity → R7); documented 06-05 controls (prompt "Say hi…",
    distinct from pilot "say OK"); cross-ref T4; `metrics_delta.py` confirmed.
- Also: created **#49** (pin observability images); added a **#34** research
  comment scoping the GPU-util↔HBM / NVLink ROI study (disambiguate HBM-bound vs
  TP-comms-bound; 4-way NVLink = 2 islands of 4, TP=8 crosses islands; maps to W2).
- Validation: `git diff --check` OK on each (docs-only; no `.py` touched).
- Open: Eagle3-ON draft VRAM not captured (open questions); untracked
  `T4-deep-research-report.md` keep-vs-delete still undecided. **All 8 W1 threads
  now hardened.**
- Next: optional final cross-thread W1 index pass; decide the T4 report file;
  post-W1 work (#34 DCGM + HBM study, #44 R1–R8, #48, #49) unchanged.

### 2026-06-06 (laptop) - W1 deep-review pass: T1–T4 hardened against sources

- Why: thread-by-thread review of the published W1 write-ups (teoria → dowód
  w projekcie, naukowa skrupulatność) — strengthen each against vLLM source
  and primary external sources instead of re-deriving from memory.
- Did (4 docs-only commits, one W1 thread each):
  - `9473660` **T1** — KV-budget bring-up failure deepened: full −19.08 GiB
    arithmetic from the DEP log, 88.44 GiB weight decomposition (embeddings/
    lm_head + MLA/norms/router/shared FFN replicated ~22 GiB + 384 routed
    experts EP-sharded 48/rank ~66.6 GiB, `layer.py:408` cite), load-vs-
    budget mechanism, DeepSeek co-residency reframed as context not cause,
    util≈0.74 to match TP@0.6 KV.
  - `887ebe7` **T2** — refocused on client-side vs vLLM server-side TTFT:
    4 divergence factors + Kimi/DeepSeek table (content 0.592 vs any 0.209;
    DeepSeek 0.253 = 0.253), single-stream server-side TTFT flagged not
    captured (deferred #44), generic `<think>`-marker tutorial cut, theses
    de-duped.
  - `6f3474d` **T3** — KV-cache numbers grounded in vLLM source: the
    "5,284 tokens vs 6.51×" non-reconciliation explained via
    `_report_kv_cache_config` vs `get_max_concurrency_for_kv_cache_config`
    (multi-group fp8_ds_mla + Lightning Indexer, 80.7× systematic
    deflation), flagged as still-open bug `vllm-project/vllm#40691`; MiB/GiB
    units fixed; added "what 0.20 vs 0.25 gives and takes for serving".
  - `0f635d9` **T4** — added "External evidence (verified)" 6-row table with
    real URLs (LiteLLM Postgres keys, synthetic 8 ms/1k RPS, aiohttp v1.72.0,
    `x-litellm-overhead-duration-ms`, Semantic Router "When to Reason");
    #A handled honestly (general confirmed, specific v1.66.0 issue not located).
- Validation: `git diff --check` OK on each (docs-only; no `.py` touched).
- Open: T5–T8 not yet given this deep-review pass; untracked
  `T4-deep-research-report.md` (citeturn tokens) — keep-as-appendix vs delete
  undecided.
- Next: continue review with T5 (observability) or pick T6/T7/T8.

> Pre-2026-06-06 handoff entries compacted 2026-06-10. Source: `520d7883127452cc5ef50dca52fecfdb2e62fabf`.
> Full history: `git show 520d7883127452cc5ef50dca52fecfdb2e62fabf:docs/operations/agent-state.md`.
>
> Period summary (2026-05-17 → 2026-06-05):
> - 2026-05-17 (laptop): `run_bench_suite.py` one-command launcher; LiteLLM Proxy compose + image pinning prep.
> - 2026-05-19 (server): Phase 1 close-out — canonical Kimi/DeepSeek compose reconciled (TP=8, not DP), proxy smoke + bench suite green for both models, Prometheus/Grafana bootstrap; issues #31–#33.
> - 2026-05-20 (laptop): #31 Kimi reasoning-TTFT parser fix merged (PR #36, 121 tests), #35 Grafana dashboard provisioning, `rg` installed.
> - 2026-05-26/27: server-session plan hardening + evidence triage — T8 paired proxy-overhead usable; T3 partial (filename↔runtime cap mismatch); T1 DEP / T6 Eagle3 still missing.
> - 2026-06-02 (laptop): W1 write-up pass from the 05-27 evidence — T8 post-evidence (+17 ms median final-answer hop), T3 partial baseline, T4 + T7 justifications, index tracker refreshed.
> - 2026-06-05 (server + laptop): the big W1 evidence slot — compose defaults `6c9db1c` (Kimi util 0.6 + max-num-batched-tokens 4096, DeepSeek 0.2), T3 clean sweep (0.15 hard-fail, 0.20/0.25 OK), T6 Eagle3 ON/OFF paired A/B (repeated p50 TTFT ~2×), T1 DEP clean startup crash captured, LiteLLM v1.66.0 `delta.reasoning` strip diagnosed (proxy unusable as the single Kimi reasoning driver); laptop audit recovered the paired OFF generation from `ec3df59` after the `fc97700` overwrite and renamed run dirs to semantic aliases.
