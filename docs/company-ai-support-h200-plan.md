# Notatka projektowa: lokalny AI support dla zespołu na serwerze 8×H200

## 1. Cel

Przejście z obecnego proof-of-concept lokalnego AI supportu (Ollama na stacji 2×A6000) na środowisko produkcyjne dla zespołu, oparte o vLLM na serwerze 8×H200 NVL.

Po 12 tygodniach środowisko ma obsługiwać:

- pracę Claude Code CLI z pełnym repozytorium / bazą kodu,
- równoczesną pracę kilku użytkowników bez kolejkowania,
- jednoczesne uruchomienie modelu dużego (>500B params) i 1-2 modeli małych,
- jeden wspólny endpoint OpenAI-compatible przed wieloma instancjami vLLM,
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
3. **Limit rozmiaru modelu ~117B params.** 96 GB VRAM nie mieści modeli klasy >200B nawet w Q4. Niedostępne pozostają Kimi K2.6, DeepSeek V3/V4, MiniMax — czyli modele o jakości porównywalnej z GPT/Claude/Gemini, w tym na publicznych benchmarkach kodowych typu SWE-bench.
4. **Małe okno kontekstu.** W praktyce uniemożliwia pracę Claude Code CLI z całym repozytorium / bazą kodu — a to jest główny zamierzony use case dla zespołu programistycznego.
5. **Brak pomiarów.** Nie potrafimy uzasadnić liczbowo "jest wolno". Brakuje TTFT, TPOT, throughputu, kosztu długiego kontekstu, profilu GPU. Każda decyzja o modelu, prompcie i konfiguracji jest oparta na subiektywnej ocenie. To, co mamy dziś, to anegdoty, nie wyniki benchmarku.

## 4. Stan docelowy

| Komponent | Konfiguracja docelowa |
|---|---|
| Backend | vLLM (paged attention, ciągłe batchowanie) |
| Sprzęt | 8× H200 NVL (≈1128 GB HBM3e łącznie) |
| Model duży | jeden z: Kimi K2.6, DeepSeek V4, MiniMax — modele MoE >500B params, dla zadań złożonych (analiza repo, refaktoryzacja, review) |
| Modele małe | 1-2 równolegle, np. DeepSeek-Lite, Gemma, Qwen — dla zadań krótkich i powtarzalnych |
| Proxy / routing | LiteLLM Proxy jako jeden endpoint OpenAI-compatible przed wieloma instancjami vLLM; routing manualny po polu `model`, klucze API per użytkownik, logi |
| Tryb pracy | duży + małe modele dostępne **jednocześnie**, bez przełączania; wybór modelu przez proxy zamiast przeładowywania backendu |
| Interfejsy | Open WebUI, Claude Code CLI, plugin VS Code — wspólny endpoint OpenAI-compatible wystawiony przez proxy |
| Obserwowalność | Prometheus + Grafana — TTFT, TPOT, throughput, concurrency, GPU util, KV cache |
| Metodyka pomiaru | inspirowana MLPerf Inference i publicznymi benchmarkami LLM serving (LLM Serving-Bench / LLMPerf); trzy tryby (SingleStream-lite / Sequential / Server-lite) z wersjonowaną listą metryk i kontroli |

```text
Użytkownicy
   |- Open WebUI
   |- Claude Code CLI
   |- VS Code plugin
        |
        v
  LiteLLM Proxy
  jeden endpoint OpenAI-compatible
  routing po polu model, klucze, logi
        |
        v
  instancje vLLM:
  - model duży
  - modele małe
        |
        v
  8× H200 NVL
        |
        v
  Prometheus / Grafana
```

Konkretny podział GPU między model duży a małe (TP, multi-instance vLLM, alokacja KV cache) zostanie ustalony empirycznie w fazach 1-2. To część zakresu projektu — zależy od wybranego modelu dużego i jego rozmiaru w precyzji docelowej.

LiteLLM Proxy pełni rolę cienkiej warstwy operacyjnej przed vLLM: daje jeden
stabilny endpoint dla narzędzi użytkownika, pozwala routować zapytania do wielu
instancji vLLM po polu `model`, rozdzielać klucze API per użytkownik oraz zbierać
logi użycia. Dzięki temu Open WebUI, Claude Code CLI i plugin VS Code nie muszą
znać szczegółów rozmieszczenia modeli na GPU.

