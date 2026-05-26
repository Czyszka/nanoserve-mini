# Plan sesji serwerowej — ~4h (ubuntusrv2, 8×H200 NVL)

## Context

Cel sesji: **uzupełnić materiał dowodowy dla W1**
(`docs/writeups/w1-multi-model-serving-baseline.md`). T2 jest napisany;
sesja serwerowa zbiera evidence dla **T8 (proxy overhead), T3 (DeepSeek
VRAM justification), T6 (Eagle3 on/off measurement), T1 (DEP startup
failure)**. T5 (co realnie widać w `/metrics`) jest niskim priorytetem —
robimy lekki capture w tle benchów (Prometheus queries) i ewentualny
pełny screenshot dashboardu jako stretch na samym końcu.

DCGM Exporter / GPU hardware panele — **skreślone**.

Stack jest docelowy: Kimi-K2.6 TP=8+Eagle3 na :8000, DeepSeek-V4-Flash
na :8004 z `--gpu-memory-utilization 0.20`, LiteLLM Proxy na :4000,
Prometheus+Grafana w `serving/compose/docker-compose.observability.yml`.

Restart Kimi (TP=8 + ładowanie wag) kosztuje 5–10 min. Kolejność:
najpierw rzeczy bez restartów modeli (T8), potem T3 (tylko `vllm-small`),
potem **jedna** sekwencja Kimi: bench Eagle3-ON → stop → próba DEP (T1) →
start bez Eagle3 → bench (T6 off) → restore z Eagle3. T5 dashboard
walidacja na końcu jeśli zostanie czas.

---

## Budżet (~240 min)

| Cz. | Co | Czas | Restart |
|---|---|---:|---|
| 0 | Start, `git pull`, snapshot live state, `rg` install | 10 | — |
| A | **T8** — proxy overhead A/B parami (Kimi + DeepSeek) | 35 | — |
| B | **T3** — DeepSeek VRAM sweep: 0.15 i 0.25 (oba) | 45 | vllm-small ×2 |
| **CHECKPOINT 1 (~90 min) — ruszamy Kimi (C–G)?** | | | |
| C | **T6** — bench Kimi z Eagle3 ON (obecny stan, bez restartu) | 15 | — |
| D | Stop Kimi | 2 | Kimi down |
| E | **T1** — DEP capture: override z DEP/DP, capture fail | 15 | — |
| F | **T6** — Start Kimi bez Eagle3 + bench OFF | 30 | Kimi |
| G | Restore Kimi z Eagle3 + smoke | 15 | Kimi |
| **CHECKPOINT 2 (~207 min) — czy zostaje 15+ min na T5?** | | | |
| H | **T5** — dashboard pod load + Prometheus snapshoty + screenshot | 18 | — |
| I | Commit + push + agent-state | 15 | — |

Sum: 10+35+45+15+2+15+30+15+18+15 = **200 min**, bufor **40 min**.

Must-have: A, B, C, D, E, F, G, I (T8 + T3 + T6 ON/OFF + T1 + commit).
Stretch: H (T5 pełny). Lekki capture T5 (queries Prometheus + raw
`/metrics`) wpisany **na boku** w C i F — czyli T5 i tak coś dostanie.

Reguła odcięcia: w CHECKPOINT 2 jeśli zostało **< 15 min** → omijamy H,
idziemy do I. Czysty zostawiony stack > niedokończony dashboard.

---

## Run directory

```bash
RUN_DIR=results/runs/2026-05-27_w1_evidence
mkdir -p "$RUN_DIR"/{t8_proxy_overhead,t3_deepseek_vram,t6_eagle3,t1_dep,t5_metrics,session}
```

`run_bench_suite.py` tworzy własne katalogi `results/runs/<auto-id>/...`
— ścieżki notujemy w `session/session_notes.md`.

---

## Cz. 0 — start (10 min)

