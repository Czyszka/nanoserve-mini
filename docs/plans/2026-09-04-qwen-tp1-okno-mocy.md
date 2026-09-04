# Sesja serwerowa 2026-09-04 — Qwen TP1: okno mocy DCGM ~350 s (slajd 3 prezentacji v2)

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, mostki NVLink 4-way — dla TP1 bez znaczenia)
**Slot:** ~55 min aktywnie (1 start silnika Qwen + 1 restore Kimi).
**Kontekst:** prezentacja `docs/presentations/2026-09-03-nvlink-meetup-v2/`,
slajd 3 „Anomalia" (wykres W0'): osiem niebieskich linii Kimi ciągnie się przez
**360 s** okna, a zielona linia odniesienia „Qwen — 1 karta" urywa się po
**~80 s** (`2026-08-31_latencja_dostepu/qwen/tp1_c64_dcgmi.txt`, 98 próbek,
z czego aktywnych ~80). Na slajdzie wygląda to jak urwany pomiar.

> **Plan samowystarczalny** — helpery i komendy inline.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH.
> **Reguła wygrzewki (od 08-03):** po starcie silnika najpierw bench-wygrzewka
> NA ODRZUT, dopiero potem pomiar.

---

## 0. Po co ta sesja

Jeden pomiar: **pobór mocy jednej karty H200 pod pełnym obciążeniem, w oknie
ciągłym ≥ 340 s**, żeby zielona linia na slajdzie 3 pokrywała się długością
z niebieskimi liniami Kimi. Nowych tez nie stawiamy — linia Qwen TP1 pełni na
slajdzie rolę **skali odniesienia**: „kartę da się obciążyć do 400–600 W".

**Jak wydłużamy okno.** Nie powtarzamy benchu kilka razy (przerwy między
biegami dałyby na wykresie zjazdy do idle) i nie zmieniamy długości odpowiedzi.
Robimy **jeden długi bieg dokładnie tego samego benchmarku**, tylko z większą
liczbą promptów: `--num-prompts` **600 → 2400**, wszystko inne bez zmian
(SWE, `--custom-output-len 256`, `--max-concurrency 64`).

To działa, bo `vllm bench serve` **cyklicznie powtarza zbiór**: bieg z 08-31
miał `--num-prompts 600` przy zbiorze liczącym 300 linii i ukończył 600
(`bench_tp1/tp1_c64.json`: `completed 600`, `duration 90 s`). Nie ma więc
żadnej różnicy metodologicznej wobec baseline'u — jest ten sam pomiar, tylko
cztery razy dłuższy. Nic do dopisywania w Q&A slajdu.

**Czego NIE robimy:** żadnych zmian power capa (`-pl` zostaje 600 W), żadnego
burn-inu, żadnych profili, żadnego dotykania mostków.

---

## 1. Predykcje — zapisane PRZED pomiarem

| # | predykcja | próg falsyfikacji | podstawa |
|---|---|---|---|
| P1 | okno aktywne (moc > 300 W) trwa **330–400 s** | < 300 s albo > 460 s → skoryguj `--num-prompts` wg wzoru w Cz. 2b i powtórz | 08-31: 600 promptów = 90 s → 2400 promptów ≈ 360 s |
| P2 | moc w części aktywnej: średnia **430–500 W**, maks. > 550 W | średnia < 380 W → obciążenie nie weszło, sprawdź `max-concurrency` i logi | 08-31 TP1 c64, część aktywna (81 próbek > 300 W): średnia **464 W**, min 402, maks 592 |
| P3 | SM_ACTIVE w części aktywnej **0,65–0,76** | < 0,50 → bench nie nasyca karty | 08-31, część aktywna: **0,712** |
| P4 | throughput **1600–1850 tok/s** | poza pasmem → inny reżim niż baseline, opisz w podsumowaniu | 08-31 TP1 c64: **1710** (600 promptów / 90 s) |
| P5 | PCIe RX ≈ **0,0–0,3 GB/s** | > 1 GB/s → coś jeszcze jedzie po łączu, pomiar skażony | TP1 nie komunikuje się z innymi kartami (08-31: **0,08 GB/s**) |

