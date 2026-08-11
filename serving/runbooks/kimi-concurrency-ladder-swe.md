# Benchmark schodkowy Kimi (c=1/16/32/64) na zestawie SWE + observability — runbook

Cel: jednym przebiegiem (a) **sprawdzić albo postawić** stack — Kimi, Prometheus,
Grafanę, (b) przejechać **drabinkę współbieżności c=1 → 16 → 32 → 64** na
przygotowanym zestawie SWE-bench Lite (nie `random`), (c) zebrać komplet
artefaktów: JSON-y klienta, akceptację spekulacji per szczebel, cross-check z
Prometheusa per okno i screen dashboardu pod obciążeniem.

**Maszyna:** ubuntusrv2 (8×H200 NVL, NVLink 4-way: wyspy GPU 0-3 / 4-7).
**Czas:** ~45 min przy ciepłym stacku, ~65-70 min jeśli Kimi trzeba podnieść od zera.
**Powtarzalny** — to przepis, nie zapis sesji. Zapis konkretnego biegu ląduje w
`results/runs/<data>_kimi_steps/NOTES.md`.

> **Runbook jest samowystarczalny** — wszystkie helpery inline, nic nie trzeba
> doklejać z innych plików.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH; `exit`
> wywala połączenie, `-e` ubija shell na pierwszym niegroźnym `grep`.
> **Świeży shell SSH.** Wklejaj częściami, czytaj kryteria OK po każdej.

---

## Założenia i świadome decyzje

1. **Zestaw testowy = SWE-bench Lite 300** (`--dataset-name custom`), 256 tokenów
   wyjścia, `--ignore-eos`. Powód: decyzja z 08-10 — benche Kimiego na `random`
   są nieporównywalne z historią; `random` używamy tylko dla Qwena.
2. **`max-num-seqs 32` zostaje** (domyślny compose). Silnik trzyma ≤32 requestów
   w locie, więc **„c=64" to etykieta workloadu klienta, nie realna głębokość
   batcha** — szczebel c=64 mierzy zachowanie kolejki, a nie szerszy batch. Tak
   samo liczyły baseline'y 06-11 i 07-31, więc porównania są ważne. Realne c=64
   wymaga restartu silnika → **Wariant B** na końcu (świadomy koszt: +20 min i
   utrata porównywalności c32 z 07-31/08-07/08-10).
