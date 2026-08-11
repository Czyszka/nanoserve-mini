#!/usr/bin/env bash
# lib.sh — wspólne helpery runbooków pokazowych (demo-*.sh).
# Konwencje: serving/runbooks/demo-conventions.md.
# Pochodzenie helperów: sprawdzone plany 08-03/08-07 + runbook
# kimi-concurrency-ladder-swe.md, dostosowane do strict mode:
#   - funkcje zwracają kod != 0 zamiast exit (przerwanie robi caller/set -e),
#   - sondy (curl/grep) opakowane w if, żeby nie ubijały skryptu pod set -e,
#   - side-effecty tylko w $DEMO_DIR i podnoszenie stacku z configu repo.
# Użycie w demo-*.sh:
#   source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
#   demo_init "<temat>"

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
COMPOSE="${COMPOSE:-$REPO_ROOT/serving/compose/docker-compose.kimi-k2.6.yml}"
OBS="${OBS:-$REPO_ROOT/serving/compose/docker-compose.observability.yml}"
SWE="${SWE:-$REPO_ROOT/results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl}"

demo_init () {          # $1=temat; ustawia $DEMO_DIR, laduje .env, snapshot commita
  local temat="${1:?demo_init: podaj temat}"
  DEMO_DIR="${DEMO_DIR:-$HOME/working/nanoserve-demo/$(date +%F)_${temat}}"
  mkdir -p "$DEMO_DIR"
  # .env: repo-root, a jak nie ma - ten przy compose
  if [ -f "$REPO_ROOT/.env" ]; then
    set -a; . "$REPO_ROOT/.env"; set +a
  elif [ -f "$REPO_ROOT/serving/compose/.env" ]; then
    set -a; . "$REPO_ROOT/serving/compose/.env"; set +a
  else
    echo "STOP: brak .env - compose Kimiego wymaga HF_TOKEN i LITELLM_MASTER_KEY"; return 1
  fi
  [ -n "${HF_TOKEN:-}" ]           || { echo "STOP: HF_TOKEN pusty"; return 1; }
  [ -n "${LITELLM_MASTER_KEY:-}" ] || { echo "STOP: LITELLM_MASTER_KEY pusty"; return 1; }
  [ -s "$SWE" ]                    || { echo "STOP: brak zestawu SWE pod $SWE"; return 1; }
  git -C "$REPO_ROOT" rev-parse HEAD > "$DEMO_DIR/commit.txt"
  echo "demo_init: artefakty -> $DEMO_DIR"
}

wait_http_health () {   # $1=url $2=proby $3=przerwa(s)
  local url="$1" attempts="$2" pause="$3" i
  for i in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then return 0; fi
    sleep "$pause"
  done
  echo "health timeout: $url" >&2
  return 1
}

ensure_kimi () {        # idempotentnie: stoi -> nic; nie stoi -> up -d configu repo
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
  docker compose -f "$COMPOSE" ps | tee "$DEMO_DIR/ps_serving.txt"
}

ensure_obs () {         # prometheus + grafana; siec nanoserve-net jest external
  if ! docker network inspect nanoserve-net >/dev/null 2>&1; then
    echo "STOP: brak sieci nanoserve-net - najpierw ensure_kimi"; return 1
  fi
  local ok_p=0 ok_g=0
  if curl -fsS http://127.0.0.1:9090/-/healthy  >/dev/null 2>&1; then ok_p=1; fi
  if curl -fsS http://127.0.0.1:3001/api/health >/dev/null 2>&1; then ok_g=1; fi
  if [ "$ok_p" = 1 ] && [ "$ok_g" = 1 ]; then
    echo "observability: JUZ DZIALA (prometheus+grafana)"
  else
    echo "observability: podnosze (prom=$ok_p grafana=$ok_g)"
    docker compose -f "$OBS" up -d
    wait_http_health http://127.0.0.1:9090/-/healthy  60 5 || echo "WARN: prometheus nie wstal"
    wait_http_health http://127.0.0.1:3001/api/health 60 5 || echo "WARN: grafana nie wstala"
  fi
  docker compose -f "$OBS" ps | tee "$DEMO_DIR/ps_observability.txt"
}

