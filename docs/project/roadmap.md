# nanoserve-mini — Roadmap

> 12-tygodniowy projekt portfolio z LLM inference. Preludium do pełnego nanoserve, ale samodzielny i skończony artefakt sam w sobie. Cel kompetencyjny: zbudować weryfikowalną kompetencję w LLM serving, observability, KV cache i kernel performance — wystarczającą do podjęcia świadomej decyzji co dalej.

**Status:** plan kierunkowy. Szczegółowe plany faz, sesji i tygodni są w `docs/plans/` oraz `docs/weekly/`; bieżący stan jest w `docs/operations/agent-state.md`.

---

## Rola dokumentu

Ten plik opisuje **kierunek, zakres, kryteria ukończenia i kolejność prac**.
Nie jest miejscem na bieżący status projektu, aktualne decyzje operacyjne,
ostatnie wyniki, listę blokad ani następny konkretny krok sesji.

Bieżący stan projektu żyje w `docs/operations/agent-state.md`. Jeśli roadmapa
i agent-state są niespójne, roadmapa odpowiada na pytanie "dokąd idziemy i
dlaczego", a agent-state odpowiada na pytanie "gdzie jesteśmy teraz i co dalej".

---

## Pozycjonowanie

`nanoserve-mini` to **skończony projekt portfolio** w 12 tygodni, który jednocześnie służy jako **dowód operacyjny czy ma sens iść w pełny `nanoserve`** (9-miesięczny projekt z własnym engine, K8s, multi-GPU, FP8 itd.).

To że nazywa się "mini" nie znaczy że jest mniej wartościowy — znaczy że ma węższy scope. Po 12 tygodniach masz CV-ready artefakt który stoi sam, niezależnie od tego czy nanoserve full kiedykolwiek powstanie.

Target rynkowy: role typu **Senior SWE Inference / Performance Engineer / ML Systems Engineer** w AI labs (Anthropic, OpenAI, Together AI, NVIDIA, Cohere, Mistral, Lambda).

---

## Cel projektu

Zbudować reprodukowalny LLM inference performance lab z:
- vLLM jako serving baseline,
- LiteLLM Proxy jako warstwą multi-model routingu (jeden endpoint OpenAI-compatible przed wieloma instancjami vLLM),
- Prometheus/Grafana observability,
- własnym benchmark harness i workload analysis,
- eksperymentem z vLLM Semantic Router (automatyczna klasyfikacja zapytań, porównanie z routingiem manualnym),
- jednym kernelem Triton (RMSNorm albo SwiGLU) z benchmarkiem i profilem,
- 5-7 technicznymi write-upami,
- final decision doc.

---

## Definition of done

Projekt jest skończony, gdy spełnia wszystkie poniższe:

1. **Działający vLLM serving setup** z reprodukowalną instalacją.
2. **LiteLLM Proxy** uruchomione przed vLLM jako jeden endpoint OpenAI-compatible z routingiem po polu `model` (multi-model setup, klucze API per użytkownik, logi).
3. **Reprodukowalny benchmark harness** dla różnych workloadów i poziomów concurrency.
4. **Prometheus/Grafana dashboard** pokazujący live metrics w trakcie load testu.
5. **Co najmniej jeden eksperyment analityczny** — workload comparison (short/medium/long/mixed) ALBO prefix cache experiment.
6. **Eksperyment z vLLM Semantic Router** — automatyczna klasyfikacja zapytań i porównanie z routingiem manualnym (jakość klasyfikacji, latency overhead, koszt obliczeniowy, satysfakcja użytkownika).
7. **Jeden kernel Triton** z testem correctness vs PyTorch, benchmarkiem dla kilku shapes i analizą memory bandwidth.
8. **5-7 write-upów technicznych** — w tym minimum jeden failure write-up opisujący rzecz, która nie zadziałała albo nie poprawiła metryk — + finalny README + decision doc opisujący wybór ścieżki dalej.

Mniej niż 5 z tych = projekt "w trakcie", nie "skończony". Komunikacja na CV/LinkedIn dopiero po wszystkich 8.

