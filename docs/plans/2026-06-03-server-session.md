# Plan sesji serwerowej 2026-06-03 — ~3h (ubuntusrv2, 8×H200 NVL)

## Context

Cel sesji: domknąć **brakujące** evidence W1, które wymagają restartów
modeli i dlatego nie dało się ich przygotować na laptopie. Zakres:
**T3 (clean DeepSeek VRAM sweep), T6 (Eagle3 ON/OFF), T1 (DEP startup
failure)**. **T8 NIE wchodzi** — smoke-baseline T8 jest już zebrany
(2026-05-27) i opisany; konkluzywny T8 (concurrency, atrybucja hopów,
macierz workloadów) czeka na osobny współbieżny driver. T5 — tylko
**darmowy boczny capture** w tle benchów Kimi; pełny dashboard to stretch.

**Stack jest aktualnie WYŁĄCZONY** — Cz. 0 najpierw go uruchamia.

Po co znowu, skoro 2026-05-27 już próbowało? Tamta sesja zrobiła T8 +
**częściowy** T3 i nie tknęła T6/T1. T3 wyszedł wadliwie: artefakt
`cap020` przy runtime `gpu_memory_utilization: 0.25`. Ta sesja:

1. robi **czysty** T3 z trzema capami {0.25, 0.15, 0.20}, gdzie cap jest
   ustawiany **tymczasowo w shellu** (`export`, nie edycja `.env`), nazwa
   pliku bierze się z **zweryfikowanego** capa z logu runtime, plus
   `nvidia-smi` per cap (ile VRAM zostaje dla Kimi),
2. robi **jeden spójny blok Kimi**: bench Eagle3 ON → restart OFF →
   bench Eagle3 OFF → (w oknie down) T1 DEP capture → restore ON. ON i
   OFF leżą obok siebie; T1 wpada w obowiązkowe okno zatrzymania Kimi
   przed restore, więc nie kosztuje dodatkowego ładowania modelu,
3. config OFF jest lustrem aktualnej komendy ON minus *wyłącznie*
   `--speculative-config`, z dumpem engine args dla obu stanów jako dowód.

DCGM Exporter / panele GPU hardware — **skreślone**.

### Aktualny stan stacku (z compose, do override'ów)

Kimi `vllm` :8000 — pełna komenda ON (referencja dla T6 OFF / T1 DEP):

```text
--model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0
--port=8000 --trust-remote-code --enable-expert-parallel
--tensor-parallel-size 8 --gpu-memory-utilization 0.65
--tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2
--enable-auto-tool-choice --language-model-only
--speculative-config='{"model":"lightseekorg/kimi-k2.6-eagle3-mla","method":"eagle3","num_speculative_tokens":3}'
--max-num-seqs 1 --max-model-len 131072
```

DeepSeek `vllm-small` :8004 — cap przez `--gpu-memory-utilization
${DEEPSEEK_GPU_MEM_UTIL:-0.25}`. docker compose podstawia tę zmienną z
**shell env w pierwszej kolejności**, więc `export DEEPSEEK_GPU_MEM_UTIL=…`
przed `up` nadpisuje wartość na czas testu bez ruszania `.env`.

---

## Budżet (~180 min, slot 8:00–15:00 daje duży zapas)

| Cz. | Co | Czas | Restart |
|---|---|---:|---|
| 0 | Start: `git pull`, **uruchom kontenery**, load `.env`, snapshot, health | 25 | start całości |
| B | **T3** — clean VRAM sweep 0.25/0.15/0.20 (shell export) + verify + nvidia-smi | 50 | vllm-small ×4 |
| **CHECKPOINT 1 (~75 min) — commit T3 + update agent-state, potem decyzja o Cz. C** | | | |
| C | **Blok Kimi: T6 ON/OFF + T1 DEP + restore** | 70 | Kimi ×3 |
| **CHECKPOINT 2 (~145 min) — zostaje 15+ min na T5?** | | | |
| H | **T5** — dashboard pod load + screenshot (stretch) | 18 | — |
| I | Commit + push + agent-state | 15 | — |

Must-have: **0, B, C, I**. Stretch: H.

Reguła odcięcia: w CHECKPOINT 2 jeśli < 15 min → omijamy H, idziemy do I.
**Czysty zostawiony stack (Kimi w Eagle3-ON) > niedokończony dashboard.**

---

## Run directory

