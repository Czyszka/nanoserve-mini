# Server work plan — 2026-05-19

Plan pracy na serwerze GPU (Ubuntu 24, 8×H200 NVL) dla `nanoserve-mini`.

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
- [ ] Sekret `LITELLM_MASTER_KEY` ustalony, dopisany do serwerowego `.env`
      w `serving/compose/` (NIE commitować). Najpóźniej rano przed sesją.

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

| Cz. | Co | Czas |
|---|---|---|
| 0 | Start, `git pull`, `uv sync`, snapshot live state | 10 min |
| A | Capture live compose + recover DeepSeek artefakty 2026-05-11 | 25 min |
| B | Postawić LiteLLM od zera (pull + config test + start) + smoke | 45 min |
| D | `run_bench_suite` Kimi + DeepSeek przez proxy | 60 min |
| E | Commit, push, update agent-state | 15 min |
| — | Bufor na poprawki configu / blockery | 25 min |

Część C (osobna walidacja metrics scripts) **wcięta** — `run_bench_suite`
woła `collect_metrics_snapshot --phase pre/post`, więc walidacja
end-to-end dzieje się przy okazji D.

---

## Część 0 — start sesji (10 min)

- [ ] `cd ~/nanoserve-mini && git status` — sprawdzić, czy nie ma
      lokalnych nietkniętych zmian z 2026-05-11.
- [ ] `git pull --ff-only origin main`.
- [ ] `uv sync --extra dev` (pierwszy raz na serwerze; nie blokujące,
      jeśli padnie — zanotować w `session_notes.md`, fallback do
      bezpośredniego `python -m benchmarks.scripts...`).
- [ ] `mkdir -p results/runs/2026-05-19_phase1_closeout`.
- [ ] Zapisać commit hash sesji do `session_notes.md`.
- [ ] `docker ps` + `nvidia-smi` — stan startowy (do `session_notes.md`).

---

## Część A — capture live state + recover artefakty (25 min)

Cel: doprowadzić repo do stanu, w którym serwer i GitHub są spójne.
**UWAGA:** stack już stoi (vllm + vllm-small z DeepSeek), więc nie
restartujemy, tylko capture.

### A1. Capture live compose

- [ ] Zlokalizować na serwerze faktycznie używany `docker-compose.*.yml`
      (prawdopodobnie w `serving/compose/` lub w `~`). `docker compose ls`
      pomoże znaleźć project name + working dir.
- [ ] `docker compose config` (z odpowiedniego katalogu) — zrzuca w pełni
      rozwiązaną konfigurację → zapisać do
      `results/runs/2026-05-19_phase1_closeout/compose_live_resolved.yml`.
- [ ] `diff` plik źródłowy względem `serving/compose/docker-compose.kimi-k2.6.yml`
      z repo → zapisać do `compose_live_vs_repo.diff`.
- [ ] Decyzja kanoniczności (zapisać w `session_notes.md`):
  - jeden plik z trzema usługami (Kimi + vllm-small + OpenWebUI + LiteLLM), albo
  - profile compose (`--profile big`, `--profile small`, `--profile proxy`).
- [ ] Zaktualizować tracked compose, jeśli live ma sensowniejsze flagi
      (np. realne `--gpu-memory-utilization`, tool/reasoning parsery,
      `--max-model-len`). Pinowanie obrazów z PR feat/litellm-proxy
      zachować. **Nie restartować żywych usług** — zmiany commitujemy,
      pull na serwerze, restart przy następnej okazji.
- [ ] Commit: `infra(serving): reconcile kimi compose with live server state`.

### A2. Recover DeepSeek-V4-Flash benchmark artefacts

- [ ] Zlokalizować artefakty z 2026-05-11 na serwerze
      (`results/runs/...`, ewentualnie ad-hoc katalogi).
- [ ] Zweryfikować, że każdy ma `controls` + `methodology`
      + `benchmark_mode` (schemat v2/v3). Jeśli któryś jest starszy —
      odnotować w `session_notes.md`, nie naprawiać ręcznie.
- [ ] Przenieść do `results/runs/<oryginalny_run_id>/` jeśli jeszcze
      nie tam są.
