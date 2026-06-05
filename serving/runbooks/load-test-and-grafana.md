# Load test vLLM + podgląd w Grafanie — runbook

Cel: wygenerować realne obciążenie na działającym vLLM i zobaczyć żywe metryki na
dashboardzie Grafany (kolejka, throughput, latencja, KV cache, spec decode), a na
końcu zrobić screen. Powtarzalny przepis — używany przy każdym pokazaniu
observability pod load (T5/#34 i później).

Procedura zweryfikowana na slocie 2026-06-05 (Kimi K2.6, Eagle3-ON, 8×H200).
Sesyjny zapis „jak i kiedy" tej konkretnej sesji: `docs/plans/2026-06-05-t5-dashboard-load.md`.

---

## Wymagania wstępne

- Stoją kontenery serwujące: `vllm` (Kimi :8000) — `docker compose -f serving/compose/docker-compose.kimi-k2.6.yml ps`.
- Stoi observability: `docker compose -f serving/compose/docker-compose.observability.yml ps` (prometheus :9090, grafana :3001).
- Dashboard provisioned (datasource + provider + JSON są w `serving/compose/grafana/provisioning/`; nic nie konfigurujemy ręcznie).
- Workload offline w repo: `results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl` (300× `{"prompt": ...}`, bez internetu).

---

## Krok 1 — health check stacku

```bash
curl -fsS http://127.0.0.1:9090/-/healthy && echo "prometheus OK"
curl -fsS http://127.0.0.1:3001/api/health && echo "grafana OK"
curl -s http://127.0.0.1:9090/api/v1/targets \
  | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'
curl -s 'http://127.0.0.1:9090/api/v1/query?query=vllm:num_requests_running' | jq '.data.result'
```

OK: prometheus + grafana zwracają healthy; targety (`vllm-kimi`, `vllm-small-deepseek`,
`litellm`) `health: up`; query zwraca serię z labelem `model_name`.

## Krok 2 — Grafana gotowa do screena

W UI (`http://<serwer>:3001`, login `admin` / `GRAFANA_ADMIN_PASSWORD`):
otwórz dashboard **vLLM Phase 1 — nanoserve-mini**, zakres **Last 15 minutes**,
refresh **5s**, dropdown „Datasource" = **Prometheus**.

OK: wszystkie panele renderują się (płaskie, bo brak ruchu — to normalne przed load).

## Krok 3 — dataset do kontenera

```bash
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml cp \
  results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl \
  vllm:/tmp/swe_bench_vllm.jsonl
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml exec vllm bash
```

OK: wewnątrz kontenera `ls -la /tmp/swe_bench_vllm.jsonl && head -1 /tmp/swe_bench_vllm.jsonl`
pokazuje plik i rekord `{"prompt": ...}`.

## Krok 4 — prerequisites w kontenerze (KLUCZOWE — tu padało 2026-06-05)

Ten obraz vLLM nie ma extras do benchu i bench próbuje dzwonić do HF:

```bash
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # bierz tokenizer z ~/hf_cache, nie z huba
pip install pandas datasets                        # deps datasetu benchu
```

- **Bez offline env** → `error retrieving file list` (bench leci do HuggingFace po tokenizer).
- **Bez pandas/datasets** → `ModuleNotFoundError: pandas` / `Please install vllm[bench]`.
- **NIE** rób `pip install vllm[bench]` — może przeinstalować vllm+torch i rozwalić serwer.
  Instaluj tylko leaf-deps; jak krzyknie o kolejny, dorzuć (`pyarrow`/`pillow`).
- Instalki są ulotne (giną po restarcie kontenera) — to OK na sesję.

OK: `python -c "import pandas, datasets; print('ok')"` zwraca `ok`.

## Krok 5 — ramp obciążenia (fazy A→B→C, back-to-back, ~12 min)

Kimi wymaga `--trust-remote-code` (custom tokenizer). `--ignore-eos --custom-output-len 256`
wymusza stały decode. `--save-result` zbiera liczby pod write-up.

```bash
DS=/tmp/swe_bench_vllm.jsonl
COMMON="--backend vllm --base-url http://127.0.0.1:8000 --model kimi-k2.6 \
  --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
  --dataset-name custom --dataset-path $DS \
  --custom-output-len 256 --ignore-eos \
  --save-result --result-dir /tmp/t5_bench \
  --metadata phase=t5 model=kimi-k2.6 eagle3=on"

# A — light
vllm bench serve $COMMON --num-warmups 8 --num-prompts 120 --max-concurrency 4  --result-filename phaseA_c4.json
# B — medium
vllm bench serve $COMMON --num-prompts 300 --max-concurrency 16 --result-filename phaseB_c16.json
# C — saturate
vllm bench serve $COMMON --num-prompts 600 --max-concurrency 64 --result-filename phaseC_c64.json
```

OK: każda faza kończy się podsumowaniem (TTFT/TPOT/throughput); na dashboardzie
widać rosnące schodki obciążenia.

Tuning: jeśli w fazie C **Requests waiting** zostaje na zerze → podbij
`--max-concurrency` (96/128); nie dobiłeś do `max_num_seqs`.
`--tokenizer moonshotai/Kimi-K2.6` jest wymagany w trybie offline (klient benchu
sam nie znajdzie tokenizera Kimiego); musi być w zamontowanym `~/hf_cache`. Jeśli
i to zawiedzie → `--skip-tokenizer-init` (metryki i tak z `/metrics` vLLM).
Pamiętaj: `max-num-seqs=1` w compose = brak batchingu (artefakt T6 single-stream);
do load testu ustaw `--max-num-seqs 32`+ i zrób `up -d vllm` (recreate kasuje
`pip install` i plik z `/tmp` — powtórz krok 3-4).
Brak `/v1/completions` → `--backend openai-chat --endpoint /v1/chat/completions`.

## Krok 6 — screen w fazie C

Kiedy: **w trakcie fazy C**, gdy `Requests waiting` odbije od zera (5-min okna
latencji już pełne). Zakres Last 15m → widać cały rozbieg A→B→C.

Co łapać: jeden zbiorczy zrzut dashboardu + opcjonalnie zbliżenia paneli
Latency p95 / Requests waiting / KV cache. Screen z Windowsa (RDP) `Win+Shift+S`
jest wystarczający; alternatywnie `gnome-screenshot -a -f ~/shot.png` na serwerze.

OK: na obrazku jednocześnie widać running na maksie, waiting > 0, p95 wysoko,
KV cache wysoko.

## Krok 7 — zgarnij wyniki + commit

> ⚠️ **NAJPIERW `cp`, POTEM `compose down`.** `--save-result` zapisuje do
> `/tmp/t5_bench` **wewnątrz kontenera** — `compose down` (a nawet `up -d` po
> zmianie configu) kasuje warstwę kontenera i te pliki przepadają. Skopiuj je na
> host zanim ruszysz stack. Metryki serwera przeżyją (Prometheus TSDB jest na
> host bind-mount `…/nanoserve-observability/prometheus-data` i `down` go nie
> rusza), więc nawet po utracie JSON-ów liczby odtworzysz zapytaniami do
> Prometheusa dla okna testu — ale to plan B, nie plan A.

```bash
# wyjście z kontenera, potem z hosta:
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml cp \
  vllm:/tmp/t5_bench results/runs/2026-06-05_w1_evidence/t5_metrics/bench/

cp <screen>.png results/runs/2026-06-05_w1_evidence/t5_metrics/grafana_t5.png
git add results/runs/2026-06-05_w1_evidence/t5_metrics/
git commit -m "bench: T5 Grafana dashboard load run + screenshot (#34)"
git push origin main
```

OK: bench JSON-y + screen w repo (PNG trzymaj mały; duże artefakty → tylko ścieżka + repro).

Plan B (jeśli JSON-y przepadły przed `cp`): odtwórz liczby z Prometheusa dla okna
testu — `max_over_time(...[W])` dla peaków (running/waiting/KV/throughput) i
`histogram_quantile(q, sum by (le)(increase(..._bucket[W])))` dla E2E/TTFT/ITL.

---

## Definicja sukcesu

Dashboard pokazuje pełny cykl obciążenia pod load, screen złapany w saturacji,
liczby z `--save-result` i obraz w repo — gotowe do wpięcia w
`docs/writeups/w1/t5-observability.md`.

## Świadomie pominięte

- Panele DCGM / GPU-hardware (#34, odłożone — nie blokują W1).
- Concurrent load-gen w naszym własnym harnessie (jest sekwencyjny; używamy
  wbudowanego `vllm bench serve`).
- Bench przez LiteLLM :4000 (proxy strippuje `delta.reasoning` Kimiego —
  jedziemy direct :8000).
