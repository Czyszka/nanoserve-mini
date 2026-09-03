# Podsumowanie sesji 2026-08-31/09-02 — latencja all-reduce, grid Qwen TP×c×łącze, profile TP1–TP8

Plan: `docs/plans/2026-08-31-latencja-dostepu-nvlink.md` (predykcje
pre-rejestrowane w §1). Dane: `results/runs/2026-08-31_latencja_dostepu/`
(commit `8d7ef5b`; start/end commit `9990bee`). Silnik Qwen: vLLM v0.20.0,
Qwen3.6-35B-A3B, MTP k=3, EP włączone, `--max-num-seqs 32`,
`--max-num-batched-tokens 8192`. Kimi zatrzymany na czas sesji.
Burn-in (Cz. 8) — poza zakresem nanoserve (test klimatyzacji serwerowni);
dane w `burnin/`, nieanalizowane tutaj.

**TL;DR:**

1. **NVLink nie skraca rundy all-reduce przy małych wiadomościach.** Przy
   4–16 KB (reżim c=1) runda trwa 28–54 µs niezależnie od łącza: wyspa-2
   27,9 µs vs nop2p 28,7 µs; wyspa-4 53,8 µs vs nop2p 30,6 µs. Podłoga
   ~28 µs to launch/protokół NCCL, nie transport. Predykcje mikro
   („wyspa-4 10–35 µs", „nop2p ≥ 3× wolniej") **obalone**.
2. **NVLink wygrywa przepustowością od ~512 KB w górę:** wyspa-4 @8 MB
   197,5 GB/s vs nop2p 13,8 GB/s (14×); wyspa-2 84,7 vs 14,1. Przecięcie
   krzywych latencji wyspa-4: między 64 KB (58 vs 39 µs — nop2p szybsze)
   a 512 KB (36 vs 130 µs — NVLink 3,6× szybsze).
3. **Mechanizm zysku do przepisania:** runda = koszt stały (~30 µs, łącze
   go nie zmienia) + przesył (∝ c × hidden / przepustowość). Przy c=1
   przesył jest pomijalny → NVLink ≈ 0 (Qwen TP4 c1 ITL wyspa 10,15 ms
   vs nop2p 8,71 ms; Kimi c1 1,2×). Pod obciążeniem przesył rośnie do
   setek KB → przepustowość rządzi → 2–3×. Teza „ogranicza nas czas
   rundy, nie przepustowość" (v1 prezentacji, slajd 12) — **wycofana**.
4. **Krzywa TP Qwen po NVLinku (c=32): 2015 / 2467 / 2990 / 1974 tok/s** —
   TP4 skaluje 1,48× vs TP1 (era PCIe c64: 1202 / 1404 / 680 / 257),
   TP8 nadal poniżej TP1. Replikacja TP4 c64: 2129 vs 2022/1989 (+5%).
5. **Profile Qwen, c=32, udział NCCL w spanie: TP1 0% → TP2 12% → TP4 18%
   → TP8 58%.** Kontrola narzutu profilera **nie przeszła** (ITL
   profilowany 1,1–2,5× nieprofilowanego) → trace'y jakościowe.
6. **Anomalia c=16 u Qwena nie występuje** przy żadnym TP ani łączu
   (ITL c16 11,5–22 ms, bez skoku).

---

## 1. Warstwa mikro — latencja all-reduce (Cz. 1)

`nvlink/nccl_lat_*.json`, 200 iteracji, fp16, `dist.all_reduce`; µs/op
(busbw GB/s w nawiasie):

