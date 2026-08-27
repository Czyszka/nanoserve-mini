# Ollama LAN bench — podsumowanie pomiarów `results/raw/202608025_claude`

Wygenerowane z plików `summary.json` (schema `ollama-lan-bench.v1`) — 26 runów,
5 hostów-klientów: `desktop1_tomek`, `w241`, `w25`, `w26`, `w27`.

## Co było testowane

- **Serwer:** Ollama (firmowy PoC, 2×A6000), endpoint OpenAI-compat `http://172.18.1.118:11434/v1`.
- **Model:** `qwen3-coder:30b-a3b-q4_K_M` (MoE 30B, aktywne 3B, kwantyzacja q4_K_M).
- **Klient:** `bench_ollama.py` (stdlib-only, kit offline), zapytania sekwencyjne (`concurrency=1` per host),
  streaming, `max_tokens=256`, `temperature=0.0`, prompty z datasetu `swe_bench_vllm.jsonl` (offset 0 — wszyscy klienci używają tych samych promptów), 1 warmup + 100 pomiarów (krótsze runy kontrolne: 15).
- **Współbieżność** realizowana liczbą komputerów startujących równocześnie o zsynchronizowanej godzinie (`--start-at`):
  fale 4×, 4×, 2× i 1× klient tego samego dnia (2026-08-19), plus baseline'y solo.
- Runy z `measured_runs=1` (prompt literal) to sondy smoke/cold-start — pierwszy request po załadowaniu modelu do VRAM.

## Fale współbieżne (2026-08-19) — per host

| Start | Hosty równolegle | Host | TTFT p50 [s] | TTFT p95 [s] | E2E p50 [s] | TPOT p50 [ms] | tok/s (host) | req ok/err |
|---|---|---|---|---|---|---|---|---|
| 09:00 | 4 | desktop1_tomek | 10.73 | 11.42 | 13.33 | 10.3 | 19.0 | 100/0 |
| 09:00 | 4 | w241 | 10.78 | 11.29 | 13.42 | 10.3 | 19.1 | 100/0 |
| 09:00 | 4 | w26 | 10.80 | 11.35 | 13.41 | 10.2 | 19.0 | 100/0 |
| 09:00 | 4 | w27 | 10.73 | 11.53 | 13.33 | 10.2 | 19.0 | 100/0 |
| 10:05 | 4 | desktop1_tomek | 8.07 | 8.81 | 10.65 | 10.2 | 23.7 | 100/0 |
| 10:05 | 4 | w25 | 8.10 | 8.64 | 10.69 | 10.2 | 23.7 | 100/0 |
| 10:05 | 4 | w26 | 8.08 | 8.72 | 10.69 | 10.2 | 23.7 | 100/0 |
| 10:05 | 4 | w27 | 8.12 | 8.61 | 10.73 | 10.3 | 23.7 | 100/0 |
| 10:36 | 2 | w25 | 2.85 | 3.26 | 5.44 | 10.2 | 46.6 | 100/0 |
| 10:36 | 2 | w26 | 2.80 | 3.31 | 5.40 | 10.2 | 46.5 | 100/0 |
| 10:58 | 1 | w26 | 0.31 | 0.72 | 2.91 | 10.2 | 85.8 | 100/0 |

## Fale współbieżne — agregat (skalowanie z liczbą klientów)

| Klienci | Start | TTFT p50 śr. [s] | E2E p50 śr. [s] | TPOT p50 śr. [ms] | tok/s per host śr. | tok/s łącznie | req/s łącznie |
|---|---|---|---|---|---|---|---|
| 4 | 09:00 | 10.76 | 13.37 | 10.2 | 19.0 | 76.2 | 0.298 |
| 4 | 10:05 | 8.09 | 10.69 | 10.2 | 23.7 | 94.8 | 0.371 |
| 2 | 10:36 | 2.83 | 5.42 | 10.2 | 46.5 | 93.0 | 0.364 |
| 1 | 10:58 | 0.31 | 2.91 | 10.2 | 85.8 | 85.8 | 0.335 |

## Runy solo (baseline, 1 klient)

