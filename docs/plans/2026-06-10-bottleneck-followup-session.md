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

- **A — Qwen TP-curve:** **pełne powtórzenie badania dla TP=2** (capture z
  2026-06-10 jest wybrakowany — zły log, brak bench JSON) **+ nowe TP=8 i
  TP=4** → krzywa TPOT/throughput vs ranki 1/2/4/8 (TP=1 mamy czysty z
  2026-06-10). Bonus: recovery starego okna TP2 z TSDB jako cross-check.
  Materiał pod W2 (TP scaling). Uwaga topologiczna (datasheet SYS-521GE-TNRT,
  dual-root + pary za switchami): domyślne placement daje TP=2 → GPU{0,1}
  (wspólny switch), TP=4 → GPU{0–3} (wspólny socket), TP=8 → przez UPI —
  krzywa mierzy więc nie tylko liczbę ranków, ale i klasę łącza; notować to
  przy interpretacji.
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
| 0 | start, observability, **serving DOWN**, topologia, snapshot | 25 | — |
| A0 | okno idle (wspólne) + bonus: recovery starego TP2 z TSDB | 15 | — |
| A1 | Qwen **TP=2** — pełne badanie (KROKI 1–7) | 40 | qwen ×1 |
| A2 | Qwen **TP=8** — jw. (kotwica r_PCIe(8) dla Kimi) | 40 | qwen ×1 |
| A3 | Qwen **TP=4** — jw. (dopełnienie krzywej) | 40 | qwen ×1 |
| A4 (stretch) | Qwen TP=2 na parze cross-socket (GPU 0,4) — pomiar podatku UPI | 25 | qwen ×1 |
| **CHECKPOINT 1 — commit A** | | 10 | |
| C | Qwen TP=2 + `NCCL_P2P_DISABLE=1`: bench c=1/c=64 | 30 | qwen ×1 |
| B | Kimi TP=8 + profiler env: load, profile c=1, podsumowanie traców | 60 | kimi ×1 |
| D | restore Kimi (plain compose) + close-out + commit | 40 | kimi ×1 |

Must-have: **0, A1 (TP2), A2 (TP8), B, D**. Kimi sprawdzamy mimo że tylko
TP=8 jest możliwe (554 GiB / 4 > 140 GiB/GPU) — Cz. B właśnie to robi.
Przy braku czasu tnij w kolejności: **A4 → C → A3 (TP4)**.

---

## Cz. 0 — start (20 min)

```bash
cd ~/nanoserve-mini
# UWAGA: celowo BEZ `set -euo pipefail` — w interaktywnej sesji SSH errexit
# zamyka shell (logout) przy pierwszym błędzie i tracisz funkcje/zmienne
# z Cz. 0. Fail-fast siedzi jawnie w funkcjach (`|| return 1` + statusy).

RUN_DIR=results/runs/$(date +%F)_bottleneck
P0OUT="$RUN_DIR/qwen_tp_curve"; PROF="$RUN_DIR/kimi_profiler"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
QWEN_COMPOSE="serving/compose/docker-compose.qwen3.6.yml"
OBS="serving/compose/docker-compose.observability.yml"
mkdir -p "$P0OUT" "$PROF" "$RUN_DIR/session"

git status && git pull --ff-only origin main
set -a; source .env; set +a

docker network inspect nanoserve-net >/dev/null 2>&1 || docker network create nanoserve-net
docker compose -f "$OBS" up -d
curl -fsS http://127.0.0.1:9090/-/healthy && echo "prometheus OK"

# serving DOWN na czas Qwen (VRAM!)
docker compose -f "$COMPOSE" stop litellm open-webui vllm vllm-small 2>/dev/null || true
docker compose -f "$QWEN_COMPOSE" stop vllm 2>/dev/null || true
# usuń zatrzymany kontener `vllm`, żeby start z compose Qwena nie trafił na
# konflikt nazwy (oba pliki deklarują container_name: vllm)
docker compose -f "$COMPOSE" rm -f vllm 2>/dev/null || true

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

wait_http_health () {  # $1=url $2=attempts $3=sleep_seconds
  url="$1"; attempts="$2"; pause="$3"
  for _ in $(seq 1 "$attempts"); do
    curl -fsS "$url" >/dev/null 2>&1 && return 0
    sleep "$pause"
  done
  echo "health timeout: $url" >&2
  return 1
}

start_sample_window () {  # $1=label $2=seconds
  sample_window "$1" "$2" &
  SAMPLE_PID=$!
}

stop_sample_window () {
  # kończy okno RAZEM z benchem: ubija dcgmi (dziecko podpowłoki) zamiast
  # czekać do końca okna — czas okna to tylko sufit; zero martwego czekania,
  # zero próbek idle w ogonie, sampler nigdy nie przeżyje do następnego configu
  status=0
  if [ -n "${SAMPLE_PID:-}" ]; then
    pkill -TERM -P "$SAMPLE_PID" 2>/dev/null || true
    wait "$SAMPLE_PID" || status=$?
    unset SAMPLE_PID
  fi
  return "$status"
}
```