3. **Wygrzewka jest obowiązkowa** (`benchmark-methodology.md`, „Engine warm-up
   rule"): pierwszy bench po starcie silnika płaci 10-15%. Robimy bench na
   odrzut przed drabinką **zawsze** — jeśli stack już stał i był ciepły, kosztuje
   to 25 s; jeśli właśnie wstał, ratuje cały pomiar.
4. **Prometheus to cross-check, nie źródło prawdy.** Liczby wiodące są z
   `--save-result` klienta; TSDB służy do peaków kolejki/KV i do planu B, gdyby
   JSON-y przepadły.
5. **Nazwy metryk zweryfikowane dla vLLM 0.20**, Kimi jedzie na **0.26** —
   dlatego §1 zrzuca `metrics_names.txt`, a zapytania w §6 są best-effort
   (brak serii → `n/a`, nie błąd).

---

## Cz. 0 — zmienne i env (2 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main
unset RUN_DIR OUT SESSION QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_ARGS

DATE=$(date +%F)
RUN_DIR="results/runs/${DATE}_kimi_steps"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
OBS="serving/compose/docker-compose.observability.yml"
SWE=results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl
DIAG=~/working/nanoserve-diag/${DATE}_kimi_steps
PROMQ=http://127.0.0.1:9090/api/v1/query
mkdir -p "$RUN_DIR/session" "$RUN_DIR/bench" "$DIAG"

# .env: repo-root, a jak nie ma - ten przy compose
if [ -f .env ]; then set -a; . ./.env; set +a
elif [ -f serving/compose/.env ]; then set -a; . ./serving/compose/.env; set +a
else echo "STOP: brak .env - compose Kimiego wymaga HF_TOKEN i LITELLM_MASTER_KEY"; fi

[ -n "$HF_TOKEN" ]                || echo "STOP: HF_TOKEN pusty"
[ -n "$LITELLM_MASTER_KEY" ]      || echo "STOP: LITELLM_MASTER_KEY pusty"
[ -n "$GRAFANA_RENDERER_TOKEN" ]  || echo "UWAGA: brak GRAFANA_RENDERER_TOKEN - observability up SIE NIE PODNIESIE (compose ma :?)"
[ -s "$SWE" ] || echo "STOP: brak zestawu SWE pod $SWE"

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"
```

**OK:** żadnego `STOP:`; `$RUN_DIR` istnieje; `wc -l $SWE` = 300.

---

## Cz. H — helpery (wklej cały blok, 2 min)

Przeniesione ze sprawdzonych planów 08-03 / 08-07 / 08-10; nowe są tylko
`ensure_kimi`, `ensure_obs`, `kimi_bench` (drabinka z tagiem) i `prom_rung`.

```bash
wait_http_health () {   # $1=url $2=proby $3=przerwa(s)
  url="$1"; attempts="$2"; pause="$3"
  for _ in $(seq 1 "$attempts"); do
    curl -fsS "$url" >/dev/null 2>&1 && return 0
    sleep "$pause"
  done
  echo "health timeout: $url" >&2
  return 1
}

ensure_kimi () {        # idempotentnie: stoi -> nic; nie stoi -> up -d
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "kimi: JUZ DZIALA (bez restartu)"; KIMI_FRESH=0
  else
    echo "kimi: nie odpowiada - podnosze pelny stack z repo compose"
    docker compose -f "$COMPOSE" up -d
    KIMI_FRESH=1
    wait_http_health http://127.0.0.1:8000/health 360 5 \
      || { echo "STOP: kimi nie wstal w 30 min - patrz 'docker logs vllm'"; return 1; }
    echo "kimi: WSTAL"
  fi
  docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/ps_serving.txt"
}

ensure_obs () {         # prometheus + grafana; sieć nanoserve-net jest external
  docker network inspect nanoserve-net >/dev/null 2>&1 \
    || { echo "STOP: brak sieci nanoserve-net - najpierw ensure_kimi"; return 1; }
  ok_p=0; ok_g=0
  curl -fsS http://127.0.0.1:9090/-/healthy  >/dev/null 2>&1 && ok_p=1
  curl -fsS http://127.0.0.1:3001/api/health >/dev/null 2>&1 && ok_g=1
  if [ "$ok_p" = 1 ] && [ "$ok_g" = 1 ]; then
    echo "observability: JUZ DZIALA (prometheus+grafana)"
  else
    echo "observability: podnosze (prom=$ok_p grafana=$ok_g)"
    docker compose -f "$OBS" up -d
    wait_http_health http://127.0.0.1:9090/-/healthy  60 5 || echo "WARN: prometheus nie wstal"
    wait_http_health http://127.0.0.1:3001/api/health 60 5 || echo "WARN: grafana nie wstala"
  fi
  docker compose -f "$OBS" ps | tee "$RUN_DIR/session/ps_observability.txt"
}

ensure_dataset () {
  docker cp "$SWE" vllm:/tmp/swe_bench_vllm.jsonl \
    || { echo "STOP: docker cp nie zadzialal - czy kontener 'vllm' stoi?"; return 1; }
  n=$(docker exec vllm sh -c 'wc -l < /tmp/swe_bench_vllm.jsonl' 2>/dev/null | tr -d ' ')
  echo "dataset w kontenerze: ${n:-BRAK} linii"
  { [ -n "$n" ] && [ "$n" -gt 100 ]; } \
    || { echo "STOP: dataset nie dotarl - NIE benchuj"; return 1; }
}

bench_prereqs () {      # po kazdym recreate: pip i /tmp nie przezywaja
  ensure_dataset || return 1
  docker compose -f "$COMPOSE" exec vllm bash -c \
    'rm -rf /tmp/kbench; mkdir -p /tmp/kbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "print(\"deps ok\")"'
}

kimi_bench () {         # $1=concurrency $2=num_prompts $3=num_warmups $4=tag
  docker exec vllm test -s /tmp/swe_bench_vllm.jsonl \
    || { echo "BRAK datasetu - uruchom ensure_dataset"; return 1; }
  t0=$(date +%s)
  docker compose -f "$COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
      --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
      --custom-output-len 256 --ignore-eos \
      --percentile-metrics ttft,tpot,itl,e2el --metric-percentiles 50,95,99 \
      --num-warmups '"$3"' --num-prompts '"$2"' --max-concurrency '"$1"' \
      --save-result --result-dir /tmp/kbench --result-filename '"$4"'.json'
  st=$?
  t1=$(date +%s)
  [ "$st" -ne 0 ] && echo "WARN: bench $4 zwrocil $st"
  printf '%s\t%s\t%s\t%s\t%s\n' "$4" "$1" "$2" "$t0" "$t1" >> "$RUN_DIR/windows.tsv"
  echo "okno $4: $t0 -> $t1 ($((t1-t0))s)"
}

spec_snap () {          # $1=etykieta - liczniki spec sa KUMULATYWNE, delty liczy laptop
  curl -s http://127.0.0.1:8000/metrics | grep -E "spec_decode.*_total" \
    > "$RUN_DIR/metrics_spec_$1.txt"
  [ -s "$RUN_DIR/metrics_spec_$1.txt" ] || echo "# brak metryk spec_decode" > "$RUN_DIR/metrics_spec_$1.txt"
}

show_bench () {
  python3 - "$1" <<'PYEOF'
import glob, json, sys
for f in sorted(glob.glob(sys.argv[1] + "/*.json")):
    d = json.load(open(f))
    print(f"{f.split('/')[-1]:26s} tok/s {d.get('output_throughput', 0):7.1f}"
          f" | TTFT p50 {d.get('median_ttft_ms', 0):8.1f}"
          f" | TPOT med {d.get('median_tpot_ms', 0):6.2f}"
          f" | ITL med {d.get('median_itl_ms', 0):7.2f}"
          f" | in_tok {d.get('total_input_tokens', 0):7d}"
          f" | done {d.get('completed', 0)}")
PYEOF
}

prom_rung () {          # $1=tag $2=start_epoch $3=end_epoch - cross-check per szczebel
  tag="$1"; s="$2"; e="$3"; d=$(( e - s )); [ "$d" -lt 15 ] && d=15
  M='model_name="kimi-k2.6"'
  qq () {   # $1=promql $2=etykieta ; okno konczy sie w $e
    curl -s --data-urlencode "query=$1" --data-urlencode "time=$e" "$PROMQ" \
      | jq -r --arg L "$2" '[.data.result[]?.value[1]]
          | (if length==0 then "n/a" else join(" ") end) | "  \($L): \(.)"'
  }
  {
    echo "## $tag  okno ${s}..${e} (${d}s)"
    qq "max_over_time(vllm:num_requests_running{$M}[${d}s])"                  "peak running"
    qq "max_over_time(vllm:num_requests_waiting{$M}[${d}s])"                  "peak waiting"
    qq "max_over_time(vllm:kv_cache_usage_perc{$M}[${d}s])*100"               "peak KV %"
    qq "increase(vllm:generation_tokens_total{$M}[${d}s])/${d}"               "gen tok/s (srednia okna)"
    qq "histogram_quantile(0.50, sum by (le)(increase(vllm:time_to_first_token_seconds_bucket{$M}[${d}s])))" "TTFT p50 s"
    qq "histogram_quantile(0.95, sum by (le)(increase(vllm:time_to_first_token_seconds_bucket{$M}[${d}s])))" "TTFT p95 s"
    qq "histogram_quantile(0.50, sum by (le)(increase(vllm:inter_token_latency_seconds_bucket{$M}[${d}s])))" "ITL p50 s"
    qq "histogram_quantile(0.95, sum by (le)(increase(vllm:e2e_request_latency_seconds_bucket{$M}[${d}s])))" "E2E p95 s"
    qq "increase(vllm:spec_decode_num_accepted_tokens_total{$M}[${d}s]) / increase(vllm:spec_decode_num_draft_tokens_total{$M}[${d}s])" "akceptacja spec"
    qq "increase(vllm:num_preemptions_total{$M}[${d}s])"                      "preemptions"
    echo
  } >> "$RUN_DIR/prometheus_rungs.txt"
}
```

**OK:** blok wkleja się bez błędu składni; `type ensure_kimi` zwraca definicję.

---

## Cz. 1 — sprawdź / postaw stack (5 min ciepły, do 30 min zimny)

Kolejność jest wymuszona: `docker-compose.observability.yml` ma sieć
`nanoserve-net` jako **external**, więc compose Kimiego musi ją najpierw stworzyć.

```bash
ensure_kimi || echo "PRZERWIJ - bez silnika nie ma czego benchowac"
ensure_obs  || echo "UWAGA - benche pojada, ale bez cross-checku z Prometheusa"

# FAIL-FAST: czy to na pewno produkcyjna konfiguracja z repo?
docker inspect vllm --format '{{.Config.Image}}' | tee "$RUN_DIR/engine_image.txt"
docker inspect vllm --format '{{json .Config.Cmd}}' > "$RUN_DIR/engine_cmd.json"
docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | sed -E 's/^(HUGGING_FACE_HUB_TOKEN|HF_TOKEN|[A-Z_]*API_KEY|[A-Z_]*SECRET[A-Z_]*)=.*/\1=REDACTED/' \
  > "$RUN_DIR/engine_env.txt"
grep -qo 'eagle3'              "$RUN_DIR/engine_cmd.json" || echo "STOP: silnik nie ma Eagle3 - to nie jest baseline"
grep -qo 'fuse_allreduce_rms'  "$RUN_DIR/engine_cmd.json" || echo "STOP: brak workaroundu fuzji (0.26 sypie sie na TP8)"
grep -qo 'max-num-seqs., .32'  "$RUN_DIR/engine_cmd.json" || echo "UWAGA: max-num-seqs != 32 - zanotuj, zmienia sens szczebla c=64"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$RUN_DIR/verify_tp.txt"
grep -q "tensor_parallel_size=8" "$RUN_DIR/verify_tp.txt" || echo "STOP: TP MISMATCH"

# smoke + inwentarz nazw metryk (0.26 mogl je poprzestawiac wzgledem 0.20)
curl -s http://localhost:8000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"kimi-k2.6","messages":[{"role":"user","content":"2+2?"}],"max_tokens":8}' \
  > "$RUN_DIR/smoke.json" 2>&1
curl -s http://127.0.0.1:8000/metrics | grep -E '^# HELP vllm:' | sed 's/^# HELP //' \
  > "$RUN_DIR/metrics_names.txt"

# czy Prometheus faktycznie scrape'uje silnik
curl -s http://127.0.0.1:9090/api/v1/targets \
  | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}' \
  | tee "$RUN_DIR/session/prom_targets.txt"
