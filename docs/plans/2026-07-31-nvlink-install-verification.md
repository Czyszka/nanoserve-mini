# Sesja serwerowa 2026-07-31 — weryfikacja instalacji NVLink 4-way

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL)
**Slot:** krótki, 1–2 h. Restarty silników dozwolone.
**Konfiguracja sprzętowa (deklarowana):** mostki **4-way, dwie wyspy** —
GPU 0-1-2-3 oraz GPU 4-5-6-7.
**Kontekst:** issue #50, werdykt `results/summaries/2026-06-11-nvlink-boundary-verdict.md`,
wątek `docs/writeups/w1/t9-bottleneck-nvlink.md`, notatka decyzyjna
`docs/writeups/w1/nvlink-4way-notatka-decyzyjna.md`.

---

## 0. Po co ta sesja

Dwa cele, w tej kolejności:

1. **Czy NVLink faktycznie działa** — sterownik widzi linki, topologia się
   zmieniła, brak narastających błędów, surowa przepustowość rośnie o rząd
   wielkości względem PCIe.
2. **Czy werdykt #50 się potwierdza.** Cała decyzja zakupowa stała na
   **predykcjach z modelu** `gain = 1/(1 − share × capture)`, wyliczonych na
   PCIe. Teraz mostki są w środku, więc predykcje są **falsyfikowalne**. To
   rzadka okazja: pre-rejestrowana predykcja + pomiar po interwencji. Jeśli
   dziś nie zmierzymy TP=4, zostanie tylko „kupiliśmy i chyba jest szybciej".

Cel 2 kosztuje ~25 min i używa gotowego `run_qwen_tp` z poprzednich sesji.
Nie odpuszczaj go, jeśli Cz. 1 przejdzie.

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

Baseline PCIe pochodzi z `results/runs/2026-06-11_nvlink_boundary/` (Q3 intra,
GPU 0-3) i `results/summaries/2026-06-11-qwen-tp-curve.md`.

| pomiar | baseline PCIe (06-11) | predykcja #50 | falsyfikacja |
|---|---:|---|---|
| P2P uni GPU0↔GPU1 (ta sama wyspa) | ~25–50 GB/s (PCIe sw.) | **> 100 GB/s** | < 60 GB/s → mostek nie działa lub siedzi krzywo |
| P2P uni GPU0↔GPU4 (**kontrola**, cross-island) | PCIe/UPI | **bez zmian** | wzrost → moja mapa wysp jest zła |
| NCCL all_reduce busbw, 4 ranki 0-3 | sufit ~7,2–7,9 GB/s (transport) | **> 100 GB/s** | < 30 GB/s → NCCL nie wybrał NVLinka |
| Qwen TP4 intra c=64, out tok/s | **680** | **~1430** (share 0,533 × capture 1,0 ⇒ 2,1×) | < 850 tok/s → model share×capture zawyżony |
| Qwen TP4 intra c=64, ITL med | **53,7 ms** | **~26 ms** | > 45 ms → jw. |
| Qwen TP4 intra c=1, ITL med | **10,54 ms** | **9–10,5 ms** (podłoga rządzi) | < 8 ms → teza „c=1 floor-bound" upada |
| Qwen TP4 intra c=1, TPOT med | **4,00 ms** | **≥ 3,4 ms** | jw. |

Punkt odniesienia dla decyzji serwowania: **TP2 na PCIe dawał 1404 tok/s @c64.**
Jeśli TP4+NVLink dobije do ~1400, TP4 przestaje być karą — to jest realna
konsekwencja operacyjna, nie ciekawostka.

**Uwaga o czystości dawki (zapisz w notatkach, nie ignoruj):** włożenie mostków
zmienia jednocześnie dwie rzeczy — (a) klasę linku, (b) **kwalifikowalność
custom all-reduce w vLLM**, który na PCIe był wyłączany komunikatem *„not
supported on more than two PCIe-only GPUs"* (`kimi_log_eagle3_on.txt:67`). Zysk
zmierzony dziś jest zyskiem **pakietu** „NVLink + odblokowany custom AR", nie
czystego linku. Rozdzielenie tego wymagałoby osobnej dawki
(`VLLM_DISABLE_CUSTOM_ALL_REDUCE=1` przy włożonych mostkach) — **poza dzisiejszym
slotem**, ale zanotuj jako otwarty wątek.

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. 0 | stan wyjściowy + zwolnienie GPU | 5 |
| Cz. 1 | **BRAMKA:** czy sterownik widzi linki + topologia | 10 |
| Cz. 2 | surowa przepustowość P2P (z kontrolą cross-island) | 15 |
| Cz. 3 | dowód ścieżki NCCL (all_reduce busbw) | 15 |
| Cz. 4 | **punkt kontrolny predykcji:** Qwen TP4 intra c=1 + c=64 | 25 |
| Cz. 5 | liczniki błędów po obciążeniu + restore + commit | 15 |
| | **razem** | **85** |

