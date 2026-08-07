# Sesja serwerowa 2026-08-07 — diagnostyka CUDA error: Kimi K2.6 na vLLM v0.26.0

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, NVLink 4-way: wyspy GPU 0-3 / 4-7)
**Slot (założenie):** ~60-75 min (repro z pełnym ładowaniem wag jest drogie — patrz budżet).
**Kontekst:** lokalna (niewypchnięta) zmiana w `serving/compose/docker-compose.kimi-k2.6.yml`:
`vllm/vllm-openai:v0.20.0-cu130-ubuntu2404` → `vllm/vllm-openai:v0.26.0`.
Przy starcie silnika wyjątek „CUDA error" przy uruchamianiu kerneli.

> **Plan samowystarczalny** — wszystkie komendy inline.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH.
> **Świeży shell SSH** na start sesji (lekcja z 08-03: stare `RUN_DIR`/zmienne
> w reużywanym shellu nadpisały artefakty). Na wszelki wypadek: `unset RUN_DIR OUT SESSION`.

---

## 0. Cel i tryb pracy

To jest **plan iteracji 1: wyłącznie zbieranie danych**, nie naprawa.
Efekt sesji = komplet artefaktów na repo (main), na których laptop robi analizę
i buduje plan iteracji 2 (izolacja przyczyny) — dopiero tam będą przełączniki.

Trzy zasady:

1. **Najpierw zrzut istniejących logów, zanim cokolwiek zrestartujesz** (Cz. A).
   Kontener ma `restart: unless-stopped`, więc pewnie crash-loopuje — logi z
   dzisiejszych prób wciąż są w `docker logs` i znikną przy `up --force-recreate`.
2. **Zero zmian w compose poza diagnostycznym overlayem** (osobny plik w `/tmp`,
   nie dotykamy plików w repo na serwerze).
3. **Sekrety:** każdy zrzut env przechodzi przez redakcję (wzorzec niżej).

---

## 1. Hipotezy pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

Tag `v0.26.0` **nie ma** sufiksu `-cu130-ubuntu2404` jak nasz pin 0.20 — to
domyślny build, potencjalnie inna baza CUDA. Stąd kolejność hipotez:

| # | hipoteza | oczekiwana sygnatura w logu |
|---|---|---|
| H1 | **Niezgodność bazy CUDA obrazu ze sterownikiem hosta** (v0.26.0 zbudowany pod nowszy CUDA runtime niż wspiera driver) | `CUDA error: no kernel image is available for execution on the device`, `forward compatibility was attempted...`, `system has unsupported display driver / cuda driver combination`; błąd już przy **pierwszym dotknięciu GPU**, także w gołym probe (Cz. B4) bez vLLM |
| H2 | **Nowy domyślny backend attention / FlashInfer w 0.26** wymaga autotune/JIT, który wywala się na sm_90 | traceback przez `flashinfer` / `attention backend`; goły probe (B4) **przechodzi**, pada dopiero vLLM |
| H3 | **Spec-decode Eagle3** (`lightseekorg/kimi-k2.6-eagle3-mla`) niekompatybilny z 0.26 | traceback przez `speculative`/`eagle`/`drafter`; błąd po załadowaniu wag targetu, przy inicjalizacji draftera lub capture grafów |
| H4 | **NCCL/NVLS**: `NCCL_NVLS_ENABLE=1` (wciąż w compose Kimi; z Qwena usunęliśmy 08-03) + nowszy NCCL w 0.26 na topologii 4+4 | `ncclUnhandledCudaError`, błąd w fazie init komunikatorów TP8, `NCCL WARN` przed wyjątkiem |
| H5 | **Zmienione/usunięte flagi CLI w 0.26** (np. `--language-model-only`, parsery `kimi_k2`, format `--speculative-config`) | to NIE byłby CUDA error, tylko argparse/validation error na starcie — sprawdzić w logu, czy silnik w ogóle dochodzi do GPU |

Rozstrzygnięcie H1 vs reszta daje **Cz. B4** (goły probe kernela w obrazie
v0.26.0, bez vLLM) — najtańszy pojedynczy pomiar tej sesji.

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. A | zrzut istniejących logów crasha + stan kontenerów (ZERO restartów) | 10 |
| Cz. B | snapshot środowiska: host, driver, obrazy, goły probe CUDA w v0.26.0 | 15 |
| Cz. C | repro z pełną telemetrią (DEBUG + CUDA_LAUNCH_BLOCKING + NCCL_DEBUG) | 30 |
| Cz. D | restore stacku v0.20 (Kimi + DeepSeek + proxy + WebUI), commit + push | 15 |
| | **razem** | **70** |

