# Agent State - nanoserve-mini

Repo-tracked handoff state for Claude Code, Codex, and human work. Keep it concise
and current. Maintained by the `sync-state` / `tidy-docs` routines (see
`docs/templates/`); Git is the archive.

---

## Summary cursor

- Last summarized commit: `0d05227`
- Last summarized at: 2026-08-11 (prezentacja dostarczona; prep DCGM + runbook
  drabinki; wieczorem: porządki repo i runbooki demo — przed sesją 2026-08-12)

---

## Current phase

**Phase 1** (plan zakładał tygodnie 1-3 z 12; stan na 2026-08-11: projekt na
razie zatrzymany w fazie 1, maj→sierpień) — vLLM serving baseline +
observability + multi-model proxy.

Phase 1 minimum milestone met: proxy/benchmark done, W1 write-up complete (all 8 threads, `5fc9648`), Grafana dashboard validated under batched load for W1 (fuller panel hardening continues under #34).

Live state:

- Kimi-K2.6 runs on the 8×H200 NVL server through Docker Compose as service `vllm`, exposed on port 8000, using TP=8 + Eagle3 speculative decoding. Compose defaults updated 2026-06-05 (`6c9db1c`): Kimi `--gpu-memory-utilization 0.6` (was 0.65), added `--max-num-batched-tokens 4096`, speculative-config now carries `"max_model_len":8192`.
- DeepSeek-V4-Flash runs alongside Kimi as service `vllm-small`, exposed on port 8004; current compose default is `DEEPSEEK_GPU_MEM_UTIL:-0.2` after the 2026-06-05 T3 sweep (was 0.25); speculative-config gained `"max_model_len":8192`.
- OpenWebUI is running in compose, but the 2026-05-27 start snapshot showed it as unhealthy.
- LiteLLM Proxy runs on port 4000 and routes by `model` to Kimi and DeepSeek. Smoke tests through proxy passed for both upstreams.
- `run_bench_suite.py` has been run through LiteLLM Proxy for both Kimi K2.6 and DeepSeek-V4-Flash; results are committed.
- Prometheus + Grafana configuration exists under `serving/compose/`, including provisioned dashboards: Phase 1 vLLM (`vllm-phase1.json`, panele zwalidowane pod obciążeniem 2026-06-05), GPU hardware DCGM (`dcgm-gpu.json`) i korelacyjny vLLM+DCGM (`vllm-dcgm-combined.json`) — oba DCGM czekają na deploy exportera (sesja 2026-08-12).
- Kimi K2.6 TTFT/TPOT parsing fixed (issue #31): `measure_ttft_once.py` now records a separate `ttft_any_token_seconds` / `tpot_any_token_seconds` covering reasoning-trace text (`delta.reasoning` / `delta.reasoning_content`) while `ttft_seconds` stays final-answer-only. Verified against the committed stream-debug artifacts.

Phase 1 deliverables still owed:

- **Prometheus + Grafana dashboard** — DONE (2026-06-05: walidacja nazw metryk + panele pod obciążeniem; screenshoty przed/po NVLink 2026-08-03). Rozszerzenie o DCGM w toku pod #34.
- **W1 write-up** — DONE (2026-06-05): all 8 threads written from committed evidence with `## Evidence` provenance; index baseline table + KV-budget synthesis filled (`5fc9648`).

---

## Current known status

- GitHub repo exists: `https://github.com/Czyszka/nanoserve-mini.git`.
- Local Windows laptop bootstrap is done; Python workflow uses `uv`; `ruff` + `pytest` configured; `.gitattributes` normalises line endings.
- Local research PDFs and Claude/Codex worktrees stay outside Git (`docs/**/papers/`, `.claude/worktrees/`, `.uv-cache-codex/`).
- **Server**: ubuntusrv2 (Ubuntu 24.04, 8×H200 NVL 143 GB, CUDA 13.2, driver
  595.58.03) z **NVLink 4-way** (07-31: dwie wyspy NV6 GPU 0-3 / 4-7,
  cross-island SYS; macierz `topo -m` i topologia w `infrastructure.md` §2.2;
  zyski i synteza: `results/summaries/2026-08-03-nvlink-day-summary.md`,
  T9 §14). Datasheet Supermicro SYS-521GE-TNRT zmirrorowany w
  `docs/operations/sys-521ge-tnrt.md`.
- **Reguła wygrzewki (od 08-03, obowiązkowa):** pomiar zawsze po
  benchu-wygrzewce na odrzut (`benchmark-methodology.md`, "Engine warm-up
  rule").
- **Kimi + DeepSeek + OpenWebUI + LiteLLM compose**: canonical compose lives at `serving/compose/docker-compose.kimi-k2.6.yml`.
- **Silnik Kimi: vLLM v0.26.0 (od 08-07) + drafter Eagle3.** Obowiązkowy
  workaround `--compilation-config pass_config.fuse_allreduce_rms=false` (race
  przy capture grafów CUDA na TP8/wyspach 4+4; diagnoza w
  `results/raw/2026-08-07_kimi_v026_*`); DeepSeek (`vllm-small`) nadal na 0.20.
  DFlash odrzucony po A/B 08-07 (`results/runs/2026-08-07_kimi_dflash_ab/NOTES.md`);
  benche c1 Kimi ZAWSZE na SWE custom — porównywalność z historią (szczegóły
  w tabeli decyzji).
- **Observability compose**: `serving/compose/docker-compose.observability.yml`
  (Prometheus + Grafana + renderer + od 2026-08-11 `dcgm-exporter` — prep
  laptopowy, deploy 2026-08-12) plus `serving/compose/prometheus/prometheus.yml`
  i provisioning w `serving/compose/grafana/provisioning/`.
- Benchmark/metrics producer scripts on `main` (`benchmarks/scripts/`):
  `request_once`, `measure_ttft_once`, `run_sequential_benchmark`,
  `collect_metrics_snapshot`, `sample_gpu_metrics`, `run_bench_suite`.

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

- **#34 — observability/DCGM:** dashboard Phase 1 zwalidowany pod obciążeniem
  (2026-06-05, 18 paneli na realnych nazwach v0.20); prep DCGM gotowy
  2026-08-11 (exporter w compose + CSV liczników + scrape job + dashboardy
  `nanoserve-dcgm-gpu` i `nanoserve-vllm-dcgm`); deploy i walidacja pól wg
  `docs/plans/2026-08-12-dcgm-observability.md`. Caveat: nazwy metryk vLLM
  weryfikowane na v0.20, Kimi na 0.26 — inwentarz w planie (Cz. 4). Runbooki:
  `serving/runbooks/load-test-and-grafana.md` oraz
  `serving/runbooks/kimi-concurrency-ladder-swe.md` (drabinka c=1/16/32/64).
- **Runbooki demo (gotowce):** decyzja 2026-08-11 — bash `lib.sh` + `demo-*.sh`
  wg kontraktu `serving/runbooks/demo-conventions.md` (read-only wobec stacku,
  artefakty poza repo); lib przetestowany na laptopie (strict mode, fail-fasty),
  test serwerowy = opcjonalna Cz. 6 planu 08-12; pierwszy gotowiec
  `demo-kimi-grafana.sh` po sesji DCGM.
- **W1 (#37 + artykuł + T9):** write-up 8 wątków, artykuł, T9 i notatka
  decyzyjna NVLink — COMPLETE; one-pager case study dodany 2026-08-10.
  Otwarte: T2/T5/T8 nie niosą wierszy z dowodami 2026-06-10 (P0/P2).
- **Prezentacja meetupowa NVLink: DOSTARCZONA (2026-08-09/10)** — samodzielny
  `index.html`, speaker notes do druku, wykresy W0–W7;
  `docs/presentations/2026-07-31-nvlink-meetup/`.
- **Drafter k=4 (plan 2026-08-10):** sesja wykonana (wg właściciela, 08-11),
  ale danych nie ma w repo — najpewniej nie zebrane albo nie wrzucone. Jeśli
  artefakty leżą na serwerze, dociągnąć przy okazji sesji 08-12; inaczej wynik
  pozostaje nieudokumentowany (plan:
  `docs/plans/2026-08-10-kimi-dflash-k4-swe.md`).
- **Benchmark Ollamy po LAN (firmowy PoC 2×A6000):** samodzielny, przenośny
  tool `benchmarks/ollama_lan_bench/` (2026-08-14, branch
  `claude/ollama-benchmark-script-uv-z2od5s`) — sekwencyjne zapytania do
  OpenAI-compat `/v1` Ollamy, start o zadanej godzinie (`--start-at`),
  prompt literal lub dataset SWE (`--dataset-offset` dla rozłącznych wycinków
  per klient), metryki TTFT/TPOT/E2E/throughput; własny projekt uv + PEP 723
  (kopiowalny na klientów bez repo), logika pomiarowa vendorowana z
  `benchmarks/scripts/`. Do zebrania: pierwsze realne runy z klientów.
- **#48 — speculative decoding methodology:** research issue otwarte; laptopowy
  follow-up przed finalnym T6.
- **#49 — pin observability images:** floating tagi (`latest`/`v3`); zrzut
  digestów wpisany do planu sesji 2026-08-12 (Cz. 5), pin po sesji.
- **#50/#51 — NVLink:** rozliczone/zamknięte; werdykty i historia:
  `results/summaries/2026-08-03-nvlink-day-summary.md`,
  `results/summaries/2026-06-11-nvlink-boundary-verdict.md`, T9, handoff log.

> Wpisy In flight skompaktowane 2026-08-11 do formatu sekcji (status, nie
> historia sesji). Pełna historia: `git show 0d5c2e0:docs/operations/agent-state.md`.

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
| NVLink 4-way | Zainstalowany 2026-07-31 (wyspy 4+4); GO dla batched TP≥4 potwierdzony pomiarem (2,08–2,97×); #51 zamknięte, #50 rozliczone komentarzem (zamknięcie po stronie właściciela) |
| Metodologia benchów | Od 2026-08-03 obowiązkowa wygrzewka po każdym starcie silnika; porównania konfiguracji tylko ciepłe-z-ciepłym; dekompozycje <10% wymagają A/B/A/B n≥3 |
| Rekonstrukcje "bez NVLinku" | `NCCL_P2P_DISABLE=1` nie zeruje ruchu NVL (ścieżki poza NCCL) — dawki tego typu są z definicji częściowe (T9 §14.6) |
| vLLM 0.26 dla Kimi | Od 2026-08-07 Kimi na `v0.26.0` z obowiązkowym `pass_config.fuse_allreduce_rms=false` (race przy capture grafów na TP8/4+4, klasa vllm#46253; 2×PASS potwierdzenia, 5×FAIL bez flagi); bramka wydajnościowa zaliczona: c32 warm 676 vs 594 tok/s (+13,8%). DeepSeek zostaje na 0.20 — migracja osobno |
| Plany sesji | Tagi obrazów Docker weryfikowane w rejestrze przed wpisaniem do planu (0.26.1rc0 istniał na GH, nie miał obrazu); helpery przenoszone ze sprawdzonych planów (wzorzec: `2026-08-03-nvlink-gap-fill.md`), zmienne raz w Cz. 0; checki fail-fast tylko na zweryfikowanym formacie danych (inspect escapuje cudzysłowy JSON) |
| Drafter Kimi | Eagle3 (k=3) zostaje; NVIDIA DFlash odrzucony po A/B 2026-08-07 (wolniejszy w c1 i c32, +0,05 util pamięci); hipoteza k=4 świadomie nieprzetestowana. Benche c1 Kimi ZAWSZE na SWE custom (nie random) — porównywalność z historią |

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
  **2026-08-03:** pola NVL 1011/1012 działają host-side (`dcgmi dmon`, probe
  nagłówka obowiązkowy — ciche pominięcie przy niedostępności); topologia po
  montażu mostków w `infrastructure.md` §2.2. Exporter (kontener + scrape job
  + wiersz dashboardu) nadal do zrobienia: prep laptopowy → deploy w osobnym
  touchu.
- [ ] Should `sample_gpu_metrics` be integrated into `run_bench_suite.py`, or stay as a separate explicit tool?
- [ ] Which Kimi-K2.6 memory parameters are stable enough for long runs while DeepSeek stays up beside it?
- [ ] When to implement `benchmarks/scripts/aggregate_runs.py` (Wave C)?

---

## Last validation

2026-08-14 (remote) standalone benchmark Ollamy `benchmarks/ollama_lan_bench/`:

```text
cd benchmarks/ollama_lan_bench && uv sync --extra dev && uv run pytest    26 passed
cd benchmarks/ollama_lan_bench && uv run ruff check .    OK
uv sync --extra dev && uv run ruff check benchmarks/ollama_lan_bench    OK (root config)
uv run pytest (root)    132 passed (regresja bez zmian)
smoke bez serwera (port zamkniety): wiersz z error=ConnectError, exit 0, JSON poprawny
zastane bledy root ruff w download_swe_bench_lite.py i results/runs/2026-07-31_*/nvlink/*.py — nietkniete
```

> Starsze bloki walidacji skompaktowane 2026-08-11 (szablon sync-state: tylko
> najnowszy blok). Pelna historia: `git show 5a2dd3c:docs/operations/agent-state.md`.

---

## Handoff log

Newest entry first.

### 2026-08-14 - Samodzielny benchmark Ollamy po LAN (ollama_lan_bench)

- Why: firmowy PoC na Ollamie (2×A6000) nie ma żadnych liczb (TTFT/TPOT/throughput — patrz `docs/project/company-ai-support-h200-plan.md`); potrzebny przenośny skrypt odpalany z klientów w sieci o zadanej godzinie.
- Did: nowy samodzielny katalog `benchmarks/ollama_lan_bench/` (bench_ollama.py z nagłówkiem PEP 723 + własny pyproject/uv.lock + 26 testów na MockTransport + README z instrukcjami uv i koordynacją wielu klientów). Sekwencyjne streamingowe zapytania do OpenAI-compat `/v1/chat/completions` (normalizacja base-url łyka też `/v1`), `--start-at HH:MM|ISO` (najbliższe wystąpienie, chunki sleep 30 s), `--prompt` lub `--dataset` (SWE JSONL) + `--dataset-offset`, warmup poza statystykami, wiersz błędu zamiast przerwania runu, artefakty results.jsonl + summary.json z blokiem `client` (hostname, scheduled/actual start). Logika pomiarowa vendorowana 1:1 z `benchmarks/scripts/` (bez importów — przenośność). Odpowiedź na pytanie o `vllm bench serve` vs Ollama w README.
- Range: branch `claude/ollama-benchmark-script-uv-z2od5s`
- Validation: OK (blok wyżej)
- Next: skopiować katalog + dataset SWE na klientów, pierwszy realny run na endpoint Ollamy; potem ewentualnie agregacja wyników wielu klientów.

### 2026-08-11 - Prezentacja dostarczona + prep DCGM/runbook przed sesją 08-12

- Why: domknięcie materiałów meetupowych i laptopowe przygotowanie rozszerzenia monitoringu o DCGM przed jutrzejszym slotem serwerowym.
- Did: samodzielny deck `index.html` + speaker notes do druku + one-pager W1; plan sesji k=4 (2026-08-10) dopisany; runbook drabinki c=1/16/32/64 na SWE; prep dcgm-exporter (compose + CSV liczników + scrape job + dashboard per-GPU i korelacyjny vLLM↔DCGM) z planem sesji 2026-08-12 (bramka koegzystencji PROF, pull obrazu w tle, rollback <2 min); wieczorem: porządki repo (sync+tidy, agent-state 56→20 KB, `_cv/` w lokalnym exclude), konwencje runbooków demo + `lib.sh` + opcjonalna Cz. 6 (test lib) w planie sesji.
- Range: `3914f46..0d05227` (15 commits, w tym 2 własne sync/tidy)
- Validation: OK
- Next: sesja serwerowa wg `docs/plans/2026-08-12-dcgm-observability.md`.

### 2026-08-07/08 - A/B drafterów Kimi: DFlash odrzucony, Eagle3 zostaje

- Why: użytkownik chciał sprawdzić drafter NVIDIA DFlash jako zamiennik Eagle3 (wyjątek od scope, jawnie odblokowany).
- Did: sesja A/B na 0.26 (obie nogi util 0,65) — DFlash wolniejszy w c1 (1,07×) i c32 (0,89×), pozycje 4-7 bloku k=8 dają 15% akceptacji; bramka NIE, compose bez zmian; stack przywrócony w pełnym składzie; wykryty i odnotowany błąd metodyczny (c1-random vs historyczne c1-SWE).
- Range: `1072d48..3914f46` (4 commits)
- Validation: OK
- Next: materiał write-upowy z A/B (opcjonalnie); komentarz do vllm#46253 wciąż po stronie właściciela; migracja DeepSeeka na 0.26 — osobna decyzja.

### 2026-08-07 - Kimi na vLLM 0.26: diagnoza CUDA error i adopcja z workaroundem

- Why: podbicie vLLM 0.20→0.26 wywalało silnik Kimi CUDA errorem przy starcie; trzeba było znaleźć przyczynę i rozwiązanie optymalne wydajnościowo.
- Did: 3 iteracje (zrzuty diagnostyczne → matrix izolacyjny R1-R4 → potwierdzenie) wskazały race w passie `fuse_allreduce_rms` przy capture grafów (TP8 na 4+4, custom AR w fallbacku PYNCCL); compose Kimi na 0.26 z flagą off, bramka zaliczona (c32 warm 676 tok/s, +13,8% vs 594).
- Range: `35ca9a5..1072d48` (8 commits)
- Validation: OK
- Next: komentarz do vllm#46253 (treść gotowa w rozmowie 08-07, wkleja właściciel); migracja Qwen/DeepSeek na 0.26 i restore stacku — osobne touche.

### 2026-08-03 - NVLink zweryfikowany pomiarem: trace, dekompozycja, wygrzewka, docs domknięte

- Why: montaż mostków (07-31) wymagał weryfikacji predykcji #50 i domknięcia mechanizmu share×capture.
- Did: 5 sesji serwerowych + analiza laptopowa — trace c32 (NCCL 83,9%→61,1%), zyski 2,08×/2,97×, odkryta kara zimnego startu 10–15% (reguła wygrzewki w metodologii), T9 §14, notatka decyzyjna §9, infrastructure §2.2, para screenów Grafany przed/po, #50 rozliczone komentarzem, #51 zamknięte, errata nadpisanych artefaktów naprawiona.
- Range: `6472d06..e7986c4` (30 commits)
- Validation: OK
- Next: prezentacja meetupowa (plan `2026-07-31-nvlink-meetup-prezentacja.md`) z gotowymi materiałami; zamknięcie #50 po stronie właściciela.

### 2026-07-31 (laptop) - server session plan: NVLink 4-way install verification

- Why: user installed 4-way NVLink bridges (islands 0-3 / 4-7) and asked for a same-day server plan; the #50 verdict was built entirely on PCIe-era predictions, so the install is an opportunity to validate the model, not just the hardware.
- Did: added `docs/plans/2026-07-31-nvlink-install-verification.md` — pre-registered prediction table (P2P >100 GB/s in-island, NCCL busbw >100 GB/s vs the 7,2-7,9 GB/s PCIe transport ceiling, Qwen TP4 c64 680 -> ~1430 tok/s, Kimi TP8 c32 285 -> ~770 tok/s, both c=1 rows unchanged because floor-bound, Kimi c16 anomaly predicted to survive, PCIe RX predicted to drop), 7 parts sized to ~112 min with an explicit cut order, `topo -m` as the hard gate, a cross-island control pair inside the P2P measurement, a 2+2 NCCL control that tests ring-vs-hierarchical before Kimi runs, torch/NCCL run from the vLLM image instead of building `cuda-samples`, DCGM NVLINK_TX/RX fields probed with a fallback, error-counter delta bracketing real load, and the custom-all-reduce confound recorded up front.
- Note: the plan is written **self-contained on purpose** — all helpers inlined, no "paste from the 06-10 plan", since the 06-11 session was lost to exactly that failure mode. Kimi's engine start is scheduled as the session restore, so the production-case benchmark costs only bench time.
- Validation: `git diff --check` OK (docs-only; no `.py` touched).
- Next: run the session; then rewrite `infrastructure.md` §2.2 (still says PCIe-only), comment predicted-vs-measured on #50, add a "measurement after intervention" section to T9.

> Pre-2026-07-31 handoff entries compacted 2026-08-11. Source: `0d5c2e0`.
> Full history: `git show 0d5c2e0:docs/operations/agent-state.md`.