| Data / start | Host | Pomiarów | TTFT p50 [s] | E2E p50 [s] | TPOT p50 [ms] | tok/s | Uwagi |
|---|---|---|---|---|---|---|---|
| 2026-08-14_115400 | w25 | 15 | 0.28 | 2.91 | 10.1 | 84.4 |  |
| 2026-08-14_131900 | desktop1_tomek | 15 | 0.30 | 2.91 | 10.2 | 84.1 |  |
| 2026-08-14_133000 | w27 | 15 | 0.31 | 2.89 | 10.1 | 84.3 |  |
| 2026-08-19_082500 | w27 | 15 | 0.32 | 2.96 | 10.3 | 84.3 |  |
| 2026-08-19_082700 | w27 | 15 | 3.07 | 5.71 | 10.2 | 44.9 | anomalia — patrz uwagi |
| 2026-08-19_083200 | w27 | 100 | 0.32 | 2.93 | 10.2 | 85.4 |  |
| 2026-08-19_093800 | w25 | 100 | 0.29 | 2.90 | 10.2 | 85.6 |  |

## Sondy smoke / cold-start (`measured_runs=1`, prompt literal)

| Data / start | Host | TTFT [s] | E2E [s] | Uwagi |
|---|---|---|---|---|
| 2026-08-14_115309 | w25 | 7.34 | 7.39 | zawiera load modelu do VRAM |
| 2026-08-14_131803 | desktop1_tomek | 7.53 | 7.58 | zawiera load modelu do VRAM |
| 2026-08-14_132833 | w27 | 7.81 | 7.86 | zawiera load modelu do VRAM |
| 2026-08-19_082220 | w27 | 6.84 | 6.87 | zawiera load modelu do VRAM |
| 2026-08-19_084511 | w26 | 7.04 | 7.08 | zawiera load modelu do VRAM |
| 2026-08-19_085521 | w241 | 6.97 | 7.01 | zawiera load modelu do VRAM |
| 2026-08-19_085841 | desktop1_tomek | 0.38 | 0.61 | model już w VRAM |
| 2026-08-19_093651 | w25 | 7.45 | 7.50 | zawiera load modelu do VRAM |

## Wnioski

1. **Serwer serializuje żądania** (zachowanie zgodne z `OLLAMA_NUM_PARALLEL=1`):
   TPOT p50 jest stały ~10.2 ms (~98 tok/s dekodowania) niezależnie od liczby
   klientów, a TTFT rośnie ~liniowo z liczbą klientów (0.3 s solo → ~2.8 s przy
   2 → ~8–11 s przy 4). Kolejka, nie równoległość.
2. **Przepustowość łączna nie skaluje się**: solo ~85 tok/s, 2 klientów ~93 tok/s
   łącznie, 4 klientów ~76–95 tok/s łącznie. Dodawanie klientów dzieli tę samą
   pulę, per klient spada do ~19–24 tok/s przy 4 hostach.
3. **Latencja per klient degraduje się drastycznie**: E2E p50 z ~2.9 s (solo) do
   ~13.4 s (4 klientów) — ~4.6×.
4. **Powtarzalność solo bardzo dobra**: 84.1–85.8 tok/s w 6 niezależnych runach
   baseline na 4 różnych hostach i w 2 różne dni; klienci/sieć LAN nie są
   wąskim gardłem.
5. **Cold start**: pierwszy request po załadowaniu modelu ma TTFT ~6.8–7.8 s
   (load do VRAM); po rozgrzaniu TTFT p50 ~0.3 s.
6. **Anomalia** `2026-08-19_082700` (w27 solo, 44.9 tok/s, TTFT p50 3.07 s —
   wynik jak przy 2 klientach): najprawdopodobniej serwer obsługiwał wtedy
   inne obciążenie; run powtórzony o 08:32 dał normalne 85.4 tok/s.
7. Różnica między falami 4-klientowymi (09:00: 76 tok/s łącznie, wall 1343 s
   vs 10:05: 95 tok/s, wall 1078 s) przy identycznych promptach (ten sam
   dataset, offset 0, śr. 713.7 tok promptu) wskazuje na dodatkowy czynnik
   serwerowy między falami; skład hostów różni się jednym klientem
   (`w241` vs `w25`).

## Reprodukcja

- Narzędzie: `benchmarks/ollama_lan_bench/bench_ollama.py` (kit: `build_kit.py`).
- Surowe dane: `results/raw/202608025_claude/<host>/<run_id>/{summary.json,results.jsonl}`.
- Tabele wygenerowane skryptem ad-hoc agregującym pola `metrics`/`throughput`
  ze wszystkich `summary.json` (percentyle policzone przez bench, nie ponownie).

