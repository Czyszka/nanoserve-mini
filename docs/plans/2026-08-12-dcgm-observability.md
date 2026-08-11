# Sesja serwerowa 2026-08-12 — deploy dcgm-exporter + dashboard GPU hardware (#34, piggyback #49)

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, wyspy NVLink GPU 0-3 / 4-7)
**Slot (założenie):** ~55 min. **Zero restartów silników** — stack serwujący
(Kimi/DeepSeek/LiteLLM/OpenWebUI) jest w tej sesji NIETYKALNY.
**Kontekst:** #34 open-blocker „GPU hardware metrics (DCGM) — HIGH VALUE":
vLLM `/metrics` nie ma żadnego sygnału sprzętowego (moc, SMACT, DRAMA, VRAM,
NVL). Cały config powstał na laptopie 2026-08-11 (compose + counters CSV +
scrape job + dashboard `dcgm-gpu.json`); sesja tylko deployuje i weryfikuje.
Przy okazji snapshot digestów obrazów pod #49 (pin robi laptop po sesji).

> **Plan jest samowystarczalny** — wszystkie komendy inline.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH.
> **Świeży shell SSH.**

---

## 0. Architektura i granice bezpieczeństwa (przeczytaj przed startem)

Co się zmienia i dlaczego to jest bezpieczne:

1. **Nowy kontener `dcgm-exporter`** w compose observability — wbudowany
   hostengine, `cap_add: SYS_ADMIN` (wymagane dla pól PROF; celowo NIE
   `privileged`), tylko odczyt liczników. Koszt próbkowania DCGM został
   uniewinniony kontrolowanym A/B 08-03 (sampler dmon 1 s vs brak — zero
   mierzalnej różnicy), a exporter próbkuje łagodniej (5 s).
2. **Prometheus:** scrape job `dcgm` jest addytywny. UWAGA gotcha:
   `prometheus.yml` to bind-mount **pojedynczego pliku** — po `git pull`
   kontener widzi stary inode, więc `/-/reload` NIE wystarczy; konieczny
   `up -d --force-recreate prometheus`. TSDB jest na bind-mouncie hosta
   (`nanoserve-observability/prometheus-data`) — dane przeżyją, dziura w
   scrape ~10-20 s, poza jakimkolwiek oknem pomiarowym.
3. **Grafana: zero dotknięć.** Katalog provisioning to bind-mount **katalogu**,
   provider skanuje co 30 s — nowy `dcgm-gpu.json` wjedzie sam po `git pull`.
   Zwalidowany `vllm-phase1.json` nietknięty (osobny plik = osobny rollback).
4. **Ryzyko nr 1 — koegzystencja PROF.** Host ma DCGM tier-1 i sesje benchowe
   używają `dcgmi dmon` (wzorzec z `infrastructure.md`). Exporter z wbudowanym
   hostengine to DRUGA sesja profilowania na tych samych GPU — pola PROF
   bywają jednosesyjne. Cz. 3 testuje to wprost i jest bramką: konflikt ⇒
   polityka „stop exportera na okna dmon" (jedna komenda), nie przebudowa.
5. **Rollback (całość < 2 min):** `docker compose -f $OBS stop dcgm-exporter`,
   revert commita prep, `up -d --force-recreate prometheus`. Nic innego się
   nie zmieniło.

Tag obrazu `4.5.2-4.8.1-ubuntu22.04` zweryfikowany w nvcr.io 2026-08-11
(lekcja: tag musi istnieć w rejestrze, nie tylko na GH).

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

