# Server session summary - 2026-05-19

Podsumowanie sesji serwerowej na Ubuntu 24 / 8x H200 NVL. To jest notatka
historyczna z dnia 2026-05-19, z krótkim statusem późniejszych follow-upów na
2026-05-20.

## Cel sesji

Celem było domknięcie minimum Phase 1 po stronie serwera: zsynchronizować
rzeczywisty Docker Compose z repo, uruchomić LiteLLM Proxy przed dwoma usługami
vLLM, wykonać smoke testy i pełne benchmark suite dla Kimi K2.6 oraz
DeepSeek-V4-Flash, a także wystartować podstawowy stack Prometheus/Grafana.

Sesja była wykonawcza, nie projektowa. Prace dokumentacyjne, repo hygiene i
poprawki parserów zostały świadomie przeniesione na laptop.

## Co zostało zrobione

- Odzyskano i wypchnięto wcześniejsze wyniki benchmarków z 2026-05-11.
- Zsynchronizowano tracked compose z faktycznie działającym stackiem serwerowym.
- Poprawiono konfigurację Kimi K2.6: zamiast błędnego DP setupu używany jest
  tensor parallelism (`--tensor-parallel-size 8`) z Eagle3 speculative decoding.
- Potwierdzono, że `vllm`, `vllm-small` i OpenWebUI są uruchomione i komunikują
  się poprawnie.
- Uruchomiono LiteLLM Proxy na porcie 4000 i potwierdzono routing po polu
  `model` do Kimi oraz DeepSeek.
- Wykonano i wypchnięto compose smoke results dla Kimi K2.6 i DeepSeek-V4-Flash.
- Wykonano i wypchnięto `run_bench_suite.py` przez LiteLLM Proxy dla obu modeli.
- Zidentyfikowano problem Kimi TTFT/TPOT: skrypt pokazywał `n/a`, bo Kimi
  streamuje reasoning w `delta.reasoning`, a parser liczył tylko `delta.content`.
- Zebrano raw Kimi stream-debug artefacts do późniejszej naprawy parsera.
- Dodano i uruchomiono podstawową konfigurację Prometheus + Grafana.
- Utworzono issue #31, #32 i #33 dla prac laptopowych po sesji.

## Najważniejsze artefakty

Run directories w `results/runs/`:

- `2026-05-11_deepseek_v4_flash_20pct_baseline` - odzyskany wcześniejszy baseline
  DeepSeek.
- `2026-05-19_kimi-k2-6_compose-smoke` - smoke result dla Kimi przez compose.
- `2026-05-19_deepseek-v4-flash_compose-smoke` - smoke result dla DeepSeek przez
  compose.
- `2026-05-19_litellm-smoke` - smoke test LiteLLM Proxy.
- `2026-05-19_kimi-k2-6_run-01` - bench suite Kimi przez LiteLLM Proxy.
- `2026-05-19_deepseek-v4-flash_run-01` i
  `2026-05-19_deepseek-v4-flash_run-02` - bench suite DeepSeek przez LiteLLM
  Proxy.
- `2026-05-19_kimi-k2-6_stream-debug` - raw SSE stream dumps użyte później do
  naprawy TTFT/TPOT dla Kimi.

Istotny kontekst commitów z sesji:

- `89b44b8` - odzyskane wyniki benchmarków z 2026-05-11.
- `4b086d9` - poprawka compose: Kimi używa TP zamiast DP.
- `46bf289` - compose smoke results dla Kimi i DeepSeek.
- `e586117` - Kimi stream-debug artefacts.
- `9bdbfbd` - LiteLLM proxy smoke.
- `0f09ea5` - LiteLLM proxy bench suite dla Kimi i DeepSeek.
- `2510f53`, `3293c38`, `8431338`, `b6fd7bc`, `4cd78e9` - bootstrap
  Prometheus/Grafana.

## Decyzje operacyjne

- Canonical compose dla Kimi, DeepSeek, OpenWebUI i LiteLLM Proxy zostaje w
  `serving/compose/docker-compose.kimi-k2.6.yml`.
- Kimi K2.6 jest serwowany jako `kimi-k2.6` przez usługę `vllm` na porcie 8000,
  z TP=8 i Eagle3 speculative decoding.
- DeepSeek-V4-Flash jest serwowany jako `DeepSeek-V4-Flash` przez usługę
  `vllm-small` na porcie 8004, równolegle z Kimi i z ograniczonym użyciem VRAM.
- LiteLLM Proxy jest ścieżką benchmarkową i wspólnym OpenAI-compatible endpointem
  dla obu modeli.
- OpenWebUI działa z obecnym stackiem; nie było potrzeby przepinania go przez
  LiteLLM w tej sesji.
- Prometheus/Grafana są uruchomione jako Docker Compose observability stack, ale
  dashboard wymaga jeszcze walidacji pod żywym obciążeniem.

## Problemy i follow-upy

- Kimi TTFT/TPOT parser: `measure_ttft_once.py` raportował `TTFT: n/a` /
  `TPOT: n/a`, bo nie czytał `delta.reasoning`. Dane źródłowe zostały zapisane w
  `2026-05-19_kimi-k2-6_stream-debug`.
- Benchmark artefacts / `.gitignore`: podczas sesji trzeba było uważać na
  ignorowanie wyników w `results/runs`, co zostało przeniesione do issue #32.
- Observability: kontenery Prometheus i Grafana wystartowały, ale panele nie były
  jeszcze zweryfikowane na żywych metrykach pod load.
- GPU hardware metrics: stack nie miał jeszcze DCGM Exporter ani paneli
  temperatury, mocy, VRAM i SM utilization.
- W1 write-up powinien powstać dopiero po tym, gdy dashboard i story
  observability będą wystarczająco spójne.

## Status po późniejszych poprawkach

Stan na 2026-05-20:

- Issue #31 zostało domknięte w PR #36. Parser Kimi zapisuje teraz
  `ttft_any_token_seconds` / `tpot_any_token_seconds` dla reasoning stream, a
  `ttft_seconds` pozostaje final-answer-only.
- Issue #32 jest zamknięte; polityka benchmark artefacts / `.gitignore` została
  uporządkowana po sesji.
- PR #35 dodał provisioned Grafana Phase 1 dashboard.
- Issue #34 pozostaje właściwym miejscem na TTFT reconciliation, DCGM Exporter /
  GPU hardware metrics i walidację dashboardu pod load.

## Następne kroki

1. Zweryfikować Grafana dashboard na żywych metrykach podczas bench suite dla
   Kimi i DeepSeek.
2. Dodać DCGM Exporter do observability stack, jeśli serwerowa walidacja
   potwierdzi tryb Docker Compose.
3. Zebrać lub zaktualizować inventory realnych nazw metryk vLLM/Prometheus.
4. Przygotować W1 write-up po domknięciu minimalnego observability artefact.
5. Na następnej sesji serwerowej zainstalować `rg` i potwierdzić parity tooling
   laptop/server.
