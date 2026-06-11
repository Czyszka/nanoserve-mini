# Plan sesji — werdykt NVLink (latency/throughput) + seria F (atrybucja podłogi)

## Context

**Dwa cele tej sesji, w tej kolejności priorytetów:**

1. **Werdykt NVLink (must-have):** po sesji #50 ma mieć tabelę
   latency/throughput — gdzie NVLink jest uzasadniony i o ile (szacunkowo),
   a gdzie nie zmienia nic / za mało. Strona latencji jest już rozstrzygnięta
   (c≈1 floor-bound: trace Kimi gaps 63% / NCCL 22.5%; zysk ≤~1.3×; modele
   ≤2 GPU: ~0 przyczynowo). **Dziś domykamy stronę throughput:** K1 (Kimi
   ramp), K2 (profil Kimi przy batchu → udział NCCL), Q1 (próg c\*), Q3
   (kara cross-island → współczynnik `capture` dla NVLink 4-way).
2. **Seria F — przyczyna podłogi:** podłoga to 63% kroku Kimi; "floor-bound"
   musi dostać adres. Dozy (jedna zmienna na restart) + profil TP1 z
   timeline CPU: F-base (kotwica), F1 (spec OFF), F2 (eager), F3 (profil),
   F6 (governor). F0 (fakty hosta) zawsze.

**Budżet:** pełny program = ~5 h. W 4 h działa rozgałęzienie po K1 (niżej).
Werdykt NVLink nie może wypaść — tnij F, nie K/Q (wyjątek: gałąź silicon,
gdzie K2 traci sens i czas idzie w F).

**Lekcje obowiązują:** zero `set -e`/`exit` (interaktywne SSH), `python3` w
kontenerze, verify configu przed benchem, `cp` artefaktów natychmiast,
profiler w v0.20 przez flagę `--profiler-config` (env usunięty upstream).

**Stan startowy:** Kimi/DeepSeek/LiteLLM/OpenWebUI UP (po restore
2026-06-11). Observability UP. `dcgmi` tier-1.

---

## Budżet i rozgałęzienie

| Cz. | Co | Czas | Restarty |
|---|---|---:|---|
| 0' | vars, helpery, serving-side DOWN, idle, **F0** | 20 | — |
| K1 | Kimi ramp c=1/8/16/32 + liczniki (Kimi już UP) | 50 | — |
| K2 | profil Kimi c=16 — **tylko gałąź comms** | 50 | kimi ×1 |
| Q1 | Qwen TP8: c=4 i c=16 (próg c\*) | 40 | qwen ×1 |
| Q3 | Qwen TP4 cross-island 2+2 (pełny pair) | 30 | qwen ×1 |
| F-base | Qwen TP1 plain — kotwica doz | 15 | qwen ×1 |
| F1 | doza: spekulacja OFF | 20 | qwen ×1 |
| F2 | doza: enforce-eager | 20 | qwen ×1 |
| F3 | profil TP1 c=1 (CPU+GPU timeline) | 45 | qwen ×1 |
| F6 | doza: governor performance (bez restartu) | 10 | — |
| D' | restore plain + smoke + commit + notes | 35 | kimi ×1 |

**Gałąź po K1 (punkt decyzyjny niżej):**

- **comms-signature** → K2 wchodzi (werdykt wymaga udziału NCCL). W 4 h:
  0'+K1+K2+Q1+Q3+D' (~225 min) + F0; z serii F wykonaj F3, jeśli zostaje
  czas; F-base/F1/F2/F6 → następny slot. W ~5 h: + F-base, F1, F3.
- **silicon-signature** → K2 odpada (NVLink-throughput dla Kimi = NO
  trywialnie, werdykt komplet po Q1+Q3). Czas idzie w F: F-base, F1, F2,
  F3, F6 mieszczą się w 4 h.

Kolejność cięcia przy poślizgu (obie gałęzie): **F2 → F6 → F-base+F1 → Q3 →
Q1-c4 (zostaw c16)**. K1, Q1(c16), D' i — w gałęzi comms — K2 są nietykalne.

---

## Cz. 0' — start (20 min)

Wklej z `docs/plans/2026-06-10-bottleneck-followup-session.md`: `sample_window`,
`wait_http_health`, `start_sample_window`, `stop_sample_window` (Cz. 0) oraz
`run_qwen_tp` (Cz. A — potrzebny dla Q3). Potem:

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main
# BEZ set -euo pipefail; BEZ exit w całej sesji (interaktywne SSH)

