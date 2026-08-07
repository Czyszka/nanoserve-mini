# Sesja serwerowa 2026-08-07 (iteracja 2) — izolacja przyczyny CUDA error Kimi K2.6 @ vLLM v0.26.0

**Status:** draft → aktywny w dniu sesji
**Maszyna:** ubuntusrv2 (8×H200 NVL, NVLink 4-way: wyspy GPU 0-3 / 4-7)
**Slot (założenie):** ~70 min (4 starty silnika po ~12 min + restore).
**Kontekst:** iteracja 1 (`results/raw/2026-08-07_kimi_v026_cuda_diag/`, commit `2a8a0f7`)
zlokalizowała crash: `cudaErrorIllegalAddress` w benchmarkingu kerneli Tritona
(Inductor `benchmark_all_configs`) podczas capture grafów CUDA (PIECEWISE 28/33),
Xid 31 na 8 GPU; z `CUDA_LAUNCH_BLOCKING=1` capture PRZECHODZI → race, nie zły kernel.
Upstream: vllm #47561 (eagle3 + compressed-tensors na Hopper), #46253 (fuzja all-reduce
przy capture).

> **Plan samowystarczalny** — wszystkie komendy inline.
> **BEZ `set -euo pipefail`, BEZ `exit`** — sesja interaktywna po SSH.
> **Świeży shell SSH**; zmienne definiujemy RAZ w bloku 0 i nie robimy `cd` po katalogach.

---

## 0. Zmienne i funkcje sesji (wykonaj raz, na początku)

```bash
unset RUN_DIR OUT SESSION
REPO=~/working/nanoserve-mini
COMPOSE=$REPO/serving/compose/docker-compose.kimi-k2.6.yml
SESSION=2026-08-07_kimi_v026_izolacja
OUT=$REPO/results/raw/$SESSION
DIAG=~/working/nanoserve-diag/$SESSION
mkdir -p "$OUT" "$DIAG"
git -C "$REPO" pull origin main
git -C "$REPO" status   # ma być czysto; tag w compose zostaje v0.20 — obraz podbijamy overlayem

# czekaj na werdykt biegu: błąd albo pełny start (max ~20 min)
czekaj() {
  for i in $(seq 1 120); do
    docker logs vllm 2>&1 | grep -qE "CUDA error|Application startup complete" && break
    sleep 10
  done
  docker logs vllm 2>&1 | grep -cE "CUDA error" && echo "== FAIL (CUDA error) ==" || echo "== brak CUDA error =="
  docker logs vllm 2>&1 | tail -n 3
}

# zrzut biegu: zrzut <nazwa> — pełny log lokalnie, do repo tylko werdykt + blok błędu
zrzut() {
  docker logs -t vllm > "$DIAG/log_full_$1.txt" 2>&1
  grep -n -i -B 20 -A 60 -m 2 -E "CUDA error|Traceback|ncclUnhandled" "$DIAG/log_full_$1.txt" > "$OUT/log_$1_error.txt" 2>&1
  [ -s "$OUT/log_$1_error.txt" ] || echo "# brak bloku błędu" > "$OUT/log_$1_error.txt"
  grep -n -E "Graph capturing finished|Application startup complete|Capturing CUDA graphs" "$DIAG/log_full_$1.txt" | tail -n 6 > "$OUT/log_$1_verdict.txt"
}

# smoke test po udanym starcie (jedno realne żądanie)
smoke() {
  curl -s http://localhost:8000/v1/chat/completions -H 'Content-Type: application/json' \
    -d '{"model":"kimi-k2.6","messages":[{"role":"user","content":"2+2?"}],"max_tokens":8}'
}
```

**Kanoniczna komenda Kimi** (kopiowana do overlayów niżej; overlay compose
ZASTĘPUJE całe `command`, więc każdy wariant niesie pełną komendę):

```text
--model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size 8 --gpu-memory-utilization 0.6 --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2 --enable-auto-tool-choice --language-model-only --max-num-seqs 32 --max-model-len 131072 --max-num-batched-tokens 4096 --speculative-config='{"model":"lightseekorg/kimi-k2.6-eagle3-mla","method":"eagle3","num_speculative_tokens":3,"max_model_len":8192}'
```

---

## 1. Predykcje pre-rejestrowane (wpisane PRZED sesją — nie zmieniaj po fakcie)

