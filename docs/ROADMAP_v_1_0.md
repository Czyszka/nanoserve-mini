# nanoserve-mini — Roadmap

> 12-tygodniowy projekt portfolio z LLM inference. Preludium do pełnego nanoserve, ale samodzielny i skończony artefakt sam w sobie. Cel kompetencyjny: zbudować weryfikowalną kompetencję w LLM serving, observability, KV cache i kernel performance — wystarczającą do podjęcia świadomej decyzji co dalej.

**Status:** plan ogólny. Szczegółowe plany każdej fazy — w osobnych dokumentach (`docs/phase-N-plan.md`), pisane na początku danej fazy, nie wcześniej.

---

## Pozycjonowanie

`nanoserve-mini` to **skończony projekt portfolio** w 12 tygodni, który jednocześnie służy jako **dowód operacyjny czy ma sens iść w pełny `nanoserve`** (9-miesięczny projekt z własnym engine, K8s, multi-GPU, FP8 itd.).

To że nazywa się "mini" nie znaczy że jest mniej wartościowy — znaczy że ma węższy scope. Po 12 tygodniach masz CV-ready artefakt który stoi sam, niezależnie od tego czy nanoserve full kiedykolwiek powstanie.

Target rynkowy: role typu **Senior SWE Inference / Performance Engineer / ML Systems Engineer** w AI labs (Anthropic, OpenAI, Together AI, NVIDIA, Cohere, Mistral, Lambda).

---

## Cel projektu

Zbudować reprodukowalny LLM inference performance lab z:
- vLLM jako serving baseline,
- Prometheus/Grafana observability,
- własnym benchmark harness i workload analysis,
- jednym kernelem Triton (RMSNorm albo SwiGLU) z benchmarkiem i profilem,
- 4-6 technicznymi write-upami,
- final decision doc.

---

## Definition of done

Projekt jest skończony, gdy spełnia wszystkie poniższe:

1. **Działający vLLM serving setup** z reprodukowalną instalacją.
2. **Reprodukowalny benchmark harness** dla różnych workloadów i poziomów concurrency.
3. **Prometheus/Grafana dashboard** pokazujący live metrics w trakcie load testu.
4. **Co najmniej jeden eksperyment analityczny** — workload comparison (short/medium/long/mixed) ALBO prefix cache experiment.
5. **Jeden kernel Triton** z testem correctness vs PyTorch, benchmarkiem dla kilku shapes i analizą memory bandwidth.
6. **4-6 write-upów technicznych** — w tym minimum jeden failure write-up opisujący rzecz, która nie zadziałała albo nie poprawiła metryk — + finalny README + decision doc opisujący wybór ścieżki dalej.

Mniej niż 4 z tych = projekt "w trakcie", nie "skończony". Komunikacja na CV/LinkedIn dopiero po wszystkich 6.

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
| **F1 — Serving baseline + observability** | 1-3 | Działający vLLM + dashboard + benchmark methodology doc | Rozumiesz operations side LLM serving |
| **F2 — Workload analysis + cache experiment** | 4-7 | Latency study + prefix cache experiment + write-upy | Rozumiesz prefill/decode economics, KV cache pressure |
| **F3 — Triton kernel + profiling** | 8-10 | Jeden kernel z benchmarkiem i profilem | Kernel credibility, memory bandwidth thinking |
| **F4 — Polish + decision** | 11-12 | README, final summary, decision doc, opcjonalny upstream PR/issue | Umiesz komunikować efekt, podejmujesz świadomą decyzję |

Szczegółowy plan tygodnia każdej fazy → osobny `docs/phase-N-plan.md`, pisany **na początku tej fazy** (nie wcześniej, bo wnioski z poprzedniej fazy zmieniają plan następnej).

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

## Świadomie poza scope

Te rzeczy są poza scope tego projektu. **Nie wracamy do dyskusji o nich w trakcie tych 12 tygodni.** Jeśli pojawi się chęć rozszerzenia — odkładamy do decyzji końcowej (Ścieżka B = nanoserve full).

- **Własny engine od zera** — używamy vLLM. Pisanie własnego inference engine to nanoserve full.
- **Implementacja PagedAttention od zera** — używamy gotowej z vLLM, zrozumieć i zmierzyć.
- **Tensor parallelism / multi-GPU** — single GPU wystarczy do zrobienia value tej fazy.
- **Kubernetes, Helm, GPU Operator** — Docker albo native install, bez K8s.
- **Multi-backend router** — zostaje vLLM, ewentualnie 1 eksperyment z prostą strategią routing nie pełen gateway.
- **Fused attention kernel** — pierwszy kernel to RMSNorm/SwiGLU/RoPE, nie attention.
- **TensorRT-LLM, SGLang integration** — vLLM wystarczy.
- **8×H200, NVLink/PCIe analysis, NUMA affinity** — to nanoserve full territory.
- **FP8, quantization** — może w nanoserve, nie tu.
- **Speculative decoding, MoE, disaggregated serving** — beyond scope.
- **Production HA, autoscaling, multi-region** — beyond scope.
- **Pełna implementacja prefix cache** — używamy vLLM APC i mierzymy zachowanie.

Wszystkie te rzeczy mają wartość **później**. Nie teraz.

---

## Reading

Kanon papers — `docs/reading-list.md` (CS349D-inspired). Czytane *w trakcie* odpowiedniej fazy, nie przed startem.

NVIDIA self-paced courses — `docs/nvidia_self_paced_courses.md`. Najwartościowsze dla projektu: **Sizing LLM Inference Systems** (faza 1), **Find the Bottleneck: Optimize AI Pipelines with Nsight Systems** (faza 3). Reszta beyond scope tego projektu.

---

## Regular cadence

- **Codziennie:** commit (nawet mały, nawet WIP). Łańcuch commitów to dowód że projekt żyje.
- **Co tydzień:** krótka notatka `docs/weekly/wN.md` — co zrobione, co blokuje, co dalej. ~10 minut, format dowolny.
- **Co fazę:** pisanie szczegółowego planu kolejnej fazy, retrospekcja poprzedniej.

---

## Co teraz

Plik powstał, kierunek jest. **Następny ruch nie jest "więcej planowania".** Następny ruch to:

1. Założyć puste repo `nanoserve-mini`.
2. Skopiować ten plik jako `ROADMAP.md`, `reading-list.md` jako `docs/reading-list.md`.
3. Postawić vLLM gdzieś gdzie masz GPU.
4. Zmierzyć pierwszy TTFT.
5. Skomitować README z trzema linijkami: co to za projekt, sprzęt, pierwszy pomiar.

Szczegółowy plan Fazy 1 piszesz **po** tych 5 krokach, nie przed. Bo dopiero z pozycji "mam vLLM odpalony" wiesz co realnie jest priorytetem do zaplanowania.
