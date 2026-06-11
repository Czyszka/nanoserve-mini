# NVLink boundary session — werdykt latency/throughput — 2026-06-11/12

Issue #50, sesja wg `docs/plans/2026-06-11-nvlink-boundary-session.md`.
Artefakty: `results/runs/2026-06-11_nvlink_boundary/` (commity `e13c30d`,
`f1b1f70`, `4aca22b`, `f0214ed`, `94eebd0` + Q4). Trace'y (poza repo):
`/home/working/nanoserve-tracing/` na ubuntusrv2. Buduje na
`2026-06-11-qwen-tp-curve.md` i `2026-06-11-kimi-tp8-profile.md`.

## K1 — Kimi TP8 batched ramp (SWE custom, 256-out)

| c | TPOT med (ms) | ITL med (ms) | out tok/s | moc / SMACT | PCIe RX (GB/s) |
|---:|---:|---:|---:|---|---:|
| 1 | 8.7 | — | 75 | — | — |
| 8 | 78.5 | 191 | 86 | 135 W / 0.093 | 7.20 |
| 16 | 190.5 | 512 | 73 | 123 W / 0.068 | 7.85 |
| 16r (powtórka) | 197.3 | 525 | 67 | 126 W / 0.074 | 7.66 |
| 32 | 94.1 | 127 | 285 | 185 W / 0.179 | 7.79 |

- **PCIe RX przybite do ~7.2–7.9 GB/s przy każdym c≥8** — ten sam sufit co
  Qwen TP8 c64 (7.18) → transportowy, niezależny od modelu.
- **Anomalia c=16 jest realna** (powtórka ±3%): krok 4× gorszy niż c=32 przy
  *niższej* mocy i SMACT. Akceptacja Eagle3 stabilna ~2.67 we wszystkich
  oknach — to nie spekulacja. Podejrzany: scheduler/batch-składanie przy
  c=16 z `max-num-seqs 32`. Patologia software'owa — c=32 "naprawia" ją bez
  żadnego hardware'u.

## K2 — profil Kimi TP8 @ c=16 (w patologii)

Trace rank0, span 67 s (`kimi_ramp/trace_summary_rank0.txt`); bench w trakcie
profilu odtworzył patologię (ITL med 535 vs 525 — narzut ~2%).

| bucket | udział spanu |
|---|---:|
| comms (NCCL) | **83.9%** |
| gaps | 10% |
| compute | 4.6% |

Kontrast z c=1 (sesja 06-10: gaps 63%, NCCL 22.5%): batched Kimi odwraca
strukturę — z floor-bound w comms-bound.

## Q1 — Qwen TP8 ramp → próg c\*

| c | TPOT med (ms) | out tok/s | PCIe RX (GB/s) |
|---:|---:|---:|---:|
| 1 | 5.12 | ~190 | — |
| 4 | 7.05 | 365 | 4.39 |
| 16 | 30.5 | 437 | 6.83 |
| 64 | — | 257 | 7.18 |

Szczyt ~c=16 (437 tok/s), załamanie do c=64 dokładnie przy dobiciu RX do
sufitu. SMACT płaskie 0.05–0.07 — TP8 transport-bound w całym zakresie.
Nawet w szczycie TP8 = ~1/3 wyniku TP2 (1404 tok/s). Dla Qwen-klasy TP8
to błąd konfiguracji, nie kandydat na NVLink.

## Q3 — TP4 cross-island (0,1,4,5) vs intra (0–3) → capture

| | intra | cross-island |
|---|---:|---:|
| c1: TPOT / ITL med (ms) | 4.00 / 10.54 | 3.99 / 10.37 |
| c64: ITL med (ms) / out tok/s | 53.7 / 680 | 48.3 / 716 |

Placement zweryfikowany (`CUDA_VISIBLE_DEVICES=0,1,4,5`). **Kara UPI: zero**
(cross ~5% lepszy przy c64 — prawdopodobnie NUMA-spread hosta). Potwierdza
A4: dawką jest liczba ranków + sufit transportu, nie klasa linku.
Wniosek dla NVLink 4-way: wyspa 4 GPU przejmuje ~100% ruchu TP4
(capture = 1.0); dla TP8 na 2 wyspach capture ≈ 0.75 (6/8 odcinków ringu).

## Q4 — profil Qwen TP4 intra @ c=64

Trace rank0, span 55 s (`qwen/trace_summary_tp4_c64_rank0.txt`); kontrola
narzutu: ITL med 49.6 profilowany vs 53.7 bez — reprezentatywny.

| bucket | udział spanu |
|---|---:|
| comms (NCCL) | **53.3%** |
| gaps | 33% |
| compute | 5.6% |

