# Post-server laptop plan — after 2026-05-19 session

Plan pracy na laptopie po udanej sesji serwerowej 2026-05-19. Cel: domknąć repo hygiene, parsery, dokumentację i przygotować następne wejście na serwer bez marnowania czasu GPU.

## Kontekst

Sesja serwerowa dostarczyła główne artefakty Phase 1:

- działający compose dla Kimi K2.6, DeepSeek-V4-Flash, OpenWebUI i LiteLLM Proxy,
- smoke i bench suite przez LiteLLM Proxy dla obu modeli,
- raw stream debug artifacts dla problemu Kimi TTFT/TPOT,
- bootstrap Prometheus + Grafana.

Na laptopie nie uruchamiamy dużych modeli. Laptop służy teraz do analizy, napraw skryptów, dokumentacji, testów jednostkowych i przygotowania kolejnej sesji GPU.

---

## Priorytet 1 — repo hygiene i odblokowanie normalnej pracy

### 1. Fix `.gitignore` dla benchmark artifacts — issue #32

Cel: małe, strukturalne wyniki benchmarków powinny dać się commitować normalnym `git add`, bez ciągłego `git add -f`.

Zakres:

- sprawdzić lokalnie `git check-ignore -v` dla przykładowych plików z `results/runs/`,
- dopuścić małe pliki wynikowe: `.json`, `.jsonl`, `.csv`, `.md`,
- dalej ignorować: `.env`, tokeny, cache HF, modele, duże logi, Nsight traces, SQLite runtime state,
- opisać w komentarzu `.gitignore`, co commitujemy, a czego nie.

Akceptacja:

- `git add results/runs/<run_id>/.../summary.json` działa bez `-f`,
- duże/local-only artefakty dalej są ignorowane,
- `uv run ruff check .` i `uv run pytest -q` przechodzą, jeśli dotknięto plików okołokodowych.

---

## Priorytet 2 — naprawa Kimi TTFT/TPOT parsera

### 2. Fix `measure_ttft_once.py` dla reasoning stream — issue #31

Cel: użyć zebranych na serwerze raw SSE artifacts do poprawy parsera bez ponownego odpalania Kimi.

Zakres:

- przeanalizować raw stream debug artifacts z `results/runs/2026-05-19_kimi-k2.6_stream-debug/`,
- potwierdzić, czy Kimi streamuje tekst w `delta.content`, `delta.reasoning_content`, czy innym polu,
- nie zmieniać po cichu semantyki obecnego `ttft_seconds`, jeśli oznacza final-answer TTFT,
- dodać osobne metryki, np.:
  - `ttft_content_seconds` albo zachować obecne `ttft_seconds` jako first final content token,
  - `ttft_any_token_seconds` jako pierwszy dowolny token tekstowy,
  - `reasoning_chars` / `content_chars`, ewentualnie licznik chunków reasoning/content,
- dodać testy jednostkowe dla streamów z `reasoning_content`, role-only chunków i usage-only chunków,
- sprawdzić wpływ na `run_bench_suite.py` i output schemas.

Akceptacja:

- testy przechodzą lokalnie,
- Kimi debug artifacts są wystarczające do potwierdzenia poprawki,
- non-reasoning modele zachowują dotychczasową semantykę,
- output JSON nie miesza reasoning TTFT z final-answer TTFT bez jawnej nazwy pola.

---

## Priorytet 3 — podsumowanie i utrwalenie sesji

### 3. Spisać podsumowanie sesji — issue #33

Cel: nie trzymać informacji o sesji tylko w rozmowie i commitach.

Sugerowany plik:

```text
docs/plans/2026-05-19-server-session-summary.md
```

Zakres:

- krótko opisać, co było celem sesji,
- lista wykonanych rzeczy,
- linki/nazwy najważniejszych runów i commitów,
- known issues: Kimi TTFT/TPOT, `.gitignore`, dashboard Grafana,
- decyzje operacyjne: OpenWebUI zostaje działające w aktualnym układzie, LiteLLM jest warstwą proxy do benchmarków,
- next steps.

Akceptacja:

- summary pozwala wrócić do projektu po kilku dniach bez przeglądania historii czatu,
- `docs/operations/agent-state.md` nie jest sprzeczny z summary.

---

## Priorytet 4 — observability jako prawdziwy artefakt, nie tylko kontenery

### 4. Zebrać realną listę metryk vLLM / Prometheus

Cel: dashboard ma być oparty o realne nazwy metryk z aktualnego vLLM, nie zgadywane query.

Zakres:

- zapisać małe inventory nazw metryk z:
  - Kimi `/metrics`,
  - DeepSeek `/metrics`,
  - Prometheus `/api/v1/label/__name__/values`,
