# Infrastructure — nanoserve-mini

Ten plik opisuje, **gdzie znajduje się sprzęt projektu i do czego służy**: laptop
domowy (Windows 11), serwer firmowy 8xH200 NVL i opcjonalny GPU cloud. Zawiera też
techniczne reguły specyficzne dla maszyn (cache HF, reproducibility, Docker/native).

To dokument organizacyjny dotyczący sprzętu i lokalizacji. Reguły wspólne (scope,
sekrety, wyniki, commit conventions, walidacja) są w `CLAUDE.md`. Aktualny stan
projektu jest w `docs/agent-state.md`. Zakres techniczny faz jest w `ROADMAP.md`.

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
- `.env` / sekrety ustawione lokalnie na serwerze,
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
