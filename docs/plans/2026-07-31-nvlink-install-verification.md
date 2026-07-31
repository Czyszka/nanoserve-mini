# Sesja serwerowa 2026-07-31 — weryfikacja instalacji NVLink 4-way

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL)
**Slot:** ~2 h. Restarty silników dozwolone.
**Konfiguracja sprzętowa (deklarowana):** mostki **4-way, dwie wyspy** —
GPU 0-1-2-3 oraz GPU 4-5-6-7.
**Kontekst:** issue #50, werdykt `results/summaries/2026-06-11-nvlink-boundary-verdict.md`,
wątek `docs/writeups/w1/t9-bottleneck-nvlink.md`, notatka decyzyjna
`docs/writeups/w1/nvlink-4way-notatka-decyzyjna.md`.

> **Plan jest samowystarczalny.** Wszystkie funkcje pomocnicze i komendy są
> wypisane w całości — nic nie trzeba doklejać z poprzednich planów. Sesja
> 2026-06-11 przepadła właśnie na tym (compose bez interpolacji `${QWEN_TP}`,
> `export QWEN_TP` po cichu zignorowany, benche z błędnym TP).

---

## 0. Po co ta sesja

Dwa cele, w tej kolejności:

1. **Czy NVLink faktycznie działa** — sterownik widzi linki, topologia się
   zmieniła, brak narastających błędów, surowa przepustowość rośnie o rząd
   wielkości względem PCIe.
2. **Czy werdykt #50 się potwierdza.** Cała decyzja zakupowa stała na
   **predykcjach z modelu** `gain = 1/(1 − share × capture)`, wyliczonych na
   PCIe. Teraz mostki są w środku, więc predykcje są **falsyfikowalne**. To
   rzadka okazja: pre-rejestrowana predykcja + pomiar po interwencji.

Mierzymy **dwa modele**, bo odpowiadają na różne pytania:

- **Qwen TP4 w jednej wyspie** — czysty test mechanizmu (wszystkie pary po
  NVLinku, zero segmentów mieszanych), tam gdzie powstała predykcja 2,1×.
- **Kimi TP8 przez dwie wyspy** — realny scenariusz produkcyjny i jedyny, który
  uzasadniał zakup (predykcja 2,7× przy `capture 0,75`). Start silnika Kimi jest
  **i tak wymagany** jako restore na koniec sesji, więc koszt krańcowy tego testu
  to same benche.

DeepSeek-V4-Flash odpada: `--max-num-seqs 2` w compose oznacza, że nie ma jak
zrobić testu batched, a jego baseline'y z 06-05 są sekwencyjne (c=1), czyli w
strefie, gdzie werdykt przewiduje zysk ≈ 0.

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

Baseline pochodzi z `results/runs/2026-06-11_nvlink_boundary/` (Q3 intra + K1)
oraz `results/summaries/2026-06-11-qwen-tp-curve.md`.

### Warstwa sprzętowa

| pomiar | baseline PCIe | predykcja | falsyfikacja |
|---|---:|---|---|
| P2P uni GPU0↔GPU1 (ta sama wyspa) | ~25–50 GB/s | **> 100 GB/s** | < 60 GB/s → mostek nie działa lub siedzi krzywo |
| P2P uni GPU0↔GPU4 (**kontrola**, cross-island) | PCIe/UPI | **bez zmian** | wzrost → mapa wysp jest zła |
| NCCL busbw, 4 ranki w wyspie (0-3) | sufit ~7,2–7,9 GB/s | **> 100 GB/s** | < 30 GB/s → NCCL nie wybrał NVLinka |
| NCCL busbw, 2+2 przez wyspy (0,1,4,5) | — | **rozstrzyga ring vs hierarchia** | ~7 GB/s → płaski ring, `capture 0,75` to zły model |

### Qwen TP4, jedna wyspa (GPU 0-3) — test mechanizmu

| pomiar | baseline PCIe (06-11) | predykcja #50 | falsyfikacja |
|---|---:|---|---|
| c=64, out tok/s | **680** | **~1430** (share 0,533 × capture 1,0 ⇒ 2,1×) | < 850 → model zawyżony |
| c=64, ITL med | **53,7 ms** | **~26 ms** | > 45 ms → jw. |
| c=1, ITL med | **10,54 ms** | **9–10,5 ms** (podłoga rządzi) | < 8 ms → teza „c=1 floor-bound" upada |
| c=1, TPOT med | **4,00 ms** | **≥ 3,4 ms** | jw. |

Punkt odniesienia dla decyzji serwowania: **TP2 na PCIe dawał 1404 tok/s @c64.**
Jeśli TP4+NVLink dobije do ~1400, TP4 przestaje być karą.

### Kimi TP8, dwie wyspy — scenariusz produkcyjny

| pomiar | baseline PCIe (K1, 06-11) | predykcja #50 | falsyfikacja |
|---|---:|---|---|
| c=32, out tok/s | **285** | **~770** (share 0,839 × capture 0,75 ⇒ 2,7×) — traktuj jako **górne** oszacowanie, patrz niżej | < 400 → `capture 0,75` zawyżony |
| c=32, ITL med | **127 ms** | **~47 ms** | > 100 ms → jw. |
| c=1, TPOT med | **8,7 ms** | **≥ 6,7 ms** (≤1,3×, gaps 63%) | < 5 ms → teza „floor-bound przy c=1" upada |
| c=16, ITL med | **512 ms** (anomalia) | **anomalia zostaje** | zniknie → anomalia była transportowa, nie schedulerowa |
| PCIe RX @c≥8 | **sufit 7,2–7,9 GB/s** | **wyraźny spadek** (ruch na NVLink) | brak spadku → NCCL nie używa mostków w TP8 |

Ostatni wiersz jest niezależnym sygnałem z liczników dcgmi — nie wymaga wiary w
log NCCL ani w benchmark.

