# Notatka projektowa: lokalny AI support dla zespołu na serwerze 8×H200

## 1. Cel

Przejście z obecnego proof-of-concept lokalnego AI supportu (Ollama na stacji 2×A6000) na środowisko produkcyjne dla zespołu, oparte o vLLM na serwerze 8×H200 NVL.

Po 12 tygodniach środowisko ma obsługiwać:

- pracę Claude Code CLI z pełnym repozytorium / bazą kodu,
- równoczesną pracę kilku użytkowników bez kolejkowania,
- jednoczesne uruchomienie modelu dużego (>500B params) i 1-2 modeli małych,
- powtarzalne benchmarki TTFT, TPOT, throughput, concurrency,
- monitoring w Grafanie,
- workload testowy radiogramów KF jako trudny przypadek oceny modeli.

Projekt ma charakter wdrożeniowo-badawczy: dostarcza zespołowi działające narzędzie i jednocześnie buduje brakującą kompetencję pomiaru wydajności inferencji LLM.

## 2. Stan obecny

| Komponent | Konfiguracja |
|---|---|
| Backend | Ollama |
| Sprzęt | 2× RTX A6000 (96 GB VRAM łącznie) |
| Modele | Llama 3.3 70B Q4, gpt-oss 120B, Qwen 3.5 — kwantyzacja Q4 |
| Tryb pracy | jeden model na raz — przełączenie wymaga zwolnienia VRAM i przeładowania |
| Interfejsy | Open WebUI (chat), Claude Code CLI (uruchamiany przez własny launcher Python) |
| Obserwowalność | brak metryk TTFT / TPOT / throughput / GPU util |

Open WebUI i launcher Claude Code CLI z wyborem modelu działają i potwierdziły sens lokalnego AI supportu. Dalszy rozwój blokuje sprzęt i backend.

## 3. Problemy ograniczające zespół

1. **Brak równoległej obsługi modeli.** Ollama trzyma jeden model w VRAM. Gdy dwóch użytkowników wybiera różne modele, drugi czeka na zwolnienie pamięci i załadowanie nowego — dla modeli klasy 70B-120B przełączenie trwa dziesiątki sekund.
2. **Długie czasy odpowiedzi przy concurrency.** Przy równoczesnej pracy kilku osób czas odpowiedzi przekracza 3 minuty. Ollama nie ma sensownego ciągłego batchowania.
3. **Limit rozmiaru modelu ~117B params.** 96 GB VRAM nie mieści modeli klasy >200B nawet w Q4. Niedostępne pozostają Kimi K2, DeepSeek V3/V4, MiniMax — czyli modele o jakości porównywalnej z GPT/Claude/Gemini, w tym na publicznych benchmarkach kodowych typu SWE-bench.
4. **Małe okno kontekstu.** W praktyce uniemożliwia pracę Claude Code CLI z całym repozytorium / bazą kodu — a to jest główny zamierzony use case dla zespołu programistycznego.
5. **Brak pomiarów.** Nie potrafimy uzasadnić liczbowo "jest wolno". Brakuje TTFT, TPOT, throughputu, kosztu długiego kontekstu, profilu GPU. Każda decyzja o modelu, prompcie i konfiguracji jest oparta na subiektywnej ocenie. To, co mamy dziś, to anegdoty, nie wyniki benchmarku.

## 4. Stan docelowy

| Komponent | Konfiguracja docelowa |
|---|---|
| Backend | vLLM (paged attention, ciągłe batchowanie) |
| Sprzęt | 8× H200 NVL (≈1128 GB HBM3e łącznie) |
| Model duży | jeden z: Kimi K2, DeepSeek V4, MiniMax — modele MoE >500B params, dla zadań złożonych (analiza repo, refaktoryzacja, review) |
| Modele małe | 1-2 równolegle, np. DeepSeek-Lite, Gemma, Qwen — dla zadań krótkich i powtarzalnych |
| Tryb pracy | duży + małe modele dostępne **jednocześnie**, bez przełączania |
| Interfejsy | Open WebUI, Claude Code CLI, plugin VS Code — wspólny endpoint OpenAI-compatible |
| Obserwowalność | Prometheus + Grafana — TTFT, TPOT, throughput, concurrency, GPU util, KV cache |
| Metodyka pomiaru | inspirowana MLPerf Inference i publicznymi benchmarkami LLM serving (LLM Serving-Bench / LLMPerf); trzy tryby (SingleStream-lite / Sequential / Server-lite) z wersjonowaną listą metryk i kontroli |

