# Plan sesji — atrybucja podłogi per-step (~2 h) + granica opłacalności NVLink (Kimi batched, Qwen c\*)

## Context

**Cel: #50.** Sesja 2026-06-11 ustaliła werdykt wstępny: krok decode jest
**floor-bound** (Kimi TP8 c=1: gaps 63% / NCCL 22.5% / compute 9%; Qwen TP1
c=1: krok ~9 ms przy SMACT 0.46 i zerowej komunikacji). Dwie rzeczy są do
zrobienia, w tej kolejności ważności:

1. **Cz. F (~2 h): ZNALEŹĆ przyczynę podłogi** — "floor-bound" musi dostać
   adres: ile kroku zjada orkiestracja spekulacji (MTP/Eagle3), ile launch
   overhead (cudagraph vs eager), ile host (clock governor / scheduling /
   sampling). Metoda: dawki (po jednej zmiennej na restart) + profil
   1-rankowy Qwen TP1 z timeline CPU.
2. **Cz. K1/Q1: domknąć matrycę NVLink** — batched Kimi (jedyny potencjalnie
   pozytywny scenariusz zakupu, dziś ekstrapolowany z Qwena) i próg c\* dla
   TP8.

Zmierzone wcześniej (nie powtarzać): krzywa Qwen TP1/2/4/8 × c1/c64; A4
(2 ranki UPI, c1); nop2p TP2 (negatywny); trace Kimi TP8 c=1.
**Lekcje obowiązują:** zero `set -e`/`exit` (interaktywne SSH), `python3` w
kontenerze, verify configu przed benchem, `cp` artefaktów natychmiast,
vLLM v0.20: profiler przez flagę `--profiler-config` (env usunięty).

**Stan startowy:** Kimi/DeepSeek/LiteLLM/OpenWebUI UP (po restore
2026-06-11). Observability UP. `dcgmi` tier-1.

---

## Budżet (4 h)

| Cz. | Co | Czas | Restarty |
|---|---|---:|---|
| 0' | vars, helpery, serving-side DOWN, idle | 15 | — |
| K1 | Kimi ramp c=1/8/16/32 + liczniki (Kimi już UP, bez restartu) | 50 | — |
| F0 | fakty hosta: governor, freq, NUMA, cudagraph mode | 5 | — |
| F-base | Qwen TP1 plain (nowy compose) — kotwica doz, c=1 | 15 | qwen ×1 |
| F1 | doza: spekulacja OFF (bez `--speculative-config`) | 20 | qwen ×1 |
| F2 | doza: `--enforce-eager` (spec ON) | 20 | qwen ×1 |
| F3 | profil TP1 c=1 (1 rank, CPU+GPU timeline) + szybkie podsumowanie | 40 | qwen ×1 |
| F6 | doza: governor → performance, re-bench c=1 (bez restartu) | 10 | — |
| Q1 | Qwen TP8: bench c=4 i c=16 (próg c\*) | 40 | qwen ×1 |
| D' | restore plain + smoke + commit + notes | 35 | kimi ×1 |

Razem ~250 min. Must-have: **0', K1, F-base, F1, F3, D'**.
Kolejność cięcia: **F6 → F2 → Q1**. K2 (profil Kimi c=8), Q2 (TP2 UPI c64)
i Q3 (TP4 2+2) świadomie przeniesione na następny slot.

---

## Cz. 0' — start (15 min)

Wklej z `docs/plans/2026-06-10-bottleneck-followup-session.md` (Cz. 0):
`sample_window`, `wait_http_health`, `start_sample_window`,
`stop_sample_window`. Potem:

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main
# BEZ set -euo pipefail; BEZ exit w całej sesji (interaktywne SSH)

RUN_DIR=results/runs/2026-06-11_nvlink_boundary
KOUT="$RUN_DIR/kimi_ramp"; QOUT="$RUN_DIR/qwen"; FOUT="$RUN_DIR/floor"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
QWEN_COMPOSE="serving/compose/docker-compose.qwen3.6.yml"
mkdir -p "$KOUT/bench" "$QOUT/bench_ramp" "$FOUT/bench" "$RUN_DIR/session"
set -a; source .env; set +a

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"

# czyste liczniki: zostaje TYLKO Kimi (vllm-small dzieli te same GPU!)
docker compose -f "$COMPOSE" stop litellm open-webui vllm-small
curl -fsS http://127.0.0.1:8000/health && echo "kimi OK"

