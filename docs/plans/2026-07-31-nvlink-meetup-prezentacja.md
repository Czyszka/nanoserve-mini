# Plan: prezentacja meetupowa — „100% GPU-Util, a tylko 1/3 mocy" (aktywny)

Status: **active** — struktura v3 zatwierdzana w sesji interaktywnej
2026-08-09: **szkieletem prezentacji jest 20-krokowy protokół badania**,
studium przypadku (serwer 8×H200, NVLink) jest wypełnieniem. Poprzednie
wersje (20 slajdów „historia NVLink"; 18 slajdów „hipotezy H1–H4") — w
historii gita.

## Kontekst i rama

Prezentacja na meetup (~30 min, po polsku, samowystarczalny HTML).

**Rama (decyzja 2026-08-09, doprecyzowana):** celem jest nauczenie widza
*procesu badania* — tak, by po prezentacji wiedział, co zrobić krok po
kroku i jak analizować wyniki. Dlatego:

- Szkieletem slajdów jest protokół badania (20 kroków, sekcja niżej);
  każdy slajd ma w tytule numer i nazwę kroku, a treścią są dane ze
  studium przypadku.
- Werdykty analiz w powtarzalnym schemacie: predykcja → pomiar →
  odniesienie do szumu → werdykt z zakresem ważności.
- Ostatni slajd = cały protokół na jednej stronie (checklista do
  zabrania).
- Analogia furgonetki WYCIĘTA całkowicie (decyzja 2026-08-09 przy
  treści slajdu 14).
- Historia kary zimnego startu WYCIĘTA (co najwyżej zdanie w speaker
  notes ostatniego slajdu).
- Terminologia za notatką decyzyjną: „stały narzut hosta" (F_host),
  „interwencje" — nie „podłoga", nie „dawki".

Ustalenia techniczne (bez zmian): HTML (nawigacja klawiaturą, licznik,
speaker notes pod `N`, motyw jasny/ciemny), commit na `main`; język
polski; publiczność mieszana (narracja dla wszystkich, liczby dla
specjalistów); wykresy matplotlib → SVG z commitowanych danych + diagram
topologii inline SVG; speaker notes pełne (3–6 zdań/slajd).

## Protokół badania (szkielet prezentacji)

1. Zauważ anomalię — coś, co przeczy intuicji.
2. Sprawdź, co naprawdę mierzy metryka, na którą patrzysz.
3. Zmierz stan licznikami, które pokazują nasycenie, a nie zajętość.
4. Zapisz wyniki liczbowo, z datą i konfiguracją.
5. Wypisz wszystkie hipotezy, które mogą tłumaczyć obraz.
6. Do każdej hipotezy dopisz przewidywanie: co zobaczysz, jeśli jest
   prawdziwa.
7. Najpierw tanie eliminacje: odrzuć hipotezy padające od danych, które
   już masz.
8. Do żywych hipotez zaplanuj eksperymenty.
9. Każdy eksperyment zmienia tylko jedną rzecz naraz.
10. Zanim porównasz cokolwiek, skalibruj szum (powtórz pomiar, zapisz
    rozrzut).
11. Wykonaj eksperymenty, zachowaj surowe wyniki.
12. Porównaj każdy wynik z przewidywaniem hipotezy.
13. Uznaj efekt tylko, gdy różnica jest wyraźnie większa od szumu.
14. Wydaj werdykt: potwierdzona / obalona / nierozstrzygnięta — z
    zakresem ważności.
15. Sprawdź wniosek drugą, niezależną metodą — liczby muszą się zgadzać.
16. Zbuduj prosty model, który streszcza wiedzę w liczbach.
17. Policz z modelu, ile da planowana zmiana (np. prawem Amdahla).
18. Zapisz predykcje z progami falsyfikacji przed zmianą — nie edytuj
    po fakcie.
19. Wykonaj zmianę i zmierz dokładnie to samo, co przed nią.
20. Porównaj wynik z predykcją i przeanalizuj błędy modelu w obie
    strony.

## Struktura prezentacji (19 slajdów)

1. **Tytuł** — „**100% GPU-Util, a tylko 1/3 mocy — jak badać wydajność
   inferencji LLM?**"; podtytuł: „Studium przypadku: vLLM, Kimi-K2.6
   (1T), 8×H200, prawo Amdahla".
