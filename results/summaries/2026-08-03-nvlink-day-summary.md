# Podsumowanie dnia 2026-08-03 — NVLink: dekompozycja, trace, wygrzewka, para screenów

Cztery sesje serwerowe jednego dnia domykające program pomiarowy po montażu
mostków NVLink 4-way (07-31). Wszystkie dane w repo; ścieżki w §7.

**TL;DR:** (1) mechanizm zysku Kimi potwierdzony trace'em — udział NCCL w spanie
spadł z 83,9% (PCIe) do **61,1%** (NVLink), cały zysk 2,08× przyszedł z
komunikacji, która pozostaje dominującym składnikiem; (2) zagadka nieudanej
replikacji Qwen TP4 rozwiązana — to nie dryf i nie liczniki, tylko **kara
zimnego pierwszego benchu po starcie silnika (10–15%)** — od dziś obowiązuje
reguła wygrzewki; (3) dawka kernela custom-AR przy c64 pozostaje w przedziale
**1,0–1,2×** (szum pojedynczego biegu ±6% uniemożliwia węższy przedział bez
protokołu A/B/A/B); (4) para screenów Grafany przed/po mostkach istnieje
(replikacja rampu T5), zrzut nvidia-smi „100% util / ~175 W" do hooka
prezentacji zrobiony; (5) `NCCL_P2P_DISABLE=1` NIE jest pełnym logicznym
odłączeniem mostków — resztkowe ~4 GB/s NVL jeździ ścieżkami poza NCCL-em.

---

## 1. Sesje dnia i commity

| sesja | commit danych | katalog wyników |
|---|---|---|
| Gap-fill (rozdzielenie dawki, c16@192, liczniki NVL) | `7c91f3d` | `results/runs/2026-08-03_nvlink_gap_fill/` |
| Trace Kimi c32 + TP4-AR z licznikami NVL | `ed7c9ce` | `results/runs/2026-08-03_kimi_trace_nvlink/` |
| Dogrywka: test dryfu B1/B2/B3 + fix rank7 | `7ac1b01` | `…_kimi_trace_nvlink/qwen/bench_drift/` |
| Domknięcie: ciepły noAR, nop2p, ramp Grafana | `b717ad1` | `results/runs/2026-08-03_domkniecie_grafana/` |

Plany sesji: `docs/plans/2026-08-03-{nvlink-gap-fill,kimi-trace-nvlink,drift-test-domkniecia,domkniecie-grafana-nop2p}.md`
(predykcje pre-rejestrowane w §1 każdego planu).

## 2. Trace Kimi TP8 c32 po NVLinku — mechanizm #50 domknięty

| podział spanu | PCIe @c16 (06-11, w anomalii) | NVLink @c32 (08-03) |
|---|---:|---:|
| NCCL/comms | 83,9% | **61,1%** (rank0) / 59,7% (rank7) |
| compute | 4,6% | **30,2%** / 30,3% |
| other | — | 8,4% |
| gaps | — | ~0–2% |

- Kontrola narzutu profilera: bench profilowany c32 ITL med 82,1 ms vs 90,2 ms
  unprofiled → **−9%, w paśmie ±15%** — trace ilościowy.
- Arytmetyka spójna: komunikacja skompresowana ~2,9× (0,839·T → 0,294·T),
  reszta ~stała → **cały zysk 2,08× przyszedł z komunikacji**; implikowany
  capture 0,62 zgodny z benchowym.
- Konsekwencja: NCCL to nadal ~61% spanu — sufit dalszej poprawy komunikacji
  (pełna siatka / NVSwitch) jest realny: teoretycznie do ~2,6× na Kimi TP8.
- Symetria ranków rank0/rank7 w 1,4 p.p. — liczba wiarygodna.
- Trace'y (8×~90 MB) poza repo: `/home/ubuntusrv2/working/nanoserve-tracing/kimi_c32_nvlink_2026-08-03`;
  drugi profil @c16 (Cz. 4b) — bench JSON zachowany (618 tok/s, ITL 50,1),
  same trace'y stracone (nieskopiowane przed force-recreate).

## 3. Kara zimnego startu — rozwiązanie zagadki replikacji

Nieudana replikacja TP4-AR (1747 vs 2022 przy identycznych `engine_cmd` i
`engine_env`) doprowadziła do testu dryfu (B1/B2/B3), a ten do ustalenia:

**Drabinka TP4 c64 (8 pomiarów, wszystkie konfiguracje):**

| wariant | zimny (1. bench po starcie) | ciepły (po wcześniejszym benchu) |
|---|---|---|
| z custom-AR | 1747 (trace), 1851 (B1) | 1989, 2022 (07-31), **2040 (B2)** |
| bez custom-AR | 1748 (gap-fill) | **1655 (domknięcie)** |

- Na 07-31 każdy c64 biegł PO c1 (epochs: 09:49→09:51, 10:01→10:02) — ciepły.
  Na 08-03 rano każdy c64 był pierwszy — zimny. B1 (bez dcgmi) 1851 vs B2
  (ZE samplerem, stare pola) 2040 pogrzebał hipotezę kosztu liczników.
- **Kara zimnego startu: 10–15%.** Sampler dcgmi i pola NVL 1011/1012 —
  niewinne. Dryfu dnia nie ma (B2 replikuje 07-31 w ±2,5%).
- Retroaktywnie wyjaśnione: Kimi c16@192 501 (zimny) vs c16@96 538 (ciepły,
  07-31); TP2-NVLink 1530 (zimny, jedyny bieg) — niedoszacowany.
