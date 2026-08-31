# Sesja serwerowa 2026-08-31 — latencja dostępu (all-reduce) + grid Qwen TP×c×łącze + profile TP1–TP8

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, NVLink 4-way: wyspy GPU 0-3 / 4-7)
**Slot (założenie):** ~7 h, w tym **2 h burn-in bez nadzoru na końcu** (część
aktywna ~5 h). 10 startów silnika (9× Qwen + restore Kimi).
**Kontekst:** issue #50 (mechanizm `share × capture`, implikowany capture 0,62),
prezentacja meetupowa (slajd 12: „ogranicza nas czas rundy, nie przepustowość
rury" — dotąd twierdzenie z literatury, nie z pomiaru), sesje
`2026-06-11_bottleneck` (krzywa TP na PCIe), `2026-07-31_nvlink_install`
(busbw duże wiadomości), `2026-08-03_kimi_trace_nvlink` (metoda profilera).

> **Plan samowystarczalny** — wszystkie helpery i komendy inline.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH.
> **Reguła wygrzewki (od 08-03):** po każdym starcie silnika najpierw
> bench-wygrzewka NA ODRZUT, dopiero potem pomiar.
> **Traców NIE commitujemy** — kopiuj do `/home/working/nanoserve-tracing/`,
> do repo idzie tylko podsumowanie.

---

## 0. Po co ta sesja

Dotąd mierzyliśmy **przepustowość** łącza (busbw przy dużych wiadomościach:
185–333 GB/s w wyspie). Ale krok dekodowania to ~`2·L` **małych** synchronicznych
rund all-reduce (wiadomość ≈ `c × hidden × 2 B`, przy c=1 to pojedyncze KB) —
tam rządzi **latencja rundy `r`**, nie przepustowość. Wartości `r` w modelu
(`T(krok) = F_host + N_rounds × r + W_silicon`) były dotąd implikowane
(np. ΔITL TP8−TP1 / liczba rund) albo literaturowe („PCIe ~20 µs, NVLink
2–9 µs"). Ta sesja mierzy `r` **bezpośrednio**, w trzech konfiguracjach łącza,
i domyka trójkąt: mikrobenchmark → bench end-to-end → profil (krok 15 protokołu).

Cztery cele:

1. **Latencja mikro:** all-reduce µs/op przy małych wiadomościach (4 KB–8 MB)
   dla grup: wyspa-2, cross-2, wyspa-4, cross-4 (2+2), all-8 — każda też
   z `NCCL_P2P_DISABLE=1`; plus surowa latencja P2P par GPU.
2. **Grid end-to-end Qwen:** TP1/TP2/TP4/TP8 × c=1/16/32/64 × łącze
   {wyspa, cross, nop2p} — w tym pierwsza pełna **krzywa TP po NVLinku**
   (baseline 06-11 był na PCIe) i kwantyfikacja kary cross-island (test
   mechanizmu capture 0,62 z analizy błędów #50).
3. **Profile (część 2):** rozkład czasu kroku (torch profiler, metoda z sesji
   Kimi 08-03) dla Qwen TP1/TP2/TP4/TP8 × c=1/16/32 — jak udział NCCL/gaps
   skaluje się z TP i c po NVLinku.
4. **Spójność:** czy `2L × r_micro` odtwarza przyrosty ITL przy c=1, a udział
   NCCL z profilu — spadki throughput (dwie niezależne drogi, jedna liczba).
5. **Burn-in termiczny:** ≥ 2 h pracy wszystkich 8 kart na ~3/4 limitu mocy
   (450 W z 600 W) z ciągłym logiem temperatur GPU/HBM z DCGM — walidacja
   chłodzenia i stabilności pod długim obciążeniem. Metoda: power cap
   `nvidia-smi -pl 450` + saturujący GEMM (inferencja nie nadaje się jako
   obciążenie — comms-bound daje 111–200 W przy TP≥4). Burn idzie **na końcu
   sesji**, żeby heat-soak nie skaził pomiarów latencji.

**Założenia (jawne, przyjęte przy pisaniu planu):**

- **TP1 bez wariantów łącza** — zero komunikacji, jeden przebieg (punkt
  odniesienia dla wszystkich wariantów).
- **Wyspa/cross:** TP2 = GPU (0,1) vs (0,4); TP4 = GPU (0-3) vs (0,1,4,5);
  **TP8 zawsze przez dwie wyspy** — tam tylko NVLink vs nop2p.
- **„Wyłączenie programowe NVLink" = `NCCL_P2P_DISABLE=1`** (precedens 08-03):
  wyłącza transport P2P w NCCL (NVLink przestaje być używany, komunikacja
  przez SHM hosta). Uczciwość: to rekonstrukcja reżimu comms-bound, nie
  bit-perfect PCIe — SHM jest wolniejsze niż P2P-po-PCIe było. Etykietować
  „nop2p", nie „PCIe".
- **Profile tylko na placementach wyspowych z NVLinkiem** (TP2 0,1; TP4 0-3;
  TP8 0-7) — flaga `--profiler-config` wchodzi przez `QWEN_EXTRA_ARGS` przy
  tych samych startach co benche, zero dodatkowych restartów. Sama obecność
  flagi nie profiluje (profil rusza dopiero po `/start_profile`), więc benche
  z tych startów pozostają porównywalne — kontrola: replikacja TP4 c64
  względem 2022/1989.
- **nop2p z mniejszym `num-prompts`** (będzie wolno): mediany ITL/TPOT
  porównywalne, `output_throughput` NIE (precedens: uwaga c=16 z 07-31).

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

Odniesienia: krzywa TP PCIe (06-11): ITL c1 8,98 / 9,91 / 10,54 / 14,16 ms,
c64 1202 / 1404 / 680 / 257 tok/s; NVLink TP4 c64: 2022/1989; busbw wyspa
185–333, cross 2+2: 24,8–31,3 GB/s; szum ±0,4 ms (TP2, niezależne starty).

### Warstwa mikro (latencja)

| pomiar | odniesienie | predykcja | falsyfikacja |
|---|---|---|---|
| P2P lat wyspa (0↔1, 0↔2, 0↔3) | busbw 132,8 GB/s (07-31) | **1–3 µs/op** | > 6 µs → NVLink nie obsługuje małych transferów tej pary (peer off?) |
| P2P lat cross (0↔4, 3↔4) | — | **8–30 µs/op, ≥ 4× wyspa** | ≤ wyspa → mapa wysp lub metodyka zła |
| NCCL lat 4–16 KB, wyspa-4 | „NVLink 2–9 µs" (literatura, slajd 12) | **10–35 µs/op** | > 70 µs → latencji rundy nie robi transport, tylko launch/protokół — uwaga do modelu `r` |
| NCCL lat 4–16 KB, all-8 vs wyspa-4 | capture 0,62: odcinki cross kosztują ponadproporcjonalnie | **≥ 2× wyspa-4** | ≈ wyspa-4 → kara cross-island nie jest latencyjna → mechanizm capture do rewizji |
| NCCL lat 4–16 KB, cross-2 vs wyspa-2 | H4 (e2e): brak kary trasy | **wyraźnie wyżej mikro** (H4 padła na e2e, bo rundy TP2 nie dominują kroku — tu powinna być widoczna) | ≈ wyspa-2 → trasa faktycznie nie kosztuje nawet mikro; H4 obalona głębiej niż sądziliśmy |
| NCCL lat nop2p (wyspa-4) | SHM przez hosta | **≥ 3× wariant NVLink** | ≤ NVLink → env nie doszło do ranków (sprawdź) |

### Warstwa end-to-end (Qwen)

| pomiar | odniesienie | predykcja | falsyfikacja |
|---|---|---|---|
| TP4 wyspa c64 (replikacja) | 2022/1989 | **1900–2100** | poza → dryf konfiguracji, diff engine_cmd |
| krzywa ITL c1 TP1→TP8 (NVLink) | PCIe: +0,93/+1,56/+5,18 ms | **przyrosty ≤ połowa PCIe-owych** | ≥ PCIe → NVLink nie skraca rund małych wiadomości → model 1−128/900 do wyrzucenia |
| TP2 cross vs wyspa, ITL c1 | H4: 9,91 vs 9,13 (PCIe era) | **\|Δ\| ≤ 0,8 ms** (2× szum) | > 1,5 ms → kara trasy istnieje po NVLinku (H4 wraca w nowym reżimie) |
| TP4 cross (2+2) c64 vs wyspa | busbw cross 24,8–31,3 GB/s | **≤ 60% wyniku wyspy** | ≥ 90% wyspy → NCCL hierarchiczny maskuje cross w e2e → capture-story do przepisania |
| nop2p TP4 c64 | PCIe era 680; SHM < P2P-PCIe | **< 850 tok/s** | > 1200 → NCCL znalazł inną szybką ścieżkę — czytaj NCCL_DEBUG z mikro |
| nop2p TP8 c32 | PCIe era c64 257 tok/s | **spadek ≥ 2× vs NVLink TP8** | brak spadku → dawka nie działa (env w kontenerze!) |
| spójność: ΔITL c1 (TPn−TP1) vs `2L × r_micro` (wiadomość ≈ hidden×2 B) | implikowane r ery PCIe ~40 µs | **zgodność w granicach 2×** | rozjazd > 3× → rund nie widać w kroku wprost (fuzje, overlap, graph) — wynik sam w sobie |

### Warstwa profili (część 2)

| pomiar | odniesienie | predykcja | falsyfikacja |
|---|---|---|---|
| TP1 c1: gaps (bez operacji GPU) | Kimi TP8 c1: 63% gaps | **> 50% spanu** (host-bound) | < 30% → Qwen TP1 nie jest floor-bound — rewizja przenośności H3 |
| TP4 c32: udział NCCL | Qwen TP4 c64 PCIe: 53,3% | **20–45% spanu** | > 60% → komunikacja nadal dominuje mimo NVLink — sufit Amdahla wciąż żywy dla TP4 |
| TP8 c32 vs TP4 c32: udział NCCL | Kimi TP8 c32 po NVLink: 61,1% | **TP8 > TP4** (dwa odcinki cross w każdej rundzie) | TP8 ≤ TP4 → koszt TP8 nie siedzi w NCCL — szukać w gaps |
| monotonia w c (każde TP) | teoria: większy batch → dłuższe wiadomości → udział NCCL rośnie | **NCCL% rośnie z c** | spada z c → latencja rund stała a compute rośnie wolniej niż span — zanotować, nie naciągać |
| kontrola narzutu profilera | 08-03: ±5% (Kimi) | profilowany ITL w **±15%** nieprofilowanego | poza → trace jakościowy, nie ilościowy |

### Warstwa burn-in (2 h @ 450 W)

| pomiar | odniesienie | predykcja | falsyfikacja |
|---|---|---|---|
| moc per GPU w oknie | cap 450 W | **445–455 W stabilnie na 8 kartach** (GEMM saturuje, cap trzyma) | < 430 W na którejś karcie → obciążenie nie saturuje (sprawdź proces) albo throttle inny niż power cap |
| temp GPU | progi z `-q -d TEMPERATURE` (odczytać na starcie) | **plateau ≤ 30 min od startu, poniżej progu slowdown** | trend rosnący bez plateau po 60 min → chłodzenie nie nadąża, PRZERWIJ burn |
| temp HBM (pole 140) | — | plateau, **≤ 95 °C** | > 95 °C → margines pamięci zbyt mały dla pracy ciągłej @450 W |
| throttle reasons (pole 112) | — | **tylko SW Power Cap** (to jest mechanizm testu — norma) | jakikolwiek HW Thermal / HW Slowdown → wynik negatywny testu chłodzenia, zanotuj kartę i czas |
| dmesg po burn | — | **zero Xid** | Xid → wpisz do issue, karta podejrzana |
| rozrzut temp między kartami | — | ≤ 10 °C między najcieplejszą a najchłodniejszą | > 15 °C → nierówny airflow (pozycja w obudowie) — zanotuj mapę |
| **Inlet Temp** (IPMI, czujnik potwierdzony) | spec platformy SYS-521GE-TNRT: praca 10–35 °C | **< 35 °C przez całe okno** (test w specyfikacji) | ≥ 35 °C → burn poza spec — wynik termiczny GPU nieinterpretowalny, odnotuj i skróć |
| delta T_GPU − T_inlet | — | **stabilna po plateau (±3 °C)** — chłodzenie nadąża niezależnie od wahań otoczenia | delta rośnie monotonicznie → radiator/airflow nie odbiera 450 W ciągłego |
| System Temp (wnętrze obudowy) | — | plateau; wzrost względem startu zanotować | brak plateau po 60 min → wnętrze się nasyca, sprawdź wyciąg z serwerowni |

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. 0 | start, pull, zwolnienie GPU, wymiary modelu | 7 |
| Cz. 1 | mikro-latencje: NCCL 8 przebiegów + P2P | 25 |
| Cz. H | helpery | 3 |
| Cz. 2 | Qwen TP1: grid c1–c64 + profile c1/c16/c32 | 35 |
| Cz. 3 | Qwen TP2 wyspa (0,1): grid + profile | 35 |
| Cz. 4 | Qwen TP4 wyspa (0-3): grid + profile | 35 |
| Cz. 5 | Qwen TP8: grid + profile | 40 |
| Cz. 6 | cross: TP2 (0,4) + TP4 (0,1,4,5), grid bez profili | 40 |
| Cz. 7 | nop2p: TP2 + TP4 + TP8, grid bez profili | 55 |
| Cz. 8 | **burn-in 2 h @ 450 W** + log temperatur DCGM (bez nadzoru po starcie) | 130 |
| Cz. 9 | odczyt burn, podsumowania traców, restore Kimi, commit | 25 |
| | **razem** | **430** (aktywnie ~300) |

**Kolejność cięcia przy poślizgu:**

1. Cz. 7 TP2-nop2p w całości (TP2 i tak ~zero efektu komunikacji — P2P-off
   dało −0,6% w erze PCIe);
2. Cz. 6 TP2-cross: zostaw c1 i c64, tnij c16/c32;
3. profile c=32 każdego TP (zostają c1 i c16);
4. Cz. 7 TP4-nop2p: tnij c32 (zostają c1/c16/c64).

**Nietykalne:** Cz. 0, **Cz. 1** (główny cel — latencja), Cz. 2 i Cz. 4 w
całości (TP1 = punkt odniesienia; TP4 wyspa = replikacja + profil), Cz. 5
c32+c64, Cz. 7 TP8-nop2p c32, **Cz. 8** (burn-in — po starcie nie kosztuje
uwagi; przy dużym poślizgu można skrócić do 90 min, NIGDY poniżej — krzywa
temperatury musi objąć plateau), Cz. 9 restore + commit.

---

## Cz. 0 — start (7 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main

RUN_DIR=results/runs/2026-08-31_latencja_dostepu
NOUT="$RUN_DIR/nvlink"; QOUT="$RUN_DIR/qwen"; PROF="$RUN_DIR/profile"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
QWEN_COMPOSE="serving/compose/docker-compose.qwen3.6.yml"
IMAGE=vllm/vllm-openai:v0.20.0-cu130-ubuntu2404
SWE=results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl
TRACE_BASE=/home/working/nanoserve-tracing/qwen_tp_grid_$(date +%F)
mkdir -p "$NOUT" "$QOUT" "$PROF" "$RUN_DIR/session" "$TRACE_BASE"
set -a; source .env; set +a
DCGM_FIELDS=155,1002,1004,1005,1009,1010,1011,1012

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"

# wymiary modelu — do rozmiaru wiadomości all-reduce (c × hidden × 2 B)
# i liczby rund (≈ 2 × num_hidden_layers):
find /home/ubuntusrv2/.vllm/models -maxdepth 5 -path '*Qwen3.6-35B*' -name config.json \
  -exec python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(sys.argv[1]); print({k: d.get(k) for k in ("hidden_size","num_hidden_layers","num_key_value_heads","moe_intermediate_size")})' {} \; \
  | tee "$RUN_DIR/session/qwen_config_dims.txt"

docker compose -f "$COMPOSE" stop vllm vllm-small litellm open-webui
docker compose -f "$COMPOSE" rm -f vllm 2>/dev/null || true
nvidia-smi --query-gpu=index,memory.used --format=csv | tee "$RUN_DIR/session/gpu_free_check.csv"
# wszystkie karty ~0 MiB — inaczej mikro-latencje będą skażone
```

---

## Cz. 1 — mikro-latencje (25 min) — NIETYKALNA

### 1a. Latencja P2P par GPU (surowy dostęp, bez NCCL)

Mały transfer (8 B) — mierzymy czas operacji, nie przepustowość.
`NCCL_P2P_DISABLE` NIE dotyczy tego testu (to flaga NCCL); wariantu „off"
tu nie ma.

```bash
cat > "$NOUT/p2p_lat.py" <<'PYEOF'
import json, torch

PAIRS = [(0, 1), (0, 2), (0, 3), (0, 4), (3, 4)]  # 0-3 wyspa; 0-4/3-4 cross
ITERS, WARMUP = 500, 50
out = []
for src, dst in PAIRS:
    peer_ok = torch.cuda.can_device_access_peer(src, dst)
    a = torch.ones(4, dtype=torch.float16, device=f"cuda:{src}")
    b = torch.empty(4, dtype=torch.float16, device=f"cuda:{dst}")
    torch.cuda.set_device(src)
    for _ in range(WARMUP):
        b.copy_(a)
    torch.cuda.synchronize()
    beg, end = torch.cuda.Event(True), torch.cuda.Event(True)
    beg.record()
    for _ in range(ITERS):
        b.copy_(a)
    end.record()
    torch.cuda.synchronize()
    us = beg.elapsed_time(end) * 1e3 / ITERS
    out.append({"src": src, "dst": dst, "peer_access": peer_ok,
                "lat_us": round(us, 2)})
    print(f"GPU{src}->GPU{dst}  peer={peer_ok}  {us:6.2f} us/op", flush=True)
json.dump(out, open("/out/nvlink/p2p_lat.json", "w"), indent=2)
PYEOF

docker run --rm --gpus all --ipc=host --entrypoint bash \
  -v "$PWD/$RUN_DIR:/out" "$IMAGE" \
  -lc 'python3 /out/nvlink/p2p_lat.py' 2>&1 | tee "$NOUT/p2p_lat.txt"
```

### 1b. Latencja all-reduce NCCL — małe wiadomości, wszystkie grupy

To jest bezpośredni pomiar `r(łącze, liczba kart)`. Rozmiary od 4 KB
(reżim c=1) do 8 MB (kontrola zgodności z busbw z 07-31).

```bash
cat > "$NOUT/nccl_lat.py" <<'PYEOF'
import os, json, torch, torch.distributed as dist

dist.init_process_group("nccl")
rank, world = dist.get_rank(), dist.get_world_size()
torch.cuda.set_device(rank)
tag = os.environ.get("LAT_TAG", "run")
SIZES = [4096, 16384, 65536, 524288, 8 << 20]   # bajty
ITERS, WARMUP = 200, 20
res = {}
for size in SIZES:
    x = torch.ones(size // 2, dtype=torch.float16, device="cuda")
    for _ in range(WARMUP):
        dist.all_reduce(x)
    torch.cuda.synchronize(); dist.barrier()
    beg, end = torch.cuda.Event(True), torch.cuda.Event(True)
    beg.record()
    for _ in range(ITERS):
        dist.all_reduce(x)
    end.record()
    torch.cuda.synchronize()
    us = beg.elapsed_time(end) * 1e3 / ITERS
    algbw = size / (us / 1e6) / 1e9
    busbw = algbw * 2 * (world - 1) / world
    res[f"{size}B"] = {"lat_us": round(us, 2), "busbw_GBps": round(busbw, 2)}
    if rank == 0:
        print(f"{size:>9d} B  {us:8.2f} us/op  busbw {busbw:7.2f} GB/s", flush=True)
if rank == 0:
    json.dump(res, open(f"/out/nvlink/nccl_lat_{tag}.json", "w"), indent=2)
dist.destroy_process_group()
PYEOF

nccl_lat_run () {  # $1=CVD $2=nproc $3=tag $4=nop2p(0/1)
  extra=""
  [ "$4" = "1" ] && extra="-e NCCL_P2P_DISABLE=1"
  docker run --rm --gpus all --ipc=host --entrypoint bash \
    -e CUDA_VISIBLE_DEVICES="$1" -e LAT_TAG="$3" $extra \
    -e NCCL_DEBUG=INFO -e NCCL_DEBUG_SUBSYS=INIT,GRAPH \
    -v "$PWD/$RUN_DIR:/out" "$IMAGE" \
    -lc "torchrun --nproc_per_node=$2 /out/nvlink/nccl_lat.py" 2>&1 \
    | tee "$NOUT/nccl_lat_$3.txt"
}

# NVLink (mostki aktywne):
nccl_lat_run 0,1               2 island2 0
nccl_lat_run 0,4               2 cross2  0
nccl_lat_run 0,1,2,3           4 island4 0
nccl_lat_run 0,1,4,5           4 cross4  0
nccl_lat_run 0,1,2,3,4,5,6,7   8 all8    0
# nop2p (wyłączenie programowe):
nccl_lat_run 0,1               2 island2_nop2p 1
nccl_lat_run 0,1,2,3           4 island4_nop2p 1
nccl_lat_run 0,1,2,3,4,5,6,7   8 all8_nop2p    1

# szybka tabela zbiorcza (µs/op @ 16 KB — reżim dekodowania c=1):
for f in "$NOUT"/nccl_lat_*.json; do
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(f"{sys.argv[1].split(chr(47))[-1]:32s} 16KB: {d[\"16384B\"][\"lat_us\"]:8.2f} us  8MB busbw: {d[\"8388608B\"][\"busbw_GBps\"]:7.1f} GB/s")' "$f"
done | tee "$NOUT/lat_summary_quick.txt"
```

**Odczyt (zanim polecisz dalej):** predykcje §1 warstwa mikro. Kontrola
spójności: busbw @8 MB w wyspie-4 powinno leżeć w paśmie 185–333 GB/s
z 07-31 — jak nie, coś jest nie tak z przebiegiem, nie z latencją.
Wariant nop2p: w logu NCCL nie powinno być ścieżek P2P/NVL (grep niżej).

```bash
grep -iE "via P2P|NVL|SHM|Channel" "$NOUT/nccl_lat_island4.txt"       | head -20 > "$NOUT/nccl_path_island4.txt"
grep -iE "via P2P|NVL|SHM|Channel" "$NOUT/nccl_lat_island4_nop2p.txt" | head -20 > "$NOUT/nccl_path_island4_nop2p.txt"
```

---

## Cz. H — helpery (wklej cały blok, 3 min)

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

# overlay nop2p dla Qwena (forma mapy — zgodna z compose Qwena):
cat > /tmp/qwen-nop2p.yml <<'EOF'
services:
  vllm:
    environment:
      NCCL_P2P_DISABLE: "1"
EOF

# flaga profilera (vLLM v0.20: --profiler-config, NIE env — lekcja 08-03):
PROFILER_ARG='--profiler-config={"profiler":"torch","torch_profiler_dir":"/tmp/vllm_profile"}'

qwen_up () {  # $1=TP $2=CVD $3=extra_args(""=brak) $4=nop2p(0/1) $5=label
  export QWEN_TP="$1"; export QWEN_CUDA_VISIBLE_DEVICES="$2"
  if [ -n "$3" ]; then export QWEN_EXTRA_ARGS="$3"; else unset QWEN_EXTRA_ARGS; fi
  if [ "$4" = "1" ]; then
    docker compose -f "$QWEN_COMPOSE" -f /tmp/qwen-nop2p.yml up -d --force-recreate vllm
  else
    docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm
  fi
  wait_http_health http://127.0.0.1:8000/health 240 5 || { echo "START FAILED ($5)"; return 1; }
  docker inspect vllm --format '{{json .Config.Cmd}}' > "$QOUT/engine_cmd_$5.json"
  docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | sed -E 's/^(HUGGING_FACE_HUB_TOKEN|HF_TOKEN|[A-Z_]*API_KEY|[A-Z_]*SECRET[A-Z_]*)=.*/\1=REDACTED/' \
    > "$QOUT/engine_env_$5.txt"
  docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$QOUT/verify_$5.txt"
  grep -qx "tensor_parallel_size=$1" "$QOUT/verify_$5.txt" || echo "TP MISMATCH ($5) — PRZERWIJ"
  grep -q "^CUDA_VISIBLE_DEVICES=$2$" "$QOUT/engine_env_$5.txt" \
    || echo "ZŁY PLACEMENT ($5) — PRZERWIJ"
  if [ "$4" = "1" ]; then
    grep -q '^NCCL_P2P_DISABLE=1' "$QOUT/engine_env_$5.txt" \
      || echo "STOP: nop2p env NIE weszło ($5) — wyniki będą o NVLinku"
  fi
  if [ -n "$3" ]; then
    grep -o 'profiler-config' "$QOUT/engine_cmd_$5.json" \
      || echo "STOP: profiler-config nie wszedł przez QWEN_EXTRA_ARGS — fallback: overlay z pełną komendą (wzór: plan 2026-08-03-kimi-trace-nvlink.md, Cz. 3)"
  fi
  ensure_dataset || return 1
  bench_prereqs "$QWEN_COMPOSE" || return 1
}

qwen_warmup () {  # wygrzewka NA ODRZUT po każdym starcie (reguła 08-03)
  docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
      --dataset-name random --random-input-len 64 --random-output-len 256 \
      --ignore-eos --num-prompts 16 --max-concurrency 8 \
      --result-dir /tmp/xbench --result-filename warmup_discard.json'
}

qwen_bench_c () {  # $1=prefix $2=c $3=num_prompts $4=sufit_dcgmi_s
  tag="${1}_c${2}"
  start_sample_window "$tag" "$4"
  if [ "$2" -eq 1 ]; then
    docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
      export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
      vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
        --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
        --dataset-name random --random-input-len 64 --random-output-len 512 \
        --ignore-eos --num-warmups 3 --num-prompts '"$3"' --max-concurrency 1 \
        --save-result --result-dir /tmp/xbench --result-filename '"$tag"'.json'
  else
    docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
      export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
      vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
        --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
        --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
        --custom-output-len 256 --ignore-eos --num-prompts '"$3"' --max-concurrency '"$2"' \
        --save-result --result-dir /tmp/xbench --result-filename '"$tag"'.json'
  fi
  st=$?
  stop_sample_window || echo "WARN: sampler $tag"
  [ "$st" -ne 0 ] && echo "WARN: bench $tag failed"
}

qwen_collect () {  # $1=prefix
  mkdir -p "$QOUT/bench_$1"
  docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/xbench/. "$QOUT/bench_$1/"
  docker logs vllm > "$QOUT/log_$1.txt" 2>&1
  show_bench "$QOUT/bench_$1"
}

profile_c () {  # $1=tp_label $2=c — silnik już stoi z --profiler-config, PO gridzie
  ptag="${1}_c${2}_prof"
  curl -fsS -X POST http://127.0.0.1:8000/start_profile \
    || { echo "start_profile FAILED ($ptag) — profiler nieaktywny, pomiń profile tego TP"; return 1; }
  if [ "$2" -eq 1 ]; then
    docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
      export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
      vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
        --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
        --dataset-name random --random-input-len 64 --random-output-len 256 \
        --ignore-eos --num-prompts 8 --max-concurrency 1 \
        --save-result --result-dir /tmp/xbench --result-filename '"$ptag"'.json'
  else
    docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
      export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
      vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
        --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
        --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
        --custom-output-len 256 --ignore-eos --num-prompts '"$2"' --max-concurrency '"$2"' \
        --save-result --result-dir /tmp/xbench --result-filename '"$ptag"'.json'
  fi
  curl -fsS -X POST http://127.0.0.1:8000/stop_profile
  for _ in $(seq 1 30); do
    n=$(docker compose -f "$QWEN_COMPOSE" exec vllm bash -c 'ls /tmp/vllm_profile 2>/dev/null | wc -l' | tr -d '[:space:]')
    [ "${n:-0}" -gt 0 ] && break
    sleep 10
  done
  sleep 20
  docker compose -f "$QWEN_COMPOSE" exec vllm ls -la /tmp/vllm_profile/
  mkdir -p "$TRACE_BASE/$ptag"
  docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/vllm_profile/. "$TRACE_BASE/$ptag"/
  docker compose -f "$QWEN_COMPOSE" exec vllm bash -c 'rm -rf /tmp/vllm_profile/*'  # rozdziela profile
  ls -la "$TRACE_BASE/$ptag" | tee -a "$PROF/trace_files_listing.txt"
}
```

Konwencja gridu (spójna dla wszystkich konfiguracji NVLink):
c1: random 64/512, 40 promptów; c16: SWE 192; c32: SWE 320; c64: SWE 600.
Wariant nop2p: 24 / 96 / 160 / 300 (mediany porównywalne, throughput nie).
Kolejność ZAWSZE c1 → c16 → c32 → c64 (c64 dostaje najcieplejszy silnik —
ta sama sekwencja co 07-31). Uwaga stała: `max-num-seqs 32` w compose —
„c=64" to etykieta workloadu, realna głębokość batcha ≤32 (jak w baseline'ach).

---

## Cz. 2 — Qwen TP1 (35 min) — NIETYKALNA (punkt odniesienia)

```bash
P0OUT="$QOUT"
qwen_up 1 0 "$PROFILER_ARG" 0 tp1 || echo "PRZERWIJ"
qwen_warmup
qwen_bench_c tp1 1  40  600
qwen_bench_c tp1 16 192 600
qwen_bench_c tp1 32 320 700
qwen_bench_c tp1 64 600 900
qwen_collect tp1

profile_c tp1 1
profile_c tp1 16
profile_c tp1 32
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/xbench/. "$QOUT/bench_tp1/"  # JSON-y profili
show_bench "$QOUT/bench_tp1"   # kontrola narzutu: *_prof vs zwykłe (±15%)
```

**Odczyt:** ITL c1 vs 8,98 ms (PCIe era; TP1 nie powinno się ruszyć — kontrola
stabilności środowiska między epokami). Profile TP1 = czysty `F_host + W_silicon`,
zero NCCL.

---

## Cz. 3 — Qwen TP2 wyspa (0,1) (35 min)

```bash
qwen_up 2 0,1 "$PROFILER_ARG" 0 tp2isl || echo "PRZERWIJ"
qwen_warmup
qwen_bench_c tp2isl 1  40  600
qwen_bench_c tp2isl 16 192 600
qwen_bench_c tp2isl 32 320 700
qwen_bench_c tp2isl 64 600 900
qwen_collect tp2isl

profile_c tp2isl 1
profile_c tp2isl 16
profile_c tp2isl 32
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/xbench/. "$QOUT/bench_tp2isl/"
show_bench "$QOUT/bench_tp2isl"
```

---

## Cz. 4 — Qwen TP4 wyspa (0-3) (35 min) — NIETYKALNA (replikacja + profil)

```bash
qwen_up 4 0,1,2,3 "$PROFILER_ARG" 0 tp4isl || echo "PRZERWIJ"
# bramka custom-AR: przy pełnej siatce w wyspie kernel MA być aktywny
docker logs vllm 2>&1 | grep -c "custom_all_reduce.py.*Registering" \
  | tee "$QOUT/allreduce_gate_tp4isl.txt"   # oczekiwane >0
qwen_warmup
qwen_bench_c tp4isl 1  40  600
qwen_bench_c tp4isl 16 192 600
qwen_bench_c tp4isl 32 320 700
qwen_bench_c tp4isl 64 600 900
qwen_collect tp4isl   # c64: REPLIKACJA vs 2022/1989 — czytaj od razu

profile_c tp4isl 1
profile_c tp4isl 16
profile_c tp4isl 32
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/xbench/. "$QOUT/bench_tp4isl/"
show_bench "$QOUT/bench_tp4isl"
```

---

## Cz. 5 — Qwen TP8 (40 min)

```bash
qwen_up 8 0,1,2,3,4,5,6,7 "$PROFILER_ARG" 0 tp8 || echo "PRZERWIJ"
# custom-AR: TP8 przez dwie wyspy = siatka NIEpełna → registering oczekiwane 0
docker logs vllm 2>&1 | grep -c "custom_all_reduce.py.*Registering" \
  | tee "$QOUT/allreduce_gate_tp8.txt"
qwen_warmup
qwen_bench_c tp8 1  40  600
qwen_bench_c tp8 16 192 700
qwen_bench_c tp8 32 320 900
qwen_bench_c tp8 64 600 1200
qwen_collect tp8

profile_c tp8 1
profile_c tp8 16
profile_c tp8 32
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/xbench/. "$QOUT/bench_tp8/"
show_bench "$QOUT/bench_tp8"
```

---

## Cz. 6 — warianty cross-island: TP2 (0,4) i TP4 (0,1,4,5) (40 min)

Bez profili — te starty odpowiadają na jedno pytanie: ile kosztuje trasa/odcinek
cross w e2e. Kontrola placementu przez pobór mocy: karty nieużywane ~70 W.

```bash
qwen_up 2 0,4 "" 0 tp2cross || echo "PRZERWIJ"
qwen_warmup
qwen_bench_c tp2cross 1  40  600
qwen_bench_c tp2cross 16 192 600
qwen_bench_c tp2cross 32 320 700
qwen_bench_c tp2cross 64 600 900
qwen_collect tp2cross

qwen_up 4 0,1,4,5 "" 0 tp4cross || echo "PRZERWIJ"
# custom-AR: 2+2 przez wyspy = siatka NIEpełna → registering oczekiwane 0;
# >0 oznaczałoby, że vLLM widzi pełną siatkę wbrew topologii — ZANOTUJ
docker logs vllm 2>&1 | grep -c "custom_all_reduce.py.*Registering" \
  | tee "$QOUT/allreduce_gate_tp4cross.txt"
qwen_warmup
qwen_bench_c tp4cross 1  40  600
qwen_bench_c tp4cross 16 192 600
qwen_bench_c tp4cross 32 320 700
qwen_bench_c tp4cross 64 600 900
qwen_collect tp4cross
```

**Uwaga interpretacyjna (TP4 cross):** wynik ≠ czysta kara trasy — 2+2 traci
też kernel custom-AR (siatka niepełna). To ta sama „ukryta druga zmiana" co
w kroku 20 prezentacji; rozdzielenie wkładów = porównanie z tp4isl-noAR
(2026-08-03: ciepły noAR c64) w analizie po sesji.

---

## Cz. 7 — nop2p (wyłączenie programowe NVLink) (55 min)

Mniejsze `num-prompts` (będzie wolno): c1 24, c16 96, c32 160, c64 300.
Mediany ITL/TPOT porównywalne z gridem NVLink, `output_throughput` NIE.

```bash
qwen_up 2 0,1 "" 1 tp2nop2p || echo "PRZERWIJ"
qwen_warmup
qwen_bench_c tp2nop2p 1  24  900
qwen_bench_c tp2nop2p 16 96  900
qwen_bench_c tp2nop2p 32 160 1200
qwen_bench_c tp2nop2p 64 300 1500
qwen_collect tp2nop2p

qwen_up 4 0,1,2,3 "" 1 tp4nop2p || echo "PRZERWIJ"
qwen_warmup
qwen_bench_c tp4nop2p 1  24  900
qwen_bench_c tp4nop2p 16 96  900
qwen_bench_c tp4nop2p 32 160 1200
qwen_bench_c tp4nop2p 64 300 1500
qwen_collect tp4nop2p

qwen_up 8 0,1,2,3,4,5,6,7 "" 1 tp8nop2p || echo "PRZERWIJ"
qwen_warmup
qwen_bench_c tp8nop2p 1  24  900
qwen_bench_c tp8nop2p 16 96  1200
qwen_bench_c tp8nop2p 32 160 1500   # NIETYKALNY — odpowiednik rekonstrukcji 08-03
qwen_bench_c tp8nop2p 64 300 1800
qwen_collect tp8nop2p

# dowód przyczynowy z liczników: NVL ~0, PCIe RX w górę (kolumny wg nagłówka!):
head -3 "$QOUT/tp8nop2p_c32_dcgmi.txt"
```

---

## Cz. 8 — burn-in 2 h @ ~3/4 mocy + log temperatur DCGM (130 min) — NIETYKALNA

**Metoda:** cap mocy 450 W (3/4 z 600) + saturujący GEMM fp16 na wszystkich
8 kartach. GEMM chce >450 W, cap trzyma równo 450 → stabilny punkt pracy;
throttle „SW Power Cap" jest wtedy **normą** (to mechanizm testu), alarmem
jest wyłącznie HW Thermal. Dlaczego nie inferencja: comms-bound daje
111–200 W przy TP≥4 — nie dojedzie do 3/4 mocy. Dlaczego ostatnia część:
2 h heat-soak nie może poprzedzać pomiarów latencji.

**Po starcie bloku „POMIAR" można odejść od klawiatury** — burn i sampler
kończą się same po ~125 min; wróć na Cz. 9.

```bash
BOUT="$RUN_DIR/burnin"; mkdir -p "$BOUT"
docker compose -f "$QWEN_COMPOSE" down    # GPU muszą być wolne

# temperatura otoczenia z BMC (czujniki potwierdzone na tym hoście:
# "Inlet Temp" = wlot obudowy, "System Temp" = wnętrze). ipmitool to czysty
# odczyt SDR — bez wpływu na serwis; przy braku /dev/ipmi0: modprobe niżej.
command -v ipmitool >/dev/null || sudo apt install -y ipmitool
[ -e /dev/ipmi0 ] || sudo modprobe ipmi_devintf ipmi_si
sudo ipmitool sensor reading "Inlet Temp" "System Temp" \
  | tee "$BOUT/ambient_check.txt"     # obie linie z liczbą? inaczej NIE licz na log

# progi termiczne i stan wyjściowy limitu mocy (do restore!):
nvidia-smi -q -d TEMPERATURE > "$BOUT/temp_thresholds.txt"
nvidia-smi -q -d POWER | grep -E "Current Power Limit|Default Power Limit" \
  | tee "$BOUT/power_limits_before.txt"
sudo nvidia-smi -pl 450 | tee "$BOUT/set_pl_450.txt"
nvidia-smi --query-gpu=index,power.limit --format=csv | tee -a "$BOUT/set_pl_450.txt"
# wszystkie 8 kart mają pokazać 450.00 W — inaczej NIE startuj burna

# skrypt obciążenia: GEMM fp16 per GPU, czas trwania w minutach jako arg
cat > "$BOUT/burn_gemm.py" <<'PYEOF'
import sys, time, torch, torch.multiprocessing as mp

def burn(i, minutes):
    torch.cuda.set_device(i)
    n = 8192
    a = torch.randn(n, n, dtype=torch.float16, device="cuda")
    b = torch.randn(n, n, dtype=torch.float16, device="cuda")
    c = torch.empty(n, n, dtype=torch.float16, device="cuda")
    t_end = time.time() + minutes * 60
    it = 0
    while time.time() < t_end:
        torch.matmul(a, b, out=c)
        it += 1
        if it % 5000 == 0:
            torch.cuda.synchronize()
            print(f"gpu{i} iter {it} t={time.strftime('%H:%M:%S')}", flush=True)
    torch.cuda.synchronize()
    print(f"gpu{i} DONE iters={it}", flush=True)

if __name__ == "__main__":
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 120
    mp.set_start_method("spawn")
    procs = [mp.Process(target=burn, args=(i, minutes))
             for i in range(torch.cuda.device_count())]
    [p.start() for p in procs]
    [p.join() for p in procs]
PYEOF

# ── POMIAR: sampler temperatur w tle + burn 120 min ──────────────────────
# pola: 150=GPU_TEMP, 140=MEMORY_TEMP(HBM), 155=POWER, 100=SM_CLOCK,
# 112=CLOCK_THROTTLE_REASONS; próbka co 5 s, sufit 125 min = 1500 próbek.
# Probe nagłówka: jeśli 140/112 nieobsługiwane — usuń je z listy i ponów.
dcgmi dmon -e 150,140,155,100,112 -d 5000 -c 2 > "$BOUT/dcgmi_probe.txt" 2>&1
head -3 "$BOUT/dcgmi_probe.txt"

date +%s > "$BOUT/burn_start_epoch.txt"
dcgmi dmon -e 150,140,155,100,112 -d 5000 -c 1500 > "$BOUT/burn_dcgmi.txt" 2>&1 &
BURN_SAMPLE_PID=$!

# snapshoty nvidia-smi co 10 min (niezależne źródło, 12 klatek):
( for _ in $(seq 1 12); do
    date -Is >> "$BOUT/nvidia_smi_snapshots.txt"
    nvidia-smi >> "$BOUT/nvidia_smi_snapshots.txt"
    sleep 600
  done ) &
SNAP_PID=$!

# temperatura otoczenia do logu, próbka co 60 s (Inlet = wlot, System = wnętrze):
( while true; do
    echo "$(date -Is) | $(sudo ipmitool sensor reading 'Inlet Temp' 'System Temp' \
      | tr '\n' ';')"
    sleep 60
  done ) >> "$BOUT/ambient_ipmi.txt" 2>&1 &
AMB_PID=$!

docker run --rm --gpus all --ipc=host --entrypoint bash \
  -v "$PWD/$BOUT:/burn" "$IMAGE" \
  -lc 'python3 /burn/burn_gemm.py 120' 2>&1 | tee "$BOUT/burn_stdout.txt"

date +%s > "$BOUT/burn_end_epoch.txt"
kill "$SNAP_PID" 2>/dev/null || true
kill "$AMB_PID" 2>/dev/null || true
pkill -TERM -P "$BURN_SAMPLE_PID" 2>/dev/null || true; wait "$BURN_SAMPLE_PID" 2>/dev/null

# ── RESTORE limitu mocy — OBOWIĄZKOWE, przed czymkolwiek innym ──────────
sudo nvidia-smi -pl 600 | tee "$BOUT/restore_pl_600.txt"
nvidia-smi --query-gpu=index,power.limit --format=csv | tee -a "$BOUT/restore_pl_600.txt"
# wartość docelowa = Default Power Limit z power_limits_before.txt (oczekiwane 600 W)

# kontrole po burnie:
sudo dmesg -T | grep -iE "xid|nvrm|thermal" | tail -40 > "$BOUT/dmesg_after_burn.txt"
[ -s "$BOUT/dmesg_after_burn.txt" ] || echo "# dmesg $(date -Is): zero wpisow xid/nvrm/thermal" > "$BOUT/dmesg_after_burn.txt"
grep -ci "xid" "$BOUT/dmesg_after_burn.txt" && echo "UWAGA: Xid po burnie — do issue" || echo "zero Xid — OK"
# log zdarzeń BMC — niezależne od dmesg źródło zdarzeń termicznych/zasilania:
sudo ipmitool sel list | tail -40 > "$BOUT/ipmi_sel_after_burn.txt" 2>&1
[ -s "$BOUT/ipmi_sel_after_burn.txt" ] || echo "# SEL pusty $(date -Is) — zero zdarzen" > "$BOUT/ipmi_sel_after_burn.txt"
```

**Szybki odczyt (kolumny sprawdź w nagłówku `burn_dcgmi.txt` — nie zgaduj):**

```bash
# max/avg temperatury i mocy per burn-okno (przykład dla układu kolumn
# GPU TMPTR MMTMP POWER SMCLK ...; POPRAW indeksy wg nagłówka):
awk 'NR>2 && $1=="GPU" {t[$2]=($3>t[$2])?$3:t[$2]; m[$2]=($4>m[$2])?$4:m[$2]; p+=$5; n++}
     END {for (g in t) printf "GPU%s  Tmax=%s  HBMmax=%s\n", g, t[g], m[g];
          if (n) printf "moc avg (wszystkie GPU): %.0f W\n", p/n}' "$BOUT/burn_dcgmi.txt" \
  | tee "$BOUT/burn_quick_readout.txt"
```

Werdykt wg §1 „Warstwa burn-in": moc ~450 W stabilnie, temperatury z plateau
poniżej progów, throttle wyłącznie SW Power Cap, zero Xid → serwer zaliczony
na pracę ciągłą @3/4 mocy. Fallback, gdyby `sudo nvidia-smi -pl` było
zablokowane: `sudo nvidia-smi -lgc <MHz>` (lock zegara dobrany tak, by moc
≈450 W — wymaga 2–3 prób kalibracji po 2 min) albo duty-cycle w skrypcie
(matmul + sleep) — mniej stabilne, oznaczyć w artefaktach.

---

## Cz. 9 — odczyt burn + podsumowania traców + restore + commit (25 min)

### 9a. Szybkie podsumowania rank0 wszystkich profili

```bash
summarize_trace () {  # $1=plik tracu $2=etykieta
  uv run python - "$1" <<'PYEOF' | tee "$PROF/trace_summary_$2.txt"
import json,gzip,sys,collections
p=sys.argv[1]; op=gzip.open if p.endswith('.gz') else open
d=json.load(op(p,'rt'))
ev=[e for e in d.get('traceEvents',[]) if e.get('ph')=='X' and 'dur' in e]
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

for d in "$TRACE_BASE"/tp*_prof; do
  f=$(find "$d" -type f \( -name '*.json' -o -name '*.json.gz' \) | sort | head -1)
  [ -n "$f" ] && summarize_trace "$f" "$(basename "$d")"
done
echo "$TRACE_BASE" > "$PROF/trace_local_path.txt"
```

### 9b. Restore Kimi + stack

```bash
nvidia-smi --query-gpu=index,power.limit --format=csv   # 600 W wszędzie? (po Cz. 8)
docker compose -f "$QWEN_COMPOSE" down 2>/dev/null || true
unset QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_ARGS
docker compose -f "$COMPOSE" up -d --force-recreate vllm    # plain, bez overlayów
wait_http_health http://127.0.0.1:8000/health 360 5 || echo "KIMI RESTORE FAILED"
docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep NCCL_P2P_DISABLE && echo "UWAGA: nop2p przetrwał restore — powtórz recreate" \
  || echo "restore czysty"
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -o 'profiler-config' \
  && echo "UWAGA: profiler w Cmd Kimi — powtórz recreate" || echo "bez profilera — OK"
docker compose -f "$COMPOSE" up -d vllm-small litellm open-webui
wait_http_health http://127.0.0.1:8004/health 240 5 && echo "deepseek OK"
curl -fsS http://127.0.0.1:8000/health && echo "kimi OK"
docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/restore_ps.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
git rev-parse HEAD > "$RUN_DIR/session/end_commit.txt"
```

### 9c. Commit

```bash
git status
du -sh "$RUN_DIR"    # traców w repo NIE ma (tylko summary/listing/ścieżka)
find "$RUN_DIR" -name 'engine_env_*' -exec grep -l "HUGGING_FACE_HUB_TOKEN=hf_" {} \; \
  && echo "STOP: token w artefaktach — popraw redakcję przed commitem"
git add "$RUN_DIR"
git commit -m "bench: latencja all-reduce (mikro) + grid Qwen TP1-8 x c x lacze + profile TP1-8 + burn-in 2h @450W"
git push -u origin main
```

---

## Po sesji (laptop, poza slotem)

1. **Kalibracja `r`:** tabela `r(łącze, grupa)` z Cz. 1 (16 KB i rozmiar
   wiadomości z `qwen_config_dims.txt`); rachunek krzyżowy
   `ΔITL c1 ≈ 2L × r_micro` per TP — wpis do notatki decyzyjnej §4.
2. **Kara cross-island w e2e** (tp4cross vs tp4isl) + rozdzielenie wkładu
   custom-AR (porównanie z ciepłym noAR 08-03) → aktualizacja mechanizmu
   capture 0,62 w #50.
3. **Profile:** macierz NCCL%/gaps%/compute% TP×c → czy komunikacja dominuje
   dopiero od TP≥4 i c≥16 także u Qwena po NVLinku (symetria z Kimi 61,1%).
4. **Burn-in:** wykres temperatura/moc w czasie z `burn_dcgmi.txt` + Inlet/System
   z `ambient_ipmi.txt` (plateau, delta T_GPU−T_inlet, rozrzut między kartami),
   krótkie podsumowanie do
   `results/summaries/` + wiersz do `infrastructure.md` (serwer zwalidowany
   na pracę ciągłą @450 W/kartę, data, warunki).
5. Docs: `benchmark-methodology.md` (metoda pomiaru latencji rundy),
   T9/notatka decyzyjna (sekcja `r` zmierzone vs implikowane), komentarz #50,
   ewentualny materiał do prezentacji (slajd 12 speaker notes: własne liczby
   zamiast literaturowych), `sync-state`.

## Wątki otwarte (nie w tym slocie)

- Latencja rund Kimi TP8 (profil per-call histogram wywołań NCCL) — osobna
  sesja, jeśli macierz Qwena potwierdzi mechanizm.
- Anomalia c=16 (zaparkowana) — grid c=16 z tej sesji da darmowy sygnał, czy
  patologia występuje też u Qwena przy którymś TP; czytać ITL, nie throughput.

---

## Walidacja planu

```text
git status + git diff --check    (docs-only; skrypty są heredocami wewnątrz planu)
```