P2 i P3 to **kontrola tożsamości pomiaru** z baseline'em 08-31: jeśli obie
wejdą w pasmo, nowy dłuższy przebieg jest tym samym reżimem, tylko dłuższym,
i wolno nim podmienić linię na slajdzie.

---

## Cz. 0 — start (8 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main

RUN_DIR=results/runs/2026-09-04_qwen_tp1_okno_mocy
QOUT="$RUN_DIR/qwen"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
QWEN_COMPOSE="serving/compose/docker-compose.qwen3.6.yml"
SWE=results/runs/2026-06-05_w1_evidence/benchmarking/swe_bench_vllm.jsonl
mkdir -p "$QOUT" "$RUN_DIR/session"
set -a; source .env; set +a
DCGM_FIELDS=155,1002,1004,1005,1009,1010,1011,1012

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"

docker compose -f "$COMPOSE" stop vllm vllm-small litellm open-webui
docker compose -f "$COMPOSE" rm -f vllm 2>/dev/null || true
nvidia-smi --query-gpu=index,memory.used,power.limit --format=csv \
  | tee "$RUN_DIR/session/gpu_free_check.csv"
# GPU0 ~0 MiB i power.limit 600 W — inaczej pomiar mocy nie jest porównywalny
```

---

## Cz. H — helpery (wklej cały blok, 2 min)

```bash
sample_window () {  # $1=label $2=sekundy(sufit)
  out="$QOUT/$1"; date +%s > "${out}_start_epoch.txt"
  dcgmi dmon -e "$DCGM_FIELDS" -d 1000 -c "$2" > "${out}_dcgmi.txt" 2>&1
  date +%s > "${out}_end_epoch.txt"
}
start_sample_window () { sample_window "$1" "$2" & SAMPLE_PID=$!; }
stop_sample_window () {
  status=0
  if [ -n "${SAMPLE_PID:-}" ]; then
    pkill -TERM -P "$SAMPLE_PID" 2>/dev/null || true
    wait "$SAMPLE_PID" || status=$?
    unset SAMPLE_PID
  fi
  return "$status"
}
wait_http_health () {
  url="$1"; attempts="$2"; pause="$3"
  for _ in $(seq 1 "$attempts"); do
    curl -fsS "$url" >/dev/null 2>&1 && return 0
    sleep "$pause"
  done
  echo "health timeout: $url" >&2; return 1
}
ensure_dataset () {
  docker cp "$SWE" vllm:/tmp/swe_bench_vllm.jsonl \
    || { echo "STOP: docker cp — czy kontener 'vllm' stoi?"; return 1; }
  n=$(docker exec vllm sh -c 'wc -l < /tmp/swe_bench_vllm.jsonl' 2>/dev/null | tr -d ' ')
  echo "dataset: ${n:-BRAK} linii"
  { [ -n "$n" ] && [ "$n" -gt 100 ]; } || { echo "STOP: dataset nie dotarł"; return 1; }
}
bench_prereqs () {
  docker compose -f "$QWEN_COMPOSE" exec vllm bash -c \
    'rm -rf /tmp/xbench; mkdir -p /tmp/xbench; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; pip install -q pandas datasets; echo deps ok' \
    || { echo "PREREQS FAILED"; return 1; }
}
show_bench () {
  python3 - "$1" <<'PYEOF'
import json, os, sys
for f in sorted(os.listdir(sys.argv[1])):
    if not f.endswith('.json'): continue
    d = json.load(open(os.path.join(sys.argv[1], f)))
    print(f"{f:34s} c={d.get('max_concurrency')} tok/s {d.get('output_throughput',0):7.0f} "
          f"ITL med {d.get('median_itl_ms',0):6.1f} TPOT med {d.get('median_tpot_ms',0):6.2f} "
          f"dur {d.get('duration',0):5.0f}s")
PYEOF
}
dcgm_window_stats () {  # $1=plik dcgmi — sprawdza P1/P2/P3/P5 dla GPU 0
  python3 - "$1" <<'PYEOF'
import sys
rows=[]
for line in open(sys.argv[1]):
    p=line.split()
    if len(p)>=8 and p[0]=='GPU' and p[1]=='0':
        try: rows.append((float(p[2]), float(p[3]), float(p[7])))
        except ValueError: pass
act=[r for r in rows if r[0] > 300]
print(f"probek GPU0: {len(rows)}, aktywnych (>300 W): {len(act)}")
if act:
    pw=[r[0] for r in act]; sm=[r[1] for r in act]; rx=[r[2] for r in act]
    print(f"moc: srednia {sum(pw)/len(pw):.0f} W, min {min(pw):.0f}, maks {max(pw):.0f}")
    print(f"SM_ACTIVE srednia {sum(sm)/len(sm):.3f}")
    print(f"PCIe RX srednia {sum(rx)/len(rx)/1e9:.2f} GB/s")
PYEOF
}
```

---

## Cz. 1 — start Qwen TP1 + wygrzewka (12 min)

```bash
export QWEN_TP=1
export QWEN_CUDA_VISIBLE_DEVICES=0
unset QWEN_EXTRA_ARGS                       # bez profilera — ma być czysty bieg
docker compose -f "$QWEN_COMPOSE" up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 240 5 || echo "START FAILED"