| grupa | 4 KB | 16 KB | 64 KB | 512 KB | 8 MB |
|---|---:|---:|---:|---:|---:|
| wyspa-2 (0,1) | 29,8 | 27,9 | 28,3 | 28,1 (18,7) | 99,0 (84,7) |
| wyspa-2 nop2p | 29,7 | 28,7 | 28,5 | 60,2 (8,7) | 596,8 (14,1) |
| wyspa-4 (0–3) | 39,1 | **53,8** | 58,4 | 36,3 (21,7) | 63,7 (**197,5**) |
| wyspa-4 nop2p | 41,0 | 30,6 | 38,7 | 130,0 (6,0) | 912,9 (13,8) |
| cross-2 (0,4) | 30,9 | 29,3 | 63,4 | 76,1 (6,9) | 448,1 (18,7) |
| cross-4 (0,1,4,5) | 31,1 | 30,1 | 34,2 | 162,4 (4,8) | 458,6 (27,4) |
| all-8 | 41,1 | 36,1 | 69,5 | 141,6 (6,5) | 986,8 (14,9) |
| all-8 nop2p | 38,5 | 59,5 | 62,5 | 238,0 (3,9) | 953,1 (15,4) |

P2P 8 B (`p2p_lat.txt`, `copy_` w pętli, peer=True wszędzie): 0→1 12,9;
0→2 12,9; 0→3 24,3; 0→4 (cross) 25,9; 3→4 (cross) 16,1 µs.

**Werdykty predykcji mikro (§1 planu):**