---

## Benchmark Contract

Każdy benchmark w projekcie musi zapisywać metryki i warunki uruchomienia w sposób umożliwiający powtórzenie wyniku.

**Metryki minimum:**
- TTFT p50/p95,
- TPOT p50/p95,
- end-to-end latency p50/p95,
- request throughput,
- output throughput tokens/s,
- input tokens / output tokens per request,
- concurrency,
- GPU memory usage,
- GPU KV cache usage, jeśli dostępne,
- prefix cache hit rate, jeśli eksperyment dotyczy cache.

**Controls minimum:**
- model name,
- dtype / quantization,
- GPU model,
- vLLM version,
- max model length,
- max number of sequences / batched tokens, jeśli ustawiane,
- decoding parameters,
- workload definition,
- liczba warmupów i liczba mierzonych runów.

---

## 4 fazy

| Faza | Tygodnie | Główny deliverable | Co udowadnia |
|------|---------|-------------------|--------------|
| **F1 — Serving baseline + observability + multi-model proxy** | 1-3 | Działający vLLM + LiteLLM Proxy + dashboard + benchmark methodology doc | Rozumiesz operations side LLM serving i multi-model routing |
| **F2 — Workload analysis + cache experiment** | 4-7 | Latency study + prefix cache experiment + write-upy | Rozumiesz prefill/decode economics, KV cache pressure |
| **F3 — Triton kernel + profiling + semantic routing** | 8-10 | Jeden kernel z benchmarkiem i profilem + eksperyment z vLLM Semantic Router | Kernel credibility, memory bandwidth thinking, świadoma ocena production routing strategies |
| **F4 — Polish + decision** | 11-12 | README, final summary, decision doc, opcjonalny upstream PR/issue | Umiesz komunikować efekt, podejmujesz świadomą decyzję |

Szczegółowe plany faz, tygodni i większych sesji roboczych trafiają do `docs/plans/` albo `docs/weekly/`, pisane **w momencie wejścia w dany etap**. Roadmapa nie powinna być aktualizowana po każdej zmianie stanu; od tego jest `docs/operations/agent-state.md`.

---

## Decision points (mid-project)

Plan zakłada checkpointy decyzyjne w trakcie. To są momenty *wymagane*, nie opcjonalne — kalendarz w nim, dzień zarezerwowany.

**Po Fazie 1 (koniec tyg 3):** czy fundamenty serving są dla mnie ciekawe? Czy chcę kontynuować plan, czy pivotować od razu w stronę kernela (skip workload study)?

**Po Fazie 2 (koniec tyg 7):** czy chcę faktycznie wejść w kernel work, czy zostaję dłużej przy serving/observability/scaling experiments? To jest moment "ostatnia szansa" żeby zmienić finałowy artefakt.

**Po Fazie 3 (koniec tyg 10):** czy kernel artifact jest w stanie który warto pokazać, czy potrzebuję jeszcze tygodnia na poprawki? Czy upstream PR ma sens?

---

## Decision point końcowy (koniec tyg 12) — 4 ścieżki

Po skończeniu projektu wybierasz jedną z czterech:

**Ścieżka A — Aplikuję.** Idziesz na proces rekrutacyjny do Anthropic / OpenAI / Together / NVIDIA / Cohere / Mistral. Kryteria: projekt skończony, mocny core artefakt (kernel albo workload study), czujesz że umiesz opowiedzieć każdy element.

**Ścieżka B — Kontynuuję w nanoserve full (9 mies).** Rozszerzasz scope do PROJECT_PLAN_v1_4 — własny engine, K8s, multi-GPU, FP8. Kryteria: projekt skończony i ciekawy przez większość czasu; lubisz kernel/perf level; masz czas i motywację na 9 mies; rynek poczeka.

**Ścieżka C — Pivot.** Skończony projekt, ale serving/observability/platform ciekawsze niż kernel. Aplikujesz na role typu "ML Platform Engineer" / "AI Infra" zamiast "Inference Engineer". Albo: w ogóle inny stack (np. RL infra, training infra). Kryteria: projekt skończony, ale konkretne wymiary cię męczyły, inne ciągnęły.