RUN_DIR=results/runs/2026-06-12_nvlink_verdict
KOUT="$RUN_DIR/kimi_ramp"; QOUT="$RUN_DIR/qwen"; FOUT="$RUN_DIR/floor"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
QWEN_COMPOSE="serving/compose/docker-compose.qwen3.6.yml"
mkdir -p "$KOUT/bench" "$QOUT/bench_ramp" "$FOUT/bench" "$RUN_DIR/session"
set -a; source .env; set +a

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"

# F0 — fakty hosta (interpretacja podłogi)
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor | sort | uniq -c | tee "$RUN_DIR/session/governor.txt"
lscpu | grep -E "MHz|NUMA" | tee "$RUN_DIR/session/cpu_freq_numa.txt"
# governor != performance => F6 obowiązkowe (tani podejrzany nr 1)

# czyste liczniki: zostaje TYLKO Kimi (vllm-small dzieli te same GPU!)
docker compose -f "$COMPOSE" stop litellm open-webui vllm-small
curl -fsS http://127.0.0.1:8000/health && echo "kimi OK"

P0OUT="$KOUT"            # sample_window pisze do $P0OUT
sample_window kimi_idle 90
```

---

## Cz. K1 — Kimi batched ramp c=1/8/16/32 (50 min, bez restartu)

Workload: SWE custom, 256-out, ignore-eos. `max-num-seqs 32` ⇒ sufit c=32.

```bash
docker compose -f "$COMPOSE" cp results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl vllm:/tmp/swe_bench_vllm.jsonl
docker compose -f "$COMPOSE" exec vllm bash -c \
  'rm -rf /tmp/kbench; mkdir -p /tmp/kbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "import pandas,datasets;print(\"deps ok\")"' || echo "PREREQS FAILED — nie leć dalej"

