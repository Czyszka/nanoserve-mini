# Reading List — LLM Inference Performance Lab

Lista papers do przeczytania w trakcie projektu, oparta na curriculum [Stanford CS349D — AI Inference Infrastructure](https://web.stanford.edu/class/cs349d/) (Spring 2026, prowadzący: Christos Kozyrakis).

**Filozofia:** czytanie odbywa się *w trakcie* implementacji, nie przed nią. Każdy paper ma swój moment w projekcie, kiedy ma kontekst i zostaje w głowie. Czytane abstrakcyjnie przed startem — zapomniane do tygodnia 6.

**Konwencja:**
- ⭐ — required reading dla tej fazy projektu
- 📖 — recommended, czytane gdy konkretny problem się pojawi
- 🔭 — optional, dla głębszego zrozumienia tematu
- ⏭️ — beyond scope tego projektu (ale warto wiedzieć że istnieje)

---

## Faza 1 — Setup, baseline, observability (tygodnie 1-3)

Cel czytelniczy: zrozumieć big picture LLM serving, zacząć rozpoznawać metryki w vLLM, zbudować mental model "co się dzieje pod maską".

- ⭐ [How to Read a Paper](https://dl.acm.org/doi/10.1145/1273445.1273458) — Keshav. 5 stron, czytasz pierwszego dnia. Reszta listy będzie szybsza dzięki temu.
- ⭐ [Efficient LLM Serving Survey](https://dl.acm.org/doi/full/10.1145/3754448) — survey, daje całą mapę terenu. Czytasz na początku tygodnia 1, wracasz w trakcie projektu.
- ⭐ [Efficiently Scaling Transformer Inference](https://arxiv.org/abs/2211.05102) — Pope et al. (Google). **Najważniejszy paper o roofline thinking dla transformerów.** Czytasz w tygodniu 2-3 gdy zaczynasz patrzeć na liczby z benchmarków.
- 📖 [PagedAttention / vLLM](https://arxiv.org/abs/2309.06180) — Kwon et al. Czytasz gdy w Grafanie zobaczysz `gpu_cache_usage` i `running/waiting requests` i będziesz chciał zrozumieć skąd te metryki się biorą.
- 🔭 [Clockwork](https://www.usenix.org/conference/osdi20/presentation/gujarati) — predictable performance for ML inference. Pre-LLM (2020), ale fundamenty SLO thinking.

## Faza 2 — Latency study, prefix cache, scheduling (tygodnie 4-6/7)

Cel czytelniczy: zrozumieć prefill vs decode economics, KV cache management, batching strategies. To jest centrum LLM serving.

- ⭐ [Orca](https://www.usenix.org/conference/osdi22/presentation/yu) — pierwsza praca o continuous batching. Czytasz gdy będziesz analizował tail latency i dlaczego naive batching jest słaby.
- ⭐ [Sarathi-Serve](https://www.usenix.org/conference/osdi24/presentation/agrawal) — chunked prefill. **Najważniejsze: tłumaczy TTFT vs TPOT trade-off w sposób operacyjny.** Czytasz w tygodniu 5.
- ⭐ [DistServe](https://arxiv.org/abs/2401.09670) — prefill-decode disaggregation. Czytasz w tygodniu 5-6 gdy będziesz miał własne dane o tym jak różnie zachowują się prefill i decode.
- 📖 [MoonCake](https://arxiv.org/abs/2407.00079) — Kimi's context caching architecture at scale. Czytasz w tygodniu 6 jeśli robisz prefix cache experiment.
- 📖 [CacheGen](https://arxiv.org/abs/2310.07240) — KV cache compression and streaming. Komplementarny do MoonCake.
- 🔭 [SplitWise](https://arxiv.org/abs/2311.18677) — Microsoft, alternatywa dla DistServe.
- 🔭 [Strata](https://arxiv.org/abs/2508.18572) — recent work on context management.

## Faza 3 — Triton kernel + profiling (tygodnie 8-10)

Cel czytelniczy: zrozumieć IO-aware kernel design zanim napiszesz pierwszy kernel. FlashAttention czytasz *przed* implementacją RMSNorm/SwiGLU — uczy memory access pattern thinking.

- ⭐ [FlashAttention](https://arxiv.org/abs/2205.14135) — Dao et al. **Fundament wszystkich szybkich attention kernels.** Czytasz na początku tygodnia 8, nawet jeśli sam piszesz RMSNorm a nie attention.
- 📖 [FlashInfer](https://arxiv.org/abs/2501.01005) — production-grade attention kernels. Lepsze do referencji implementacji niż FA1.
- 🔭 [FlashAttention-3](https://arxiv.org/abs/2407.08608) — H100-specific optimizations (asynchrony, FP8). Optional, chyba że masz H100.
- 🔭 [FlashAttention-4](https://arxiv.org/abs/2603.05451) — najnowsza wersja.

## Faza 4 — Polish, write-upy, decyzja (tygodnie 11-12)

- 📖 [SGLang](https://arxiv.org/abs/2312.07104) — alternatywny engine, dobry reference do "co bym zrobił inaczej". Przydatne do final write-upu.
- 🔭 [Speculative Decoding](https://arxiv.org/abs/2211.17192) — Leviathan et al. Wymieniony w "future work" Twojego oryginalnego nanoserve, warto wiedzieć.
- 🔭 [SpecInfer](https://arxiv.org/abs/2305.09781) — tree-based speculative decoding.

---

## Beyond scope tego projektu

Te papers są w curriculum CS349D, ale nie pasują do scope 12-tygodniowego inference performance lab. Zostaw je na ewentualną kontynuację lub Phase 2 nanoserve.

### Parallelism (training-side, mniej relewantne dla pure inference)

- ⏭️ [FlexFlow](https://arxiv.org/abs/1807.05358) — training-time parallelism search.
- ⏭️ [Alpa](https://arxiv.org/pdf/2201.12023) — auto-parallelism dla training.
- ⏭️ [LoongServe](https://dl.acm.org/doi/10.1145/3694715.3695948) — long-context serving.
- ⏭️ [Arctic](https://arxiv.org/abs/2507.11830).

### Mixture of Experts

- ⏭️ [MegaScale-Infer](https://arxiv.org/abs/2504.02263)
- ⏭️ [Helix Parallelism](https://arxiv.org/abs/2406.01566)
- ⏭️ [Original MoE paper (Shazeer et al.)](https://arxiv.org/abs/1701.06538) — fundament historyczny.
- ⏭️ [FlashMoE](https://arxiv.org/abs/2506.04667)

### Hybrid architectures (Mamba etc.)

- ⏭️ [Mamba](https://arxiv.org/abs/2312.00752)
- ⏭️ [Marconi](https://mlsys.org/virtual/2025/poster/3260)
- ⏭️ [DeepSeek-V3.2](https://arxiv.org/abs/2512.02556)

### Routing & multi-tenancy (relevant dla późniejszych faz nanoserve)

- ⏭️ [Optimizing Model Selection for Compound AI Systems](https://arxiv.org/abs/2502.14815) — przydatne jeśli wrócisz do routing layer.
- ⏭️ [Clipper](https://www.usenix.org/conference/nsdi17/technical-sessions/presentation/crankshaw) — pre-LLM serving system, warto znać historycznie.
- ⏭️ [LithOS](https://arxiv.org/abs/2504.15465) — multi-tenancy GPU OS.
- ⏭️ [Prism](https://arxiv.org/abs/2505.04021) — multi-tenancy LLM serving.
- ⏭️ [Fork in the Road](https://www.usenix.org/conference/osdi25/presentation/chai-xiaohu)

### Agentic, memory, RL (inny domain)

- ⏭️ [Autellix](https://arxiv.org/abs/2502.13965), [Parrot](https://arxiv.org/abs/2405.19888) — agentic workflows scheduling.
- ⏭️ [MetaGPT](https://arxiv.org/abs/2308.00352), [DSPy](https://arxiv.org/abs/2310.03714)
- ⏭️ [Cartridges](https://arxiv.org/abs/2506.06266), [mem0](https://arxiv.org/abs/2504.19413), [MemGPT](https://arxiv.org/abs/2310.08560), [Agentic Context Engineering](https://arxiv.org/abs/2510.04618)
- ⏭️ [HybridFlow](https://arxiv.org/abs/2409.19256), [RLHFuse](https://arxiv.org/abs/2409.13221) — RL training infrastructure.
- ⏭️ [DeepSeek R1 Technical Report](https://arxiv.org/abs/2501.12948)

### Routing systems w produkcji

- ⏭️ [NVIDIA Dynamo](https://developer.nvidia.com/blog/introducing-nvidia-dynamo-a-low-latency-distributed-inference-framework-for-scaling-reasoning-ai-models/) — blog post, nie paper, ale informacyjny.

---

## Pełny schedule CS349D (reference)

Original Stanford schedule, dla pełności kontekstu i jeśli chcesz śledzić kurs gdy dodadzą notatki.

| # | Date | Topic | Required | Optional |
|---|------|-------|----------|----------|
| 1 | Mar 30 | Introduction | How to Read a Paper | Efficient LLM Serving Survey, Clockwork |
| 2 | Apr 1 | Parallelism | FlexFlow, Efficiently Scaling Transformer Inference | LoongServe, Alpa, Arctic |
| 3 | Apr 6 | Serving Engines | PagedAttention, SGLang | — |
| 5 | Apr 13 | Batching | Orca, Clipper | — |
| 6 | Apr 15 | Disaggregation | DistServe, Dynamo | SplitWise, Sarathi-Serve |
| 7 | Apr 20 | Speculative Decoding | Speculative Decoding, SpecInfer | — |
| 9 | Apr 27 | Context Management | MoonCake, CacheGen | Strata |
| 10 | Apr 29 | Efficient Attention | FlashAttention, FlashInfer | FA3, FA4 |
| 11 | May 4 | Hybrid LLMs | Marconi, DeepSeek-V3.2 | Mamba |
| 12 | May 6 | Mixture of Experts | MegaScale-Infer, Helix Parallelism | Original MoE, FlashMoE |
| 14 | May 13 | Load Balancing & Routing | Optimizing Model Selection | — |
| 15 | May 18 | Agentic Workflows | Autellix, Parrot | MetaGPT, DSPy |
| 16 | May 20 | Memory | Cartridges, mem0 | MemGPT, Agentic Context Engineering |
| 17 | May 27 | Reinforcement Learning | HybridFlow, RLHFuse | DeepSeek R1 |
| 18 | Jun 1 | Multi-tenancy | LithOS, Prism | Fork in the Road |

Wykłady 4 i 13 to programming assignment meetings (bez readingu), 8 to guest lecture (Ying Sheng, SGLang/RadixArk), 19 to project presentations.

---

## Notatki własne

Tu zapisuj swoje wnioski po każdym paperze w 2-3 zdaniach. Po projekcie ten fragment będzie sam w sobie wartościowym artefaktem (kandydat na blog post: "Reading list dla LLM inference engineer — co przeczytałem i co z tego zostaje").

Format sugerowany:

> **[Paper title]** — czytany w tygodniu N. Główna idea: ... Co z tego biorę do projektu: ... Co mi się nie zgrywało: ...

> **Towards Efficient Generative Large Language Model Serving: A Survey from Algorithms to Systems** — czytany w tygodniu 1 / Phase 1. Główna idea: LLM serving trzeba rozumieć jako cały stos: autoregresyjny prefill/decode, KV cache, scheduler, batching, kernel backend i benchmark methodology, a nie jako pojedynczy speedup. Co z tego biorę do projektu: pierwszy vLLM baseline ma od razu zapisywać TTFT, E2E, workload controls i server controls, a później korelować je z `/metrics`; nie implementujemy alternatywnych serving systemów, tylko mierzymy objawy opisane w surveyu.