```

**OK:** `smoke.json` ma `"content"`; brak `STOP:`; `metrics_names.txt` niepusty;
target `vllm-kimi` ma `health: "up"` (`vllm-small`/`litellm` mogą być `down` —
nie blokuje). Zanotuj `KIMI_FRESH` (`echo $KIMI_FRESH`): `1` = silnik wstał w tej
sesji, więc wygrzewka jest krytyczna.

---

## Cz. 2 — prereqs w kontenerze (3 min)

Obraz vLLM nie ma extras do benchu, a bench bez offline-env dzwoni do HF.

```bash
bench_prereqs || echo "PRZERWIJ - prereqs nie przeszly"
```

**OK:** `deps ok` na wyjściu i `dataset w kontenerze: 300 linii`.
Gdy krzyknie o kolejny moduł — dorzuć `pyarrow`/`pillow` do `pip install`.
**NIE** rób `pip install vllm[bench]` (przeinstaluje vllm+torch i rozwali serwer).

---

## Cz. 3 — wygrzewka na odrzut (2 min, OBOWIĄZKOWA)

```bash
kimi_bench 32 64 2 warmup_discard
spec_snap 00_baseline
```

**OK:** bench kończy się podsumowaniem. Liczby z `warmup_discard` **nie wchodzą
do tabeli** — plik zostaje w repo tylko jako dowód, że wygrzewka była.

---

## Cz. 4 — drabinka c=1 → 16 → 32 → 64 (~13 min)

Back-to-back, bez restartów. `spec_snap` po każdym szczeblu — liczniki
spekulacji są kumulatywne, więc akceptacja per szczebel to różnica sąsiednich
snapshotów (liczy laptop po sesji).

| szczebel | prompty | fale | dlaczego tyle |
|---|---:|---:|---|
| c=1  |  24 | 24 | bit-zgodność z 07-31 / 08-10 (`total_input_tokens` = **48479**) |
| c=16 | 192 | 12 | ten sam rozmiar co „nietykalny" c16 z 08-03 |
| c=32 | 384 | 12 | ten sam rozmiar co 07-31 / 08-07 / 08-10 (`in_tok` = **339979**) |
| c=64 | 768 | 12 | 12 fal jak wyżej — równa waga statystyczna szczebla |

```bash
kimi_bench 1  24  3 c01 ; spec_snap 01_po_c1
kimi_bench 16 192 2 c16 ; spec_snap 02_po_c16
kimi_bench 32 384 2 c32 ; spec_snap 03_po_c32
kimi_bench 64 768 2 c64 ; spec_snap 04_po_c64