P0OUT="$KOUT"            # sample_window pisze do $P0OUT — na czas K1
sample_window kimi_idle 90
```

---

## Cz. K1 — Kimi batched ramp c=1/8/16/32 (50 min, bez restartu)

Workload jak Cz. A (SWE custom, 256-out, ignore-eos). `max-num-seqs 32` ⇒
sufit c=32 (wyżej tylko kolejka).

```bash
docker compose -f "$COMPOSE" cp results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl vllm:/tmp/swe_bench_vllm.jsonl
docker compose -f "$COMPOSE" exec vllm bash -c \
  'rm -rf /tmp/kbench; mkdir -p /tmp/kbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "import pandas,datasets;print(\"deps ok\")"' || echo "PREREQS FAILED — nie leć dalej"

kimi_bench_c () {  # $1=c  $2=num_prompts  $3=sampler_cap_s
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
  stop_sample_window || echo "WARN: sampler $tag exit != 0"
  [ "$bench_status" -ne 0 ] && echo "WARN: bench $tag failed"
  docker compose -f "$COMPOSE" cp vllm:/tmp/kbench/. "$KOUT/bench/" || echo "WARN: cp $tag"
}

kimi_bench_c 1   24  600
kimi_bench_c 8   96  600
kimi_bench_c 16 192  900
kimi_bench_c 32 384 1200
docker logs vllm > "$KOUT/log_kimi_ramp.txt" 2>&1
nvidia-smi > "$KOUT/nvidia_smi_ramp.txt"
```

**Odczyt na żywo (c=32):** moc <150 W + SMACT <0.15 + PCIe RX >4 GB/s =
comms-signature (throughput-case NVLink żywy → profil K2 w następnym
slocie); moc 300+ W + SMACT >0.3 = silicon-signature (NVLink NO-GO totalne).

---

## Cz. F — atrybucja podłogi per-step (~2 h)

Cel: rozbić ~9 ms kroku TP1 c=1 (i przez analogię podłogę Kimi) na
**addytywny ledger**: spekulacja (orkiestracja MTP) + launch (cudagraph vs
eager) + host clock/scheduling + reszta. Każda doza = jedna zmienna.
Wszystkie benche: c=1, random 64-in/512-out, 40 promptów (identycznie jak
krzywa TP — wyniki wprost porównywalne z `2026-06-11_bottleneck`).

### F0 — fakty hosta (5 min, bez restartu)

```bash
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor | sort | uniq -c | tee "$FOUT/governor.txt"
grep MHz /proc/cpuinfo | sort -n -k4 | head -3; grep MHz /proc/cpuinfo | sort -n -k4 | tail -3
lscpu | grep -E "MHz|NUMA" | tee "$FOUT/cpu_freq_numa.txt"
# w logu startowym Qwen/Kimi: tryb cudagraph (compilation mode, capture sizes)
```

Jeśli governor ≠ `performance` → F6 staje się obowiązkowe (tani podejrzany
nr 1 dla host-floor).

### Helper benchowy F (po starcie silnika; prereqs jak KROK 3 planu 06-10 — pamiętaj `python3`)

```bash
P0OUT="$FOUT"   # okna dcgmi do $FOUT
fbench () {  # $1=tag
  tag="$1"
  start_sample_window "qwen_${tag}_c1" 600
  docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
      --dataset-name random --random-input-len 64 --random-output-len 512 \
      --ignore-eos --num-warmups 3 --num-prompts 40 --max-concurrency 1 \
      --save-result --result-dir /tmp/qbench --result-filename '"$tag"'_c1.json'
  bench_status=$?
  stop_sample_window || echo "WARN: sampler $tag"
  [ "$bench_status" -ne 0 ] && echo "WARN: bench $tag failed"
  docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/qbench/. "$FOUT/bench/" || echo "WARN: cp $tag"
  docker logs vllm > "$FOUT/log_${tag}.txt" 2>&1
}
```

### F-base — kotwica: TP1 plain na nowym compose (15 min, qwen ×1)

```bash
docker compose -f "$COMPOSE" stop vllm 2>/dev/null || true
docker compose -f "$COMPOSE" rm -f vllm 2>/dev/null || true
export QWEN_TP=1
docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 240 5
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$FOUT/verify_base.txt"   # =1
# prereqs (KROK 3, python3), potem:
fbench base
```

### F1 — doza: spekulacja OFF (20 min, qwen ×1)

Overlay nadpisuje komendę = kanoniczna **minus `--speculative-config`**
(placeholdery `${...}` zostają — compose je zinterpoluje):

```bash
cat > /tmp/qwen-nospec.yml <<'EOF'
services:
  vllm:
    command:
      --model Qwen/Qwen3.6-35B-A3B --served-model-name=${QWEN_SERVED_MODEL_NAME:-Qwen3.6} --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size ${QWEN_TP:-8} --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 --mm-encoder-tp-mode data --max-model-len ${QWEN_MAX_MODEL_LEN:-65536} --max-num-seqs ${QWEN_MAX_NUM_SEQS:-32} --max-num-batched-tokens ${QWEN_MAX_NUM_BATCHED_TOKENS:-8192} --gpu-memory-utilization ${QWEN_GPU_MEM_UTIL:-0.9}
