# Runbooki pokazowe (demo) — konwencje

Gotowce typu "odpal i pokaż": szybki pokaz działania stacku i wyników (np.
Kimi + Grafana) jednym poleceniem, bez czytania procedury. To **nie są**
procedury pomiarowe — liczby z demo nie wchodzą do historii benchmarków.

Decyzja 2026-08-11: implementacja w bashu — wspólna biblioteka
[`lib.sh`](./lib.sh) + skrypt `demo-<temat>.sh` na gotowiec, z krótką kartą
`demo-<temat>.md` obok.

## Kontrakt

Każdy `demo-*.sh` musi spełniać wszystkie punkty:

1. **Jedno polecenie bez argumentów działa**: `bash demo-<temat>.sh`.
   Flagi opcjonalne (np. `--fast` = krótsze obciążenie).
2. **Read-only wobec stacku**: zero restartów silnika, zero zmian
   konfiguracji, żadnych overlayów compose. Stack leży → `up -d` z configu
   repo. Demo zostawia stan taki, jaki zastało (lub lepszy: podniesiony).
3. **Fail-fast w pierwszych ~30 s**: env, health, flagi silnika
   (`check_engine_baseline`). Jak ma paść — pada od razu z czytelnym
   `STOP: <powód>`, nie w 4. minucie pokazu.
4. **Strict mode**: `set -euo pipefail` + `trap` na sprzątanie. To skrypt
   uruchamiany `bash demo-*.sh`, nie wklejka do interaktywnego SSH — zakazy
   z runbooków pomiarowych ("bez `set -e`, bez `exit`") tu **nie obowiązują**.
5. **Epilog `CO POKAZAĆ`**: na końcu skrypt drukuje URL-e dashboardów, które
   panele oglądać i jaki kształt ma być widoczny (gotowa narracja dla widza).
6. **Artefakty poza repo**: `~/working/nanoserve-demo/<data>_<temat>/`.
   Nigdy do `results/runs/` — historia pomiarowa musi zostać czysta
   (porównywalność c1/c32 z metodologii opiera się na tym, że każdy wpis
   tam to pomiar wg reguł, z wygrzewką).
7. **Budżet czasu w nagłówku karty**; cel: ≤10 min przy ciepłym stacku.
8. **Helpery tylko przez `source lib.sh`** — nie kopiowane do skryptu.
   Nowy helper najpierw trafia do `lib.sh` (przenoszony ze sprawdzonych
   planów/runbooków, zgodnie z regułą domową), potem jest używany.

## Demo vs pomiar

| | demo (`demo-*.sh`) | pomiar (runbook pomiarowy / plan sesji) |
|---|---|---|
| cel | pokazać mechanizm | zmierzyć liczbę |
| wygrzewka | zbędna | obowiązkowa (od 08-03) |
| obciążenie | minimalne, żeby wykresy ożyły (~5 min) | pełne wg metodologii |
| artefakty | katalog roboczy, jednorazowe | `results/runs/`, commitowane |
| zmiany konfiguracji | zakazane | dozwolone wg planu, z restore |
| dataset | SWE custom (offline, prompty w pliku — zero HF w trakcie pokazu) | wg metodologii |

## Struktura plików

```text
serving/runbooks/
  lib.sh              wspólne helpery (source, nie kopiuj)
  demo-<temat>.sh     skrypt gotowca
  demo-<temat>.md     karta gotowca
```

Karta `demo-<temat>.md` — szkielet:

```markdown
# demo: <temat>

Co pokazuje: <1-2 zdania — mechanizm, nie liczby>.
Czas: ~X min (ciepły stack) / ~Y min (zimny).
Wymaga: <env / .env / dataset / co musi stać>.

Uruchomienie: `bash serving/runbooks/demo-<temat>.sh`

Co mówić widzowi: <2-4 punkty — co widać na ekranie i dlaczego tak wygląda>.
Znane ograniczenia: <opcjonalnie>.
```

## Zasady `lib.sh`

- Funkcje **zwracają kod ≠ 0** zamiast wołać `exit` — o przerwaniu decyduje
  skrypt wywołujący (strict mode zrobi to za niego).
- Kompatybilne z `set -euo pipefail`: sondy (curl/grep) opakowane w `if`,
  zmienne z domyślnymi `${VAR:-}`.
- Bez side-effectów poza `$DEMO_DIR` i podnoszeniem stacku z configu repo.
- Walidacja na laptopie: `bash -n lib.sh` (składnia). Test realny — tylko na
  serwerze; po pierwszym przebiegu odnotuj wynik w karcie gotowca.

## Planowane gotowce

- `demo-kimi-grafana` — pierwszy; po sesji DCGM 2026-08-12, żeby pokazywał
  oba dashboardy (vLLM Phase 1 + korelacyjny vLLM↔DCGM).
- `demo-spec-decode` — akceptacja Eagle3 na żywo (kandydat).