nvidia-smi > "$RUN_DIR/session/nvidia_smi_po_drabince.txt"
cat "$RUN_DIR/windows.tsv"
```

**OK po każdym szczeblu:** `completed` = liczba promptów (24/192/384/768),
`windows.tsv` dostaje wiersz z epokami.

**Kryteria sanity (odniesienia historyczne, patrz tabela na końcu):**
c=1 TPOT med **7-9 ms** i `in_tok` **48479**; c=32 throughput **≥600 tok/s**
(historia: 649 @0,65 i 676 @0,60 na 0.26; 594 na 0.20) i `in_tok` **339979**.
Odchyłka > ~6% od tych wartości to nie „szum" — zanotuj w `NOTES.md` zamiast
tłumaczyć ją po fakcie.

**Screen Grafany:** rób go **w trakcie szczebla c=64** (wtedy `Requests waiting`
odbija od zera przy `max-num-seqs 32`) — patrz Cz. 6.

---

## Cz. 5 — zbierz artefakty (5 min)

> ⚠️ **NAJPIERW `cp`, POTEM cokolwiek z compose.** `--save-result` pisze do
> `/tmp/kbench` **wewnątrz kontenera**; `down`, a nawet `up -d` po zmianie
> configu, kasuje warstwę kontenera i JSON-y przepadają bezpowrotnie.

```bash
docker compose -f "$COMPOSE" cp vllm:/tmp/kbench/. "$RUN_DIR/bench/"
show_bench "$RUN_DIR/bench" | tee "$RUN_DIR/bench_summary.txt"
docker logs -t vllm > "$DIAG/log_full_steps.txt" 2>&1        # pelny log lokalnie, NIE do repo
grep -n -E "Graph capturing finished|Application startup complete|speculative|preempt" \
  "$DIAG/log_full_steps.txt" | tail -n 10 > "$RUN_DIR/log_verdict.txt"