| pomiar | predykcja | jeśli inaczej |
|---|---|---|
| `/metrics` exportera | 11 pól × 8 GPU, w tym `NVLINK_TX/RX` (NIE cicho pominięte) | brak pól NVL → lekcja 08-03 (ciche pominięcie przy niedostępności): porównaj wersję DCGM kontenera z driverem 595; zanotuj, NIE brnij |
| FB_USED idle (Kimi @0,60 + DeepSeek @0,20 załadowane) | ~110-120 GiB/GPU (0,8 × 143 GB) | dużo mniej → któryś silnik nie stoi; `docker compose ps` |
| Power idle | 80-160 W/GPU | — |
| SM_ACTIVE idle | ~0-0,05 | trwale wysokie bez ruchu → ktoś inny liczy na GPU; `nvidia-smi` procesy |
| koegzystencja: dmon równolegle z exporterem | **NIEPEWNA — to jest bramka.** DCGM 4.x multiplexuje w obrębie jednego hostengine'a, ale tu są DWA | dmon zwraca N/A lub błąd → werdykt KONFLIKT; polityka stop-na-okna-dmon (Cz. 3) |
| mini-load: skok Power/SMACT/NVL na **wszystkich 8** GPU (TP8) | wyraźny vs idle | brak skoku na NVL przy skoku SMACT → pole NVL martwe w exporterze mimo obecności — cross-check z dmon rozstrzyga |
| cross-check NVL: exporter vs `dcgmi dmon` 1011/1012 w tym samym oknie | zgodność co do rzędu wielkości (GB/s) | rozjazd → semantyka pola do wyjaśnienia ZANIM trafi do write-upów |

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. 0 | pull, zmienne, snapshoty startowe | 5 |
| Cz. 1 | deploy: exporter + force-recreate prometheusa, targety | 10 |
| Cz. 2 | walidacja pól (8 serii/pole, sanity idle) | 8 |
| Cz. 3 | **bramka koegzystencji** dmon ⊕ exporter | 10 |
| Cz. 4 | mini-load + Grafana + screenshot + cross-check NVL | 14 |
| Cz. 5 | digesty (#49), NOTES, commit/push | 8 |
| | **razem** | **~55** |

**Kolejność cięcia:** Cz. 4 screenshot/renderer → Cz. 4 mini-load (walidację
pod realnym loadem i tak da następna sesja benchowa). **Nietykalne:** Cz. 3
(bramka bezpieczeństwa przyszłych sesji dmon) i Cz. 5 commit.

---

## Cz. 0 — start (5 min)

```bash
cd ~/nanoserve-mini && git pull --ff-only origin main
unset RUN_DIR OUT SESSION
RUN_DIR=results/runs/2026-08-12_dcgm_deploy
OBS="serving/compose/docker-compose.observability.yml"
COMPOSE="serving/compose/docker-compose.kimi-k2.6.yml"
mkdir -p "$RUN_DIR/session"
set -a; source .env; set +a

# obraz exportera (~1 GB) ciagnij W TLE od razu - nie pal slotu na pull w Cz. 1
docker compose -f "$OBS" pull -q dcgm-exporter & PULL_PID=$!

git rev-parse HEAD > "$RUN_DIR/session/start_commit.txt"
nvidia-smi > "$RUN_DIR/session/nvidia_smi_start.txt"
nvidia-smi -L > "$RUN_DIR/gpu_uuid_map.txt"          # mapa gpu-index <-> UUID do joinow w analizie
{ pgrep -a nv-hostengine || echo "(brak nv-hostengine host-side)"; } \
  | tee "$RUN_DIR/session/host_hostengine.txt"
ss -ltn | grep -q ':9400 ' && echo "UWAGA: port 9400 zajety - sprawdz przed up"
docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/ps_serving_start.txt"
docker compose -f "$OBS" ps     | tee "$RUN_DIR/session/ps_obs_start.txt"
```

**OK:** pull przeszedł (prep commit z 08-11 jest na main); serving stack stoi
(healthy) — nie jest warunkiem deployu, ale predykcja FB_USED go zakłada.
Brak `nv-hostengine` NIE blokuje deployu — patrz kontyngencja w Cz. 3.

---

## Cz. 1 — deploy (10 min)

```bash
wait "$PULL_PID" && echo "obraz exportera pobrany"

# 1) prometheus MUSI byc force-recreated (single-file bind mount nie widzi
#    podmiany pliku po git pull; /-/reload przeladowalby STARY plik)
docker compose -f "$OBS" up -d --force-recreate prometheus

# 2) nowy serwis - dotyka wylacznie siebie
docker compose -f "$OBS" up -d dcgm-exporter

# 3) grafany NIE dotykamy - provider sam zassie dcgm-gpu.json w <=30 s

docker compose -f "$OBS" ps | tee "$RUN_DIR/session/ps_obs_after.txt"
for i in $(seq 1 24); do
  curl -fsS http://127.0.0.1:9400/metrics >/dev/null 2>&1 && { echo "exporter OK"; break; }
  sleep 5
done
curl -fsS http://127.0.0.1:9090/-/healthy && echo "prometheus OK"
curl -s http://127.0.0.1:9090/api/v1/targets \
  | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}' \
  | tee "$RUN_DIR/session/prom_targets.txt"
docker logs dcgm-exporter 2>&1 | tail -20 > "$RUN_DIR/session/exporter_log_tail.txt"
```

**OK:** `exporter OK` w ≤2 min; wszystkie 4 joby (`vllm-kimi`,
`vllm-small-deepseek`, `litellm`, `dcgm`) `health: "up"`; log exportera bez
`Failed to watch metrics` / `CAP_SYS_ADMIN`.
**FAIL:** exporter w crash-loopie → `docker logs dcgm-exporter`, zanotuj,
rollback (sekcja 0 pkt 5) i kończymy sesję commitem artefaktów diagnozy.

---

## Cz. 2 — walidacja pól (8 min)

```bash
curl -s http://127.0.0.1:9400/metrics > "$RUN_DIR/dcgm_metrics_idle.txt"

for f in DCGM_FI_DEV_POWER_USAGE DCGM_FI_DEV_GPU_TEMP DCGM_FI_DEV_FB_USED DCGM_FI_DEV_FB_FREE \
         DCGM_FI_PROF_SM_ACTIVE DCGM_FI_PROF_PIPE_TENSOR_ACTIVE DCGM_FI_PROF_DRAM_ACTIVE \
         DCGM_FI_PROF_PCIE_TX_BYTES DCGM_FI_PROF_PCIE_RX_BYTES \
         DCGM_FI_PROF_NVLINK_TX_BYTES DCGM_FI_PROF_NVLINK_RX_BYTES; do
  n=$(grep -c "^$f{" "$RUN_DIR/dcgm_metrics_idle.txt")
  [ "$n" -eq 8 ] || echo "UWAGA: $f ma $n serii (oczekiwane 8)"
done
echo "-- przeglad pol zakonczony (brak UWAG = komplet) --"

# sanity na idle (miekkie widelki z predykcji)
python3 - "$RUN_DIR/dcgm_metrics_idle.txt" <<'PYEOF'
import re, sys
txt = open(sys.argv[1]).read()
def vals(f):
    return [float(m.group(1)) for m in re.finditer(rf'^{f}{{[^}}]*}} ([0-9.eE+-]+)$', txt, re.M)]
for f, lo, hi in [("DCGM_FI_DEV_POWER_USAGE", 60, 250),
                  ("DCGM_FI_DEV_FB_USED", 90000, 135000),
                  ("DCGM_FI_PROF_SM_ACTIVE", 0.0, 0.2)]:
    v = vals(f)
    flag = "" if v and all(lo <= x <= hi for x in v) else "  <-- POZA WIDELKAMI (zanotuj w NOTES)"
    print(f"{f}: n={len(v)} min={min(v) if v else '-':} max={max(v) if v else '-'}{flag}")
PYEOF

# czy Prometheus juz to widzi
curl -s --data-urlencode 'query=count by (__name__)({__name__=~"DCGM_FI_.*"})' \
  http://127.0.0.1:9090/api/v1/query \
  | jq -r '.data.result[] | "\(.metric.__name__) \(.value[1])"' \
  | tee "$RUN_DIR/prom_dcgm_series.txt"
```

**OK:** komplet 11 pól × 8 serii po obu stronach (exporter i Prometheus);
sanity bez flag. Pola NVL **muszą** być obecne — to główny cel W2/#34.

---

## Cz. 3 — BRAMKA: koegzystencja host-side dmon ⊕ exporter (10 min)

Przyszłe sesje benchowe używają `dcgmi dmon` z hosta. Sprawdzamy, czy obie
sesje profilowania żyją równolegle — na spokojnym stacku, nie w środku benchu.

**Kontyngencja:** jeśli Cz. 0 pokazała brak `nv-hostengine`, najpierw
`sudo systemctl start nvidia-dcgm` (tier-1 z 06-10 działał, więc serwis jest
zainstalowany); jeśli i to nie wstaje — bramka „NIETESTOWALNA DZIŚ" w NOTES,
a polityką domyślną dla przyszłych sesji dmon zostaje wariant ostrożny
(stop exportera na okna dmon) do czasu przetestowania.

```bash
# dmon dokladnie we wzorcu z infrastructure.md, 10 probek
dcgmi dmon -e 155,1002,1005,1011,1012 -d 1000 -c 10 | tee "$RUN_DIR/coexist_dmon.txt"

# czy exporter dalej raportuje swieze wartosci PROF po oknie dmon?
sleep 8
curl -s http://127.0.0.1:9400/metrics > "$RUN_DIR/dcgm_metrics_po_dmon.txt"
grep -c '^DCGM_FI_PROF_SM_ACTIVE{' "$RUN_DIR/dcgm_metrics_po_dmon.txt"
docker logs dcgm-exporter 2>&1 | tail -10
```

**Werdykt (wpisz do NOTES):**

- **KOEGZYSTENCJA OK** = dmon dał 10 pełnych wierszy z liczbami (nie `N/A`)
  we wszystkich kolumnach **oraz** exporter po oknie nadal ma 8 serii
  SM_ACTIVE i czysty log → nic nie robimy, exporter zostaje włączony na stałe.
- **KONFLIKT** = dmon błąd/`N/A` w polach PROF albo exporter przestał
  raportować → **polityka: przed każdym oknem dmon w sesjach benchowych
  `docker compose -f serving/compose/docker-compose.observability.yml stop
  dcgm-exporter`, po oknie `start`.** Wpis do NOTES + follow-up laptopowy:
  dopisać tę linijkę do wzorca samplera w `infrastructure.md`; ewentualny
  wariant „exporter podpięty do hostengine'a hosta" (network_mode: host,
  `-r 127.0.0.1:5555`) to osobna decyzja, NIE przebudowujemy w tym slocie.