### Warstwa vLLM — co ma się zmienić w logu silnika

Custom all-reduce **nie jest wyłączony flagą w compose** — engine config raportuje
`disable_custom_all_reduce=False`. vLLM **sam** go dezaktywuje w runtime, bo nie
spełniony jest warunek topologiczny. To znaczy, że włożenie mostków powinno go
odblokować bez żadnej zmiany konfiguracji.

**Uwaga kluczowa: `custom_all_reduce` wymaga PEŁNEJ SIATKI NVLink w grupie TP.**
vLLM nie pyta „czy jest jakiś NVLink", tylko sprawdza **każdą parę ranków** (NVML
P2P per para, `is_full_nvlink`). Przy mostkach 4+4:

- **TP=4 w jednej wyspie (Qwen, GPU 0-3)** — wszystkie 6 par ma link ⇒ pełna
  siatka ⇒ **warning znika**.
- **TP=8 przez dwie wyspy (Kimi)** — pary typu GPU0↔GPU4 linku nie mają ⇒ siatka
  niepełna ⇒ **warning zostaje**, mimo że mostki działają poprawnie.

| linia w logu | PCIe (06-08) | Qwen TP4 intra | Kimi TP8 (4+4) |
|---|---|---|---|
| `custom_all_reduce.py:153` *„not supported on more than two PCIe-only GPUs"* | obecna | **znika** | **zostaje** (siatka niepełna) |
| `flashinfer_all_reduce.py:65` *„does not support multicasting … **NVLink bridge-only** or PCIe"* | obecna | zostaje | zostaje |
| `allreduce_rms_fusion.py:801` *„fusion will be disabled"* | obecna | zostaje | zostaje |

Drugi wiersz: vLLM **wprost wymienia „NVLink bridge-only"** jako topologię bez
multicastu. Multicast daje NVSwitch, nie mostki — ścieżka FlashInfer/NVLS nie
wróci ani przy TP4, ani przy TP8.

**To daje darmowy rozstrzygacz, o ile Cz. 4 poleci przed Cz. 5:**

| Qwen TP4 | Kimi TP8 | wniosek |
|---|---|---|
| warning znika | warning zostaje | **mostki działają**; TP=8 nie dostaje custom AR z powodu topologii 4+4 — zgodnie z oczekiwaniem |
| warning zostaje | warning zostaje | **vLLM nie widzi mostków w ogóle** — awaria, wróć do Cz. 1 |
| warning znika | warning znika | niespodzianka — vLLM traktuje TP8 jako pełną siatkę; zanotuj, bo przeczy powyższemu modelowi |

Bez wyniku z Qwena warning u Kimi jest **nierozstrzygalny** — dlatego Cz. 4 nie
jest tu tylko „ładniejsza metodologicznie".

**Konsekwencja dla predykcji Kimi:** jeśli TP=8 nigdy nie dostanie kernela custom
all-reduce przy topologii 4+4, to cały zysk musi pochodzić z tego, że **NCCL**
używa NVLinka na odcinkach wewnątrz wysp. Szacunek 2,7× był liczony bez tego
rozróżnienia, więc należy go traktować jako **optymistyczny**. Zejście na TP=4 w
jednej wyspie nie jest dla Kimi opcją — T9 ustalił, że model się na 4 GPU nie
mieści.

**Uwaga o czystości dawki:** mostki zmieniają dwie rzeczy naraz — (a) klasę linku,
(b) odblokowanie custom all-reduce. Dzisiejszy zysk to zysk **pakietu**.
Rozdzielenie wymaga osobnej dawki: jawne `--disable-custom-all-reduce` w komendzie
silnika **przy włożonych mostkach** (to flaga CLI, nie zmienna środowiskowa) —
poza tym slotem, zanotowane w wątkach otwartych.

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. 0 | stan wyjściowy + zwolnienie GPU | 5 |
| Cz. 1 | **BRAMKA:** czy sterownik widzi linki + topologia | 10 |
| Cz. 2 | surowa przepustowość P2P (z kontrolą cross-island) | 15 |
| Cz. 3 | NCCL busbw: wyspa + **kontrola 2+2** | 15 |
| Cz. H | wklejenie funkcji pomocniczych | 2 |
| Cz. 4 | Qwen TP4 intra c=1 + c=64 (test mechanizmu) | 25 |
| Cz. 5 | Kimi TP8 c=1/16/32 (= restore + bench) | 30 |
| Cz. 6 | liczniki błędów, domknięcie stacku, commit | 10 |
| | **razem** | **112** |

**Kolejność cięcia przy poślizgu:**
Cz. 5 c=16 → Cz. 4 c=1 → Cz. 3 (wyspa 0-3) → Cz. 2 (pary dalsze) → Cz. 4 c=64.

**Nietykalne:** Cz. 0, Cz. 1, Cz. 3 (kontrola 2+2), **start Qwena TP4 z odczytem
logu** (rozstrzygacz custom all-reduce, §1), **Cz. 5 c=32**, Cz. 6.

Uzasadnienie: Cz. 5 c=32 to jedyny pomiar realnego scenariusza produkcyjnego.
Cz. 4 można okroić do samego startu silnika + `grep` po logu (~7 min) — **ale nie
skasować całkowicie**, bo bez niej warning o custom all-reduce u Kimi jest
nierozstrzygalny (nie wiadomo, czy to normalna konsekwencja topologii 4+4, czy
awaria montażu). **Cz. 6 nigdy nie tnij:** restore stacku i tak trzeba zrobić, a
liczniki błędów bez odczytu po obciążeniu są bezwartościowe.

---

## Cz. 0 — start i stan wyjściowy (5 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main
# BEZ set -euo pipefail; BEZ exit — sesja interaktywna po SSH