W późniejszej fazie projekt może porównać routing manualny z automatyczną
klasyfikacją zapytań przez vLLM Semantic Router. To pozostaje eksperymentem
pomiarowym: należy sprawdzić jakość klasyfikacji, narzut latency i realną
oszczędność kosztu obliczeniowego.

Istotnym wariantem do sprawdzenia jest tryb shared-node: dwie osobne instancje
vLLM widzą ten sam serwer 8×H200. Przykładowo Kimi K2.6 działa jako model premium
na `tensor_parallel_size=8`, a drugi, szybszy model działa jako osobny endpoint
vLLM na tych samych GPU. Nie jest to twardy podział GPU na dwie niezależne pule,
tylko eksperyment współdzielenia pamięci, compute i przepustowości HBM. Jego
celem jest sprawdzenie, czy mały/szybszy model zachowuje akceptowalne p95/p99
latency, gdy model premium wykonuje długi prefill albo decode.

## 5. Uzasadnienie modernizacji

- **Sprzęt już jest.** Projekt aktywuje istniejące zasoby — brak zewnętrznych kosztów hardware.
- **On-prem jest wymagany.** Zewnętrzne API nie wchodzą w grę; lokalna inferencja to jedyna opcja.
- **Jakość modeli.** Modele >500B params (Kimi K2.6, DeepSeek V4, MiniMax) zbliżają się jakościowo do GPT/Claude/Gemini. Bez H200 są dla nas niedostępne.
- **Praca z repo.** Większe okno kontekstu odblokowuje pełne wykorzystanie Claude Code CLI w codziennej pracy programistycznej — dziś główny blocker.
- **Concurrency.** vLLM eliminuje 3-minutowe odpowiedzi przy kilku użytkownikach.
- **Brak przełączania modeli.** Duży i małe modele równolegle, bez kolejki "czekam aż się załaduje".
- **Routing po koszcie.** Proxy pozwala kierować krótkie i powtarzalne zadania do
  mniejszych modeli, a duży model zostawić dla analizy repo, refaktoryzacji i
  trudnych zadań reasoningowych. To jest warunek praktycznego obniżenia kosztu
  obliczeniowego bez pogarszania doświadczenia użytkownika.
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

## 6. Przykładowe wyliczenia pojemności i scenariusze użycia

Poniższe wyliczenia mają charakter planistyczny. Ich celem nie jest obiecanie
konkretnej wydajności przed pomiarem, ale pokazanie, dlaczego serwer 8×H200 jest
właściwym zasobem do pracy z dużym kontekstem, dużymi modelami MoE oraz
concurrency zespołowym.

Serwer 8×H200 NVL udostępnia około:

- 8 × 141 GB HBM3e = 1128 GB pamięci GPU brutto,
- realnie mniej po uwzględnieniu runtime, vLLM, buforów, CUDA graphs, KV cache i
  rezerwy operacyjnej.

Dla modeli klasy DeepSeek V4 istotne jest to, że checkpoint nie jest prostym
FP16/BF16 ani czystym FP8. Według vLLM Recipes modele DeepSeek V4 używają
mieszanego formatu FP4+FP8: eksperci MoE są w FP4, a pozostałe komponenty
(attention, norm, router) w FP8.

### 6.1 Przykład: DeepSeek-V4-Pro

DeepSeek-V4-Pro to model MoE klasy 1.6T parametrów łącznie / 49B aktywnych
parametrów na token.

Według vLLM Recipes:

- rekomendowany deployment na H200 to 8×GPU,
- używany jest data parallelism + expert parallelism,
- na H200 kontekst jest ograniczany do około 800k tokenów, żeby zostawić miejsce
  na KV cache i narzuty runtime,
- mieszany checkpoint ma rząd wielkości około 960 GB.

To oznacza, że DeepSeek-V4-Pro jest kandydatem na model premium do najtrudniejszych
zadań:

- analiza dużej części repozytorium,
- review z szerokim kontekstem,
- refaktoryzacja wielu powiązanych modułów,
- zadania reasoningowe i agentowe,
- praca z długą dokumentacją techniczną.

Nie jest to model, który należy zakładać jako domyślny dla każdego krótkiego
zapytania. Celem projektu jest zmierzenie, dla jakich zadań jego koszt
obliczeniowy jest uzasadniony.

### 6.2 Przykład: DeepSeek-V4-Flash

DeepSeek-V4-Flash to mniejszy model MoE klasy 284B parametrów łącznie / 13B
aktywnych parametrów na token.

Według vLLM Recipes:

- model obsługuje kontekst do 1M tokenów,
- rekomendowany deployment na H200 może używać 4 z 8 GPU per replica,
- druga połowa serwera może zostać wykorzystana na dodatkową replikę,
  prefill/decode disaggregation, tuning throughput-vs-latency albo mniejsze
  modele.

To czyni DeepSeek-V4-Flash dobrym kandydatem na model codzienny dla zespołu:

- typowe pytania programistyczne,
- analiza PR,
- praca z modułem kodu,
- debugowanie,
- generowanie testów,
- krótsze zadania w Claude Code CLI,
- workloady wymagające większego kontekstu, ale niekoniecznie największego
  modelu.

### 6.3 Koszt KV cache

Długi kontekst nie zużywa pamięci tylko przez wagę modelu. Każde aktywne
zapytanie wymaga KV cache. Koszt KV cache rośnie wraz z:

- długością kontekstu,
- liczbą równoległych użytkowników,
- liczbą generowanych tokenów,
- konfiguracją modelu i attention.

Dla DeepSeek V4 vLLM opisuje silnie skompresowany mechanizm attention. Według
bloga vLLM, przy 1M tokenów DeepSeek V4 ma około 9.62 GiB KV cache na sekwencję
przy BF16 KV cache, a praktyczne użycie FP4/FP8 cache może zmniejszać ten koszt
jeszcze około dwukrotnie.

Orientacyjne przeliczenie:

| Kontekst | KV cache / request, BF16 | KV cache / request, FP4/FP8 szacunkowo | 4 równoległe requesty | 8 równoległych requestów |
|---:|---:|---:|---:|---:|
| 128k tokenów | ~1.2 GiB | ~0.6 GiB | ~2.4 GiB | ~4.8 GiB |
| 384k tokenów | ~3.5 GiB | ~1.8 GiB | ~7.2 GiB | ~14.4 GiB |
| 800k tokenów | ~7.3 GiB | ~3.7 GiB | ~14.8 GiB | ~29.6 GiB |
| 1M tokenów | ~9.6 GiB | ~4.8 GiB | ~19.2 GiB | ~38.4 GiB |

Wniosek: dla DeepSeek V4 sam KV cache nie powinien być głównym blockerem przy
concurrency 4-8. Bardziej istotne do zmierzenia będą:

- czas prefill dla 128k / 384k / 800k tokenów,
- TTFT przy długim kontekście,
- TPOT przy wielu równoległych użytkownikach,
- stabilność vLLM przy dużym `max_model_len`,
- wykorzystanie GPU i zachowanie p95/p99 latency.

### 6.4 Scenariusze pomiarowe

Projekt powinien mierzyć nie tylko pojedyncze zapytanie, ale scenariusze
odpowiadające realnej pracy zespołu.

| Scenariusz | Model kandydat | Kontekst | Concurrency | Cel pomiarowy |
|---|---|---:|---:|---|
| Krótkie pytanie kodowe | mały model / V4-Flash | 4k-16k | 4-8 | p95 E2E < 30 s |
| Typowy PR albo moduł | V4-Flash | 32k-128k | 4 | p95 E2E < 60 s |
| Duża analiza repo | V4-Flash / V4-Pro | 128k-384k | 1-4 | p95 E2E < 2 min |
| Repo-scale / agentic task | V4-Pro | 384k-800k | 1 | wynik mierzony, bez obietnicy wstępnego SLO |
| Load test zespołowy | mix modeli przez proxy | mixed | 8 | brak timeoutów, stabilny p95/p99 |
| Routing po koszcie | mały model vs V4-Flash/V4-Pro | mixed | 4-8 | porównanie jakości, latency i kosztu obliczeniowego |
| Shared-node vLLM | Kimi K2.6 TP=8 + szybszy model vLLM na tym samym 8×H200 | mixed | 1-4 | pomiar interferencji latency i stabilności p95/p99 |

Concurrency jest istotne, ponieważ AI support ma działać jako usługa zespołowa,
a nie jako pojedynczy eksperyment. Jeżeli kilku użytkowników pracuje równolegle,
system musi utrzymać wiele aktywnych KV cache, batchować requesty i zachować
akceptowalne opóźnienia. Dlatego benchmarki muszą mierzyć concurrency 1 / 4 / 8,
a docelowo także 16, zamiast ograniczać się do jednego requestu.

Czas odpowiedzi można interpretować jako:

```text
E2E latency ~= TTFT + liczba_tokenów_wyjściowych × TPOT
```