```bash
cd ~/nanoserve-mini
RUN_DIR=results/runs/2026-06-03_w1_evidence
mkdir -p "$RUN_DIR"/{t3_deepseek_vram,t6_eagle3,t1_dep,t5_metrics,session}
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
OBS="serving/compose/docker-compose.observability.yml"
```

Ustaw `RUN_DIR`/`COMPOSE`/`OBS` raz po `cd` i trzymaj w tej samej sesji
shellowej. `run_bench_suite.py` tworzy własne katalogi
`results/runs/<auto-id>/...` — ścieżki notuj w `session/session_notes.md`.

---

## Cz. 0 — start stacku + snapshot (25 min)

Kontenery są wyłączone — najpierw je podnosimy. Kimi (TP=8, ~1T MoE)
ładuje się minutami; `start_period` w healthcheck = 30 min.

```bash
cd ~/nanoserve-mini
RUN_DIR=results/runs/2026-06-03_w1_evidence
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
OBS="serving/compose/docker-compose.observability.yml"
mkdir -p "$RUN_DIR"/{t3_deepseek_vram,t6_eagle3,t1_dep,t5_metrics,session}

git status
git pull --ff-only origin main
uv sync --extra dev

# load env (standardowa metoda: set -a / source / set +a)
set -a; source serving/compose/.env; set +a
test -n "$LITELLM_MASTER_KEY" || { echo "missing LITELLM_MASTER_KEY in .env"; exit 1; }

# .env NIE powinien pinować capa DeepSeeka — sweep robimy w shellu
grep -n '^DEEPSEEK_GPU_MEM_UTIL=' serving/compose/.env \
  && echo "WARNING: .env pins DEEPSEEK_GPU_MEM_UTIL — shell export w Cz.B i tak nadpisze, ale po sesji wróci do tej wartości" \
  || echo "no DEEPSEEK_GPU_MEM_UTIL in .env (default 0.25) — OK"

# START: serving (litellm pociąga vllm + vllm-small) + observability
docker compose -f "$COMPOSE" up -d vllm vllm-small litellm
docker compose -f "$OBS" up -d

# czekaj aż Kimi i DeepSeek są healthy (Kimi wolny start)
echo "waiting for vLLM healthy..."
for _ in $(seq 1 180); do curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 10; done
for _ in $(seq 1 60);  do curl -fsS http://127.0.0.1:8004/health >/dev/null 2>&1 && break; sleep 5;  done
curl -fsS http://127.0.0.1:8000/health && echo " kimi OK"
curl -fsS http://127.0.0.1:8004/health && echo " deepseek OK"
curl -fsS -H "Authorization: Bearer $LITELLM_MASTER_KEY" http://127.0.0.1:4000/v1/models | jq '.data[].id'
curl -fsS http://127.0.0.1:9090/-/healthy && echo " prometheus OK"

# snapshot stanu startowego (po podniesieniu)
git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
docker compose -f "$COMPOSE" ps > "$RUN_DIR/session/docker_ps_start.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"
```

---

## Cz. B — T3 clean DeepSeek VRAM sweep (50 min)

Cel: uzasadnienie capa DeepSeeka z **liczbami** — ile zajmują wagi, ile
zostaje na KV cache, ile VRAM zostaje dla Kimi przy każdym capie, czy
któryś nie wstaje (OOM). Cap ustawiamy **tymczasowo w shellu** (`export`),
nie edytujemy `.env`. Nazwa pliku pochodzi z **zweryfikowanego** runtime
capa (naprawia rozjazd nazwa↔config z 2026-05-27).