```

**OK:** 5 plików w `$RUN_DIR/bench/` (`warmup_discard`, `c01`, `c16`, `c32`,
`c64`), każdy z `done` = oczekiwana liczba promptów.

---

## Cz. 6 — cross-check z Prometheusa + Grafana (8 min)

### 6a. Podsumowanie serwerowe per szczebel

```bash
: > "$RUN_DIR/prometheus_rungs.txt"
while IFS=$'\t' read -r tag c np s e; do
  [ "$tag" = "warmup_discard" ] && continue
  prom_rung "$tag" "$s" "$e"
done < "$RUN_DIR/windows.tsv"
cat "$RUN_DIR/prometheus_rungs.txt"
```

**OK:** każdy szczebel ma blok z peakami. Oczekiwane: `peak running` rośnie
1 → 16 → 32 → **32** (sufit `max-num-seqs`), a `peak waiting` startuje z zera i
przy c=64 **wyraźnie > 0** — to jest dowód, że c=64 mierzy kolejkę, nie batch.
Jeśli któraś pozycja to `n/a` — sprawdź nazwę w `metrics_names.txt` (0.26 mogło
zmienić nazwę względem 0.20) i popraw zapytanie zamiast zgadywać.

### 6b. Screen dashboardu

W UI: `http://<serwer>:3001`, login `admin` / `$GRAFANA_ADMIN_PASSWORD`,
dashboard **vLLM Phase 1 — nanoserve-mini**, zakres **Last 30 minutes**,
refresh **5s**. Zrzut ręczny (`Win+Shift+S` przez RDP) w trakcie c=64 jest w
pełni wystarczający → zapisz jako `$RUN_DIR/grafana_steps.png`.