| predykcja | pomiar | werdykt |
|---|---|---|
| P2P wyspa 1–3 µs (> 6 → problem) | 12,9–24,3 | **chybiona, ale test nieczuły**: 8-bajtowa kopia w pętli mierzy narzut launchu (~10–25 µs), nie łącze; 0→3 w wyspie 24 µs = 0→4 cross. Latencji P2P tym testem nie zmierzono. |
| P2P cross ≥ 4× wyspa | 2,0× (0→4 vs 0→1); 3→4 < 0→3 | **nierozstrzygnięta** (jw.) |
| NCCL 4–16 KB wyspa-4: 10–35 µs (> 70 → nie transport) | 39–54 µs | **chybiona w górę**, próg 70 nie przekroczony; wyspa-4 wolniejsza niż wyspa-2 (28) i niż własne nop2p (31) — runda małych wiadomości to launch/protokół, nie łącze |
| all-8 ≥ 2× wyspa-4 (kara cross latencyjna) | all-8 36 µs **<** wyspa-4 54 µs | **obalona**: kara cross-island nie jest latencyjna → capture 0,62 (#50) do rewizji jako efekt przepustowościowy |
| cross-2 wyraźnie > wyspa-2 | 29,3 vs 27,9 | **obalona** (≈): trasa nie kosztuje nawet mikro; H4 obalona głębiej |
| nop2p ≥ 3× NVLink (wyspa-4) | 16 KB: 30,6 vs 53,8 (nop2p szybsze); 8 MB: 913 vs 64 (NVLink 14×) | **obalona dla małych, potwierdzona dla dużych**; env doszło do ranków (busbw 13,8 vs 197,5; `nccl_path_island4*.txt`) |

Kontrola spójności: busbw wyspa-4 @8 MB 197,5 GB/s — w paśmie 185–333 z
07-31. NVLS multicast niedostępny (log NCCL) — kandydat na wyjaśnienie,
dlaczego wyspa-4 przy 16–64 KB jest wolniejsza niż wyspa-2 (algorytm
ring/tree na 4 rankach zamiast 2). **Otwarte.**

## 2. Warstwa end-to-end — grid Qwen (Cz. 2–7)

Nieprofilowane benche, ciepłe (po wygrzewce), SWE custom. Tok/s łącznie;
w nawiasie ITL med (ms). nop2p z mniejszym `num-prompts` (24/96/160/300
vs 40/192/320/600) — throughput nop2p mniej porównywalny, ITL tak.

| TP / wariant | c=1 | c=16 | c=32 | c=64 |
|---|---|---|---|---|
| TP1 | 255 (9,40) | 1438 (18,0) | 2015 (22,9) | 1710 (21,8) |
| TP2 wyspa (0,1) | 263 (9,13) | 1620 (14,4) | 2467 (17,5) | 2050 (16,8) |
| TP2 cross (0,4) | 267 (9,29) | 1427 (15,9) | 2058 (20,5) | 1689 (20,0) |
| TP2 nop2p | 276 (8,96) | 1170 (14,8) | 1674 (18,7) | 1985 (20,1) |
| TP4 wyspa (0–3) | 265 (10,15) | 1851 (11,5) | **2990 (13,5)** | 2129 (14,0) |
| TP4 cross (0,1,4,5) | 233 (10,8) | 1314 (16,7) | 1928 (23,6) | 1472 (23,5) |
| TP4 nop2p | 275 (8,71) | 1164 (13,4) | 1556 (17,6) | 1784 (18,9) |
| TP8 (2 wyspy) | 232 (11,3) | 1426 (16,3) | 1974 (22,3) | 1625 (21,9) |
| TP8 nop2p | 217 (11,1) | 825 (21,7) | 1041 (33,3) | 1248 (36,7) |

Bramki custom all-reduce (`allreduce_gate_*.txt`): TP4 wyspa **8**
(aktywny), TP4 cross **0**, TP8 **0** — zgodnie z geometrią wysp.

Liczniki DCGM, GPU0, okno c=32 (`qwen/*_c32_dcgmi.txt`; średnia z okna):

| wariant | moc (W) | SMACT | DRAMA | PCIe RX (GB/s) | NVL TX (GB/s) |
|---|---:|---:|---:|---:|---:|
| TP1 | 356 | 0,50 | 0,31 | 0,06 | 0 |
| TP2 wyspa | 276 | 0,41 | 0,22 | 0,07 | 5,1 |
| TP4 wyspa | 230 | 0,30 | 0,13 | 0,05 | 8,6 |
| TP4 cross | 180 | 0,19 | 0,09 | 7,7 | 6,7 |
| TP4 nop2p | 183 | 0,18 | 0,08 | 4,2 | 2,0 (resztkowe, poza NCCL) |
| TP8 | 152 | 0,13 | 0,05 | 7,6 | 6,9 |
| TP8 nop2p | 133 | 0,10 | 0,04 | 7,7 | 0,0 |

Obraz anomalii wraca z TP: moc 356 → 152 W, SMACT 0,50 → 0,13 przy tej
samej pracy. Sufit PCIe RX ~7,6–7,7 GB/s pojawia się wszędzie tam, gdzie
ruch przechodzi między wyspami (TP4 cross, TP8) albo przez hosta
(TP8 nop2p) — ten sam sufit co w erze PCIe (7,2–7,9).

**Werdykty predykcji e2e:**

| predykcja | pomiar | werdykt |
|---|---|---|
| TP4 wyspa c64 replikacja 1900–2100 | 2129 | **+1,4% ponad pasmo** (vs 2022: +5%) — dryf w granicach szumu ±6% pojedynczego biegu |
| ΔITL c1 TP1→TP8 ≤ ½ PCIe (+0,93/+1,56/+5,18) | −0,27 / +0,75 / **+1,91** | **potwierdzona** (TP8: 37% wartości PCIe) |
| TP2 cross vs wyspa c1 \|Δ\| ≤ 0,8 ms | 9,29 vs 9,13 (+0,16) | **potwierdzona** — H4 (kara trasy) nadal obalona |
| TP4 cross c64 ≤ 60% wyspy | 69% (c64), 64% (c32) | **chybiona o kilka p.p.**, daleko od progu 90% — kara cross-island realna, NCCL hierarchiczny nie maskuje jej w e2e; uwaga: cross traci też custom-AR (siatka niepełna) |
| nop2p TP4 c64 < 850 (> 1200 → inna ścieżka) | **1784** | **obalona**: nop2p nie odtwarza ery PCIe (680); resztkowy NVL 2,0 GB/s poza NCCL + SHM hosta szybsze niż P2P-po-PCIe z czerwca. Jak 08-03: nop2p = rekonstrukcja częściowa |
| nop2p TP8 c32 spadek ≥ 2× | 1041 vs 1974 = **1,90×** | **na granicy** (ITL 33,3 vs 22,3 = 1,5×); NVL = 0 w DCGM — dawka zadziałała w pełni przy TP8 |
| spójność ΔITL c1 ≈ 2L × r_micro (w 2×) | TP8: +1,91 ms vs 2L×36 µs; TP2: −0,27 ms vs 2L×28 µs; TP4: +0,75 vs 2L×54 µs | liczba warstw L Qwen3.6 nieodczytana (`qwen_config_dims.txt`: None — config zagnieżdżony). Dla L=48: TP8 3,5 ms (1,8× pomiaru — **w granicach 2×**); TP2/TP4 2,7 / 5,2 ms vs ≤0,75 (**rozjazd > 3×**) — rund nie widać w kroku: custom-AR (TP4), overlap/CUDA graphs. Wynik sam w sobie, jak przewidywał plan |

**c=64 < c=32 we wszystkich wariantach** — wyjaśnione konfiguracją:
`--max-num-seqs 32` ogranicza batch do 32 sekwencji; przy c=64 reszta
czeka w kolejce (TTFT med 3–5 s vs 0,2 s), a prefill-bursty obniżają
throughput. Do porównań z historią (c64 2022) używać c64; do krzywej TP
„czysty decode" używać c=32.

## 3. Profile Qwen po NVLinku (Cz. 2–5, torch profiler, rank0)

Udział w spanie (%): comms / compute / other / gaps
(`profile/trace_summary_*.txt`; bucket wg nazwy kernela — metoda 08-03).

| TP | c=1 | c=16 | c=32 |
|---|---|---|---|
| TP1 | 0 / 24 / 48 / 28 | 0 / 41 / 36 / 23 | 0 / 45 / 37 / 19 |
| TP2 wyspa | 0,7 / 12 / 27 / 60 | 2,8 / 22 / 26 / 48 | 12 / 28 / 43 / 17 |
| TP4 wyspa | 2,9 / 15 / 50 / 33 | 1,5 / 12 / 17 / 69 | 18 / 19 / 45 / 18 |
| TP8 | **69** / 8 / 18 / 5 | 36 / 6 / 10 / 47 | **58** / 11 / 17 / 13 |

**Kontrola narzutu profilera — NIE PRZESZŁA.** ITL profilowany /
nieprofilowany: TP1 1,34 / 1,22 / 1,09; TP2 2,53 / 1,34 / 1,27; TP4 1,40 /
2,09 / 1,53; TP8 2,02 / 1,41 / 1,17 (c1 / c16 / c32). Tylko TP1 c32 i TP8
c32 w paśmie ±15%. Przyczyny: (a) benche profilowane miały 8/16/32
promptów i 3–20 s trwania — okno zdominowane prefill-burstem (TTFT med
0,8–2,6 s przy c≥16) i rozgrzewką, nie stanem ustalonym decode;
(b) narzut samego profilera. **Trace'y tej sesji są jakościowe**
(kierunek, rzędy wielkości), nie ilościowe. Jedyny profil ilościowy
w projekcie pozostaje Kimi c32 z 08-03 (−9%).

**Werdykty predykcji profili:**

| predykcja | pomiar | werdykt |
|---|---|---|
| TP1 c1 gaps > 50% (host-bound) | 28% gaps, 48% „other" | **obalona** (< 30%): Qwen TP1 c1 nie jest gap-bound; bucket „other" (kernele niesklasyfikowane: MTP, sampling, kopie, GDN?) wymaga rozbicia, zanim H3 zostanie przeniesiona na Qwena |
| TP4 c32 NCCL 20–45% | 18% | **o 2 p.p. poniżej pasma**; sufit Amdahla dla TP4 po NVLinku niski — spójne z e2e (TP4 = optimum) |
| TP8 c32 NCCL > TP4 c32 | 58 > 18 | **potwierdzona** |
| NCCL% rośnie z c (każde TP) | TP2 ✓ (0,7→2,8→12); TP4 ✗ (2,9→1,5→18; c16 = 69% gaps — artefakt krótkiego okna); TP8 ✗ (**69**→36→58) | **niepotwierdzona**; TP8 c1 comms-bound (69%, gaps 5%) — Qwen na 8 kartach czeka na all-reduce nawet przy jednym kliencie, inaczej niż Kimi c1 (63% gaps) |
| narzut profilera ±15% | 1,09–2,53× | **nie przeszła** (jw.) |

## 4. Co z tego wynika dla modelu mechanizmu (#50, T9, prezentacja)

- Model `T(krok) = F_host + N_rounds × r + W_silicon` z jednym `r(łącze)`
  jest za prosty: `r = r_0 + bajty/B`, gdzie `r_0 ≈ 28–54 µs` **nie
  zależy od łącza**, a `B` tak (14 → 85–197 GB/s w wyspie). Stąd zysk ≈ 0
  przy c=1 i 2–3× pod obciążeniem — bez odwoływania się do „latencji
  NVLink 2–9 µs" z literatury (A100/V100), której na H200 NVL z mostkiem
  4-way nie widać.
- Capture 0,62 dla Kimi TP8 (2 wyspy): kara cross nie jest latencyjna
  (all-8 36 µs < wyspa-4 54 µs), tylko przepustowościowa (all-8 @8 MB
  14,9 GB/s = poziom nop2p; cross-4 27,4). TP8 przez dwie wyspy jeździ
  dużymi wiadomościami w tempie PCIe/UPI — dlatego 2,08×, nie 2,97×.
- Kara cross-island w e2e (TP4: 64–69% wyspy) — pierwsza bezpośrednia
  kwantyfikacja; obejmuje utratę custom-AR.
- Do prezentacji v2 (slajdy 7–9): koszt stały + przesył; tabela
  „koszt stały bez zmian / przesył 14× szybciej"; wyspy tłumaczą 2× vs 3×.

## 5. Sprawy otwarte

1. Wyspa-4 wolniejsza niż wyspa-2 i niż nop2p przy 16–64 KB (54 vs 28/31
   µs) — algorytm NCCL na 4 rankach bez NVLS? Sprawdzić `NCCL_ALGO`/
   `NCCL_PROTO` (LL/LL128/Simple) w logu; ewentualnie 1 przebieg z
   `NCCL_PROTO=LL` w następnym slocie.
2. Test P2P do poprawy: większy bufor (np. 64 KB–1 MB) i pomiar bez
   launch-overheadu (batch kopii w CUDA graph) — obecny wynik nie mówi
   nic o łączu.
3. Liczba warstw/hidden Qwen3.6-35B-A3B — odczytać z `text_config`
   (config zagnieżdżony); potrzebne do rachunku `2L × r` i rozmiaru
   wiadomości.
4. Bucket „other" 17–50% spanu — rozbić po nazwach kerneli (MTP head,
   GDN attention, sampling), zanim udziały trafią na slajd/do T9.
