# Plan: prezentacja meetupowa — „Historia NVLink" (draft)

Status: **draft** — wracamy po sesji gap-fill 08-03
(`docs/plans/2026-08-03-nvlink-gap-fill.md`); jej wyniki mogą wzmocnić puentę 1
(rozdzielenie dawki custom all-reduce od dawki łącza).

## Kontekst

Prezentacja na meetup/konferencję (po polsku, ~20 slajdów, pełne speaker notes,
format: samowystarczalny HTML) opowiadająca techniczną historię z tego repo:
obserwacja → hipotezy → proces badania → propozycja rozwiązania z predykcją
(prawo Amdahla) → pomiary po montażu NVLink 4-way → podsumowanie przed/po.

Ustalenia z 2026-07-31:

- Format: HTML (slajdy z nawigacją klawiaturą), commit na `main`.
- Język: polski.
- Wykresy: matplotlib z prawdziwych, commitowanych danych + diagram topologii.
- Speaker notes: pełne (3–6 zdań narracji na slajd), panel pod klawiszem `N`.

## Struktura prezentacji (20 slajdów)

1. **Tytuł** — „**100% GPU-Util — a karty się nudzą**. Śledztwo performance na
   8×H200, które skończyło się zakupem NVLink" (podtytuł: vLLM, Kimi-K2.6 ~1T,
   prawo Amdahla).
2. **Kontekst** — lab nanoserve-mini; sprzęt: Supermicro SYS-521GE-TNRT,
   2× Xeon Gold 6530, 8× H200 NVL 143 GB, **PCIe-only**; modele: Kimi-K2.6
   (~1T, 554 GB wag, TP8+Eagle3) i Qwen3.6-35B (model testowy).
3. **Obserwacja otwierająca (hook)** — `nvidia-smi` pod obciążeniem: GPU-Util
   100%, a pobór mocy tylko ~180–240 W z 600 W. Głębiej (DCGM): SMACT ~0,2,
   DRAM_ACTIVE 0,07–0,09, moc 169–199 W — **nic nie jest nasycone**; GPU-Util
   mierzy „czy cokolwiek się dzieje", nie „czy krzem pracuje" (WYKRES W2).
4. **Zastanowienie: co może dawać taki obraz?** — przestrzeń hipotez, każda
   z przewidywaniem w licznikach: **H1** memory-bound/HBM (wysoki DRAM_ACTIVE —
   a jest 0,07–0,09), **H2** komunikacja między GPU po PCIe, **H3** podłoga
   hosta (CPU/launch/orkiestracja spekulacji), **H4** kara UPI za cross-socket.
   H1 odpada od razu z liczników; H2–H4 wymagają eksperymentów → plan śledztwa.