Baseline: crash 3/3 prób (Xid 07:45, 07:53, 08:06 lokalnie), zawsze ta sama faza.
Bug jest racem, więc **pojedynczy PASS wariantu wymaga 1 powtórki** zanim uznamy
go za winowajcę; FAIL jest jednoznaczny od razu.

| bieg | zmiana vs baseline | PASS oznacza | FAIL oznacza |
|---|---|---|---|
| R1 `bez_combobench` | Inductor: `combo_kernels=false`, `benchmark_combo_kernel=false` | race siedzi w benchmarkingu combo-kerneli podczas capture (zgodne ze stack trace) | benchmarking niewinny; idź do R2 |
| R2 `bez_eagle3` | usunięty `--speculative-config` | klasa vllm #47561 — drafter eagle3 (compressed-tensors) psuje capture | drafter niewinny; idź do R3 |
| R3 `bez_fuzji_ar` | `pass_config.fuse_allreduce_rms=false` | klasa vllm #46253 — fuzja allreduce+RMSNorm psuje capture | fuzja niewinna; idź do R4 |
| R4 `eager` | `--enforce-eager` (zero grafów CUDA) | sanity: silnik 0.26 działa bez capture (spójne z biegiem LAUNCH_BLOCKING) | coś głębszego niż capture — wracamy do analizy |
| R5 (opcja) `rc` | obraz `v0.26.1rc0` przy configu kanonicznym | naprawione upstream — czekamy na stable 0.26.1 | bug żyje w rc |