5. Profile ilościowe: powtórzyć z pełnym `num-prompts` (≥ 192 przy c≥16)
   i profilem uruchamianym po ustaleniu się decode (opóźniony
   `/start_profile`), żeby kontrola ±15% przeszła.
6. Kimi po NVLinku, c=8 — jeden bieg z rampu 08-03 (17,5 ms TPOT);
   powtórka na SWE custom, jeśli tabela „ilu użytkowników → ile sekund"
   idzie na slajd.

## 6. Ścieżki dowodowe

- Mikro: `nvlink/nccl_lat_{island2,island4,cross2,cross4,all8}[_nop2p].{json,txt}`,
  `nvlink/lat_summary_quick.txt`, `nvlink/nccl_path_island4{,_nop2p}.txt`,
  `nvlink/p2p_lat.{json,txt,py}`, `nvlink/nccl_lat.py`.
- E2E: `qwen/bench_<wariant>/<wariant>_c{1,16,32,64}.json` (+ `_prof`),
  `qwen/engine_cmd_<wariant>.json`, `qwen/engine_env_<wariant>.txt`,
  `qwen/log_<wariant>.txt`, `qwen/allreduce_gate_*.txt`.
- DCGM: `qwen/<wariant>_c<c>_dcgmi.txt` + `*_start/end_epoch.txt`
  (pola 155,1002,1004,1005,1009,1010,1011,1012).
- Profile: `profile/trace_summary_<wariant>_c<c>_prof.txt`,
  `profile/trace_files_listing.txt`; trace'y poza repo:
  `profile/trace_local_path.txt` (ubuntusrv2).
- Sesja: `session/{start,end}_commit.txt`, `session/nvidia_smi_{start,end}.txt`,
  `session/gpu_free_check.csv`, `session/qwen_config_dims.txt`.