```bash
cd ~/nanoserve-mini
git status
git pull --ff-only origin main
uv sync --extra dev

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml ps > "$RUN_DIR/session/docker_ps_start.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"

command -v rg || sudo apt-get install -y ripgrep

export LITELLM_MASTER_KEY="$(grep '^LITELLM_MASTER_KEY' serving/compose/.env | cut -d= -f2)"
curl -fsS -H "Authorization: Bearer $LITELLM_MASTER_KEY" http://127.0.0.1:4000/v1/models | jq '.data[].id'
curl -fsS http://127.0.0.1:8000/health && echo " kimi OK"
curl -fsS http://127.0.0.1:8004/health && echo " deepseek OK"
```

---

## Cz. A — T8 proxy overhead A/B parami (35 min)

Metoda z #37: różnica parami + odwrócona kolejność w parze + warmup.
Ten sam request leci raz `direct → vllm`, raz `proxy → 4000 → vllm`,
przeplatanie kolejności. Oba modele osobno.

```bash
OUT="$RUN_DIR/t8_proxy_overhead"
mkdir -p "$OUT"

# warmup obu ścieżek dla obu modeli
for url in http://127.0.0.1:8000 http://127.0.0.1:4000; do
  uv run python -m benchmarks.scripts.request_once \
    --base-url $url --model kimi-k2.6 --api-key "$LITELLM_MASTER_KEY" \
    --prompt "warmup" >/dev/null 2>&1 || true
done
for url in http://127.0.0.1:8004 http://127.0.0.1:4000; do
  uv run python -m benchmarks.scripts.request_once \
    --base-url $url --model DeepSeek-V4-Flash --api-key "$LITELLM_MASTER_KEY" \
    --prompt "warmup" >/dev/null 2>&1 || true
done

# Kimi: 10 par. Pierwsze 5: A=direct,B=proxy. Kolejne 5: B=proxy,A=direct
for i in $(seq 1 5); do
  uv run python -m benchmarks.scripts.measure_ttft_once \
    --base-url http://127.0.0.1:8000 --model kimi-k2.6 \
    --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
    --output "$OUT/kimi_${i}_A_direct.json"
  uv run python -m benchmarks.scripts.measure_ttft_once \
    --base-url http://127.0.0.1:4000 --model kimi-k2.6 \
    --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
    --output "$OUT/kimi_${i}_B_proxy.json"
done
for i in $(seq 6 10); do
  uv run python -m benchmarks.scripts.measure_ttft_once \
    --base-url http://127.0.0.1:4000 --model kimi-k2.6 \
    --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
    --output "$OUT/kimi_${i}_B_proxy.json"
  uv run python -m benchmarks.scripts.measure_ttft_once \
    --base-url http://127.0.0.1:8000 --model kimi-k2.6 \
    --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
    --output "$OUT/kimi_${i}_A_direct.json"
done

# DeepSeek: analogicznie 8004 vs 4000
for i in $(seq 1 5); do
  uv run python -m benchmarks.scripts.measure_ttft_once \
    --base-url http://127.0.0.1:8004 --model DeepSeek-V4-Flash \
    --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
    --output "$OUT/ds_${i}_A_direct.json"
  uv run python -m benchmarks.scripts.measure_ttft_once \
    --base-url http://127.0.0.1:4000 --model DeepSeek-V4-Flash \
    --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
    --output "$OUT/ds_${i}_B_proxy.json"
done
for i in $(seq 6 10); do
  uv run python -m benchmarks.scripts.measure_ttft_once \
    --base-url http://127.0.0.1:4000 --model DeepSeek-V4-Flash \
    --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
    --output "$OUT/ds_${i}_B_proxy.json"
  uv run python -m benchmarks.scripts.measure_ttft_once \
    --base-url http://127.0.0.1:8004 --model DeepSeek-V4-Flash \
    --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
    --output "$OUT/ds_${i}_A_direct.json"
done

# cross-check: snapshot metryk LiteLLM (upstream vs total)
curl -s http://127.0.0.1:4000/metrics > "$OUT/litellm_metrics_post.txt"
```

Interpretacja par-delt (delta = proxy − direct) — laptop-side po sesji.

---

## Cz. B — T3 DeepSeek VRAM sweep 0.15 i 0.25 (45 min)