**Ścieżka D — Stop.** LLM inference nie jest dla mnie jako career direction. Zostajesz w obecnej roli albo szukasz czegoś bliżej obecnego stacka. Kryteria: projekt męczył przez większość czasu, kernel/perf nie dawały satysfakcji, gdyby nie commitment to byś rzucił w połowie.

Decision doc (`docs/decision.md`) pisany w tygodniu 12 jest częścią Definition of done — niezależnie od ścieżki.

---

## W scope dzięki projektowi firmowemu (synteza, bez własnej infrastruktury)

Następujące obszary **pierwotnie były poza scope** prywatnego mini, ale dzięki temu, że równolegle prowadzony jest projekt firmowy na sprzęcie 8×H200 (vLLM, modele >500B MoE w FP8, multi-tenant), wchodzą do prywatnego scope **jako materiał do write-upów**, bez konieczności stawiania własnej infrastruktury.

Reguła: pomiar wykonywany jest raz, na sprzęcie firmowym. Synteza dla rynku idzie do prywatnego repo z higieną — publiczne workloady (ShareGPT, MMLU, dummy syntetyczne), publiczne modele HF, standardowy sprzęt. **Workload domenowy z pracy nie wchodzi do write-upów portfolio.**

Obszary wchodzące do scope tym kanałem:

- **8×H200, NVLink/PCIe topology** — pomiary podczas pracy, synteza w write-upie.
- **Tensor parallelism, multi-GPU** — TP scaling, koszty komunikacji, sweet spot.
- **MoE serving** — Kimi K2 / DeepSeek V4 / MiniMax: KV cache pressure, expert routing, ograniczenia wydajnościowe.
- **FP8 quantization** — trade-off cost/quality, wpływ na throughput i pamięć.
- **Multi-tenant serving** — duży + małe modele na jednej maszynie, alokacja GPU, izolacja workloadów.
- **Multi-model proxy / routing strategies** — LiteLLM Proxy jako manualny routing po `model`, vLLM Semantic Router jako automatyczna klasyfikacja, porównanie obu podejść.

## Świadomie poza scope (nawet z projektem firmowym)

- **Własny engine od zera** — używamy vLLM. Pisanie własnego inference engine to nanoserve full.
- **Implementacja PagedAttention od zera** — używamy gotowej z vLLM, zrozumieć i zmierzyć.
- **Kubernetes, Helm, GPU Operator** — Docker albo native install, bez K8s.
- **Fused attention kernel** — pierwszy kernel to RMSNorm/SwiGLU/RoPE, nie attention.
- **TensorRT-LLM, SGLang integration** — vLLM wystarczy.
- **Speculative decoding, disaggregated serving** — beyond scope.
- **Production HA, autoscaling, multi-region** — beyond scope.
- **Pełna implementacja prefix cache** — używamy vLLM APC i mierzymy zachowanie.

Wszystkie te rzeczy mają wartość **później**. Nie teraz.

---

## Write-upy (titles roboczo, do dopracowania)

Plan 7 write-upów portfolio, mapowanych na fazy pracy firmowej + prywatny Triton track. Tytuły robocze — finalne decyduje treść po zebraniu danych.