kimi_bench_c () {  # $1=c  $2=num_prompts  $3=sampler_cap_s  $4=sufiks tagu (opcjonalny)
  c="$1"; np="$2"; tag="kimi_c${c}${4:-}"
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

### PUNKT DECYZYJNY — sygnatura z `kimi_c32_dcgmi.txt` (per GPU, 5 min)

- **comms-signature**: moc < ~150 W, SMACT < ~0.15, PCIe RX > ~4 GB/s, a
  TPOT(c32) ≫ TPOT(c8) → **gałąź comms: wykonaj K2**.
- **silicon-signature**: moc → 300+ W, SMACT > ~0.3 → **gałąź silicon:
  pomiń K2, po Q1/Q3 całą resztę czasu daj serii F**.
- niejednoznaczne → traktuj jak comms (K2 rozstrzygnie wprost).

**ROZSTRZYGNIĘTE w trakcie sesji (po K1 + powtórce c16r):** sygnatura comms
(moc ≤185 W, SMACT ≤0.18, PCIe RX 7.2–7.9 GB/s na suficie przy każdym c≥8).
Anomalia c=16 odtworzona (ITL med 512→525 ms, ±3%) → realna patologia, nie
szum. **K2 wykonujemy przy c=16**, tam gdzie patologia żyje.

## Cz. K2 — profil Kimi c=16 (50 min, kimi ×1) — gałąź comms

```bash
# heredoc /tmp/kimi-profiler.yml — skopiuj 1:1 z Cz. B planu 2026-06-10
# (komenda Kimi + --profiler-config='{"profiler":"torch","torch_profiler_dir":"/tmp/vllm_profile"}')
docker compose -f "$COMPOSE" -f /tmp/kimi-profiler.yml up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 180 10
docker inspect vllm --format '{{json .Config.Cmd}}' > "$KOUT/engine_cmd_profiled.json"
grep -o 'profiler-config' "$KOUT/engine_cmd_profiled.json" || echo "BRAK profiler-config — nie startuj profilu"
# prereqs ponownie (force-recreate!) — blok jak w K1
curl -fsS -X POST http://127.0.0.1:8000/start_profile
kimi_bench_c 16 16 300 p         # tag kimi_c16p — KRÓTKIE okno = strawny trace
curl -fsS -X POST http://127.0.0.1:8000/stop_profile
# flush-wait, kopia POZA repo (TRACE_DIR=/home/working/nanoserve-tracing/kimi_c16_$(date +%F)),
# podsumowanie rank0 + rank_last — bloki 1:1 z poprawionego Cz. B planu 06-10;
# tee do "$KOUT/trace_summary_c16_rank0.txt" / "..._rank_last.txt"
```

**Wyjście do werdyktu:** udział NCCL w spanie przy batchu →
`gain_est = 1/(1 − share×capture)`, `capture` z Q3.

---

## Cz. Q1 — Qwen TP8: c=4 i c=16 → próg c\* (40 min, qwen ×1)

```bash
P0OUT="$QOUT"
docker compose -f "$COMPOSE" stop vllm 2>/dev/null || true
docker compose -f "$COMPOSE" rm -f vllm 2>/dev/null || true
export QWEN_TP=8
docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm   # BEZ overlayów
wait_http_health http://127.0.0.1:8000/health 240 5
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$QOUT/verify_tp8.txt"
grep -q "tensor_parallel_size=8" "$QOUT/verify_tp8.txt" || echo "TP MISMATCH — nie benchuj"
# prereqs (python3, KROK 3 planu 06-10), potem:
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

## Cz. Q3 — TP4 cross-island 2+2 (30 min, qwen ×1)

```bash
export QWEN_CUDA_VISIBLE_DEVICES=0,1,4,5
run_qwen_tp 4 x0145
unset QWEN_CUDA_VISIBLE_DEVICES
grep '^CUDA_VISIBLE_DEVICES=0,1,4,5$' "$QOUT/engine_env_tp4x0145.txt" || echo "ZŁY PLACEMENT — Q3 nieważne"
```

Porównanie: `tp4x0145` vs `tp4` intra (krok c64 53.7 ms).
`capture ≈ 1 − Δ_island/Δ_comms_total` — ile komunikacji NVLink 4-way
realnie przejmuje, skoro UPI między wyspami zostaje.

---

## Cz. F — atrybucja podłogi (dozy + profil; benche: c=1, random 64/512, 40 promptów)

### Helper (po starcie silnika; prereqs jak KROK 3 planu 06-10 — `python3`!)

```bash
P0OUT="$FOUT"
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

### F-base — kotwica: TP1 plain, nowy compose (15 min, qwen ×1)

```bash
export QWEN_TP=1
docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 240 5
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$FOUT/verify_base.txt"   # =1
# prereqs, potem:
fbench base
```

### F1 — doza: spekulacja OFF (20 min, qwen ×1)

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

Bez spekulacji krok = 1 token ⇒ ITL ≈ krok; vs F-base rozdziela zysk MTP od
kosztu jego orkiestracji.

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

Δkrok(eager − base) = ile launch overhead zdejmują cudagraphy.

### F3 — profil TP1 c=1 z timeline CPU (45 min, qwen ×1)

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
# prereqs, potem PROFIL KRÓTKI (1 request):
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

Głęboka atrybucja gapów (frame'y Pythona, fazy draft→verify→sample) —
offline na laptopie z kopii tracu.

### F6 — doza: governor performance (10 min, bez restartu silnika)

Tylko jeśli F0 pokazał governor ≠ performance:

```bash
sudo cpupower frequency-set -g performance && cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
fbench perfgov     # porównuj 1:1 z benchem na TEJ SAMEJ konfiguracji silnika sprzed zmiany
# po sesji przywróć poprzedni governor, jeśli polityka serwera tego wymaga
```

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
git add "$RUN_DIR" && git commit -m "bench: nvlink verdict + floor attribution session" && git push origin main
```

---

## Deliverable 1: tabela werdyktu NVLink (do #50, po analizie)

| scenariusz | werdykt NVLink | źródło liczby |
|---|---|---|
| **Latencja** c≈1, dowolny model | NIE — ≤~1.3× | zmierzone 2026-06-11 |
| Dowolny tryb, model ≤2 GPU | NIE — ~0 | zmierzone (TP2 optimum, nop2p) |
| Throughput TP8, c < c\* | NIE — reżim podłogi | Q1 (próg c\*) |
| **Throughput Kimi TP8, c ≥ c\*** | szacunek `1/(1−share×capture)` | share: K2 (lub górna granica z K1), capture: Q3 |
| Throughput TP4 (model 2–4 GPU) | "do ~4.7× × capture" | krzywa 06-11 + Q3 |

## Deliverable 2: ledger podłogi (Cz. F)

"Podłoga = X ms spekulacja (F1) + Y ms launch (F2) + Z ms host-sched/sampling
(F3) + W ms governor (F6)" — z dowodem per składnik i rubryką "nieprzypisane",
jeśli nie sumuje się do ~9 ms. Wniosek do rekomendacji: obniżenie podłogi
software'owo podnosi `share` comms → werdykt NVLink liczyć na udziałach po
optymalizacji.

## Świadomie poza scope

- Q2 (TP2 UPI c64), podnoszenie `max-num-seqs` >32, EP on/off, NCCL_ALGO, nsys.
- Zmiany produkcyjnego configu Kimi (dozy tylko na Qwen TP1).