---

## Cz. A0 — okno idle (wspólne) + bonus: recovery starego TP2 (15 min)

Jedno okno idle wystarczy dla całej krzywej (stan bezczynny nie zależy od TP;
serving jest DOWN po Cz. 0, więc to baseline pustych GPU):

```bash
sample_window idle 120
nvidia-smi > "$P0OUT/nvidia_smi_idle.txt"
```

**Bonus (opcjonalny cross-check — kanoniczny TP2 da i tak Cz. A1):** stare
okno TP2 z 2026-06-10 (start epoch **1781096733**, 253 próbki) leciało na
`:8000`, więc było scrape'owane (label `model_name="Qwen3.6"`). Retencja
Prometheusa default 15 d; puste wyniki → pomiń bez żalu.

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

## Cz. A1 / A2 / A3 — Qwen TP=2 / TP=8 / TP=4: pełne badanie, krok po kroku (40 min każde)

To jest **pełne powtórzenie metodyki z `2026-06-10-server-session.md` Cz. B**
per wartość TP: verify configu → prereqs → okno c=1 z licznikami → okno c=64 z
licznikami → natychmiastowy zbiór artefaktów. TP=2 wykonujemy **w całości od
nowa** (capture 2026-06-10 jest wybrakowany); TP=8 i TP=4 są nowe. Placement
domyślny (kolejność urządzeń CUDA): TP=2 → GPU{0,1} = wspólny switch PCIe,
TP=4 → GPU{0–3} = wspólny socket, TP=8 → wszystkie = przez UPI; zanotuj to w
session notes przy każdym wyniku (klasa łącza ≠ tylko liczba ranków).

Dedykowany compose Qwen ma ten sam service/container `vllm` i port `8000`, więc
observability zostaje bez zmian. TP, placement i warianty testowe ustawiamy przez
zmienne środowiskowe:

```bash
run_qwen_tp () {  # $1 = TP (2|4|8), optional $2=tag suffix, optional $3=c1-only
  tp="$1"; tag="tp${tp}${2:-}"
  mode="${3:-full}"
  export QWEN_TP="$tp"
  compose_args=(-f "$QWEN_COMPOSE")
  if [ -n "${QWEN_EXTRA_COMPOSE:-}" ]; then
    compose_args+=(-f "$QWEN_EXTRA_COMPOSE")
  fi

  # KROK 1: start silnika z zadanym TP (TP=8: load + capture cudagraphów
  # potrafi trwać >10 min — limit 20 min, health kończy pętlę wcześniej)
  docker compose "${compose_args[@]}" up -d --force-recreate vllm || return 1
  wait_http_health http://127.0.0.1:8000/health 240 5 || return 1

  # ── KROK 2: FAIL-FAST verify — runtime musi potwierdzić TP (lekcja 06-10);
  #            verify grepem po PEŁNYM logu (tail 500 utnie linię configu
  #            przy TP=8 i przy NCCL_DEBUG=INFO); artefakty z kontenera `vllm` ──
  docker inspect vllm --format '{{json .Config.Cmd}}' > "$P0OUT/engine_cmd_${tag}.json"
  # env z redakcją sekretów — surowy dump zawiera HUGGING_FACE_HUB_TOKEN,
  # a $P0OUT idzie do repo na CHECKPOINT 1 (polityka: tokeny nigdy do gita)
  docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | sed -E 's/^(HUGGING_FACE_HUB_TOKEN|HF_TOKEN|[A-Z_]*API_KEY|[A-Z_]*SECRET[A-Z_]*)=.*/\1=REDACTED/' \
    > "$P0OUT/engine_env_${tag}.txt"
  docker logs vllm --tail 500 > "$P0OUT/log_start_qwen_${tag}.txt" 2>&1
  docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$P0OUT/verify_${tag}.txt"
  grep -q "tensor_parallel_size=${tp}" "$P0OUT/verify_${tag}.txt" \
    || { echo "TP MISMATCH — oczekiwane tensor_parallel_size=${tp}, w logu: '$(cat "$P0OUT/verify_${tag}.txt")' — przerwij"; return 1; }

  # ── KROK 3: prereqs benchu w świeżym kontenerze + dataset (po każdym
  #            recreate od zera — pip i /tmp nie przeżywają) ──────────────
  docker compose "${compose_args[@]}" cp \
    results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl vllm:/tmp/swe_bench_vllm.jsonl || return 1
  docker compose "${compose_args[@]}" exec vllm bash -c \
    'rm -rf /tmp/qbench; mkdir -p /tmp/qbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "import pandas,datasets;print(\"deps ok\")"' || return 1

  run_failed=0

  # ── KROK 4: okno c=1 (random 64-in/512-out, ignore-eos) + liczniki dcgmi;
  #            600 s to sufit — stop_sample_window utnie okno na końcu benchu ──
  start_sample_window "qwen_${tag}_c1" 600
  docker compose "${compose_args[@]}" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
      --dataset-name random --random-input-len 64 --random-output-len 512 \
      --ignore-eos --num-warmups 3 --num-prompts 40 --max-concurrency 1 \
      --save-result --result-dir /tmp/qbench --result-filename '"${tag}"'_c1.json'
  bench_status=$?
  stop_sample_window || { echo "WARN: sampler c1 (${tag}) exit != 0"; run_failed=1; }
  [ "$bench_status" -ne 0 ] && { echo "WARN: bench c1 (${tag}) failed"; run_failed=1; }

  # ── KROK 5: okno c=64 (SWE custom, 256-out) + liczniki dcgmi ───────────
  if [ "$mode" = "full" ] && [ "$run_failed" -eq 0 ]; then
    start_sample_window "qwen_${tag}_c64" 900
    docker compose "${compose_args[@]}" exec vllm bash -c '
      export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
      vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
        --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
        --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
        --custom-output-len 256 --ignore-eos --num-prompts 600 --max-concurrency 64 \
        --save-result --result-dir /tmp/qbench --result-filename '"${tag}"'_c64.json'
    bench_status=$?
    stop_sample_window || { echo "WARN: sampler c64 (${tag}) exit != 0"; run_failed=1; }
    [ "$bench_status" -ne 0 ] && { echo "WARN: bench c64 (${tag}) failed"; run_failed=1; }
  fi

  # ── KROK 6: ZAWSZE zbierz artefakty — także po porażce benchu (lekcja
  #            06-10: brak `cp` od razu = bezpowrotna utrata JSON-ów) ─────
  rm -rf "$P0OUT/bench_${tag}"
  mkdir -p "$P0OUT/bench_${tag}"
  docker compose "${compose_args[@]}" cp vllm:/tmp/qbench/. "$P0OUT/bench_${tag}/" || run_failed=1
  expected_json=2; [ "$mode" = "c1-only" ] && expected_json=1
  json_count=$(find "$P0OUT/bench_${tag}" -maxdepth 1 -name '*.json' | wc -l)
  test "$json_count" -eq "$expected_json" || { echo "bench JSON count mismatch (${tag}): got $json_count expected $expected_json"; run_failed=1; }

  # ── KROK 7: log z WŁAŚCIWEGO kontenera + stan kart ─────────────────────
  #            PEŁNY log, bez tail — kontener jest świeży per run, więc log
  #            obejmuje tylko ten run; tail 400 ucinałby c=1 i WARNING-i
  docker logs vllm > "$P0OUT/log_qwen_${tag}.txt" 2>&1
  nvidia-smi > "$P0OUT/nvidia_smi_${tag}.txt"
  return "$run_failed"
}

run_qwen_tp 2     # A1 — re-run wybrakowanego TP=2
run_qwen_tp 8     # A2 — kotwica r_PCIe(8): te same ranki co Kimi
run_qwen_tp 4     # A3 — dopełnienie krzywej
```