docker inspect vllm --format '{{json .Config.Cmd}}' > "$QOUT/engine_cmd_tp1.json"
docker inspect vllm --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | sed -E 's/^(HUGGING_FACE_HUB_TOKEN|HF_TOKEN|[A-Z_]*API_KEY|[A-Z_]*SECRET[A-Z_]*)=.*/\1=REDACTED/' \
  > "$QOUT/engine_env_tp1.txt"
docker logs vllm 2>&1 | grep -m1 -o "tensor_parallel_size=[0-9]*" | tee "$QOUT/verify_tp1.txt"
grep -qx "tensor_parallel_size=1" "$QOUT/verify_tp1.txt" || echo "TP MISMATCH — PRZERWIJ"
grep -q "^CUDA_VISIBLE_DEVICES=0$" "$QOUT/engine_env_tp1.txt" || echo "ZŁY PLACEMENT — PRZERWIJ"

ensure_dataset || echo "STOP"
bench_prereqs || echo "STOP"

# wygrzewka NA ODRZUT (reguła 08-03 — zimny pierwszy bench zaniża o 10–15%)
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name random --random-input-len 64 --random-output-len 256 \
    --ignore-eos --num-prompts 32 --max-concurrency 16 \
    --result-dir /tmp/xbench --result-filename warmup_discard.json'
```

---

## Cz. 2 — pomiar główny: okno ~350 s (15 min)

### 2a. Bieg

```bash
start_sample_window tp1_c64_long 420          # sufit 420 s > oczekiwane ~360
docker compose -f "$QWEN_COMPOSE" exec vllm bash -c '
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  vllm bench serve --backend vllm --base-url http://127.0.0.1:8000 \
    --model Qwen3.6 --trust-remote-code --tokenizer Qwen/Qwen3.6-35B-A3B \
    --dataset-name custom --dataset-path /tmp/swe_bench_vllm.jsonl \
    --custom-output-len 256 --ignore-eos --num-prompts 2400 --max-concurrency 64 \
    --save-result --result-dir /tmp/xbench --result-filename tp1_c64_long.json'
stop_sample_window || echo "WARN: sampler"