EOF
docker compose -f "$QWEN_COMPOSE" -f /tmp/qwen-nospec.yml up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 240 5
docker inspect vllm --format '{{json .Config.Cmd}}' | tee "$FOUT/engine_cmd_nospec.json" | grep -o 'speculative' && echo "SPEC NADAL W CMD — przerwij" || echo "spec OFF ok"
# prereqs, potem:
fbench nospec
```

**Odczyt:** bez spekulacji krok = 1 token, więc ITL ≈ krok. Porównanie
tokenów/s i kroku z F-base rozdziela: zysk MTP vs koszt jego orkiestracji.

### F2 — doza: enforce-eager, spec ON (20 min, qwen ×1)

```bash
cat > /tmp/qwen-eager.yml <<'EOF'
services:
  vllm:
    command:
      --model Qwen/Qwen3.6-35B-A3B --served-model-name=${QWEN_SERVED_MODEL_NAME:-Qwen3.6} --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size ${QWEN_TP:-8} --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 --speculative-config='{"method":"mtp","num_speculative_tokens":${QWEN_NUM_SPECULATIVE_TOKENS:-3},"max_model_len":${QWEN_SPEC_MAX_MODEL_LEN:-8192}}' --mm-encoder-tp-mode data --max-model-len ${QWEN_MAX_MODEL_LEN:-65536} --max-num-seqs ${QWEN_MAX_NUM_SEQS:-32} --max-num-batched-tokens ${QWEN_MAX_NUM_BATCHED_TOKENS:-8192} --gpu-memory-utilization ${QWEN_GPU_MEM_UTIL:-0.9} --enforce-eager
EOF
docker compose -f "$QWEN_COMPOSE" -f /tmp/qwen-eager.yml up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 240 5
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -o 'enforce-eager' || echo "BRAK enforce-eager — przerwij"
# prereqs, potem:
fbench eager
```

**Odczyt:** Δkrok(eager − base) = ile launch overhead cudagraphy faktycznie
zdejmują. Mały Δ ⇒ launch nie jest podłogą; duży ⇒ host-launch istotny, a
cudagraph go już maskuje (podłoga leży gdzie indziej).

### F3 — profil TP1 c=1 z timeline CPU (40 min, qwen ×1)

Jeden rank ⇒ trace czytelny; `with_stack` (default) pokaże, **co robi CPU w
przerwach GPU** — to jest właściwy adres podłogi.

```bash
cat > /tmp/qwen-prof.yml <<'EOF'
services:
  vllm:
    command:
      --model Qwen/Qwen3.6-35B-A3B --served-model-name=${QWEN_SERVED_MODEL_NAME:-Qwen3.6} --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size ${QWEN_TP:-8} --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 --speculative-config='{"method":"mtp","num_speculative_tokens":${QWEN_NUM_SPECULATIVE_TOKENS:-3},"max_model_len":${QWEN_SPEC_MAX_MODEL_LEN:-8192}}' --mm-encoder-tp-mode data --max-model-len ${QWEN_MAX_MODEL_LEN:-65536} --max-num-seqs ${QWEN_MAX_NUM_SEQS:-32} --max-num-batched-tokens ${QWEN_MAX_NUM_BATCHED_TOKENS:-8192} --gpu-memory-utilization ${QWEN_GPU_MEM_UTIL:-0.9} --profiler-config='{"profiler":"torch","torch_profiler_dir":"/tmp/vllm_profile"}'
EOF
docker compose -f "$QWEN_COMPOSE" -f /tmp/qwen-prof.yml up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 240 5
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -o 'profiler-config' || echo "BRAK profiler-config — przerwij"
# prereqs, potem PROFIL KRÓTKI (1 request, nie pełny bench):
curl -fsS -X POST http://127.0.0.1:8000/start_profile
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name random --random-input-len 64 --random-output-len 256 \
    --ignore-eos --num-prompts 1 --max-concurrency 1 \
    --save-result --result-dir /tmp/qbench --result-filename prof_c1.json'
