# Sesja serwerowa 2026-08-10 (poniedziałek) — DFlash k=4 vs Eagle3, całość na SWE custom

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, NVLink 4-way: wyspy GPU 0-3 / 4-7)
**Slot (założenie):** ~110 min (2 starty A/B + restore, 6 benchy).
**Kontekst:** A/B 08-07 (`results/runs/2026-08-07_kimi_dflash_ab/NOTES.md`) odrzucił
DFlash k=8 (c1 1,07×, c32 0,89× vs Eagle3), ale profil akceptacji pokazał, że
pozycje 0-3 niosą 85% akceptacji — stąd test **k=4**. Druga poprawka: benche c1
z 08-07 poszły na `random` (błąd metodyczny) — dziś **wszystko na SWE custom**,
w tym c1 na 24 promptach jak 07-31 (kontrola bit-zgodności: `total_input_tokens`
ma wyjść **48479**). Obie nogi @util **0,65** (wymóg pamięciowy DFlash; c1 jest
na util niewrażliwe, c32 porównujemy w ramach dnia).

> **Plan jest samowystarczalny** — wszystkie helpery i komendy inline.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH.
> **Świeży shell SSH.** Koniec sesji = restore pełnego stacku z repo compose.

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

Odniesienia: Eagle3 c1-SWE = 7,44 ms TPOT (0.20, 07-31, ten sam zestaw 24 prompty);
Eagle3 c32-SWE = 649 (@0,65, 08-07) / 676 (@0,60, 08-07) / 594 (0.20, 07-31).
Szum ±6%. Metryki spec_decode są kumulatywne → snapshot PO KAŻDYM benchu
(`spec_snap`), delty liczy laptop.

| pomiar | predykcja | odczyt |
|---|---|---|
| kontrola zestawu: c1 `total_input_tokens` | **48479** (bit-zgodność z 07-31) | inna wartość → sampling datasetu zależny od num_prompts inaczej niż zakładamy — zanotuj, porównania c1 z 7,44 tylko jakościowe |
| Eagle3-dziś c1-SWE TPOT | **7–9 ms** (0.26 zdrowe w c1; 7,44 na 0.20) | >10 ms → regresja c1 w 0.26 NA REALNYM TEKŚCIE — nowy wątek, ważniejszy niż DFlash |
| DFlash k=4 c1-SWE TPOT | **8–13 ms** (akceptacja na SWE skoczy vs random; 5 tok weryfikacji/krok zamiast 9) | ≤0,85× Eagle3-dziś → wygrana latencji; ≥ Eagle3 → k=4 też odpada |
| DFlash k=4 c32 warm | **600–680** | — |
| akceptacja DFlash k=4 na SWE (delta per bench) | p0 **55–70%** (vs 46% na miksie z randomem); śr. ≥1,5 tok akceptowanych/krok | p0 <45% także na czystym SWE → drafter słabo dopasowany do targetu niezależnie od workloadu |
| akceptacja Eagle3 na SWE (delta per bench) | p0 ~60% (zgodnie z historią) | dużo niżej → coś zmieniło się w 0.26, odnotuj |

**Bramka adopcji DFlash k=4** (jak poprzednio): (c1 TPOT ≤ 0,85× Eagle3-dziś)
**ORAZ** (c32 warm ≥ 0,94× Eagle3-dziś c32). Oba → zmiana spec-config w compose
(laptop, osobny commit). Inaczej: Eagle3 zostaje i **temat DFlash zamykamy na
dobre** (dwie przegrane konfiguracje wystarczą; k∈{5,6,7} nie testujemy).

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. 0 | start, pull, snapshoty, zmienne | 4 |
| Cz. H | helpery | 2 |
| Cz. 3 | start DFlash k=4 (overlay @0,65) + verify | 15 |
| Cz. 4 | benche DFlash: c1-SWE → c32 b1 → c32 b2 (+ spec_snap po każdym) | 30 |
| Cz. 5 | start Eagle3 (overlay @0,65) + c1-SWE → c32 b1 → c32 b2 | 40 |
| Cz. 6 | restore pełnego stacku z repo compose, NOTES, commit/push | 18 |
| | **razem** | **~109** |

**Kolejność cięcia:** Eagle3 c32 b2 → DFlash c32 b2 (b1 zostaje jako zimny punkt;
warm-to-warm wtedy niedostępne — zanotuj w NOTES). **Nietykalne:** oba c1-SWE
(główne pytanie sesji + kontrola bit-zgodności), Cz. 6.

