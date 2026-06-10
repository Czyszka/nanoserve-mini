# Infrastructure — nanoserve-mini

Ten plik opisuje, **gdzie znajduje się sprzęt projektu i do czego służy**: laptop
domowy (Windows 11), serwer firmowy 8xH200 NVL i opcjonalny GPU cloud. Zawiera też
techniczne reguły specyficzne dla maszyn (cache HF, reproducibility, Docker/native).

To dokument organizacyjny dotyczący sprzętu i lokalizacji. Reguły wspólne (scope,
sekrety, wyniki, commit conventions, walidacja) są w `CLAUDE.md`. Aktualny stan
projektu jest w `docs/operations/agent-state.md`. Zakres techniczny faz jest w
`docs/project/roadmap.md`.

---

## 1. Centralna zasada

Repozytorium GitHub jest **single source of truth** dla projektu.

```text
Laptop domowy  -> GitHub <- Serwer GPU 8xH200
                         <- Opcjonalny GPU cloud
```

GitHub przechowuje kod, dokumentację, konfiguracje, skrypty benchmarkowe, małe
wyniki tekstowe (JSONL/CSV), podsumowania i write-upy. GitHub **nie** przechowuje
wag modeli, cache Hugging Face, dużych logów, profili Nsight, dumpów baz danych ani
sekretów (pełna polityka: `CLAUDE.md`).

---

## 2. Środowiska pracy

## 2.1 Laptop domowy — Windows 11

### Lokalizacja i rola

Laptop stoi **w domu**. Jest to środowisko do pracy po godzinach.

Służy do:

- pisania kodu,
- pisania dokumentacji,
- przygotowywania benchmark scripts,
- analizowania wyników,
- robienia wykresów i tabel,
- pracy z GitHub,
- planowania następnych eksperymentów,
- przygotowania komend przed sesją GPU.

Nie jest głównym miejscem do:

- uruchamiania dużych modeli,
- benchmarków GPU,
- profilowania GPU,
- długich eksperymentów inference.

### Wymagania lokalne

- Git
- GitHub access
- VS Code / Cursor / inne IDE
- Python 3.12
- uv
- SSH client
- opcjonalnie Docker Desktop

---

## 2.2 Serwer firmowy — Ubuntu 24 + 8x H200 NVL

### Lokalizacja i rola

Serwer stoi **w pracy** (firma). Jest głównym środowiskiem wykonawczym dla modeli
i eksperymentów GPU.

Służy do:

- uruchamiania vLLM,
- testowania modeli,
- pierwszych benchmarków TTFT / TPOT / throughput,
- eksperymentów z concurrency,
- eksperymentów z KV cache / prefix cache,
- Prometheus/Grafana observability,
- późniejszego profilowania,
- późniejszych testów kernela Triton.

### Topologia GPU/CPU (stan wiedzy 2026-06-10; datasheet + env snapshot)

Źródła: datasheet platformy `docs/operations/sys-521ge-tnrt.md` (Supermicro
**SYS-521GE-TNRT**, płyta X13DEG-OA) i `results/raw/server_env_snapshot.json`
(lscpu, nvidia-smi z 2026-05-06).