RUN_DIR=results/runs/2026-07-31_nvlink_install
NOUT="$RUN_DIR/nvlink"; QOUT="$RUN_DIR/qwen"; KOUT="$RUN_DIR/kimi"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
QWEN_COMPOSE="serving/compose/docker-compose.qwen3.6.yml"
IMAGE=vllm/vllm-openai:v0.20.0-cu130-ubuntu2404
SWE=results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl
mkdir -p "$NOUT" "$QOUT" "$KOUT" "$RUN_DIR/session"
set -a; source .env; set +a

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"

# inwentarz z bus-ID — potrzebny do mapowania numerów GPU na fizyczne sloty
nvidia-smi --query-gpu=index,serial,uuid,pci.bus_id --format=csv \
  | tee "$RUN_DIR/session/gpu_inventory.csv"

# ślad trenowania linków po zmianie topologii
dmesg | grep -i "nvlink\|nvrm" | tail -80 \
  > "$RUN_DIR/session/dmesg_nvrm.txt" 2>&1
```

Fabric manager świadomie pominięty: to warstwa dla **NVSwitch** (HGX/DGX), a tu
są bezpośrednie mostki — nie ma fabric do zainicjalizowania.

**Zwolnij GPU na Cz. 1–4:**

```bash
docker compose -f "$COMPOSE" stop vllm vllm-small litellm open-webui
docker compose -f "$COMPOSE" rm -f vllm 2>/dev/null || true   # kolizja container_name z compose Qwena
nvidia-smi --query-gpu=index,memory.used --format=csv | tee "$RUN_DIR/session/gpu_free_check.csv"
# wszystkie karty powinny mieć ~0 MiB — inaczej pomiary P2P będą zaniżone
```

---

## Cz. 1 — BRAMKA: czy sterownik widzi linki i czy topologia się zmieniła (10 min)

To jest jedyna część, bez której cała reszta nie ma sensu.

```bash
nvidia-smi nvlink --help > "$NOUT/nvlink_help.txt" 2>&1   # składnia flag bywa wersyjna
nvidia-smi nvlink -s      > "$NOUT/nvlink_status.txt" 2>&1
nvidia-smi nvlink -c      > "$NOUT/nvlink_caps.txt" 2>&1
nvidia-smi -q -d NVLINK   > "$NOUT/nvlink_query_full.txt" 2>&1

# TOPOLOGIA — pojedynczy najważniejszy artefakt sesji
nvidia-smi topo -m        | tee "$NOUT/topo_m.txt"
nvidia-smi topo -p2p rw   > "$NOUT/topo_p2p_rw.txt" 2>&1
# macierz NVLink per para — to jest dokładnie to, co czyta vLLM w is_full_nvlink;
# jeśli flaga 'n' nie jest wspierana, ta sama informacja jest w topo -m
nvidia-smi topo -p2p n    > "$NOUT/topo_p2p_nvlink.txt" 2>&1

# migawka liczników błędów PRZED obciążeniem (delta > reset — nie zależy od
# tego, czy ta wersja nvidia-smi w ogóle wspiera reset liczników)
nvidia-smi nvlink -e > "$NOUT/nvlink_errors_before.txt" 2>&1
```

**Jak to czytać — trzy warunki, wszystkie muszą być spełnione:**

1. **`topo_m.txt`:** każda z **sześciu** par wewnątrz wyspy 0-3 (`0↔1, 0↔2, 0↔3,
   1↔2, 1↔3, 2↔3`) pokazuje `NV<n>`, i analogicznie sześć par w 4-7. Jeżeli
   `NV` widać tylko dla par sąsiednich (`0↔1`, `2↔3`), mostek pracuje jak
   **dwa 2-way**, a nie jak 4-way — a wtedy werdykt #50 przewiduje zysk ≈ 0,
   bo TP=2 był przypadkiem NO-GO.
2. **Pary międzywyspowe (`0↔4` itd.) muszą dalej pokazywać `SYS`.** To nie
   błąd — to potwierdzenie mapy wysp i podstawa dla `capture ≈ 0,75` przy TP=8.
3. **`nvlink_status.txt`:** policz linki per peer. H200 NVL ma 18 linków po
   ~26,5 GB/s/kierunek. Przy 4-way spodziewaj się **~6 linków na peera**
   (`NV6` w macierzy) ⇒ ok. 155–160 GB/s/kierunek do sąsiada. Przy 2-way byłoby
   18 linków do jednego peera. **Zapisz to, co widzisz** — liczba linków jest
   twardym odczytem trybu mostka, niezależnym od deklaracji montażowej.

**Bramka 1 — STOP, jeśli:** `topo -m` pokazuje `SYS`/`PXB`/`PIX` między parami,
które fizycznie zmostkowałeś, albo `nvlink -s` daje `inactive` / pusty output.
`nvlink -s` potrafi raportować obecność linku, którego topologia nie używa —
**wierz `topo -m`, nie `nvlink -s`.** W tym wypadku nie benchuj; przejdź do
sekcji „Gdy nic nie widać" i skończ sesję na diagnostyce (to też jest wynik
wart commita).

---

## Cz. 2 — surowa przepustowość P2P (15 min)

Świadomie **nie klonujemy `cuda-samples`** — `make` w krótkim slocie to strata
15 min i zależność od sieci. Obraz vLLM ma torch i NCCL; to wystarcza.

Kluczowy element metodyczny: **para kontrolna `0↔4`** mierzona tym samym
skryptem, w tym samym przebiegu. Nie porównujemy z zapamiętanymi liczbami PCIe
z czerwca — mamy kontrolę wewnątrz pomiaru.

```bash
cat > "$NOUT/p2p_bw.py" <<'PYEOF'
import json, torch

PAIRS = [(0, 1), (0, 2), (0, 3), (4, 5), (0, 4), (3, 4)]  # 0..3 wyspa, 0-4/3-4 = kontrola
N = 1 << 28          # 512 MiB w fp16
ITERS, WARMUP = 20, 3
out = []