TTFT rośnie głównie z długością promptu i kosztem prefill. TPOT pokazuje koszt
generowania kolejnych tokenów i pogarsza się przy większym concurrency.

Celem projektu nie jest założenie z góry, że każdy request będzie szybki. Celem
jest zmierzenie, które kombinacje modelu, kontekstu i concurrency pozostają
interaktywne dla zespołu oraz kiedy należy używać mniejszego modelu, większego
modelu albo szybkiej ścieżki deterministycznej.

### 6.5 Eksperyment shared-node: Kimi K2.6 + szybszy model

Dodatkowym kandydatem na model premium jest Kimi K2.6. W wariancie vLLM należy
traktować go jako model uruchamiany na całym serwerze 8×H200, z
`tensor_parallel_size=8`. Równoległe wystawienie drugiego modelu nie oznacza wtedy
podziału GPU typu 5+3 albo 6+2. Oznacza uruchomienie dwóch osobnych instancji vLLM
na tym samym node:

```text
LiteLLM Proxy
   |
   |-- vLLM endpoint A: Kimi K2.6, TP=8, model premium
   |
   |-- vLLM endpoint B: szybszy model, np. DeepSeek-V4-Flash / Qwen / Gemma
```

Wariant ten trzeba potraktować jako eksperyment wydajnościowy, nie jako gwarantowany
układ produkcyjny. Kluczowe pytanie nie brzmi tylko "czy oba modele zmieszczą się
w VRAM", ale:

- czy oba endpointy startują stabilnie,
- ile VRAM zostaje po uruchomieniu obu instancji,
- jak zmienia się TTFT/TPOT Kimi K2.6 solo vs Kimi K2.6 + drugi model,
- jak zmienia się p95/p99 szybszego modelu, gdy Kimi K2.6 wykonuje długi prefill,
- czy szybszy model nadal pozostaje interaktywny dla krótkich zadań zespołu,
- czy współdzielenie HBM bandwidth i compute nie eliminuje korzyści z drugiego
  modelu.

Minimalna macierz pomiarowa:

| Test | Cel |
|---|---|
| Kimi K2.6 solo | baseline TTFT/TPOT/E2E dla modelu premium |
| Szybszy model solo | baseline latency modelu codziennego |
| Kimi K2.6 + drugi model idle | narzut samego współistnienia dwóch instancji |
| Kimi K2.6 long-context + krótkie zapytania do drugiego modelu | wpływ prefill na interaktywność modelu codziennego |
| Oba modele pod obciążeniem | stabilność p95/p99 i timeouty |

Jeżeli p95/p99 szybszego modelu pozostaje akceptowalne, shared-node może być
docelowym wariantem dla pary "model premium + model codzienny". Jeżeli nie,
należy wrócić do pary, w której większy model mieści się na mniejszej liczbie GPU,
a szybki model dostaje osobną pulę GPU.

Źródła techniczne do tych założeń:

- DeepSeek-V4-Pro vLLM Recipe: <https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro>
- DeepSeek-V4-Flash vLLM Recipe: <https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash>
- Kimi K2.6 vLLM Recipe: <https://recipes.vllm.ai/moonshotai/Kimi-K2.6>
- vLLM blog o DeepSeek V4: <https://vllm.ai/blog/deepseek-v4>
- NVIDIA H200: <https://www.nvidia.com/en-gb/data-center/h200/>

## 7. Workload testowy: radiogramy KF

Radiogramy KF są wykorzystywane jako trudny workload domenowy do oceny modeli i promptów. Cechy istotne:

- nietypowy, często przestawny szyk zdania,
- relacja nadawca-odbiorca odwrotna względem typowych zadań językowych,
- skrótowa, kontekstowa struktura komunikatów.

W ramach projektu zostanie sprawdzona koncepcja dwóch ścieżek:

- **Szybka ścieżka** — reguły / parsery dla znanych struktur. Niski koszt, deterministyczna, bez LLM.
- **Wolna ścieżka** — LLM analizuje przypadki nowe lub niejednoznaczne; wynik po weryfikacji człowieka może zasilić szybką ścieżkę jako nowa reguła.

Cel: koszt LLM ponoszony tylko dla nowych przypadków, powtarzalne przypadki obsługiwane deterministycznie.

## 8. Plan 12-tygodniowy

### Faza 1 (tyg. 1-3) — vLLM baseline

