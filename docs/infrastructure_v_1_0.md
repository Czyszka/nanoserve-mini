# Infrastructure & Workflow — nanoserve-mini

Ten plik opisuje środowiska pracy, zasady synchronizacji przez GitHub, sposób używania serwera GPU, opcjonalny cloud GPU oraz politykę wyników i sekretów.

To jest dokument organizacyjny. Nie definiuje szczegółowych benchmarków ani scope'u technicznego faz. Te rzeczy są w `ROADMAP.md` i w planach fazowych.

---

## 1. Centralna zasada

Repozytorium GitHub jest **single source of truth** dla projektu.

```text
Laptop domowy  -> GitHub <- Serwer GPU 8xH200
                         <- Opcjonalny GPU cloud
```

GitHub przechowuje:

- kod,
- dokumentację,
- konfiguracje,
- skrypty benchmarkowe,
- małe wyniki tekstowe / JSONL / CSV,
- podsumowania eksperymentów,
- tygodniowe notatki,
- finalne write-upy.

GitHub nie przechowuje:

- wag modeli,
- cache Hugging Face,
- dużych logów,
- dużych profili Nsight,
- dumpów baz danych,
- sekretów,
- tokenów,
- dużych artefaktów benchmarkowych.

---

## 2. Środowiska pracy

## 2.1 Laptop domowy — Windows 11

### Rola

Laptop domowy jest środowiskiem do pracy po godzinach.

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

### Typowy cykl pracy na laptopie

```bash
git pull

# edycja kodu / dokumentacji
# lokalne testy bez GPU, formatowanie, analiza wyników

git status
git add .
git commit -m "docs: update workflow"   # albo feat:/fix:/bench:
git push
```

---

## 2.2 Serwer firmowy — Ubuntu 24 + 8x H200 NVL

### Rola

Serwer 8xH200 NVL jest głównym środowiskiem wykonawczym dla modeli i eksperymentów GPU.

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

Dni z dostępem do serwera traktujemy jak sloty eksperymentalne.

Na serwer nie przychodzimy projektować. Na serwer przychodzimy odpalać przygotowane rzeczy.

Przed wejściem na serwer powinny być gotowe:

- aktualny branch wypchnięty do GitHuba,
- lista komend,
- lista eksperymentów,
- oczekiwane output paths,
- fallback plan,
- `.env` / sekrety ustawione lokalnie na serwerze,
- model / cache przygotowany, jeśli to możliwe.

Typowy flow na serwerze:

```bash
git pull

# run vLLM
# run benchmark
# save raw results / summaries

git status
git add scripts benchmarks results docs README.md
git commit -m "bench: record first vllm ttft run"
git push
```

Po pracy na serwerze:

```bash
# na laptopie
git pull
# analiza wyników, opis, wykresy, wnioski
```

---

## 2.3 Opcjonalny GPU cloud

### Rola

GPU cloud jest buforem do pracy po godzinach, gdy potrzebny jest dostęp do GPU poza serwerem firmowym.

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
- cloud nie jest domyślnym środowiskiem, tylko narzędziem do odblokowania pracy po godzinach.

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

## 4. Branching i commity

## 4.1 Branch główny

```text
main
```

`main` powinien być zawsze w stanie względnie stabilnym:

- dokumentacja się otwiera,
- skrypty nie są celowo popsute,
- README nie kłamie o stanie projektu,
- ostatnie wyniki mają opis albo summary.

## 4.2 Branching początkowy

Na start używamy prostego modelu:

```text
main + małe commity bezpośrednio
```

Dopiero gdy pojawią się większe eksperymenty, można dodać:

```text
work/week-01
bench/yyyy-mm-dd-description
experiment/name
```

## 4.3 Konwencja commitów

Preferowane commit messages:

```text
docs: update infrastructure workflow
feat: add ttft measurement script
bench: record first sequential baseline
fix: handle streaming timeout
infra: add vllm docker command
```

Najważniejsza zasada: commit ma być mały i opisywać jeden logiczny krok.

---

## 5. Repo structure

Docelowa struktura repo:

```text
nanoserve-mini/
  README.md
  ROADMAP.md
  .gitignore
  .env.example
  pyproject.toml

  docs/
    infrastructure.md
    reading-list.md
    nvidia_self_paced_courses.md
    phase-1-plan.md
    weekly/
      w1.md

  scripts/
    measure_ttft_once.py
    run_sequential_benchmark.py
    record_environment.py

  benchmarks/
    prompts/
    configs/

  infra/
    docker/
    compose/

  results/
    raw/
    runs/
    summaries/
```

---

## 6. Cache Hugging Face

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

Jeśli persistent volume nie jest dostępny, cloud traktujemy tylko jako krótkie środowisko testowe i unikamy dużych modeli.

---

## 7. Secrets policy

W repo dodajemy:

```text
.env.example
```

Nie commitujemy:

```text
.env
```

Minimalne `.env.example`:

```env
HF_TOKEN=
VLLM_MODEL=Qwen/Qwen3-0.6B
VLLM_PORT=8000
HF_HOME=/workspace/.cache/huggingface
```

Sekrety per maszyna:

- Hugging Face token,
- GitHub SSH key / token,
- ewentualnie W&B API key,
- ewentualnie cloud provider credentials.

