# Server work plan — 2026-05-11

Roboczy plan pracy na serwerze GPU dla `nanoserve-mini`.

Cel dnia: sprawdzić praktyczną użyteczność mniejszego modelu programistycznego względem Kimi-K2.6, przygotować go pod lokalny coding-agent workflow, zebrać metryki systemowe i wykonać pierwsze benchmarki w nomenklaturze MLPerf-inspired lite.

Ten plan jest operacyjny. Nie jest finalnym benchmark write-upem.

---

## Założenia

- Główny serwer: Ubuntu 24.04, 8x H200 NVL.
- Aktualny duży model: `moonshotai/Kimi-K2.6`, działający przez vLLM z TP=8.
- Nowy kandydat na mniejszy, ale użyteczny model: model programistyczny / agentic coding model, prawdopodobnie TP=4.
- Claude Code CLI jest już zainstalowany; najpierw sprawdzamy, czy da się go skierować do lokalnego vLLM.
- Jeśli Claude Code CLI nie działa z lokalnym vLLM bez nadmiernej integracji/proxy, fallbackiem jest instalacja i użycie OpenCode.
- Wyniki zapisujemy w `results/runs/<run_id>/`.
- GitHub pozostaje single source of truth dla kodu, konfiguracji, małych wyników i summary.
- Nie commitujemy wag modeli, cache Hugging Face, dużych logów, dużych trace'ów ani sekretów.

---

## Modele do sprawdzenia

### Primary candidate

- `MiniMaxAI/MiniMax-M2.7`
- Uzasadnienie: najnowszy MiniMax M2, model nastawiony na coding, tool use, agent workflows i long-context reasoning.
- Zakładany tryb: TP=4.
- Recipe: <https://recipes.vllm.ai/MiniMaxAI/MiniMax-M2.7>

### Research / high-upside candidate

- `poolside/Laguna-XS.2`
- Uzasadnienie: model opisany jako agentic coding MoE, potencjalnie bardzo pasuje do Claude Code-like workflows.
- Ryzyko: może wymagać nightly albo pinned Docker image.
- Recipe: <https://recipes.vllm.ai/poolside/Laguna-XS.2>

### Safe fallback candidate

- `Qwen/Qwen3.6-35B-A3B`
- Uzasadnienie: mniejszy MoE, duży kontekst, prawdopodobnie łatwiejszy operacyjnie niż większe modele.
- Recipe: <https://recipes.vllm.ai/Qwen/Qwen3.6-35B-A3B>

### Stretch candidate

- `deepseek-ai/DeepSeek-V4-Flash`
- Uzasadnienie: ciekawy model reasoning/coding z rodziny DeepSeek.
- Ryzyko: bardziej złożona konfiguracja niż prosty TP=4; raczej nie jako pierwszy model dnia.
- Recipe: <https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash>

---

## Run directory

Na początku sesji tworzymy jeden katalog runu:

```text
results/runs/2026-05-11_minimax-m2.7_coding_eval_dualmodel/
```

Docelowa struktura:

```text
results/runs/2026-05-11_minimax-m2.7_coding_eval_dualmodel/
  config.json
  server_commands.md
  environment_snapshot.json
  gpu_metrics/
    before_download.csv
    after_minimax_start.csv
    after_coding_agent_eval.csv
    after_dualmodel_start.csv
    after_benchmarks.csv
  vllm_metrics/
    minimax_after_start.prom
    minimax_after_coding_agent_eval.prom
    kimi_after_dualmodel_start.prom
    minimax_after_dualmodel_start.prom
    kimi_after_benchmarks.prom
    minimax_after_benchmarks.prom
  coding_agent_eval/
    agent_selection.md
    tasks_summary.md
    results.jsonl
    transcripts/
  singlestream_lite_correctness/
  singlestream_lite_latency/
  singlestream_lite_repeated/
  summary.md
```

---

# Część A — model programistyczny + coding agent CLI