**Kolejność cięcia przy poślizgu:** Cz. 3 → Cz. 4 (c=1) → Cz. 2 (pary dalsze).
Nietykalne: **Cz. 0, Cz. 1, Cz. 4 (c=64), Cz. 5**.

Uzasadnienie cięcia Cz. 3 jako pierwszej: Cz. 4 i tak zostawia w logu vLLM ślad,
jakiego transportu użył NCCL — dowód ścieżki jest wtedy wtórny, choć słabszy.

---

## Cz. 0 — start i stan wyjściowy (5 min)

Migawka „przed": commit, stan kart, mapowanie numerów GPU na bus-ID (potrzebne,
gdyby trzeba było wrócić do fizycznych slotów), `dmesg` po zmianie topologii.

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main
# BEZ set -euo pipefail; BEZ exit — sesja interaktywna po SSH

RUN_DIR=results/runs/2026-07-31_nvlink_install
NOUT="$RUN_DIR/nvlink"; QOUT="$RUN_DIR/qwen"
mkdir -p "$NOUT" "$QOUT" "$RUN_DIR/session"
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

**Zwolnij GPU na resztę sesji:**

```bash
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
QWEN_COMPOSE="serving/compose/docker-compose.qwen3.6.yml"
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

# migawka liczników błędów PRZED obciążeniem (delta > reset — nie zależy od
# tego, czy ta wersja nvidia-smi w ogóle wspiera reset liczników)
nvidia-smi nvlink -e > "$NOUT/nvlink_errors_before.txt" 2>&1
```

**Jak to czytać — trzy warunki, wszystkie muszą być spełnione:**

1. **`topo_m.txt`:** każda z **sześciu** par wewnątrz wyspy 0-3 (`0↔1, 0↔2, 0↔3,
   1↔2, 1↔3, 2↔3`) pokazuje `NV<n>`, i analogicznie sześć par w 4-7. Jeżeli
   `NV` widać tylko dla par sąsiednich (`0↔1`, `2↔3`), to mostek pracuje jak
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
15 min i zależność od sieci. Kontener vLLM ma torch i NCCL; to wystarcza.

Kluczowy element metodyczny: **para kontrolna `0↔4`** mierzona tym samym
skryptem, w tym samym przebiegu. Dzięki temu nie porównujemy z zapamiętanymi
liczbami PCIe z czerwca, tylko mamy kontrolę wewnątrz pomiaru.

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
  -v "$PWD/$RUN_DIR:/out" vllm/vllm-openai:v0.20.0-cu130-ubuntu2404 \
  -lc 'python3 /out/nvlink/p2p_bw.py' 2>&1 | tee "$NOUT/p2p_bw.txt"
```

**Odczyt:** oczekiwany rozjazd to rząd wielkości — pary w wyspie ~130–160 GB/s,
para kontrolna `0↔4` w okolicach kilkudziesięciu GB/s (PCIe 5.0 x16) lub mniej.
Jeśli **wszystkie** pary wyglądają podobnie, albo `peer_access=False` w wyspie,
to nie jest zwycięstwo NVLinka tylko wspólna ścieżka hosta.

---

## Cz. 3 — dowód ścieżki NCCL (15 min)

Statusy potrafią kłamać, a vLLM nie robi `copy_` — robi all-reduce przez NCCL.
To jest test docelowy.

```bash
cat > "$NOUT/nccl_ar.py" <<'PYEOF'
import os, json, torch, torch.distributed as dist

dist.init_process_group("nccl")
rank, world = dist.get_rank(), dist.get_world_size()
torch.cuda.set_device(rank)
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
    nbytes = x.numel() * 2
    algbw = nbytes / sec / 1e9
    res[f"{mb}MiB"] = {"algbw_GBps": round(algbw, 1),
                       "busbw_GBps": round(algbw * 2 * (world - 1) / world, 1)}
    if rank == 0:
        print(f"{mb:4d} MiB  algbw {algbw:7.1f}  busbw "
              f"{algbw * 2 * (world - 1) / world:7.1f} GB/s", flush=True)
if rank == 0:
    json.dump(res, open("/out/nvlink/nccl_allreduce.json", "w"), indent=2)
dist.destroy_process_group()
PYEOF

docker run --rm --gpus all --ipc=host --entrypoint bash \
  -e CUDA_VISIBLE_DEVICES=0,1,2,3 -e NCCL_DEBUG=INFO -e NCCL_DEBUG_SUBSYS=INIT,GRAPH \
  -v "$PWD/$RUN_DIR:/out" vllm/vllm-openai:v0.20.0-cu130-ubuntu2404 \
  -lc 'torchrun --nproc_per_node=4 /out/nvlink/nccl_ar.py' 2>&1 \
  | tee "$NOUT/nccl_allreduce_island0.txt"