`.gitignore`:

```gitignore
.env
.venv/
__pycache__/
*.pyc
.cache/
*.log
*.ncu-rep
*.nsys-rep
*.sqlite
.DS_Store
```

---

## 8. Results policy

## 8.1 Co commitować

Commitujemy:

- małe JSON / JSONL z wynikami,
- krótkie snapshoty tekstowe,
- podsumowania CSV,
- markdown summaries,
- konfiguracje benchmarków,
- komendy użyte do uruchomienia,
- `record_environment.json` dla runu.

## 8.2 Czego nie commitować

Nie commitujemy:

- wag modeli,
- cache Hugging Face,
- wielkich logów,
- pełnych trace'ów Nsight,
- dumpów baz danych,
- sekretów,
- plików, które bez potrzeby powiększają repo.

Jeżeli wynik jest duży, commitujemy tylko:

- summary,
- ścieżkę lokalną,
- hash / identyfikator runu,
- opis jak odtworzyć.

## 8.3 Struktura wyników runu

Preferowany katalog:

```text
results/runs/<timestamp>_<short_git_hash>/
  config.json
  environment.json
  results.jsonl
  summary.json
  stdout.log          # jeśli mały
  stderr.log          # jeśli mały
```

Dla dużych logów commitujemy tylko `summary.json` i notatkę w markdown.

---

## 9. Reproducibility rules

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

## 10. Docker / native policy

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

---

## 11. Standardowy flow tygodnia

Każdy tydzień ma ten sam rytm:

```text
1. Laptop: przygotuj kod i plan eksperymentu.
2. GitHub: push.
3. Serwer GPU / cloud: pull, run, save results.
4. GitHub: commit + push wyników albo summary.
5. Laptop: pull, analiza, write-up.
6. Weekly note: co zrobione, co blokuje, co dalej.
```

---

## 12. Weekly note

Każdy tydzień ma plik:

```text
docs/weekly/wN.md
```

Format:

```md
# Week N

## Goal

## Done

## Measurements

## Problems

## Decisions

## Next week
```

Jeżeli używasz GPU cloud, dodaj:

```md
## Cloud cost

- Provider:
- GPU:
- Hours:
- Cost:
- Purpose:
```

---

## 13. Minimalny flow sesji na serwerze 8xH200

Przed sesją:

```text
- git push z laptopa
- lista komend gotowa
- model wybrany
- output directory wybrany
- fallback: mały model / krótszy benchmark
```

W trakcie sesji:

```bash
git pull
mkdir -p results/runs/<run_id>

# run server
# run benchmark
# save environment
# save results

git add results/runs/<run_id> docs README.md scripts benchmarks
git commit -m "bench: record <description>"
git push
```

Po sesji:

```text
- git pull na laptopie
- analiza wyników
- update weekly note
- decyzja co uruchomić następnym razem
```

---

## 14. Disaster recovery

### Jeśli laptop padnie

- wszystko ważne powinno być w GitHub,
- nowy laptop wymaga tylko Git, Python/uv, IDE i kluczy,
- środowisko GPU jest na serwerze/cloud.

### Jeśli serwer 8xH200 jest chwilowo niedostępny

- kontynuujemy dokumentację, analizę i skrypty na laptopie,
- małe testy GPU przenosimy do cloud,
- nie rozszerzamy scope'u tylko dlatego, że serwer jest niedostępny.

### Jeśli wyciekną sekrety

- rotacja HF token,
- rotacja GitHub key/token,
- rotacja W&B/cloud token, jeśli używany,
- sprawdzenie historii Git pod kątem sekretów.

---

## 15. Decyzje początkowe

| Obszar | Decyzja |
|---|---|
| Centralny system pracy | GitHub repo |
| Laptop domowy | dev, docs, analysis |
| Serwer 8xH200 | primary GPU execution |
| GPU cloud | optional support for home GPU testing |
| Budget cloud | max 200 USD/month |
| Serving | vLLM |
| Benchmark scripts | Python + uv |
| Dokumentacja | Markdown |
| Wyniki | JSONL / CSV / markdown summaries |
| Cache modeli | Hugging Face cache poza repo |

---

## 16. Otwarte pytania

- [ ] Czy repo będzie publiczne od początku, czy prywatne do końca F1?
- [ ] Czy GPU cloud jest potrzebny już w tygodniu 1, czy dopiero gdy brak dostępu do serwera blokuje pracę?
- [ ] Jaki provider GPU cloud wybrać, jeśli będzie potrzebny?
- [ ] Czy używać W&B, czy na razie wystarczą lokalne JSONL/CSV + markdown summaries?
- [ ] Czy `results/raw` commitować selektywnie, czy trzymać raw lokalnie i commitować tylko summaries?

---

## 17. Najbliższy następny krok

Utworzyć repo i dodać pliki organizacyjne:

```text
README.md
ROADMAP.md
docs/infrastructure.md
docs/reading-list.md
docs/nvidia_self_paced_courses.md
.env.example
.gitignore
```

Pierwszy commit:

```bash
git add .
git commit -m "docs: init project infrastructure workflow"
```

Po tym przejść do pierwszego uruchomienia vLLM i pierwszego pomiaru TTFT.
