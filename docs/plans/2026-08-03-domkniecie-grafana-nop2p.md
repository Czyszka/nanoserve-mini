# Sesja serwerowa — domknięcie dekompozycji + wykresy Grafana + rzut „przed mostkami"

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, NVLink 4-way: wyspy GPU 0-3 / 4-7)
**Slot (założenie):** ~110 min. 1× start Qwen + 2× start Kimi (drugi = restore).
**Kontekst:** issue #50, #51, #34; sesje 08-03 (`gap_fill`, `kimi_trace_nvlink`,
dogrywka `7ac1b01`); ustalenie „kara zimnego pierwszego benchu" z analizy dogrywki.

> **Plan samowystarczalny** — wszystkie komendy inline.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH.
> **NOWA REGUŁA METODYCZNA (obowiązuje od tej sesji):** po każdym starcie
> silnika najpierw bench-wygrzewka NA ODRZUT, dopiero potem pomiar.
> Dowód: zimne pierwsze c64 1747–1851 vs ciepłe drugie 1989–2040 (rozdz. 0).

---

## 0. Po co ta sesja

Dogrywka rozstrzygnęła zagadkę replikacji: **nie ma dryfu dnia, sampler dcgmi
niewinny** (B2 ze samplerem = 2040 = replikacja 07-31); winna była **kara
zimnego pierwszego benchu po starcie silnika (10–15%)** — na 07-31 każdy c64
biegł po c1 (ciepły), na 08-03 rano każdy c64 był pierwszy (zimny).

Trzy cele:

1. **Domknięcie dekompozycji (#50/#51):** ciepły noAR c64 — jedyna brakująca
   komórka. Mamy ciepły AR (~2020) i tylko zimny noAR (1748); dawka kernela
   przy c64 jest przez to nierozstrzygnięta (wiemy tylko, że ≤ ~1,10).
   Do tego dmesg (trzeci podejście — tym razem z gwarancją niepustego pliku)
   i notatka o straconych trace'ach c16.
2. **Wykresy Grafana pod obciążeniem (#34 + prezentacja):** replikacja 1:1
   rampu T5 z 06-05 (runbook `serving/runbooks/load-test-and-grafana.md`,
   fazy **A c4/120 → B c16/300 → C c64/600**, Kimi Eagle3-ON, SWE 256-out) —
   dokładnie ten test wygenerował screen sprzed mostków
   `results/runs/2026-06-05_w1_evidence/2026-06-05_grafana_dashboard-max_num_seqs_32.png`.
   Ten sam test po mostkach = para przed/po do bezpośredniego porównania
   (slajd W6) + domknięcie pozycji „screenshot pod obciążeniem" z #34.
   Faza C (c64 > `max-num-seqs 32`) zapala panel kolejki jak wtedy.
3. **Rzut nvidia-smi „100% util / mały pobór" (hook prezentacji, slajd W0):**
   mostków fizycznie nie odłączymy, ale reżim sprzed mostków da się
   **odtworzyć przyczynowo**: `NCCL_P2P_DISABLE=1` wyłącza transport P2P
   (NVLink przestaje być używany), komunikacja idzie przez pamięć hosta →
   GPU znów „nudzą się" w oczekiwaniu na komunikację: util 100%, moc spada
   do ~110–200 W. **Uczciwość:** to REKONSTRUKCJA reżimu comms-bound, nie
   bit-perfect PCIe (SHM przez hosta jest wolniejsze niż P2P po PCIe było) —
   w prezentacji podpisać „NCCL z wyłączonym P2P — odtworzenie reżimu sprzed
   mostków", a obok pokazać historyczne liczby z committowanych okien dcgmi
   (06-11: 111–185 W przy c≥8). Bonus naukowy: pola NVL w oknie dcgmi powinny
   spaść do ~0 → bezpośredni dowód przyczynowy, że liczniki śledzą transport.

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

| pomiar | odniesienie | predykcja / odczyt |
|---|---|---|
| **ciepły noAR c64** | ciepły AR ~2020 (B2/07-31); zimny noAR 1748 | **≈1950–2100 → kernel@c64 ≈ 0** (cała różnica AR/noAR z gap-fillu była karą zimnego startu) · **≈1750–1850 → kernel realny ~1,10×** (wniosek gap-fillu wraca, tylko mniejszy) |
| Kimi c32 **nop2p** tok/s | 594–608 (NVLink); 285 (PCIe 06-11) | **150–350** — SHM przez hosta gorsze niż PCIe-P2P; spadek vs NVLink ≥1,7× |
| Kimi c32 nop2p: moc/util | NVLink c32: ~270 W | **110–200 W przy GPU-Util 100%** — warunek zrzutu; jeśli moc NIE spada → dawka nie zadziałała, sprawdź env w kontenerze |
| Kimi c32 nop2p: NVL TX/RX | 7,89 GB/s avg (c32, NVLink) | **~0 GB/s** + PCIe RX w górę → dowód przyczynowy liczników; NVL nadal wysokie → NCCL zignorował flagę (sprawdź `docker exec vllm env`) |
| panel kolejki przy c64 | c32: waiting ≈ 0 (`max-num-seqs 32`) | `vllm:num_requests_waiting` > 20 przez większość biegu c64 |
| dmesg | 2× pusty plik | plik NIEPUSTY zawsze (wynik albo jawna notatka o pustym buforze); zero Xid |

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. 0 | start, pull, zwolnienie GPU | 5 |
| Cz. 1 | dmesg (gwarantowany artefakt) + notatka c16 | 3 |
| Cz. 2 | Qwen TP4 noAR: wygrzewka c1 → **pomiar c64 ciepły** | 25 |
| Cz. 3 | Kimi TP8 + `NCCL_P2P_DISABLE=1`: bench c32 w tle + **rzut nvidia-smi** | 30 |
| Cz. 4 | restore plain Kimi + stack → **ramp T5 A/B/C (replikacja 06-05)** + screenshoty | 35 |
| Cz. 5 | snapshoty końcowe, commit | 10 |
| | **razem** | **108** |

**Kolejność cięcia:** Cz. 4 faza A (zostaw B→C — porównywalność screena
wymaga co najmniej C) → Cz. 3 okno dcgmi (sam zrzut zostaje) → Cz. 1 notatki.
**Nietykalne:** Cz. 0, **Cz. 2** (domyka #50), Cz. 4 restore + co najmniej
jeden screenshot, Cz. 5.

---

## Cz. 0 — start (5 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main

RUN_DIR=results/runs/2026-08-03_domkniecie_grafana
QOUT="$RUN_DIR/qwen"; KOUT="$RUN_DIR/kimi"; GOUT="$RUN_DIR/grafana"
COMPOSE=serving/compose/docker-compose.kimi-k2.6.yml
QWEN_COMPOSE=serving/compose/docker-compose.qwen3.6.yml
SWE=results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl
mkdir -p "$QOUT" "$KOUT" "$GOUT" "$RUN_DIR/session"
set -a; source .env; set +a
DCGM_FIELDS=155,1002,1004,1005,1009,1010,1011,1012

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"

docker compose -f "$COMPOSE" stop vllm vllm-small litellm open-webui
docker compose -f "$COMPOSE" rm -f vllm 2>/dev/null || true
nvidia-smi --query-gpu=index,memory.used --format=csv | tee "$RUN_DIR/session/gpu_free_check.csv"
```

Helpery (wklej cały blok):

```bash
sample_window () {  # $1=label $2=sekundy(sufit)
  out="$P0OUT/$1"; date +%s > "${out}_start_epoch.txt"
  dcgmi dmon -e "$DCGM_FIELDS" -d 1000 -c "$2" > "${out}_dcgmi.txt" 2>&1
  date +%s > "${out}_end_epoch.txt"
}
start_sample_window () { sample_window "$1" "$2" & SAMPLE_PID=$!; }
stop_sample_window () {
  status=0
  if [ -n "${SAMPLE_PID:-}" ]; then
    pkill -TERM -P "$SAMPLE_PID" 2>/dev/null || true
    wait "$SAMPLE_PID" || status=$?
    unset SAMPLE_PID
  fi
  return "$status"
}
wait_http_health () {
  url="$1"; attempts="$2"; pause="$3"
  for _ in $(seq 1 "$attempts"); do
    curl -fsS "$url" >/dev/null 2>&1 && return 0
    sleep "$pause"
  done
  echo "health timeout: $url" >&2; return 1
}
ensure_dataset () {
  docker cp "$SWE" vllm:/tmp/swe_bench_vllm.jsonl \
    || { echo "STOP: docker cp — czy kontener 'vllm' stoi?"; return 1; }
  n=$(docker exec vllm sh -c 'wc -l < /tmp/swe_bench_vllm.jsonl' 2>/dev/null | tr -d ' ')
  echo "dataset: ${n:-BRAK} linii"
  { [ -n "$n" ] && [ "$n" -gt 100 ]; } || { echo "STOP: dataset nie dotarł"; return 1; }
}
bench_prereqs () {  # $1=compose
  docker compose -f "$1" exec vllm bash -c \
    'rm -rf /tmp/xbench; mkdir -p /tmp/xbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; echo deps ok' \
    || { echo "PREREQS FAILED"; return 1; }
}
show_bench () {
  python3 - "$1" <<'PYEOF'
import glob, json, sys
for f in sorted(glob.glob(sys.argv[1] + "/*.json")):
    d = json.load(open(f))
    print(f"{f.split('/')[-1]:34s} out tok/s {d.get('output_throughput',0):8.1f}"
          f" | ITL med {d.get('median_itl_ms',0):8.2f}"
          f" | TPOT med {d.get('median_tpot_ms',0):7.2f}"
          f" | done {d.get('completed',0)}")
PYEOF
}
```

---

## Cz. 1 — dmesg z GWARANCJĄ artefaktu + notatka c16 (3 min)

Dwa poprzednie podejścia zostawiły plik 0-bajtowy (nieodróżnialny od
niewykonania). Teraz plik jest niepusty ZAWSZE:

```bash
DM=results/runs/2026-08-03_nvlink_gap_fill/session/dmesg_end.txt
sudo dmesg -T | grep -iE "nvlink|nvrm|xid" | tail -60 > "$DM"
[ -s "$DM" ] || echo "# sudo dmesg przejrzany $(date -Is): bufor pierscieniowy nie siega boota; zero wpisow nvlink/nvrm/xid od poczatku bufora" > "$DM"
cat "$DM" | head -5
grep -qi "xid" "$DM" && echo "UWAGA: Xid — wpisz do #51" || echo "zero Xid — OK"

# notatka o straconych trace'ach c16 (kontener recreate'owany przed kopią):
echo "trace c16 (Cz. 4b sesji trace): NIE skopiowane przed force-recreate przy restore — STRACONE; bench JSON kimi_c16_profiled.json (618 tok/s, ITL 50,09) zachowany; c32 jest kanoniczny" \
  > results/runs/2026-08-03_kimi_trace_nvlink/profile/trace_c16_status.txt
```

---

## Cz. 2 — domknięcie #50: CIEPŁY noAR c64 (25 min) — NIETYKALNY

Jedyna brakująca komórka macierzy: ciepły-vs-ciepły AR/noAR.

```bash
P0OUT="$QOUT"
export QWEN_TP=4
export QWEN_CUDA_VISIBLE_DEVICES=0,1,2,3
export QWEN_EXTRA_ARGS="--disable-custom-all-reduce"

docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 240 5 || echo "START FAILED — nie benchuj"

docker inspect vllm --format '{{json .Config.Cmd}}' > "$QOUT/engine_cmd_noAR_warm.json"
grep -o 'disable-custom-all-reduce' "$QOUT/engine_cmd_noAR_warm.json" \
  || echo "STOP: flaga nie weszła — QWEN_EXTRA_ARGS zignorowany"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$QOUT/verify_noAR_warm.txt"
grep -q "tensor_parallel_size=4" "$QOUT/verify_noAR_warm.txt" || echo "TP MISMATCH — PRZERWIJ"
CAR_REG=$(docker logs vllm 2>&1 | grep -c "custom_all_reduce.py.*Registering" || true)
echo "custom AR registering lines: $CAR_REG (oczekiwane 0)" | tee "$QOUT/allreduce_gate_noAR_warm.txt"

ensure_dataset || echo "PRZERWIJ"
bench_prereqs "$QWEN_COMPOSE"

# WYGRZEWKA NA ODRZUT (c1 random, jak c1 na 07-31 — ta sama sekwencja):
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name random --random-input-len 64 --random-output-len 512 \
    --ignore-eos --num-warmups 3 --num-prompts 40 --max-concurrency 1 \
    --save-result --result-dir /tmp/xbench --result-filename noAR_warmup_c1.json'

# POMIAR — ciepły noAR c64:
start_sample_window "qwen_noAR_warm_c64" 600
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 256 --ignore-eos --num-prompts 600 --max-concurrency 64 \
    --save-result --result-dir /tmp/xbench --result-filename noAR_warm_c64.json'
stop_sample_window || echo "WARN: sampler"

mkdir -p "$QOUT/bench"
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/xbench/. "$QOUT/bench/"
docker logs vllm > "$QOUT/log_qwen_noAR_warm.txt" 2>&1
show_bench "$QOUT/bench"
```

**Odczyt:** vs ciepły AR ~2020 — przedziały w §1. Ta liczba zamyka
dekompozycję link/kernel w T9.

---

## Cz. 3 — rzut „przed mostkami": Kimi TP8 + NCCL_P2P_DISABLE=1 (30 min)

**Cel wizualny:** terminal z `nvidia-smi`, wszystkie 8 GPU: `100%` util,
moc ~110–200 W / 600 W — obraz z hooka prezentacji. **Cel naukowy:** dawka
przyczynowa (NVLink wyłączony logicznie) + NVL≈0 w licznikach.

```bash
docker compose -f "$QWEN_COMPOSE" down
unset QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_ARGS

# overlay: TYLKO env, komenda zostaje kanoniczna z compose
cat > /tmp/kimi-nop2p.yml <<'EOF'
services:
  vllm:
    environment:
      - NCCL_P2P_DISABLE=1
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-nop2p.yml up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 360 5 || echo "KIMI START FAILED"

docker exec vllm env | grep NCCL_P2P_DISABLE | tee "$KOUT/verify_nop2p_env.txt"
grep -q "NCCL_P2P_DISABLE=1" "$KOUT/verify_nop2p_env.txt" || echo "STOP: env nie weszło"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$KOUT/verify_kimi_nop2p.txt"

ensure_dataset || echo "PRZERWIJ"
bench_prereqs "$COMPOSE"

# wygrzewka na odrzut (krótka — nop2p będzie wolne):
docker compose -f "$COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 32 --ignore-eos --num-prompts 32 --max-concurrency 32 \
    --result-dir /tmp/xbench --result-filename warmup_discard.json'

# POMIAR + ZRZUT — bench w TLE, żeby terminal był wolny na nvidia-smi:
P0OUT="$KOUT"
start_sample_window "kimi_c32_nop2p" 900
docker compose -f "$COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 256 --ignore-eos --num-prompts 192 --max-concurrency 32 \
    --save-result --result-dir /tmp/xbench --result-filename kimi_c32_nop2p.json' &
BENCH_PID=$!

sleep 60                                   # niech batch się rozpędzi
nvidia-smi | tee "$KOUT/nvidia_smi_nop2p_under_load.txt"   # dowód do repo
# >>> TERAZ ZRZUT EKRANU <<<  — w DRUGIM terminalu:  watch -n1 nvidia-smi
# czekaj na klatkę: wszystkie 8 GPU Util=100%, Pwr ~110-200W/600W.
# Zapisz screenshot lokalnie; do repo commitnij PNG do
#   docs/presentations/assets/nvidia-smi-nop2p-rekonstrukcja.png
# ETYKIETA (do prezentacji): "NCCL z wylaczonym P2P - odtworzenie rezimu
# comms-bound sprzed mostkow; historyczne PCIe: 111-185 W (dcgmi 06-11)".
sleep 60 && nvidia-smi >> "$KOUT/nvidia_smi_nop2p_under_load.txt"   # druga klatka

wait "$BENCH_PID" || echo "WARN: bench nop2p exit != 0"
stop_sample_window || echo "WARN: sampler nop2p"
mkdir -p "$KOUT/bench"
docker compose -f "$COMPOSE" cp vllm:/tmp/xbench/. "$KOUT/bench/"
docker logs vllm > "$KOUT/log_kimi_nop2p.txt" 2>&1
show_bench "$KOUT/bench"
# szybki odczyt NVL (oczekiwane ~0 przy nop2p):
awk '$1=="GPU" && $9!="N/A"{s+=$9;n++} END{if(n)printf "NVL TX avg %.2f GB/s (n=%d)\n",s/n/1e9,n}' \
  "$KOUT/kimi_c32_nop2p_dcgmi.txt"
```

---

## Cz. 4 — restore + ramp pod Grafanę (35 min)

Restore = produkcyjny Kimi (Eagle3-ON, bez overlaya) — na NIM robimy wykresy,
bo dashboard ma pokazywać prawdziwy stack (w tym panele spec-decode).

### 4a. Restore + przygotowanie Grafany

```bash
docker compose -f "$COMPOSE" up -d --force-recreate vllm    # plain, BEZ overlaya
wait_http_health http://127.0.0.1:8000/health 360 5 || echo "KIMI RESTORE FAILED"
docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep NCCL_P2P_DISABLE && echo "UWAGA: nop2p przetrwal restore — powtorz recreate" \
  || echo "restore czysty (bez nop2p)"
docker compose -f "$COMPOSE" up -d vllm-small litellm open-webui

# stack obserwability — musi stac PRZED rampem:
docker compose -f serving/compose/docker-compose.observability.yml up -d
curl -fsS http://127.0.0.1:9090/-/healthy && echo "prometheus OK"
curl -fsS http://127.0.0.1:3001/api/health && echo "grafana OK"
# target vllm:8000 musi byc UP (scrape 15s):
sleep 20
curl -s http://127.0.0.1:9090/api/v1/targets \
  | grep -o '"health":"[a-z]*"' | sort | uniq -c
```

**W przeglądarce (przygotuj PRZED rampem — IDENTYCZNIE jak 06-05):**

1. `http://<ip-serwera>:3001` (login `admin` / `GRAFANA_ADMIN_PASSWORD`) →
   dashboard **vLLM Phase 1 — nanoserve-mini**.
2. Zakres czasu: **Last 15 minutes**; auto-refresh: **5s** — te same
   ustawienia co przy screenie 06-05 (porównywalność wizualna).
3. Zostaw otwarte — fazy pojawią się na żywo.

### 4b. Ramp T5 — REPLIKACJA 1:1 sekwencji z 06-05 (runbook
`serving/runbooks/load-test-and-grafana.md`, Krok 5)

Te same fazy, te same liczby promptów, ten sam workload i model co przy
screenie sprzed mostków. Jedyna różnica to sprzęt (mostki) — i o to chodzi.
Uwaga porównawcza: przy ~2× throughput fazy skończą się szybciej, więc
schodki na osi czasu będą krótsze — to oczekiwane i samo w sobie jest
wynikiem (ta sama praca w krótszym czasie).

```bash
ensure_dataset || echo "PRZERWIJ"
bench_prereqs "$COMPOSE"

date +%s > "$GOUT/ramp_start_epoch.txt"
docker compose -f "$COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  DS=/tmp/swe_bench_vllm.jsonl
  COMMON="--backend vllm --base-url http://127.0.0.1:8000 --model kimi-k2.6 \
    --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
    --dataset-name custom --dataset-path $DS \
    --custom-output-len 256 --ignore-eos \
    --save-result --result-dir /tmp/xbench \
    --metadata phase=t5-nvlink model=kimi-k2.6 eagle3=on"
  # A — light (jak 06-05; 8 warmupow = wygrzewka silnika zgodnie z nowa regula)
  vllm bench serve $COMMON --num-warmups 8 --num-prompts 120 --max-concurrency 4  --result-filename phaseA_c4.json
  # B — medium
  vllm bench serve $COMMON --num-prompts 300 --max-concurrency 16 --result-filename phaseB_c16.json
  # C — saturate (tu robimy screen)
  vllm bench serve $COMMON --num-prompts 600 --max-concurrency 64 --result-filename phaseC_c64.json'
date +%s > "$GOUT/ramp_end_epoch.txt"

# NAJPIERW cp, POTEM jakikolwiek restart (lekcja z runbooka):
mkdir -p "$GOUT/bench"
docker compose -f "$COMPOSE" cp vllm:/tmp/xbench/. "$GOUT/bench/"
show_bench "$GOUT/bench"
```

### 4c. Screenshoty (jak w Kroku 6 runbooka)

- **W TRAKCIE fazy C**, gdy `Requests waiting` odbije od zera: jeden zbiorczy
  zrzut dashboardu (running na maksie, waiting > 0, p95, KV cache) —
  odpowiednik screena 06-05, zakres Last 15m obejmuje rozbieg A→B→C.
- Nazwa pliku symetryczna do starego:
  `$GOUT/2026-08-03_grafana_dashboard-nvlink-max_num_seqs_32.png`
  (stary: `2026-06-05_grafana_dashboard-max_num_seqs_32.png`) + kopia
  najlepszego ujęcia do `docs/presentations/assets/` pod slajd W6
  (para przed/po obok siebie).
- Opcjonalnie drugie ujęcie po zakończeniu C: pełne schodki A→B→C w kadrze.
- Porównanie liczbowe do podpisu pary: `phaseC_c64.json` vs T5 06-05
  (`results/runs/2026-06-05_w1_evidence/t5_metrics/`) — throughput/ITL/TTFT.

---

## Cz. 5 — snapshoty końcowe + commit (10 min)

```bash
curl -fsS http://127.0.0.1:8000/health && echo "kimi OK"
wait_http_health http://127.0.0.1:8004/health 240 5 && echo "deepseek OK"
docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/restore_ps.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
git rev-parse HEAD > "$RUN_DIR/session/end_commit.txt"

git status
du -sh "$RUN_DIR"     # PNG maja byc male (<1-2 MB); tracow/duzych plikow brak
git add "$RUN_DIR" \
  results/runs/2026-08-03_nvlink_gap_fill/session/dmesg_end.txt \
  results/runs/2026-08-03_kimi_trace_nvlink/profile/trace_c16_status.txt \
  docs/presentations/assets/ 2>/dev/null
git commit -m "bench: cieply noAR c64 (#50), rekonstrukcja nop2p ze zrzutem, ramp Grafana (#34), dmesg #51"
git push -u origin main
```

---

## Po sesji (laptop, poza slotem)

1. Analiza: ciepły noAR → finalna dekompozycja link/kernel; nop2p c32 →
   liczba do slajdu „dawka przyczynowa"; NVL≈0 → wiersz do T9.
2. Docs należne (zbiorczo za cały dzień 08-03): T9 „pomiar po interwencji"
   + **reguła wygrzewki w metodologii** (`benchmark-methodology.md`),
   komentarz #50 z pełną tabelą, zamknięcie #51, infrastructure §2.2,
   usunięcie `NCCL_NVLS_ENABLE=1` z compose Qwena, `sync-state`.
3. Prezentacja: wpiąć zrzut nvidia-smi (W0) i screenshoty Grafany (W6)
   do planu `2026-07-31-nvlink-meetup-prezentacja.md`.

---

## Walidacja planu

```text
git diff --check    (docs-only; skrypty są blokami kodu wewnątrz planu)
```