```text
Użytkownicy
   |- Open WebUI
   |- Claude Code CLI
   |- VS Code plugin
        |
        v
  endpoint OpenAI-compatible (vLLM)
        |
        v
  vLLM: model duży + modele małe
        |
        v
  8× H200 NVL
        |
        v
  Prometheus / Grafana
```

Konkretny podział GPU między model duży a małe (TP, multi-instance vLLM, alokacja KV cache) zostanie ustalony empirycznie w fazach 1-2. To część zakresu projektu — zależy od wybranego modelu dużego i jego rozmiaru w precyzji docelowej.

## 5. Uzasadnienie modernizacji

- **Sprzęt już jest.** Projekt aktywuje istniejące zasoby — brak zewnętrznych kosztów hardware.
- **On-prem jest wymagany.** Zewnętrzne API nie wchodzą w grę; lokalna inferencja to jedyna opcja.
- **Jakość modeli.** Modele >500B params (Kimi K2, DeepSeek V4, MiniMax) zbliżają się jakościowo do GPT/Claude/Gemini. Bez H200 są dla nas niedostępne.
- **Praca z repo.** Większe okno kontekstu odblokowuje pełne wykorzystanie Claude Code CLI w codziennej pracy programistycznej — dziś główny blocker.
- **Concurrency.** vLLM eliminuje 3-minutowe odpowiedzi przy kilku użytkownikach.
- **Brak przełączania modeli.** Duży i małe modele równolegle, bez kolejki "czekam aż się załaduje".
- **Kompetencja pomiarowa.** Projekt buduje umiejętność, której nie mamy: jak mierzyć i optymalizować inferencję LLM. Metodyka jest spisywana wewnętrznie i nie wymyślana ad-hoc w trakcie projektu. Bez tego każda kolejna decyzja infrastrukturalna pozostanie intuicyjna.

### Inspiracja metodyczna

Benchmarki w tym projekcie nie są pełną implementacją MLPerf ani LLM Serving-Bench. Metodyka jest **inspirowana** tymi rozwiązaniami i przejmuje z nich konkretne elementy dyscypliny pomiarowej.

Z **MLPerf Inference** bierzemy:

- jasno zdefiniowane scenariusze benchmarku,
- reprodukowalne kontrole workloadu i systemu (model, dtype, wersja silnika, max_model_len, decoding, warmup/measured runs),
- rozdzielenie latency i throughputu jako osobnych metryk,
- porównywalność wyników między modelami i konfiguracjami.

Z benchmarków **LLM serving** typu LLM Serving-Bench / LLMPerf bierzemy:

- realistyczny model arrival process (Poisson, target QPS) zamiast "wyślij wszystko naraz",
- pomiar TTFT i TPOT jako osobnych metryk, wymóg streamingu,
- p95/p99 tail latency pod obciążeniem,
- koncepcję pomiarów sterowanych concurrency (1 / 4 / 8 / 16) zamiast jednej liczby.

Świadomie poza zakresem zostają: pełna zgodność MLPerf, MLPerf LoadGen, oficjalne pakiety submission, large-model compliance runs. Zakres jest węższy, dyscyplina ta sama.

## 6. Workload testowy: radiogramy KF

Radiogramy KF są wykorzystywane jako trudny workload domenowy do oceny modeli i promptów. Cechy istotne:

- nietypowy, często przestawny szyk zdania,
- relacja nadawca-odbiorca odwrotna względem typowych zadań językowych,
- skrótowa, kontekstowa struktura komunikatów.

W ramach projektu zostanie sprawdzona koncepcja dwóch ścieżek:

- **Szybka ścieżka** — reguły / parsery dla znanych struktur. Niski koszt, deterministyczna, bez LLM.
- **Wolna ścieżka** — LLM analizuje przypadki nowe lub niejednoznaczne; wynik po weryfikacji człowieka może zasilić szybką ścieżkę jako nowa reguła.