Wariant headless (renderer stoi w compose observability) — obejmuje całą
drabinkę z `windows.tsv`:

```bash
DS_UID=$(curl -s -u "admin:${GRAFANA_ADMIN_PASSWORD:-admin}" \
  http://127.0.0.1:3001/api/datasources | jq -r '.[] | select(.type=="prometheus") | .uid' | head -1)
FROM=$(( $(head -1 "$RUN_DIR/windows.tsv" | cut -f4) * 1000 - 60000 ))
TO=$((   $(tail -1 "$RUN_DIR/windows.tsv" | cut -f5) * 1000 + 60000 ))
curl -s -u "admin:${GRAFANA_ADMIN_PASSWORD:-admin}" -o "$RUN_DIR/grafana_steps.png" \
  "http://127.0.0.1:3001/render/d/nanoserve-vllm-phase1/?from=${FROM}&to=${TO}&width=1920&height=1400&kiosk&var-datasource=${DS_UID}"
file "$RUN_DIR/grafana_steps.png"
```

**OK:** `file` mówi `PNG image data`, a na obrazku widać cztery schodki
obciążenia. Jeśli PNG jest pusty / to JSON z błędem — nie walcz z rendererem,
zrób zrzut ręczny (to nie jest cel sesji). Trzymaj PNG mały; duże artefakty →
tylko ścieżka + instrukcja repro.

---

## Cz. 7 — NOTES i commit (10 min)

```bash
git rev-parse HEAD > "$RUN_DIR/session/end_commit.txt"

cat > "$RUN_DIR/NOTES.md" <<'EOF'
# Drabinka c=1/16/32/64 — Kimi K2.6, zestaw SWE custom

Konfiguracja: vLLM 0.26.0, TP8, Eagle3 k=3, util 0,60, max-num-seqs 32,
`--custom-output-len 256 --ignore-eos`. Wygrzewka: bench 64@c32 na odrzut.
Silnik wstał w tej sesji (KIMI_FRESH): TAK/NIE

| szczebel | tok/s | TTFT p50 (ms) | TPOT med (ms) | ITL med (ms) | in_tok | done | peak waiting (Prom) |
|---|---:|---:|---:|---:|---:|---:|---:|
| c=1  | | | | | | | |
| c=16 | | | | | | | |
| c=32 | | | | | | | |
| c=64 | | | | | | | |

Kontrole:
- c=1 `in_tok` = 48479 (bit-zgodność z 07-31/08-10): TAK/NIE
- c=32 `in_tok` = 339979: TAK/NIE
- c=32 throughput >= 600 tok/s (historia 649/676 @0.26): TAK/NIE
- peak running przy c=64 utknął na 32 (sufit max-num-seqs): TAK/NIE

Akceptacja spekulacji per szczebel (delty `metrics_spec_*`, liczone na laptopie):

Odstępstwa od runbooka / anomalie:
EOF
${EDITOR:-nano} "$RUN_DIR/NOTES.md"

git status
find "$RUN_DIR" -name 'engine_env*' -exec grep -l "HUGGING_FACE_HUB_TOKEN=hf_" {} \; \
  && echo "STOP: token w artefaktach - popraw redakcje przed commitem"
git add "$RUN_DIR"
git commit -m "bench: drabinka c=1/16/32/64 Kimi na zestawie SWE custom + cross-check Prometheus"
git push -u origin main
```

**OK:** `git status` czysty poza `$RUN_DIR`; `find` nie znajduje tokenu.

---

## Wariant B — realne c=64 (opcjonalny, +20 min)

Bierz **tylko** gdy pytaniem sesji jest głębokość batcha, a nie zachowanie
kolejki. Koszt: restart silnika (wygrzewka od nowa, `/tmp` i `pip` znikają) oraz
**utrata porównywalności c=32 z 07-31/08-07/08-10** (inny `max-num-seqs` zmienia
scheduling). Nie mieszaj wyników z tych dwóch wariantów w jednej tabeli.