grep -iE "NVL|nvlink|P2P/|via " "$NOUT/nccl_allreduce_island0.txt" \
  | head -40 | tee "$NOUT/nccl_path_grep.txt"
```

**Odczyt:** w logu `NCCL_DEBUG` szukaj oznaczenia **`NVL`** w opisie kanałów /
grafu. Uwaga: samo `via P2P` **nie rozstrzyga** — P2P działa też po PCIe i tak
było w czerwcu. Rozstrzyga (a) etykieta `NVL` w grafie, (b) liczba `busbw`:
sufit PCIe zmierzony w czerwcu to ~7,2–7,9 GB/s transportu, więc **busbw > 100
GB/s jest dowodem nie do podważenia**, nawet gdyby log był niejednoznaczny.

Opcjonalnie, jeśli zostaje minuta — ten sam przebieg na `CUDA_VISIBLE_DEVICES=0,1,4,5`
(2+2 przez wyspy) jako kontrola: busbw powinien spaść do poziomu PCIe.

---

## Cz. 4 — punkt kontrolny predykcji #50: Qwen TP4 w jednej wyspie (25 min)

Wklej z `docs/plans/2026-06-10-bottleneck-followup-session.md`: `sample_window`,
`wait_http_health`, `start_sample_window`, `stop_sample_window` (Cz. 0) oraz
`run_qwen_tp` (Cz. A). Potem:

```bash
P0OUT="$QOUT"                       # sample_window / run_qwen_tp piszą tutaj
export QWEN_CUDA_VISIBLE_DEVICES=0,1,2,3     # ta sama wyspa co baseline 06-11 (intra)
run_qwen_tp 4 _nvlink
unset QWEN_CUDA_VISIBLE_DEVICES

# darmowy dowód z silnika: czy vLLM odblokował custom all-reduce
grep -iE "custom all.?reduce|PCIe-only|NVLink|nvls" "$QOUT/log_qwen_tp4_nvlink.txt" \
  | head -20 | tee "$QOUT/vllm_allreduce_lines.txt"
```

`run_qwen_tp` sam robi fail-fast verify na `tensor_parallel_size=4` i zbiera
`engine_cmd_*`, `engine_env_*` (z redakcją sekretów), liczniki dcgmi oraz oba
benche. **Nie modyfikuj workloadu** — porównanie z 06-11 jest ważne tylko przy
identycznym benchu (c=1: random 64/512, 40 promptów; c=64: SWE custom, 256-out,
600 promptów).

**Odczyt na żywo, zanim wstaniesz od terminala:**

```bash
python3 - <<'EOF'
import json, glob
for f in sorted(glob.glob("results/runs/2026-07-31_nvlink_install/qwen/bench_tp4_nvlink/*.json")):
    d = json.load(open(f))
    print(f.split("/")[-1], "| out tok/s", round(d.get("output_throughput", 0), 1),
          "| ITL med", round(d.get("median_itl_ms", 0), 2),
          "| TPOT med", round(d.get("median_tpot_ms", 0), 2))
EOF
```

Porównaj z tabelą predykcji z sekcji 1. **Trzy możliwe wyniki i co każdy znaczy:**

- **~1400 tok/s @c64** → predykcja 2,1× trafiona; model `share × capture`
  zwalidowany na interwencji; TP=4 dogania TP=2 — realna zmiana rekomendacji
  serwowania.
- **~850–1100 tok/s** → kierunek dobry, `share` przeszacowany. Najbardziej
  prawdopodobna przyczyna: czas NCCL zawiera **peer-wait**, którego szybszy link
  nie usuwa (zastrzeżenie 2 werdyktu). To wynik, nie porażka — doprecyzowuje model.
- **< 850 tok/s** → predykcja obalona. Wtedy sprawdź najpierw, czy c=64 nie
  wpadło w patologię schedulera analogiczną do anomalii Kimi c=16
  (`max-num-seqs 32` vs `--max-concurrency 64`) — czyli czy limiterem nie jest
  software, a nie transport.

Jeśli zostaje czas: powtórz sam bench c=64 drugi raz (bez restartu silnika),
żeby mieć pasmo szumu. W czerwcu trzy niezależne starty TP2 dały ±0,4 ms na
kroku c=1 — bez powtórki nie wiadomo, czy różnica mieści się w szumie.

---

## Cz. 5 — liczniki błędów po obciążeniu, restore, commit (15 min)

Liczniki mają sens tylko wtedy, gdy obejmują realny ruch — dlatego czytamy je
**po** Cz. 2–4, a nie zaraz po włożeniu mostków.

```bash
nvidia-smi nvlink -e > "$NOUT/nvlink_errors_after.txt" 2>&1
diff "$NOUT/nvlink_errors_before.txt" "$NOUT/nvlink_errors_after.txt" \
  > "$NOUT/nvlink_errors_delta.txt" 2>&1