2. **Kontekst studium przypadku** — lab nanoserve-mini; sprzęt:
   Supermicro SYS-521GE-TNRT, 2× Xeon Gold 6530, 8× H200 NVL 143 GB,
   **PCIe-only** (stan wyjściowy); modele: Kimi-K2.6 (1T, 554 GB wag,
   TP8+Eagle3) i Qwen3.6-35B (model testowy).
3. **KROK 1: Zauważ anomalię** — zrzut nvidia-smi „100% util /
   ~175 W z 600 W"
   (`results/runs/2026-08-03_domkniecie_grafana/nvidia_smi_nop2p.png`;
   bez adnotacji na slajdzie — kontekst rekonstrukcji nop2p tylko w
   speaker notes) + **WYKRES W0**: moc w czasie z oryginalnych badań
   ery PCIe (linia limitu 600 W — stan trwały, nie chwilowy) +
   pytanie do sali wyświetlone na slajdzie: „kto spotkał się z taką
   sytuacją i zastanawiał się, dlaczego przy 100% GPU-Util karty
   zużywają tylko ~30% dostępnej mocy?". Bez liczb w podpisach —
   obserwacja wizualna.
4. **KROK 2: Zrozum, co mierzy Twoja metryka** — GPU-Util = % czasu
   okna próbkowania, w którym na karcie wykonywał się **jakikolwiek**
   kernel — miara „czy coś się dzieje", nie „ile krzemu pracuje";
   składowe wliczane do zajętości na równych prawach: kernele compute,
   kernele komunikacyjne NCCL (w tym spin-wait na inne GPU), operacje
   memory-bound o niskim SMACT, drobne kernele orkiestracji.
5. **KROKI 3–4: Zmierz nasycenie właściwymi licznikami** — narzędzie:
   DCGM (`dcgmi dmon`, host-side, bez modyfikacji kontenerów);
   liczniki: moc (`DCGM_FI_DEV_POWER_USAGE`), aktywność SM-ów
   (`SM_ACTIVE`), nasycenie pamięci (`DRAM_ACTIVE`), transport PCIe
   RX/TX (po montażu też pola NVLink 1011/1012). Wyniki — ile czasu
   pracował każdy element: SM-y ~20% czasu, interfejs HBM 7–9%, moc
   ~30% limitu, wszystko przy GPU-Util 100% — **nic nie jest nasycone**
   (WYKRES W2).
6. **KROKI 5–6: Postaw hipotezy z przewidywaniami** — **H1**
   memory-bound/HBM (przewidywanie: wysoki DRAM_ACTIVE), **H2**
   komunikacja między GPU po PCIe (przewidywanie: throughput spada z
   liczbą ranków, NCCL dominuje krok), **H3** podłoga hosta —
   CPU/launch/orkiestracja spekulacji (przewidywanie: przy c=1 dominują
   przerwy między kernelami), **H4** kara UPI za cross-socket
   (przewidywanie: placement przez UPI wyraźnie wolniejszy).
7. **KROK 7: Tanie eliminacje** — slajd czysto o H1, skonfrontowanej z
   danymi, które już mamy: DRAM_ACTIVE 0,070–0,093 vs oczekiwane
   0,70–0,90 → **OBALONA bez żadnego eksperymentu** (WYKRES W7:
   DRAM_ACTIVE w osi czasu + pas oczekiwany). Tu debiutuje stały
   „boks werdyktu" (predykcja → pomiar → werdykt z zakresem ważności).
   Poszlaka PCIe za H2 przeniesiona do bloku H2 (slajd 11/12).
8. **KROKI 8–10: Zaplanuj eksperymenty i skalibruj szum** — plan (jedna
   zmiana naraz), kolejność wg kosztu — najtańsze sprawdzenie najpierw:
   **H4** → placement TP2 same-switch vs cross-socket
   (`CUDA_VISIBLE_DEVICES=0,4`) — jeden bieg; **H3** → jeden trace
   przy c=1 (gaps) + interwencje eager vs cudagraphs i spekulacja
   on/off; **H2** → najdroższa: pełna krzywa TP 1/2/4/8 przy c=64
   (osobne starty silnika), interwencja `NCCL_P2P_DISABLE=1`, udział
   NCCL w trace. Kalibracja szumu: niezależne restarty silnika
   wymagane przez warianty → pasmo ±0,4 ms (TP=2).
9. **KROKI 11–14: Eksperyment H4 — kara UPI (najtańszy test)** — tło:
   DIAGRAM D1 (przed): 2 CPU ↔ UPI, 4 switche PCIe 5.0 x16, pary GPU
   na wspólnych switchach, połączenia cross-socket przez UPI.
   Eksperyment placementu: TP2 same-switch vs cross-socket GPU{0,4}:
   9,13 vs 9,91 ms przy c=1 — różnica w paśmie szumu. **WERDYKT: H4
   OBALONA** — jeden tani bieg zamknął hipotezę, nie wracamy.