```bash
OUT="$RUN_DIR/t3_deepseek_vram"; mkdir -p "$OUT"

# helper: ustaw cap w shellu, recreate vllm-small, czekaj healthy, capture + VERIFY
run_t3_cap () {
  cap="$1"; tag="$(echo "$cap" | tr -d '.')"        # 0.25 -> 025
  export DEEPSEEK_GPU_MEM_UTIL="$cap"                # shell env, NIE .env
  docker compose -f "$COMPOSE" up -d --force-recreate vllm-small

  ok=0
  for _ in $(seq 1 60); do
    curl -fsS http://127.0.0.1:8004/health >/dev/null 2>&1 && { ok=1; break; }
    sleep 5
  done

  if [ "$ok" = 1 ]; then
    docker logs vllm-small --tail 4000 > "$OUT/log_cap${tag}.txt" 2>&1
    nvidia-smi > "$OUT/nvidia_smi_cap${tag}.txt"
    grep -o "'gpu_memory_utilization': [0-9.]*" "$OUT/log_cap${tag}.txt" | head -1 > "$OUT/verify_cap${tag}.txt"
    echo "intended=$cap runtime=$(cat "$OUT/verify_cap${tag}.txt")" | tee -a "$OUT/verify_cap${tag}.txt"
    uv run python -m benchmarks.scripts.measure_ttft_once \
      --base-url http://127.0.0.1:8004 --model DeepSeek-V4-Flash \
      --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
      --output "$OUT/ttft_cap${tag}.json"
  else
    docker logs vllm-small --tail 4000 > "$OUT/log_cap${tag}_FAILED.txt" 2>&1
    nvidia-smi > "$OUT/nvidia_smi_cap${tag}_FAILED.txt"
    echo "cap=$cap did NOT come up healthy (possible OOM / too low headroom)" > "$OUT/cap${tag}_status.txt"
  fi
}

run_t3_cap 0.25     # = obecny default, baseline
run_t3_cap 0.15     # za nisko?
run_t3_cap 0.20     # kandydat

# finał: zdejmij shell override -> wraca do compose default (lub wartości z .env)
unset DEEPSEEK_GPU_MEM_UTIL
docker compose -f "$COMPOSE" up -d --force-recreate vllm-small
for _ in $(seq 1 60); do curl -fsS http://127.0.0.1:8004/health >/dev/null 2>&1 && break; sleep 5; done
docker logs vllm-small --tail 200 > "$OUT/log_restored_default.txt" 2>&1
```

Materiał T3 (laptop): z `log_cap*.txt` — `Loading model weights` (MiB),
`Available KV cache memory`, `GPU KV cache size` (tokeny), ewentualny
OOM/traceback; z `nvidia_smi_cap*.txt` — ile VRAM wolne / dla Kimi.
**Decyzja o finalnym capie zapada laptop-side po sesji.**

> Jeśli `verify_cap*.txt` pokaże runtime ≠ intencja → **przerwij i sprawdź**
> (czy `${DEEPSEEK_GPU_MEM_UTIL}` jest faktycznie podstawiany), zanim
> polecisz dalej — inaczej powtórzysz błąd z 2026-05-27.

---

## ⏸ CHECKPOINT 1 (~75 min) — najpierw zapisz T3, potem decyzja

**Zabezpiecz T3 zanim ruszysz blok Kimi** — gdyby sesja się urwała na
restartach Kimi, evidence T3 jest już w repo i stan odzwierciedlony.

```bash
git add results/runs/2026-06-03_w1_evidence/t3_deepseek_vram \
        results/runs/2026-06-03_w1_evidence/session
git commit -m "bench: W1 T3 DeepSeek VRAM sweep (2026-06-03)"
git push origin main
```

Krótki update [docs/operations/agent-state.md](../operations/agent-state.md)
— **tylko T3**: "In flight" #37 (T3 clean sweep {0.25,0.15,0.20} zebrany,
nazwy zweryfikowane z runtime), "Last validation" (data + artefakty T3).
Commit + push tego osobno albo doklej do commitu T3.

Decyzja: ruszamy blok Kimi (Cz. C, ~70 min)?

- **≥ 90 min do końca slotu** → pełne C (T6 ON/OFF + T1 + restore).
- **45–90 min** → tylko C1 (bench Eagle3 ON, bez restartu) → restore nie
  potrzebny (Kimi już ON) → I. T6-OFF i T1 zostają.
- **< 45 min** → od razu I (już po commicie T3). Kimi zostaje w czystym
  Eagle3-ON.

---

## Cz. C — Blok Kimi: T6 Eagle3 ON/OFF + T1 DEP + restore (70 min)

Jeden spójny cykl życia Kimi. Kolejność: **C1 bench ON → C2 bench OFF**
(porównanie T6 obok siebie) → **C3 T1 DEP** (w oknie gdy Kimi i tak stoi)
→ **C4 restore ON**. Restore na końcu, więc kończymy w stanie
produkcyjnym.

### C1 — bench Eagle3 ON (Kimi już chodzi z Cz. 0)