for src, dst in PAIRS:
    peer_ok = torch.cuda.can_device_access_peer(src, dst)
    a = torch.empty(N, dtype=torch.float16, device=f"cuda:{src}")
    b = torch.empty(N, dtype=torch.float16, device=f"cuda:{dst}")
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
    gbs = ITERS * a.numel() * 2 / 1e9 / (beg.elapsed_time(end) / 1e3)
    out.append({"src": src, "dst": dst, "peer_access": peer_ok,
                "uni_GBps": round(gbs, 1)})
    print(f"GPU{src}->GPU{dst}  peer={peer_ok}  {gbs:7.1f} GB/s", flush=True)
    del a, b
    torch.cuda.empty_cache()

json.dump(out, open("/out/nvlink/p2p_bw.json", "w"), indent=2)
PYEOF

docker run --rm --gpus all --ipc=host --entrypoint bash \
  -v "$PWD/$RUN_DIR:/out" "$IMAGE" \
  -lc 'python3 /out/nvlink/p2p_bw.py' 2>&1 | tee "$NOUT/p2p_bw.txt"
```

**Odczyt:** oczekiwany rozjazd to rząd wielkości — pary w wyspie ~130–160 GB/s,
para kontrolna `0↔4` w okolicach kilkudziesięciu GB/s lub mniej. Jeśli
**wszystkie** pary wyglądają podobnie albo `peer_access=False` w wyspie, to nie
jest zwycięstwo NVLinka tylko wspólna ścieżka hosta.

---

## Cz. 3 — NCCL: busbw w wyspie i kontrola przez wyspy (15 min)

Statusy potrafią kłamać, a vLLM nie robi `copy_` — robi all-reduce przez NCCL.

```bash
cat > "$NOUT/nccl_ar.py" <<'PYEOF'
import os, json, torch, torch.distributed as dist

dist.init_process_group("nccl")
rank, world = dist.get_rank(), dist.get_world_size()
torch.cuda.set_device(rank)
tag = os.environ.get("AR_TAG", "run")
res = {}
for mb in (8, 64, 512):
    x = torch.ones(mb << 19, dtype=torch.float16, device="cuda")  # mb MiB
    for _ in range(5):
        dist.all_reduce(x)
    torch.cuda.synchronize(); dist.barrier()
    beg, end = torch.cuda.Event(True), torch.cuda.Event(True)
    beg.record()
    for _ in range(20):
        dist.all_reduce(x)
    end.record()
    torch.cuda.synchronize()
    sec = beg.elapsed_time(end) / 1e3 / 20
    algbw = x.numel() * 2 / sec / 1e9
    busbw = algbw * 2 * (world - 1) / world
    res[f"{mb}MiB"] = {"algbw_GBps": round(algbw, 1), "busbw_GBps": round(busbw, 1)}
    if rank == 0:
        print(f"{mb:4d} MiB  algbw {algbw:7.1f}  busbw {busbw:7.1f} GB/s", flush=True)
if rank == 0:
    json.dump(res, open(f"/out/nvlink/nccl_allreduce_{tag}.json", "w"), indent=2)
dist.destroy_process_group()
PYEOF

# 3a — cztery ranki w JEDNEJ wyspie
docker run --rm --gpus all --ipc=host --entrypoint bash \
  -e CUDA_VISIBLE_DEVICES=0,1,2,3 -e AR_TAG=island \
  -e NCCL_DEBUG=INFO -e NCCL_DEBUG_SUBSYS=INIT,GRAPH \
  -v "$PWD/$RUN_DIR:/out" "$IMAGE" \
  -lc 'torchrun --nproc_per_node=4 /out/nvlink/nccl_ar.py' 2>&1 \
  | tee "$NOUT/nccl_allreduce_island.txt"

# 3b — KONTROLA 2+2 przez wyspy (nie opcjonalna, patrz odczyt niżej)
docker run --rm --gpus all --ipc=host --entrypoint bash \
  -e CUDA_VISIBLE_DEVICES=0,1,4,5 -e AR_TAG=cross \
  -e NCCL_DEBUG=INFO -e NCCL_DEBUG_SUBSYS=INIT,GRAPH \
  -v "$PWD/$RUN_DIR:/out" "$IMAGE" \
  -lc 'torchrun --nproc_per_node=4 /out/nvlink/nccl_ar.py' 2>&1 \
  | tee "$NOUT/nccl_allreduce_cross.txt"

grep -iE "NVL|nvlink|via |Channel|Trees" "$NOUT/nccl_allreduce_island.txt" \
  | head -40 | tee "$NOUT/nccl_path_island.txt"
grep -iE "NVL|nvlink|via |Channel|Trees" "$NOUT/nccl_allreduce_cross.txt" \
  | head -40 | tee "$NOUT/nccl_path_cross.txt"