Zbieżność dwóch metod: share 0.53 z trace ≈ 52% spadku przepustowości
TP2→TP4 (1404→680 tok/s; usunięcie share 0.533 podnosi 680 → ~1456 ≈ 1404
z TP2). Caveat: okno zawiera prefill-burst 64 promptów
(TTFT med 21.8 s) — share czystego decode raczej wyższy.

## F — ledger podłogi (TP1, c=1, random 64/512; dawki)

| dawka | krok/ITL med (ms) | TPOT med (ms) | moc / SMACT |
|---|---:|---:|---|
| base (MTP + cudagraphs) | 8.93 | 3.39 | 94 W / 0.052 |
| nospec (MTP off) | 5.36 | 5.36 | 92 W / 0.053 |
| eager (cudagraphs off) | 55.1 | 19.6 | 78 W / 0.009 |
| perfgov (governor performance) | 9.86 | 3.70 | — |

- **Orkiestracja MTP: 3.57 ms/krok = 40% podłogi** (dose-izolowane). Spec
  i tak wygrywa na TPOT (3.39 vs 5.36) dzięki akceptacji ~2.6.
- **Cudagraphs maskują ~46 ms/krok launch-overheadu** (eager: SMACT 0.009 —
  czysty launch-bound). Podłoga jest hostowo-launchowa z natury.
- Pozostałość 5.36 ms = forward + host scheduling/sampling. **Governor
  uniewinniony (F6):** `performance` daje 9.86 ms vs 8.93 base — zero zysku
  (różnica powyżej pasma szumu w złą stronę; `schedutil` nie jest składnikiem
  podłogi). Restore governora udokumentowany.
- **F3 (profil TP1 c=1, `floor/trace_summary_tp1_c1.txt`):** trace skażony
  zimnym startem — bench bez warmupów złapał kompilację torch.compile
  (TOP cpu_op: dynamo/inductor ~0.77 s; gaps 73% spanu zawierają one-time
  compile). Jakościowo spójny (zero NCCL przy TP1, compute 8.6%); ilościowa
  atrybucja podłogi stoi na dawkach, nie na tym trace.

Sesja zamknięta częścią D': restore plain compose, smoke OK, manifest
artefaktów w `session/artifact_manifest.txt` (91 plików).

## TABELA WERDYKTU — kiedy NVLink 4-way ma sens (#50)

| scenariusz | werdykt | szacunek zysku | dowód |
|---|---|---|---|
| model mieści się na 1–2 GPU (Qwen-klasa) | **NO-GO** | ≈ 0 (tax TP2 +0.15 ms/krok; nop2p dose ≈ 0) | L2 przyczynowy |
| TP≥4 / TP8 dla modelu, który mieści się na mniej | **NO-GO** (błąd konfiguracji) | TP8 max 437 vs TP2 1404 tok/s | L2 |
| model wymaga TP=4, interactive c=1 | **NO-GO** | ≤ −28% TPOT teoretycznie (tax 1.56 ms = sync+transfer), realnie mniej | L2 (tax zmierzony) |
| model wymaga TP=4, **batched** | **GO warunkowe** | **~2.1×** (share 0.533, capture 1.0); dolne oszacowanie | L2 (trace + zbieżny rachunek efficiency) |
| Kimi-klasa TP8, interactive c=1 | **NO-GO** | ≤ 1.3× (NCCL 22.5%, gaps 63%) | L2 (trace) |
| Kimi-klasa TP8, **batched** | **GO** | **~2.7×** (share 0.839 @c16, capture 0.75); sufit 6.2× | L2 (trace) + liczniki c≥8 |

Zastrzeżenia werdyktu:

1. Share Kimi zmierzony w punkcie patologicznym c=16; c=32 (najlepszy punkt
   pracy) nie był profilowany — liczniki (RX na suficie, SMACT 0.18) wskazują
   tę samą sygnaturę, ale share przy c=32 to ekstrapolacja.
2. Czas NCCL zawiera in-kernel peer-wait — szybszy link nie usuwa całości;
   szacunki traktować jako optymistyczny środek.
3. Część kary c=16 może być usuwalna softwarem (c=32 działa 4× lepiej za
   darmo) — przed zakupem warto wyczerpać dźwignię konfiguracyjną.
4. Przy c=1 wszędzie rządzi podłoga (software: MTP-orkiestracja 40%,
   host/launch) — kable jej nie obniżą.

**Rekomendacja zakupowa:** NVLink 4-way ma uzasadnienie wyłącznie, jeśli
motywacją jest **throughput batched serwowania modeli wymagających TP≥4**
(szac. 2–3×). Dla latencji interaktywnej i modeli mieszczących się na
1–2 GPU — NO-GO. Decyzja = pytanie o profil obciążenia, nie o sprzęt.