Cel części A: odpowiedzieć, czy `MiniMaxAI/MiniMax-M2.7` realnie nadaje się do pracy programistycznej przez lokalny coding-agent workflow. Najpierw sprawdzamy Claude Code CLI, bo jest już zainstalowany. Jeśli integracja Claude Code CLI z lokalnym vLLM nie działa albo wymaga zbyt dużego proxy/gateway work, instalujemy i testujemy OpenCode.

## A1. Przygotowanie sesji

- [ ] `git pull` na serwerze.
- [ ] Sprawdzić `git status`.
- [ ] Utworzyć katalog runu.
- [ ] Zapisać aktualny commit do `config.json` albo `git_commit.txt`.
- [ ] Zebrać początkowe GPU metrics.
- [ ] Zebrać aktualny stan kontenerów Docker.
- [ ] Sprawdzić dostępny HF cache / Docker volume.

## A2. Pobranie modeli

- [ ] Pobrać `MiniMaxAI/MiniMax-M2.7` do stałego cache.
- [ ] Zapisać czas pobierania i ewentualne błędy.
- [ ] Zapisać revision / commit modelu, jeśli dostępne.
- [ ] Opcjonalnie pobrać `poolside/Laguna-XS.2` albo `Qwen/Qwen3.6-35B-A3B`.
- [ ] Nie commitować cache ani wag.

## A3. Uruchomienie MiniMax-M2.7 przez vLLM

- [ ] Uruchomić `MiniMaxAI/MiniMax-M2.7` zgodnie z vLLM recipe.
- [ ] Preferowany tryb: TP=4, jeśli recipe i zasoby to potwierdzają.
- [ ] Zapisać dokładną komendę launch w `server_commands.md`.
- [ ] Zapisać parametry:
  - Docker image,
  - vLLM version,
  - model id,
  - port,
  - GPU mapping,
  - tensor parallel size,
  - max model len,
  - gpu memory utilization,
  - tool-call parser,
  - reasoning parser,
  - compilation config,
  - inne niestandardowe flagi.
- [ ] Zebrać GPU metrics po starcie.
- [ ] Zebrać vLLM `/metrics` po starcie.

## A4. Coding agent CLI: Claude Code first, OpenCode fallback

Najpierw sprawdzamy Claude Code CLI, bo jest już zainstalowany. OpenCode jest fallbackiem, jeśli Claude Code nie potrafi łatwo pracować z lokalnym vLLM albo wymaga zbyt dużego Anthropic-compatible gateway/proxy.

### A4.1. Claude Code CLI — check z lokalnym vLLM

- [ ] Sprawdzić aktualną instalację Claude Code CLI i wersję.
- [ ] Sprawdzić, czy Claude Code CLI można skonfigurować na lokalny endpoint vLLM / OpenAI-compatible endpoint bez dodatkowego dużego proxy.
- [ ] Spróbować skierować Claude Code CLI do `MiniMaxAI/MiniMax-M2.7` serwowanego przez vLLM.
- [ ] Wykonać minimalny test w roboczym repo testowym:
  - prosty prompt,
  - mała edycja pliku,
  - opcjonalnie uruchomienie testu/komendy.
- [ ] Potwierdzić w logach albo obserwacji:
  - endpoint,
  - model id,
  - format requestu,
  - format odpowiedzi,
  - czy tool calls / command execution nie psują przepływu.
- [ ] Zapisać wynik checku do:

```text
results/runs/<run_id>/coding_agent_eval/agent_selection.md
```

### A4.2. Decyzja po checku Claude Code CLI

- [ ] Jeśli Claude Code CLI działa z lokalnym vLLM: użyć Claude Code CLI jako pierwszego agenta do testów programistycznych.
- [ ] Jeśli Claude Code CLI nie działa z lokalnym vLLM albo blocker jest zbyt duży: zapisać blocker i przejść do OpenCode.
- [ ] Nie poświęcać dużej części dnia na budowanie gateway/proxy, jeśli OpenCode pozwala szybciej przejść do oceny modelu.

### A4.3. OpenCode fallback