- [ ] Commit: `bench: recover deepseek-v4-flash artefacts from 2026-05-11 session`.

---

## Część B — postawić LiteLLM Proxy od zera + smoke (45 min)

Cel: LiteLLM Proxy **nie jest jeszcze uruchomione ani ściągnięte na
serwer**. Trzeba zrobić full setup: pull obrazu, walidacja configu zanim
podniesiemy, start, smoke. Phase 1 DoD #2.

### B1. Pre-flight (5 min)

- [ ] Potwierdzić, że Kimi (8000) i DeepSeek (8004) odpowiadają
      bezpośrednio: `curl -s http://localhost:8000/v1/models | jq`,
      `curl -s http://localhost:8004/v1/models | jq`.
- [ ] Sprawdzić, że `serving/compose/.env` na serwerze ma
      `LITELLM_MASTER_KEY=...` i `LITELLM_HOST_PORT=4000` (jeśli nie —
      dopisać teraz, **nie commitować**).
- [ ] Sprawdzić, że port 4000 jest wolny: `ss -ltn | grep :4000`.
- [ ] Project name żywego compose: `docker compose ls` — zanotować,
      czy LiteLLM trafi do tej samej sieci co istniejący `vllm` /
      `vllm-small` (krytyczne dla `http://vllm:8000` w configu).

### B2. Walidacja configu przed startem (10 min)

- [ ] `cat serving/compose/litellm-config.yaml` — przegląd:
      `model_list` zgadza się z `--served-model-name` na obu vllm-ach
      (Kimi → `kimi-k2.6`, DeepSeek → `DeepSeek-V4-Flash`);
      `api_base` na `http://vllm:8000/v1` i `http://vllm-small:8004/v1`
      tylko jeśli sieć compose wspólna (B1).
- [ ] `python -c "import yaml; yaml.safe_load(open('serving/compose/litellm-config.yaml'))"`
      — parsuje bez błędu.
- [ ] Dry-run compose: `docker compose config litellm` — pokaże ostateczny
      wolumen z configiem, env i komendę startową. Sprawdzić, że
      `LITELLM_MASTER_KEY` się interpoluje (nie zostaje literalnie
      `${LITELLM_MASTER_KEY}`).
- [ ] Jeśli sieć nie jest wspólna z żywym stackiem — zdecydować:
      (a) przepisać `api_base` na `http://host.docker.internal:8000/v1`
      + `:8004/v1` i dodać `extra_hosts` w compose, albo
      (b) wystartować nowy compose project i podpiąć go do istniejącej
      sieci (`networks.<name>.external: true`). Decyzję zapisać
      w `session_notes.md`.

### B3. Pull + start (10 min)

- [ ] `cd serving/compose && docker compose pull litellm` — pierwsze
      ściągnięcie obrazu `ghcr.io/berriai/litellm:main-v1.66.0-stable`.
      Zapisać rozmiar obrazu i czas pull do `session_notes.md`.
- [ ] `docker compose up -d litellm` — **tylko ten service**, vllm/vllm-small
      nie ruszamy.
- [ ] `docker compose logs --tail 100 litellm` — szukać:
      `LiteLLM Proxy initialized`, brak ERRORów na ładowaniu configu,
      `healthcheck` przechodzi.
- [ ] `docker compose ps litellm` — status `healthy` (healthcheck na
      `/health/liveliness`).

### B4. Smoke (10 min)

Wyniki dopisać do `results/runs/2026-05-19_phase1_closeout/litellm_smoke.txt`.

- [ ] `curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
        http://localhost:4000/v1/models | jq`
      — powinno listować `kimi-k2.6` i `DeepSeek-V4-Flash`.
- [ ] `curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
        -H "Content-Type: application/json" \
        -d '{"model":"kimi-k2.6","messages":[{"role":"user","content":"ping"}],"max_tokens":8}' \
        http://localhost:4000/v1/chat/completions | jq`
- [ ] Powtórzyć dla `DeepSeek-V4-Flash`.
- [ ] Test 401: ten sam request bez nagłówka `Authorization` powinien
      dostać 401 — potwierdza, że master key działa.