nvidia-smi topo -m > "$NOUT/topo_m_after.txt"     # topologia nie powinna się ruszyć
dmesg | grep -i "nvlink\|nvrm" | tail -40 > "$RUN_DIR/session/dmesg_end.txt"
```

**Odczyt:** rosnące `Replay` / `Recovery` / CRC = link marginalny, najczęściej
niedociśnięty mostek. Zero przyrostu przy kilkuset GB przepchniętych w Cz. 2–4
to mocny sygnał poprawnego montażu. **Pusty `nvlink_errors_delta.txt` = wynik
pozytywny** — zapisz go jawnie w notatkach, żeby nie wyglądał jak brak pomiaru.

Restore:

```bash
unset QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_COMPOSE
docker compose -f "$QWEN_COMPOSE" down
docker compose -f "$COMPOSE" up -d --force-recreate vllm vllm-small litellm open-webui
wait_http_health http://127.0.0.1:8000/health 240 5 && echo "kimi OK"
wait_http_health http://127.0.0.1:8004/health 240 5 && echo "deepseek OK"
docker inspect vllm --format '{{json .Config.Cmd}}' > "$RUN_DIR/session/restore_engine_cmd.json"
grep -o 'speculative-config' "$RUN_DIR/session/restore_engine_cmd.json" || echo "UWAGA: Kimi bez Eagle3"
# darmowa obserwacja: czy Kimi TP8 też zmienił komunikat o custom all-reduce
docker logs vllm 2>&1 | grep -iE "custom all.?reduce|PCIe-only|NVLink" | head \
  | tee "$RUN_DIR/session/kimi_allreduce_lines.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
```

Commit (artefakty są małe — tekst/JSON; polityka wyników w `CLAUDE.md`):

```bash
git status
du -sh "$RUN_DIR"
git add "$RUN_DIR" && git commit -m "bench: weryfikacja instalacji NVLink 4-way — topologia, P2P, NCCL, Qwen TP4"
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
   `nvidia-smi` — mapowanie robisz przez `pci.bus_id` z `gpu_inventory.csv`
   (znane pary za switchami: `1D/1E`, `40/41`, `AA/AB`, `BB/BC`).
3. **Zimny start, nie warm reboot.** Trenowanie linku po zmianie topologii
   bywa wykonywane tylko przy pełnym cyklu zasilania.

Negatywny wynik też commituj — „mostki włożone, topologia się nie zmieniła, oto
`dmesg`" to pełnoprawny artefakt diagnostyczny i oszczędza następną sesję.

---

## Po sesji (laptop, poza slotem)

1. **`docs/operations/infrastructure.md` §2.2** — wklej macierz `topo -m`.
   Sekcja od 2026-06-10 ma jawne TODO „po zebraniu wkleić macierz do tej
   sekcji", a zdanie *„Interconnect GPU↔GPU: wyłącznie PCIe — brak NVLink"*
   przestaje być prawdą i musi zostać przepisane wraz z datą zmiany.
2. **Issue #50** — komentarz z tabelą predykcja vs pomiar. Issue może zostać
   zamknięte dopiero po tym porównaniu, nie po samym zakupie.
3. **`docs/writeups/w1/t9-bottleneck-nvlink.md`** — nowa sekcja „pomiar po
   interwencji". T9 jest zapisem decyzji; walidacja predykcji na interwencji to
   najmocniejszy materiał, jaki ten wątek może dostać.
4. **`docs/writeups/w1/nvlink-4way-notatka-decyzyjna.md`** — dopisek, czy
   decyzja się obroniła.
5. **`docs/operations/agent-state.md`** — `sync-state`.

## Wątki otwarte po tej sesji (nie dziś)

- Rozdzielenie dawki: `VLLM_DISABLE_CUSTOM_ALL_REDUCE=1` przy włożonych
  mostkach — ile z zysku to link, a ile odblokowany custom AR.
- Kimi TP8 batched (predykcja ~2,7×, capture 0,75) — wymaga dłuższego slotu,
  bo TP8 to load + capture cudagraphów > 10 min.
- Anomalia Kimi c=16: czy NVLink ją usuwa, czy zostaje (jeśli zostaje —
  potwierdza diagnozę „patologia software'owa").
- Czy `NCCL_NVLS_ENABLE=1` (już w compose Qwena) cokolwiek zmienia bez NVSwitcha.

---

## Walidacja planu

```text
git diff --check    (docs-only; bez .py w repo — skrypty są heredocami w planie)
```
