# Sesja serwerowa 2026-08-07 (iteracja 3) — potwierdzenie R3 + adopcja vLLM v0.26.0 z workaroundem

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, NVLink 4-way: wyspy GPU 0-3 / 4-7)
**Slot (założenie):** ~70 min (2 starty silnika + 2 benche c32).
**Kontekst:** iteracja 2 (`results/raw/2026-08-07_kimi_v026_izolacja/`, commit `2215ea2`)
wskazała winowajcę: pass `fuse_allreduce_rms` (R3 z flagą off = PASS; R1/R2 = FAIL,
baseline 3×FAIL). Bug jest racem → R3 wymaga powtórki wg reguły stopu z iteracji 2.
Compose Kimi ma już na main poprawkę: tag `v0.26.0` + `--compilation-config`
z `pass_config.fuse_allreduce_rms=false` (commit z tej samej paczki co ten plan).

> **Plan jest samowystarczalny** — wszystkie helpery i komendy inline.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH.
> **Świeży shell SSH** na start. Koniec sesji = `docker compose down`
> (ustalenie dla serii diagnostycznej 0.26 — bez restore pełnego stacku).

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

Odniesienie wydajnościowe: Kimi TP8 c32 @384 promptów SWE = **594 tok/s**
(v0.20, NVLink, 07-31). Szum pojedynczego biegu ±6%; kara zimnego startu 10–15%
(reguła wygrzewki z `benchmark-methodology.md`).

| pomiar | predykcja | odczyt |
|---|---|---|
| Cz. 2: R3 powtórka (overlay, config jak R3 z iteracji 2) | **PASS** (2. z rzędu → winowajca potwierdzony formalnie) | FAIL → diagnoza wraca do analizy laptopowej; wykonaj revert compose (komenda w Cz. 5) i zakończ sesję |
| Cz. 3: start z compose repo (tag+flaga z main) | PASS jak R3 — to ta sama konfiguracja, inną ścieżką podania | FAIL przy PASS powtórki → różnica między overlayem a compose (porównaj `engine_cmd_*`) |
| Cz. 4: bench b1 (zimny, pierwszy po starcie) | **500–570 tok/s** (kara zimnego startu vs 594) | — |
| Cz. 4: bench b2 (wygrzany) | **560–680 tok/s**; próg braku regresji: ≥559 (594−6%) | <535 (−10%) → regresja realna: revert compose, zostajemy na 0.20, temat do analizy |
| spec-decode na 0.26 | log zawiera `speculative_config` z eagle3 (drafter działa po upgrade) | brak akceptowanych draftów / warningi eagle → zanotuj do analizy, NIE blokuje adopcji |

**Bramka adopcji (Cz. 5):** powtórka PASS **i** b2 ≥ 559 → compose zostaje na
0.26. Szara strefa 535–559 (wewnątrz szumu) → zostaje, z notatką. b2 < 535 →
revert. Decyzja ma być wpisana w NOTES przed commitem.

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. 0 | start, pull, snapshoty, zmienne | 4 |
| Cz. H | helpery | 2 |
| Cz. 2 | R3 powtórka (overlay) | 15 |
| Cz. 3 | start z compose repo + fail-fast verify + smoke | 15 |
| Cz. 4 | bench c32 ×2 (b1 zimny, b2 wygrzany) | 25 |
| Cz. 5 | bramka adopcji, down, NOTES, commit/push | 10 |
| | **razem** | **~71** |

**Kolejność cięcia:** Cz. 4 b2 → (nic więcej — reszta nietykalna).
**Nietykalne:** Cz. 2 (formalne domknięcie diagnozy), Cz. 3, Cz. 5.
Jeśli tniesz b2: bramka adopcji zostaje otwarta, decyzja po następnej sesji —
zapisz to w NOTES.

---

## Cz. 0 — start (4 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main
unset RUN_DIR OUT SESSION QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_ARGS

RUN_DIR=results/raw/2026-08-07_kimi_v026_adopcja
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
DIAG=~/working/nanoserve-diag/2026-08-07_kimi_v026_adopcja
SWE=results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl
mkdir -p "$RUN_DIR/session" "$DIAG"
set -a; source .env; set +a