---

## Cz. 0 — start (4 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main
unset RUN_DIR OUT SESSION QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_ARGS DL_PID

RUN_DIR=results/runs/2026-08-10_kimi_dflash_k4_swe
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
DIAG=~/working/nanoserve-diag/2026-08-10_kimi_dflash_k4_swe
SWE=results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl
mkdir -p "$RUN_DIR/session" "$RUN_DIR/bench" "$DIAG"
set -a; source .env; set +a

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"
# draft nvidia/Kimi-K2.6-DFlash jest już w cache HF po sesji 08-07 — bez pobierania
```

---

## Cz. H — helpery (wklej cały blok, 2 min)

Sprawdzone 08-03/08-07; nowy jest tylko `spec_snap` (snapshot per bench zamiast
jednego kumulatywnego — lekcja 08-07) i `kimi_c1_swe` (c1 na SWE, nie random).

```bash
czekaj() {  # werdykt biegu: błąd albo pełny start (max ~20 min)
  for i in $(seq 1 120); do
    docker logs vllm 2>&1 | grep -qE "CUDA error|Application startup complete" && break
    sleep 10
  done
  docker logs vllm 2>&1 | grep -cE "CUDA error" && echo "== FAIL (CUDA error) ==" || echo "== brak CUDA error =="
  docker logs vllm 2>&1 | tail -n 3
}

zrzut() {  # $1=nazwa biegu — pełny log lokalnie; do repo werdykt + błąd + cmd/env
  docker logs -t vllm > "$DIAG/log_full_$1.txt" 2>&1
  docker inspect vllm --format '{{.Config.Image}}' > "$RUN_DIR/engine_image_$1.txt"
  docker inspect vllm --format '{{json .Config.Cmd}}' > "$RUN_DIR/engine_cmd_$1.json"
  docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | sed -E 's/^(HUGGING_FACE_HUB_TOKEN|HF_TOKEN|[A-Z_]*API_KEY|[A-Z_]*SECRET[A-Z_]*)=.*/\1=REDACTED/' \
    > "$RUN_DIR/engine_env_$1.txt"
  grep -n -i -B 20 -A 60 -m 2 -E "CUDA error|Traceback|ncclUnhandled" \
    "$DIAG/log_full_$1.txt" > "$RUN_DIR/log_$1_error.txt" 2>&1
  [ -s "$RUN_DIR/log_$1_error.txt" ] || echo "# brak bloku błędu" > "$RUN_DIR/log_$1_error.txt"
  grep -n -E "Graph capturing finished|Application startup complete|speculative" \
    "$DIAG/log_full_$1.txt" | tail -n 6 > "$RUN_DIR/log_$1_verdict.txt"
}