Justification z liczbami dla wybranego 0.20: konkretnie odrzucone
warianty 0.15 (za nisko) i 0.25 (za wysoko, ryzyko OOM / mniej miejsca
dla Kimi).

**Wymaga pre-flight laptopowego** (patrz niżej): zamienić w
[serving/compose/docker-compose.kimi-k2.6.yml](serving/compose/docker-compose.kimi-k2.6.yml)
dla `vllm-small`: `--gpu-memory-utilization ${DEEPSEEK_GPU_MEM_UTIL:-0.20}`.

```bash
OUT="$RUN_DIR/t3_deepseek_vram"
mkdir -p "$OUT"

# 0. baseline (cap=0.20)
docker logs vllm-small --tail 3000 > "$OUT/log_cap020_baseline.txt"
uv run python -m benchmarks.scripts.measure_ttft_once \
  --base-url http://127.0.0.1:8004 --model DeepSeek-V4-Flash \
  --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
  --output "$OUT/ttft_cap020.json"

# helper
restart_vllm_small () {
  docker compose -f serving/compose/docker-compose.kimi-k2.6.yml stop vllm-small
  docker compose -f serving/compose/docker-compose.kimi-k2.6.yml up -d vllm-small
  for _ in $(seq 1 60); do
    curl -fsS http://127.0.0.1:8004/health >/dev/null && return 0
    sleep 5
  done
  return 1
}

# 1. cap = 0.15
sed -i '/^DEEPSEEK_GPU_MEM_UTIL=/d' serving/compose/.env
echo "DEEPSEEK_GPU_MEM_UTIL=0.15" >> serving/compose/.env
restart_vllm_small && {
  docker logs vllm-small --tail 3000 > "$OUT/log_cap015.txt"
  uv run python -m benchmarks.scripts.measure_ttft_once \
    --base-url http://127.0.0.1:8004 --model DeepSeek-V4-Flash \
    --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
    --output "$OUT/ttft_cap015.json"
} || {
  docker logs vllm-small --tail 3000 > "$OUT/log_cap015_FAILED.txt"
  echo "cap=0.15 did not come up healthy" > "$OUT/cap015_status.txt"
}

# 2. cap = 0.25
sed -i '/^DEEPSEEK_GPU_MEM_UTIL=/d' serving/compose/.env
echo "DEEPSEEK_GPU_MEM_UTIL=0.25" >> serving/compose/.env
restart_vllm_small && {
  docker logs vllm-small --tail 3000 > "$OUT/log_cap025.txt"
  uv run python -m benchmarks.scripts.measure_ttft_once \
    --base-url http://127.0.0.1:8004 --model DeepSeek-V4-Flash \
    --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
    --output "$OUT/ttft_cap025.json"
} || {
  docker logs vllm-small --tail 3000 > "$OUT/log_cap025_FAILED.txt"
  echo "cap=0.25 did not come up healthy" > "$OUT/cap025_status.txt"
}

# 3. revert do 0.20
sed -i '/^DEEPSEEK_GPU_MEM_UTIL=/d' serving/compose/.env
restart_vllm_small
docker logs vllm-small --tail 200 > "$OUT/log_cap020_restored.txt"
```

Materiał T3: linie `Loading model weights`, `KV cache`, ile bloków,
ile MiB wagi, czy zostało miejsca dla Kimi, OOM przy 0.25 (jeśli wystąpi).

---

## ⏸ CHECKPOINT 1 (~90 min)

Decyzja: ruszamy sekwencję Kimi (C–G, ~77 min + bufor)?

- **≥ 90 min** → pełne C, D, E, F, G.
- **60–90 min** → tylko C (bench Eagle3 ON bez restartu), potem I. T1 i T6-OFF zostawiamy.
- **< 60 min** → idziemy do I. Zostawiamy Kimi w czystym Eagle3-ON.

---

## Cz. C — T6 Eagle3 ON bench (15 min)

Kimi już chodzi z Eagle3 — bench bez restartu. **W tle: T5 capture
queries** (lekki).

