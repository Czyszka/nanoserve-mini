# Werdykty 2026-08-07 iteracja 3 (adopcja v0.26.0)
| krok | werdykt | uwagi |
|---|---|---|
| R3 powtórka (overlay) | PASS | capture 29 s, startup complete, zero błędów → 2. PASS z rzędu, winowajca `fuse_allreduce_rms` potwierdzony formalnie |
| start z compose repo | PASS | capture 25 s, `'fuse_allreduce_rms': False` w configu (verify_pass_off.txt) |
| bench b1 zimny (tok/s) | 645,4 | ITL med 82,9 ms, TPOT med 41,1 ms, 384/384 done |
| bench b2 wygrzany (tok/s) | 676,1 | ITL med 82,8 ms, TPOT med 40,4 ms; delta zimny→wygrzany +4,8% |
| DECYZJA bramki (0.26 zostaje / revert) | **0.26 ZOSTAJE** | b2 = 676 ≥ próg 559; +13,8% vs baseline 594 (v0.20, 07-31) — upgrade jest wygrany wydajnościowo |
- Stack na koniec: celowo down (decyzja serii diagnostycznej), restore w osobnym touchu
- Odstępstwa od planu: brak
- Werdykty uzupełnione laptopowo z logów/benchy (tabela poszła z sesji pusta)