curl -fsS -X POST http://127.0.0.1:8000/stop_profile
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/qbench/. "$FOUT/bench/" || echo "WARN cp prof"
# flush-wait + kopia POZA repo (bloki 1:1 z poprawionego Cz. B planu 06-10):
TRACE_DIR=/home/working/nanoserve-tracing/qwen_tp1_$(date +%F)
mkdir -p "$TRACE_DIR" && docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/vllm_profile/. "$TRACE_DIR"/
T=$(find "$TRACE_DIR" -type f \( -name '*.json' -o -name '*.json.gz' \) | sort | head -n 1)
echo "trace: ${T:-NOT FOUND}"
[ -n "$T" ] && uv run python - "$T" <<'EOF' | tee "$FOUT/trace_summary_tp1_c1.txt"
import json,gzip,sys,collections
p=sys.argv[1]; op=gzip.open if p.endswith('.gz') else open
d=json.load(op(p,'rt'))
ev=[e for e in d.get('traceEvents',[]) if e.get('ph')=='X' and 'dur' in e]
kern=[e for e in ev if e.get('cat','')=='kernel']
def bucket(n):
    n=n.lower()
    if 'nccl' in n: return 'comms'
    if any(k in n for k in ('gemm','matmul','marlin','mla','attn','moe','silu','norm','quant')): return 'compute'
    return 'other'
agg=collections.Counter()
for e in kern: agg[bucket(e.get('name',''))]+=e['dur']
span=max(e['ts']+e['dur'] for e in kern)-min(e['ts'] for e in kern); tot=sum(agg.values())
print(f"span {span/1e6:.2f}s kernel {tot/1e6:.2f}s gaps {(span-tot)/1e6:.2f}s ({(span-tot)/span*100:.0f}%)")
for k,v in agg.most_common(): print(f"  {k:10} {v/1e6:7.2f}s {v/span*100:5.1f}%")
# CPU: co zjada czas hosta (top 25 cpu_op po sumie czasu)
cpu=collections.Counter()
for e in ev:
    if e.get('cat')=='cpu_op': cpu[e['name']]+=e['dur']
print("\nTOP-25 cpu_op (suma ms):")
for n,v in cpu.most_common(25): print(f"  {v/1e3:9.1f} ms  {n[:90]}")
ann=collections.Counter()
for e in ev:
    if 'annotation' in e.get('cat',''): ann[e['name']]+=e['dur']
print("\nannotations (suma ms):")
for n,v in ann.most_common(15): print(f"  {v/1e3:9.1f} ms  {n[:90]}")
EOF
```

Głęboka atrybucja przerw (które frame'y Pythona aktywne w gapach, fazy
draft→verify→sample per krok) — offline na laptopie z kopii tracu; serwer
dostarcza trace + powyższe szybkie podsumowanie.

### F6 — doza: governor performance (10 min, bez restartu silnika)

Tylko jeśli F0 pokazał governor ≠ performance:

```bash
sudo cpupower frequency-set -g performance && cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
fbench base_perfgov     # silnik z F3 nadal stoi? użyj bieżącego configu i porównuj 1:1 z odpowiadającą kotwicą
```

(porównanie 1:1: ta sama konfiguracja silnika przed/po zmianie governora;
jeśli silnik z F3 (profiler) stoi — profil NIE włączony = zachowanie
normalne, porównaj z F3-bench; zanotuj w notes, z czym porównujesz.
Po sesji przywróć poprzedni governor, jeśli polityka serwera tego wymaga.)

---

## Cz. Q1 — Qwen TP8: c=4 i c=16 → próg c\* (40 min, qwen ×1)

```bash
P0OUT="$QOUT"
export QWEN_TP=8
docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm   # BEZ overlayów!
wait_http_health http://127.0.0.1:8000/health 240 5
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$QOUT/verify_tp8.txt"
grep -q "tensor_parallel_size=8" "$QOUT/verify_tp8.txt" || echo "TP MISMATCH — nie benchuj"
# prereqs (python3), potem (helper jak kimi_bench_c, flagi Qwen, custom SWE 256-out):
qwen_bench_c () {  # $1=c $2=np $3=cap
  c="$1"; np="$2"; tag="qwen_tp8_c${c}"
  start_sample_window "$tag" "$3"
  docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
      --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
      --custom-output-len 256 --ignore-eos --num-warmups 2 \
      --num-prompts '"$np"' --max-concurrency '"$c"' \
      --save-result --result-dir /tmp/qbench --result-filename '"$tag"'.json'
  bench_status=$?
  stop_sample_window || echo "WARN: sampler $tag"
  [ "$bench_status" -ne 0 ] && echo "WARN: bench $tag failed"
  docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/qbench/. "$QOUT/bench_ramp/" || echo "WARN: cp $tag"
}
qwen_bench_c 4  100 600
qwen_bench_c 16 300 900
docker logs vllm > "$QOUT/log_qwen_tp8_ramp.txt" 2>&1
```

(c=1 i c=64 dla TP8 już są w `2026-06-11_bottleneck` → 4 punkty krzywej.)

---

## Cz. D' — restore + close-out (35 min, kimi ×1)

```bash
docker compose -f "$QWEN_COMPOSE" stop vllm; docker compose -f "$QWEN_COMPOSE" rm -f vllm
unset QWEN_TP QWEN_CUDA_VISIBLE_DEVICES
docker compose -f "$COMPOSE" up -d --force-recreate vllm vllm-small litellm open-webui
wait_http_health http://127.0.0.1:8000/health 180 10
docker inspect vllm --format '{{json .Config.Cmd}}' > "$RUN_DIR/session/restore_engine_cmd.json"
if docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qE 'profiler-config|enforce-eager'; then
  echo "UWAGA: flaga sesyjna w Cmd po restore — recreate z samym plain compose"