```bash
OUT="$RUN_DIR/t6_eagle3"
T5OUT="$RUN_DIR/t5_metrics"
mkdir -p "$OUT" "$T5OUT/eagle3-on"

# T5 boczny capture w tle: co 10s przez 120s
( for i in $(seq 1 12); do
    ts=$(date +%s)
    curl -s http://127.0.0.1:8000/metrics > "$T5OUT/eagle3-on/vllm_metrics_${ts}.txt"
    for q in 'vllm:num_requests_running' 'vllm:num_requests_waiting' \
             'rate(vllm:generation_tokens_total[1m])' 'vllm:gpu_cache_usage_perc'; do
      safe=$(echo "$q" | tr -c 'A-Za-z0-9' '_' | cut -c1-40)
      curl -s "http://127.0.0.1:9090/api/v1/query?query=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$q")" \
        > "$T5OUT/eagle3-on/snap_${ts}_${safe}.json"
    done
    sleep 10
  done ) &
T5PID=$!

uv run python -m benchmarks.scripts.run_bench_suite \
  --base-url http://127.0.0.1:4000 \
  --metrics-base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 \
  --api-key "$LITELLM_MASTER_KEY" \
  --warmup 1 --runs 5 \
  --run-id "$(date +%F)_kimi-k2.6_eagle3-on" > "$OUT/bench_on.log" 2>&1

wait $T5PID 2>/dev/null || true
docker logs vllm --tail 1000 > "$OUT/kimi_log_eagle3_on.txt"
```

---

## Cz. D — stop Kimi (2 min)

```bash
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml stop vllm
```

---

## Cz. E — T1 DEP capture (15 min)

Override jednorazowy z DEP/DP zamiast TP=8. Spodziewany deterministyczny
crash; zostawia Kimi down — Cz. F podnosi z innym configiem.

```bash
OUT="$RUN_DIR/t1_dep"
mkdir -p "$OUT"

cat > /tmp/kimi-dep-override.yml <<'EOF'
services:
  vllm:
    command: >-
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6
      --host=0.0.0.0 --port=8000 --trust-remote-code
      --enable-expert-parallel --data-parallel-size 8
      --gpu-memory-utilization 0.7
      --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2
      --enable-auto-tool-choice --language-model-only
EOF

docker compose -f serving/compose/docker-compose.kimi-k2.6.yml \
               -f /tmp/kimi-dep-override.yml up -d vllm

# tail logów do 8 min lub do crashu
( docker logs -f vllm 2>&1 | tee "$OUT/dep_startup.log" ) &
TAIL=$!
sleep 480 || true
kill $TAIL 2>/dev/null || true

# pełen log + engine args + state
docker logs vllm > "$OUT/dep_full.log" 2>&1
docker inspect vllm --format '{{json .Config.Cmd}}' > "$OUT/dep_engine_cmd.json"
docker inspect vllm --format '{{.State.Status}} {{.State.ExitCode}} {{.State.Error}}' > "$OUT/dep_state.txt"

docker compose -f serving/compose/docker-compose.kimi-k2.6.yml stop vllm
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml rm -f vllm
```

---

## Cz. F — start Kimi BEZ Eagle3 + bench T6 OFF (30 min)