---

## Cz. 4 — mini-load, Grafana, cross-check NVL (14 min)

Cel: zobaczyć skok na panelach i porównać NVL exportera z dmon w tym samym
oknie. To NIE jest pomiar wydajności (bez wygrzewki, bez porównań z historią)
— tylko sygnał na wykresach.

```bash
# load w tle: 40 sekwencyjnych requestow do Kimi (ok. 3-4 min)
( for i in $(seq 1 40); do
    curl -s http://localhost:8000/v1/chat/completions -H 'Content-Type: application/json' \
      -d '{"model":"kimi-k2.6","messages":[{"role":"user","content":"Wyjasnij w 3 zdaniach czym jest tensor parallelism."}],"max_tokens":96}' \
      >/dev/null
  done ) &
LOAD_PID=$!

# TYLKO gdy Cz. 3 = KOEGZYSTENCJA OK: dmon rownolegle, cross-check NVL
dcgmi dmon -e 1011,1012 -d 1000 -c 60 | tee "$RUN_DIR/load_dmon_nvl.txt"
# (przy KONFLIKCIE: pomin dmon, niech load leci a exporter sam zbiera)

wait "$LOAD_PID"
curl -s http://127.0.0.1:9400/metrics > "$RUN_DIR/dcgm_metrics_load.txt"
grep -E '^DCGM_FI_(DEV_POWER_USAGE|PROF_SM_ACTIVE|PROF_NVLINK_TX_BYTES)\{' \
  "$RUN_DIR/dcgm_metrics_load.txt"
```

