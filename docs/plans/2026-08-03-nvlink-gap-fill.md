# Sesja serwerowa 2026-08-03 — uzupełnienie porównania po montażu NVLink

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, mostki 4-way: wyspy GPU 0-3 i 4-7 — potwierdzone 07-31)
**Slot (założenie):** ~2 h. Restarty silników dozwolone.
**Kontekst:** issue #50, plan i wyniki `docs/plans/2026-07-31-nvlink-install-verification.md`
+ `results/runs/2026-07-31_nvlink_install/`.

> **Plan jest samowystarczalny** — wszystkie helpery i komendy inline.
> **Wymaganie wstępne:** compose Qwena ma już `${QWEN_EXTRA_ARGS:-}` na końcu
> `command` (patch z 07-31/laptop). Cz. 0 to weryfikuje fail-fastem.

---

## 0. Po co ta sesja — co zostało po 07-31

Sesja 07-31 potwierdziła montaż (pełna siatka NV6 w obu wyspach, P2P 132,8 GB/s,
NCCL busbw w wyspie 185–333 GB/s, delta błędów pusta) i zmierzyła zysk pakietu:

| pomiar | PCIe (06-11) | NVLink (07-31) | zysk |
|---|---:|---:|---:|
| Qwen TP4 c64 out tok/s | 680 | **2022** (test2: 1989) | **2,97×** |
| Qwen TP4 c64 ITL med | 53,7 ms | 13,6 ms | 3,9× |
| Qwen TP4 c1 TPOT med | 4,00 ms | 3,21 ms | 1,25× |
| Kimi TP8 c32 out tok/s | 285 | **594** | **2,08×** |
| Kimi TP8 c1 TPOT med | 8,7 ms | 7,44 ms | 1,17× |
| Kimi TP8 c16 ITL med | 512 ms (anomalia) | **48,6 ms** | anomalia ZNIKŁA |

Bramka custom all-reduce: Qwen TP4 — warning **zniknął** + `custom_all_reduce.py:215
Registering … cuda graph addresses` (kernel aktywny); Kimi TP8 — warning **został**
(8×, oczekiwane przy 4+4). Wiersz 1 tabeli decyzyjnej z planu 07-31: mostki działają.

**Cztery braki, które ta sesja domyka:**

1. **Rozdzielenie dawki (Qwen TP4).** Zysk 2,97× to pakiet: klasa linku + kernel
   custom AR, który vLLM na PCIe wyłączał sam. 2,97× **przekracza sufit modelu**
   `1/(1−share)` = 2,14× przy `share 0,533` — bez rozdzielenia nie wiadomo,
   co model przegapił. Jedna dawka: `--disable-custom-all-reduce` przy
   włożonych mostkach, bench c=64.
2. **Liczniki NVLink dcgmi.** 07-31 pola 1011/1012 nie weszły do próbek (kolumny
   NVL nieobecne, `dcgm_fields_probe/dcgm_fields_used` brak w artefaktach).
   Dowód przeniesienia ruchu jest tylko pośredni (PCIe RX: Kimi c32 4,3 GB/s
   vs sufit 7,2–7,9; Qwen c64 0,07 vs 5,65). Probe + okna z polami NVL, jeśli
   sterownik je wystawia.
3. **Kimi c16 przy 192 promptach.** 07-31 biegło 96 → ITL porównywalny (anomalia
   znikła), ale throughput z baseline K1 (192) nieporównywalny.
4. **Drobne artefakty:** `nvidia-smi -q -d NVLINK` padł na parsowaniu flag,
   `topo -p2p n` niezapisany, brak `nvidia_smi_end` / `restore_ps` /
   `end_commit`, `dmesg_end.txt` pusty.

Opcja (tnij pierwszą): **Qwen TP2 na NVLink** — TP2 PCIe (1404 tok/s, GPU{0,1},
optimum serwowania wg krzywej TP) vs TP4+NVLink (2022). Bez pomiaru TP2+NVLink
rekomendacja serwowania wisi na porównaniu skrzyżowanym.