10. **KROKI 11–14: Eksperyment H3 — podłoga hosta** — czym jest podłoga
    (czas niewidoczny w żadnym kernelu: scheduler vLLM, launch,
    orkiestracja MTP/Eagle3, Python/CPU); narzędzie: trace torch
    profiler (wprowadzenie — wróci przy H2); trace Kimi TP8 c=1: **gaps
    63% / NCCL 22,5% / compute 9%** (WYKRES W3); ledger: MTP 3,57 ms =
    **40% kroku** (spekulacja i tak wygrywa: TPOT 3,39 vs 5,36 ms),
    cudagraphs maskują **~46 ms/krok** launchu (dawka eager: SMACT
    0,009), governor uniewinniony; kontrola: profiled vs unprofiled
    ~5%. **WERDYKT: H3 POTWIERDZONA dla c=1 (floor-bound)** — żadne
    łącze tego nie naprawi.
11. **KROKI 11–13: Eksperyment H2 (a) — jak płynie komunikacja** —
    DIAGRAM D1 (wraca): przepływ dla TP=1 (zero komunikacji), TP=2
    (wspólny switch, PIX), TP=4 (przez root CPU, NODE), TP=8 (pary
    cross-socket przez UPI, SYS); skala: all-reduce ~2/warstwę, Kimi
    ~122 scalenia/krok — krok czeka na najwolniejszą ścieżkę.