```

**Odczyt 3a:** w logu szukaj oznaczenia **`NVL`** w opisie grafu. Samo `via P2P`
**nie rozstrzyga** — P2P działa też po PCIe i tak było w czerwcu. Rozstrzyga
(a) etykieta `NVL`, (b) liczba: sufit PCIe zmierzony w czerwcu to ~7,2–7,9 GB/s,
więc **busbw > 100 GB/s jest dowodem nie do podważenia**, nawet przy
niejednoznacznym logu.

**Odczyt 3b — to jest test `capture 0,75`, nie ozdobnik.** Dwa z czterech
odcinków idą po PCIe, czyli w miniaturze odtwarza to sytuację Kimi TP8:

- **busbw ≈ 7 GB/s** ⇒ NCCL zbudował **płaski ring**, w którym najwolniejszy
  segment kasuje zysk z pozostałych. Wtedy `capture 0,75` jest złym modelem, a
  predykcja 2,7× dla Kimi TP8 traci podstawę **jeszcze przed Cz. 5**.
- **busbw wyraźnie wyżej** ⇒ kolektyw **hierarchiczny** (redukcja w wyspie po
  NVLinku, potem cross-island) i predykcja ma podstawy.

Zanotuj wynik 3b przed Cz. 5 — zmienia to, czego się w Cz. 5 spodziewasz.

---

## Cz. H — funkcje pomocnicze (wklej raz, 2 min)

Wklej **cały blok** do tej samej sesji SSH. Dalsze części z niego korzystają.
Nic tu nie jest skrótem do innego pliku.

```bash
# ── sampler liczników GPU (tier-1 dcgmi, potwierdzony na tym hoście) ─────
# 155  = POWER_USAGE           1002 = PROF_SM_ACTIVE
# 1004 = PROF_PIPE_TENSOR_ACT  1005 = PROF_DRAM_ACTIVE
# 1009 = PROF_PCIE_TX_BYTES    1010 = PROF_PCIE_RX_BYTES
# 1011 = PROF_NVLINK_TX_BYTES  1012 = PROF_NVLINK_RX_BYTES
# Pola NVLink są nowe w tej sesji — sprawdź, czy sterownik je wystawia:
dcgmi dmon -e 155,1002,1004,1005,1009,1010,1011,1012 -d 1000 -c 2 \
  > "$RUN_DIR/session/dcgmi_fields_probe.txt" 2>&1
grep -qi "error\|not supported\|unknown field" "$RUN_DIR/session/dcgmi_fields_probe.txt" \
  && DCGM_FIELDS=155,1002,1004,1005,1009,1010 \
  || DCGM_FIELDS=155,1002,1004,1005,1009,1010,1011,1012
echo "DCGM_FIELDS=$DCGM_FIELDS" | tee "$RUN_DIR/session/dcgm_fields_used.txt"

sample_window () {  # $1=label $2=sekundy(sufit)
  out="$P0OUT/$1"; date +%s > "${out}_start_epoch.txt"
  dcgmi dmon -e "$DCGM_FIELDS" -d 1000 -c "$2" > "${out}_dcgmi.txt" 2>&1
  date +%s > "${out}_end_epoch.txt"
}

start_sample_window () {  # $1=label $2=sekundy(sufit)
  sample_window "$1" "$2" &
  SAMPLE_PID=$!
}