check_engine_baseline () {  # fail-fast: czy silnik to produkcyjna konfiguracja z repo
  local cmd_json tp
  cmd_json="$(docker inspect vllm --format '{{json .Config.Cmd}}' 2>/dev/null || true)"
  [ -n "$cmd_json" ] || { echo "STOP: kontener vllm nie istnieje"; return 1; }
  echo "$cmd_json" > "$DEMO_DIR/engine_cmd.json"
  if ! grep -qo 'eagle3' "$DEMO_DIR/engine_cmd.json"; then
    echo "STOP: silnik bez Eagle3 - to nie jest konfiguracja produkcyjna"; return 1
  fi
  if ! grep -qo 'fuse_allreduce_rms' "$DEMO_DIR/engine_cmd.json"; then
    echo "STOP: brak workaroundu fuzji (0.26 sypie sie na TP8)"; return 1
  fi
  tp="$(docker logs vllm 2>&1 | grep -m1 -o 'tensor_parallel_size=[0-9]*' || true)"
  echo "${tp:-brak}" > "$DEMO_DIR/verify_tp.txt"
  if [ "$tp" != "tensor_parallel_size=8" ]; then
    echo "STOP: TP MISMATCH (${tp:-nie znaleziono w logu})"; return 1
  fi
  echo "engine: Eagle3 + fuse_allreduce_rms=off + TP8 - OK"
}

ensure_dataset () {
  docker cp "$SWE" vllm:/tmp/swe_bench_vllm.jsonl \
    || { echo "STOP: docker cp nie zadzialal - czy kontener 'vllm' stoi?"; return 1; }
  local n
  n="$(docker exec vllm sh -c 'wc -l < /tmp/swe_bench_vllm.jsonl' 2>/dev/null | tr -d ' ' || true)"
  echo "dataset w kontenerze: ${n:-BRAK} linii"
  if [ -z "$n" ] || [ "$n" -le 100 ]; then
    echo "STOP: dataset nie dotarl"; return 1
  fi
}

bench_prereqs () {      # po kazdym recreate: pip i /tmp nie przezywaja
  ensure_dataset || return 1
  docker compose -f "$COMPOSE" exec vllm bash -c \
    'rm -rf /tmp/kdemo; mkdir -p /tmp/kdemo; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "print(\"deps ok\")"'
}

demo_load () {          # $1=concurrency $2=num_prompts $3=tag - krotkie obciazenie pokazowe
  local c="$1" np="$2" tag="$3" t0 t1 st=0
  docker exec vllm test -s /tmp/swe_bench_vllm.jsonl \
    || { echo "BRAK datasetu - uruchom bench_prereqs"; return 1; }
  t0=$(date +%s)
  docker compose -f "$COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
      --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
      --custom-output-len 256 --ignore-eos \
      --num-prompts '"$np"' --max-concurrency '"$c"' \
      --save-result --result-dir /tmp/kdemo --result-filename '"$tag"'.json' || st=$?
  t1=$(date +%s)
  [ "$st" -ne 0 ] && echo "WARN: obciazenie $tag zwrocilo $st"
  printf '%s\t%s\t%s\t%s\t%s\n' "$tag" "$c" "$np" "$t0" "$t1" >> "$DEMO_DIR/windows.tsv"
  echo "okno $tag: $t0 -> $t1 ($((t1-t0))s)"
}

collect_demo_bench () { # JSON-y z kontenera do $DEMO_DIR (poza repo) + podsumowanie
  mkdir -p "$DEMO_DIR/bench"
  docker compose -f "$COMPOSE" cp vllm:/tmp/kdemo/. "$DEMO_DIR/bench/" \
    || { echo "WARN: brak wynikow do zebrania"; return 0; }
  show_bench "$DEMO_DIR/bench" | tee "$DEMO_DIR/bench_summary.txt"
}

show_bench () {         # $1=katalog z JSON-ami vllm bench serve
  python3 - "$1" <<'PYEOF'
import glob, json, sys
for f in sorted(glob.glob(sys.argv[1] + "/*.json")):
    d = json.load(open(f))
    print(f"{f.split('/')[-1]:26s} tok/s {d.get('output_throughput', 0):7.1f}"
          f" | TTFT p50 {d.get('median_ttft_ms', 0):8.1f}"
          f" | TPOT med {d.get('median_tpot_ms', 0):6.2f}"
          f" | ITL med {d.get('median_itl_ms', 0):7.2f}"
          f" | done {d.get('completed', 0)}")
PYEOF
}