- **Interconnect GPU↔GPU: wyłącznie PCIe** — brak NVLink i NVSwitch.
  Potwierdzone z logów vLLM (custom all-reduce: *"not supported on more than
  two PCIe-only GPUs"*; FlashInfer: *"expected on GPUs without NVSwitch"*).
  **NVLink Bridge jest oficjalną opcją tego chassis** (datasheet: "GPU-GPU
  interconnect: NVIDIA NVLink Bridge, optional") — ścieżka dokupienia mostków
  istnieje; decyzja zakupowa = issue #50.
- **Dual-socket, dual-root:** 2× Intel Xeon Gold 6530 (32C/64T każdy; lscpu:
  `Socket(s): 2`). Datasheet: architektura **"Dual-Root PCIe"**, CPU↔GPU =
  *"PCIe 5.0 x16 Switch Dual-Root"* — GPU wiszą pod switchami PCIe, po jednej
  domenie root na socket. Dodatkowo `NUMA node(s): 4` (SNC-2: każdy socket
  podzielony na 2 węzły NUMA).
- **Parowanie GPU za switchami (z bus-ID, do potwierdzenia `topo -m`):**
  GPU0/1 = `1D/1E`, GPU2/3 = `40/41`, GPU4/5 = `AA/AB`, GPU6/7 = `BB/BC` —
  cztery pary po wspólnym switchu; zakresy adresów wskazują GPU0–3 pod CPU0,
  GPU4–7 pod CPU1. Wynikają z tego **trzy klasy ścieżek GPU↔GPU**:
  1. para za wspólnym switchem (najtaniej),
  2. wspólny socket, różne switche (przez root complex),
  3. **cross-socket przez UPI** (`GPU → PCIe → CPU0 → UPI → CPU1 → PCIe →
     GPU`, najdrożej). TP=8 z konstrukcji przechodzi przez UPI; mostki NVLink
  4-way muszą być sparowane zgodnie z socketami (wyspy 4+4).
- **Jak to się łączy (schemat presumed — bus-ID + datasheet; potwierdzić
  `nvidia-smi topo -m`):**

  ```text
                    UPI (cross-socket)
     CPU0 (Xeon 6530)  <==========>  CPU1 (Xeon 6530)
     NUMA 0+1                        NUMA 2+3
      |         |                     |         |
    PCIe5     PCIe5                 PCIe5     PCIe5
     x16       x16                   x16       x16
      |         |                     |         |
    [SW0]     [SW1]                 [SW2]     [SW3]
     |  |      |  |                  |  |      |  |
   GPU0 GPU1 GPU2 GPU3             GPU4 GPU5 GPU6 GPU7
   1D   1E   40   41               AA   AB   BB   BC
  ```

  Przykłady klas ścieżek (oczekiwane oznaczenia w `topo -m`):
  `GPU0↔GPU1` przez SW0 (`PIX`, klasa 1) · `GPU0↔GPU2` SW0 → root CPU0 → SW1
  (`PXB`/`NODE`, klasa 2) · `GPU0↔GPU4` SW0 → CPU0 → **UPI** → CPU1 → SW2
  (`SYS`, klasa 3).
- **DCGM dostępny na hoście (tier-1):** `dcgmi` działa (potwierdzone
  2026-06-10) — w planach sesji nie trzeba fallbacków exporter/dmon. Wzorzec
  samplera: `dcgmi dmon -e 155,1002,1004,1005,1009,1010 -d 1000 -c <N>`
  (power, SM_ACTIVE, PIPE_TENSOR_ACTIVE, DRAM_ACTIVE, PCIE_TX/RX).
- Do potwierdzenia na serwerze: `nvidia-smi topo -m` (macierz PIX/PXB/NODE/SYS
  per para GPU) — w planie
  `docs/plans/2026-06-10-bottleneck-followup-session.md`; po zebraniu wkleić
  macierz do tej sekcji.

### Dostępność

```text
Dostęp: 2 dni w tygodniu
Godziny: 8:00-15:00
Status: główna maszyna GPU projektu
```

### Zasada użycia

Dni z dostępem do serwera traktujemy jak sloty eksperymentalne. Na serwer nie
przychodzimy projektować — przychodzimy odpalać przygotowane rzeczy.

Przed wejściem na serwer powinny być gotowe:

- aktualny branch wypchnięty do GitHuba,
- lista komend,
- lista eksperymentów,
- oczekiwane output paths,
- fallback plan,
- `.env` / sekrety ustawione lokalnie na serwerze. **Kanoniczna
  lokalizacja: główny katalog repo (`~/nanoserve-mini/.env`), nie
  `serving/compose/.env`.** `docker compose` jest odpalany z roota repo,
  więc auto-ładuje root `.env`; ręczne `source .env` w planach też zakłada
  root. Plik jest w `.gitignore` (`.env`), commitujemy tylko `.env.example`.
- model / cache przygotowany, jeśli to możliwe.

---

## 2.3 Opcjonalny GPU cloud

### Rola

GPU cloud jest buforem do pracy po godzinach, gdy potrzebny jest dostęp do GPU
poza serwerem firmowym.

Służy do:

- sanity check vLLM poza serwerem,
- testowania małych modeli,
- odtwarzania problemów środowiskowych,
- rozwijania benchmark harness,
- krótkich eksperymentów 1xGPU,
- przygotowania pracy przed wejściem na H200.

Nie służy do:

- masowego benchmarkowania,
- długich eksperymentów bez kontroli kosztów,
- zastępowania serwera 8xH200,
- trzymania instancji włączonej bez konkretnego celu.

### Budżet

```text
Maksymalny budżet miesięczny: 200 USD
Preferencja: 1x H100 / A100 / L40S / RTX 4090, zależnie od ceny i dostępności
```

### Zasady kosztowe

- instancja uruchamiana tylko na konkretną sesję,
- po sesji zawsze shutdown / destroy,
- przed startem sesji lista komend jest przygotowana lokalnie,
- koszt sesji zapisujemy w weekly note,
- cloud nie jest domyślnym środowiskiem, tylko narzędziem do odblokowania pracy
  po godzinach.

---

## 3. Podział pracy między środowiska

| Typ pracy | Laptop domowy | Serwer 8xH200 | GPU cloud |
|---|---:|---:|---:|
| Dokumentacja | TAK | Niepreferowane | Nie |
| Pisanie benchmark scripts | TAK | Tylko poprawki | TAK |
| Lokalne testy bez GPU | TAK | TAK | TAK |
| Uruchomienie vLLM | Nie | TAK | TAK |
| Pierwszy TTFT | Nie | TAK | TAK |
| Benchmark GPU | Nie | TAK | TAK, małe testy |
| Prometheus/Grafana | Przygotowanie configu | TAK | Opcjonalnie |
| Profilowanie GPU | Nie | TAK | Opcjonalnie |
| Triton kernel dev | Kod/analiza | TAK | TAK |
| Analiza wyników | TAK | Minimalnie | TAK |
| Wykresy | TAK | Niepreferowane | Opcjonalnie |
| Commit/push | TAK | TAK | TAK |

---

## 4. Cache Hugging Face

Modele są duże. Pobieranie modeli w czasie sesji GPU marnuje czas i pieniądze.

### Serwer 8xH200

Na serwerze używamy stałego katalogu cache:

```text
~/hf_cache
```

Cel:

- pobrać model raz,
- używać wielokrotnie,
- nie tracić slotu pracy na download.

### GPU cloud

Na cloud preferujemy persistent volume, jeśli provider to wspiera.

Mount docelowy:

```text
~/.cache/huggingface
```

Jeśli persistent volume nie jest dostępny, cloud traktujemy tylko jako krótkie
środowisko testowe i unikamy dużych modeli.

---

## 5. Reproducibility rules

Każdy benchmark powinien zapisać:

- git commit hash,
- model name,
- model revision, jeśli znany,
- vLLM version,
- Python version,
- CUDA version,
- NVIDIA driver version,
- GPU model,
- liczba GPU użytych w runie,
- container image albo Python environment,
- command used to start server,
- command used to run benchmark,
- decoding parameters,
- workload definition,
- raw output file path.

Docelowy skrypt:

```text
scripts/record_environment.py
```

Ten skrypt powinien generować JSON dołączany do każdego benchmarku.

---

## 6. Docker / native policy

Na start:

```text
vLLM server: Docker preferowany
Benchmark scripts: Python + uv
Prometheus/Grafana: Docker Compose później
Triton kernel work: do decyzji w Fazie 3
```

Nie budujemy od razu pełnego środowiska produkcyjnego.

W Tygodniu 1 wystarczy:

- uruchomić vLLM,
- wykonać jeden request,
- zmierzyć TTFT,
- zapisać environment snapshot.
