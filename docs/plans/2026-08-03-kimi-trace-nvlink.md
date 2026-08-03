# Sesja serwerowa — trace Kimi TP8 c32 po NVLinku + domknięcia 08-03

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, NVLink 4-way: wyspy GPU 0-3 / 4-7)
**Slot (założenie):** ~2 h. Restarty silników dozwolone (2× start Kimi wliczony).
**Kontekst:** issue #50 (mechanizm `share × capture`), sesje
`2026-07-31_nvlink_install` + `2026-08-03_nvlink_gap_fill`, baseline trace
`results/summaries/2026-06-11-kimi-tp8-profile.md` (K2 @c16: NCCL 83,9% spanu).

> **Plan samowystarczalny** — wszystkie helpery i komendy inline.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH.
> **Traców NIE commitujemy** (polityka repo) — kopiuj do
> `/home/working/nanoserve-tracing/`, do repo idzie tylko podsumowanie.

---

## 0. Po co ta sesja

**Główny cel: mechanizm.** Werdykt #50 stoi na rachunku
`gain = 1/(1 − share × capture)`. Po stronie *skutku* mamy pomiar (Kimi c32
2,08×, Qwen TP4 2,97×), ale po stronie *mechanizmu* ostatni trace Kimi jest
sprzed interwencji: **NCCL 83,9% spanu @c16 na PCIe** (06-11, w reżimie
anomalii ITL 512 ms). Nie wiemy, co NVLink zrobił z podziałem spanu:

- jeśli NCCL nadal dominuje (>70%) → sufit 6,2× wciąż żywy, komunikacja
  dalej jest dźwignią (NVSwitch/pełna siatka miałaby co zbierać);
- jeśli NCCL spadł do ~połowy → zysk 2,08× jest „domknięty" komunikacyjnie,
  a resztę trzyma floor/gaps — dalsze inwestycje w link mają mały zwrot;
- do tego link-only 2,57× (Qwen, 08-03) **przebija sufit Amdahla 2,14×**
  z share 0,533 — trace po interwencji to jedyny sposób, żeby zobaczyć,
  czego stary model nie liczył (peer-wait? overlap? scheduler?).