**Poza slotem (świadomie):** trace Kimi TP8 c32 po NVLinku (`--profiler-config`;
udział NCCL z 83,9% → ?) — osobna sesja; NCCL island JSON nadpisany przez cross
(dane są w txt — nie odtwarzamy).

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

| pomiar | odniesienie | predykcja | odczyt |
|---|---:|---|---|
| Qwen TP4 c64 **bez custom AR** | 2022 (z AR) / 680 (PCIe) | **1300–1800** — NCCL po NVLinku szybki, ale komunikaty decode małe ⇒ narzut per-call, który kernel usuwał, wraca | ≥1900 → kernel marginalny, zysk ≈ sam link; <1100 → kernel był głównym składnikiem pakietu |
| dekompozycja | — | `zysk_link = X/680`, `zysk_kernel = 2022/X` | suma ma się złożyć na 2,97× |
| Kimi c16 @192, ITL med | 48,6 ms @96 | **45–65 ms** (anomalia nie wraca) | >200 ms → anomalia zależna od num_prompts, wraca diagnoza schedulerowa |
| Kimi c16 @192, tok/s | K1 c16 (192 promptów) | **≈2× K1** (spójnie z c32 2,08×) | — |
| dcgmi 1011/1012 | — | warunkowe: jeśli probe OK → Kimi c32 NVL RX ≫ PCIe RX; Qwen c64 ruch ~wyłącznie NVL | pola N/A → zapisz jawnie, sygnałem zostaje spadek PCIe RX |
| Qwen TP2 NVLink c64 (opcja) | 1404 (PCIe, PIX) | **1400–1700** — TP2 miał minimalny narzut komunikacyjny (c64: net-win vs TP1), więc mało do odzyskania | >1900 → narzut TP2 na PCIe był niedoszacowany; per-GPU: TP2 702 tok/s/GPU vs TP4+NVLink 505 — czy optimum się przesuwa |