**Sanity na żywo (po każdym TP):** `median_tpot_ms` z bench JSON c=1 vs
TP1 = 3.68 ms (2026-06-10). Oczekiwanie przy hipotezie comms: monotoniczny
wzrost TP1 → TP2 → TP4 → TP8; różnice TPOT/krok dzielone przez przyrost rund
dają `r_PCIe(ranks)` do modelu #50.

### Cz. A4 (stretch) — TP=2 na parze cross-socket: bezpośredni pomiar podatku UPI

Domyślny TP=2 siedzi na GPU{0,1} (wspólny switch). Ta sama konfiguracja na
GPU{0,4} (różne sockety) zmienia wyłącznie klasę łącza — różnica TPOT c=1 to
czysty podatek UPI:

```bash
export QWEN_CUDA_VISIBLE_DEVICES=0,4
run_qwen_tp 2 x04 c1-only
grep '^CUDA_VISIBLE_DEVICES=0,4$' "$P0OUT/engine_env_tp2x04.txt" || echo "ZŁY PLACEMENT — wynik A4 nieważny"
unset QWEN_CUDA_VISIBLE_DEVICES
```

## ⏸ CHECKPOINT 1 — commit A

```bash
git add "$RUN_DIR" && git commit -m "bench: qwen TP-curve TP2/TP4/TP8 + TP2 recovery (bottleneck follow-up)" && git push origin main
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
export QWEN_EXTRA_COMPOSE=/tmp/qwen-nop2p.yml
run_qwen_tp 2 _nop2p
docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -E '^NCCL_P2P_DISABLE=1$' | tee "$P0OUT/verify_nop2p_env.txt"
docker logs vllm 2>&1 \
  | grep -im3 -E "P2P (is )?disabled|P2P_DISABLE" | tee "$P0OUT/verify_nop2p_log.txt" || true
# (pełny log, nie tail — NCCL_DEBUG=INFO wypycha linie initu daleko za 500)
unset QWEN_EXTRA_COMPOSE
```

`run_qwen_tp` wykonuje identyczny pair benchy (tag `tp2_nop2p`, prereqs po
recreate, cp od razu). **Interpretacja:** TPOT(tp2_nop2p) ≫ TPOT(tp2) →
komponenta komunikacyjna potwierdzona przyczynowo i zgrubnie zmierzona
(różnica = koszt przejścia P2P→host na tych samych wiadomościach).

Po C: `docker compose -f "$QWEN_COMPOSE" stop vllm && docker compose -f "$QWEN_COMPOSE" rm -f vllm && unset QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_COMPOSE` (czyste pole pod Kimi).

---