# FAIL-FAST: pull musiał dowieźć poprawkę compose (tag 0.26 + flaga)
grep -q 'v0.26.0' "$COMPOSE" && grep -q 'fuse_allreduce_rms' "$COMPOSE" \
  || echo "STOP: compose bez poprawki — git pull nie dowiózł commita"

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"
```

---

## Cz. H — helpery (wklej cały blok, 2 min)

Sprawdzone w iteracji 2 (`czekaj`, `zrzut`, `smoke`) + sprawdzone z 08-03
(`wait_http_health`, `ensure_dataset`, `show_bench`).

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
  grep -n -E "Graph capturing finished|Application startup complete" \
    "$DIAG/log_full_$1.txt" | tail -n 4 > "$RUN_DIR/log_$1_verdict.txt"
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

## Cz. 2 — R3 powtórka przez overlay (15 min, NIETYKALNE)

Dokładnie ta sama konfiguracja co PASS z iteracji 2 (obraz + pełne `command`
w overlayu), żeby powtórka była bitowo porównywalna z pierwszym PASS-em.

```bash
cat > /tmp/kimi-r3.yml <<'EOF'
services:
  vllm:
    image: vllm/vllm-openai:v0.26.0
    restart: "no"
    command:
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size 8 --gpu-memory-utilization 0.6 --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2 --enable-auto-tool-choice --language-model-only --max-num-seqs 32 --max-model-len 131072 --max-num-batched-tokens 4096 --speculative-config='{"model":"lightseekorg/kimi-k2.6-eagle3-mla","method":"eagle3","num_speculative_tokens":3,"max_model_len":8192}' --compilation-config='{"pass_config":{"fuse_allreduce_rms":false}}'
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-r3.yml up -d --force-recreate vllm

docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qo 'fuse_allreduce_rms' \
  || echo "STOP: flaga nie weszła do cmd"

czekaj
zrzut r3_powtorka
smoke > "$RUN_DIR/smoke_r3_powtorka.json" 2>&1
```

**FAIL tutaj = koniec sesji:** wykonaj revert z Cz. 5 (wariant FAIL), commit
artefaktów, down. Nie idź do Cz. 3.

---

## Cz. 3 — start z compose repo (tag+flaga z main) + verify (15 min)

Ta sama konfiguracja, ale podana ścieżką produkcyjną (plik w repo, bez
overlaya) — to jest stan, który zostaje po sesji.

```bash
docker compose -f "$COMPOSE" up -d --force-recreate vllm   # TYLKO vllm; bez vllm-small/proxy/webui

# FAIL-FAST verify (dawka widoczna w runtime — lekcja 06-11)
docker inspect vllm --format '{{.Config.Image}}' | grep -q 'v0.26.0' || echo "STOP: zły obraz"
docker inspect vllm --format '{{json .Config.Cmd}}' | grep -qo 'fuse_allreduce_rms' \
  || echo "STOP: flaga nie weszła do cmd"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*"   # ma być =8

czekaj
zrzut adopcja_compose
smoke > "$RUN_DIR/smoke_adopcja.json" 2>&1
# potwierdzenie w logu configu, że pass jest wyłączony:
docker logs vllm 2>&1 | grep -m1 -o "'fuse_allreduce_rms': False" \
  | tee "$RUN_DIR/verify_pass_off.txt"
```

---

## Cz. 4 — sanity wydajnościowe: c32 ×2 (25 min)

b1 = zimny (pierwszy po starcie, płaci karę 10–15%), b2 = wygrzany — **do
bramki adopcji liczy się b2** (warm-to-warm vs 594 wg reguły wygrzewki).

```bash
ensure_dataset || echo "PRZERWIJ — bez datasetu bench nie ma sensu"
docker compose -f "$COMPOSE" exec vllm bash -c \
  'rm -rf /tmp/kbench; mkdir -p /tmp/kbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; python3 -c "print(\"deps ok\")"' \
  || echo "PREREQS FAILED — nie leć dalej"

kimi_c32 () {   # $1 = nazwa pliku wyniku (b1/b2)
  docker compose -f "$COMPOSE" exec vllm bash -c '
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
      --model kimi-k2.6 --trust-remote-code --tokenizer moonshotai/Kimi-K2.6 \
      --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
      --custom-output-len 256 --ignore-eos --num-warmups 2 \
      --num-prompts 384 --max-concurrency 32 \
      --save-result --result-dir /tmp/kbench --result-filename '"$1"'.json'
}

kimi_c32 v026_c32_b1_cold
kimi_c32 v026_c32_b2_warm

