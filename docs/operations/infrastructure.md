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

### Topologia GPU/CPU (stan wiedzy 2026-08-03; `topo -m` zmierzone)

Źródła: datasheet platformy `docs/operations/sys-521ge-tnrt.md` (Supermicro
**SYS-521GE-TNRT**, płyta X13DEG-OA), `results/raw/server_env_snapshot.json`
(lscpu, nvidia-smi z 2026-05-06) oraz pomiary po montażu mostków:
`results/runs/2026-07-31_nvlink_install/nvlink/` i
`results/runs/2026-08-03_nvlink_gap_fill/nvlink/`.

- **Interconnect GPU↔GPU: NVLink 4-way w dwóch wyspach + PCIe między
  wyspami** (od 2026-07-31; wcześniej wyłącznie PCIe). Mostki NVLink 4-way
  zainstalowane zgodnie z socketami: **wyspa GPU 0–3 (CPU0) i wyspa GPU 4–7
  (CPU1)**; w każdej wyspie pełna siatka `NV6` (każda para połączona),
  między wyspami nadal `SYS` (PCIe + UPI). Zmierzona macierz `topo -m`:

  ```text
        GPU0  GPU1  GPU2  GPU3  GPU4  GPU5  GPU6  GPU7
  GPU0   X    NV6   NV6   NV6   SYS   SYS   SYS   SYS
  GPU1  NV6    X    NV6   NV6   SYS   SYS   SYS   SYS
  GPU2  NV6   NV6    X    NV6   SYS   SYS   SYS   SYS
  GPU3  NV6   NV6   NV6    X    SYS   SYS   SYS   SYS
  GPU4  SYS   SYS   SYS   SYS    X    NV6   NV6   NV6
  GPU5  SYS   SYS   SYS   SYS   NV6    X    NV6   NV6
  GPU6  SYS   SYS   SYS   SYS   NV6   NV6    X    NV6
  GPU7  SYS   SYS   SYS   SYS   NV6   NV6   NV6    X
  ```

  Zmierzone przepustowości: P2P w wyspie 132,8 GB/s (kontrola cross-island
  29,1), NCCL busbw w wyspie 185–333 GB/s, 2+2 cross-island 24,8–31,3 GB/s
  (kolektyw hierarchiczny). Konsekwencje dla vLLM: custom all-reduce
  **aktywny przy TP≤4 w jednej wyspie** (pełna siatka), przy TP=8 nadal
  wyłączany (grupa TP nie jest pełną siatką — oczekiwane przy 4+4). Zyski
  serwowania i model decyzyjny: T9 §14, issue #50.
- **Dual-socket, dual-root:** 2× Intel Xeon Gold 6530 (32C/64T każdy; lscpu:
  `Socket(s): 2`). Datasheet: architektura **"Dual-Root PCIe"**, CPU↔GPU =
  *"PCIe 5.0 x16 Switch Dual-Root"* — GPU wiszą pod switchami PCIe, po jednej
  domenie root na socket. Dodatkowo `NUMA node(s): 4` (SNC-2: każdy socket
  podzielony na 2 węzły NUMA).
- **Parowanie GPU za switchami PCIe (z bus-ID; spójne z `topo -m`):**
  GPU0/1 = `1D/1E`, GPU2/3 = `40/41`, GPU4/5 = `AA/AB`, GPU6/7 = `BB/BC` —
  cztery pary po wspólnym switchu; GPU0–3 pod CPU0, GPU4–7 pod CPU1
  (`CPU Affinity` w macierzy: 0-15,64-79 vs 32-47,96-111). Po montażu mostków
  klasy ścieżek GPU↔GPU są **dwie**:
  1. **w wyspie: NVLink `NV6`** (dawne klasy „wspólny switch" i „wspólny
     socket" zlały się w jedną — NVLink omija PCIe),
  2. **między wyspami: `SYS`** (PCIe + UPI, jak dotąd). TP=8 z konstrukcji
     przechodzi cross-island; ruch NCCL w wyspach idzie po NVLinku
     (hierarchicznie), stąd Kimi TP8 zyskuje mimo braku pełnej siatki.
- **Jak to się łączy (PCIe pod spodem bez zmian; NVLink nakłada się na
  wyspy):**

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
    └───┴──NVLink──┴───┘            └───┴──NVLink──┴───┘
        wyspa 0-3 (NV6)                 wyspa 4-7 (NV6)
  ```

  Przykłady ścieżek (zmierzone oznaczenia w `topo -m`):
  `GPU0↔GPU1`, `GPU0↔GPU2`, `GPU0↔GPU3` — **NVLink `NV6`** (w wyspie) ·
  `GPU0↔GPU4` SW0 → CPU0 → **UPI** → CPU1 → SW2 (`SYS`, cross-island).
- **DCGM dostępny na hoście (tier-1):** `dcgmi` działa (potwierdzone
  2026-06-10) — w planach sesji nie trzeba fallbacków exporter/dmon. Wzorzec
  samplera: `dcgmi dmon -e 155,1002,1004,1005,1009,1010,1011,1012 -d 1000 -c <N>`
  (power, SM_ACTIVE, PIPE_TENSOR_ACTIVE, DRAM_ACTIVE, PCIE_TX/RX,
  **NVLINK_TX/RX** — pola 1011/1012 działają, potwierdzone 2026-08-03;
  probe nagłówka i tak obowiązkowy: przy niedostępności kolumny NVL znikają
  PO CICHU, wzorzec probe'a w
  `docs/plans/2026-08-03-nvlink-gap-fill.md` Cz. 1c). Uwaga interpretacyjna:
  pola NVL liczą też ruch custom-all-reduce i ścieżki P2P poza NCCL-em
  (`NCCL_P2P_DISABLE=1` nie zeruje NVL — T9 §14.6).

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
