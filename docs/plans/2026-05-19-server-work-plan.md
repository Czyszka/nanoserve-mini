# Server work plan — 2026-05-19

Plan pracy na serwerze GPU (Ubuntu 24, 8×H200 NVL) dla `nanoserve-mini`.

## Status po sesji — 2026-05-19

### Zrobione

- [x] Odzyskano i wypchnięto wyniki benchmarków z 2026-05-11.
- [x] Zlokalizowano i zsynchronizowano poprawny Docker Compose z serwera.
- [x] Poprawiono compose dla Kimi K2.6: użycie tensor parallelism zamiast błędnego DP setupu.
- [x] Uruchomiono i potwierdzono komunikację: `vllm`, `vllm-small`, OpenWebUI.
- [x] Uruchomiono smoke benchmarki dla Kimi K2.6 i DeepSeek-V4-Flash.
- [x] Zebrano i wypchnięto surowe artefakty stream debug dla Kimi K2.6 pod późniejszą naprawę TTFT/TPOT.
- [x] Utworzono issue #31 dla poprawki parsera Kimi TTFT/TPOT.
- [x] Utworzono issue #32 dla uporządkowania `.gitignore` i artefaktów benchmarkowych.
- [x] Uruchomiono LiteLLM Proxy.
- [x] Wykonano smoke testy LiteLLM Proxy.
- [x] Uruchomiono i wypchnięto `run_bench_suite.py` przez LiteLLM Proxy dla Kimi K2.6 i DeepSeek-V4-Flash.
- [x] Dodano konfigurację Prometheus + Grafana do repo.
- [x] Uruchomiono kontenery Prometheus + Grafana.

### Częściowo zrobione / do domknięcia

- [~] Observability: kontenery działają i metryki są widoczne, ale dashboard/panele Grafany nie są jeszcze zdefiniowane jako gotowy artefakt.
- [~] Metryki vLLM: rozpoczęto identyfikację realnych nazw metryk; dashboard powinien powstać na podstawie faktycznej listy metryk, nie zgadywanych nazw.
- [~] Dokumentacja sesji: brak czasu na notatkę w repo; przeniesione do issue #33.

### Zostaje po sesji

- [ ] Naprawa parsera Kimi TTFT/TPOT na laptopie — issue #31.
- [ ] Uporządkowanie `.gitignore` dla `results/runs` na laptopie — issue #32.
- [ ] Spisanie podsumowania sesji — issue #33.
- [ ] Utworzenie właściwego dashboardu Grafana dla vLLM/Kimi/DeepSeek.
- [ ] W1 write-up po domknięciu dashboardu/observability.
- [ ] Aktualizacja `docs/operations/agent-state.md`, jeśli nadal jest niezgodny ze stanem po sesji.

---

**Cel sesji:** zamknąć Phase 1 minimum — odzyskać artefakty z 2026-05-11,
uzgodnić compose, smoke LiteLLM Proxy, zwalidować skrypty metryk
end-to-end na żywym vLLM i puścić po jednym pełnym `run_bench_suite`
per model przez proxy. Bez Grafany, bez W1, bez nowego runbooka TP=8 —
te zostają na kolejne sesje.

Plan jest operacyjny. Założenie: **~3h netto** (sesja skrócona przez
dodatkowe obowiązki). Sesja ma odpalać przygotowane rzeczy, nie
projektować.

**Stan startowy potwierdzony przez użytkownika:** na serwerze już stoi
`vllm-small` z `deepseek-ai/DeepSeek-V4-Flash` (i prawdopodobnie Kimi),
więc Część A skraca się do capture + diff, a w Części D mieszczą się
**oba modele**. Osobna walidacja metryk wycięta — `run_bench_suite`
robi pre/post snapshot przy okazji.

---

## Warunki wstępne (zrobione na laptopie przed sesją)

- [x] PR `feat/litellm-proxy` zmergowany (compose + `litellm-config.yaml`
      + pinowane tagi obrazów + `LITELLM_MASTER_KEY` w `.env.example`).
- [x] PR `feat/run-bench-suite` zmergowany (`benchmarks/scripts/run_bench_suite.py`
      + `--api-key` propagacja).
- [x] `main` zielony lokalnie: `ruff` clean, `pytest -q` = 113 passed.
- [x] Sekret `LITELLM_MASTER_KEY` ustalony, dopisany do serwerowego `.env`
      w `serving/compose/` (NIE commitować). Potwierdzone po smoke/bench przez proxy.