Cel: koszt LLM ponoszony tylko dla nowych przypadków, powtarzalne przypadki obsługiwane deterministycznie.

## 7. Plan 12-tygodniowy

### Faza 1 (tyg. 1-3) — vLLM baseline

- vLLM uruchomione na 8×H200, pierwszy duży model działa,
- endpoint OpenAI-compatible wystawiony,
- pierwsza integracja z Open WebUI i Claude Code CLI,
- uruchomienie trybów SingleStream-lite i Sequential z pełnym zestawem kontroli (git commit, model revision, dtype, wersja vLLM, max_model_len, parametry dekodowania, workload label, warmup/measured runs),
- pierwsze pomiary TTFT, TPOT, throughput,
- minimalny dashboard Prometheus / Grafana.

### Faza 2 (tyg. 4-7) — integracje i wybór modeli

- równoległe uruchomienie modelu dużego + 1-2 małych,
- wybór finalnego modelu dużego (porównanie kandydatów: Kimi K2 / DeepSeek V4 / MiniMax),
- integracja z VS Code,
- benchmark harness (powtarzalne pomiary jednym poleceniem),
- uruchomienie trybu Offline-lite throughput (stały zestaw promptów, kontrolowany concurrency),
- pierwsza wersja workloadu radiogramów KF z wersjonowanymi promptami,
- pierwsze porównanie modeli na radiogramach.

### Faza 3 (tyg. 8-10) — profilowanie i analiza

- uruchomienie trybu Server-lite arrival (Poisson, target QPS, p95/p99, zachowanie timeoutów),
- pomiary przy concurrency 1 / 4 / 8 / 16,
- analiza KV cache i pamięci GPU pod realnym obciążeniem,
- wpływ długości promptu i promptów reasoningowych na TTFT / TPOT,
- porównanie kosztu szybkiej i wolnej ścieżki radiogramów,
- pełny dashboard Grafana.

### Faza 4 (tyg. 11-12) — stabilizacja i raport

- stabilizacja konfiguracji vLLM,
- instrukcja korzystania dla zespołu,
- raport końcowy: benchmarki, wnioski z radiogramów KF, rekomendacja dalszych prac.

## 8. Kryteria sukcesu

Po 12 tygodniach:

1. vLLM działa stabilnie na 8×H200.
2. Model duży (>500B params) i co najmniej jeden mały model dostępne **jednocześnie**, bez przełączania.
3. Open WebUI, Claude Code CLI i plugin VS Code korzystają z tego samego lokalnego endpointu.
4. Czas odpowiedzi dla typowego zapytania programistycznego nie przekracza minuty przy 4 równoległych użytkownikach (próg do potwierdzenia liczbowo w fazie 1 — dziś nie znamy baseline'u).
5. Dostępne metryki TTFT, TPOT, throughput, concurrency, GPU util w Grafanie.
6. Powtarzalny benchmark harness uruchamiany jednym poleceniem; działają trzy tryby benchmarku: SingleStream-lite, Sequential, Server-lite.
7. Wszystkie raporty benchmarków zawierają komplet kontroli (git commit, model revision, dtype, wersja vLLM, max_model_len, parametry dekodowania, workload label, warmup/measured runs, concurrency) zgodnie z wewnętrzną specyfikacją metodyki.
8. Workload radiogramów KF z wersjonowanymi promptami i pierwszym porównaniem modeli.
9. Sprawdzona koncepcja szybkiej i wolnej ścieżki.
10. Raport końcowy z liczbowymi rekomendacjami doboru modelu i konfiguracji.

## 9. Nakład

2 dni tygodniowo × 12 tygodni.

Czas obejmuje: konfigurację vLLM, integracje, benchmark harness, testy modeli, analizę wyników, dashboardy, dokumentację i raport końcowy.

## 10. Wartość dla zespołu

- Praca z całymi repozytoriami przez Claude Code CLI — odblokowuje główny use case.
- Brak kolejek przy równoczesnej pracy kilku osób.
- Dostęp do modeli klasy GPT/Claude/Gemini lokalnie, bez zewnętrznego API.
- Kompetencja pomiaru wydajności inferencji LLM — podstawa pod kolejne decyzje infrastrukturalne (dobór modelu, planowanie sprzętu, optymalizacja promptów).