**Kolejność cięcia:** C (repro debug) — jeśli slot krótki, A+B wystarczą na
analizę iteracji 1, a C wchodzi do iteracji 2.
**Nietykalne:** A (logi znikają!), B, D.

---

## Cz. A — zrzut istniejącego stanu (PRZED jakimkolwiek restartem) (10 min)

```bash
# świeży shell; katalog artefaktów w repo
unset RUN_DIR OUT SESSION
cd ~/working/nanoserve-mini   # ścieżka repo na serwerze — popraw jeśli inna
git pull origin main
SESSION=2026-08-07_kimi_v026_cuda_diag
OUT="results/raw/${SESSION}"
mkdir -p "$OUT"

# stan kontenerów i restart-count (crash-loop widać po RestartCount)
docker ps -a > "$OUT/docker_ps_start.txt" 2>&1
docker inspect vllm --format 'RestartCount={{.RestartCount}} StartedAt={{.State.StartedAt}} ExitCode={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}}' > "$OUT/vllm_state_start.txt" 2>&1

# PEŁNY log z dotychczasowych prób — lokalnie (duży), NIE do repo
mkdir -p ~/working/nanoserve-diag/${SESSION}
docker logs -t vllm > ~/working/nanoserve-diag/${SESSION}/log_full_pre.txt 2>&1
wc -l ~/working/nanoserve-diag/${SESSION}/log_full_pre.txt

# do repo: przycięty log — początek (wersje, config, backend) + blok błędu
head -n 150 ~/working/nanoserve-diag/${SESSION}/log_full_pre.txt > "$OUT/log_pre_head.txt"
grep -n -i -B 20 -A 60 -m 3 -E "CUDA error|cudaError|Traceback|NCCL WARN|ncclUnhandled|RuntimeError" \
  ~/working/nanoserve-diag/${SESSION}/log_full_pre.txt > "$OUT/log_pre_error_block.txt" 2>&1
[ -s "$OUT/log_pre_error_block.txt" ] || echo "# grep nie znalazł bloku błędu — sprawdź log_full_pre.txt ręcznie i wklej fragment" > "$OUT/log_pre_error_block.txt"

# KLUCZOWE dla analizy: zanotuj FAZĘ błędu (przed/po załadowaniu wag,
# przy init NCCL, przy capture grafów CUDA, przy pierwszym requeście)
grep -n -i -E "Loading model weights|weights loaded|init.*distributed|custom all-?reduce|Capturing|CUDA graph|speculative|eagle|flashinfer|Attention backend" \
  ~/working/nanoserve-diag/${SESSION}/log_full_pre.txt | tail -n 40 > "$OUT/log_pre_phase_markers.txt" 2>&1

# lokalna zmiana compose (nie jest na gh) — udokumentuj diff
git diff serving/compose/docker-compose.kimi-k2.6.yml > "$OUT/compose_local_diff.txt" 2>&1
[ -s "$OUT/compose_local_diff.txt" ] || echo "# git diff pusty — zmiana taga zrobiona poza repo? zanotuj gdzie" > "$OUT/compose_local_diff.txt"

# dmesg — Xid to twardy sygnał sprzętowy/sterownikowy (wzorzec gwarantowanie-niepusty)
DM="$OUT/dmesg_xid.txt"
sudo dmesg -T 2>/dev/null | grep -i -E "xid|nvrm|nvlink" > "$DM"
[ -s "$DM" ] || echo "# sudo dmesg przejrzany $(date -Is): zero wpisów xid/nvrm/nvlink w buforze" > "$DM"
```

---

## Cz. B — snapshot środowiska + goły probe CUDA (15 min)

