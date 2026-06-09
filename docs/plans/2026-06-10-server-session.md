# Plan sesji serwerowej 2026-06-10 — P0 GPU counters + P2 hop attribution (ubuntusrv2, 8×H200 NVL)

## Context

Sesja zbiera **dwa brakujące dowody dla pogłębionego artykułu W1**
(`docs/plans/2026-06-09-w1-article-deepening.md`):

- **P0 — liczniki GPU (DCGM)**: rozstrzygnięcie "HBM-bound vs PCIe-comms-bound"
  z Inv 5 / T5 (rdzeń #34). Trzy okna pomiarowe: idle, single-stream (c=1),
  batched (c=64). Liczniki: power, `SM_ACTIVE`, `PIPE_TENSOR_ACTIVE`,
  `DRAM_ACTIVE`, `PCIE_TX/RX_BYTES`.
- **P2 — atrybucja hopa proxy (T8 R1, #44)**: vLLM jako shared reference clock —
  snapshoty `/metrics` wokół izolowanych żądań, direct `:8000` vs proxy `:4000`,
  `metrics_delta.py` (Δsum/Δcount). Zamyka "Deferred" w Inv 2 i Inv 3 artykułu.

**Świadomie POZA sesją (decyzja 2026-06-09):** P1 (Eagle3 n=20 clean A/B) i
P3 (concurrency sweep) — odrzucone; tuning `num_speculative_tokens` — poza
roadmapą. Okna c=1 i c=64 w Cz. B służą **wyłącznie interpretacji liczników**
(dwa punkty pracy), nie są sweepem.

**Zero restartów silników.** Compose Kimi ma już produkcyjne
`--max-num-seqs 32` (`serving/compose/docker-compose.kimi-k2.6.yml`) — okno
batched działa na bieżącej konfiguracji. Niskie ryzyko; stack po sesji zostaje
dokładnie w stanie zastanym.

---

## Budżet (slot 8:00–15:00; plan ~4,5 h → duży zapas)

| Cz. | Co | Czas | Restart |
|---|---|---:|---|
| 0 | start/health stacku + snapshot | 30 | start całości (jeśli leży) |
| A | tooling liczników (dcgmi → exporter → dmon) + okno idle | 45 | — |
| B | prereqs bench + okno single c=1 + okno batched c=64 + eksport Prometheus | 75 | — |
| **CHECKPOINT 1 — commit P0** | | 15 | |
| C | P2: hop attribution, 2 warianty max_tokens × 5 par ABBA | 60 | — |
| D | close-out: manifest, session notes, agent-state, commit+push | 30 | — |

Must-have: **0, A (min. tier-3), B (min. okno batched), C (wariant mt=64), D**.

Reguła odcięcia: jeśli tooling A utknie > 45 min → przejdź na tier-3
(`nvidia-smi dmon`) i jedź dalej; **C jest tańsze i pewniejsze niż B — gdyby
B padło na prereqs, zrób C w całości, potem wróć do B z fallbackiem.**

---

## Run directory

```bash
cd ~/nanoserve-mini
RUN_DIR=results/runs/2026-06-10_w1_article_evidence
P0OUT="$RUN_DIR/p0_gpu_counters"
P2OUT="$RUN_DIR/p2_hop_attribution"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
OBS="serving/compose/docker-compose.observability.yml"
mkdir -p "$P0OUT" "$P2OUT" "$RUN_DIR/session"
```

Zmienne ustaw raz i trzymaj w jednej sesji shellowej.

---

## Cz. 0 — start stacku + snapshot (30 min)

```bash
cd ~/nanoserve-mini
git status
git pull --ff-only origin main
uv sync --extra dev

set -a; source .env; set +a
test -n "$LITELLM_MASTER_KEY" || { echo "missing LITELLM_MASTER_KEY in .env"; exit 1; }

docker compose -f "$COMPOSE" up -d vllm vllm-small litellm
docker compose -f "$OBS" up -d

echo "waiting for vLLM healthy (Kimi ładuje się minutami)..."
for _ in $(seq 1 180); do curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 10; done
for _ in $(seq 1 60);  do curl -fsS http://127.0.0.1:8004/health >/dev/null 2>&1 && break; sleep 5;  done
curl -fsS http://127.0.0.1:8000/health && echo " kimi OK"
curl -fsS http://127.0.0.1:8004/health && echo " deepseek OK"
curl -fsS -H "Authorization: Bearer $LITELLM_MASTER_KEY" http://127.0.0.1:4000/v1/models | jq '.data[].id'
curl -fsS http://127.0.0.1:9090/-/healthy && echo " prometheus OK"

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
docker compose -f "$COMPOSE" ps > "$RUN_DIR/session/docker_ps_start.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"
# dowód configu: max-num-seqs 32 + Eagle3 ON (kontekst dla P0)
docker inspect vllm --format '{{json .Config.Cmd}}' > "$RUN_DIR/session/engine_cmd.json"
```

---

## Cz. A — tooling liczników GPU + okno idle (45 min)

Trzy tiery, od najlepszego. Ustal `GPU_TOOL` i nie zmieniaj go między oknami
(porównywalność).

### A1 — tier 1: `dcgmi` na hoście

```bash
command -v dcgmi && dcgmi discovery -l && GPU_TOOL=dcgmi
# jeśli discovery pada na braku hostengine:
#   systemctl status nvidia-dcgm 2>/dev/null || true
#   sudo systemctl start nvidia-dcgm   # albo: sudo nv-hostengine
# po starcie powtórz: dcgmi discovery -l && GPU_TOOL=dcgmi
```

Pola (DCGM field IDs): `155`=power W, `1002`=SM_ACTIVE, `1004`=PIPE_TENSOR_ACTIVE,
`1005`=DRAM_ACTIVE, `1009`/`1010`=PCIE_TX/RX bytes.

### A2 — tier 2: dcgm-exporter w kontenerze (gdy brak `dcgmi`/sudo)

```bash
cat > /tmp/dcgm-custom.csv <<'EOF'
DCGM_FI_DEV_POWER_USAGE,        gauge, power draw (W)
DCGM_FI_PROF_SM_ACTIVE,         gauge, SM active ratio
DCGM_FI_PROF_PIPE_TENSOR_ACTIVE,gauge, tensor pipe active ratio
DCGM_FI_PROF_DRAM_ACTIVE,       gauge, DRAM active ratio
DCGM_FI_PROF_PCIE_TX_BYTES,     gauge, PCIe TX bytes/s
DCGM_FI_PROF_PCIE_RX_BYTES,     gauge, PCIe RX bytes/s
EOF

docker run -d --rm --gpus all --cap-add SYS_ADMIN --net host \
  --name dcgm-exporter \
  -v /tmp/dcgm-custom.csv:/etc/dcgm-exporter/custom.csv:ro \
  nvcr.io/nvidia/k8s/dcgm-exporter:3.3.5-3.4.1-ubuntu22.04 \
  -f /etc/dcgm-exporter/custom.csv -c 2000
# jeśli pull tagu padnie: sprawdź dostępne tagi w NGC, użyj najbliższego i
# zapisz digest:  docker images --digests | grep dcgm >> "$RUN_DIR/session/session_notes.md"
sleep 10; curl -s http://127.0.0.1:9400/metrics | grep -c '^DCGM_FI_' && GPU_TOOL=exporter
```

### A3 — tier 3 (last resort, zero instalacji): `nvidia-smi dmon`

Degradacja: brak rozbicia tensor-pipe; zostaje power, sm%, mem% (≈DRAM busy),
PCIe rx/tx MB/s — wystarcza do częściowego rozstrzygnięcia H1/H2. Odnotuj
ograniczenie w `session_notes.md`.

```bash
GPU_TOOL=smidmon
```

### Sampler (wspólny dla wszystkich okien)

```bash
sample_window () {  # $1=label  $2=czas_w_sekundach
  out="$P0OUT/$1"
  date +%s > "${out}_start_epoch.txt"
  case "$GPU_TOOL" in
    dcgmi)    dcgmi dmon -e 155,1002,1004,1005,1009,1010 -d 1000 -c "$2" \
                > "${out}_dcgmi.txt" 2>&1 ;;
    exporter) ( for _ in $(seq 1 $(( $2 / 5 ))); do
                  echo "ts=$(date +%s)"
                  curl -s http://127.0.0.1:9400/metrics | grep -E '^DCGM_FI_'
                  sleep 5
                done ) > "${out}_dcgm_exporter.txt" ;;
    smidmon)  timeout "$2" nvidia-smi dmon -s put -o DT -d 1 \
                > "${out}_smidmon.txt" 2>&1 ;;
  esac
  date +%s > "${out}_end_epoch.txt"
}
```

### Okno W_idle (120 s, bez ruchu)

```bash
# upewnij się, że nic nie biegnie:
curl -s 'http://127.0.0.1:9090/api/v1/query?query=vllm:num_requests_running' \
  | jq '.data.result[] | {model: .metric.model_name, v: .value[1]}'
# oczekiwane: 0 dla obu modeli; jeśli nie — poczekaj aż spadnie

sample_window idle 120
nvidia-smi > "$P0OUT/nvidia_smi_idle.txt"
```

---

## Cz. B — okna pod obciążeniem (75 min)

Procedura bench = `serving/runbooks/load-test-and-grafana.md` (zweryfikowana
2026-06-05). Skrót poniżej; przy problemach sięgnij do runbooka.

### B1 — prereqs w kontenerze (klucz: offline env + leaf-deps)

```bash
docker compose -f "$COMPOSE" cp \
  results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl \
  vllm:/tmp/swe_bench_vllm.jsonl

docker compose -f "$COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  pip install -q pandas datasets
  python -c "import pandas, datasets; print(\"deps ok\")"
  ls -la /tmp/swe_bench_vllm.jsonl'
```

> **NIE** instaluj `vllm[bench]` (może przeinstalować vllm/torch i rozwalić
> serwer). Tylko leaf-deps; jak krzyknie o kolejny → dorzuć (`pyarrow`/`pillow`).

### B2 — okno W_single (c=1, decode-dominated, ~4 min)

Random dataset (krótki prompt 64 tok → okno zdominowane przez decode, nie
prefill), `--ignore-eos` wymusza stałe 512 tokenów wyjścia.

```bash
sample_window single_c1 300 & SAMP=$!

docker compose -f "$COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
    --dataset-name random --random-input-len 64 --random-output-len 512 \
    --ignore-eos --num-warmups 3 --num-prompts 40 --max-concurrency 1 \
    --save-result --result-dir /tmp/p0_bench --result-filename single_c1.json \
    --metadata phase=p0 window=single_c1' 

wait $SAMP
```

### B3 — okno W_batched (c=64, jak faza C z 2026-06-05, ~8 min)

```bash
sample_window batched_c64 900 & SAMP=$!

docker compose -f "$COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 256 --ignore-eos \
    --num-prompts 600 --max-concurrency 64 \
    --save-result --result-dir /tmp/p0_bench --result-filename batched_c64.json \
    --metadata phase=p0 window=batched_c64'

wait $SAMP
```

### B4 — zgarnij wyniki + eksport Prometheus per okno

> ⚠️ **Najpierw `cp` z kontenera** — `/tmp` w kontenerze nie przeżyje recreate.

```bash
docker compose -f "$COMPOSE" cp vllm:/tmp/p0_bench "$P0OUT/bench/"

export_range () {  # $1=label $2=start_epoch $3=end_epoch
  for q in 'vllm:num_requests_running{model_name="kimi-k2.6"}' \
           'vllm:num_requests_waiting{model_name="kimi-k2.6"}' \
           'vllm:kv_cache_usage_perc{model_name="kimi-k2.6"}' \
           'rate(vllm:generation_tokens_total{model_name="kimi-k2.6"}[1m])'; do
    safe=$(echo "$q" | tr -c 'A-Za-z0-9' '_' | cut -c1-50)
    curl -sG http://127.0.0.1:9090/api/v1/query_range \
      --data-urlencode "query=$q" --data-urlencode "start=$2" \
      --data-urlencode "end=$3" --data-urlencode "step=5" \
      > "$P0OUT/range_${1}_${safe}.json"
  done
}
export_range single_c1   "$(cat "$P0OUT/single_c1_start_epoch.txt")"   "$(cat "$P0OUT/single_c1_end_epoch.txt")"
export_range batched_c64 "$(cat "$P0OUT/batched_c64_start_epoch.txt")" "$(cat "$P0OUT/batched_c64_end_epoch.txt")"
```

### Interpretacja (laptop-side; tu tylko sanity-check na żywo)

| Okno | H1: HBM-bound przewiduje | H2: PCIe/latency-bound przewiduje |
|---|---|---|
| single c=1 | `DRAM_ACTIVE` wysokie | wszystko niskie (DRAM ≪ 50%, tensor ~0, power ~200 W) — GPU *czeka* na all-reduce |
| batched c=64 | `DRAM_ACTIVE` rośnie wyraźnie z batchem, power rośnie | `DRAM_ACTIVE` zostaje niskie, PCIe bytes rosną z batchem |

Sanity-check na żywo: w oknie batched `DRAM_ACTIVE`/mem% powinno być wyraźnie
wyższe niż w idle. Jeśli liczniki w ogóle nie drgnęły między idle a batched →
tooling nie mierzy (zły tier/pole), nie wyciągaj wniosków — odnotuj i sprawdź
tier niżej.

---

## ⏸ CHECKPOINT 1 — commit P0 zanim ruszysz P2

```bash
du -sh "$P0OUT"   # spodziewane: pojedyncze MB; jeśli dużo więcej → zostaw raw
                  # lokalnie, scommituj okrojone grep-em pliki + ścieżki (polityka repo)
git add "$RUN_DIR"
git commit -m "bench: W1 article P0 GPU counters (idle/c1/c64, 2026-06-10)"
git push origin main
```

---

## Cz. C — P2: hop attribution R1 (60 min)

Warunek wstępny: stack **cichy** (po B odczekaj, aż `num_requests_running`
= 0 — query jak w Cz. A). W trakcie C nie może lecieć żaden inny ruch na Kimi;
`metrics_delta` ma sens tylko przy dokładnie 1 żądaniu między snapshotami.

Prompt = default skryptu (`"Say hi in one short sentence."` — ten sam co
capture 2026-06-05). Dwa warianty `max_tokens`: **64** (reprodukcja
`completed:false` przez proxy — dowód R1, że server-side TTFT identyczny gdy
client-side any-token TTFT = null) i **1024** (odpowiedź dochodzi do contentu
na obu ścieżkach — czysty pomiar narzutu na ukończonym żądaniu).

```bash
# warmup po jednym żądaniu na ścieżkę (nie liczy się do pomiaru)
uv run python -m benchmarks.scripts.measure_ttft_once \
  --base-url http://127.0.0.1:8000 --model kimi-k2.6 \
  --api-key "$LITELLM_MASTER_KEY" --max-tokens 64 \
  --output "$P2OUT/warmup_direct.json"
uv run python -m benchmarks.scripts.measure_ttft_once \
  --base-url http://127.0.0.1:4000 --model kimi-k2.6 \
  --api-key "$LITELLM_MASTER_KEY" --max-tokens 64 \
  --output "$P2OUT/warmup_proxy.json"

hop_once () {  # $1=label(direct|proxy) $2=base_url $3=max_tokens $4=idx
  tag="${1}_mt${3}_${4}"
  uv run python -m benchmarks.scripts.collect_metrics_snapshot \
    --base-url http://127.0.0.1:8000 --output "$P2OUT/${tag}_pre.json"
  uv run python -m benchmarks.scripts.measure_ttft_once \
    --base-url "$2" --model kimi-k2.6 --api-key "$LITELLM_MASTER_KEY" \
    --max-tokens "$3" --output "$P2OUT/${tag}_client.json"
  uv run python -m benchmarks.scripts.collect_metrics_snapshot \
    --base-url http://127.0.0.1:8000 --output "$P2OUT/${tag}_post.json"
  uv run python -m benchmarks.scripts.metrics_delta \
    --pre "$P2OUT/${tag}_pre.json" --post "$P2OUT/${tag}_post.json" \
    --output "$P2OUT/${tag}_delta.json"
}

for mt in 64 1024; do
  for i in 1 2 3 4 5; do          # ABBA: nieparzyste direct-first, parzyste proxy-first
    if [ $((i % 2)) = 1 ]; then
      hop_once direct http://127.0.0.1:8000 "$mt" "$i"
      hop_once proxy  http://127.0.0.1:4000 "$mt" "$i"
    else
      hop_once proxy  http://127.0.0.1:4000 "$mt" "$i"
      hop_once direct http://127.0.0.1:8000 "$mt" "$i"
    fi
  done
done
```

**Kontrola jakości na bieżąco:** `metrics_delta` wypisuje
`d_count=<n> request` per histogram — dla `e2e_request_latency` musi być
**`d_count=1`**. Jeśli 0 lub ≥2 → ta para jest skażona (równoległy ruch /
snapshot przed zakończeniem) — powtórz parę z kolejnym indeksem i odnotuj.

**Bonus (1 komenda):** nagłówek narzutu LiteLLM na żądaniu non-stream:

```bash
curl -is http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H 'Content-Type: application/json' \
  -d '{"model":"kimi-k2.6","messages":[{"role":"user","content":"Say hi in one short sentence."}],"max_tokens":64,"stream":false}' \
  | tee "$P2OUT/proxy_overhead_header.txt" | grep -i x-litellm
```

---

## Cz. D — close-out (30 min)

```bash
# jeśli startował tier-2:
docker stop dcgm-exporter 2>/dev/null || true

docker compose -f "$COMPOSE" ps > "$RUN_DIR/session/docker_ps_end.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
find "$RUN_DIR" -type f | sort > "$RUN_DIR/session/artifact_manifest.txt"

$EDITOR "$RUN_DIR/session/session_notes.md"
# zanotuj: użyty GPU_TOOL (tier!), tag/digest exportera jeśli tier-2, pary P2
# powtórzone z powodu d_count≠1, wszystko co odbiegło od planu

git status
git add "$RUN_DIR"
git commit -m "bench: W1 article evidence 2026-06-10 (P0 close-out + P2 hop attribution)"
git push origin main
```

Zaktualizuj [docs/operations/agent-state.md](../operations/agent-state.md):
"In flight" (artykuł W1 — P0/P2 zebrane), "Last validation" (data + artefakty),
wpis "Handoff log". Stack zostaje **up** w stanie zastanym (produkcyjny config,
bez override'ów); jeśli polityka slotu wymaga zgaszenia — `docker compose down`
na obu plikach po commicie.

---

## Mapa artefakt → sekcja artykułu

- **P0** → Inv 5 / sekcja 7: `p0_gpu_counters/{idle,single_c1,batched_c64}_*`,
  `range_*.json`, `bench/{single_c1,batched_c64}.json` — werdykt
  roofline-box (H1 vs H2), promocja L1 → L2 dla "memory-bound vs comms-bound".
- **P2** → Inv 2–3 / sekcje 4–5: `p2_hop_attribution/*_delta.json` +
  `*_client.json` — `outside_proxy − outside_direct` per wariant; dowód
  "server-side identyczny, client-side rozjechany" dla mt=64.

## Fallbacki

- **A: brak dcgmi i pull exportera pada** → tier-3 `nvidia-smi dmon` (degradacja
  opisana w A3); sesja idzie dalej.
- **B: prereqs benchu padają** (pip offline itp.) → W_single zastąp
  `run_bench_suite --runs 10 --max-tokens 1024` direct `:8000` (krótki prompt,
  decode-window słabszy ale użyteczny); W_batched zastąp 16 równoległymi
  instancjami `run_bench_suite` w tle (`&`) — prymitywna konkurencja zamiast
  `vllm bench serve`. Odnotuj w session notes.
- **C: powtarzające się `d_count≠1`** → sprawdź, czy nie biegnie OpenWebUI /
  inny klient (`docker compose -f "$COMPOSE" ps`, ewentualnie `stop open-webui`
  na czas C; po sesji z powrotem `up -d`).

## Świadomie poza scope

- P1 (Eagle3 n=20 A/B z naprawioną impurity) i P3 (concurrency sweep) —
  odrzucone decyzją 2026-06-09.
- Tuning `num_speculative_tokens` — poza roadmapą W1.
- Wpinanie dcgm-exportera do Prometheus/Grafana (pełny #34) — tu tylko
  jednorazowy capture do plików.
- Jakiekolwiek zmiany compose / configu silników.

## Verification (laptop, po sesji)

Sesja nie rusza `.py` — walidacja = spójność artefaktów (epoch-i okien obecne,
`d_count=1` w deltach P2, manifest) + `git log --stat -n 3`. Analiza liczb =
Etap 3 planu deepening.