smoke() {
  curl -s http://localhost:8000/v1/chat/completions -H 'Content-Type: application/json' \
    -d '{"model":"kimi-k2.6","messages":[{"role":"user","content":"2+2?"}],"max_tokens":8}'
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

ensure_dataset () {
  docker cp "$SWE" vllm:/tmp/swe_bench_vllm.jsonl \
    || { echo "STOP: docker cp nie zadziałał — czy kontener 'vllm' stoi?"; return 1; }
  n=$(docker exec vllm sh -c 'wc -l < /tmp/swe_bench_vllm.jsonl' 2>/dev/null | tr -d ' ')
  echo "dataset w kontenerze: ${n:-BRAK} linii"
  { [ -n "$n" ] && [ "$n" -gt 100 ]; } \
    || { echo "STOP: dataset nie dotarł — NIE benchuj"; return 1; }
}

bench_prereqs () {   # po każdym recreate, przed benchami
  ensure_dataset || return 1
  docker compose -f "$COMPOSE" exec vllm bash -c \
    'rm -rf /tmp/kbench; mkdir -p /tmp/kbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "print(\"deps ok\")"'
}

kimi_c1_swe () {  # $1=nazwa wyniku — c1 na SWE, 24 prompty JAK 07-31 (bit-zgodność)
  docker compose -f "$COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
      --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
      --custom-output-len 256 --ignore-eos --num-warmups 3 \
      --num-prompts 24 --max-concurrency 1 \
      --save-result --result-dir /tmp/kbench --result-filename '"$1"'.json'
}

kimi_c32 () {  # $1=nazwa wyniku — c32 SWE 384 (identyczne z 07-31 i 08-07)
  docker compose -f "$COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
      --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
      --custom-output-len 256 --ignore-eos --num-warmups 2 \
      --num-prompts 384 --max-concurrency 32 \
      --save-result --result-dir /tmp/kbench --result-filename '"$1"'.json'
}

spec_snap () {  # $1=etykieta — snapshot liczników spec PO danym benchu; delty liczy laptop
  curl -s http://127.0.0.1:8000/metrics | grep -E "spec_decode.*_total" \
    > "$RUN_DIR/metrics_spec_$1.txt"
  [ -s "$RUN_DIR/metrics_spec_$1.txt" ] || echo "# brak metryk spec_decode" > "$RUN_DIR/metrics_spec_$1.txt"
}

show_bench () {
  python3 - "$1" <<'PYEOF'
import glob, json, sys
for f in sorted(glob.glob(sys.argv[1] + "/*.json")):
    d = json.load(open(f))
    print(f"{f.split('/')[-1]:28s} tok/s {d.get('output_throughput', 0):7.1f}"
          f" | TPOT med {d.get('median_tpot_ms', 0):6.2f}"
          f" | ITL med {d.get('median_itl_ms', 0):7.2f}"
          f" | in_tok {d.get('total_input_tokens', 0):7d}"
          f" | done {d.get('completed', 0)}")
PYEOF
}
```

---

## Cz. 3 — start DFlash k=4 (overlay @0,65) (15 min)

```bash
cat > /tmp/kimi-dflash-k4.yml <<'EOF'
services:
  vllm:
    restart: "no"
    command:
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size 8 --gpu-memory-utilization 0.65 --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2 --enable-auto-tool-choice --language-model-only --max-num-seqs 32 --max-model-len 131072 --max-num-batched-tokens 4096 --speculative-config='{"method":"dflash","model":"nvidia/Kimi-K2.6-DFlash","num_speculative_tokens":4}' --compilation-config='{"pass_config":{"fuse_allreduce_rms":false}}'
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-dflash-k4.yml up -d --force-recreate vllm

# FAIL-FAST na gołych tokenach (inspect escapuje cudzysłowy JSON-a)
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qo 'dflash' \
  || echo "STOP: spec-config dflash nie wszedł do cmd"
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qo 'num_speculative_tokens.:4' \
  || echo "STOP: k=4 nie wszedł do cmd"
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qo 'fuse_allreduce_rms' \
  || echo "STOP: workaround fuzji wypadł z komendy"

czekaj
zrzut dflash4_start
smoke > "$RUN_DIR/smoke_dflash4.json" 2>&1
```

---

## Cz. 4 — benche DFlash k=4, wszystko SWE (30 min)

```bash
bench_prereqs || echo "PRZERWIJ — prereqs nie przeszły"
spec_snap dflash4_00_baseline

kimi_c1_swe dflash4_c1
spec_snap dflash4_01_po_c1
kimi_c32 dflash4_c32_b1
spec_snap dflash4_02_po_b1
kimi_c32 dflash4_c32_b2
spec_snap dflash4_03_po_b2

docker compose -f "$COMPOSE" cp vllm:/tmp/kbench/. "$RUN_DIR/bench/"
show_bench "$RUN_DIR/bench"
# KONTROLA ZESTAWU: dflash4_c1 ma mieć in_tok 48479 (bit-zgodność z 07-31);
# c32 ma mieć in_tok 339979. Inne wartości → zanotuj w NOTES, nie przerywaj.
nvidia-smi > "$RUN_DIR/session/nvidia_smi_dflash4.txt"
```

---

## Cz. 5 — noga Eagle3 @0,65, ten sam dzień, te same benche (40 min)

```bash
cat > /tmp/kimi-eagle3-065.yml <<'EOF'
services:
  vllm:
    restart: "no"
    command:
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size 8 --gpu-memory-utilization 0.65 --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2 --enable-auto-tool-choice --language-model-only --max-num-seqs 32 --max-model-len 131072 --max-num-batched-tokens 4096 --speculative-config='{"model":"lightseekorg/kimi-k2.6-eagle3-mla","method":"eagle3","num_speculative_tokens":3,"max_model_len":8192}' --compilation-config='{"pass_config":{"fuse_allreduce_rms":false}}'
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-eagle3-065.yml up -d --force-recreate vllm
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qo 'eagle3' \
  || echo "STOP: to nie jest config Eagle3"
czekaj
zrzut eagle3_dzis

bench_prereqs || echo "PRZERWIJ"
spec_snap eagle3_00_baseline
kimi_c1_swe eagle3_c1_swe
spec_snap eagle3_01_po_c1
kimi_c32 eagle3_c32_b1
spec_snap eagle3_02_po_b1
kimi_c32 eagle3_c32_b2
spec_snap eagle3_03_po_b2

docker compose -f "$COMPOSE" cp vllm:/tmp/kbench/. "$RUN_DIR/bench/"
show_bench "$RUN_DIR/bench"
```

---

## Cz. 6 — restore z repo compose, NOTES, commit (18 min)

```bash
docker compose -f "$COMPOSE" up -d --force-recreate      # pełny stack, repo = Eagle3 @0,60
wait_http_health http://127.0.0.1:8000/health 360 5 && echo "kimi OK"
wait_http_health http://127.0.0.1:8004/health 240 5 && echo "deepseek OK"
docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/restore_ps.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
git rev-parse HEAD > "$RUN_DIR/session/end_commit.txt"

cat > "$RUN_DIR/NOTES.md" <<'EOF'
# Werdykty 2026-08-10 — DFlash k=4 vs Eagle3 (całość SWE, oba @0,65)
| pomiar | DFlash k=4 | Eagle3 (dziś) | odniesienia |
|---|---|---|---|
| c1-SWE TPOT med (ms) | | | 7,44 (0.20, 07-31, ten sam zestaw) |
| c1 in_tok = 48479? | | | kontrola bit-zgodności |
| c32 b1 / b2 (tok/s) | | | Eagle3 08-07: 649 @0,65 / 676 @0,60; 594 (0.20) |
| akceptacja p0 na SWE (delta per bench) | | | k=8 na miksie: p0 46% |
- BRAMKA (c1 ≤0,85× Eagle3-dziś ORAZ c32 b2 ≥0,94× Eagle3-dziś): TAK/NIE
- Jeśli NIE → temat DFlash ZAMKNIĘTY (dwie przegrane konfiguracje)
- Stack na koniec: pełny restore z repo compose: TAK/NIE
- Odstępstwa od planu:
EOF
${EDITOR:-nano} "$RUN_DIR/NOTES.md"

git status
find "$RUN_DIR" -name 'engine_env_*' -exec grep -l "HUGGING_FACE_HUB_TOKEN=hf_" {} \; \
  && echo "STOP: token w artefaktach — popraw redakcję przed commitem"
git add "$RUN_DIR"
git commit -m "bench: DFlash k=4 vs Eagle3 na SWE custom - c1/c32, akceptacja per bench"
git push -u origin main
```

---

## Po sesji (laptop, poza slotem)

1. Delty akceptacji z par `metrics_spec_*` (per bench, per pozycja) + werdykt
   bramki; przy TAK — zmiana spec-config w compose osobnym commitem.
2. Eagle3 c1-SWE @0.26 vs 7,44 @0.20 — pierwszy prawomocny punkt ciągłości c1
   między wersjami (caveat: dzień + util, ale zestaw ten sam).
3. `sync-state`.

## Wątki otwarte (nie w tym slocie)

- Komentarz do vllm#46253 — treść gotowa (08-07), wkleja właściciel.
- Migracja DeepSeeka (`vllm-small`) na 0.26 — osobna decyzja.
- Write-up A/B drafterów (k=8 + k=4 razem — pełniejsza historia).

---

## Walidacja planu

```text
git diff --check    (docs-only; skrypty są heredocami wewnątrz planu)
```

## Checklista artefaktów (commit do repo)

- [ ] `session/`: `start_commit.txt`, `nvidia_smi_{start,dflash4,end}.txt`, `restore_ps.txt`, `end_commit.txt`
- [ ] `engine_image_*`, `engine_cmd_*.json`, `engine_env_*` (redakcja!), `log_*_{error,verdict}.txt` dla obu startów
- [ ] `smoke_dflash4.json`
- [ ] `bench/`: `dflash4_c1.json`, `dflash4_c32_b{1,2}.json`, `eagle3_c1_swe.json`, `eagle3_c32_b{1,2}.json`
- [ ] `metrics_spec_{dflash4,eagle3}_0{0,1,2,3}_*.txt` (snapshoty per bench)
- [ ] `NOTES.md` — tabela + DECYZJA bramki **wypełnione**
- [ ] pełne logi lokalnie w `~/working/nanoserve-diag/2026-08-10_kimi_dflash_k4_swe/` (NIE do repo)