**Piggybacki (issue #51 — braki z analizy 08-03):**

- **pkt 2:** `dmesg_end.txt` wyszedł pusty drugi raz (bufor się przekręcił);
  kontrola negatywna „zero błędów NVLink/Xid w kernel logu" wciąż niezapisana.
- **pkt 3:** liczniki NVL 1011/1012 mamy tylko dla TP4 **bez** custom-AR
  (run 07-31 z AR nie miał kolumn NVL — ciche pominięcie); brakuje symetrii
  AR vs noAR w bezpośrednich licznikach + replikacja 2022 tok/s przy okazji.

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

| pomiar | odniesienie | predykcja | odczyt |
|---|---|---|---|
| Kimi c32 trace: udział NCCL w spanie | 83,9% @c16 PCIe (w anomalii) | **55–70%** — arytmetyka: jeśli cały zysk 2,08× zszedł z komunikacji, share_post ≈ (0,839−0,52)/0,48 ≈ 0,66 | >75% → comms nadal dominuje, sufit 6,2× żywy; **<40% → floor wrócił jako limiter**, dalszy upside linku mały |
| Kimi c32 trace: compute share | 4,6% @c16 PCIe | **8–12%** (span się skurczył, compute bez zmian) | — |
| kontrola narzutu profilera | 08-03 c32 ITL med 90,2 ms | profilowany bench ITL w granicach **±15%** | poza pasmem → trace jakościowy, nie ilościowy (jak F3 06-12) |
| Qwen TP4-AR c64 replikacja | 2022 / 1989 (07-31) | **1900–2100** | poza → dryf konfiguracji, sprawdź engine_cmd diff |
| Qwen TP4-AR c64: NVL avg per GPU | noAR: 4,68 GB/s avg (08-03) | **4–7 GB/s** — pola 1011/1012 są link-level, powinny liczyć też P2P load/store kernela AR | **≪1 GB/s → liczniki NIE widzą ruchu custom-AR** — samo w sobie ustalenie do T9 |
| dmesg (sudo, wzorzec + Xid) | 07-31 `dmesg_nvrm.txt` miał wpisy bootowe | wpisy bootowe NVLink + **zero Xid** | jakikolwiek Xid → wpisz do issue #51, nie ignoruj |

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. 0 | start, pull, zwolnienie GPU | 5 |
| Cz. 1 | piggyback pkt 2: dmesg z sudo + Xid | 2 |
| Cz. H | helpery | 2 |
| Cz. 2 | piggyback pkt 3: Qwen TP4 **z** AR, c64 + okno NVL | 25 |
| Cz. 3 | Kimi start z overlayem profilera | 30 |
| Cz. 4 | **trace c32** + flush + kopia poza repo + summary rank0/rank_last | 30 |
| Cz. 4b | opcja: drugi profil @c16 (bez restartu) | 10 |
| Cz. 5 | restore plain Kimi + stack, smoke, commit | 15 |
| | **razem** | **119** |

**Kolejność cięcia:** Cz. 4b → Cz. 2 → Cz. 1.
**Nietykalne:** Cz. 0, **Cz. 3 + Cz. 4** (główny cel), Cz. 5.

---

## Cz. 0 — start (5 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main

RUN_DIR=results/runs/2026-08-03_kimi_trace_nvlink
QOUT="$RUN_DIR/qwen"; KOUT="$RUN_DIR/kimi"; PROF="$RUN_DIR/profile"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
QWEN_COMPOSE="serving/compose/docker-compose.qwen3.6.yml"
SWE=results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl
mkdir -p "$QOUT" "$KOUT" "$PROF" "$RUN_DIR/session"
set -a; source .env; set +a

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"

docker compose -f "$COMPOSE" stop vllm vllm-small litellm open-webui
docker compose -f "$COMPOSE" rm -f vllm 2>/dev/null || true   # kolizja container_name
nvidia-smi --query-gpu=index,memory.used --format=csv | tee "$RUN_DIR/session/gpu_free_check.csv"

# pola DCGM: zestaw zweryfikowany 08-03 (kolumny NVL weszły) — bez ponownego probe'a,
# ale nagłówek pierwszego okna i tak obejrzyj
DCGM_FIELDS=155,1002,1004,1005,1009,1010,1011,1012
```

---

## Cz. 1 — piggyback pkt 2: dmesg (2 min)

```bash
# 08-03 plik wyszedł pusty (bufor przekręcony); sudo + szerszy wzorzec (Xid = błędy GPU).
# Dopisujemy do KATALOGU SESJI 08-03 (uzupełnienie tamtego artefaktu), nie do dzisiejszego:
sudo dmesg -T | grep -iE "nvlink|nvrm|xid" | tail -60 \
  > results/runs/2026-08-03_nvlink_gap_fill/session/dmesg_end.txt
wc -l results/runs/2026-08-03_nvlink_gap_fill/session/dmesg_end.txt   # >0 oczekiwane (wpisy bootowe)
grep -i "xid" results/runs/2026-08-03_nvlink_gap_fill/session/dmesg_end.txt \
  && echo "UWAGA: Xid w logu — przepisz do issue #51" || echo "zero Xid — OK"
```

---

## Cz. H — helpery (wklej cały blok, 2 min)

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

wait_http_health () {  # $1=url $2=próby $3=sekundy przerwy
  url="$1"; attempts="$2"; pause="$3"
  for _ in $(seq 1 "$attempts"); do
    curl -fsS "$url" >/dev/null 2>&1 && return 0
    sleep "$pause"
  done
  echo "health timeout: $url" >&2
  return 1
}

ensure_dataset () {   # po KAŻDYM recreate
  docker cp "$SWE" vllm:/tmp/swe_bench_vllm.jsonl \
    || { echo "STOP: docker cp nie zadziałał — czy kontener 'vllm' stoi?"; return 1; }
  n=$(docker exec vllm sh -c 'wc -l < /tmp/swe_bench_vllm.jsonl' 2>/dev/null | tr -d ' ')
  echo "dataset w kontenerze: ${n:-BRAK} linii"
  { [ -n "$n" ] && [ "$n" -gt 100 ]; } \
    || { echo "STOP: dataset nie dotarł — NIE benchuj"; return 1; }
}

bench_prereqs () {   # $1 = plik compose
  docker compose -f "$1" exec vllm bash -c \
    'rm -rf /tmp/xbench; mkdir -p /tmp/xbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "import pandas,datasets;print(\"deps ok\")"' \
    || { echo "PREREQS FAILED — nie leć dalej"; return 1; }
}

show_bench () {  # $1 = katalog z JSON-ami benchu
  python3 - "$1" <<'PYEOF'
import glob, json, sys
for f in sorted(glob.glob(sys.argv[1] + "/*.json")):
    d = json.load(open(f))
    print(f"{f.split('/')[-1]:30s} out tok/s {d.get('output_throughput', 0):8.1f}"
          f" | ITL med {d.get('median_itl_ms', 0):8.2f}"
          f" | TPOT med {d.get('median_tpot_ms', 0):7.2f}"
          f" | done {d.get('completed', 0)}")
PYEOF
}
```

---

## Cz. 2 — piggyback pkt 3: Qwen TP4 Z custom-AR + okno NVL (25 min)

Identyczna konfiguracja jak 07-31 (TP4, GPU 0-3, custom AR w auto = włączony) —
dziś różni się tylko tym, że okno dcgmi MA kolumny NVL. Daje symetrię AR/noAR
w licznikach + replikację 2022.

```bash
P0OUT="$QOUT"
export QWEN_TP=4
export QWEN_CUDA_VISIBLE_DEVICES=0,1,2,3
unset QWEN_EXTRA_ARGS                        # custom AR w auto → na NVLinku AKTYWNY

docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 240 5 || echo "START FAILED — nie benchuj"

docker inspect vllm --format '{{json .Config.Cmd}}' > "$QOUT/engine_cmd_tp4_ar.json"
docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | sed -E 's/^(HUGGING_FACE_HUB_TOKEN|HF_TOKEN|[A-Z_]*API_KEY|[A-Z_]*SECRET[A-Z_]*)=.*/\1=REDACTED/' \
  > "$QOUT/engine_env_tp4_ar.txt"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$QOUT/verify_tp4_ar.txt"
grep -q "tensor_parallel_size=4" "$QOUT/verify_tp4_ar.txt" || echo "TP MISMATCH — PRZERWIJ"
grep '^CUDA_VISIBLE_DEVICES=0,1,2,3$' "$QOUT/engine_env_tp4_ar.txt" \
  || echo "ZŁY PLACEMENT — porównanie z 2022 nieważne"
CAR_REG=$(docker logs vllm 2>&1 | grep -c "custom_all_reduce.py.*Registering" || true)
echo "custom AR registering lines: $CAR_REG (oczekiwane >0)" | tee "$QOUT/allreduce_gate_ar.txt"

ensure_dataset || echo "PRZERWIJ"
bench_prereqs "$QWEN_COMPOSE"

start_sample_window "qwen_tp4_ar_c64" 900
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 256 --ignore-eos --num-prompts 600 --max-concurrency 64 \
    --save-result --result-dir /tmp/xbench --result-filename tp4_ar_c64.json'
stop_sample_window || echo "WARN: sampler"

mkdir -p "$QOUT/bench_tp4_ar"
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/xbench/. "$QOUT/bench_tp4_ar/"
docker logs vllm > "$QOUT/log_qwen_tp4_ar.txt" 2>&1
nvidia-smi > "$QOUT/nvidia_smi_tp4_ar.txt"
show_bench "$QOUT/bench_tp4_ar"
head -2 "$QOUT/qwen_tp4_ar_c64_dcgmi.txt"    # kolumny NVLTX/NVLRX obecne?
```

**Odczyt:** tok/s vs 2022/1989 (replikacja) + `NVL avg` z okna vs 4,68 GB/s
(noAR). Interpretacja w §1.

---

## Cz. 3 — Kimi start z overlayem profilera (30 min)

vLLM v0.20 nie czyta `VLLM_TORCH_PROFILER_DIR` (env usunięty upstream);
profiler włącza flaga `--profiler-config`, a `/start_profile` rejestruje się
tylko gdy jest obecna. Overlay nadpisuje CAŁĄ komendę — poniżej kopia
kanonicznej z `docker-compose.kimi-k2.6.yml` (zsynchronizowana 2026-08-03)
+ flaga na końcu.

```bash
docker compose -f "$QWEN_COMPOSE" down
unset QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_ARGS

cat > /tmp/kimi-profiler.yml <<'EOF'
services:
  vllm:
    command:
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size 8 --gpu-memory-utilization 0.6 --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2 --enable-auto-tool-choice --language-model-only --max-num-seqs 32 --max-model-len 131072 --max-num-batched-tokens 4096 --speculative-config='{"model":"lightseekorg/kimi-k2.6-eagle3-mla","method":"eagle3","num_speculative_tokens":3,"max_model_len":8192}' --profiler-config='{"profiler":"torch","torch_profiler_dir":"/tmp/vllm_profile"}'
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-profiler.yml up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 360 5 || echo "KIMI START FAILED"

docker inspect vllm --format '{{json .Config.Cmd}}' > "$PROF/engine_cmd_profiled.json"
grep -o 'profiler-config' "$PROF/engine_cmd_profiled.json" \
  || echo "BRAK profiler-config w Cmd — NIE startuj profilu"
grep -o 'speculative-config' "$PROF/engine_cmd_profiled.json" || echo "UWAGA: bez Eagle3"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$KOUT/verify_kimi_prof.txt"
grep -q "tensor_parallel_size=8" "$KOUT/verify_kimi_prof.txt" || echo "TP MISMATCH — PRZERWIJ"

ensure_dataset || echo "PRZERWIJ"
bench_prereqs "$COMPOSE"
```

---

## Cz. 4 — TRACE c32 (30 min) — NIETYKALNY

Profil obejmuje KRÓTKI bench: **32 prompty @c32** (jedna pełna fala batcha,
~15 s dekodowania — trace 8 ranków zostaje strawny). Warmupy PRZED
start_profile, żeby torch.compile nie zaśmiecił tracu (lekcja F3 z 06-12:
zimny profil = cudagraph/compile w cpu_op, użytek tylko jakościowy).

```bash
P0OUT="$KOUT"

# warmup POZA profilem (ta sama ścieżka co bench, krótko):
docker compose -f "$COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 64 --ignore-eos --num-prompts 32 --max-concurrency 32 \
    --result-dir /tmp/xbench --result-filename warmup_discard.json'

curl -fsS -X POST http://127.0.0.1:8000/start_profile
start_sample_window "kimi_c32_profiled" 300
docker compose -f "$COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 256 --ignore-eos --num-prompts 32 --max-concurrency 32 \
    --save-result --result-dir /tmp/xbench --result-filename kimi_c32_profiled.json'
stop_sample_window || echo "WARN: sampler"
curl -fsS -X POST http://127.0.0.1:8000/stop_profile

mkdir -p "$KOUT/bench"
docker compose -f "$COMPOSE" cp vllm:/tmp/xbench/. "$KOUT/bench/"
show_bench "$KOUT/bench"     # KONTROLA NARZUTU: ITL med vs 90,2 ms (±15% → §1)

# flush: 8 ranków pisze duże JSON-y nawet kilka minut po stop_profile
for _ in $(seq 1 60); do
  n=$(docker compose -f "$COMPOSE" exec vllm bash -c 'ls /tmp/vllm_profile 2>/dev/null | wc -l' | tr -d '[:space:]')
  [ "${n:-0}" -gt 0 ] && break
  sleep 10
done
docker compose -f "$COMPOSE" exec vllm ls -la /tmp/vllm_profile/
sleep 30
docker compose -f "$COMPOSE" exec vllm ls -la /tmp/vllm_profile/   # rozmiary stabilne? dopiero wtedy kopiuj

TRACE_DIR=/home/working/nanoserve-tracing/kimi_c32_nvlink_$(date +%F)
mkdir -p "$TRACE_DIR" && docker compose -f "$COMPOSE" cp vllm:/tmp/vllm_profile/. "$TRACE_DIR"/
ls -la "$TRACE_DIR" | tee "$PROF/trace_files_listing.txt"
echo "$TRACE_DIR" > "$PROF/trace_local_path.txt"
```

### Podsumowanie tracu — rank0 i rank_last (na serwerze)

```bash
# przy NOT FOUND popraw TRACE_DIR i powtórz — BEZ exit
summarize_trace () {  # $1=plik tracu  $2=etykieta
  uv run python - "$1" <<'PYEOF' | tee "$PROF/trace_summary_c32_$2.txt"
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
agg=collections.Counter()
for e in kern: agg[bucket(e.get('name',''))]+=e['dur']
span=max(e['ts']+e['dur'] for e in kern)-min(e['ts'] for e in kern)
tot=sum(agg.values())
print(f"span {span/1e6:.2f}s  kernel-time {tot/1e6:.2f}s  gaps {(span-tot)/1e6:.2f}s ({(span-tot)/span*100:.0f}%)")
for k,v in agg.most_common(): print(f"  {k:18} {v/1e6:8.2f}s  {v/span*100:5.1f}% of span")
PYEOF
}

T0=$(find "$TRACE_DIR" -type f \( -name '*.json' -o -name '*.json.gz' \) | sort | head -n 1)
TL=$(find "$TRACE_DIR" -type f \( -name '*.json' -o -name '*.json.gz' \) | sort | tail -n 1)
echo "rank0: ${T0:-NOT FOUND}"; echo "rank_last: ${TL:-NOT FOUND}"
[ -n "$T0" ] && summarize_trace "$T0" rank0
[ -n "$TL" ] && [ "$TL" != "$T0" ] && summarize_trace "$TL" rank_last
```

**Fallback:** jeśli `cudagraph_opaque` zjada większość czasu, powtórz profil
z `--enforce-eager` doklejonym do komendy overlaya (jeden dodatkowy restart;
wynik oznaczyć *eager — wyższy narzut launchów*, nadal rozdziela NCCL od
compute).

---

## Cz. 4b — OPCJA: drugi profil @c16 (10 min, bez restartu)

Porównywalność 1:1 z baseline'em 06-11 (tam trace był @c16, w anomalii).
Ten sam silnik, tylko start/stop_profile ponownie:

```bash
curl -fsS -X POST http://127.0.0.1:8000/start_profile
docker compose -f "$COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 256 --ignore-eos --num-prompts 16 --max-concurrency 16 \
    --save-result --result-dir /tmp/xbench --result-filename kimi_c16_profiled.json'
curl -fsS -X POST http://127.0.0.1:8000/stop_profile
# flush-wait jak w Cz. 4; kopia do "$TRACE_DIR"/c16/ ; summary z sufiksem c16:
mkdir -p "$TRACE_DIR/c16"
sleep 60; docker compose -f "$COMPOSE" cp vllm:/tmp/vllm_profile/. "$TRACE_DIR/c16/"
# UWAGA: katalog w kontenerze zawiera teraz TRACE'y OBU profili — rozdziel po
# timestampach plików; summary c16 licz z najnowszego pliku rank0.
docker compose -f "$COMPOSE" cp vllm:/tmp/xbench/. "$KOUT/bench/"
```

---

## Cz. 5 — restore + commit (15 min)

```bash
docker compose -f "$COMPOSE" up -d --force-recreate vllm    # plain, bez overlaya
wait_http_health http://127.0.0.1:8000/health 360 5 || echo "KIMI RESTORE FAILED"
docker inspect vllm --format '{{json .Config.Cmd}}' > "$RUN_DIR/session/restore_engine_cmd.json"
grep -o 'profiler-config' "$RUN_DIR/session/restore_engine_cmd.json" \
  && echo "UWAGA: profiler flag nadal w Cmd — powtórz recreate z SAMYM plain compose" \
  || echo "restore czysty"

docker compose -f "$COMPOSE" up -d vllm-small litellm open-webui
wait_http_health http://127.0.0.1:8004/health 240 5 && echo "deepseek OK"
curl -fsS http://127.0.0.1:8000/health && echo "kimi OK"
docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/restore_ps.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
git rev-parse HEAD > "$RUN_DIR/session/end_commit.txt"

git status
du -sh "$RUN_DIR"      # traców NIE ma w repo? (tylko summary + listing + ścieżka)
find "$RUN_DIR" -name 'engine_env_*' -exec grep -l "HUGGING_FACE_HUB_TOKEN=hf_" {} \; \
  && echo "STOP: token w artefaktach — popraw redakcję przed commitem"
git add "$RUN_DIR" results/runs/2026-08-03_nvlink_gap_fill/session/dmesg_end.txt
git commit -m "bench: trace Kimi TP8 c32 po NVLinku + domkniecia #51 (dmesg, NVL dla TP4-AR)"
git push -u origin main
```

---

## Po sesji (laptop, poza slotem)

1. Analiza tracu → aktualizacja `share` w rachunku #50; zestawienie
   83,9% (PCIe/c16/anomalia) vs dzisiejszy podział spanu.
2. Wyjaśnienie „link-only 2,57× > sufit 2,14×" — z nowym share sprawdzić,
   czy stary share 0,533 (Qwen) / 0,839 (Kimi) zawierał peer-wait.
3. T9 sekcja „pomiar po interwencji" + notatka decyzyjna — dopiski mechanizmowe.
4. Komentarz #50 (predykcja vs pomiar, dekompozycja, trace) + zamknięcie #51.
5. Reszta listy z planu 08-03: infrastructure §2.2, usunięcie
   `NCCL_NVLS_ENABLE=1` z compose Qwena, `sync-state`.

## Wątki otwarte (nie w tym slocie)

- dcgm-exporter (#34, HIGH VALUE) — najpierw prep laptopowy (compose + scrape
  job + wiersz dashboardu), deploy w osobnym touchu.
- Screenshot Grafany pod obciążeniem (#34) — jeśli stack stoi w trakcie
  Cz. 4, można zrobić przy okazji (przeglądarka, zero skryptu).
- #44 T8 proxy overhead (R1–R8) — osobna sesja.

---

## Walidacja planu

```text
git diff --check    (docs-only; skrypty są blokami kodu wewnątrz planu)
```