**Nie zmieniaj env między dzisiejszymi a piątkowymi biegami Qwena** —
`NCCL_NVLS_ENABLE=1` zostaje w compose do końca tej sesji (martwa flaga wg
warningu FlashInfera, ale usunięcie teraz psuje porównywalność). Sprzątanie po sesji.

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. 0 | start, pull, weryfikacja patcha compose, zwolnienie GPU | 5 |
| Cz. 1 | diagnostyka uzupełniająca + liczniki błędów BEFORE | 8 |
| Cz. H | helpery | 2 |
| Cz. 2 | **Qwen TP4 + `--disable-custom-all-reduce`**: c64 + c1 | 30 |
| Cz. 3 | Qwen TP2 NVLink c64 (opcja) | 20 |
| Cz. 4 | Kimi restore + c16@192 (+ c32@384 warunkowo — liczniki NVL) | 35 |
| Cz. 5 | błędy AFTER, restore stacku, snapshoty, digesty obs (#49), commit | 12 |
| | **razem** | **112** |

**Kolejność cięcia:** Cz. 4 c32-rerun → Cz. 3 → Cz. 2 c1 → Cz. 1 `topo -p2p n`.
**Nietykalne:** Cz. 0, **Cz. 2 c64** (główny cel sesji), Cz. 4 restore + c16@192, Cz. 5.

---

## Cz. 0 — start (5 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main
# BEZ set -euo pipefail; BEZ exit — sesja interaktywna po SSH

RUN_DIR=results/runs/2026-08-03_nvlink_gap_fill
NOUT="$RUN_DIR/nvlink"; QOUT="$RUN_DIR/qwen"; KOUT="$RUN_DIR/kimi"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
QWEN_COMPOSE="serving/compose/docker-compose.qwen3.6.yml"
SWE=results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl
mkdir -p "$NOUT" "$QOUT" "$KOUT" "$RUN_DIR/session"
set -a; source .env; set +a

# FAIL-FAST: patch compose musi być na serwerze, inaczej Cz. 2 nie ma jak podać flagi
grep -q 'QWEN_EXTRA_ARGS' "$QWEN_COMPOSE" \
  || echo "STOP: brak QWEN_EXTRA_ARGS w compose — git pull nie dowiózł patcha"

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"

docker compose -f "$COMPOSE" stop vllm vllm-small litellm open-webui
docker compose -f "$COMPOSE" rm -f vllm 2>/dev/null || true   # kolizja container_name
nvidia-smi --query-gpu=index,memory.used --format=csv | tee "$RUN_DIR/session/gpu_free_check.csv"
```

---

## Cz. 1 — diagnostyka uzupełniająca + błędy BEFORE (8 min)

```bash
# (a) artefakty, które 07-31 nie wyszły:
nvidia-smi -q -d NVLINK -i 0 > "$NOUT/nvlink_query_gpu0.txt" 2>&1   # 07-31: "Failed to parse --display/-d flags"
grep -qi "fail\|error" "$NOUT/nvlink_query_gpu0.txt" \
  && nvidia-smi nvlink -s -i 0 > "$NOUT/nvlink_query_gpu0.txt" 2>&1  # fallback
nvidia-smi topo -p2p n > "$NOUT/topo_p2p_nvlink.txt" 2>&1
nvidia-smi topo -m     | tee "$NOUT/topo_m.txt"    # kontrola: stan z 07-31 bez zmian

# (b) liczniki błędów PRZED obciążeniem tej sesji
nvidia-smi nvlink -e > "$NOUT/nvlink_errors_before.txt" 2>&1

# (c) PROBE pól NVLink dcgmi — 07-31 kolumny NVL zniknęły PO CICHU (nagłówek
# bez NVLTX/NVLRX, zero komunikatu błędu), więc sam grep po "error" NIE wystarcza.
# Rozstrzyga POZYTYWNY test nagłówka: kolumna NVL musi być widoczna.
dcgmi dmon -e 155,1002,1004,1005,1009,1010,1011,1012 -d 1000 -c 3 \
  > "$RUN_DIR/session/dcgmi_fields_probe.txt" 2>&1
head -3 "$RUN_DIR/session/dcgmi_fields_probe.txt"   # obejrzyj nagłówek sam
if grep -qi "error\|not supported\|unknown field" "$RUN_DIR/session/dcgmi_fields_probe.txt"; then
  DCGM_FIELDS=155,1002,1004,1005,1009,1010          # jawny błąd → fallback
elif head -1 "$RUN_DIR/session/dcgmi_fields_probe.txt" | grep -q "NVL"; then
  DCGM_FIELDS=155,1002,1004,1005,1009,1010,1011,1012  # kolumny NVL SĄ (N/A w 1. próbce OK — pola prof mają rozbieg)
else
  DCGM_FIELDS=155,1002,1004,1005,1009,1010          # ciche pominięcie jak 07-31 → fallback
fi
echo "DCGM_FIELDS=$DCGM_FIELDS" | tee "$RUN_DIR/session/dcgm_fields_used.txt"
```

Jeśli pola NVL są niedostępne: **zapisz to jawnie** (plik `dcgm_fields_used.txt`
to dokumentuje) i tnij rerun c32 w Cz. 4 — pośredni sygnał PCIe RX już istnieje.

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

ensure_dataset () {   # dataset SWE do kontenera + WERYFIKACJA (po KAŻDYM recreate)
  docker cp "$SWE" vllm:/tmp/swe_bench_vllm.jsonl \
    || { echo "STOP: docker cp nie zadziałał — czy kontener 'vllm' stoi?"; return 1; }
  n=$(docker exec vllm sh -c 'wc -l < /tmp/swe_bench_vllm.jsonl' 2>/dev/null | tr -d ' ')
  echo "dataset w kontenerze: ${n:-BRAK} linii"
  { [ -n "$n" ] && [ "$n" -gt 100 ]; } \
    || { echo "STOP: dataset nie dotarł — NIE benchuj"; return 1; }
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

## Cz. 2 — GŁÓWNY CEL: Qwen TP4 + `--disable-custom-all-reduce` (30 min)

Identyczna konfiguracja jak 07-31 (TP4, GPU 0-3, ta sama wyspa, ten sam
workload) — **jedyna dawka to flaga CLI.** Wynik rozdziela pakiet
„link + kernel" na składowe.

```bash
P0OUT="$QOUT"
export QWEN_TP=4
export QWEN_CUDA_VISIBLE_DEVICES=0,1,2,3
export QWEN_EXTRA_ARGS="--disable-custom-all-reduce"

# KROK 1 — start
docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 240 5 || echo "START FAILED — nie benchuj"

# KROK 2 — FAIL-FAST verify (dawka MUSI być widoczna w runtime, lekcja 06-11)
docker inspect vllm --format '{{json .Config.Cmd}}' > "$QOUT/engine_cmd_tp4_noAR.json"
grep -o 'disable-custom-all-reduce' "$QOUT/engine_cmd_tp4_noAR.json" \
  || echo "STOP: flaga nie weszła do cmd — QWEN_EXTRA_ARGS zignorowany"
docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | sed -E 's/^(HUGGING_FACE_HUB_TOKEN|HF_TOKEN|[A-Z_]*API_KEY|[A-Z_]*SECRET[A-Z_]*)=.*/\1=REDACTED/' \
  > "$QOUT/engine_env_tp4_noAR.txt"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$QOUT/verify_tp4_noAR.txt"
grep -q "tensor_parallel_size=4" "$QOUT/verify_tp4_noAR.txt" || echo "TP MISMATCH — PRZERWIJ"
grep '^CUDA_VISIBLE_DEVICES=0,1,2,3$' "$QOUT/engine_env_tp4_noAR.txt" \
  || echo "ZŁY PLACEMENT — porównanie z 2022 tok/s (GPU 0-3) nieważne"
docker logs vllm 2>&1 | grep -m1 -o "disable_custom_all_reduce=True" \
  | tee -a "$QOUT/verify_tp4_noAR.txt"
# 07-31 kernel aktywny zostawiał ślad "Registering ... cuda graph addresses" —
# dziś ma go NIE być:
CAR_REG=$(docker logs vllm 2>&1 | grep -c "custom_all_reduce.py.*Registering" || true)
echo "custom AR registering lines: $CAR_REG (oczekiwane 0)" | tee "$QOUT/allreduce_gate_noAR.txt"

# KROK 3 — prereqs (świeży kontener po recreate)
ensure_dataset || echo "PRZERWIJ — bez datasetu bench c=64 nie ma sensu"
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c \
  'rm -rf /tmp/qbench; mkdir -p /tmp/qbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "import pandas,datasets;print(\"deps ok\")"' \
  || echo "PREREQS FAILED — nie leć dalej"

# KROK 4 — c=64 (SWE custom, 256-out) — NIETYKALNY
start_sample_window "qwen_tp4_noAR_c64" 900
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 256 --ignore-eos --num-prompts 600 --max-concurrency 64 \
    --save-result --result-dir /tmp/qbench --result-filename tp4_noAR_c64.json'
stop_sample_window || echo "WARN: sampler c64"

# KROK 5 — c=1 (random 64/512) — TNIJ przy poślizgu
start_sample_window "qwen_tp4_noAR_c1" 600
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name random --random-input-len 64 --random-output-len 512 \
    --ignore-eos --num-warmups 3 --num-prompts 40 --max-concurrency 1 \
    --save-result --result-dir /tmp/qbench --result-filename tp4_noAR_c1.json'
stop_sample_window || echo "WARN: sampler c1"

# KROK 6 — ZAWSZE zbierz artefakty
mkdir -p "$QOUT/bench_tp4_noAR"
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/qbench/. "$QOUT/bench_tp4_noAR/"
docker logs vllm > "$QOUT/log_qwen_tp4_noAR.txt" 2>&1
nvidia-smi > "$QOUT/nvidia_smi_tp4_noAR.txt"
show_bench "$QOUT/bench_tp4_noAR"
```

**Odczyt (X = out tok/s @c64):** `zysk_link = X/680`, `zysk_kernel = 2022/X`.
Przedziały interpretacyjne w §1. Dodatkowo c=1: TPOT vs 3,21 ms (z AR) i 4,00 ms
(PCIe) mówi, czy kernel gra rolę także w reżimie latencji.

---

## Cz. 3 — Qwen TP2 na NVLink (20 min, OPCJA — tnij drugą)

TP2 był optimum serwowania na PCIe (1404 tok/s, GPU{0,1}). Para 0-1 ma teraz NV6.
Bez tego pomiaru rekomendacja „TP4 przestaje być karą" wisi na porównaniu
TP4-NVLink vs TP2-PCIe.

**Metodycznie czysty punkt:** warning custom AR dotyczy tylko „more than two
PCIe-only GPUs" — przy TP2 kernel custom AR działał **już na PCIe** (baseline
06-11 miał go włączonego). TP2-NVLink vs TP2-PCIe to więc **czysta dawka klasy
linku**, bez konfundu kernela — komplementarna do dekompozycji z Cz. 2.

```bash
export QWEN_TP=2
export QWEN_CUDA_VISIBLE_DEVICES=0,1        # placement baseline'u TP2 (PIX)
unset QWEN_EXTRA_ARGS                        # custom AR wraca do auto

docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 240 5 || echo "START FAILED"
docker inspect vllm --format '{{json .Config.Cmd}}' > "$QOUT/engine_cmd_tp2_nvlink.json"
docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | sed -E 's/^(HUGGING_FACE_HUB_TOKEN|HF_TOKEN|[A-Z_]*API_KEY|[A-Z_]*SECRET[A-Z_]*)=.*/\1=REDACTED/' \
  > "$QOUT/engine_env_tp2_nvlink.txt"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$QOUT/verify_tp2_nvlink.txt"
grep -q "tensor_parallel_size=2" "$QOUT/verify_tp2_nvlink.txt" || echo "TP MISMATCH — PRZERWIJ"
grep '^CUDA_VISIBLE_DEVICES=0,1$' "$QOUT/engine_env_tp2_nvlink.txt" \
  || echo "ZŁY PLACEMENT — porównanie z baseline TP2 (GPU 0,1 PIX) nieważne"

ensure_dataset || echo "PRZERWIJ"
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c \
  'rm -rf /tmp/qbench; mkdir -p /tmp/qbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "print(\"deps ok\")"'

start_sample_window "qwen_tp2_nvlink_c64" 900
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 256 --ignore-eos --num-prompts 600 --max-concurrency 64 \
    --save-result --result-dir /tmp/qbench --result-filename tp2_nvlink_c64.json'
stop_sample_window || echo "WARN: sampler tp2"

mkdir -p "$QOUT/bench_tp2_nvlink"
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/qbench/. "$QOUT/bench_tp2_nvlink/"
docker logs vllm > "$QOUT/log_qwen_tp2_nvlink.txt" 2>&1
nvidia-smi > "$QOUT/nvidia_smi_tp2_nvlink.txt"
show_bench "$QOUT/bench_tp2_nvlink"
```

**Odczyt:** tabela per-GPU — TP2-NVLink (X/2) vs TP4-NVLink (2022/4 = 505) vs
TP2-PCIe (702). To domyka krzywą TP po interwencji.

---

## Cz. 4 — Kimi restore + benche uzupełniające (35 min)

Restore i tak wymagany; benche są kosztem krańcowym.

```bash
P0OUT="$KOUT"
unset QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_ARGS   # inaczej wyciekną do compose Kimi

docker compose -f "$QWEN_COMPOSE" down
docker compose -f "$COMPOSE" up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 360 5 || echo "KIMI START FAILED"

docker inspect vllm --format '{{json .Config.Cmd}}' > "$KOUT/engine_cmd_kimi.json"
grep -o 'speculative-config' "$KOUT/engine_cmd_kimi.json" || echo "UWAGA: Kimi bez Eagle3"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$KOUT/verify_kimi.txt"
grep -q "tensor_parallel_size=8" "$KOUT/verify_kimi.txt" || echo "TP MISMATCH — PRZERWIJ"

ensure_dataset || echo "PRZERWIJ — bez datasetu benche nie ruszą"
docker compose -f "$COMPOSE" exec vllm bash -c \
  'rm -rf /tmp/kbench; mkdir -p /tmp/kbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "print(\"deps ok\")"'

kimi_bench_c () {   # $1=concurrency  $2=num_prompts  $3=sufit okna dcgmi (s)
  c="$1"; np="$2"; tag="kimi_c${c}"
  docker exec vllm test -s /tmp/swe_bench_vllm.jsonl \
    || { echo "BRAK datasetu — uruchom ensure_dataset"; return 1; }
  start_sample_window "$tag" "$3"
  docker compose -f "$COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
      --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
      --custom-output-len 256 --ignore-eos --num-warmups 2 \
      --num-prompts '"$np"' --max-concurrency '"$c"' \
      --save-result --result-dir /tmp/kbench --result-filename '"$tag"'.json'
  bench_status=$?
  stop_sample_window || echo "WARN: sampler $tag"
  [ "$bench_status" -ne 0 ] && echo "WARN: bench $tag failed"
  mkdir -p "$KOUT/bench"
  docker compose -f "$COMPOSE" cp vllm:/tmp/kbench/. "$KOUT/bench/" || echo "WARN: cp $tag"
}

# c16 przy PEŁNEJ liczbie promptów baseline'u K1 — porównywalność throughput
kimi_bench_c 16 192 1200                     # NIETYKALNY

# rerun c32 TYLKO jeśli DCGM_FIELDS zawiera 1011,1012 (liczniki NVL pod realnym
# ruchem — replikacja 594 tok/s przy okazji); inaczej TNIJ
if echo "$DCGM_FIELDS" | grep -q 1011; then
  kimi_bench_c 32 384 1200
else
  echo "pola NVL niedostępne — c32 rerun pominięty (zanotowane w dcgm_fields_used.txt)"
fi

docker logs vllm > "$KOUT/log_kimi.txt" 2>&1
nvidia-smi > "$KOUT/nvidia_smi_kimi.txt"
show_bench "$KOUT/bench"
```

**Odczyt:** c16@192 — ITL vs 48,6 ms (07-31 @96) i 512 ms (K1); throughput wprost
vs K1. Jeśli c32 rerun poszedł: średnie NVL TX/RX z `kimi_c32_dcgmi.txt` to
pierwszy **bezpośredni** licznik ruchu NVLink w projekcie.

**Piggyback #34 (opcjonalnie, zero skryptu):** benche c16/c32 to dokładnie ten
concurrent load, którego brakowało panelom queue/latency/KV. Jeśli stack
obserwability stoi i masz Grafanę w przeglądarce — zrób screenshot dashboardu
vLLM **w trakcie** biegu c32; domyka pozycję „screenshot pod obciążeniem" z #34.

---

## Cz. 5 — błędy AFTER, restore stacku, commit (12 min)

```bash
nvidia-smi nvlink -e > "$NOUT/nvlink_errors_after.txt" 2>&1
diff "$NOUT/nvlink_errors_before.txt" "$NOUT/nvlink_errors_after.txt" \
  > "$NOUT/nvlink_errors_delta.txt" 2>&1
# pusty delta = wynik POZYTYWNY (zero przyrostu błędów pod obciążeniem)
nvidia-smi topo -m > "$NOUT/topo_m_after.txt"
dmesg | grep -i "nvlink\|nvrm" | tail -40 > "$RUN_DIR/session/dmesg_end.txt" 2>&1

# restore pełnego stacku + snapshoty, których 07-31 zabrakło
docker compose -f "$COMPOSE" up -d vllm-small litellm open-webui
wait_http_health http://127.0.0.1:8004/health 240 5 && echo "deepseek OK"
curl -fsS http://127.0.0.1:8000/health && echo "kimi OK"
docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/restore_ps.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
git rev-parse HEAD > "$RUN_DIR/session/end_commit.txt"

# piggyback #49 (czysty odczyt, ~2 min): digesty obrazów obserwability —
# bez nich nie da się przypiąć wersji (Grafana/Prometheus/renderer są na
# floating tagach). Pinning sam w sobie to praca laptopowa, PO sesji.
docker images --digests | grep -iE "grafana|prom" \
  > "$RUN_DIR/session/obs_image_digests.txt" 2>&1 || true
docker compose -f serving/compose/docker-compose.observability.yml ps \
  > "$RUN_DIR/session/obs_stack_ps.txt" 2>&1 || true

git status
du -sh "$RUN_DIR"
find "$RUN_DIR" -name 'engine_env_*' -exec grep -l "HUGGING_FACE_HUB_TOKEN=hf_" {} \; \
  && echo "STOP: token w artefaktach — popraw redakcję przed commitem"
git add "$RUN_DIR"
git commit -m "bench: NVLink gap-fill - rozdzielenie dawki custom AR, Kimi c16@192, liczniki NVL"
git push -u origin main
```

---

## Po sesji (laptop, poza slotem)

1. **`docs/operations/infrastructure.md` §2.2** — macierz `topo -m` + przepisanie
   zdania o „wyłącznie PCIe" (należne od 07-31).
2. **Issue #50** — komentarz: tabela predykcja vs pomiar (07-31) + dekompozycja
   link/kernel (dzisiejsza); dopiero potem zamknięcie.
3. **`docs/writeups/w1/t9-bottleneck-nvlink.md`** — sekcja „pomiar po interwencji";
   kluczowe: 2,97× > sufit modelu 2,14× (model niekompletny — co pominął),
   anomalia c16 była transportowa (nie schedulerowa), capture ≈0,62 vs założone 0,75.
4. **`docs/writeups/w1/nvlink-4way-notatka-decyzyjna.md`** — dopisek, czy decyzja
   się obroniła (c32: 2,08× — tak, choć poniżej górnego 2,7×).
5. **Compose Qwena** — usunąć `NCCL_NVLS_ENABLE=1` (martwa flaga potwierdzona
   warningiem FlashInfera na mostkach); dopiero PO tej sesji.
6. **`docs/operations/agent-state.md`** — `sync-state`.

## Wątki otwarte (nie w tym slocie)

- **Trace Kimi TP8 @c32 po NVLinku** (`--profiler-config`) — udział NCCL z 83,9% → ?;
  domyka rachunek `share × capture` od strony mechanizmu. Osobna sesja.
- **Anomalia c16** — jeśli wróci przy 192 promptach: diagnoza od strony
  `max-num-seqs` vs `max-concurrency`.
- **dcgm-exporter (#34, HIGH VALUE)** — świadomie NIE w tym slocie: laptop-prep
  nie istnieje (brak serwisu w observability compose), a nieprzetestowany
  kontener wdrażany przy restore psułby czystość sesji; do tego exporter
  watchuje te same pola `PROF_*`, co okna `dcgmi dmon`. Kolejność: prep na
  laptopie (compose + scrape job + wiersz dashboardu) → deploy w osobnym touchu.
- **NCCL_ALGO sweep + nsys** — odłożone do W2 (plan 06-10).
- **#44 T8 proxy overhead (R1–R8)** — własny program pomiarowy, osobna sesja.

---

## Walidacja planu

```text
git diff --check    (docs + compose; skrypty są heredocami wewnątrz planu)
```
