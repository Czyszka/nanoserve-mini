# vLLM Compose - Kimi-K2.6 + small model + LiteLLM Proxy + OpenWebUI

Ten katalog zawiera roboczy `docker compose` dla serwera GPU `ubuntusrv2`
z 8x H200 NVL.

Aktualny plik:

```text
docker-compose.kimi-k2.6.yml
litellm-config.yaml
```

Definiuje cztery uslugi:

| Service | Container | Port hosta | Rola |
|---|---|---:|---|
| `vllm` | `vllm-kimi-k2-6` | `8000` | duzy model `moonshotai/Kimi-K2.6` |
| `vllm-small` | `vllm-small` | `8004` | maly model `deepseek-ai/DeepSeek-V4-Flash` |
| `litellm` | `litellm-proxy` | `4000` | OpenAI-compatible proxy z routingiem po polu `model` |
| `open-webui` | `open-webui` | `3000` | UI podlaczone do `vllm:8000` |

Compose jest dokumentacja aktualnego eksperymentu, nie finalnym runbookiem
produkcyjnym. Po kazdej zmianie launch command z serwera trzeba zsynchronizowac
ten plik i `docs/operations/agent-state.md`.

## Wymagania

- Ubuntu 24.04 na serwerze GPU.
- Docker + Docker Compose.
- NVIDIA Container Toolkit.
- Dostep do modeli na Hugging Face.
- Lokalny katalog cache modeli:

```text
/home/ubuntusrv2/.vllm/models
```

Ten katalog jest montowany do kontenerow jako:

```text
/root/.cache/huggingface
```

Nie commituj tokenow, wag modeli, cache HF ani duzych logow.

## Konfiguracja

Skopiuj przyklad env i ustaw token:

```bash
cd serving/compose
cp .env.example .env
```

Wymagane:

```bash
HF_TOKEN=...
LITELLM_MASTER_KEY=sk-local-dev-replace-me
```

Uzywane przez YAML:

- `HF_TOKEN` - wymagany dla uslugi `vllm`.
- `LITELLM_MASTER_KEY` - wymagany dla uslugi `litellm`; klienci wysylaja `Authorization: Bearer <ta wartosc>`.
- `VLLM_HOST_PORT` - opcjonalny port hosta dla Kimi, domyslnie `8000`.
- `LITELLM_HOST_PORT` - opcjonalny port hosta dla LiteLLM Proxy, domyslnie `4000`.
- `OPEN_WEBUI_HOST_PORT` - opcjonalny port hosta dla OpenWebUI, domyslnie `3000`.
- `OPENWEBUI_OPENAI_API_KEY` - opcjonalny dummy/API key dla OpenWebUI.
- `SERVED_MODEL_NAME` - opcjonalna nazwa serwowana przez `vllm-small`, domyslnie `DeepSeek-V4-Flash`.

## Uruchomienie

Start calego stosu:

```bash
docker compose -f docker-compose.kimi-k2.6.yml up -d
```

Logi:

```bash
docker compose -f docker-compose.kimi-k2.6.yml logs -f vllm
docker compose -f docker-compose.kimi-k2.6.yml logs -f vllm-small
docker compose -f docker-compose.kimi-k2.6.yml logs -f litellm
docker compose -f docker-compose.kimi-k2.6.yml logs -f open-webui
```

Status:

```bash
docker compose -f docker-compose.kimi-k2.6.yml ps
```

Stop:

```bash
docker compose -f docker-compose.kimi-k2.6.yml down
```

## Endpointy

Kimi-K2.6:

```bash
curl -fsS http://localhost:8000/health
curl -s http://localhost:8000/v1/models | jq .
```

DeepSeek-V4-Flash:

```bash
curl -fsS http://localhost:8004/health
curl -s http://localhost:8004/v1/models | jq .
```

LiteLLM Proxy (jeden endpoint dla obu modeli):

```bash
curl -fsS http://localhost:4000/health/liveliness
curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" http://localhost:4000/v1/models | jq .
```

Routing: `model: kimi-k2.6` -> `http://vllm:8000/v1`,
`model: DeepSeek-V4-Flash` -> `http://vllm-small:8004/v1`.
Mapowanie zywe w `litellm-config.yaml`.

OpenWebUI:

```text
http://localhost:3000
```

