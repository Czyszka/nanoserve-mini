# Pierwsza sesja na serwerze — runbook

Cel: zero improwizacji w pierwszym slocie na Ubuntu 24 / 8x H200 NVL. Kolejność niżej jest sztywna. Każdy krok ma jasne kryterium "OK".

Slot serwerowy jest rzadki (2 dni/tydz). Tej sesji **nie** używamy do stawiania vLLM. Cel sesji to tylko snapshot środowiska + decyzja o ścieżce instalacji.

---

## Wymagania wstępne

- Dostęp SSH do serwera.
- GitHub remote dostępny: `https://github.com/Czyszka/nanoserve-mini.git`.
- `uv` zainstalowane na serwerze (jeśli nie, instalacja wg [oficjalnych instrukcji](https://docs.astral.sh/uv/getting-started/installation/) — to jest jedyna globalna instalacja jaką akceptujemy).

Nie potrzebujemy: Dockera, vLLM, modeli, HF tokena. To dopiero po snapshot decyzji.

---

## Krok 1 — clone / pull repo

Nowy serwer:

```bash
cd ~
git clone https://github.com/Czyszka/nanoserve-mini.git
cd nanoserve-mini
```

Jeśli repo już istnieje:

```bash
cd ~/nanoserve-mini
git fetch origin
git checkout main
git pull --ff-only origin main
git status
```

OK gdy: `git status` pokazuje `working tree clean` na `main`, HEAD równy `origin/main`.

---

## Krok 2 — `uv sync --extra dev`

```bash
uv sync --extra dev
```

OK gdy: komenda kończy się bez błędu i tworzy `.venv/`. Brak instalacji jakichkolwiek pakietów GPU na tym etapie — `pyproject.toml` na razie ich nie deklaruje.

---

## Krok 3 — `scripts/check_server_env.py`

```bash
uv run python scripts/check_server_env.py
```

OK gdy:

- skrypt kończy się bez wyjątku,
- powstaje plik `results/raw/server_env_snapshot.json`,
- w stdout widać sekcje `platform` + `commands`.

Skrypt nie failuje, jeśli któraś komenda nie jest zainstalowana — zapisuje wynik z `command not found` i jedzie dalej. To jest świadome, bo właśnie ten snapshot ma nam **powiedzieć**, czego brakuje.

---

## Krok 4 — inspect `results/raw/server_env_snapshot.json`

Otwieramy plik i odpowiadamy na pytania z `docs/agent-state.md` ("Open questions"):

- [ ] `nvidia_smi`: 8x H200 NVL widoczne? `returncode == 0`, w `stdout` 8 GPU.
- [ ] `nvidia_smi_query`: każde GPU ma `memory.total ~= 141 GB` i ten sam `driver_version`?
- [ ] `nvcc_version`: CUDA toolkit zainstalowany? Jeśli `command not found`, decydujemy czy potrzebny (zwykle nie — vLLM przychodzi z prebuilt CUDA wheels).
- [ ] `python_version`: 3.10–3.12? (vLLM ma matrycę kompatybilności).
- [ ] `uv_version`: zainstalowane?
- [ ] `docker_version` + `docker_compose_version`: dostępne?
- [ ] `memory`: ile RAM, ile swap?
- [ ] `disk`: ile wolnego miejsca? (modele HF potrafią zająć dziesiątki GB).

Zapisujemy odpowiedzi w głowie / notesie — jedziemy do następnego kroku.

---

## Krok 5 — commit + push snapshotu

Snapshot jest mały (kilka–kilkanaście KB JSON), więc go committujemy. Polityka `Results and secrets policy` na to pozwala (mały, tekstowy, useful).

```bash
git status
git add results/raw/server_env_snapshot.json
git commit -m "infra: add first server env snapshot"
git push origin main
```

OK gdy: push przechodzi, `origin/main` zawiera plik.

Jeśli plik byłby duży (>~100 KB) — committujemy tylko summary, nie raw. Na tym etapie nie powinno tak być.

---

## Krok 6 — decyzja: Docker vs uv/native dla vLLM

Wybieramy **jedną** ścieżkę i zapisujemy decyzję w `docs/agent-state.md`. Kryteria:

**Wybierz Docker, jeśli:**

- `docker --version` i `docker compose version` zwróciły `returncode == 0`,
- chcemy pełnej izolacji od systemowego CUDA / Pythona,
- planujemy łatwy rollback do innej wersji vLLM przez tag obrazu.

**Wybierz uv/native, jeśli:**

- Docker nie jest dostępny i nie chcemy go ciągnąć tylko po to,
- driver NVIDIA + CUDA na hoście są spójne z wymaganiami vLLM,
- chcemy mieć szybki iteracyjny development (edycja kodu vLLM jako editable install) — w `nanoserve-mini` to nie jest priorytet, ale jeśli wybieramy native, dostajemy to za darmo.

**Default tie-breaker:** jeśli oba dostępne — Docker. Łatwiej powtórzyć i łatwiej przekazać innej osobie.

Aktualizujemy `docs/agent-state.md`:

- "Current decisions" → wpis `vLLM setup` z konkretną wartością (`Docker` / `uv-native`).
- "Open questions" → odhaczamy odpowiedzi z kroku 4.
- "Handoff log" → nowy wpis z datą sesji, co zrobione, co dalej.

Commit:

```bash
git add docs/agent-state.md
git commit -m "docs: record vLLM setup decision after server env snapshot"
git push origin main
```

---

## Co NIE robimy w tej sesji

- Nie instalujemy vLLM.
- Nie pobieramy modeli z HF.
- Nie stawiamy Prometheus/Grafany.
- Nie konfigurujemy systemd / nginx / nic produkcyjnego.

Wszystko powyżej jest dopiero **po** decyzji z kroku 6, w osobnym slocie serwerowym, z osobnym planem.

---

## Definicja "sesja udana"

1. `results/raw/server_env_snapshot.json` jest na `origin/main`.
2. Decyzja Docker vs native jest zapisana w `docs/agent-state.md` na `origin/main`.
3. Wiemy, jaki jest następny konkretny krok (np. "pull obrazu vLLM X.Y.Z" albo "uv add vllm w nowym extras").

Jeśli te 3 punkty są spełnione — sesja zaliczona, niezależnie od tego ile czasu zostało w slocie. Resztę slotu można zostawić, nie ma sensu rozpoczynać kolejnego dużego kroku w stresie.