```bash
OUT="$RUN_DIR/t6_eagle3"; T5OUT="$RUN_DIR/t5_metrics"; mkdir -p "$OUT" "$T5OUT/eagle3-on"

# DOWÓD stanu ON: engine args
docker inspect vllm --format '{{json .Config.Cmd}}' > "$OUT/engine_cmd_eagle3_on.json"

# T5 boczny capture (free, w tle): co 10s przez 120s
( for i in $(seq 1 12); do
    ts=$(date +%s)
    curl -s http://127.0.0.1:8000/metrics > "$T5OUT/eagle3-on/vllm_metrics_${ts}.txt"
    for q in 'vllm:num_requests_running' 'vllm:num_requests_waiting' \
             'rate(vllm:generation_tokens_total[1m])' 'vllm:kv_cache_usage_perc'; do
      safe=$(echo "$q" | tr -c 'A-Za-z0-9' '_' | cut -c1-40)
      curl -sG --data-urlencode "query=$q" http://127.0.0.1:9090/api/v1/query \
        > "$T5OUT/eagle3-on/snap_${ts}_${safe}.json"
    done
    sleep 10
  done ) &
T5PID=$!

uv run python -m benchmarks.scripts.run_bench_suite \
  --base-url http://127.0.0.1:4000 --metrics-base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 --api-key "$LITELLM_MASTER_KEY" \
  --warmup 1 --runs 5 \
  --run-id "$(date +%F)_kimi-k2.6_eagle3-on" > "$OUT/bench_on.log" 2>&1

wait $T5PID 2>/dev/null || true
docker logs vllm --tail 1000 > "$OUT/kimi_log_eagle3_on.txt"
```

### C2 — restart bez Eagle3 + bench OFF

OFF = lustro komendy ON minus **wyłącznie** `--speculative-config` (TP=8,
mem 0.65, max-num-seqs 1, max-model-len 131072 zachowane) → fair A/B.

```bash
cat > /tmp/kimi-no-eagle3.yml <<'EOF'
services:
  vllm:
    command: >-
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6
      --host=0.0.0.0 --port=8000 --trust-remote-code
      --enable-expert-parallel --tensor-parallel-size 8
      --gpu-memory-utilization 0.65
      --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2
      --enable-auto-tool-choice --language-model-only
      --max-num-seqs 1 --max-model-len 131072
EOF

docker compose -f "$COMPOSE" -f /tmp/kimi-no-eagle3.yml up -d --force-recreate vllm
for _ in $(seq 1 180); do curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 10; done

T5OUT="$RUN_DIR/t5_metrics"; mkdir -p "$T5OUT/eagle3-off"
docker inspect vllm --format '{{json .Config.Cmd}}' > "$OUT/engine_cmd_eagle3_off.json"  # dowód: brak speculative-config

( for i in $(seq 1 12); do
    ts=$(date +%s)
    curl -s http://127.0.0.1:8000/metrics > "$T5OUT/eagle3-off/vllm_metrics_${ts}.txt"
    for q in 'vllm:num_requests_running' 'vllm:num_requests_waiting' \
             'rate(vllm:generation_tokens_total[1m])' 'vllm:kv_cache_usage_perc'; do
      safe=$(echo "$q" | tr -c 'A-Za-z0-9' '_' | cut -c1-40)
      curl -sG --data-urlencode "query=$q" http://127.0.0.1:9090/api/v1/query \
        > "$T5OUT/eagle3-off/snap_${ts}_${safe}.json"
    done
    sleep 10
  done ) &
T5PID=$!

uv run python -m benchmarks.scripts.run_bench_suite \
  --base-url http://127.0.0.1:4000 --metrics-base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 --api-key "$LITELLM_MASTER_KEY" \
  --warmup 1 --runs 5 \
  --run-id "$(date +%F)_kimi-k2.6_eagle3-off" > "$OUT/bench_off.log" 2>&1

wait $T5PID 2>/dev/null || true
docker logs vllm --tail 1000 > "$OUT/kimi_log_eagle3_off.txt"
docker compose -f "$COMPOSE" stop vllm
docker compose -f "$COMPOSE" rm -f vllm
```

### C3 — T1 DEP capture (Kimi i tak stoi po C2)

Override: DEP (`--enable-expert-parallel --data-parallel-size 8`) zamiast
`--tensor-parallel-size 8`; reszta jak aktualny config; `speculative-config`
pominięty (izolacja ścieżki DEP); `restart: "no"` → jeden czysty crash.