- vLLM uruchomione na 8×H200, pierwszy duży model działa,
- LiteLLM Proxy wystawione jako wspólny endpoint OpenAI-compatible przed vLLM,
- routing po polu `model` działa dla co najmniej dwóch backendów / modeli,
- pierwsza integracja z Open WebUI i Claude Code CLI,
- uruchomienie trybów SingleStream-lite i Sequential z pełnym zestawem kontroli (git commit, model revision, dtype, wersja vLLM, max_model_len, parametry dekodowania, workload label, warmup/measured runs),
- pierwsze pomiary TTFT, TPOT, throughput,
- minimalny dashboard Prometheus / Grafana.

### Faza 2 (tyg. 4-7) — integracje i wybór modeli

- równoległe uruchomienie modelu dużego + 1-2 małych,
- wybór finalnego modelu dużego (porównanie kandydatów: Kimi K2 / DeepSeek V4 / MiniMax),
- zdefiniowanie manualnych zasad routingu: mały model dla krótkich zadań, większy model dla zadań repo-scale i reasoningowych,
- eksperyment shared-node: Kimi K2.6 na `tensor_parallel_size=8` oraz drugi
  szybszy endpoint vLLM na tym samym 8×H200,
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
- eksperyment z vLLM Semantic Router: automatyczna klasyfikacja zapytań i porównanie z routingiem manualnym przez LiteLLM Proxy,
- pełny dashboard Grafana.

### Faza 4 (tyg. 11-12) — stabilizacja i raport

- stabilizacja konfiguracji vLLM,
- stabilizacja konfiguracji proxy, kluczy użytkowników, logów i zasad wyboru modelu,
- instrukcja korzystania dla zespołu,
- raport końcowy: benchmarki, wnioski z radiogramów KF, rekomendacja dalszych prac.

## 9. Kryteria sukcesu

Po 12 tygodniach:

1. vLLM działa stabilnie na 8×H200.
2. LiteLLM Proxy działa jako jeden lokalny endpoint OpenAI-compatible przed wieloma instancjami vLLM.
3. Routing po polu `model` pozwala wybrać model duży albo mały bez przeładowywania backendu.
4. Model duży (>500B params) i co najmniej jeden mały model dostępne **jednocześnie**, bez przełączania.
5. Open WebUI, Claude Code CLI i plugin VS Code korzystają z tego samego lokalnego endpointu.
6. Czas odpowiedzi dla typowego zapytania programistycznego nie przekracza minuty przy 4 równoległych użytkownikach (próg do potwierdzenia liczbowo w fazie 1 — dziś nie znamy baseline'u).
7. Dostępne metryki TTFT, TPOT, throughput, concurrency, GPU util w Grafanie.
8. Powtarzalny benchmark harness uruchamiany jednym poleceniem; działają trzy tryby benchmarku: SingleStream-lite, Sequential, Server-lite.
9. Zmierzony jest wariant shared-node: Kimi K2.6 TP=8 + drugi szybszy endpoint vLLM na tym samym 8×H200, z porównaniem latency solo vs razem.
10. Wszystkie raporty benchmarków zawierają komplet kontroli (git commit, model revision, dtype, wersja vLLM, max_model_len, parametry dekodowania, workload label, warmup/measured runs, concurrency) zgodnie z wewnętrzną specyfikacją metodyki.
11. Workload radiogramów KF z wersjonowanymi promptami i pierwszym porównaniem modeli.
12. Sprawdzona koncepcja szybkiej i wolnej ścieżki.
13. Porównany routing manualny i automatyczny: jakość klasyfikacji, latency overhead i koszt obliczeniowy.
14. Raport końcowy z liczbowymi rekomendacjami doboru modelu i konfiguracji.

## 10. Nakład

2 dni tygodniowo × 12 tygodni.

Czas obejmuje: konfigurację vLLM, konfigurację proxy, integracje, benchmark harness, testy modeli, analizę wyników, dashboardy, dokumentację i raport końcowy.

## 11. Wartość dla zespołu

- Praca z całymi repozytoriami przez Claude Code CLI — odblokowuje główny use case.
- Brak kolejek przy równoczesnej pracy kilku osób.
- Dostęp do modeli klasy GPT/Claude/Gemini lokalnie, bez zewnętrznego API.
- Jeden endpoint dla narzędzi zespołu, mimo że pod spodem działa wiele modeli i instancji vLLM.
- Możliwość routingu po koszcie: mały model dla prostych zadań, duży model dla pracy repo-scale.
- Kompetencja pomiaru wydajności inferencji LLM — podstawa pod kolejne decyzje infrastrukturalne (dobór modelu, planowanie sprzętu, optymalizacja promptów).