mkdir -p "$QOUT/bench_tp1"
docker compose -f "$QWEN_COMPOSE" cp vllm:/tmp/xbench/. "$QOUT/bench_tp1/"
docker logs vllm > "$QOUT/log_tp1.txt" 2>&1
show_bench "$QOUT/bench_tp1"
dcgm_window_stats "$QOUT/tp1_c64_long_dcgmi.txt" | tee "$QOUT/window_stats.txt"
```

### 2b. Odczyt predykcji — ZANIM pójdziesz dalej

Sprawdź P1–P5 z sekcji 1. Jeżeli **P1 nie wyszła**, przelicz i powtórz sam
bieg (silnik już stoi, wygrzany — koszt ~7 min):

```
num_prompts = 350 s × (tok/s z tego biegu) ÷ 256
```

Przykład: wyszło 1500 tok/s i 410 s → `350 × 1500 / 256 ≈ 2050` promptów.
Liczba promptów może przekraczać 300 linii zbioru — `vllm bench serve` je
cyklicznie powtarza (potwierdzone biegiem 08-31: 600 promptów, 300 linii).

Jeżeli **P2 lub P3 nie wyszły**, pomiar NIE nadaje się do podmiany linii na
slajdzie (inny reżim niż baseline) — zapisz go, zostaw stary wykres i opisz
rozbieżność w podsumowaniu.

### 2c. Zapas: gdyby długi bieg padł w połowie

Bieg jest jednym wywołaniem, więc awaria = brak pliku JSON. Okno DCGM i tak
zostanie zapisane i **jeśli objęło ≥ 300 s pracy, nadaje się na wykres** —
sprawdź `dcgm_window_stats` i dopiero potem decyduj o powtórce. Powtórka:
ten sam blok z Cz. 2a z `--num-prompts` przeliczonym wg 2b; silnik stoi
wygrzany, koszt ~8 min.

---

## Cz. 3 — restore Kimi + commit (15 min)

```bash
docker compose -f "$QWEN_COMPOSE" down 2>/dev/null || true
unset QWEN_TP QWEN_CUDA_VISIBLE_DEVICES QWEN_EXTRA_ARGS
docker compose -f "$COMPOSE" up -d --force-recreate vllm
wait_http_health http://127.0.0.1:8000/health 360 5 || echo "KIMI RESTORE FAILED"
docker compose -f "$COMPOSE" up -d vllm-small litellm open-webui
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
git rev-parse HEAD > "$RUN_DIR/session/end_commit.txt"

git add "$RUN_DIR"
git commit -m "bench(qwen-tp1): okno mocy DCGM ~350 s dla slajdu 3 prezentacji v2"
git push -u origin main
```

---

## Cz. 4 — po sesji, na laptopie: podmiana linii na slajdzie 3

Wykres W0' (`docs/presentations/2026-09-03-nvlink-meetup-v2/generate_charts.py`,
funkcja `w0_moc_w_czasie`) czyta dziś:

```python
qwen = read_dcgmi(RUNS / "2026-08-31_latencja_dostepu" / "qwen" / "tp1_c64_dcgmi.txt")
```

Po sesji zmienić na:

```python
qwen = read_dcgmi(RUNS / "2026-09-04_qwen_tp1_okno_mocy" / "qwen" / "tp1_c64_long_dcgmi.txt")
```

W tej samej funkcji stoi przycięcie do części aktywnej i do długości okna Kimi:

```python
active = [i for i, v in enumerate(q) if v > 300]
q = q[active[0]: active[-1] + 1][:n] if active else q[:n]
```

Zostaje bez zmian — przy dłuższym oknie po prostu przestanie ucinać. Potem:

```bash
uv run --with matplotlib python docs/presentations/2026-09-03-nvlink-meetup-v2/generate_charts.py
uv run python docs/presentations/2026-09-03-nvlink-meetup-v2/build_index.py
```

W `tresc-slajdow-v2.md` (slajd 3, sekcja Źródło) podmienić ścieżkę pliku
i liczbę próbek. Treść slajdu i puenta bez zmian — to ten sam benchmark
co dotąd, tylko dłuższy.

---

## Budżet czasu

| część | co | min |
|---|---|---:|
| Cz. 0 | start, zwolnienie GPU | 8 |
| Cz. H | helpery | 2 |
| Cz. 1 | start Qwen TP1 + wygrzewka | 12 |
| Cz. 2 | pomiar + odczyt predykcji | 15 |
| Cz. 3 | restore Kimi + commit | 15 |
| | **razem** | **52** |

Zapas na jedną powtórkę biegu (P1 poza pasmem): +8 min.

**Kryteria stop:** GPU0 nie zwolniona po Cz. 0 · TP mismatch albo zły
placement po starcie · dataset nie dotarł. W każdym z tych przypadków nie
mierzymy — restore Kimi i koniec.

**Nietykalne:** Cz. 3 (restore Kimi — serwer musi wrócić do stanu
produkcyjnego niezależnie od tego, czy pomiar wyszedł).