```bash
cat > /tmp/kimi-seqs64.yml <<'EOF'
services:
  vllm:
    restart: "no"
    command:
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size 8 --gpu-memory-utilization 0.6 --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2 --enable-auto-tool-choice --language-model-only --max-num-seqs 64 --max-model-len 131072 --max-num-batched-tokens 4096 --speculative-config='{"model":"lightseekorg/kimi-k2.6-eagle3-mla","method":"eagle3","num_speculative_tokens":3,"max_model_len":8192}' --compilation-config='{"pass_config":{"fuse_allreduce_rms":false}}'
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-seqs64.yml up -d --force-recreate vllm
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qo 'max-num-seqs., .64' \
  || echo "STOP: max-num-seqs 64 nie wszedl do cmd"
wait_http_health http://127.0.0.1:8000/health 360 5 || echo "STOP: nie wstal"

bench_prereqs || echo "PRZERWIJ"
kimi_bench 32 64 2 warmup_discard_seqs64      # wygrzewka po restarcie - OBOWIAZKOWA
kimi_bench 64 768 2 c64_seqs64 ; spec_snap 05_po_c64_seqs64
docker compose -f "$COMPOSE" cp vllm:/tmp/kbench/. "$RUN_DIR/bench/"

# RESTORE do konfiguracji z repo - nie zostawiaj stacku na overlayu
docker compose -f "$COMPOSE" up -d --force-recreate
wait_http_health http://127.0.0.1:8000/health 360 5 && echo "kimi OK"
wait_http_health http://127.0.0.1:8004/health 240 5 && echo "deepseek OK"
docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/restore_ps.txt"
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qo 'max-num-seqs., .32' \
  || echo "STOP: restore nie przywrocil max-num-seqs 32"
```

---

## Tabela odniesień (historia, do sanity-checku)

| pomiar | wartość | źródło |
|---|---|---|
| c=1 TPOT med, SWE 24 prompty | 7,44 ms | 07-31, vLLM 0.20, util 0,20 |
| c=1 `total_input_tokens`, 24 prompty | 48479 | 07-31 / 08-10 (kontrola bit-zgodności) |
| c=16 ITL med | 48,6 ms (po NVLink) / 512 ms (przed) | 07-31, `2026-08-03-nvlink-day-summary.md` |
| c=32 throughput | 594 (0.20) / 649 (0.26 @0,65) / 676 (0.26 @0,60) tok/s | 07-31, 08-07 |
| c=32 `total_input_tokens`, 384 prompty | 339979 | 07-31 / 08-07 / 08-10 |
| kara za brak wygrzewki | 10-15% (Qwen: 1747-1851 zimne vs 1989-2040 ciepłe) | `benchmark-methodology.md` |

Odniesień nie traktuj jak progów zaliczenia — to detektor zmian: rozjazd większy
niż ~6% oznacza, że coś się zmieniło w konfiguracji, obrazie albo maszynie.

---

## Definicja sukcesu

Cztery JSON-y klienta (`c01`, `c16`, `c32`, `c64`) z kompletem `completed`,
snapshoty `metrics_spec_*` pozwalające policzyć akceptację per szczebel,
`prometheus_rungs.txt` z peakami kolejki/KV per okno, screen dashboardu z
widocznymi czterema schodkami, `NOTES.md` z wypełnioną tabelą i odpowiedzią
na cztery kontrole — wszystko w `results/runs/<data>_kimi_steps/` na `main`.

## Świadomie pominięte

- **Liczniki DCGM per szczebel** (moc, SMACT, DRAMA, NVLink TX/RX). Wartościowe,
  ale to osobna warstwa z własnym gotchą (probe nagłówka pól — pola 1011/1012
  potrafią cicho wypaść z próbki). Gotowy helper `start_sample_window` /
  `stop_sample_window`: `docs/plans/2026-08-03-nvlink-gap-fill.md`.
- **Bench przez LiteLLM :4000** — proxy strippuje `delta.reasoning` Kimiego;
  drabinka jedzie direct na :8000.
- **DeepSeek (`vllm-small`)** — `--max-num-seqs 2` uniemożliwia sensowny bench
  batchowany; stoi obok i tylko zjada VRAM (to część baseline'u, nie zmieniamy).
- **A/B drafterów i zmiany util** — inny cel; ten runbook mierzy konfigurację
  produkcyjną z repo, niczego nie stroi.