```bash
OUT1="$RUN_DIR/t1_dep"; mkdir -p "$OUT1"

cat > /tmp/kimi-dep-override.yml <<'EOF'
services:
  vllm:
    restart: "no"
    command: >-
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6
      --host=0.0.0.0 --port=8000 --trust-remote-code
      --enable-expert-parallel --data-parallel-size 8
      --gpu-memory-utilization 0.65
      --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2
      --enable-auto-tool-choice --language-model-only
      --max-num-seqs 1 --max-model-len 131072
EOF

docker compose -f "$COMPOSE" -f /tmp/kimi-dep-override.yml up -d vllm

( docker logs -f vllm 2>&1 | tee "$OUT1/dep_startup.log" ) &
TAIL=$!; sleep 480 || true; kill $TAIL 2>/dev/null || true

docker logs vllm > "$OUT1/dep_full.log" 2>&1
docker inspect vllm --format '{{json .Config.Cmd}}' > "$OUT1/dep_engine_cmd.json"
docker inspect vllm --format '{{.State.Status}} {{.State.ExitCode}} {{.State.Error}}' > "$OUT1/dep_state.txt"
cat "$OUT1/dep_state.txt"

docker compose -f "$COMPOSE" stop vllm
docker compose -f "$COMPOSE" rm -f vllm
```

Jeśli DEP **nieoczekiwanie wstanie** healthy — to też wynik: zanotuj w
`session_notes.md`, zrób smoke; W1 trzeba będzie przepisać.

### C4 — restore Kimi Eagle3-ON + smoke

```bash
docker compose -f "$COMPOSE" up -d vllm     # bez override = pełny config z Eagle3
for _ in $(seq 1 180); do curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 10; done

docker inspect vllm --format '{{json .Config.Cmd}}' > "$RUN_DIR/session/restore_engine_cmd.json"  # sprawdź: speculative-config znów obecny
uv run python -m benchmarks.scripts.measure_ttft_once \
  --base-url http://127.0.0.1:4000 --model kimi-k2.6 \
  --api-key "$LITELLM_MASTER_KEY" --prompt "say OK" \
  --output "$RUN_DIR/session/restore_smoke.json"
```

Materiał T6: `bench_on.log` vs `bench_off.log` (TTFT, TPOT/ITL, throughput)
przy identycznym workloadzie; `engine_cmd_*` jako dowód, że różni się tylko
Eagle3; z logów Kimi ON — speculative acceptance rate (klucz: czy się opłaca).

---

## ⏸ CHECKPOINT 2 (~145 min)

Zostało ≥ 15 min? → H (stretch). Jeśli nie → od razu I.

---

## Cz. H — T5 dashboard pod load + screenshot (18 min, stretch)

```bash
OUT="$RUN_DIR/t5_metrics/full-load"; mkdir -p "$OUT"

( uv run python -m benchmarks.scripts.run_bench_suite \
    --base-url http://127.0.0.1:4000 --metrics-base-url http://127.0.0.1:8000 \
    --model kimi-k2.6 --api-key "$LITELLM_MASTER_KEY" --warmup 1 --runs 5 \
    --run-id "$(date +%F)_kimi-k2.6_t5-load" > "$OUT/kimi_load.log" 2>&1 ) &
KIMI_PID=$!
( uv run python -m benchmarks.scripts.run_bench_suite \
    --base-url http://127.0.0.1:4000 --metrics-base-url http://127.0.0.1:8004 \
    --model DeepSeek-V4-Flash --api-key "$LITELLM_MASTER_KEY" --warmup 1 --runs 5 \
    --run-id "$(date +%F)_DeepSeek-V4-Flash_t5-load" > "$OUT/ds_load.log" 2>&1 ) &
DS_PID=$!

# w trakcie loadu: screenshot z lapka (Grafana http://<server>:3001 -> vLLM Phase 1)
curl -s http://127.0.0.1:8000/metrics > "$OUT/vllm_kimi_metrics.txt"
curl -s http://127.0.0.1:8004/metrics > "$OUT/vllm_small_metrics.txt"
wait $KIMI_PID $DS_PID
```

---

## Cz. I — commit + push + agent-state (15 min)