5. **Problem skwantyfikowany** — krzywa TP Qwen c=64: 1202/1404/680/257 tok/s,
   scaling eff. 100/58/14/**2,7%** (WYKRES W1); PCIe RX przyklejony do
   **7,2–7,9 GB/s** niezależnie od modelu.
6. **Analogia edukacyjna** — kurs furgonetki kurierskiej (T9 §2): jazda=compute,
   ronda=all-reduce (~2/warstwę, Kimi ~122 scalenia/krok), papierkowa
   robota=F_host.
7. **Topologia PRZED** — diagram: 2 CPU ↔ UPI, 4 switche PCIe 5.0 x16, pary GPU
   (bus-ID 1D/1E, 40/41, AA/AB, BB/BC), klasy ścieżek PIX/NODE/SYS (DIAGRAM D1).
8. **Śledztwo 1: dawki przyczynowe** (test H4 i taniości comms) — A4
   cross-socket: UPI niewinne (9,13 vs 9,91 ms); nop2p: negatywny (1404→1396);
   kalibracja szumu ±0,4 ms → delty TP4/TP8 to 4×/13× szumu. Winowajca:
   **liczba ranków + sufit transportu**. **H4 obalona.**
9. **Śledztwo 2: trace'y** (H2 vs H3) — udziały span: Kimi c=1 → gaps 63% /
   NCCL 22,5% / compute 9% (**floor-bound → H3 przy c=1**); Kimi c=16 → NCCL
   **83,9%** (**comms-bound → H2 pod batchem**); Qwen TP4 c=64 → NCCL 53,3%
   (WYKRES W3). Obie hipotezy prawdziwe, każda w swoim reżimie współbieżności.
10. **Zbieżność dwóch metod** — 680 ÷ (1−0,533) ≈ 1456 ≈ 1404 tok/s (TP2).
    Plus zagadka: **anomalia c=16** (ITL 512 ms, reprodukowalna ±3%) — werdykt:
    „software/scheduler".
11. **Model parametryczny** — `T(krok) = F_host + N_rounds × r(łącze, ranki) +
    W_silicon`; ledger podłogi: MTP 40% kroku, cudagraphs maskują ~46 ms,
    governor uniewinniony.
12. **Propozycja: NVLink 4-way + Amdahl** — `S_nvlink = 1/(1 − s·capture·
    (1−128/900))`; tabela S_ideal/S_nvlink: TP4 c64 **2,14/1,84**, Kimi TP8
    batched **2,70/2,18**, c=1 ≤1,3×; werdykt #50: GO tylko batched TP≥4.
13. **Predykcje pre-rejestrowane** (plan 07-31 §1, „nie edytuj po fakcie"):
    P2P >100 GB/s, NCCL busbw >100, Qwen TP4 c64 680→**~1430**, Kimi c32
    285→**~770**, c=1 bez zmian, **anomalia c16 zostaje**, PCIe RX spada —
    z progami falsyfikacji.
14. **Montaż** — 2 wyspy (GPU 0-3, 4-7); topologia PO: NV6 w wyspach, SYS
    między (DIAGRAM D1 wariant PO); bramka custom-AR: Qwen warning znika
    (kernel aktywny) / Kimi zostaje (4+4 ≠ pełna siatka przy TP8) — para
    zgodna z przewidywaniem.
15. **Weryfikacja mikro** — P2P 132,8 (wyspa) vs 29,1 (cross); NCCL busbw
    185–333 GB/s (wyspa) vs 24,8–31,3 (2+2) vs stary sufit 7,2–7,9
    (WYKRES W4, skala log).
16. **Weryfikacja end-to-end** — Qwen TP4 c64: 680→**2022 tok/s (2,97×)**;
    Kimi c32: 285→**594 (2,08×)**; c=1 ~20% zysku (WYKRES W5, przed/po +
    markery predykcji).
17. **Puenta 1: model mylił się w obie strony** — Qwen 2,97× **ponad sufit
    modelu 2,14×** (odblokowany custom all-reduce + zniknięcie kontencji —
    dawka była podwójna); Kimi 2,08× < 2,7× (implikowany capture 0,62 vs
    założone 0,75).
18. **Puenta 2: anomalia c16 ZNIKŁA** — ITL 512→48,6 ms; predykcja „zostaje"
    obalona — była transportowa, nie schedulerowa. Falsyfikacja zadziałała
    dokładnie tak, jak zaprojektowano (WYKRES W6: ramp ITL Kimi przed/po).
19. **Podsumowanie przed/po + lekcje** — tabela zbiorcza; wnioski: GPU-Util
    kłamie — patrz na moc/SMACT/DRAM; stawiaj hipotezy z przewidywaniami;
    dawki przyczynowe > korelacje; pre-rejestruj predykcje; Amdahl wymaga
    znajomości `capture` i ukrytych dawek.
20. **Co dalej + kontakt** — gap-fill 08-03 (rozdzielenie dawki
    `--disable-custom-all-reduce`, liczniki NVL, Kimi c16@192), link do repo.

## Wykresy (matplotlib → SVG, osadzone inline w HTML)

Dane wyłącznie z commitowanych plików:

- **W1** krzywa TP Qwen c=64:
  `results/runs/2026-06-11_bottleneck/qwen_tp_curve/bench_tp{2,4,8}/tp*_c64.json`
  + TP1 z summary (1202, adnotacja źródła) — słupki tok/s + linia efektywności.
- **W2** „100% util vs rzeczywistość": GPU-Util 100% zestawione z mocą
  (169–240 W z 600 W), SMACT (~0,2), DRAM_ACTIVE (0,07–0,09) — z tabel
  `results/summaries/2026-06-11-qwen-tp-curve.md`,
  `results/summaries/2026-06-11-nvlink-boundary-verdict.md` i notatki
  decyzyjnej §6.1.
- **W3** udziały trace (3 scenariusze, słupki skumulowane): gaps/NCCL/compute —
  z summaries.
- **W4** P2P + NCCL busbw przed/po:
  `results/runs/2026-07-31_nvlink_install/nvlink/{p2p_bw.json,nccl_allreduce.json,nccl_allreduce_island0.txt}`
  vs sufit PCIe 7,2–7,9.
- **W5** end-to-end przed/po z markerami predykcji: bench JSONy 06-11 vs
  `results/runs/2026-07-31_nvlink_install/{qwen,kimi}/bench*/*.json`.
- **W6** Kimi ramp ITL przed/po (c=1/8/16/32; po montażu brak punktu c=8 —
  adnotacja na wykresie).
- **D1** diagram topologii przed/po — ręczny inline SVG wg
  `docs/operations/infrastructure.md` (diagram ASCII) + macierzy
  `results/runs/2026-06-11_bottleneck/session/nvidia_topo.txt` (przed) /
  `results/runs/2026-07-31_nvlink_install/nvlink/topo_m.txt` (po).

## Pliki do utworzenia (na `main`)

```text
docs/presentations/2026-07-31-nvlink-meetup/
├── index.html            # samowystarczalne slajdy (pełny dokument HTML)
├── generate_charts.py    # reprodukcja W1–W6 z commitowanych danych → SVG
└── charts/*.svg          # wygenerowane wykresy (małe, tekstowe)
```

- `generate_charts.py` uruchamiany przez `uv run --with matplotlib python ...` —
  bez dodawania matplotlib do `pyproject.toml`.
- HTML: lekki własny framework slajdów (strzałki/PgUp/PgDn, licznik slajdów,
  panel notatek pod `N`, motyw jasny/ciemny), SVG wykresów inline.

## Kolejność wykonania

1. `generate_charts.py` → W1–W6 (walidacja liczb ze źródłami wymienionymi wyżej).
2. `index.html` (20 slajdów + speaker notes + inline SVG + diagram D1).
3. Walidacja: `uv sync --extra dev`, `uv run ruff check .`, `uv run pytest`
   (dochodzi `.py`), `git diff --check`.
4. Aktualizacja `docs/operations/agent-state.md` (wpis handoff + In flight).
5. Commit + push na `main`.

## Kluczowe liczby (zweryfikowane ze źródłami)

Krzywa TP c=64: 1202 / 1404 / 680 / 257 tok/s (eff. 100/58/14/2,7%). Sufit PCIe
RX 7,2–7,9 GB/s. Trace: c1 gaps 63%/NCCL 22,5%; c16 NCCL 83,9%; Qwen TP4 c64
NCCL 53,3%. Amdahl: S_nvlink TP4 c64 1,84 (ideal 2,14); Kimi TP8 batched 2,18
(ideal 2,70). Predykcje: Qwen ~1430 (próg <850), Kimi ~770 (próg <400), c16
„zostaje". Po montażu: P2P 132,8/29,1; NCCL busbw 185–333 vs 24,8–31,3; Qwen
2022 (2,97×); Kimi 594 (2,08×); c16 ITL 512→48,6 ms; Qwen c1 TPOT 3,21 ms;
Kimi c1 TPOT 7,44 ms; bramka custom-AR: znika/zostaje.