- [ ] `curl -s http://localhost:4000/health/liveliness` — 200.
- [ ] Jeśli endpoint pada — fallback: bezpośredni `curl` do `:8000`/`:8004`
      (już w B1 potwierdzone że działają), żeby izolować, czy problem
      jest w proxy czy upstream. Najczęstsze przyczyny: wrong
      `api_base` (DNS), brak `served-model-name` matchu, master key.

### B5. Bufor na poprawki configu (10 min)

- [ ] Slot zarezerwowany na typowe poprawki: poprawić `api_base`,
      dodać brakujący `litellm_params.api_key: fake` (vllm nie wymaga
      ale LiteLLM tak), zmienić nazwę modelu, restart litellm
      (`docker compose restart litellm`), repeat smoke.
- [ ] Jeśli nie wykorzystany — przelewa się do bufora ogólnego sesji.

### B6. Decyzja OpenWebUI

- [ ] Decyzja w `session_notes.md`: OpenWebUI zostaje na bezpośrednim
      `vllm:8000`, czy przepinamy na `litellm:4000`. Domyślnie zostawić
      bezpośrednio dla mniejszego ryzyka. Open question w agent-state
      zamknąć w obie strony.

### B2. Smoke

Wyniki dopisać do `results/runs/2026-05-19_phase1_closeout/litellm_smoke.txt`.

- [ ] `curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" http://localhost:4000/v1/models | jq`
      — powinno listować `kimi-k2.6` i `DeepSeek-V4-Flash`.
- [ ] `curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
        -H "Content-Type: application/json" \
        -d '{"model":"kimi-k2.6","messages":[{"role":"user","content":"ping"}],"max_tokens":8}' \
        http://localhost:4000/v1/chat/completions | jq`
- [ ] Powtórzyć dla `DeepSeek-V4-Flash`.
- [ ] Jeśli któryś endpoint pada — fallback: bezpośredni `curl` do
      `http://localhost:8000/v1` i `http://localhost:8004/v1`, żeby
      izolować, czy problem jest w upstream czy w proxy.

### B3. Decyzja OpenWebUI

- [ ] Decyzja w `session_notes.md`: OpenWebUI zostaje na bezpośrednim
      `vllm:8000`, czy przepinamy na `litellm:4000`. Domyślnie zostawić
      bezpośrednio dla mniejszego ryzyka. Open question w agent-state
      zamknąć w obie strony.

---

## Część D — `run_bench_suite` Kimi + DeepSeek przez LiteLLM (75 min)

Cel: pierwszy live test bench launchera. Oba modele (vllm-small z DeepSeek
już stoi). Suite wewnętrznie woła `snapshot_pre → request_once →
measure_ttft_once → run_sequential_benchmark → snapshot_post`, więc
**przy okazji waliduje metrics scripts end-to-end** na żywym vLLM
(zamiast osobnej Części C).

- [ ] `export LITELLM_MASTER_KEY=<...>` (potwierdzić, że ustawiony).

### D1. Kimi-K2.6 (~30 min)

- [ ] `uv run python -m benchmarks.scripts.run_bench_suite \
        --base-url http://127.0.0.1:4000 \
        --metrics-base-url http://127.0.0.1:8000 \
        --model kimi-k2.6`
- [ ] `ls results/runs/2026-05-19_kimi-k2-6_run-01/` — sprawdzić wszystkie
      podkatalogi (correctness, latency, repeated, server_metrics pre/post,
      bench_suite/summary.json).
- [ ] Otworzyć `bench_suite/summary.json` — czy `git_commit`, `run_uuid`,
      `workload_spec` zapisane.
- [ ] Sanity check `server_metrics/snapshot_*.json`: czy `kv_cache_usage`,
      `num_requests`, GPU memory mają sensowne wartości, czy nic puste/NaN.

### D2. DeepSeek-V4-Flash (~25 min)

- [ ] `uv run python -m benchmarks.scripts.run_bench_suite \
        --base-url http://127.0.0.1:4000 \
        --metrics-base-url http://127.0.0.1:8004 \
        --model DeepSeek-V4-Flash`
- [ ] Te same sanity checki co D1.
- [ ] Notatka w `session_notes.md`: różnice TTFT/TPOT Kimi vs DeepSeek
      (1-2 zdania, bez wniosków — surowe liczby).

