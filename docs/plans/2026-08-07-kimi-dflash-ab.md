# Sesja serwerowa 2026-08-07/08 — DFlash vs Eagle3: A/B draftera dla Kimi K2.6 @ vLLM 0.26

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, NVLink 4-way: wyspy GPU 0-3 / 4-7)
**Slot (założenie):** ~90 min (2 starty silnika + 4-5 benchy + restore stacku).
**Kontekst:** Kimi na v0.26.0 z workaroundem `fuse_allreduce_rms=false` (adopcja
`results/raw/2026-08-07_kimi_v026_adopcja/`, bramka 676 tok/s c32 warm). Próba
draftera **DFlash** (`nvidia/Kimi-K2.6-DFlash`, drafting blokowy dyfuzyjny,
`num_speculative_tokens: 8`) jako zamiennika Eagle3 — wsparcie w vLLM ≥0.20
(PR #38300, #39930), config-only. Decyzja użytkownika odblokowuje wyjątek od
granicy scope „spec decoding poza baseline Eagle3".

> **Plan jest samowystarczalny** — wszystkie helpery i komendy inline.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH.
> **Świeży shell SSH.** Koniec sesji = **restore pełnego stacku** (Eagle3 z repo
> compose) — noga A/B Eagle3 robi za restore-start, seria „down" zakończona.

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

Odniesienia: Eagle3 na 0.26 c32 = 645 zimny / **676 warm** (wczoraj); Eagle3 c1
TPOT med = 7,44 ms (0.20, 07-31 — **cross-day/cross-version**, stąd noga Eagle3
c1 mierzona DZIŚ w tej samej sesji; lekcja dryfu dnia ~13% z 08-03). Szum ±6%.
Marketing NVIDII (15× Blackwell/gpt-oss) nie przenosi się wprost; realny punkt
odniesienia: ~2× interaktywności vs EAGLE-3.

| pomiar | predykcja | odczyt |
|---|---|---|
| start dflash (overlay) | PASS — config-only swap na 0.26; workaround fuzji zostaje | FAIL → zrzuty jak w serii diagnostycznej i KONIEC (aparat mamy); możliwa klasa #47561 na świeżym kodzie draftera |
| warning `max_num_scheduled_tokens` | wystąpi (8 tok/seq × 32 seq > budżet 4096) — **zanotować, NIE tunować** (jedna zmienna na sesję) | brak warninga → też zanotuj |
| dflash c1 TPOT med | **3,5–6,5 ms**, jeśli drafting blokowy działa jak reklamowany (~2× vs Eagle3) | ≥ Eagle3-dziś → DFlash nie wygrywa latencji na tym modelu/Hopperze |
| Eagle3-dziś c1 TPOT med | 6,5–8,5 ms (kotwica A/B; 7,44 na 0.20) | poza pasmem → dryf wersji 0.26 w reżimie c1, zanotuj |
| dflash c32 warm | **600–780 tok/s**; przy c32 weryfikacja kosztuje compute, więc zysk mały lub ujemny | — |
| akceptacja draftów | `spec_decode_*` z /metrics: średnia akceptowana długość bloku — raport (Eagle3 miał ~stabilną akceptację przy 3) | metryki brak/zerowe → zanotuj, to też wynik |

**Bramka adopcji DFlash do compose:** (c1 TPOT ≤ 0,85× Eagle3-dziś) **ORAZ**
(c32 warm ≥ 640 = 676−6%). Oba warunki → podmiana spec-config w compose (praca
laptopowa po sesji). Inaczej: **zostaje Eagle3**, a wyniki idą do write-upu jako
pierwszy czysty A/B drafterów. Decyzję wpisz w NOTES.

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. 0 | start, pull, snapshoty, zmienne | 4 |
| Cz. H | helpery | 2 |
| Cz. 3 | pobranie draftu z HF (w tle od razu w Cz. 0) + start dflash + verify | 18 |
| Cz. 4 | benche dflash: c1 → c32 b1 → c32 b2 (+ snapshot /metrics) | 30 |
| Cz. 5 | restart na Eagle3 (repo compose) + c1 dziś (+ opcja c32 dziś) | 22 |
| Cz. 6 | restore reszty stacku, bramka, NOTES, commit/push | 12 |
| | **razem** | **~88** |

**Kolejność cięcia:** Cz. 5 opcja c32-Eagle3-dziś (wczorajsze 676 wystarczy) →
Cz. 4 b1 (wtedy c32 tylko warm po c1). **Nietykalne:** Cz. 3, Cz. 4 c1 + c32
warm, Cz. 5 c1, Cz. 6.

---

## Cz. 0 — start (4 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main
unset RUN_DIR OUT SESSION QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_ARGS

RUN_DIR=results/runs/2026-08-07_kimi_dflash_ab
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
DIAG=~/working/nanoserve-diag/2026-08-07_kimi_dflash_ab
SWE=results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl
mkdir -p "$RUN_DIR/session" "$RUN_DIR/bench" "$DIAG"
set -a; source .env; set +a

# FAIL-FAST: compose ma być na 0.26 z workaroundem (baza tej sesji)
grep -q 'v0.26.0' "$COMPOSE" && grep -q 'fuse_allreduce_rms' "$COMPOSE" \
  || echo "STOP: compose bez adopcji 0.26 — zła baza"

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"

# pobranie draftera W TLE od razu (mały model, ale nie blokujmy się na starcie silnika);
# nowsze obrazy mają CLI `hf` zamiast `huggingface-cli` — próbujemy obu
docker run --rm -e HUGGING_FACE_HUB_TOKEN="$HF_TOKEN" -e HF_HUB_ENABLE_HF_TRANSFER=1 \
  -v /home/ubuntusrv2/.vllm/models:/root/.cache/huggingface \
  --entrypoint bash vllm/vllm-openai:v0.26.0 \
  -c 'huggingface-cli download nvidia/Kimi-K2.6-DFlash || hf download nvidia/Kimi-K2.6-DFlash' \
  > "$DIAG/hf_download_dflash.log" 2>&1 &
DL_PID=$!
```

---

## Cz. H — helpery (wklej cały blok, 2 min)

Sprawdzone w sesjach 08-03/08-07.

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
  grep -n -E "Graph capturing finished|Application startup complete|speculative|max_num_scheduled_tokens" \
    "$DIAG/log_full_$1.txt" | tail -n 8 > "$RUN_DIR/log_$1_verdict.txt"
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

ensure_dataset () {   # dataset SWE do kontenera + WERYFIKACJA (po KAŻDYM recreate)
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

kimi_c1 () {   # $1=nazwa pliku wyniku — reżim latencji (random 64/512, 3 warmupy)
  docker compose -f "$COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
      --dataset-name random --random-input-len 64 --random-output-len 512 \
      --ignore-eos --num-warmups 3 --num-prompts 40 --max-concurrency 1 \
      --save-result --result-dir /tmp/kbench --result-filename '"$1"'.json'
}

kimi_c32 () {  # $1=nazwa pliku wyniku — reżim batched (SWE 384)
  docker compose -f "$COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
      --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
      --custom-output-len 256 --ignore-eos --num-warmups 2 \
      --num-prompts 384 --max-concurrency 32 \
      --save-result --result-dir /tmp/kbench --result-filename '"$1"'.json'
}

spec_metrics () {  # $1=etykieta — snapshot metryk spec-decode
  curl -s http://127.0.0.1:8000/metrics | grep -iE "spec_decode|accept" \
    > "$RUN_DIR/metrics_spec_$1.txt"
  [ -s "$RUN_DIR/metrics_spec_$1.txt" ] || echo "# brak metryk spec_decode w /metrics" > "$RUN_DIR/metrics_spec_$1.txt"
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

## Cz. 3 — start Kimi z DFlash przez overlay (18 min)

Overlay = pełna kanoniczna komenda 0.26 (z workaroundem fuzji!) z podmienionym
TYLKO `--speculative-config`. Compose w repo nietykalny do decyzji bramki.

```bash
[ -n "${DL_PID:-}" ] && wait "$DL_PID"                 # (guard: świeży shell nie ma DL_PID)
tail -2 "$DIAG/hf_download_dflash.log"                 # download draftu skończony?

cat > /tmp/kimi-dflash.yml <<'EOF'
services:
  vllm:
    restart: "no"
    command:
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size 8 --gpu-memory-utilization 0.6 --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2 --enable-auto-tool-choice --language-model-only --max-num-seqs 32 --max-model-len 131072 --max-num-batched-tokens 4096 --speculative-config='{"method":"dflash","model":"nvidia/Kimi-K2.6-DFlash","num_speculative_tokens":8}' --compilation-config='{"pass_config":{"fuse_allreduce_rms":false}}'
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-dflash.yml up -d --force-recreate vllm

# FAIL-FAST: dawka w runtime (lekcja 06-11). UWAGA: wyjście `inspect '{{json ...}}'`
# escapuje cudzysłowy JSON-a (\"method\") — wzorce muszą być gołymi tokenami bez cudzysłowów
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qo 'dflash' \
  || echo "STOP: spec-config dflash nie wszedł do cmd"
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qo 'fuse_allreduce_rms' \
  || echo "STOP: workaround fuzji wypadł z komendy — NIE startuj bez niego"

czekaj
zrzut dflash_start
smoke > "$RUN_DIR/smoke_dflash.json" 2>&1
```

**Jeśli start padnie na walidacji spec-configu** (nie CUDA, tylko argparse —
np. drafter wymaga jawnego `max_model_len`): dopisz do spec-configu
`,"max_model_len":8192` i jedna powtórka. Każdy inny FAIL → zrzuty i koniec
(analiza laptopowa); Eagle3 wraca w Cz. 5/6 tak czy inaczej.

---

## Cz. 4 — benche DFlash (30 min)

Kolejność: c1 (z 3 warmupami — robi też za wygrzewkę silnika) → c32 b1 → c32 b2.
Do bramki liczą się c1 oraz **c32 b2 (warm)** — symetrycznie do wczorajszej
ścieżki Eagle3 (645 zimny → 676 warm).

```bash
bench_prereqs || echo "PRZERWIJ — prereqs nie przeszły"

kimi_c1  dflash_c1
kimi_c32 dflash_c32_b1
kimi_c32 dflash_c32_b2
spec_metrics dflash

docker compose -f "$COMPOSE" cp vllm:/tmp/kbench/. "$RUN_DIR/bench/"
docker logs vllm > "$DIAG/log_full_dflash_bench.txt" 2>&1
nvidia-smi > "$RUN_DIR/session/nvidia_smi_dflash.txt"
show_bench "$RUN_DIR/bench"
```

---

## Cz. 5 — noga A/B: Eagle3 DZIŚ (22 min)

Repo compose = Eagle3 na 0.26; ten restart jest jednocześnie początkiem restore.
Kotwica c1 mierzona tego samego dnia neutralizuje dryf dzienny; c32-dziś jest
opcją (wczorajsze 676 to akceptowalne odniesienie).

```bash
docker compose -f "$COMPOSE" up -d --force-recreate vllm
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qo 'eagle3' \
  || echo "STOP: to nie jest config Eagle3 z repo"
czekaj
zrzut eagle3_dzis

bench_prereqs || echo "PRZERWIJ"
kimi_c1 eagle3_c1_dzis
# OPCJA (tnij pierwszą): c32 warm dziś dla czystego A/B w batched
kimi_c32 eagle3_c32_dzis
spec_metrics eagle3

docker compose -f "$COMPOSE" cp vllm:/tmp/kbench/. "$RUN_DIR/bench/"
show_bench "$RUN_DIR/bench"
```

---

## Cz. 6 — restore reszty stacku, bramka, commit (12 min)

```bash
# pełny stack: Kimi (Eagle3, już stoi) + DeepSeek + LiteLLM + OpenWebUI
docker compose -f "$COMPOSE" up -d vllm-small litellm open-webui
wait_http_health http://127.0.0.1:8000/health 240 5 && echo "kimi OK"
wait_http_health http://127.0.0.1:8004/health 240 5 && echo "deepseek OK"
docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/restore_ps.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
git rev-parse HEAD > "$RUN_DIR/session/end_commit.txt"

cat > "$RUN_DIR/NOTES.md" <<'EOF'
# Werdykty 2026-08-07/08 — A/B DFlash vs Eagle3 (Kimi @ 0.26)
| pomiar | DFlash | Eagle3 (dziś) | Eagle3 (wczoraj) |
|---|---|---|---|
| c1 TPOT med (ms) | | | 7,44 (0.20, 07-31) |
| c32 warm (tok/s) | | (opcja) | 676 |
| akceptacja draftów | | | ~stabilna @3 |
| warning scheduled_tokens | | | tak |
- BRAMKA (c1 ≤0,85× Eagle3-dziś ORAZ c32 ≥640): DFlash wchodzi do compose TAK/NIE
- Stack na koniec: pełny restore (Kimi Eagle3 + DeepSeek + proxy + WebUI): TAK/NIE
- Odstępstwa od planu:
EOF
${EDITOR:-nano} "$RUN_DIR/NOTES.md"

git status
find "$RUN_DIR" -name 'engine_env_*' -exec grep -l "HUGGING_FACE_HUB_TOKEN=hf_" {} \; \
  && echo "STOP: token w artefaktach — popraw redakcję przed commitem"
git add "$RUN_DIR"
git commit -m "bench: A/B drafterow Kimi - DFlash vs Eagle3 na vLLM 0.26 (c1 + c32, akceptacja)"
git push -u origin main
```

---

## Po sesji (laptop, poza slotem)

1. Analiza A/B → decyzja bramki; jeśli DFlash wygrał: podmiana spec-config w
   compose (osobny commit infra) + restart Kimi w kolejnym touchu.
2. Wyniki do materiału write-upowego (pierwszy czysty A/B drafterów na tym
   stacku; kontekst firmowego Kimi Eagle3 baseline z roadmapy).
3. `docs/operations/agent-state.md` — `sync-state`.

## Wątki otwarte (nie w tym slocie)

- Tuning `max-num-batched-tokens` pod 8 tokenów draftu (jeśli warning potwierdzi
  presję budżetu) — osobna sesja, dopiero po decyzji o adopcji DFlash.
- Migracja DeepSeeka (`vllm-small`) na 0.26 — osobna decyzja; dziś wraca na 0.20.
- Komentarz do vllm#46253 — treść gotowa (rozmowa 08-07), wkleja właściciel.

---

## Walidacja planu

```text
git diff --check    (docs-only; skrypty są heredocami wewnątrz planu)
```

## Checklista artefaktów (commit do repo)

- [ ] `session/`: `start_commit.txt`, `nvidia_smi_start.txt`, `nvidia_smi_dflash.txt`, `restore_ps.txt`, `nvidia_smi_end.txt`, `end_commit.txt`
- [ ] `engine_image_*`, `engine_cmd_*.json`, `engine_env_*` (redakcja!), `log_*_error.txt`, `log_*_verdict.txt` dla obu startów
- [ ] `smoke_dflash.json`
- [ ] `bench/`: `dflash_c1.json`, `dflash_c32_b{1,2}.json`, `eagle3_c1_dzis.json` (+ `eagle3_c32_dzis.json` jeśli nie ucięte)
- [ ] `metrics_spec_dflash.txt`, `metrics_spec_eagle3.txt`
- [ ] `NOTES.md` — tabela A/B + DECYZJA bramki **wypełnione**
- [ ] pełne logi lokalnie w `~/working/nanoserve-diag/2026-08-07_kimi_dflash_ab/` (NIE do repo)