- commitować raczej `*.metric-names.txt`, nie pełne surowe dumps, jeśli są duże/noisy,
- oznaczyć, które metryki odpowiadają za:
  - target health,
  - requests running/waiting,
  - token throughput,
  - TTFT/TPOT histogramy, jeśli są,
  - KV/GPU cache usage, jeśli są.

Akceptacja:

- istnieje mały plik z inventory realnych metryk,
- wiadomo, z których metryk budować pierwszy dashboard.

### 5. Zbudować pierwszy dashboard Grafana

Cel: minimalny, ale użyteczny dashboard Phase 1.

Minimalne panele:

- Prometheus target health (`up`) per job,
- running/waiting requests,
- token throughput, jeśli metryka istnieje,
- TTFT/TPOT p50/p95, jeśli histogramy istnieją,
- KV/GPU cache usage, jeśli metryka istnieje,
- opcjonalnie panel z model/job labels.

Zakres repo:

- dashboard JSON pod `serving/compose/grafana/provisioning/dashboards/`,
- dashboard provisioning YAML,
- aktualizacja `serving/compose/README.md` z krótką instrukcją uruchomienia i wejścia do Grafany.

Akceptacja:

- `docker compose -f serving/compose/docker-compose.observability.yml up -d` startuje stack,
- Grafana ma Prometheus datasource,
- dashboard pojawia się automatycznie albo jest jasno opisany import,
- dashboard pokazuje sensowne dane przy bench runie.

---

## Priorytet 5 — przygotowanie W1

Plan i metodyka W1 żyją w **issue #37**. Nie pisać pełnego artykułu przed
domknięciem dashboardu (T5) i zebraniem logów z sesji serwerowej (T1, T3, T6, T8).

### Laptop — zadania analityczne W1 (#37)

- **T2** — spisać pełną ścieżkę śledztwa `TTFT: n/a` → fix; dowód gotowy w `results/raw/`.
- **T4** — spisać odrzucone alternatywy dla LiteLLM (dwa porty vLLM wprost, nginx).
- **T5** — analiza "na sucho" metryk z `results/raw/observability`; inwentarz nazw.
- **T8** — po sesji serwerowej: analiza zebranych par A/B; cross-check z metrykami LiteLLM.

Akceptacja: pierwsze cztery wątki (T2, T4, T5 analiza, T7) gotowe na laptopie → można zacząć pisać kręgosłup W1.

---

## Proponowana kolejność na najbliższe dni

### Dzień laptopowy 1

1. Issue #32: `.gitignore` / tracking wyników.
2. Issue #33: session summary.
3. Szybki przegląd agent-state i planów, czy nic nie jest sprzeczne.

### Dzień laptopowy 2

1. Issue #31: analiza Kimi stream debug artifacts.
2. Implementacja parser fix + testy.
3. Lokalna walidacja: `uv run ruff check .`, `uv run pytest -q`.

### Dzień laptopowy 3

1. Inventory metryk Prometheus/vLLM.
2. Pierwszy dashboard JSON/provisioning.
3. Aktualizacja docs dla observability.

### Następna sesja serwerowa

1. Pull najnowszego repo.
2. Zainstalować `rg` (ripgrep) na serwerze: `sudo apt-get install -y ripgrep` —
   żeby laptop i serwer miały te same narzędzia. `rg` jest już na laptopie;
   `check_server_env.py` sprawdza jego obecność (`rg_version`). Szybkie zadanie,
   nie zajmuje slotu GPU.
3. Uruchomić observability stack.
4. Puścić bench suite dla obu modeli pod load.
5. Potwierdzić dashboard live.
6. Zebrać brakujące screenshoty/liczby do W1.

#### Capture pod W1 — szczegóły w #37

Fold do sesji; żadne nie wymaga osobnego slotu GPU. Analiza i pisanie na laptopie.

7. **DEP startup logs (#37 T1).** Próba DEP/DP dla Kimi-K2; przechwycić startup
   log vLLM (engine args, `Loading model weights`, KV profiling, traceback).
   Zapisać do `results/raw/`.
8. **VRAM split logs (#37 T3).** Logi ładowania wag Kimi + DeepSeek; przetestować
   kilka wartości VRAM capu DeepSeek. Zapisać do `results/raw/`.
9. **SC on/off benchmark (#37 T6).** Kimi z Eagle3 i bez: TTFT, TPOT, throughput.
10. **Proxy overhead (#37 T8).** Benchmark A (proxy:4000) vs B (vLLM:8000) metodą
    parami; warmup; zapisać metryki latencji LiteLLM do cross-checku.

---

## Nie robić teraz

- Nie wracać do coding-agent eval — zarchiwizowane, poza Phase 1.
- Nie rozszerzać scope do SGLang/TensorRT-LLM/Kubernetes.
- Nie pisać pełnego W1 przed uporządkowaniem dashboardu i parser issue.
- Nie używać czasu serwera na `.gitignore`, docs-only cleanup ani refaktory niezależne od GPU.