fi
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -o 'speculative-config' || echo "UWAGA: brak spec w Cmd po restore"
uv run python -m benchmarks.scripts.measure_ttft_once --base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 --api-key "$LITELLM_MASTER_KEY" --max-tokens 1024 \
  --output "$RUN_DIR/session/restore_smoke.json"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
find "$RUN_DIR" -type f | sort > "$RUN_DIR/session/artifact_manifest.txt"
du -sh "$RUN_DIR"   # traców nie ma w repo?
git add "$RUN_DIR" && git commit -m "bench: floor attribution + nvlink boundary (kimi ramp, qwen doses c1, tp8 c4/c16)" && git push origin main
```

---

## Kryteria rozstrzygnięcia

### Ledger podłogi (Cz. F) — cel: addytywny rozkład ~9 ms kroku TP1 c=1

| pomiar | co wycenia |
|---|---|
| F-base vs nospec (F1) | koszt/zysk orkiestracji MTP: krok bez spekulacji = czysty (silnik+host) na 1 token; tok/s rozstrzyga, czy MTP netto pomaga przy c=1 |
| F-base vs eager (F2) | ile launch overhead zdejmują cudagraphy (Δ mały ⇒ launch to nie podłoga) |
| F3 trace | adres przerw: top cpu_op/annotations w gapach (sched, sampling, draft, detokenize) |
| F6 | udział clock-governora w hoście (częsta, banalna przyczyna) |

Werdykt do artykułu/T9: "podłoga = X ms spekulacja + Y ms launch + Z ms
host-sched/sampling (+ W ms governor)" — z dowodem per składnik. Jeśli
składniki nie sumują się do ~9 ms, różnica = "nieprzypisane" (uczciwie) i
kierunek na kolejny profil.

### Matryca NVLink (K1 + Q1, reszta zmierzona wcześniej)

NVLink **uzasadniony** tylko gdy łącznie: (1) model wymusza TP≥4 (dla
mieszczących się na ≤2 GPU zysk ≈ 0 — zmierzone przyczynowo), (2) praca w
reżimie c ≥ c\* (Q1: pierwszy punkt, gdzie krok TP8 > ~1.5× kroku c=1 przy
licznikach na podłodze), (3) K1 pokazuje comms-signature przy c=16/32
(inaczej NO-GO totalne). Przy spełnionych (1–3): granica zysku = udział
comms (Amdahl); dokładny udział → K2 w następnym slocie. Niezależnie:
podłoga z Cz. F jest dźwignią software'ową PRZED każdym zakupem.

## Świadomie poza scope

- K2 (profil Kimi c=8), Q2 (TP2 UPI c64), Q3 (TP4 2+2) — następny slot.
- Podnoszenie `max-num-seqs` Kimi >32; EP on/off; NCCL_ALGO; nsys.
- Zmiany produkcyjnego configu Kimi (wszystkie dozy tylko na Qwen TP1).
