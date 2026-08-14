# ollama-lan-bench

Samodzielny benchmark sekwencyjny dla zdalnego serwera **Ollama** w sieci LAN.
Jeden klient → jeden endpoint Ollamy (OpenAI-compatible `/v1/chat/completions`).
`bench_ollama.py` jest **czysty stdlib** (zero zależności) — działa z dowolnym
Pythonem 3.12+, także z wbudowanym Pythonem w zestawie offline (niżej), albo
przez [uv](https://docs.astral.sh/uv/) na maszynie deweloperskiej.

## Co mierzy

- **TTFT** — czas od wysłania requestu do pierwszego chunka z treścią odpowiedzi.
- **E2E latency** — czas od wysłania requestu do pełnego zdrenowania streamu.
- **TPOT** — `(E2E − TTFT) / (completion_tokens − 1)`; wymaga, by Ollama
  raportowała `usage` w streamie (nowsze wersje honorują
  `stream_options.include_usage`); bez tego TPOT/tokeny = `null`, a
  przepustowość znakowa nadal jest liczona.
- **Przepustowość** — req/s, znaki/s i tokeny/s po wall clocku fazy mierzonej
  (warmup wykluczony).

Agregaty: `count / min / p50 / p95 / max / mean`. Definicje metryk są zgodne z
`docs/operations/benchmark-methodology.md` w repo nanoserve-mini.

## Klienci offline (Windows) — zestaw bez Pythona i bez internetu

Gdy komputery-klienci nie mają internetu, Pythona ani uv, zbuduj przenośny kit
na maszynie z internetem (np. serwer Linux):

```bash
python3 build_kit.py          # albo: uv run build_kit.py
```

Skrypt pobiera oficjalny *embeddable package* CPythona z python.org (wersja
pinowana w `build_kit.py`, obecnie 3.12.10), waliduje go strukturalnie, drukuje SHA256
(przypnij go przy kolejnych buildach: `--expected-sha256 <hash>`) i składa
`dist/ollama_bench_kit.zip` (~15 MB): wbudowany Python + `bench_ollama.py` +
dataset SWE + `run_bench.bat` + instrukcja `README_KIT.txt`.

Przenieś zip pendrive'em na klienta, rozpakuj w dowolne miejsce i uruchom
z cmd — bez żadnej instalacji:

```bat
run_bench.bat --base-url http://192.168.1.50:11434 --model llama3.3:70b ^
    --dataset swe_bench_vllm.jsonl --num-requests 10 --start-at 08:30
```

Przydatne flagi buildu: `--embed-zip PATH` (użyj już pobranej paczki, np. przy
budowaniu w środowisku bez dostępu do python.org), `--dataset PATH|none`,
`--dist DIR`.

## Uruchamianie z uv (maszyna deweloperska z internetem)

1. Zainstaluj uv:
   - Windows (PowerShell): `winget install astral-sh.uv`
   - Linux/macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Ścieżka minimalna — wystarczy sam plik skryptu (zero zależności do
   pobrania):

   ```bash
   uv run bench_ollama.py --base-url http://192.168.1.50:11434 --model llama3.3:70b
   ```

3. Ścieżka pełna (cały katalog; potrzebna do testów):

   ```bash
   uv sync --extra dev     # pytest, ruff (runtime nie ma zależności)
   uv run pytest
   uv run python bench_ollama.py --base-url ... --model ...
   ```

## Dataset SWE

Testowy dataset repo (300 promptów SWE-bench Lite, po jednym
`{"prompt": "..."}` na linię) leży w
`results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl`.
Skopiuj go na klienta obok skryptu i wskaż:

```bash
uv run bench_ollama.py --base-url http://192.168.1.50:11434 --model llama3.3:70b \
    --dataset ./swe_bench_vllm.jsonl --num-requests 10
```

## Start o zadanej godzinie i wiele klientów

`--start-at HH:MM` czeka do najbliższego wystąpienia tej godziny (czas
**lokalny systemowy klienta** — przy koordynacji kilku maszyn upewnij się, że
mają zsynchronizowane zegary, np. NTP). Akceptowany też pełny format
`YYYY-MM-DDTHH:MM`. Bez flagi start jest natychmiastowy.

Każdy klient bierze rozłączny wycinek datasetu przez `--dataset-offset`:

```bash
# klient A                                  # klient B
... --start-at 08:30 --dataset-offset 0     ... --start-at 08:30 --dataset-offset 50
```

Zapytania w ramach jednego klienta są ściśle sekwencyjne — kolejne wychodzi
dopiero po pełnej odpowiedzi na poprzednie. Błąd pojedynczego requestu jest
zapisywany jako wiersz z `error` i run trwa dalej.

Domyślnie `--warmup 1` — pierwszy request po bezczynności Ollamy zawiera
ładowanie modelu do VRAM (dziesiątki sekund dla 70B+), więc nie wchodzi do
statystyk. Wyniki: `./results/<run-id>/results.jsonl` (wiersz per request,
z `client_hostname` — wyniki z wielu klientów można konkatenować)
i `summary.json` (agregaty + pełna konfiguracja runu).

## A `vllm bench serve`?

Da się nim testować Ollamę: `vllm bench serve --backend openai-chat
--base-url http://<host>:11434 --endpoint /v1/chat/completions --model <tag>
--tokenizer <hf-repo>`, bo Ollama mówi protokołem OpenAI chat streaming.
Zastrzeżenia: trzeba wskazać pasujący tokenizer z HF (vllm bench liczy tokeny
re-tokenizując tekst po stronie klienta — przy niezgodnym tokenizerze TPOT to
przybliżenie), `usage` może nie wrócić w oczekiwanej formie, sweepy
concurrency mierzą głównie kolejkowanie (Ollama nie ma continuous batchingu,
por. `OLLAMA_NUM_PARALLEL`), a na kliencie trzeba zainstalować całe vLLM —
ciężka zależność. Do sekwencyjnych, planowanych czasowo runów z wielu lekkich
klientów ten skrypt jest właściwym narzędziem; `vllm bench serve` nadaje się
jako cross-check pojedynczego poziomu obciążenia z jednej mocnej maszyny.