---

## Run directory

Dla benchmarków per model używamy auto-generowanych identyfikatorów
z `run_bench_suite.py` (`YYYY-MM-DD_<model-slug>_run-NN`). Dla artefaktów
sesyjnych (snapshot env, notatki, compose diff) tworzymy osobny katalog:

```text
results/runs/2026-05-19_phase1_closeout/
  session_notes.md
  compose_live_vs_repo.diff
  litellm_smoke.txt
  metrics_validation/
    snapshot_pre.json
    snapshot_post.json
    gpu_samples.csv
    gpu_samples_meta.json
```

---

## Budżet czasu (~3h netto)

| Cz. | Co | Czas | Status |
|---|---|---:|---|
| 0 | Start, `git pull`, `uv sync`, snapshot live state | 10 min | częściowo / wykonane operacyjnie |
| A | Capture live compose + recover artefakty 2026-05-11 | 25 min | done |
| B | Postawić LiteLLM od zera (pull + config test + start) + smoke | 45 min | done |
| D | `run_bench_suite` Kimi + DeepSeek przez proxy | 60 min | done |
| E | Commit, push, update agent-state | 15 min | commit/push done; agent-state do sprawdzenia |
| — | Bufor na poprawki configu / blockery | 25 min | zużyty na compose/Git/observability |

Część C (osobna walidacja metrics scripts) **wcięta** — `run_bench_suite`
woła `collect_metrics_snapshot --phase pre/post`, więc walidacja
end-to-end dzieje się przy okazji D.

---

## Część 0 — start sesji (10 min)

- [x] `cd ~/nanoserve-mini && git status` — sprawdzić, czy nie ma
      lokalnych nietkniętych zmian z 2026-05-11.
- [x] `git pull --ff-only origin main` / późniejsze synchronizacje przez `pull --rebase`.
- [x] `uv sync --extra dev` lub środowisko `uv` wystarczające do uruchomienia benchmarków.
- [x] Utworzono katalogi runów dla wyników i artefaktów.
- [ ] Zapisać commit hash sesji do `session_notes.md`.
- [x] `docker ps` + `nvidia-smi` — stan startowy sprawdzany operacyjnie podczas uruchamiania usług.

---

## Część A — capture live state + recover artefakty (25 min)

Cel: doprowadzić repo do stanu, w którym serwer i GitHub są spójne.
**UWAGA:** stack już stoi (vllm + vllm-small z DeepSeek), więc nie
restartujemy, tylko capture.

### A1. Capture live compose

- [x] Zlokalizować na serwerze faktycznie używany `docker-compose.*.yml`.
- [x] Porównać live compose z tracked compose.
- [x] Zaktualizować tracked compose, jeśli live ma sensowniejsze flagi.
- [x] Zachować konfigurację bez sekretów.
- [x] Commit/push compose: m.in. poprawka Kimi TP zamiast DP.

### A2. Recover benchmark artefacts

- [x] Zlokalizować i wypchnąć artefakty benchmarkowe z 2026-05-11 / sesji powiązanych.
- [x] Dodać smoke results dla Kimi i DeepSeek.
- [x] Dodać Kimi stream debug artifacts.
- [x] Dodać LiteLLM proxy suite results dla obu modeli.
- [ ] Pełne uporządkowanie polityki `.gitignore` dla wyników — przeniesione do issue #32.

---

## Część B — postawić LiteLLM Proxy od zera + smoke (45 min)

Cel: LiteLLM Proxy jako Phase 1 DoD #2.

### B1. Pre-flight

- [x] Potwierdzić, że Kimi (8000) i DeepSeek (8004) odpowiadają bezpośrednio.
- [x] Sprawdzić / ustawić `LITELLM_MASTER_KEY` w serwerowym `.env`.
- [x] Sprawdzić i użyć portu 4000.
- [x] Potwierdzić, że usługi są w odpowiedniej sieci Docker / komunikują się.

### B2. Walidacja configu przed startem

- [x] Przejrzeć `serving/compose/litellm-config.yaml`.
- [x] Dopasować `model_list` do `served-model-name`.
- [x] Zweryfikować skutecznie przez start i smoke testy.

### B3. Pull + start

- [x] Uruchomić LiteLLM Proxy.
- [x] Sprawdzić logi/status kontenera.
- [x] Potwierdzić health/liveliness.

### B4. Smoke