**OK:** Power/SMACT/NVL wyraźnie nad idle na wszystkich 8 GPU; NVL exportera
i średnie z `load_dmon_nvl.txt` zgadzają się co do rzędu wielkości.

**Grafana — jawny check provisioningu** (provider skanuje co 30 s, do tego
momentu minęło dużo więcej):

```bash
for uid in nanoserve-dcgm-gpu nanoserve-vllm-dcgm; do
  curl -s -u "admin:${GRAFANA_ADMIN_PASSWORD:-admin}" \
    "http://127.0.0.1:3001/api/dashboards/uid/$uid" \
    | jq -r --arg u "$uid" '($u + ": ") + (.dashboard.title // "BRAK - niesprovisionowany")'
done
```

**OK:** oba uid-y zwracają tytuły (`GPU hardware (DCGM) …` i
`Serving ↔ GPU hardware (vLLM + DCGM) …`). `BRAK` → sprawdź
`docker logs grafana | grep -i provision` (JSON-y przeszły `jq .` na laptopie,
więc podejrzany jest mount/pull, nie składnia).

Potem UI: `http://<serwer>:3001` → dashboard **GPU hardware (DCGM) —
nanoserve-mini**, zakres Last 30 minutes. Screenshot ręczny (`Win+Shift+S`
przez RDP) → `$RUN_DIR/grafana_dcgm.png`. Wariant headless:

```bash
DS_UID=$(curl -s -u "admin:${GRAFANA_ADMIN_PASSWORD:-admin}" \
  http://127.0.0.1:3001/api/datasources | jq -r '.[]|select(.type=="prometheus").uid' | head -1)
curl -s -u "admin:${GRAFANA_ADMIN_PASSWORD:-admin}" -o "$RUN_DIR/grafana_dcgm.png" \
  "http://127.0.0.1:3001/render/d/nanoserve-dcgm-gpu/?from=now-30m&to=now&width=1920&height=1200&kiosk&var-datasource=${DS_UID}"
file "$RUN_DIR/grafana_dcgm.png"
```

Jeśli renderer marudzi — screenshot ręczny i jedziemy dalej, to nie jest cel
sesji.

---

## Cz. 5 — digesty (#49), NOTES, commit (8 min)

```bash
docker images --digests | grep -Ei 'grafana|prom/|dcgm' | tee "$RUN_DIR/images_digests.txt"
docker compose -f "$COMPOSE" ps | tee "$RUN_DIR/session/ps_serving_end.txt"   # dowod: serving nietkniety
nvidia-smi > "$RUN_DIR/session/nvidia_smi_end.txt"
git rev-parse HEAD > "$RUN_DIR/session/end_commit.txt"

cat > "$RUN_DIR/NOTES.md" <<'EOF'
# Werdykty 2026-08-12 — deploy dcgm-exporter (#34)
| kontrola | wynik |
|---|---|
| exporter up + 4 targety Prometheusa `up` | TAK/NIE |
| 11 pól × 8 GPU, w tym NVLINK_TX/RX obecne | TAK/NIE |
| sanity idle (power/FB_USED/SMACT w widelkach) | TAK/NIE |
| **koegzystencja dmon ⊕ exporter** | OK / KONFLIKT (polityka stop-na-okna-dmon) |
| mini-load widoczny na panelach (8 GPU) | TAK/NIE |
| cross-check NVL exporter vs dmon (rząd wielkości) | TAK/NIE/POMINIĘTY |
| dashboard DCGM w Grafanie + screenshot | TAK/NIE |
| serving stack nietknięty (ps start == end) | TAK/NIE |
- Odstępstwa od planu:
EOF
${EDITOR:-nano} "$RUN_DIR/NOTES.md"

git status
git add "$RUN_DIR"
git commit -m "infra: deploy dcgm-exporter + walidacja pol i koegzystencji z dmon (#34)"
git push -u origin main
```