| # | Faza źródłowa | Tytuł roboczy | Treść |
|---|---|---|---|
| W1 | F1 firma | **vLLM + LiteLLM Proxy on 8×H200: a multi-model serving baseline from zero to first measurement** | Stack od instalacji po pierwszy TTFT/E2E z pełnym zestawem kontroli; LiteLLM Proxy jako jeden endpoint OpenAI-compatible przed wieloma instancjami vLLM (routing po `model`, klucze API, logi); observability (Prometheus + Grafana) i co realnie widać w `/metrics`. |
| W2 | F2 firma | **Tensor parallelism scaling on 8×H200: where the sweet spot really is** | TP=1/2/4/8 dla modeli klasy 70B-200B, koszt all-reduce, wpływ NVLink, kiedy TP przestaje się opłacać. |
| W3 | F2-F3 firma | **Serving 1T-parameter MoE in FP8: KV cache, expert routing, and the cost of context length** | Kimi K2 / DeepSeek V4 — co realnie ogranicza throughput, jak skaluje się KV cache z długością kontekstu, ile kosztuje FP8 jakościowo. |
| W4 | F3 firma | **Semantic routing for production LLM serving: vLLM Semantic Router vs manual model selection** | Eksperyment z vLLM Semantic Router — automatyczna klasyfikacja zapytań (krótkie/proste vs długie/złożone, kodowe vs ogólne), porównanie z routingiem manualnym (LiteLLM po `model`): jakość klasyfikacji, latency overhead, koszt obliczeniowy, satysfakcja użytkownika. |
| W5 | F3 prywatna | **Writing a Triton kernel for RMSNorm: correctness, benchmark, and what the profile actually shows** | Jeden kernel od zera, test correctness vs PyTorch, benchmark dla kilku shapes, analiza memory bandwidth i Nsight profile. |
| W6 | dowolna | **What didn't work: a failure write-up** | Konkretny eksperyment, który nie poprawił metryk — dlaczego, co to mówi o intuicji, co bym zrobił inaczej. Najmocniejszy artefakt z całej siódemki. Naturalni kandydaci do bycia tym write-upem: W4 (semantic router gorszy niż manual) lub W5 (Triton kernel nie pobił `torch.compile`) — który nie dowiezie, ten staje się W6. |
| W7 | F4 | **12 weeks of LLM inference: methodology, numbers, decisions** | Synteza całego projektu — metodyka MLPerf-inspired + Serving-Bench-inspired, kluczowe liczby, najważniejsze wnioski, decision doc w skrócie. |

Triton (W5) to jedyny write-up oparty na pracy poza godzinami firmowymi. Reszta korzysta z pomiarów wykonanych w ramach projektu firmowego — write-up jest pakowaniem tych danych pod kątem rynku, nie powtarzaniem eksperymentu.

Cadence pisania: co ~1.7 tygodnia jeden write-up (W1 koniec F1, W2-W3 w F2, W4-W5 w F3, W6 elastycznie, W7 w F4).

---

## Reading

Kanon papers — `docs/learning/reading-list.md` (CS349D-inspired). Czytane *w trakcie* odpowiedniej fazy, nie przed startem.

NVIDIA self-paced courses — `docs/learning/nvidia-self-paced-courses.md`. Najwartościowsze dla projektu: **Sizing LLM Inference Systems** (faza 1), **Find the Bottleneck: Optimize AI Pipelines with Nsight Systems** (faza 3). Reszta beyond scope tego projektu.

---

## Regular cadence

- **Codziennie:** commit (nawet mały, nawet WIP). Łańcuch commitów to dowód że projekt żyje.
- **Co tydzień:** krótka notatka `docs/weekly/wN.md` — co zrobione, co blokuje, co dalej. ~10 minut, format dowolny.
- **Co fazę:** pisanie szczegółowego planu kolejnej fazy, retrospekcja poprzedniej.

---

## Jak aktualizować roadmapę

Roadmapę zmieniaj tylko wtedy, gdy zmienia się jeden z trwałych elementów
projektu:

1. zakres projektu,
2. definicja ukończenia,
3. kolejność lub treść faz,
4. benchmark contract,
5. świadome granice scope,
6. plan write-upów albo końcowy kierunek portfolio.

Nie dopisuj tutaj:

- aktualnego statusu serwera,
- wyników ostatnich benchmarków,
- bieżących blokad,
- listy następnych komend,
- szczegółowego logu sesji,
- decyzji operacyjnych, które mogą zmienić się w kolejnej iteracji.

Te informacje należą do `docs/operations/agent-state.md`, planów roboczych w
`docs/plans/`, runbooków w `docs/operations/runbooks/` albo tygodniówek w
`docs/weekly/`.