### D3. Decyzja przy blockerze

- [ ] Jeśli D1 padnie: NIE iść w D2, zapisać failure (komenda, krok, błąd,
      hipoteza), użyć buforu na fix lub przepiąć na bezpośredni endpoint
      vllm (`--base-url http://127.0.0.1:8000`) żeby odizolować problem
      proxy vs upstream.
- [ ] Jeśli D2 padnie po działającym D1: nie blokować sesji, commit z D1
      + failure note z D2.

Sample_gpu_metrics pod load — następna sesja.

---

## Część E — commit + handoff (20 min)

- [ ] `git status` — przegląd; sprawdzić, że nie wchodzą wagi, cache,
      sekrety.
- [ ] Reguła wyników: jeśli któryś plik `.json` / `.jsonl` z runu jest
      > kilka MB, commitować tylko `summary.json` + ścieżkę lokalną
      do raw (zgodnie z policy w CLAUDE.md).
- [ ] `git add -p` na artefakty + ewentualne małe poprawki compose /
      docs.
- [ ] Walidacja przed commitem (skrócona, jeśli nie zmienialiśmy kodu):
      `uv run ruff check .` i jeśli były zmiany w skryptach
      `uv run pytest -q`.
- [ ] Commit: `bench: phase 1 close-out — litellm smoke + bench suite live runs`.
- [ ] `git push`.
- [ ] Update `docs/operations/agent-state.md`:
  - zamknąć open questions w zakresie tego co realnie sprawdzone
    (recovery 2026-05-11, kanoniczność compose, OpenWebUI routing,
    walidacja metrics scripts — tę zamykamy efektem ubocznym `run_bench_suite`),
  - oznaczyć DoD #2 (LiteLLM Proxy) jako done jeśli smoke przeszedł,
  - zostawić #4 (Grafana) i #8 (W1) jako not started,
  - dopisać do next-steps drugi model (DeepSeek) i sample_gpu_metrics
    pod load jako pierwsze rzeczy na następną sesję,
  - handoff entry z `Did / Validation / Next`.

---

## Kryteria udanej sesji (minimum DoD #2)

- [ ] Artefakty 2026-05-11 w repo.
- [ ] LiteLLM Proxy odpowiada na `/v1/models` i przepuszcza
      `/v1/chat/completions` do obu upstreamów.
- [ ] `collect_metrics_snapshot` + `sample_gpu_metrics` produkują
      sensowne JSON-y na żywym vLLM.
- [ ] `run_bench_suite` dla Kimi skończony end-to-end przez proxy
      (to jednocześnie waliduje metrics scripts).
- [ ] `run_bench_suite` dla DeepSeek-V4-Flash skończony albo
      udokumentowany failure note.
- [ ] Commit + push + agent-state zaktualizowany.

## Kryteria nieudanej, ale wartościowej sesji

- [ ] LiteLLM nie startuje → failure note z konkretnym błędem
      (image tag? config? port? master key?), upstreamy nadal działają
      bezpośrednio.
- [ ] `run_bench_suite` pada → wiadomo na którym kroku
      (`snapshot_pre` / `request_once` / `ttft` / `sequential` /
      `snapshot_post`) i z jakim błędem, bo step ordering jest
      otestowany lokalnie.
- [ ] Metrics scripts pokazują, że schemat `v1` nie pasuje do
      aktualnego vLLM `/metrics` → mamy konkretną listę pól do
      poprawienia na laptopie w kolejnej sesji.

---

## Świadomie poza scope tej sesji

- **`sample_gpu_metrics` pod load** — następna sesja (dziś za drogie czasowo).
- **Prometheus + Grafana** (DoD #4) — kolejna sesja serwerowa.
- W1 write-up — pisanie na laptopie po sesji.
- Runbook TP=8 + Eagle3 — compose po reconcile traktujemy jako runbook.
- Optymalizacja parametrów Kimi pod małyfit — open question zostaje.
- `aggregate_runs.py` (Wave C) — laptop, później.
- Coding-agent eval — zarchiwizowane na `archive/coding-agent-tasks`.