- [x] `/v1/models` przez LiteLLM Proxy działa.
- [x] `/v1/chat/completions` przez LiteLLM Proxy działa dla `kimi-k2.6`.
- [x] `/v1/chat/completions` przez LiteLLM Proxy działa dla `DeepSeek-V4-Flash`.
- [x] Wynik smoke / dowód działania wypchnięty do repo.

### B5. Bufor na poprawki configu

- [x] Wykorzystany na poprawki compose / konflikt Git / konfigurację observability.

### B6. Decyzja OpenWebUI

- [x] OpenWebUI działa z aktualnym stackiem; pełne przepięcie przez LiteLLM nie było potrzebne w tej sesji.

---

## Część D — `run_bench_suite` Kimi + DeepSeek przez LiteLLM (75 min)

Cel: pierwszy live test bench launchera. Oba modele (vllm-small z DeepSeek
już stoi). Suite wewnętrznie woła `snapshot_pre → request_once →
measure_ttft_once → run_sequential_benchmark → snapshot_post`, więc
**przy okazji waliduje metrics scripts end-to-end** na żywym vLLM
(zamiast osobnej Części C).

- [x] `LITELLM_MASTER_KEY` ustawiony i użyty.

### D1. Kimi-K2.6

- [x] `run_bench_suite` wykonany przez LiteLLM Proxy dla `kimi-k2.6`.
- [x] Wyniki wypchnięte do repo.
- [x] Zidentyfikowano problem `TTFT: n/a` / `TPOT: n/a`.
- [x] Zebrano dodatkowe stream debug artifacts do późniejszej naprawy parsera.
- [x] Utworzono issue #31.

### D2. DeepSeek-V4-Flash

- [x] `run_bench_suite` wykonany przez LiteLLM Proxy dla `DeepSeek-V4-Flash`.
- [x] Wyniki wypchnięte do repo.
- [x] Smoke + benchmark potwierdzają działanie przez proxy.

### D3. Decyzja przy blockerze

- [x] Kimi TTFT/TPOT nie blokuje sesji; zapisano jako problem parsera i przeniesiono do issue #31.

Sample_gpu_metrics pod load — następna sesja.

---

## Część E — commit + handoff (20 min)

- [x] `git status` / przegląd zmian wykonywany wielokrotnie.
- [x] Sprawdzono i uniknięto commitowania sekretów / `.env`.
- [x] Artefakty wynikowe wypchnięte, w razie potrzeby przez `git add -f`.
- [x] Commit + push wyników compose smoke, stream debug i bench suite.
- [ ] Update `docs/operations/agent-state.md` — do sprawdzenia po sesji, jeśli jest stale.
- [x] Brak czasu na osobną notatkę — utworzono issue #33 z treścią do spisania później.

---

## Kryteria udanej sesji (minimum DoD #2)

- [x] Artefakty 2026-05-11 / powiązane benchmarki w repo.
- [x] LiteLLM Proxy odpowiada na `/v1/models` i przepuszcza
      `/v1/chat/completions` do obu upstreamów.
- [x] `run_bench_suite` produkuje pre/post snapshots i wyniki na żywym vLLM.
- [x] `run_bench_suite` dla Kimi skończony end-to-end przez proxy.
- [x] `run_bench_suite` dla DeepSeek-V4-Flash skończony end-to-end przez proxy.
- [x] Commit + push wykonane.
- [ ] Agent-state do aktualizacji, jeśli stale.

## Kryteria nieudanej, ale wartościowej sesji

Nie dotyczy głównej ścieżki: LiteLLM i bench suite przeszły. Wartościowy blocker:

- [x] Kimi TTFT/TPOT parser pokazuje `n/a`; zebrano dane i utworzono issue #31.
- [x] `.gitignore` / tracking wyników wymaga uporządkowania; utworzono issue #32.

---

## Świadomie poza scope tej sesji

- **`sample_gpu_metrics` pod load** — następna sesja.
- **Pełny dashboard Grafana** — stack dodany i uruchomiony, ale panele/dashboard jako artefakt nadal do zrobienia.
- W1 write-up — pisanie na laptopie po sesji.
- Runbook TP=8 + Eagle3 — compose po reconcile traktujemy jako runbook.
- Optymalizacja parametrów Kimi pod małyfit — open question zostaje.
- `aggregate_runs.py` (Wave C) — laptop, później.
- Coding-agent eval — zarchiwizowane na `archive/coding-agent-tasks`.
