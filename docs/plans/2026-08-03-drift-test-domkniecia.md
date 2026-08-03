# Sesja serwerowa 2026-08-03 (dogrywka) — test dryfu TP4-AR + domknięcia

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, NVLink 4-way: wyspy GPU 0-3 / 4-7)
**Slot (założenie):** ~50 min. Restart Qwena + restore Kimi wliczone.
**Kontekst:** issue #50, #51; sesje `2026-08-03_nvlink_gap_fill` (rano) i
`2026-08-03_kimi_trace_nvlink` (trace, commit `ed7c9ce`); analiza rozbieżności
replikacji z rozmowy 08-03.

> **Plan samowystarczalny** — wszystkie komendy inline.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH.

---

## 0. Po co ta dogrywka

Sesja trace'owa dowiozła główny cel (NCCL share 83,9% → **61,1%** spanu,
kontrola narzutu ±9% — mechanizm #50 domknięty), ale odsłoniła problem:

**Replikacja Qwen TP4-AR c64 NIE wyszła: 1747 tok/s vs 2022/1989 z 07-31
(−13,6%), przy bitowo identycznych `engine_cmd` i `engine_env`.** Jednocześnie
dzisiejszy AR (1747) = poranny noAR (1748), czyli:

- same-day A/B mówi: dawka kernela custom-AR przy c64 ≈ **1,00× (zero)**;
- dekompozycja z gap-fillu („link 2,57× × kernel 1,16×") była cross-day —
  ten 1,16× to najpewniej **dryf między sesjami ~13%**, nie kernel;
- każdy dzień jest wewnętrznie spójny (07-31: 2022+1989; 08-03: 1748+1747) —
  skok jest między dniami; strata siedzi w prefillu/ogonie (TTFT +10%,
  mean ITL +8%), nie w steady-state (ITL med +2,7%).

**Jedyna znana różnica pomiarowa między dniami:** okna dcgmi 08-03 mają
dodatkowo pola PROF 1011/1012 (NVLTX/NVLRX); 07-31 ich nie miało. Liczniki
profilingowe potrafią kosztować. Test: bieg c64 **bez żadnego okna dcgmi**
(B1) + bieg ze **starym zestawem pól** jak 07-31 (B2) rozstrzyga trójstronnie.

Do tego trzy domknięcia bez dotykania silników (blok A):

1. **dmesg (#51 pkt 2)** — plik `dmesg_end.txt` z gap-fillu nadal 0 bajtów.
2. **Naprawa `trace_summary_c32_rank_last.txt`** — `find | sort | tail -1`
   złapał `vllm_1.async_llm...` (proces API, sam `python_function`, stąd
   absurdalne gaps −3322%) zamiast pliku `...rank7...`. Trace'y leżą lokalnie
   w `/home/ubuntusrv2/working/nanoserve-tracing/kimi_c32_nvlink_2026-08-03`.
3. **Trace'y c16 (Cz. 4b)** — sprawdzić, czy kopia do `$TRACE_DIR/c16`
   istnieje; kontener był recreate'owany przy restore, więc `/tmp/vllm_profile`
   w kontenerze już NIE istnieje — brak kopii = strata (zanotować jawnie).

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

| pomiar | odniesienie | predykcja / odczyt |
|---|---|---|
| **B1**: TP4-AR c64 **bez dcgmi** | 1747 (z pełnym oknem, dziś) / 2022 (07-31, stare pola) | **≈2000 → winne okno dcgmi** (pomiar zaburzał pomiar; wszystkie okna 08-03 do adnotacji) · **≈1750 → dryf dnia** (sampler niewinny, 1,16× „kernela" to dryf) |
| **B2**: TP4-AR c64, dcgmi **stare pola** (155,1002,1004,1005,1009,1010) | jak wyżej | B1≈2000 i B2≈2000 → koszt siedzi w polach **NVL 1011/1012** · B1≈2000 i B2≈1750 → koszt w samym samplerze (ale 07-31 przeczy — wtedy sampler biegł przy 2022; sprzeczność → dryf) · B1≈B2≈1750 → dryf dnia potwierdzony podwójnie |
| **B3**: TP4-AR c1 TPOT med | 3,21 (AR 07-31) / 3,58 (noAR 08-03 rano) | **≈3,2 → kernel realny w reżimie latencji** (wniosek c1 z gap-fillu się broni) · **≈3,6 → efekt c1 też był dryfem**, kernel ≈ 0 wszędzie |
| A1 dmesg | 07-31 `dmesg_nvrm.txt` miał wpisy bootowe | plik niepusty albo jawna notatka „bufor nie sięga boota"; **zero Xid** (jakikolwiek Xid → do #51) |
| A2 rank7 summary | rank0: comms 61,1% / compute 30,2% / gaps ~0% | comms w granicach **±10 p.p. rank0** (symetria ranków); duża asymetria → notatka do analizy |

**Nie zmieniaj env vs biegi poranne** — `NCCL_NVLS_ENABLE=1` zostaje w compose
do końca dnia (usunięcie = praca laptopowa PO sesjach, inaczej psujemy
porównywalność B1/B2 z rankiem).

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. A | dmesg + naprawa rank7 + kontrola traców c16 (bez restartów) | 10 |
| Cz. B | Qwen TP4-AR: B1 (bez dcgmi) → B2 (stare pola) → B3 (c1) | 30 |
| Cz. C | restore Kimi + stack, snapshoty, commit | 12 |
| | **razem** | **52** |

**Kolejność cięcia:** B3 → B2 → A3 (kontrola c16).
**Nietykalne:** A1, A2, **B1** (rozstrzyga dryf), Cz. C.

---

## Cz. A — domknięcia bez restartów (10 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main
RUN_DIR=results/runs/2026-08-03_kimi_trace_nvlink
PROF=$RUN_DIR/profile
QOUT=$RUN_DIR/qwen
TRACE_DIR=/home/ubuntusrv2/working/nanoserve-tracing/kimi_c32_nvlink_2026-08-03
COMPOSE=serving/compose/docker-compose.kimi-k2.6.yml
QWEN_COMPOSE=serving/compose/docker-compose.qwen3.6.yml
SWE=results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl
set -a; source .env; set +a

# A1 — dmesg (#51 pkt 2):
sudo dmesg -T | grep -iE "nvlink|nvrm|xid" | tail -60 \
  > results/runs/2026-08-03_nvlink_gap_fill/session/dmesg_end.txt
wc -l results/runs/2026-08-03_nvlink_gap_fill/session/dmesg_end.txt   # >0 oczekiwane
grep -i "xid" results/runs/2026-08-03_nvlink_gap_fill/session/dmesg_end.txt \
  && echo "UWAGA: Xid — wpisz do #51" || echo "zero Xid — OK"

# A2 — NAPRAWA summary rank_last (celujemy JAWNIE w plik rank7, nie tail -1):
T7=$(find "$TRACE_DIR" -maxdepth 1 -name '*rank7*.pt.trace.json.gz' | head -1)
echo "rank7: ${T7:-NOT FOUND — popraw TRACE_DIR}"
[ -n "$T7" ] && uv run python - "$T7" <<'PYEOF' | tee "$PROF/trace_summary_c32_rank_last.txt"
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

# A3 — czy trace'y c16 (Cz. 4b) przeżyły? /tmp/vllm_profile w kontenerze już
# NIE istnieje (recreate przy restore) — brak kopii = strata, zanotuj jawnie:
if ls "$TRACE_DIR/c16"/*.json.gz >/dev/null 2>&1; then
  T16=$(find "$TRACE_DIR/c16" -name '*rank0*.pt.trace.json.gz' | sort | tail -1)
  echo "c16 rank0: $T16"
  # summary jak w A2, tee do "$PROF/trace_summary_c16_rank0.txt"
else
  echo "c16 traces STRACONE (brak kopii przed recreate)" \
    | tee "$PROF/trace_c16_status.txt"
fi
```

---

## Cz. B — test dryfu: Qwen TP4-AR (30 min)

Identyczna konfiguracja jak rano i jak 07-31 (TP4, GPU 0-3, custom AR w auto).
Trzy biegi różnią się WYŁĄCZNIE obecnością/zestawem pól okna dcgmi + jeden c1.

```bash
docker compose -f "$COMPOSE" stop vllm vllm-small litellm open-webui
docker compose -f "$COMPOSE" rm -f vllm 2>/dev/null || true
export QWEN_TP=4
export QWEN_CUDA_VISIBLE_DEVICES=0,1,2,3
unset QWEN_EXTRA_ARGS                        # custom AR w auto → AKTYWNY

docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm
for _ in $(seq 1 240); do curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 5; done
curl -fsS http://127.0.0.1:8000/health || echo "START FAILED — nie benchuj"

# FAIL-FAST verify (lekcja 06-11):
docker inspect vllm --format '{{json .Config.Cmd}}' > "$QOUT/engine_cmd_drift.json"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$QOUT/verify_drift.txt"
grep -q "tensor_parallel_size=4" "$QOUT/verify_drift.txt" || echo "TP MISMATCH — PRZERWIJ"
docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep '^CUDA_VISIBLE_DEVICES=0,1,2,3$' || echo "ZŁY PLACEMENT — PRZERWIJ"
CAR_REG=$(docker logs vllm 2>&1 | grep -c "custom_all_reduce.py.*Registering" || true)
echo "custom AR registering lines: $CAR_REG (oczekiwane >0)" | tee "$QOUT/allreduce_gate_drift.txt"

# prereqs (świeży kontener):
docker cp "$SWE" vllm:/tmp/swe_bench_vllm.jsonl
n=$(docker exec vllm sh -c 'wc -l < /tmp/swe_bench_vllm.jsonl' | tr -d ' '); echo "dataset: $n linii"
[ "${n:-0}" -gt 100 ] || echo "STOP: dataset nie dotarł — NIE benchuj"
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c \
  'rm -rf /tmp/xbench; mkdir -p /tmp/xbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; echo deps ok'

qbench_c64 () {  # $1=nazwa pliku wynikowego
  docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
      --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
      --custom-output-len 256 --ignore-eos --num-prompts 600 --max-concurrency 64 \
      --save-result --result-dir /tmp/xbench --result-filename '"$1"'.json'
}

# B1 — c64 BEZ ŻADNEGO okna dcgmi — NIETYKALNY (rozstrzyga dryf):
qbench_c64 drift_b1_no_dcgmi_c64

# B2 — c64 z oknem dcgmi na STARYM zestawie pól (dokładnie jak 07-31, bez NVL):
dcgmi dmon -e 155,1002,1004,1005,1009,1010 -d 1000 -c 200 > "$QOUT/drift_b2_dcgmi.txt" 2>&1 &
DCGMI_PID=$!
qbench_c64 drift_b2_old_fields_c64
kill "$DCGMI_PID" 2>/dev/null; wait "$DCGMI_PID" 2>/dev/null

# B3 — c1 z AR (random 64/512, jak wszystkie c1 w projekcie) — TNIJ pierwszą:
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name random --random-input-len 64 --random-output-len 512 \
    --ignore-eos --num-warmups 3 --num-prompts 40 --max-concurrency 1 \
    --save-result --result-dir /tmp/xbench --result-filename drift_b3_ar_c1.json'

# ZAWSZE zbierz artefakty:
mkdir -p "$QOUT/bench_drift"
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/xbench/. "$QOUT/bench_drift/"
docker logs vllm > "$QOUT/log_qwen_drift.txt" 2>&1
nvidia-smi > "$QOUT/nvidia_smi_drift.txt"
python3 - "$QOUT/bench_drift" <<'PYEOF'
import glob,json,sys
for f in sorted(glob.glob(sys.argv[1]+"/*.json")):
    d=json.load(open(f))
    print(f"{f.split('/')[-1]:32s} out tok/s {d.get('output_throughput',0):8.1f}"
          f" | ITL med {d.get('median_itl_ms',0):7.2f}"
          f" | TPOT med {d.get('median_tpot_ms',0):6.2f}"
          f" | done {d.get('completed',0)}")
PYEOF
```

**Odczyt:** macierz interpretacyjna w §1. Wynik B1 porównuj z 1747 (dziś,
pełne okno) i 2022/1989 (07-31, stare pola).

---

## Cz. C — restore + commit (12 min)

```bash
docker compose -f "$QWEN_COMPOSE" down
unset QWEN_TP QWEN_CUDA_VISIBLE_DEVICES

docker compose -f "$COMPOSE" up -d --force-recreate vllm
for _ in $(seq 1 360); do curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 5; done
curl -fsS http://127.0.0.1:8000/health && echo "kimi OK" || echo "KIMI RESTORE FAILED"
docker compose -f "$COMPOSE" up -d vllm-small litellm open-webui
for _ in $(seq 1 240); do curl -fsS http://127.0.0.1:8004/health >/dev/null 2>&1 && break; sleep 5; done
curl -fsS http://127.0.0.1:8004/health && echo "deepseek OK"

docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/restore_ps2.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end2.txt"
git rev-parse HEAD > "$RUN_DIR/session/end_commit2.txt"

git status
du -sh "$RUN_DIR"      # traców NIE ma w repo?
git add "$RUN_DIR" results/runs/2026-08-03_nvlink_gap_fill/session/dmesg_end.txt
git commit -m "bench: test dryfu TP4-AR (dcgmi on/off, stare pola), c1 same-day, fix rank7 summary, dmesg #51"
git push -u origin main
```

**Opcja przy okazji (#34, zero skryptu):** po restore Kimi stoi — jeśli masz
Grafanę w przeglądarce, wygeneruj ruch (kilka requestów przez OpenWebUI albo
krótki bench) i zrób screenshot dashboardu vLLM pod obciążeniem.

---

## Po sesji (laptop, poza slotem)

1. Analiza macierzy B1/B2/B3 → rozstrzygnięcie dryf-vs-sampler; korekta
   dekompozycji link/kernel w T9 i notatce decyzyjnej (1,16× „kernela" —
   utrzymany, przypisany polom NVL albo przypisany dryfowi).
2. Komentarz #50: predykcja vs pomiar (07-31 + 08-03), trace 61,1%,
   dekompozycja z adnotacją dryfu; zamknięcie #51.
3. Reszta listy z planów 08-03: infrastructure §2.2, usunięcie
   `NCCL_NVLS_ENABLE=1` z compose Qwena (dopiero teraz), `sync-state`.

## Wątki otwarte (nie w tym slocie)

- dcgm-exporter (#34, HIGH VALUE) — prep laptopowy przed deployem; UWAGA:
  jeśli B1/B2 wskaże koszt pól NVL, exporter musi mieć ten wniosek w konfigu
  (nie watchować 1011/1012 domyślnie na środowisku benchmarkowym).
- #44 T8 proxy overhead (R1–R8) — osobna sesja.

---

## Walidacja planu

```text
git diff --check    (docs-only; skrypty są blokami kodu wewnątrz planu)
```