W obecnym YAML OpenWebUI jest podlaczone bezposrednio do `vllm:8000`,
**nie** przez LiteLLM. Docelowo mozna je przepiac na proxy
(`OPENAI_API_BASE_URLS=http://litellm:4000/v1`), zeby UI widzialo oba
modele i zeby caly ruch szedl przez jeden endpoint. Decyzja po pierwszym
smoke serwera.

## Aktualne parametry modeli

### Kimi-K2.6

`vllm` uruchamia:

- image: `vllm/vllm-openai:v0.20.0-cu130-ubuntu2404`
- model: `moonshotai/Kimi-K2.6`
- served model name: `kimi-k2.6`
- port w kontenerze: `8000`
- `--enable-expert-parallel`
- `--data-parallel-size=8`
- `--gpu-memory-utilization 0.75`
- `--tool-call-parser=kimi_k2`
- `--reasoning-parser=kimi_k2`
- `--enable-auto-tool-choice`
- `--language-model-only`
- Eagle3 speculative head: `lightseekorg/kimi-k2.6-eagle3-mla`

Ten wariant trzeba nadal porownac z faktycznie dzialajaca komenda z serwera,
zwlaszcza jesli poprzedni stabilny run byl czystym TP=8.

### DeepSeek-V4-Flash

`vllm-small` uruchamia:

- image: `vllm/vllm-openai:v0.20.0-cu130-ubuntu2404`
- model: `deepseek-ai/DeepSeek-V4-Flash`
- port w kontenerze: `8004`
- `--tensor-parallel-size 8`
- `--gpu-memory-utilization 0.20`
- `--max-model-len 65536`
- `--max-num-seqs 2`
- `--max-num-batched-tokens 4096`
- `--kv-cache-dtype fp8`
- `--tokenizer-mode deepseek_v4`
- `--tool-call-parser deepseek_v4`
- `--reasoning-parser deepseek_v4`
- MTP speculative config: `{"method":"mtp","num_speculative_tokens":1}`

Intencja: maly model ma uzywac ok. 20% VRAM na 8 GPU, a reszta VRAM ma zostac
dostepna dla duzego modelu.

## Benchmark smoke

Przykladowy run dla malego modelu:

```bash
RUN_ID=2026-05-11_deepseek-v4-flash_small

uv run python -m benchmarks.scripts.request_once \
  --base-url http://127.0.0.1:8004 \
  --model DeepSeek-V4-Flash \
  --run-id "$RUN_ID"

uv run python -m benchmarks.scripts.measure_ttft_once \
  --base-url http://127.0.0.1:8004 \
  --model DeepSeek-V4-Flash \
  --run-id "$RUN_ID"

uv run python -m benchmarks.scripts.run_sequential_benchmark \
  --base-url http://127.0.0.1:8004 \
  --model DeepSeek-V4-Flash \
  --warmup 1 --runs 5 \
  --run-id "$RUN_ID"
```

Przykladowy run dla Kimi:

```bash
RUN_ID=2026-05-11_kimi-k2-6

uv run python -m benchmarks.scripts.request_once \
  --base-url http://127.0.0.1:8000 \
  --model kimi-k2.6 \
  --run-id "$RUN_ID"
```

## Najblizsze TODO

1. Wrzucic z serwera najnowsza wersje compose i wyniki benchmarkow
   DeepSeek-V4-Flash (wtorkowa sesja).
2. Potwierdzic, czy konfiguracja `vllm` dla Kimi w YAML odpowiada realnie
   dzialajacej komendzie.
3. Smoke test LiteLLM Proxy z obu modeli przez `curl /v1/models` i
   `/v1/chat/completions` z `Authorization: Bearer`.
4. **Bench-run launcher** (`benchmarks/scripts/run_bench_suite.py`) -
   jeden skrypt odpalajacy pelna sekwencje
   `collect_metrics_snapshot pre -> request_once -> measure_ttft_once ->
   sample_gpu_metrics (w tle) -> run_sequential_benchmark -> snapshot post`
   per model, ruch przez proxy:4000, metryki snapshot wprost do vLLM.
   Wymaga `--api-key` w `_client.py` i trzech skryptach benchmarkow.
5. **Prometheus + Grafana dashboard** (Phase 1 DoD #4) - blokuje W1 write-up.
6. **W1 write-up** ("vLLM + LiteLLM Proxy on 8xH200: from zero to first
   measurement") - po dashboardzie.
7. Pobrac drugi maly model i wykonac ten sam zestaw benchmarkow.