```bash
cat > /tmp/kimi-no-eagle3.yml <<'EOF'
services:
  vllm:
    command: >-
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6
      --host=0.0.0.0 --port=8000 --trust-remote-code
      --enable-expert-parallel --tensor-parallel-size 8
      --gpu-memory-utilization 0.7
      --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2
      --enable-auto-tool-choice --language-model-only
EOF

docker compose -f serving/compose/docker-compose.kimi-k2.6.yml \
               -f /tmp/kimi-no-eagle3.yml up -d vllm

# wait healthy
for _ in $(seq 1 90); do
  curl -fsS http://127.0.0.1:8000/health >/dev/null && break || sleep 10
done

OUT="$RUN_DIR/t6_eagle3"
T5OUT="$RUN_DIR/t5_metrics"
mkdir -p "$T5OUT/eagle3-off"

# T5 boczny capture w tle
( for i in $(seq 1 12); do
    ts=$(date +%s)
    curl -s http://127.0.0.1:8000/metrics > "$T5OUT/eagle3-off/vllm_metrics_${ts}.txt"
    for q in 'vllm:num_requests_running' 'vllm:num_requests_waiting' \
             'rate(vllm:generation_tokens_total[1m])' 'vllm:gpu_cache_usage_perc'; do
      safe=$(echo "$q" | tr -c 'A-Za-z0-9' '_' | cut -c1-40)
      curl -s "http://127.0.0.1:9090/api/v1/query?query=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$q")" \
        > "$T5OUT/eagle3-off/snap_${ts}_${safe}.json"
    done
    sleep 10
  done ) &
T5PID=$!

uv run python -m benchmarks.scripts.run_bench_suite \
  --base-url http://127.0.0.1:4000 \
  --metrics-base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 \
  --api-key "$LITELLM_MASTER_KEY" \
  --warmup 1 --runs 5 \
  --run-id "$(date +%F)_kimi-k2.6_eagle3-off" > "$OUT/bench_off.log" 2>&1

wait $T5PID 2>/dev/null || true
docker logs vllm --tail 1000 > "$OUT/kimi_log_eagle3_off.txt"
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml stop vllm
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml rm -f vllm
```

---

## Cz. G — restore Kimi z Eagle3 (15 min)

```bash
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml up -d vllm

for _ in $(seq 1 90); do
  curl -fsS http://127.0.0.1:8000/health >/dev/null && break || sleep 10
done

uv run python -m benchmarks.scripts.measure_ttft_once \
  --base-url http://127.0.0.1:4000 --model kimi-k2.6 \
  --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
  --output "$RUN_DIR/session/restore_smoke.json"
```

---

## ⏸ CHECKPOINT 2 (~207 min)

Zostało ≥ 15 min? → H. Jeśli nie → od razu I.

---

## Cz. H — T5 dashboard pod load + screenshoty (18 min, stretch)

```bash
OUT="$RUN_DIR/t5_metrics/full-load"
mkdir -p "$OUT"

# load = oba modele równolegle przez proxy
( uv run python -m benchmarks.scripts.run_bench_suite \
    --base-url http://127.0.0.1:4000 --metrics-base-url http://127.0.0.1:8000 \
    --model kimi-k2.6 --api-key "$LITELLM_MASTER_KEY" \
    --warmup 1 --runs 5 \
    --run-id "$(date +%F)_kimi-k2.6_t5-load" > "$OUT/kimi_load.log" 2>&1 ) &
KIMI_PID=$!
( uv run python -m benchmarks.scripts.run_bench_suite \
    --base-url http://127.0.0.1:4000 --metrics-base-url http://127.0.0.1:8004 \
    --model DeepSeek-V4-Flash --api-key "$LITELLM_MASTER_KEY" \
    --warmup 1 --runs 5 \
    --run-id "$(date +%F)_DeepSeek-V4-Flash_t5-load" > "$OUT/ds_load.log" 2>&1 ) &
DS_PID=$!

# w trakcie loadu: screenshot z lapka (Grafana http://<server>:3001 → vLLM Phase 1)
# zapisz jako t5_dashboard_*.png i wgraj do repo po sesji

# raw /metrics post-load
curl -s http://127.0.0.1:8000/metrics > "$OUT/vllm_kimi_metrics.txt"
curl -s http://127.0.0.1:8004/metrics > "$OUT/vllm_small_metrics.txt"

wait $KIMI_PID $DS_PID
```

---

## Cz. I — commit + push + agent-state (15 min)

```bash
docker compose -f serving/compose/docker-compose.kimi-k2.6.yml ps > "$RUN_DIR/session/docker_ps_end.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"

$EDITOR "$RUN_DIR/session/session_notes.md"

git status
git add results/runs/2026-05-27_w1_evidence
# run_bench_suite auto-id dirs (jeśli powstały):
for d in "results/runs/$(date +%F)_kimi-k2.6_eagle3-on" \
         "results/runs/$(date +%F)_kimi-k2.6_eagle3-off" \
         "results/runs/$(date +%F)_kimi-k2.6_t5-load" \
         "results/runs/$(date +%F)_DeepSeek-V4-Flash_t5-load"; do
  [ -d "$d" ] && git add "$d"
done

git commit -m "bench: W1 evidence (T8 proxy, T3 VRAM, T6 Eagle3, T1 DEP)"
git push origin main
```