---

## Po sesji (laptop, poza slotem)

1. #49: pin `grafana`/`prometheus`/`renderer` do wersji + digestów z
   `images_digests.txt` (config-only commit; exporter już jest pinowany tagiem).
2. Przy KONFLIKCIE w Cz. 3: dopisać politykę stop-exportera do wzorca samplera
   w `infrastructure.md` §DCGM.
3. `infrastructure.md`: dopisać exporter jako tier obserwability (obok tier-1
   dmon) + `sync-state`.
4. Następna sesja benchowa (np. drabinka `serving/runbooks/kimi-concurrency-ladder-swe.md`)
   waliduje panele DCGM pod realnym obciążeniem — dokłada brakujący „GPU
   hardware row pod load" do #34.

## Świadomie pominięte

- **Wiersz DCGM w `vllm-phase1.json`** — osobny plik dashboardu zamiast edycji
  zwalidowanego JSON-a (osobny rollback, zero ryzyka regresji paneli W1).
- **Wariant remote-hostengine** (`-r 127.0.0.1:5555` + network_mode: host) —
  tylko jako udokumentowany fallback po ewentualnym KONFLIKCIE; nie w tym slocie.
- **Alerty / retencja TSDB / rekording rules** — poza zakresem #34.
- **Pin obrazów Grafana/Prometheus w tym slocie** — #49 wymaga digestów, które
  dopiero zbieramy; pin to bezpieczny commit laptopowy po sesji.

---

## Walidacja planu (laptop, 2026-08-11)

```text
docker compose -f serving/compose/docker-compose.observability.yml config    OK (dummy GRAFANA_RENDERER_TOKEN)
jq . serving/compose/grafana/provisioning/dashboards/dcgm-gpu.json           OK
git diff --check                                                             OK
tag 4.5.2-4.8.1-ubuntu22.04 obecny w nvcr.io (tags/list)                     OK
pola PROF *_BYTES = gauge B/s wg default-counters.csv exportera              OK
flagi CLI potwierdzone w zrodle exportera (pkg/cmd/app.go):
  -f/--collectors (plik CSV), -c/--collect-interval (MILISEKUNDY, def. 30000) OK
snippet sanity Cz. 2 przetestowany na fixture (8 serii, notacja naukowa)     OK
przeglad 08-11: naprawiony pgrep|tee (tee maskowal exit code), pull obrazu
  przeniesiony w tlo do Cz. 0, kontyngencja nv-hostengine w Cz. 3,
  jawny check provisioningu dashboardu przez API                             OK
```

## Checklista artefaktów (commit do repo)

- [ ] `session/`: `start_commit.txt`, `end_commit.txt`, `nvidia_smi_{start,end}.txt`, `ps_{serving,obs}_*.txt`, `host_hostengine.txt`, `prom_targets.txt`, `exporter_log_tail.txt`
- [ ] `gpu_uuid_map.txt`
- [ ] `dcgm_metrics_{idle,po_dmon,load}.txt`, `prom_dcgm_series.txt`
- [ ] `coexist_dmon.txt` (+ `load_dmon_nvl.txt` jeśli koegzystencja OK)
- [ ] `images_digests.txt` (wsad pod #49)
- [ ] `grafana_dcgm.png` (mały PNG)
- [ ] `NOTES.md` — tabela werdyktów **wypełniona**, w tym bramka koegzystencji
