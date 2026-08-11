# Runbooks

Ten katalog zawiera powtarzalne runbooki operacyjne dla projektu `nanoserve-mini` — bootstrap środowiska, sesje serwerowe, walidacje. Każdy runbook to przepis używany wielokrotnie, a nie jednorazowy zapis historyczny.

Używaj ich, gdy potrzebujesz wykonać znaną procedurę z minimalną improwizacją (nowa maszyna, reinstalacja, handoff do innego operatora, weryfikacja po update'ach).

## Lista runbooków

- [`server-env-bootstrap.md`](./server-env-bootstrap.md) — bootstrap / re-walidacja środowiska serwera GPU: snapshot env + decyzja Docker vs uv-native dla vLLM.
- [`load-test-and-grafana.md`](./load-test-and-grafana.md) — load test vLLM (`vllm bench serve`) + podgląd metryk w Grafanie i screen; z gotchami z sesji 2026-06-05 (offline env, `pip install pandas datasets`, `--trust-remote-code`).
- [`kimi-concurrency-ladder-swe.md`](./kimi-concurrency-ladder-swe.md) — sprawdzenie/postawienie stacku (Kimi + Prometheus + Grafana) i drabinka współbieżności c=1/16/32/64 na zestawie SWE custom; JSON-y klienta, akceptacja spekulacji per szczebel, cross-check z Prometheusa, screen dashboardu.

## Runbooki pokazowe (demo)

Osobna kategoria: gotowce "odpal i pokaż" — jeden skrypt podnosi/sprawdza stack,
puszcza krótkie obciążenie i mówi, co oglądać w Grafanie. Nie są procedurami
pomiarowymi; ich artefakty nie wchodzą do `results/runs/`.

- [`demo-conventions.md`](./demo-conventions.md) — kontrakt gotowców (8 punktów),
  różnica demo vs pomiar, szkielet karty.
- [`lib.sh`](./lib.sh) — wspólne helpery (`ensure_kimi`, `ensure_obs`,
  `check_engine_baseline`, `demo_load`…); `source`, nie kopiuj.
- Pierwszy gotowiec `demo-kimi-grafana.sh` — planowany po sesji DCGM 2026-08-12.

## Zasady

- Dodawaj nowe runbooki tutaj, gdy procedura okazuje się powtarzalna (zostanie wykonana więcej niż raz).
- Każdy runbook powinien mieć: cel, krok-po-kroku z kryterium "OK" dla każdego kroku, definicję sukcesu, listę rzeczy świadomie pominiętych.
- Jednorazowe zapisy (np. log konkretnej sesji) trzymaj poza tym katalogiem — to nie jest historia, tylko biblioteka przepisów.
