# Plan sesji serwerowej (najbliższy slot) — wąskie gardło decode: Qwen TP-curve + Kimi profiler + NCCL dose-response

## Context

**Cel nadrzędny: issue
[#50](https://github.com/Czyszka/nanoserve-mini/issues/50)** — (1) nazwać
aktualne wąskie gardło decode na poziomie L2, (2) skalibrować model decyzyjny
zakupu NVLink 4-way: ile zyskają konfiguracje TP=1/2/4/8 (parametry do
zmierzenia tutaj: `r_PCIe(ranks)`, udział comms w kroku Kimi, podłoga
`F_host`). Wyniki sesji wypełniają tabelę szacunków w #50.

P0 (2026-06-10) obaliło HBM-bound (`DRAM_ACTIVE` ≤9%), a dodatkowe runy Qwen3.6
TP1/TP2 (`results/runs/2026-06-10_extra/`) pokazały sygnaturę podatku PCIe:
TP1 c=64 → 443 W / SMACT 0.68 / DRAMA 0.39 na jednym GPU; TP2 c=64 → 265 W /
SMACT 0.40 / DRAMA 0.18 per GPU + 5.8/6.7 GB/s na PCIe. Ale: (1) **brak liczb
klienckich TP2** (bench JSON niezapisany), (2) TP1 c=1 z zerową komunikacją ma
i tak tylko SMACT 0.47 i ~9 ms/krok → istnieje podłoga narzutu per-step
niezależna od PCIe. Sesja domyka trzy klamry (decyzja usera 2026-06-10: A+B+C;
D — DeepSeek TP sweep — odrzucone):

- **A — Qwen TP-curve:** odzyskać TP2 z Prometheus TSDB + czysty bench TP2 i
  TP4 → krzywa TPOT/throughput vs liczba ranków (jeden model, jedna dźwignia).
  Bonus: materiał pod W2 (TP scaling).
- **B — Kimi torch profiler:** `VLLM_TORCH_PROFILER_DIR` + `/start_profile` /
  `/stop_profile` → udział kernelów NCCL w kroku decode TP=8. Jedyna metoda
  domykająca atrybucję dla Kimi (L2).
- **C — NCCL dose-response:** Qwen TP2 z `NCCL_P2P_DISABLE=1` → jeśli TPOT
  rośnie, składnik komunikacyjny zmierzony przyczynowo.

**Lekcje z 2026-06-10_extra (obowiązują w tej sesji):** logi zgrywać z
WŁAŚCIWEGO kontenera (`docker logs vllm`, nie stary `vllm-qwen`); przed każdym
benchem grep `tensor_parallel_size=<N>` w logu (fail-fast); bench JSON-y `cp`
z kontenera od razu po benchu; `sample_window` musi się skończyć przed
przełączeniem konfiguracji (inaczej dokleja próbki do cudzego pliku).

**Stan startowy:** Kimi/DeepSeek/LiteLLM mogą być up albo down — Cz. A i C
wymagają, żeby były **DOWN** (Qwen bierze `--gpu-memory-utilization 0.9`).
Observability musi być UP (recovery z TSDB). GPU_TOOL = `dcgmi` (tier-1
potwierdzony 2026-06-10).

---

## Budżet (slot 8:00–15:00; ~4 h pracy)

| Cz. | Co | Czas | Restarty |
|---|---|---:|---|
| 0 | start, observability, **serving DOWN**, snapshot | 20 | — |
| A1 | recovery TP2 z Prometheus TSDB (bez GPU) | 20 | — |
| A2 | Qwen TP2: start + verify + bench c=1/c=64 + counters | 35 | qwen ×1 |
| A3 | Qwen TP4: jw. | 35 | qwen ×1 |
| **CHECKPOINT 1 — commit A** | | 10 | |
| C | Qwen TP2 + `NCCL_P2P_DISABLE=1`: bench c=1/c=64 | 30 | qwen ×1 |
| B | Kimi TP8 + profiler env: load, profile c=1, podsumowanie traców | 60 | kimi ×1 |
| D | restore Kimi (plain compose) + close-out + commit | 40 | kimi ×1 |

Must-have: **0, A2, B, D** (A1 to bonus — A2 i tak daje czysty TP2; C i A3
tnij w tej kolejności przy braku czasu: najpierw A3, potem C).

---

## Cz. 0 — start (20 min)

```bash
cd ~/nanoserve-mini
RUN_DIR=results/runs/$(date +%F)_bottleneck
P0OUT="$RUN_DIR/qwen_tp_curve"; PROF="$RUN_DIR/kimi_profiler"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
OBS="serving/compose/docker-compose.observability.yml"
mkdir -p "$P0OUT" "$PROF" "$RUN_DIR/session"

git status && git pull --ff-only origin main
set -a; source .env; set +a

docker compose -f "$OBS" up -d
curl -fsS http://127.0.0.1:9090/-/healthy && echo "prometheus OK"

# serving DOWN na czas Qwen (VRAM!)
docker compose -f "$COMPOSE" stop litellm open-webui vllm vllm-small 2>/dev/null || true

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"

# TOPOLOGIA CPU/PCIe (#50 — weryfikacja dual-socket/UPI; bez obciążenia, 1 min)
nvidia-smi topo -m > "$RUN_DIR/session/nvidia_topo.txt"
lscpu > "$RUN_DIR/session/lscpu.txt"
numactl --hardware > "$RUN_DIR/session/numactl_hardware.txt" 2>&1 || true
# czytanie: w topo macierzy 'SYS' = ścieżka przez UPI między socketami,
# 'NODE'/'PHB' = wspólny root complex. Zanotuj w session_notes, które GPU
# wiszą pod którym socketem — to ustala (a) asymetrię r_PCIe per para,
# (b) jak NVLink 4-way wyspy muszą być sparowane (4+4 per socket).

# sampler jak 2026-06-10 (tier-1 dcgmi)
sample_window () {  # $1=label $2=sekundy
  out="$P0OUT/$1"; date +%s > "${out}_start_epoch.txt"
  dcgmi dmon -e 155,1002,1004,1005,1009,1010 -d 1000 -c "$2" > "${out}_dcgmi.txt" 2>&1
  date +%s > "${out}_end_epoch.txt"
}
```

---

## Cz. A1 — recovery TP2 z Prometheus TSDB (20 min, bez GPU)

Okno TP2 z 2026-06-10: start epoch **1781096733**, sampler zebrał 253 próbki.
Qwen TP2 leciał na `:8000` → był scrape'owany (label `model_name="Qwen3.6"`).
Retencja Prometheusa default 15 d — działa, jeśli slot jest w ciągu ~2 tygodni
od 2026-06-10; jak puste wyniki → trudno, A2 i tak daje czysty TP2.

```bash
START=1781096733; END=$((START+253)); P=http://127.0.0.1:9090/api/v1
for q in 'rate(vllm:generation_tokens_total{model_name="Qwen3.6"}[1m])' \
         'vllm:num_requests_running{model_name="Qwen3.6"}'; do
  safe=$(echo "$q" | tr -c 'A-Za-z0-9' '_' | cut -c1-50)
  curl -sG "$P/query_range" --data-urlencode "query=$q" \
    --data-urlencode "start=$START" --data-urlencode "end=$END" \
    --data-urlencode "step=5" > "$P0OUT/recovery_tp2_${safe}.json"
done
# percentyle ITL/TPOT w oknie (modyfikator @):
for h in inter_token_latency_seconds time_to_first_token_seconds; do
  for qq in 0.5 0.95; do
    curl -sG "$P/query" --data-urlencode \
      "query=histogram_quantile($qq, sum by(le)(increase(vllm:${h}_bucket{model_name=\"Qwen3.6\"}[300s] @ $END)))" \
      > "$P0OUT/recovery_tp2_${h}_p${qq#0.}.json"
  done
done
jq -r '.data.result[0].value[1] // "EMPTY"' "$P0OUT"/recovery_tp2_inter_token_latency_seconds_p5.json
```

---

## Cz. A2 / A3 — Qwen TP2 i TP4: czysty bench + counters (35 min każdy)

Override parametryzowany `QWEN_TP` (komenda = 1:1 z `engine_cmd.json` runów
2026-06-10, tylko TP zmienny):

```bash
cat > /tmp/qwen-override.yml <<'EOF'
services:
  vllm:
    command: >-
      --model Qwen/Qwen3.6-35B-A3B --served-model-name=Qwen3.6
      --host=0.0.0.0 --port=8000 --trust-remote-code
      --tensor-parallel-size ${QWEN_TP:-2} --enable-expert-parallel
      --enable-auto-tool-choice --max-model-len 65536 --max-num-seqs 32
      --gpu-memory-utilization 0.9 --tool-call-parser qwen3_coder
      --reasoning-parser qwen3 --mm-encoder-tp-mode data
      --speculative-config '{"method":"mtp","num_speculative_tokens":3, "max_model_len":8192}'
EOF

run_qwen_tp () {  # $1 = TP (2|4)   — start, VERIFY, prereqs, bench c=1 + c=64, counters, logi
  tp="$1"; tag="tp${tp}"
  export QWEN_TP="$tp"
  docker compose -f "$COMPOSE" -f /tmp/qwen-override.yml up -d --force-recreate vllm
  for _ in $(seq 1 120); do curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 5; done

  # FAIL-FAST: runtime musi potwierdzić TP — inaczej STOP (lekcja z 06-10)
  docker inspect vllm --format '{{json .Config.Cmd}}' > "$P0OUT/engine_cmd_${tag}.json"
  docker logs vllm 2>&1 | grep -o "tensor_parallel_size=[0-9]*" | head -1 | tee "$P0OUT/verify_${tag}.txt"
  grep -q "tensor_parallel_size=${tp}" "$P0OUT/verify_${tag}.txt" || { echo "TP MISMATCH — przerwij"; return 1; }

  # prereqs w świeżym kontenerze + dataset
  docker compose -f "$COMPOSE" cp \
    results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl vllm:/tmp/swe_bench_vllm.jsonl
  docker compose -f "$COMPOSE" exec vllm bash -c \
    'export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python -c "import pandas,datasets;print(\"deps ok\")"'

  # c=1 (random 64/512, jak 06-10)
  sample_window "qwen_${tag}_c1" 240 & S=$!
  docker compose -f "$COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
      --dataset-name random --random-input-len 64 --random-output-len 512 \
      --ignore-eos --num-warmups 3 --num-prompts 40 --max-concurrency 1 \
      --save-result --result-dir /tmp/qbench --result-filename '"${tag}"'_c1.json'
  wait $S

  # c=64 (SWE custom 256-out, jak 06-10)
  sample_window "qwen_${tag}_c64" 300 & S=$!
  docker compose -f "$COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
      --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
      --custom-output-len 256 --ignore-eos --num-prompts 600 --max-concurrency 64 \
      --save-result --result-dir /tmp/qbench --result-filename '"${tag}"'_c64.json'
  wait $S

  # OD RAZU cp wyników + log z WŁAŚCIWEGO kontenera
  docker compose -f "$COMPOSE" cp vllm:/tmp/qbench "$P0OUT/bench_${tag}/"
  docker logs vllm --tail 400 > "$P0OUT/log_qwen_${tag}.txt" 2>&1
}

run_qwen_tp 2     # A2
run_qwen_tp 4     # A3
```

**Sanity na żywo:** TP2 c=1 `median_tpot_ms` z bench JSON vs TP1 3.68 ms —
jeśli wyraźnie wyżej, podatek komunikacyjny widać już na poziomie klienta.

## ⏸ CHECKPOINT 1 — commit A

```bash
git add "$RUN_DIR" && git commit -m "bench: qwen TP-curve TP2/TP4 + TP2 recovery (bottleneck follow-up)" && git push origin main
```

---

## Cz. C — dose-response: Qwen TP2 + NCCL_P2P_DISABLE (30 min)

```bash
cat > /tmp/qwen-nop2p.yml <<'EOF'
services:
  vllm:
    environment:
      NCCL_P2P_DISABLE: "1"
      NCCL_DEBUG: "INFO"
EOF
export QWEN_TP=2
docker compose -f "$COMPOSE" -f /tmp/qwen-override.yml -f /tmp/qwen-nop2p.yml up -d --force-recreate vllm
for _ in $(seq 1 120); do curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 5; done
docker logs vllm 2>&1 | grep -iE "P2P (is )?disabled|P2P_DISABLE" | head -3 | tee "$P0OUT/verify_nop2p.txt"   # dowód dźwigni
```

Potem identyczny pair benchy jak w `run_qwen_tp` (tag `tp2_nop2p`, prereqs po
recreate, cp od razu). **Interpretacja:** TPOT(tp2_nop2p) ≫ TPOT(tp2) →
komponenta komunikacyjna potwierdzona przyczynowo i zgrubnie zmierzona
(różnica = koszt przejścia P2P→host na tych samych wiadomościach).

Po C: `docker compose -f "$COMPOSE" stop vllm && docker compose -f "$COMPOSE" rm -f vllm` (czyste pole pod Kimi).

---

## Cz. B — Kimi TP8 pod torch profilerem (60 min)

```bash
cat > /tmp/kimi-profiler.yml <<'EOF'
services:
  vllm:
    environment:
      VLLM_TORCH_PROFILER_DIR: /tmp/vllm_profile
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-profiler.yml up -d --force-recreate vllm
for _ in $(seq 1 180); do curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 10; done
docker inspect vllm --format '{{json .Config.Cmd}}' > "$PROF/engine_cmd.json"   # TP8 + Eagle3 bez zmian

# PROFIL KRÓTKI: 1 request c=1 (kilka sekund decode — trace i tak będzie duży)
curl -fsS -X POST http://127.0.0.1:8000/start_profile
uv run python -m benchmarks.scripts.measure_ttft_once \
  --base-url http://127.0.0.1:8000 --model kimi-k2.6 --api-key "$LITELLM_MASTER_KEY" \
  --max-tokens 256 --output "$PROF/profiled_request_c1.json"
curl -fsS -X POST http://127.0.0.1:8000/stop_profile
sleep 10
docker compose -f "$COMPOSE" exec vllm ls -la /tmp/vllm_profile/
```

> ⚠️ **Traców NIE commitujemy** (polityka repo — duże profile jak Nsight).
> Kopiuj poza repo: `docker compose -f "$COMPOSE" cp vllm:/tmp/vllm_profile ~/nanoserve-local/vllm_profile_$(date +%F)/`
> Do repo idzie tylko podsumowanie poniżej + ścieżka lokalna w session notes.

Podsumowanie tracu (rank 0) na serwerze — udział NCCL vs compute vs przerwy:

```bash
T=$(ls ~/nanoserve-local/vllm_profile_$(date +%F)/*.json* | head -1)
uv run python - "$T" <<'EOF' | tee "$PROF/trace_summary_rank0.txt"
import json,gzip,sys,collections
p=sys.argv[1]; op=gzip.open if p.endswith('.gz') else open
d=json.load(op(p,'rt'))
ev=[e for e in d.get('traceEvents',[]) if e.get('ph')=='X' and 'dur' in e]
cats=collections.Counter(e.get('cat','?') for e in ev)
print("kategorie:",dict(cats))
kern=[e for e in ev if e.get('cat','').lower() in ('kernel','gpu_op','cuda_runtime_kernel')]
if not kern: kern=ev
def bucket(name):
    n=name.lower()
    if 'nccl' in n or 'allreduce' in n or 'all_reduce' in n or 'allgather' in n or 'alltoall' in n: return 'comms'
    if any(k in n for k in ('gemm','matmul','marlin','mla','attn','moe','silu','norm','quant')): return 'compute'
    if 'graph' in n: return 'cudagraph_opaque'
    return 'other'
agg=collections.Counter(); 
for e in kern: agg[bucket(e.get('name',''))]+=e['dur']
span=max(e['ts']+e['dur'] for e in kern)-min(e['ts'] for e in kern)
tot=sum(agg.values())
print(f"span {span/1e6:.2f}s  kernel-time {tot/1e6:.2f}s  gaps {(span-tot)/1e6:.2f}s ({(span-tot)/span*100:.0f}%)")
for k,v in agg.most_common(): print(f"  {k:18} {v/1e6:8.2f}s  {v/span*100:5.1f}% of span")
EOF
```

**Fallback:** jeśli `cudagraph_opaque` zjada większość czasu (kernele schowane
w graph capture), powtórz profil z dodatkowym override `--enforce-eager` na
komendzie Kimi (jeden dodatkowy restart; wynik oznaczyć jako *eager — wyższy
narzut launchów*, nadal rozdziela NCCL od compute). Stretch (tylko jeśli czas):
drugi profil pod c=8 (8× `measure_ttft_once &` w trakcie start/stop_profile).

---

## Cz. D — restore + close-out (40 min)

```bash
docker compose -f "$COMPOSE" up -d vllm vllm-small litellm        # plain compose, prod config
for _ in $(seq 1 180); do curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 10; done
docker inspect vllm --format '{{json .Config.Cmd}}' > "$RUN_DIR/session/restore_engine_cmd.json"
uv run python -m benchmarks.scripts.measure_ttft_once --base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 --api-key "$LITELLM_MASTER_KEY" --max-tokens 1024 \
  --output "$RUN_DIR/session/restore_smoke.json"

nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
find "$RUN_DIR" -type f | sort > "$RUN_DIR/session/artifact_manifest.txt"
$EDITOR "$RUN_DIR/session/session_notes.md"
# notuj: ścieżkę lokalną traców, każdy verify_*, odchylenia; dopisz erratę do
# 2026-06-10_extra (log_cap_qwen_tp2.txt = log kontenera TP1; brak bench TP2)

du -sh "$RUN_DIR"            # traców nie ma w repo? sprawdź zanim dodasz
git add "$RUN_DIR" && git commit -m "bench: bottleneck follow-up (qwen NCCL dose-response, kimi profiler summary)" && git push origin main
```

Update `docs/operations/agent-state.md` (In flight, Last validation, Handoff).

---

## Kryteria rozstrzygnięcia (co mówią wyniki)

Wyjścia sesji kalibrują model `T(tp, link) = F_host + N_rounds × r(link, ranks)
+ W_silicon` z #50: `r_PCIe(2)` i `r_PCIe(4)` z różnic TPOT krzywej Qwen
(ΔTPOT / Δrund na krok), `r` pod degradacją z wariantu nop2p, udział comms i
`F_host` dla Kimi z podziału spanu w trace'u, `N_rounds` z liczby kerneli NCCL
na krok w trace'ie. Po sesji: przeliczyć tabelę szacunków NVLink w #50 na
wartości zmierzone (laptop-side) i dopiero wtedy formułować rekomendację
zakupową.

| Wynik | Werdykt |
|---|---|
| TPOT rośnie z TP (TP1→TP2→TP4) przy stałym modelu; nop2p pogarsza dalej | podatek PCIe potwierdzony przyczynowo (L2); rozmiar = różnice TPOT |
| Trace Kimi: comms ≥ ~40% span przy c=1 | Kimi TP8 decode comms-bound wprost (L2) |
| Trace Kimi: gaps/other dominują, comms małe | podłoga per-step (launch/host/MTP) — hipoteza PCIe do rewizji, artykuł znowu do poprawki (uczciwie) |
| TP2 ≈ TP1 TPOT i nop2p bez zmian | komunikacja tania — szukać w podłodze per-step |

## Świadomie poza scope

- D (DeepSeek TP sweep) — odrzucone decyzją 2026-06-10.
- Zmiany topologii/NVLink, NCCL_ALGO sweep, nsys — później/W2.
- Commit surowych traców profilera — zabronione polityką repo.