```bash
# host: driver, CUDA wspierane przez driver, stan GPU
nvidia-smi > "$OUT/nvidia_smi_host.txt" 2>&1
nvidia-smi --query-gpu=index,name,driver_version,memory.used,memory.total --format=csv > "$OUT/nvidia_smi_query.txt" 2>&1
cat /proc/driver/nvidia/version > "$OUT/nvidia_driver_version.txt" 2>&1

# obrazy: digesty obu wersji + metadane bazy CUDA obrazu v0.26.0
docker images --digests | grep -E "vllm|IMAGE" > "$OUT/docker_images_digests.txt" 2>&1
docker inspect vllm/vllm-openai:v0.26.0 --format '{{json .Config.Env}}' | tr ',' '\n' | grep -i -E "cuda|nccl|torch|ubuntu" > "$OUT/image_v026_env.txt" 2>&1

# wersje bibliotek WEWNĄTRZ obrazu v0.26.0 (one-off, bez vLLM, bez wag)
docker run --rm --gpus all --entrypoint python3 vllm/vllm-openai:v0.26.0 -c "
import torch, importlib
print('torch', torch.__version__)
print('torch.cuda (runtime build)', torch.version.cuda)
print('nccl', torch.cuda.nccl.version())
try:
    import vllm; print('vllm', vllm.__version__)
except Exception as e: print('vllm import:', e)
try:
    fi = importlib.import_module('flashinfer'); print('flashinfer', getattr(fi,'__version__','?'))
except Exception as e: print('flashinfer import:', e)
" > "$OUT/image_v026_versions.txt" 2>&1

# GOŁY PROBE KERNELA (rozstrzyga H1): launch prostego kernela w obrazie v0.26.0
docker run --rm --gpus all --entrypoint python3 vllm/vllm-openai:v0.26.0 -c "
import torch
print('device', torch.cuda.get_device_name(0), 'capability', torch.cuda.get_device_capability(0))
a = torch.randn(1024, 1024, device='cuda')
b = (a @ a).sum().item()
print('matmul OK, sum =', b)
" > "$OUT/probe_v026_kernel.txt" 2>&1
cat "$OUT/probe_v026_kernel.txt"
# PADŁ z 'no kernel image' / driver mismatch => H1 potwierdzona, Cz. C można skrócić
# PRZESZEDŁ => H1 odpada, błąd jest w stosie vLLM (H2/H3/H4) — Cz. C obowiązkowa

# ten sam probe w starym obrazie v0.20 (kontrola, że host zdrowy)
docker run --rm --gpus all --entrypoint python3 vllm/vllm-openai:v0.20.0-cu130-ubuntu2404 -c "
import torch; a=torch.randn(1024,1024,device='cuda'); print('v0.20 matmul OK', (a@a).sum().item())
" > "$OUT/probe_v020_kernel.txt" 2>&1
```

---

## Cz. C — reprodukcja z pełną telemetrią (30 min; tnij jeśli brak slotu)

Overlay diagnostyczny: DEBUG-logi vLLM, synchroniczne launche kernelów
(dokładna atrybucja miejsca błędu), NCCL INFO, bez crash-loopa. Overlay
dokłada TYLKO `environment` i `restart` — `command` zostaje z pliku bazowego.

```bash
cat > /tmp/kimi-v026-diag.yml <<'EOF'
services:
  vllm:
    restart: "no"
    environment:
      VLLM_LOGGING_LEVEL: DEBUG
      CUDA_LAUNCH_BLOCKING: "1"
      NCCL_DEBUG: INFO
      NCCL_DEBUG_SUBSYS: INIT,GRAPH,ENV
EOF

cd ~/working/nanoserve-mini/serving/compose
docker compose -f docker-compose.kimi-k2.6.yml -f /tmp/kimi-v026-diag.yml up -d --force-recreate vllm

# efektywna konfiguracja po merge'u (z redakcją sekretów) — do repo
docker compose -f docker-compose.kimi-k2.6.yml -f /tmp/kimi-v026-diag.yml config vllm 2>/dev/null \
  | sed -E 's/(HUGGING_FACE_HUB_TOKEN|HF_TOKEN|LITELLM_MASTER_KEY)(:|=).*/\1\2 REDACTED/' \
  > ~/working/nanoserve-mini/"$OUT"/compose_effective_diag.txt

# obserwuj na żywo; ładowanie wag Kimi trwa — czekamy na błąd albo health OK
docker logs -f vllm
# (Ctrl+C po wystąpieniu błędu lub po pełnym starcie)

# zrzut po zakończeniu próby
cd ~/working/nanoserve-mini
docker logs -t vllm > ~/working/nanoserve-diag/${SESSION}/log_full_debug.txt 2>&1
head -n 150 ~/working/nanoserve-diag/${SESSION}/log_full_debug.txt > "$OUT/log_debug_head.txt"
grep -n -i -B 30 -A 80 -m 2 -E "CUDA error|cudaError|Traceback|ncclUnhandled" \
  ~/working/nanoserve-diag/${SESSION}/log_full_debug.txt > "$OUT/log_debug_error_block.txt" 2>&1
[ -s "$OUT/log_debug_error_block.txt" ] || echo "# brak bloku błędu w biegu debug — silnik wstał? sprawdź /health i zanotuj" > "$OUT/log_debug_error_block.txt"
grep -n -i -E "NCCL INFO|NCCL WARN" ~/working/nanoserve-diag/${SESSION}/log_full_debug.txt | head -n 60 > "$OUT/log_debug_nccl.txt" 2>&1
grep -n -i -E "Attention backend|flashinfer|speculative|eagle|custom all-?reduce|Capturing|CUDA graph" \
  ~/working/nanoserve-diag/${SESSION}/log_full_debug.txt > "$OUT/log_debug_phase_markers.txt" 2>&1

# env silnika z kontenera (redakcja!)
docker exec vllm env 2>/dev/null | sed -E 's/(HUGGING_FACE_HUB_TOKEN|HF_TOKEN)=.*/\1=REDACTED/' | sort > "$OUT/engine_env_debug.txt"
[ -s "$OUT/engine_env_debug.txt" ] || echo "# kontener już nie żyje — env z compose_effective_diag.txt" > "$OUT/engine_env_debug.txt"
```