```bash
docker compose -f "$COMPOSE" ps > "$RUN_DIR/session/docker_ps_end.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
find "$RUN_DIR" -type f | sort > "$RUN_DIR/session/artifact_manifest.txt"
wc -l < "$RUN_DIR/session/artifact_manifest.txt" > "$RUN_DIR/session/artifact_count.txt"

# potwierdź czysty stan: brak resztkowego shell override
echo "DEEPSEEK_GPU_MEM_UTIL in shell = '${DEEPSEEK_GPU_MEM_UTIL:-<unset>}'"  # powinno być <unset>

$EDITOR "$RUN_DIR/session/session_notes.md"   # co wyszło / co padło / ścieżki auto-id

# T3 jest już zacommitowany w CHECKPOINT 1 — tu dokładamy resztę (T6/T1/T5).
git status
git add results/runs/2026-06-03_w1_evidence
for d in "results/runs/$(date +%F)_kimi-k2.6_eagle3-on" \
         "results/runs/$(date +%F)_kimi-k2.6_eagle3-off" \
         "results/runs/$(date +%F)_kimi-k2.6_t5-load" \
         "results/runs/$(date +%F)_DeepSeek-V4-Flash_t5-load"; do
  [ -d "$d" ] && git add "$d"
done

git commit -m "bench: W1 evidence 2026-06-03 (T6 Eagle3 ON/OFF, T1 DEP, session close-out)"
git push origin main
```

Finalizuj [docs/operations/agent-state.md](../operations/agent-state.md)
(częściowo zaktualizowany już w CHECKPOINT 1 o T3): dopisz T6/T1 do
"In flight" #37, uzupełnij "Last validation", dodaj wpis "Handoff log"
(styl 2026-05-19) obejmujący całą sesję.

---

## Pre-flight LAPTOPOWY (status: gotowe)

Nic do zmiany w kodzie/compose.

1. **Env param VRAM cap** JEST w compose (`${DEEPSEEK_GPU_MEM_UTIL:-0.25}`) —
   T3 działa przez shell `export`, bez edycji `.env`.
2. **Komendy override T6/T1** są lustrem aktualnej komendy ON
   ([docker-compose.kimi-k2.6.yml](../../serving/compose/docker-compose.kimi-k2.6.yml)).
3. Przed sesją tylko: `git pull --ff-only origin main` na serwerze.

**Out of scope tej sesji (osobna robota laptopowa):**
- Konkluzywny T8 — współbieżny driver (nowy kod) + macierz workloadów;
  pełny program R1–R8 w issue #44.
- Atrybucja hopów T8.2 — narzędzia już są gotowe na laptopie:
  `metrics_delta.py` (Δsum/Δcount) + poprawione nazwy w `_server_metrics.py`;
  metoda = snapshot `/metrics` pre/post wokół każdego requestu + diff-of-diffs.
- Pisanie wątków W1 z liczb — laptop po sesji.

---

## Mapa W1 wątek → artefakt (ta sesja)

- **T3** → `t3_deepseek_vram/log_cap{025,015,020}.txt`, `verify_cap*.txt`,
  `nvidia_smi_cap*.txt`, `ttft_cap*.json`, `log_restored_default.txt`.
- **T6** → `t6_eagle3/bench_{on,off}.log`, `engine_cmd_eagle3_{on,off}.json`,
  `kimi_log_eagle3_{on,off}.txt`, `results/runs/*_eagle3-{on,off}/`.
- **T1** → `t1_dep/dep_full.log`, `dep_startup.log`, `dep_engine_cmd.json`,
  `dep_state.txt`.
- **T5** (boczny, free) → `t5_metrics/{eagle3-on,eagle3-off}/...` (+ full-load
  i screenshoty jeśli H).

## Verification (laptop, po sesji)

```bash
uv run ruff check .   # tylko jeśli ruszony .py (nie powinien)
uv run pytest -q
git log --stat -n 5
```

Ta sesja nie rusza `.py` — to bench/config/docs. Walidacja = spójność
artefaktów (verify_cap*, engine_cmd_*, dep_state) i `git log`.

Sukces sesji = **0 + B + C + I** (T3 clean sweep + T6 ON/OFF + T1 DEP,
Kimi z powrotem w Eagle3-ON, shell bez override capa). Stretch = H.

## Świadomie poza scope

- DCGM Exporter / panele GPU hardware — skreślone.
- T8 (każda forma) — smoke gotowy, konkluzywny czeka na driver.
- T3 capy poza {0.15, 0.20, 0.25}.
- `sample_gpu_metrics` w bench suite, `aggregate_runs.py` — odłożone.