Update [docs/operations/agent-state.md](docs/operations/agent-state.md):
- "In flight" #37 — które wątki dostały evidence,
- "Last validation" — wpis z datą + listą artefaktów,
- "Handoff log" — wpis w stylu 2026-05-19.

---

## Pre-flight LAPTOPOWY (do zrobienia DZIŚ)

1. **Param VRAM cap przez env** dla `vllm-small` w
   [serving/compose/docker-compose.kimi-k2.6.yml](serving/compose/docker-compose.kimi-k2.6.yml):
   `--gpu-memory-utilization ${DEEPSEEK_GPU_MEM_UTIL:-0.20}` (potrzebne w Cz. B).
2. **Skopiować ten plan** do
   [docs/plans/2026-05-27-server-session.md](docs/plans/2026-05-27-server-session.md)
   jako repo-tracked artefakt sesji.
3. **Opcjonalnie**: dorzucić ścieżki evidence pod TODO w
   [docs/writeups/w1-multi-model-serving-baseline.md](docs/writeups/w1-multi-model-serving-baseline.md)
   (T1/T3/T6/T8) — żeby po sesji wiedzieć, gdzie dokleić liczby.

Bez tego sesja traci ~15 min na edycje on-the-fly w Cz. B.

---

## Krytyczne pliki

- [serving/compose/docker-compose.kimi-k2.6.yml](serving/compose/docker-compose.kimi-k2.6.yml)
- [serving/compose/docker-compose.observability.yml](serving/compose/docker-compose.observability.yml)
- [serving/compose/prometheus/prometheus.yml](serving/compose/prometheus/prometheus.yml)
- [serving/compose/grafana/provisioning/dashboards/vllm-phase1.json](serving/compose/grafana/provisioning/dashboards/vllm-phase1.json)
- [benchmarks/scripts/run_bench_suite.py](benchmarks/scripts/run_bench_suite.py)
- [benchmarks/scripts/measure_ttft_once.py](benchmarks/scripts/measure_ttft_once.py)
- [docs/writeups/w1-multi-model-serving-baseline.md](docs/writeups/w1-multi-model-serving-baseline.md)
- [docs/operations/agent-state.md](docs/operations/agent-state.md)

## Mapa W1 wątek → artefakt

- **T1** → `t1_dep/dep_full.log`, `dep_engine_cmd.json`, `dep_state.txt`.
- **T3** → `t3_deepseek_vram/log_cap{015,020,025}.txt` + `ttft_cap*.json`.
- **T5** → `t5_metrics/{eagle3-on,eagle3-off,full-load}/vllm_metrics_*.txt` + snap queries (+ screenshoty Grafany jeśli H).
- **T6** → `t6_eagle3/bench_{on,off}.log` + `results/runs/*_eagle3-*/`.
- **T8** → `t8_proxy_overhead/{kimi,ds}_*_{A_direct,B_proxy}.json` + `litellm_metrics_post.txt`.

## Verification (laptop, po sesji)

```bash
uv run ruff check .
uv run pytest -q
git log --stat -n 5
```

Sukces sesji = **A + B + C + D + E + F + G + I** (T8 + T3 + T6 ON/OFF +
T1, Kimi z powrotem w Eagle3-ON). Stretch = H (T5 dashboard).

## Świadomie poza scope

- DCGM Exporter / panele GPU hardware — skreślone na życzenie usera.
- Pełny T3 sweep poza {0.15, 0.20, 0.25}.
- TTFT reconciliation (#34 pkt 1) — laptopowa.
- Pisanie wątków W1 — robota laptopowa po sesji.
- `sample_gpu_metrics` zintegrowane w bench suite, `aggregate_runs.py` —
  odłożone (open question w agent-state).