## Cz. B — Kimi TP8 pod torch profilerem (60 min)

```bash
docker compose -f "$QWEN_COMPOSE" stop vllm 2>/dev/null || true
docker compose -f "$QWEN_COMPOSE" rm -f vllm 2>/dev/null || true
unset QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_COMPOSE

# vLLM v0.20 nie czyta VLLM_TORCH_PROFILER_DIR (env usunięty z envs.py);
# profiler włącza flaga --profiler-config, a /start_profile rejestruje się
# tylko gdy jest obecna → overlay nadpisuje CAŁĄ komendę (kopia kanonicznej
# z docker-compose.kimi-k2.6.yml + flaga na końcu; trzymać w synchronizacji)
cat > /tmp/kimi-profiler.yml <<'EOF'
services:
  vllm:
    command:
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size 8 --gpu-memory-utilization 0.6 --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2 --enable-auto-tool-choice --language-model-only --max-num-seqs 32 --max-model-len 131072 --max-num-batched-tokens 4096 --speculative-config='{"model":"lightseekorg/kimi-k2.6-eagle3-mla","method":"eagle3","num_speculative_tokens":3,"max_model_len":8192}' --profiler-config='{"profiler":"torch","torch_profiler_dir":"/tmp/vllm_profile"}'
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-profiler.yml up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 180 10
docker inspect vllm --format '{{json .Config.Cmd}}' > "$PROF/engine_cmd.json"   # TP8 + Eagle3 + profiler-config
grep -o 'profiler-config' "$PROF/engine_cmd.json" || { echo "BRAK profiler-config w Cmd — przerwij"; }

# PROFIL KRÓTKI: 1 request c=1 (kilka sekund decode — trace i tak będzie duży)
curl -fsS -X POST http://127.0.0.1:8000/start_profile
uv run python -m benchmarks.scripts.measure_ttft_once \
  --base-url http://127.0.0.1:8000 --model kimi-k2.6 --api-key "$LITELLM_MASTER_KEY" \
  --max-tokens 256 --output "$PROF/profiled_request_c1.json"
curl -fsS -X POST http://127.0.0.1:8000/stop_profile
# trace TP=8 flushuje się nawet kilka minut po stop_profile (8 ranków pisze
# duże JSON-y) — czekaj aż pliki się pojawią, potem aż rozmiary przestaną rosnąć
for _ in $(seq 1 60); do
  n=$(docker compose -f "$COMPOSE" exec vllm bash -c 'ls /tmp/vllm_profile 2>/dev/null | wc -l' | tr -d '[:space:]')
  [ "${n:-0}" -gt 0 ] && break
  sleep 10
done
docker compose -f "$COMPOSE" exec vllm ls -la /tmp/vllm_profile/
sleep 30
docker compose -f "$COMPOSE" exec vllm ls -la /tmp/vllm_profile/   # rozmiary stabilne? dopiero wtedy kopiuj
```

> ⚠️ **Traców NIE commitujemy** (polityka repo — duże profile jak Nsight).
> Kopiuj poza repo (najpierw ustaw `TRACE_DIR`, `cp` z `/.` kopiuje pliki
> wprost do celu, bez zagnieżdżania podkatalogu):
> `TRACE_DIR=~/nanoserve-local/vllm_profile_$(date +%F); mkdir -p "$TRACE_DIR" && docker compose -f "$COMPOSE" cp vllm:/tmp/vllm_profile/. "$TRACE_DIR"/`
> Do repo idzie tylko podsumowanie poniżej + ścieżka lokalna w session notes.

Podsumowanie tracu (rank 0) na serwerze — udział NCCL vs compute vs przerwy:

```bash
# TRACE_DIR jak przy kopiowaniu wyżej (albo własna ścieżka); find rekursywny —
# działa też gdy cp zagnieździł podkatalog. BEZ `exit` (w interaktywnym SSH
# exit zamyka sesję i kasuje zmienne) — przy NOT FOUND popraw TRACE_DIR i powtórz.
T=$(find "$TRACE_DIR" -type f \( -name '*.json' -o -name '*.json.gz' \) | sort | head -n 1)
echo "trace: ${T:-NOT FOUND w $TRACE_DIR}"
[ -n "$T" ] && uv run python - "$T" <<'EOF' | tee "$PROF/trace_summary_rank0.txt"
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
docker compose -f "$COMPOSE" up -d --force-recreate vllm vllm-small litellm open-webui        # plain compose, prod config
wait_http_health http://127.0.0.1:8000/health 180 10
docker inspect vllm --format '{{json .Config.Cmd}}' > "$RUN_DIR/session/restore_engine_cmd.json"
if docker inspect vllm --format '{{json .Config.Cmd}}' | grep -q 'profiler-config'; then
  # BEZ exit (interaktywny SSH!) — napraw ręcznie: up -d --force-recreate vllm
  # z SAMYM plain compose i powtórz check
  echo "UWAGA: profiler flag still present in Cmd after restore" >&2
fi
uv run python -m benchmarks.scripts.measure_ttft_once --base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 --api-key "$LITELLM_MASTER_KEY" --max-tokens 1024 \
  --output "$RUN_DIR/session/restore_smoke.json"

nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
find "$RUN_DIR" -type f | sort > "$RUN_DIR/session/artifact_manifest.txt"
"${EDITOR:-nano}" "$RUN_DIR/session/session_notes.md"
# notuj: ścieżkę lokalną traców, każdy verify_*, odchylenia; dopisz erratę do
# 2026-06-10_extra (log_cap_qwen_tp2.txt = log kontenera TP1; brak bench TP2)

du -sh "$RUN_DIR"            # traców nie ma w repo? sprawdź zanim dodasz
git add "$RUN_DIR" && git commit -m "bench: bottleneck follow-up (qwen NCCL dose-response, kimi profiler summary)" && git push origin main
```

Update `docs/operations/agent-state.md` (In flight, Last validation, Handoff).

---

## Kryteria rozstrzygnięcia (co mówią wyniki)

Wyjścia sesji kalibrują model `T(tp, link) = F_host + N_rounds × r(link, ranks)
+ W_silicon` z #50: `r_PCIe(2/4/8)` z różnic TPOT krzywej Qwen
(ΔTPOT / Δrund na krok, z adnotacją klasy łącza: switch-para / socket / UPI;
A4 wycenia UPI wprost), `r` pod degradacją z wariantu nop2p, udział comms i
`F_host` dla Kimi z podziału spanu w trace'u, `N_rounds` z liczby kerneli NCCL
na krok w trace'ie. Po sesji: przeliczyć tabelę szacunków NVLink w #50 na
wartości zmierzone (laptop-side) i dopiero wtedy formułować rekomendację
zakupową.

| Wynik | Werdykt |
|---|---|
| TPOT rośnie z TP (TP1→TP2→TP4→TP8) przy stałym modelu; nop2p pogarsza dalej | podatek PCIe potwierdzony przyczynowo (L2); rozmiar = różnice TPOT; A4 rozdziela ranki od klasy łącza (UPI) |
| Trace Kimi: comms ≥ ~40% span przy c=1 | Kimi TP8 decode comms-bound wprost (L2) |
| Trace Kimi: gaps/other dominują, comms małe | podłoga per-step (launch/host/MTP) — hipoteza PCIe do rewizji, artykuł znowu do poprawki (uczciwie) |
| TP2 ≈ TP1 TPOT i nop2p bez zmian | komunikacja tania — szukać w podłodze per-step |

## Świadomie poza scope

- D (DeepSeek TP sweep) — odrzucone decyzją 2026-06-10.
- Zmiany topologii/NVLink, NCCL_ALGO sweep, nsys — później/W2.
- Commit surowych traców profilera — zabronione polityką repo.