stop_sample_window () {
  # kończy okno RAZEM z benchem: ubija dcgmi (dziecko podpowłoki) zamiast
  # czekać do końca okna — czas okna to tylko sufit; zero próbek idle w ogonie
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

show_bench () {  # $1 = katalog z JSON-ami benchu
  python3 - "$1" <<'PYEOF'
import glob, json, sys
for f in sorted(glob.glob(sys.argv[1] + "/*.json")):
    d = json.load(open(f))
    print(f"{f.split('/')[-1]:28s} out tok/s {d.get('output_throughput', 0):8.1f}"
          f" | ITL med {d.get('median_itl_ms', 0):8.2f}"
          f" | TPOT med {d.get('median_tpot_ms', 0):7.2f}"
          f" | done {d.get('completed', 0)}")
PYEOF
}
```

---

## Cz. 4 — Qwen TP4 w jednej wyspie: test mechanizmu (25 min)

### Dlaczego Qwen — i czego ten pomiar NIE mówi

Qwen TP4 jest **przyrządem pomiarowym, nie scenariuszem produkcyjnym**.

Za: (a) jedyne miejsce z **pre-rejestrowaną predykcją i baseline 1:1**;
(b) predykcja 2,1× została wyprowadzona **z trace'u tego właśnie configu**
(Q4, NCCL 53,3%); (c) TP4 na GPU 0-3 leży **w całości w jednej wyspie** —
najczystszy możliwy test; (d) start ~5 min.

Ograniczenia, które trzeba zapisać razem z wynikiem:

1. **Qwen 35B-A3B mieści się na 1-2 GPU.** Werdykt #50 klasyfikuje TP≥4 dla
   takiego modelu jako *błąd konfiguracji* (wiersz NO-GO). Mierzymy konfigurację,
   której nikt by nie serwował — żeby zwalidować model, nie żeby ją zalecić.
2. **3B aktywnych parametrów + `--enable-expert-parallel`.** Mało obliczeń na
   token względem komunikacji, a EP dokłada all-to-all ponad all-reduce TP.
   Zmierzony zysk to raczej **górne oszacowanie** dla modelu gęstego.
3. **Nie waliduje `capture 0,75` dla TP=8** — od tego jest Cz. 3b i Cz. 5.
4. **`max-num-seqs 32` przy `--max-concurrency 64`** — silnik trzyma ≤32
   requestów w locie. Baseline 06-11 miał to samo, więc porównanie jest ważne,
   ale „c=64" to etykieta workloadu, nie realna głębokość batcha.

### Przebieg

```bash
P0OUT="$QOUT"                                # sample_window pisze tutaj
export QWEN_TP=4
export QWEN_CUDA_VISIBLE_DEVICES=0,1,2,3     # ta sama wyspa co baseline 06-11

# KROK 1 — start silnika
docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 240 5 || echo "START FAILED — nie benchuj"

# KROK 2 — FAIL-FAST verify: runtime musi potwierdzić TP (lekcja 06-11).
#          grep po PEŁNYM logu; tail ucina linię configu przy dłuższych startach.
docker inspect vllm --format '{{json .Config.Cmd}}' > "$QOUT/engine_cmd_tp4.json"
docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | sed -E 's/^(HUGGING_FACE_HUB_TOKEN|HF_TOKEN|[A-Z_]*API_KEY|[A-Z_]*SECRET[A-Z_]*)=.*/\1=REDACTED/' \
  > "$QOUT/engine_env_tp4.txt"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$QOUT/verify_tp4.txt"
grep -q "tensor_parallel_size=4" "$QOUT/verify_tp4.txt" \
  || echo "TP MISMATCH — w logu: '$(cat "$QOUT/verify_tp4.txt")' — PRZERWIJ"
grep '^CUDA_VISIBLE_DEVICES=0,1,2,3$' "$QOUT/engine_env_tp4.txt" \
  || echo "ZŁY PLACEMENT — porównanie z baseline 06-11 nieważne"

# KROK 3 — prereqs w świeżym kontenerze (pip i /tmp nie przeżywają recreate)
docker compose -f "$QWEN_COMPOSE" cp "$SWE" vllm:/tmp/swe_bench_vllm.jsonl
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c \
  'rm -rf /tmp/qbench; mkdir -p /tmp/qbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "import pandas,datasets;print(\"deps ok\")"' \
  || echo "PREREQS FAILED — nie leć dalej"

# KROK 4 — okno c=1 (random 64-in/512-out, ignore-eos)
start_sample_window "qwen_tp4_c1" 600
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name random --random-input-len 64 --random-output-len 512 \
    --ignore-eos --num-warmups 3 --num-prompts 40 --max-concurrency 1 \
    --save-result --result-dir /tmp/qbench --result-filename tp4_c1.json'
stop_sample_window || echo "WARN: sampler c1"

# KROK 5 — okno c=64 (SWE custom, 256-out)
start_sample_window "qwen_tp4_c64" 900
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 256 --ignore-eos --num-prompts 600 --max-concurrency 64 \
    --save-result --result-dir /tmp/qbench --result-filename tp4_c64.json'
stop_sample_window || echo "WARN: sampler c64"

# KROK 6 — ZAWSZE zbierz artefakty (lekcja 06-10: brak cp = bezpowrotna strata)
mkdir -p "$QOUT/bench_tp4"
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/qbench/. "$QOUT/bench_tp4/"
docker logs vllm > "$QOUT/log_qwen_tp4.txt" 2>&1
nvidia-smi > "$QOUT/nvidia_smi_tp4.txt"
# ── ROZSTRZYGACZ dla całej sesji: TP=4 w wyspie to PEŁNA siatka NVLink,
#    więc TU warning o custom all-reduce ma zniknąć. Bez tego odczytu ten sam
#    warning u Kimi (Cz. 5) jest nierozstrzygalny — patrz §1, „Warstwa vLLM".
grep -iE "custom all.?reduce|PCIe-only|multicast|NVSwitch|NVLink|nvls|flashinfer_all_reduce|allreduce_rms" \
  "$QOUT/log_qwen_tp4.txt" | tee "$QOUT/vllm_allreduce_lines.txt" | head -30
CAR_Q=$(grep -c "not supported on more than two PCIe-only GPUs" "$QOUT/vllm_allreduce_lines.txt")
echo "Qwen TP4 custom_all_reduce WARNING: $CAR_Q  (0 = mostki widziane przez vLLM)" \
  | tee "$QOUT/allreduce_gate.txt"

show_bench "$QOUT/bench_tp4"
```

**Odczyt — trzy możliwe wyniki:**

- **~1400 tok/s @c64** → predykcja 2,1× trafiona; TP=4 dogania TP=2 — realna
  zmiana rekomendacji serwowania.
- **~850–1100 tok/s** → kierunek dobry, `share` przeszacowany. Najbardziej
  prawdopodobna przyczyna: czas NCCL zawiera **peer-wait**, którego szybszy link
  nie usuwa (zastrzeżenie 2 werdyktu). To doprecyzowanie modelu, nie porażka.
- **< 850 tok/s** → predykcja obalona. Sprawdź najpierw, czy c=64 nie wpadło w
  patologię schedulera analogiczną do anomalii Kimi c=16 — czy limiterem nie jest
  software zamiast transportu.

---

## Cz. 5 — Kimi TP8 przez dwie wyspy: scenariusz produkcyjny (30 min)

**To jest jednocześnie restore stacku.** Compose Kimi ma TP=8 i Eagle3 zaszyte na
sztywno — czyli dokładnie konfigurację baseline K1 z 06-11. Start silnika trzeba
było wykonać tak czy inaczej; benche są kosztem krańcowym.

`vllm-small` (DeepSeek) **musi zostać wyłączony** przez cały ten etap — dzieli te
same GPU i skaziłby liczniki dcgmi. Wraca dopiero w Cz. 6.

```bash
P0OUT="$KOUT"                                # sample_window pisze tutaj
unset QWEN_TP QWEN_CUDA_VISIBLE_DEVICES      # inaczej wyciekną do compose Kimi

docker compose -f "$QWEN_COMPOSE" down
docker compose -f "$COMPOSE" up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 360 5 || echo "KIMI START FAILED"
# TP=8 + capture cudagraphów potrafi trwać >10 min — stąd 360 prób po 5 s

# verify: TP=8 i Eagle3 obecne (bez tego porównanie z K1 jest nieważne)
docker inspect vllm --format '{{json .Config.Cmd}}' > "$KOUT/engine_cmd_kimi.json"
grep -o 'speculative-config' "$KOUT/engine_cmd_kimi.json" || echo "UWAGA: Kimi bez Eagle3"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$KOUT/verify_kimi.txt"
grep -q "tensor_parallel_size=8" "$KOUT/verify_kimi.txt" || echo "TP MISMATCH — PRZERWIJ"

# ── BRAMKA vLLM: czy silnik w ogóle zobaczył mostki ────────────────────
# Na PCIe (06-08) log Kimi miał 8× WARNING z custom_all_reduce.py:153.
# Nie jest to nasza flaga — compose nie ustawia --disable-custom-all-reduce,
# a engine config raportuje disable_custom_all_reduce=False. vLLM wyłączał to
# SAM, bo topologia była PCIe-only. Po NVLinku warunek przestaje obowiązywać.
docker logs vllm 2>&1 | grep -iE "custom all.?reduce|PCIe-only|multicast|NVSwitch|NVLink|nvls|flashinfer_all_reduce|allreduce_rms" \
  | tee "$KOUT/vllm_allreduce_lines.txt" | head -30

CAR_K=$(grep -c "not supported on more than two PCIe-only GPUs" "$KOUT/vllm_allreduce_lines.txt")
FIR_K=$(grep -c "does not support multicasting" "$KOUT/vllm_allreduce_lines.txt")
CAR_Q=$(grep -c "not supported on more than two PCIe-only GPUs" "$QOUT/vllm_allreduce_lines.txt" 2>/dev/null || echo BRAK)
{ echo "Kimi TP8  custom_all_reduce WARNING: $CAR_K   flashinfer multicast: $FIR_K"
  echo "Qwen TP4  custom_all_reduce WARNING: $CAR_Q   (rozstrzygacz z Cz. 4)"
} | tee "$KOUT/allreduce_gate.txt"
# TP=8 na mostkach 4+4 NIE jest pelna siatka NVLink, wiec warning u Kimi jest
# OCZEKIWANY. Rozstrzyga dopiero zestawienie z Qwenem TP4 (pelna siatka w wyspie).

# prereqs benchu
docker compose -f "$COMPOSE" cp "$SWE" vllm:/tmp/swe_bench_vllm.jsonl
docker compose -f "$COMPOSE" exec vllm bash -c \
  'rm -rf /tmp/kbench; mkdir -p /tmp/kbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "import pandas,datasets;print(\"deps ok\")"' \
  || echo "PREREQS FAILED — nie leć dalej"

kimi_bench_c () {   # $1=concurrency  $2=num_prompts  $3=sufit okna dcgmi (s)
  c="$1"; np="$2"; tag="kimi_c${c}"
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

kimi_bench_c 32 384 1200    # NIETYKALNY — najlepszy punkt pracy, baseline 285 tok/s
kimi_bench_c  1  24  600    # kontrola podłogi, baseline TPOT 8,7 ms
kimi_bench_c 16  96  900    # anomalia, baseline ITL med 512 ms — TNIJ JAKO PIERWSZY

docker logs vllm > "$KOUT/log_kimi.txt" 2>&1
nvidia-smi > "$KOUT/nvidia_smi_kimi.txt"
show_bench "$KOUT/bench"
```

**Kolejność benchy jest celowa** — c=32 idzie pierwszy, bo jest nietykalny; przy
poślizgu tracisz c=16, nie kluczowy pomiar.

**Uwaga do porównania c=16:** baseline K1 miał 192 prompty, tu jest 96 (oszczędność
~6 min). **ITL/TPOT median są porównywalne** (mediana po tysiącach interwałów),
ale `output_throughput` **nie** — mniejszy udział steady-state względem rampy.
Do sprawdzenia anomalii porównuj ITL, nie throughput.

**Odczyt — najpierw bramka vLLM, potem liczby.** `allreduce_gate.txt` czytaj
**zanim** zinterpretujesz cokolwiek innego, i czytaj go **parą** Qwen+Kimi
(pełna tabela decyzyjna w §1, „Warstwa vLLM"):

| Qwen TP4 | Kimi TP8 | co to znaczy dla Cz. 5 |
|---|---|---|
| znika | zostaje | **norma dla 4+4.** Mostki działają; TP=8 nie dostaje kernela custom AR, bo siatka niepełna. Liczby są o NVLinku przez NCCL — czytaj dalej |
| zostaje | zostaje | **awaria** — vLLM nie widzi mostków. Wyniki Cz. 5 nie są o NVLinku, wróć do Cz. 1 |
| znika | znika | vLLM uznał TP8 za pełną siatkę wbrew modelowi — zanotuj, zysk może być wyższy niż predykcja |

Sam warning u Kimi **nie jest** dowodem awarii — przy 4+4 jest oczekiwany.
Warning FlashInfera o multicaście ma zostać w obu przypadkach.

Dopiero potem liczby:

- **c=32 ~770 tok/s** → predykcja 2,7× trafiona, `capture 0,75` się broni, zakup
  uzasadniony w scenariuszu, dla którego był robiony.
- **c=32 400–600 tok/s** → zysk realny, ale `capture` niższy niż 0,75. Zestaw z
  busbw z Cz. 3b — jeśli tam wyszedł płaski ring, to jest spójna historia.
- **c=32 ≈ 285 tok/s (bez zmian)** → NCCL nie używa mostków przy 8 rankach.
  Sprawdź `vllm_allreduce_lines.txt` i liczniki PCIe RX: jeśli RX dalej siedzi na
  suficie 7,2–7,9 GB/s, ruch w ogóle nie przeszedł na NVLink.
- **c=16 dalej ~512 ms ITL** → potwierdza diagnozę „patologia schedulera", bo
  zmiana transportu jej nie ruszyła. To wynik pozytywny dla tezy z werdyktu.

Szybki odczyt liczników bez czekania na analizę laptopową:

```bash
for f in "$KOUT"/kimi_c*_dcgmi.txt; do
  echo "== $f"; awk 'NR>2 && NF>6 {p+=$3; rx+=$8; n++} END {if(n) printf "  srednia moc %.0f W | PCIE_RX %.2f | probek %d\n", p/n, rx/n, n}' "$f"
done
```

Kolumny `dcgmi dmon` zależą od `$DCGM_FIELDS` — jeśli powyższy `awk` pokaże
bzdury, obejrzyj nagłówek pliku i popraw numery kolumn. **Nie zgaduj — to
2 sekundy `head -3`.**

---

## Cz. 6 — liczniki błędów, domknięcie stacku, commit (10 min)

Liczniki mają sens tylko wtedy, gdy obejmują realny ruch — dlatego czytamy je
**po** Cz. 2–5, a nie zaraz po włożeniu mostków.

```bash
nvidia-smi nvlink -e > "$NOUT/nvlink_errors_after.txt" 2>&1
diff "$NOUT/nvlink_errors_before.txt" "$NOUT/nvlink_errors_after.txt" \
  > "$NOUT/nvlink_errors_delta.txt" 2>&1
nvidia-smi topo -m > "$NOUT/topo_m_after.txt"     # topologia nie powinna się ruszyć
dmesg | grep -i "nvlink\|nvrm" | tail -40 > "$RUN_DIR/session/dmesg_end.txt"
```

**Odczyt:** rosnące `Replay` / `Recovery` / CRC = link marginalny, najczęściej
niedociśnięty mostek. Zero przyrostu po kilkuset GB przepchniętych w Cz. 2–5 to
mocny sygnał poprawnego montażu. **Pusty `nvlink_errors_delta.txt` = wynik
pozytywny** — zapisz to jawnie w notatkach, żeby nie wyglądał jak brak pomiaru.

Domknięcie stacku (Kimi już stoi z Cz. 5 — dostawiamy resztę):

```bash
docker compose -f "$COMPOSE" up -d vllm-small litellm open-webui
wait_http_health http://127.0.0.1:8004/health 240 5 && echo "deepseek OK"
curl -fsS http://127.0.0.1:8000/health && echo "kimi OK"
docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/restore_ps.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
git rev-parse HEAD > "$RUN_DIR/session/end_commit.txt"
```

Commit (artefakty są małe — tekst/JSON; polityka wyników w `CLAUDE.md`):

```bash
git status
du -sh "$RUN_DIR"
find "$RUN_DIR" -name 'engine_env_*' -exec grep -l "HUGGING_FACE_HUB_TOKEN=hf_" {} \; \
  && echo "STOP: token w artefaktach — popraw redakcję przed commitem"
git add "$RUN_DIR"
git commit -m "bench: weryfikacja instalacji NVLink 4-way - topologia, P2P, NCCL, Qwen TP4, Kimi TP8"
git push -u origin main
```

---

## Gdy nic nie widać (checklista awaryjna)

Kolejność od najtańszego:

1. **`dmesg | grep -i nvlink` i `| grep -i nvrm`** — błędy trenowania linku
   pojawiają się tam, nie w `nvidia-smi`.
2. **Rozstaw slotów.** H200 NVL wspiera konkretne konfiguracje mostków;
   mechaniczne wejście nie oznacza elektrycznego połączenia. Sprawdź, czy
   zmostkowane pary odpowiadają fizycznym parom kart, nie tylko numerom w
   `nvidia-smi` — mapowanie przez `pci.bus_id` z `gpu_inventory.csv` (znane pary
   za switchami: `1D/1E`, `40/41`, `AA/AB`, `BB/BC`).
3. **Zimny start, nie warm reboot.** Trenowanie linku po zmianie topologii bywa
   wykonywane tylko przy pełnym cyklu zasilania.

Negatywny wynik też commituj — „mostki włożone, topologia się nie zmieniła, oto
`dmesg`" to pełnoprawny artefakt diagnostyczny i oszczędza następną sesję.

---

## Po sesji (laptop, poza slotem)

1. **`docs/operations/infrastructure.md` §2.2** — wklej macierz `topo -m`. Sekcja
   ma jawne TODO „po zebraniu wkleić macierz do tej sekcji", a zdanie
   *„Interconnect GPU↔GPU: wyłącznie PCIe — brak NVLink"* przestaje być prawdą i
   musi zostać przepisane wraz z datą zmiany.
2. **Issue #50** — komentarz z tabelą predykcja vs pomiar (osobno Qwen TP4 i Kimi
   TP8). Issue może zostać zamknięte dopiero po tym porównaniu, nie po zakupie.
3. **`docs/writeups/w1/t9-bottleneck-nvlink.md`** — sekcja „pomiar po
   interwencji". T9 jest zapisem decyzji; walidacja predykcji na interwencji to
   najmocniejszy materiał, jaki ten wątek może dostać.
4. **`docs/writeups/w1/nvlink-4way-notatka-decyzyjna.md`** — dopisek, czy decyzja
   się obroniła.
5. **`docs/operations/agent-state.md`** — `sync-state`.

## Wątki otwarte po tej sesji (nie dziś)

- **Rozdzielenie dawki:** jawne `--disable-custom-all-reduce` w komendzie silnika
  **przy włożonych mostkach** — ile z zysku to sam link, a ile kernel custom
  all-reduce, który vLLM na PCIe wyłączał automatycznie. Jedna dawka, jeden bench
  c=32, ~20 min. Bez tego zysk z Cz. 5 jest wielkością pakietową.
- **Trace Kimi TP8 @c=32 po NVLinku** — udział NCCL powinien spaść z 83,9%; to
  domknęłoby rachunek `share × capture` od strony mechanizmu, a nie tylko wyniku.
  Wymaga `--profiler-config` (w vLLM v0.20 `VLLM_TORCH_PROFILER_DIR` już nie działa).
- **Kimi c=32 vs c=16** — jeśli anomalia przeżyła NVLink, warto ją wreszcie
  zdiagnozować od strony schedulera (`max-num-seqs` vs `max-concurrency`).
- **`NCCL_NVLS_ENABLE=1` w compose Qwena — prawie na pewno martwy zapis.** NVLS
  (NVLink SHARP) opiera się na multicaście, a log vLLM z 06-08 mówi wprost, że
  „NVLink bridge-only" go nie ma. Do sprawdzenia przy okazji i ewentualnego
  usunięcia z compose, żeby nie sugerował działającej funkcji.

---

## Walidacja planu

```text
git diff --check    (docs-only; skrypty są heredocami wewnątrz planu)
```