- [ ] Jeśli Claude Code CLI nie działa, zainstalować OpenCode.
- [ ] Skonfigurować OpenCode do lokalnego vLLM / OpenAI-compatible endpointu.
- [ ] Skierować OpenCode do `MiniMaxAI/MiniMax-M2.7`.
- [ ] Wykonać ten sam minimalny test w roboczym repo testowym.
- [ ] Zapisać:
  - wersję OpenCode,
  - konfigurację bez sekretów,
  - endpoint,
  - model id,
  - wynik minimalnego testu,
  - ewentualne ograniczenia.

## A5. Test weryfikujący model w coding agent CLI

Przygotować cztery syntetyczne zadania programistyczne w osobnym roboczym repo testowym. Zadania nie mają bazować na `nanoserve-mini`. Każde zadanie powinno mieć kilka etapów o rosnącym poziomie trudności. Wynik pracy per model będzie porównywany przez commit końcowy z roboczego repo.

Docelowy katalog z definicjami zadań:

```text
benchmarks/coding-agent-tasks/
  01_powershell_environment_and_backup/
  02_python_cli_and_streaming_client/
  03_cpp_buffer_and_hotpath/
  04_csharp_allocation_aware_refactor/
```

Każde zadanie powinno mieć:

- [ ] otwartą treść promptu / README dla modelu,
- [ ] ukryte testy i ukrytą ocenę,
- [ ] pliki wejściowe,
- [ ] komendę testującą dla jawnych testów,
- [ ] kryteria zaliczenia,
- [ ] limit czasu,
- [ ] informację, że model może uruchamiać testy i komendy,
- [ ] kilka etapów o rosnącym poziomie trudności.

### Zadanie 1 — PowerShell, poziom A

- [ ] Skrypt sprawdzający status środowiska Docker/vLLM/GPU.
- [ ] Walidacja środowiska.
- [ ] Backup/export małych wyników.
- [ ] Kryterium zaliczenia: działa dla happy path i błędnych parametrów, poprawnie raportuje status.

### Zadanie 2 — Python, poziom B

- [ ] CLI parser.
- [ ] Streaming OpenAI-compatible client.
- [ ] Raportowanie wyników JSON/JSONL.
- [ ] Kryterium zaliczenia: poprawna obsługa argumentów, streaming chunks, timeout/error handling i zapis wyników.

### Zadanie 3 — C++, poziom B

- [ ] Bug w buforze / allocator-like logic.
- [ ] Performance hot path.
- [ ] Kompilacja + testy.
- [ ] Kryterium zaliczenia: poprawność, brak oczywistych błędów pamięci, lepszy albo niegorszy hot path.

### Zadanie 4 — C#, poziom C

- [ ] Allocation-aware refactor.
- [ ] Performance/memory allocation problem.
- [ ] Testy i benchmark-like checks.
- [ ] Kryterium zaliczenia: testy przechodzą, public API zachowane, alokacje albo czas wykonania poprawione bez nieczytelnego kodu.

## A6. Metryki dla coding agent eval

Dla każdego zadania zapisać:

- [ ] agent (`claude_code` albo `opencode`),
- [ ] model,
- [ ] start timestamp,
- [ ] end timestamp,
- [ ] wall-clock time,
- [ ] pass/fail,
- [ ] liczba requestów do modelu, jeśli dostępna,
- [ ] input tokens, jeśli dostępne,
- [ ] output tokens, jeśli dostępne,
- [ ] liczba zmienionych plików,
- [ ] liczba uruchomień testów,
- [ ] czy model sam naprawił błąd po failed test,
- [ ] E2E latency dla requestów, jeśli dostępna,
- [ ] GPU metrics przed/po,
- [ ] vLLM metrics przed/po,
- [ ] skrócony transcript albo ścieżka do transcriptu,
- [ ] commit hash z roboczego repo po wykonaniu zadania.

Wyniki zapisać do:

```text
results/runs/<run_id>/coding_agent_eval/results.jsonl
results/runs/<run_id>/coding_agent_eval/tasks_summary.md
```

---

# Część B — dwa modele równolegle + benchmarki MLPerf-inspired lite

Cel części B: uruchomić dwa modele równolegle i wykonać minimalny zestaw benchmarków latency/correctness zgodny z naszą metodologią MLPerf-inspired lite.