**Uwaga:** `CUDA_LAUNCH_BLOCKING=1` mocno spowalnia — ten bieg służy TYLKO
diagnostyce, żadnych benchmarków na nim.

---

## Cz. D — restore stacku v0.20 + commit (15 min)

```bash
cd ~/working/nanoserve-mini/serving/compose

# przywróć tag v0.20 w compose (cofnięcie lokalnej zmiany)
git checkout -- docker-compose.kimi-k2.6.yml
git diff --stat   # ma być pusto

# pełny stack jak zwykle na koniec sesji: Kimi + DeepSeek + proxy + WebUI
docker compose -f docker-compose.kimi-k2.6.yml up -d --force-recreate
watch -n 20 'docker ps --format "table {{.Names}}\t{{.Status}}"'
# (Ctrl+C gdy vllm i vllm-small healthy; start_period do 30 min)

cd ~/working/nanoserve-mini
docker ps > "$OUT/docker_ps_end.txt" 2>&1
nvidia-smi > "$OUT/nvidia_smi_end.txt" 2>&1

# notatka sesyjna — wypełnij ręcznie 3 linie:
cat > "$OUT/NOTES.md" <<'EOF'
# Notatki sesji 2026-08-07 (diagnostyka Kimi v0.26.0)
- Faza błędu (przed wagami / po wagach / init NCCL / capture grafów / 1. request):
- Probe B4 (goły kernel w v0.26.0): PASS / FAIL:
- Odstępstwa od planu:
EOF
${EDITOR:-nano} "$OUT/NOTES.md"

git add "$OUT"
git commit -m "bench: diagnostyka CUDA error Kimi K2.6 na vLLM v0.26.0 - zrzuty iteracji 1"
git push origin main
```

Po pushu: sesja laptopowa analizuje `log_*_error_block.txt` + `probe_*` +
wersje i buduje **plan iteracji 2** (izolacja: obraz `v0.26.0-cu130-ubuntu2404`
jeśli istnieje / bez spec-decode / backend attention / NVLS=0 — wybór zależny
od danych, nie zgadujemy teraz).

---

## Checklista artefaktów (commit do repo)

- [ ] `docker_ps_start.txt`, `vllm_state_start.txt` (RestartCount/ExitCode)
- [ ] `log_pre_head.txt`, `log_pre_error_block.txt`, `log_pre_phase_markers.txt`
- [ ] `compose_local_diff.txt`
- [ ] `dmesg_xid.txt`
- [ ] `nvidia_smi_host.txt`, `nvidia_smi_query.txt`, `nvidia_driver_version.txt`
- [ ] `docker_images_digests.txt`, `image_v026_env.txt`, `image_v026_versions.txt`
- [ ] `probe_v026_kernel.txt`, `probe_v020_kernel.txt`
- [ ] (Cz. C) `log_debug_head.txt`, `log_debug_error_block.txt`, `log_debug_nccl.txt`, `log_debug_phase_markers.txt`, `compose_effective_diag.txt`, `engine_env_debug.txt`
- [ ] `docker_ps_end.txt`, `nvidia_smi_end.txt`, `NOTES.md`
- [ ] pełne logi zostają lokalnie w `~/working/nanoserve-diag/2026-08-07_kimi_v026_cuda_diag/` (NIE do repo)
