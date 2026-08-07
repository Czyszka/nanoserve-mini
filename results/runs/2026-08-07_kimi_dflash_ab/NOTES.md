# Werdykty 2026-08-07/08 — A/B DFlash vs Eagle3 (Kimi @ 0.26, oba @util 0.65)
| pomiar | DFlash (k=8) | Eagle3 (dziś, k=3) | Eagle3 (wczoraj @0.60) |
|---|---|---|---|
| c1 TPOT med (ms) | 20,90 | 19,61 | — (7,44 z 07-31 NIEPORÓWNYWALNE — patrz odstępstwa) |
| c32 warm (tok/s) | 576,4 | 649,2 | 676 |
| akceptacja | 16,2%/token draftu; śr. 1,30 tok akceptowanych/krok (2,30 tok/krok); pozycje 4-7 łącznie tylko 15% akceptacji (p7 = 1,9%) | 30,4%/token; śr. 0,91/krok (1,91 tok/krok) | ~stabilna @3 (na SWE) |
| warning scheduled_tokens | tak (zanotowany, nie tunowany) | tak | tak |
- **BRAMKA: NIE — DFlash nie wchodzi do compose, Eagle3 zostaje.**
  c1: 20,9/19,6 = 1,07× (wymagane ≤0,85×); c32: 576/649 = 0,89× (wymagane ≥0,94×).
  Do tego koszt pamięci: DFlash wymaga util 0,65 (OOM @0,60).
- Mechanizm porażki: profil akceptacji jest ZDROWY (monotoniczny spadek, p0 46%),
  drafter działa — ale blok 8 zmusza do weryfikacji 9 tok/krok, z czego pozycje 4-7
  oddają grosze; cięższy forward draftera dyfuzyjnego zjada resztę. "2%" z sesji to
  akceptacja POZYCJI 7, nie całości.
- Hipoteza nieprzetestowana: k=4 (pozycje 0-3 niosą 85% akceptacji DFlash) — mogłoby
  zbliżyć do Eagle3; świadomie nie testowane (bramka przegrana, scope).
- Stack na koniec: pełny restore (Kimi Eagle3 + DeepSeek + proxy + WebUI): TAK (restore_ps)
- Odstępstwa od planu:
  1. util 0,65 dla OBU nóg (DFlash OOM @0,60) — A/B wewnętrznie czyste; 676 @0,60 tylko odniesienie.
  2. **Błąd metodyczny planu: c1 na `random 64/512`** zamiast SWE custom — wzorzec przeniesiony
     z benchy Qwena. Historyczne Kimi c1 (7,44 ms TPOT, 07-31) było na SWE custom (24 prompty,
     ~2020 tok inputu, 256 out; potwierdzone w kimi_c1.json) → dzisiejszych c1 NIE porównywać
     z 7,44. Random zaniża akceptację obu drafterów (OOD), ale symetrycznie — A/B ważne.
  3. Metryki spec_decode kumulatywne per start silnika — wartości mieszają c1-random i c32-SWE.