## B1. Nazewnictwo benchmarków

Nie używamy nazwy „oficjalny MLPerf”. Używamy nazw roboczych:

| Nazwa robocza | Skrypt | Znaczenie |
|---|---|---|
| `SingleStream-lite correctness` | `scripts/request_once.py` | Jeden non-streaming request; sanity/correctness gate, nie benchmark wydajnościowy. |
| `SingleStream-lite latency` | `scripts/measure_ttft_once.py` | Jeden streaming request; TTFT + E2E. |
| `SingleStream-lite repeated` | `scripts/run_sequential_benchmark.py` | Powtarzany streaming request z `concurrency=1`; p50/p95 TTFT/E2E. |
| `Offline-lite throughput` | future / `vllm bench serve` | Workload wysyłany możliwie szybko przy kontrolowanej concurrency. |
| `Server-lite QPS` | future / `vllm bench serve` | Workload z finite request rate / target QPS. |

Wyniki powinny zawierać pola:

```json
{
  "methodology": "mlperf_inspired_lite",
  "benchmark_mode": "singlestream_lite_latency"
}
```

Jeśli obecne skrypty jeszcze tego nie zapisują, dodać to jako małą poprawkę.

## B2. Sprawdzenie zgodności obecnych skryptów z metodologią

- [ ] `request_once.py`: dodać zapis JSON do `--output`, jeśli nadal go nie ma.
- [ ] `request_once.py`: oznaczyć wynik jako `singlestream_lite_correctness`.
- [ ] `measure_ttft_once.py`: sprawdzić, czy zapisuje JSON do wybranego katalogu runu.
- [ ] `measure_ttft_once.py`: dodać `methodology` i `benchmark_mode`, jeśli brakuje.
- [ ] `run_sequential_benchmark.py`: sprawdzić JSONL + summary path.
- [ ] `run_sequential_benchmark.py`: dodać `methodology` i `benchmark_mode`, jeśli brakuje.
- [ ] Upewnić się, że każdy wynik ma controls: model, base URL, decoding params, workload, warmup, measured runs, vLLM version, GPU model.

## B3. Uruchomienie dwóch modeli równolegle

Preferowany wariant:

- Model A: `moonshotai/Kimi-K2.6`.
- Model B: `MiniMaxAI/MiniMax-M2.7`.

Zadania:

- [ ] Uruchomić Kimi-K2.6 albo potwierdzić, że działa.
- [ ] Uruchomić MiniMax-M2.7 jako drugą instancję.
- [ ] Ustalić porty, np. Kimi `8000`, MiniMax `8001`.
- [ ] Zapisać launch commands obu instancji.
- [ ] Zapisać GPU allocation obu instancji.
- [ ] Zebrać GPU metrics po starcie dual-model.
- [ ] Zebrać vLLM `/metrics` z obu instancji.
- [ ] Jeśli dual-model nie działa pamięciowo, zapisać failure note i aktualny bottleneck.

## B4. SingleStream-lite correctness

Dla każdego modelu:

- [ ] Uruchomić `scripts/request_once.py`.
- [ ] Zapisać wynik do:

```text
results/runs/<run_id>/singlestream_lite_correctness/kimi.json
results/runs/<run_id>/singlestream_lite_correctness/minimax_m2_7.json
```

- [ ] Zapisać output text i usage.
- [ ] Zapisać E2E latency, jeśli `request_once.py` zostanie rozszerzony.

## B5. SingleStream-lite latency

Dla każdego modelu:

- [ ] Uruchomić `scripts/measure_ttft_once.py`.
- [ ] Zapisać wynik do:

```text
results/runs/<run_id>/singlestream_lite_latency/kimi_ttft.json
results/runs/<run_id>/singlestream_lite_latency/minimax_m2_7_ttft.json
```

- [ ] Zebrać TTFT.
- [ ] Zebrać E2E latency.
- [ ] Zapisać prompt, max tokens i decoding params.

## B6. SingleStream-lite repeated

Dla każdego modelu:

- [ ] Uruchomić `scripts/run_sequential_benchmark.py`.
- [ ] Parametry początkowe:
  - warmup: 1,
  - measured runs: 5 albo 10,
  - concurrency: 1,
  - temperature: 0,
  - max tokens: 64 albo 128,
  - jeden stały prompt.
- [ ] Zapisać JSONL + summary:

```text
results/runs/<run_id>/singlestream_lite_repeated/kimi.jsonl
results/runs/<run_id>/singlestream_lite_repeated/kimi_summary.json
results/runs/<run_id>/singlestream_lite_repeated/minimax_m2_7.jsonl
results/runs/<run_id>/singlestream_lite_repeated/minimax_m2_7_summary.json
```

## B7. Metryki po benchmarkach

- [ ] Zebrać GPU metrics po benchmarkach.
- [ ] Zebrać vLLM `/metrics` z Kimi.
- [ ] Zebrać vLLM `/metrics` z MiniMax.
- [ ] Zapisać `docker stats --no-stream`.
- [ ] Zapisać krótką interpretację:
  - VRAM before,
  - VRAM after Kimi,
  - VRAM after MiniMax,
  - VRAM after dual-model,
  - VRAM after benchmark,
  - czy widać interferencję.

## B8. Opcjonalnie: vLLM bench serve

Jeśli powyższe działa stabilnie:

- [ ] Odpalić `vllm bench serve` jako `Offline-lite throughput`.
- [ ] Użyć `--save-result`, `--save-detailed`, `--result-dir`, `--metadata`.
- [ ] Ustawić kontrolowany `max_concurrency`.
- [ ] Na ten dzień nie robić jeszcze pełnego `Server-lite QPS`, chyba że zostanie dużo czasu.

---

# Kryteria zakończenia dnia

Dzień uznajemy za udany, jeśli mamy co najmniej:

- [ ] pobrany `MiniMaxAI/MiniMax-M2.7`,
- [ ] uruchomiony MiniMax-M2.7 przez vLLM,
- [ ] zapisaną komendę launch,
- [ ] zebrane GPU metrics i vLLM metrics,
- [ ] sprawdzone, czy Claude Code CLI działa z lokalnym vLLM,
- [ ] jeśli Claude Code CLI nie działa: zainstalowany albo przynajmniej rozpoczęty fallback OpenCode,
- [ ] przygotowane 4 zadania programistyczne,
- [ ] wykonany przynajmniej jeden test coding agent CLI,
- [ ] próba dual-model Kimi + MiniMax,
- [ ] wyniki `SingleStream-lite correctness`, `SingleStream-lite latency` i `SingleStream-lite repeated` dla co najmniej jednego modelu,
- [ ] summary w `results/runs/<run_id>/summary.md`,
- [ ] commit + push.

---

# Kryteria nieudanej, ale wartościowej sesji

Sesja nadal jest wartościowa, jeśli:

- [ ] MiniMax-M2.7 nie uruchomił się, ale mamy failure note z konkretnym błędem.
- [ ] Claude Code CLI nie zadziałał, ale mamy jasny blocker integracyjny i decyzję o fallbacku do OpenCode.
- [ ] OpenCode też nie zadziałał, ale mamy oddzielny blocker instalacyjny/konfiguracyjny.
- [ ] Dual-model setup nie zadziałał, ale mamy metryki VRAM i powód.
- [ ] Benchmark nie przeszedł, ale skrypt zapisał błąd w JSON/JSONL.

Failure write-up jest poprawnym artefaktem projektu, jeśli zawiera warunki, błąd, hipotezę i następny krok.

---

# Commit plan

Na koniec sesji:

- [ ] Upewnić się, że nie ma sekretów ani dużych plików.
- [ ] Dodać tylko kod, docs, konfiguracje i małe wyniki.
- [ ] Uruchomić, jeśli czas pozwoli:

```bash
uv run ruff check .
uv run pytest
```

- [ ] Commit:

```bash
git add scripts tests infra docs benchmarks results/runs/<run_id>
git commit -m "bench: record minimax coding eval and dual-model baseline"
git push
```

- [ ] Zaktualizować `docs/agent-state.md`.