- **REGUŁA (od 08-03): po każdym starcie silnika bench-wygrzewka na odrzut,
  dopiero potem pomiar.** Do wpisania w `benchmark-methodology.md`.

## 4. Dekompozycja link/kernel — stan końcowy

- Pakiet (ciepły AR ~2017 vs PCIe 680): **~2,97×** — bez zmian.
- **Dawka kernela custom-AR @c64: przedział 1,0–1,2×, nierozstrzygnięta.**
  Zimny-zimny (1747 vs 1748) → 1,00×; ciepły-ciepły (2017 śr. vs 1655) →
  1,22×; przy szumie ±6% pojedynczego biegu (zimne AR: 1747–1851; ciepły noAR
  1655 < zimny noAR 1748) rozstrzygnięcie wymaga protokołu A/B/A/B n≥3.
  Świadomie NIE planujemy takiej sesji — dla werdyktu #50 bez znaczenia.
- Dawka kernela @c1: **realna, ~+8%** — TPOT 3,30 (AR, B3, replikuje 3,21
  z 07-31) vs 3,58 (noAR); ciepły warmup-c1 noAR 3,80 potwierdza kierunek.
- Liczniki NVL widzą ruch custom-AR: TP4-AR 3,78 GB/s avg vs noAR 4,68 —
  kernel przenosi ~19% mniej bajtów przy zbliżonym throughputcie.
- Link-only (ciepłe 07-31 vs PCIe): nadal > sufit Amdahla 2,14× ze starego
  share 0,533 — po trace'ie wiemy, że stary share z K2/Q4 zawierał peer-wait
  i nie był czystym czasem transferu; do przepisania w T9.

## 5. Rekonstrukcja „przed mostkami" (nop2p) + materiał wizualny

- Kimi TP8 c32 z `NCCL_P2P_DISABLE=1`: **458 tok/s** (NVLink: 594–608;
  PCIe-era: 285), ITL 80 ms. Moc w klatkach zrzutu: **172–181 W przy 100%
  util na 8 GPU** — obraz hooka W0 uzyskany (`nvidia_smi_nop2p.png`).
- **Dawka częściowa (ustalenie):** PCIe RX wrócił na stary sufit (7,10 GB/s
  vs 7,2–7,9 z ery PCIe) → NCCL faktycznie zszedł na hosta; ale NVL TX nadal
  **4,03 GB/s** — ścieżki poza NCCL-em (kopie P2P torch/vLLM) nie podlegają
  tej fladze. Stąd 458 > 285. Etykieta na slajd: „NCCL bez P2P — częściowa
  rekonstrukcja reżimu comms-bound; resztkowy ruch NVL 4 GB/s poza NCCL;
  historyczne PCIe: 111–185 W (dcgmi 06-11)".
- **Para screenów Grafany przed/po** (replikacja rampu T5 A c4/120 → B c16/300
  → C c64/600): `2026-08-03_grafana_dashboard-nvlink-max_num_seqs_32.png` vs
  `2026-06-05_grafana_dashboard-max_num_seqs_32.png`. Faza C: 552 tok/s,
  TTFT med 12,6 s (kolejka nabita — panel waiting świecił). Uwaga: benche
  klienckie z 06-05 nie są w repo (tylko snapy Prometheusa) — podpis liczbowy
  „przed" ze snapów `t5_metrics/`, albo para zostaje wizualna. #34
  „screenshot pod obciążeniem" — DOMKNIĘTE.
- Schodki bonus (c1→c64): 55 / 328 / 596 / 563 / 611 tok/s — spójne z
  gap-fillem (c32 608).

## 6. Braki i sprawy otwarte

- `dmesg_end.txt` (gap-fill) — czwarte podejście nie wykonane; plik nadal
  0 B. Do zrobienia przy następnym SSH (komenda z gwarancją niepustego pliku
  w planie domknięcia, Cz. 1). #51 zad. 1 otwarte.
- `trace_c16_status.txt` — notatka o straconych trace'ach c16 nie powstała
  (ta wiedza jest w tym summary; plik przy okazji).
- Kimi c16 przy 192 promptach na ciepłym silniku — obecne 501 to zimny bieg;
  wartość informacyjna niska (ITL identyczny), nie planujemy.
- `NCCL_NVLS_ENABLE=1` w compose Qwena — do usunięcia TERAZ (dzień pomiarowy
  zamknięty, porównywalność już niepotrzebna).

## 7. Ścieżki dowodowe

- Trace summary: `results/runs/2026-08-03_kimi_trace_nvlink/profile/trace_summary_c32_rank{0,_last}.txt`
- Drabinka TP4: `…_nvlink_gap_fill/qwen/bench_tp4_noAR/`, `…_kimi_trace_nvlink/qwen/bench_tp4_ar/`,
  `…_kimi_trace_nvlink/qwen/bench_drift/`, `…_domkniecie_grafana/qwen/bench/`,
  `results/runs/2026-07-31_nvlink_install/qwen/bench_tp4_nvlink*/`
- Kolejność biegów 07-31 (dowód wygrzewki): `…_nvlink_install/qwen/qwen_tp4_nvlink*_start_epoch.txt` + pola `date` w JSON-ach
- nop2p: `…_domkniecie_grafana/kimi/` (bench, dcgmi z NVL, nvidia-smi txt) + PNG w katalogu głównym runu
- Ramp T5 + para: `…_domkniecie_grafana/grafana/bench/` + PNG; stary screen w `results/runs/2026-06-05_w1_evidence/`
- Liczniki NVL (gap-fill): `…_nvlink_gap_fill/{kimi,qwen}/*_dcgmi.txt` (pola 1011/1012)