12. **KROKI 12–14: Eksperyment H2 (b) — wyniki i werdykt** — krzywa TP
    c=64: 1202/1404/680/257 tok/s, eff. 100/58/14/**2,7%** (WYKRES W1);
    sufit transportu 7,2–7,9 GB/s; delty TP4/TP8 = **4×/13× szumu**;
    nop2p przy TP2 negatywny (1404→1396) — przy 2 rankach komunikacja
    tania; trace pod batchem (narzędzie z H3): NCCL 53,3% spanu (Qwen
    TP4 c64), 83,9% (Kimi TP8 c16). **WERDYKT: H2 POTWIERDZONA dla
    TP≥4 pod batchem** — winowajca: liczba ranków × sufit transportu.
    Bilans śledztwa: dwaj winowajcy, każdy w swoim reżimie — c=1 →
    podłoga hosta (H3), batch+TP≥4 → komunikacja (H2).
13. **KROK 15: Sprawdź drugą metodą** — konwergencja niezależnych
    metod: z udziału NCCL w trace 680 ÷ (1−0,533) ≈ 1456 ≈ 1404 tok/s
    zmierzone na TP2 — trace przewiduje bench. Zagadka poza modelem:
    **anomalia c=16** (ITL 512 ms, reprodukowalna ±3%) zaparkowana z
    werdyktem roboczym „software/scheduler".
14. **KROKI 16–17: Zbuduj model i policz zysk** — kalibracja wzoru z
    kroku 5 liczbami z eksperymentów: tabela wejść (s, capture,
    podstawa pomiarowa — §7 notatki) + wzór `S_nvlink = 1/(1 −
    s·capture·(1−128/900))` + tabela wyników S_ideal/S_nvlink (TP4
    c64 **2,14/1,84**, TP8 wysoka współb. **2,70/2,18**, c=1 ≤1,2×).
    Bez furgonetki; S_ideal i zastrzeżenie o s=0,839 (c=16) w notes.
15. **KROK 18: Pre-rejestruj predykcje** — skrócona tabela ~8 wierszy
    z jawną kolumną progów falsyfikacji (plan 07-31 §1): P2P >100
    GB/s, NCCL busbw >100, Qwen TP4 c64 680→**~1430** (próg <850),
    Kimi c32 285→**~770** (próg <400), c=1 bez zmian, **anomalia c16
    zostaje**, PCIe RX spada, **para warningów custom-AR (Qwen
    znika / Kimi zostaje)** — przeniesiona tu ze slajdu montażu.
    „Nie edytuj po fakcie" w notes, bez motta.
16. **KROK 19 (a): Interwencja** — montaż NVLink 4-way: 2 wyspy (GPU
    0-3, 4-7); topologia PO (DIAGRAM D1 wariant PO: NV6 w wyspach, SYS
    między); bramka custom-AR: Qwen warning znika (kernel aktywny) /
    Kimi zostaje (4+4 ≠ pełna siatka przy TP8) — para zgodna z
    przewidywaniem; mikro-sanity: P2P 132,8 (wyspa) vs 29,1 (cross);
    NCCL busbw 185–333 GB/s vs 24,8–31,3 (2+2) vs stary sufit 7,2–7,9
    (WYKRES W4, skala log).
17. **KROK 19 (b): Zmierz dokładnie to samo** — end-to-end, te same
    benche co przed montażem: Qwen TP4 c64 680→**2022 tok/s (2,97×)**;
    Kimi c32 285→**594 (2,08×)**; c=1 ~20% zysku (WYKRES W5, przed/po +
    markery predykcji).
18. **KROK 20: Analizuj błędy modelu w obie strony** — Qwen 2,97×
    **ponad sufit modelu 2,14×** (ukryta dawka: odblokowany custom
    all-reduce + zniknięcie kontencji), Kimi 2,08× < 2,7× (implikowany
    capture 0,62 vs założone 0,75). Wzmocnienie trace'em 08-03: NCCL w
    spanie Kimi 83,9%→**61,1%** — cały zysk 2,08× przyszedł z
    komunikacji; dawka kernela custom-AR @c64 nierozstrzygnięta
    (1,0–1,2×), @c1 realna ~+8%.
19. **Cały protokół na jednej stronie** — checklista 20 kroków (klamra:
    to był szkielet całej prezentacji) + co dalej: NCCL to nadal ~61%
    spanu → pełna siatka / NVSwitch teoretycznie do ~2,6× na Kimi TP8.
    Bez danych prelegenta, wydarzenia i linków do GH (decyzja
    2026-08-09) — prelegent przedstawia się ustnie.

## Wykresy (matplotlib → SVG, osadzone inline w HTML)

Dane wyłącznie z commitowanych plików; przypisanie do slajdów wg
numeracji v3:

- **W0** (slajd 3) moc w czasie pod obciążeniem, era PCIe: kolumna
  power z
  `results/runs/2026-06-11_nvlink_boundary/kimi_ramp/kimi_c32_dcgmi.txt`
  (i/lub `qwen_tp_curve/qwen_tp8_c64_dcgmi.txt`) — przebieg per GPU
  przez całe okno benchmarku + linia limitu 600 W.
- **W1** (slajd 12) krzywa TP Qwen c=64:
  `results/runs/2026-06-11_bottleneck/qwen_tp_curve/bench_tp{2,4,8}/tp*_c64.json`
  + TP1 z summary (1202, adnotacja źródła) — słupki tok/s + linia
  efektywności.
- **W2** (slajd 5) „100% util vs rzeczywistość": GPU-Util 100%
  zestawione z mocą, SMACT i DRAM_ACTIVE — źródło pierwotne: notatka
  decyzyjna §6.1 (Kimi TP8: spoczynek / c=1 / c=64 → 99/170/199 W,
  SMACT 0/0,21/0,20, DRAM 0/0,093/0,070, PCIe ~10% przepustowości);
  pomocniczo `results/summaries/2026-06-11-{qwen-tp-curve,nvlink-boundary-verdict}.md`.
- **W3** udziały trace (dane z notatki §6.4): wariant **W3a**
  (slajd 10) słupek skumulowany Kimi c=1; na slajdzie 12 pełne
  3 scenariusze jako TABELA (jak w notatce), nie wykres — decyzja
  2026-08-09.
- **W4** (slajd 16) P2P + NCCL busbw przed/po:
  `results/runs/2026-07-31_nvlink_install/nvlink/{p2p_bw.json,nccl_allreduce.json,nccl_allreduce_island0.txt}`
  vs sufit PCIe 7,2–7,9.
- **W5** (slajd 17) end-to-end przed/po z markerami predykcji: bench
  JSONy 06-11 vs
  `results/runs/2026-07-31_nvlink_install/{qwen,kimi}/bench*/*.json`.
- **W6** — WYCIĘTY razem ze slajdem zagadki c=16 (decyzja
  2026-08-09: temat bez wyjaśnionego mechanizmu); wiersz c=16 usunięty
  też z tabeli predykcji (slajd 15).
- **W7** (slajd 7) DRAM_ACTIVE w osi czasu (okna c=1 i c=64, Kimi TP8)
  + pas 0,70–0,90 „oczekiwane przy memory-bound": szeregi dcgmi z sesji
  P0 `results/runs/2026-06-10_w1_article_evidence/` (ścieżki plików do
  potwierdzenia przy generowaniu wykresu).
- **D2** (slajd 4) schemat osi czasu zajętości GPU — ręczny inline
  SVG, poglądowy (bez danych pomiarowych): odcinki kerneli różnych
  typów + przerwa hosta, klamra „dla GPU-Util wszystko = zajęte".
- **D3** (slajd 11) schemat warstwy pod TP (wg mermaid z notatki §4):
  attention → SCALENIE 1 → FFN/MoE → SCALENIE 2, ×61 warstw ≈ 122
  scalenia/krok, adnotacja o synchroniczności.
- **D1** (slajdy 9, 11 i 16) diagram topologii przed/po — ręczny inline SVG
  wg `docs/operations/infrastructure.md` (diagram ASCII) + macierzy
  `results/runs/2026-06-11_bottleneck/session/nvidia_topo.txt` (przed) /
  `results/runs/2026-07-31_nvlink_install/nvlink/topo_m.txt` (po).
- **Screenshot hooka** (slajd 3):
  `results/runs/2026-08-03_domkniecie_grafana/nvidia_smi_nop2p.png` —
  JEST w repo (zdobyty 08-03); bez adnotacji na slajdzie (decyzja
  2026-08-09) — kontekst rekonstrukcji nop2p w speaker notes.

## Pliki do utworzenia (na `main`)

```text
docs/presentations/2026-07-31-nvlink-meetup/
├── index.html            # samowystarczalne slajdy (pełny dokument HTML)
├── generate_charts.py    # reprodukcja W0–W5 i W7 z commitowanych danych → SVG
└── charts/*.svg          # wygenerowane wykresy (małe, tekstowe)
```

- `generate_charts.py` uruchamiany przez `uv run --with matplotlib python ...` —
  bez dodawania matplotlib do `pyproject.toml`.
- HTML: lekki własny framework slajdów (strzałki/PgUp/PgDn, licznik slajdów,
  panel notatek pod `N`, motyw jasny/ciemny), SVG wykresów inline.

## Proces pracy (sesja interaktywna, od 2026-08-09)

Praca iteracyjna z użytkownikiem, krok po kroku: (1) struktura ogólna —
v3 (protokół jako szkielet, 20 slajdów, kolejność eksperymentów
H4→H3→H2 wg kosztu) — ZATWIERDZONA 2026-08-09; (2) treść slajd po
slajdzie — W TOKU; (3) forma graficzna (wykresy + HTML) — dopiero po
zamknięciu treści. Priorytet: merytoryczność.

## Kolejność wykonania (po zamknięciu treści)

1. `generate_charts.py` → W0–W5 + W7 (walidacja liczb ze źródłami
   wymienionymi wyżej).
2. `index.html` (19 slajdów + speaker notes + inline SVG + diagram D1).
3. Walidacja: `uv sync --extra dev`, `uv run ruff check .`, `uv run pytest`
   (dochodzi `.py`), `git diff --check`.
4. Aktualizacja `docs/operations/agent-state.md` (wpis handoff + In flight).
5. Commit + push na `main`.

## Kluczowe liczby (zweryfikowane ze źródłami)

Krzywa TP c=64: 1202 / 1404 / 680 / 257 tok/s (eff. 100/58/14/2,7%). Sufit
PCIe RX 7,2–7,9 GB/s. Trace przed: c1 gaps 63%/NCCL 22,5%; c16 NCCL 83,9%;
Qwen TP4 c64 NCCL 53,3%. Amdahl: S_nvlink TP4 c64 1,84 (ideal 2,14); Kimi
TP8 batched 2,18 (ideal 2,70). Predykcje: Qwen ~1430 (próg <850), Kimi ~770
(próg <400), c16 „zostaje". Po montażu: P2P 132,8/29,1; NCCL busbw 185–333
vs 24,8–31,3; Qwen 2022 (2,97×); Kimi 594 (2,08×); c16 ITL 512→48,6 ms;
Qwen c1 TPOT 3,21 ms; Kimi c1 TPOT 7,44 ms; bramka custom-AR: znika/zostaje.
Z sesji 08-03: trace Kimi c32 po NVLinku NCCL 61,1% spanu (compute 30,2%);
dawka kernela custom-AR @c64 1,0–1,2× (nierozstrzygnięta), @c1 ~+8%; nop2p
rekonstrukcja 458 tok/s przy 172–181 W (dawka częściowa, ~4 GB/s NVL poza
NCCL).