mkdir -p "$RUN_DIR/bench"
docker compose -f "$COMPOSE" cp vllm:/tmp/kbench/. "$RUN_DIR/bench/"
show_bench "$RUN_DIR/bench"
```

**Odczyt:** b2 vs 594 (progi w §1). Zapisz też ITL/TPOT — 0.26 mógł zmienić
profil latencji nawet przy równym throughputcie.

---

## Cz. 5 — bramka adopcji, down, commit (10 min)

```bash
# WARIANT FAIL (powtórka R3 padła albo b2 < 535): revert poprawki compose
# git revert --no-edit $(git log -n1 --format=%H -- "$COMPOSE")
# (revert TYLKO w wariancie FAIL — przy PASS compose zostaje na 0.26)

docker logs vllm > "$DIAG/log_full_koniec.txt" 2>&1     # pełny log przed down
docker compose -f "$COMPOSE" down                        # ustalenie serii: down, bez restore
docker ps > "$RUN_DIR/session/docker_ps_end.txt" 2>&1
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
git rev-parse HEAD > "$RUN_DIR/session/end_commit.txt"

cat > "$RUN_DIR/NOTES.md" <<'EOF'
# Werdykty 2026-08-07 iteracja 3 (adopcja v0.26.0)
| krok | werdykt | uwagi |
|---|---|---|
| R3 powtórka (overlay) | |
| start z compose repo | |
| bench b1 zimny (tok/s) | |
| bench b2 wygrzany (tok/s) | |
| DECYZJA bramki (0.26 zostaje / revert) | |
- Stack na koniec: celowo down (decyzja serii diagnostycznej), restore w osobnym touchu
- Odstępstwa od planu:
EOF
${EDITOR:-nano} "$RUN_DIR/NOTES.md"

git status
find "$RUN_DIR" -name 'engine_env_*' -exec grep -l "HUGGING_FACE_HUB_TOKEN=hf_" {} \; \
  && echo "STOP: token w artefaktach — popraw redakcję przed commitem"
git add "$RUN_DIR"
git commit -m "bench: adopcja vLLM v0.26.0 dla Kimi - powtorka R3, sanity c32, bramka"
git push -u origin main
```

---

## Po sesji (laptop, poza slotem)

1. Werdykty → jeśli adopcja przeszła: komentarz do issue upstream
   (vllm-project/vllm#46253; treść przygotowana w rozmowie 08-07).
2. `docs/operations/agent-state.md` — `sync-state` po domknięciu tematu.
3. Migracja Qwena/DeepSeeka na 0.26 (ten sam pass może strzelić przy TP>1) —
   osobna decyzja i osobne sesje; nie w tym slocie.

## Wątki otwarte (nie w tym slocie)

- Restore pełnego stacku (Kimi + DeepSeek + proxy + WebUI) — po zamknięciu serii
  diagnostycznej 0.26.
- Pomiar kosztu samego workaroundu (fuzja on/off na topologii z aktywnym custom
  AR, czyli TP4 w wyspie) — tylko jeśli kiedyś zaboli; na TP8/4+4 custom AR i
  tak jest wyłączony, więc fuzja nie miała czego przyspieszać.
- `NCCL_NVLS_ENABLE=1` w compose Kimi (martwa flaga) — sprzątanie w osobnym
  commicie, nie mieszać z adopcją.

---

## Walidacja planu

```text
git diff --check    (docs + compose; skrypty są heredocami wewnątrz planu)
```

## Checklista artefaktów (commit do repo)

- [ ] `session/`: `start_commit.txt`, `nvidia_smi_start.txt`, `docker_ps_end.txt`, `nvidia_smi_end.txt`, `end_commit.txt`
- [ ] `engine_image_*`, `engine_cmd_*.json`, `engine_env_*` (redakcja!), `log_*_error.txt`, `log_*_verdict.txt` dla powtórki i startu z compose
- [ ] `smoke_r3_powtorka.json`, `smoke_adopcja.json`, `verify_pass_off.txt`
- [ ] `bench/v026_c32_b1_cold.json`, `bench/v026_c32_b2_warm.json`
- [ ] `NOTES.md` — tabela werdyktów + DECYZJA bramki **wypełnione**
- [ ] pełne logi lokalnie w `~/working/nanoserve-diag/2026-08-07_kimi_v026_adopcja/` (NIE do repo)