**Reguła stopu:** pierwszy PASS → powtórz TEN SAM bieg raz (potwierdzenie, że to
nie szczęście w race'ie); 2×PASS = winowajca zidentyfikowany, resztę matrixu tnij
i idź do Cz. C. Każdy bieg ma limit ~15 min ściany.

---

## 2. Budżet czasu i kolejność cięcia

| część | co | min |
|---|---|---:|
| Cz. A | overlaye + biegi R1→R4 (przerywane regułą stopu) | 45-55 |
| Cz. B | (opcja) R5 na v0.26.1rc0 — tylko jeśli został slot i pull obrazu nie zamula | 15 |
| Cz. C | restore v0.20 pełny stack + **weryfikacja** + NOTES + commit/push | 15 |
| | **razem** | **~70** |

**Kolejność cięcia:** R5 → R4 → R3. **Nietykalne:** R1, R2, Cz. C.

---

## Cz. A — matrix izolacyjny (R1→R4)

Wszystkie overlaye w `/tmp`, każdy nadpisuje `image` (repo zostaje na v0.20),
`restart: "no"` (bez crash-loopa) i pełne `command`.

### R1 — bez benchmarkingu combo-kerneli

```bash
cat > /tmp/kimi-r1.yml <<'EOF'
services:
  vllm:
    image: vllm/vllm-openai:v0.26.0
    restart: "no"
    command:
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size 8 --gpu-memory-utilization 0.6 --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2 --enable-auto-tool-choice --language-model-only --max-num-seqs 32 --max-model-len 131072 --max-num-batched-tokens 4096 --speculative-config='{"model":"lightseekorg/kimi-k2.6-eagle3-mla","method":"eagle3","num_speculative_tokens":3,"max_model_len":8192}' --compilation-config='{"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false}}'
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-r1.yml up -d --force-recreate vllm
czekaj
zrzut r1_bez_combobench
# PASS => smoke; zapisz odpowiedź; potem POWTÓRKA: up -d --force-recreate + czekaj + zrzut r1_powtorka
smoke > "$OUT/smoke_r1.json" 2>&1
```

### R2 — bez spec-decode eagle3

```bash
cat > /tmp/kimi-r2.yml <<'EOF'
services:
  vllm:
    image: vllm/vllm-openai:v0.26.0
    restart: "no"
    command:
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size 8 --gpu-memory-utilization 0.6 --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2 --enable-auto-tool-choice --language-model-only --max-num-seqs 32 --max-model-len 131072 --max-num-batched-tokens 4096
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-r2.yml up -d --force-recreate vllm
czekaj
zrzut r2_bez_eagle3
smoke > "$OUT/smoke_r2.json" 2>&1
```

### R3 — bez fuzji allreduce+RMSNorm

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
czekaj
zrzut r3_bez_fuzji_ar
smoke > "$OUT/smoke_r3.json" 2>&1
```

### R4 — enforce-eager (sanity, tylko gdy R1-R3 wszystkie FAIL)

```bash
cat > /tmp/kimi-r4.yml <<'EOF'
services:
  vllm:
    image: vllm/vllm-openai:v0.26.0
    restart: "no"
    command:
      --model moonshotai/Kimi-K2.6 --served-model-name=kimi-k2.6 --host=0.0.0.0 --port=8000 --trust-remote-code --enable-expert-parallel --tensor-parallel-size 8 --gpu-memory-utilization 0.6 --tool-call-parser=kimi_k2 --reasoning-parser=kimi_k2 --enable-auto-tool-choice --language-model-only --max-num-seqs 32 --max-model-len 131072 --max-num-batched-tokens 4096 --speculative-config='{"model":"lightseekorg/kimi-k2.6-eagle3-mla","method":"eagle3","num_speculative_tokens":3,"max_model_len":8192}' --enforce-eager
EOF
docker compose -f "$COMPOSE" -f /tmp/kimi-r4.yml up -d --force-recreate vllm
czekaj
zrzut r4_eager
smoke > "$OUT/smoke_r4.json" 2>&1
```

---

## Cz. B (opcja) — R5 na v0.26.1rc0

Tylko jeśli został slot. Pull obrazu potrafi trwać — odpal wcześniej w tle
(np. zaraz po R1): `docker pull vllm/vllm-openai:v0.26.1rc0 &`. Jeśli tag nie
istnieje, zanotuj i odpuść.

```bash
sed 's/v0.26.0/v0.26.1rc0/' /tmp/kimi-r1.yml > /tmp/kimi-r5.yml   # baza = R1? NIE:
# R5 ma być KANONICZNY config na nowym obrazie — użyj wzoru R3 bez ostatniej flagi
# (skopiuj /tmp/kimi-r3.yml, zmień image na v0.26.1rc0, usuń --compilation-config=...)
docker compose -f "$COMPOSE" -f /tmp/kimi-r5.yml up -d --force-recreate vllm
czekaj
zrzut r5_rc
```

---

## Cz. C — restore v0.20 + weryfikacja + commit (15 min)

**Uwaga z iteracji 1:** `docker_ps_end` pokazał brak vllm/vllm-small/litellm/
open-webui — stack NIE był przywrócony na koniec. Tym razem weryfikacja jest
częścią definicji ukończenia.

```bash
docker compose -f "$COMPOSE" up -d --force-recreate     # pełny stack, obraz z repo = v0.20
# poczekaj aż vllm i vllm-small będą zdrowe (start_period do 30 min):
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
# ^ powtarzaj aż OBA vllm-y "healthy"; do zrzutu końcowego mają być 4 kontenery stacku:
docker ps > "$OUT/docker_ps_end.txt" 2>&1
nvidia-smi > "$OUT/nvidia_smi_end.txt" 2>&1

# tabela werdyktów — wypełnij PASS/FAIL/pominięty przy każdym biegu:
cat > "$OUT/NOTES.md" <<'EOF'
# Werdykty 2026-08-07 iteracja 2 (izolacja v0.26.0)
| bieg | werdykt | uwagi |
|---|---|---|
| R1 bez_combobench | |
| R1 powtórka (jeśli PASS) | |
| R2 bez_eagle3 | |
| R3 bez_fuzji_ar | |
| R4 eager | |
| R5 rc (opcja) | |
- Stack v0.20 przywrócony i healthy (vllm, vllm-small, litellm, open-webui): TAK/NIE
- Odstępstwa od planu:
EOF
${EDITOR:-nano} "$OUT/NOTES.md"

git -C "$REPO" add "$OUT"
git -C "$REPO" commit -m "bench: izolacja CUDA error Kimi v0.26.0 - matrix R1-R5, werdykty"
git -C "$REPO" push origin main
```

Po pushu: analiza laptopowa → decyzja (workaround flagą / czekać na 0.26.1
stable / zostać na 0.20) + ewentualne zgłoszenie upstream z naszymi danymi
(mamy komplet: stack trace, Xid, config, kontrfaktyczny bieg LAUNCH_BLOCKING).

---

## Checklista artefaktów (commit do repo)

- [ ] `log_r*_error.txt`, `log_r*_verdict.txt` dla każdego wykonanego biegu
- [ ] `smoke_r*.json` dla biegów PASS
- [ ] `docker_ps_end.txt` (4 kontenery stacku, oba vllm healthy), `nvidia_smi_end.txt`
- [ ] `NOTES.md` z tabelą werdyktów — **wypełnioną**
- [ ] pełne logi lokalnie w `~/working/nanoserve-diag/2026-08-07_kimi_v026_izolacja/` (NIE do repo)
