# vLLM Compose - Kimi-K2.6 (single-node DEP)

Stos `docker compose` do uruchomienia vLLM 0.20.0 (CUDA 13) z modelem
`moonshotai/Kimi-K2.6` na serwerze 8x H200 NVL w strategii
**single-node DEP** (Data Parallel + Expert Parallel) zgodnie z
[vLLM recipes](https://recipes.vllm.ai/moonshotai/Kimi-K2.6?strategy=single_node_dep).

## Założenia środowiska

Z `results/raw/server_env_snapshot.json`:

- Ubuntu 24.04, kernel 6.8, x86_64
- 8x NVIDIA H200 NVL 143 GB (driver 595.58.03, CUDA 13.2)
- Docker 28.5.0, Docker Compose v2.39.4
- 3 TiB RAM, 1.8 TB system disk + 11 TB SAS RAID

Wymagany jest zainstalowany **NVIDIA Container Toolkit**
(`/etc/docker/daemon.json` z runtime `nvidia`). Jeśli nie ma:
`sudo apt install nvidia-container-toolkit && sudo systemctl restart docker`.

## Uruchomienie

```bash
cd infra/compose
cp .env.example .env
# edytuj .env i ustaw HF_TOKEN

docker compose -f docker-compose.kimi-k2.6.yml up -d
docker compose -f docker-compose.kimi-k2.6.yml logs -f vllm
```

Pierwszy start pobiera wagi modelu (~setki GB) do nazwanego wolumenu
`nanoserve-hf-cache`. Kolejne starty są szybkie - cache jest trwały.

Status:

```bash
docker compose -f docker-compose.kimi-k2.6.yml ps
docker volume inspect nanoserve-hf-cache
```

## Test z hosta

```bash
# health
curl -fsS http://localhost:8000/health

# lista modeli
curl -s http://localhost:8000/v1/models | jq .

# chat (OpenAI-compatible)
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "kimi-k2.6",
    "messages": [{"role":"user","content":"Powiedz cześć po polsku."}],
    "max_tokens": 64
  }' | jq .
```

## Claude Code CLI

Endpoint vLLM jest **OpenAI-compatible** (`/v1/chat/completions`), nie
Anthropic-native. Claude Code CLI rozmawia w protokole Anthropic
(`/v1/messages`), więc samo ustawienie `ANTHROPIC_BASE_URL` na
`http://<host>:8000` nie wystarczy.

Dwie opcje:

1. **LiteLLM Proxy** (zgodnie z roadmap-em):
   uruchom LiteLLM jako tłumacza Anthropic <-> OpenAI, wystaw na np. 4000,
   skonfiguruj model `kimi-k2.6` -> `openai/kimi-k2.6` z `api_base`
   wskazującym na `http://vllm:8000/v1`, a w Claude Code:

   ```bash
   export ANTHROPIC_BASE_URL=http://<host>:4000
   export ANTHROPIC_AUTH_TOKEN=<klucz_litellm>
   export ANTHROPIC_MODEL=kimi-k2.6
   ```

2. **claude-code-router / anthropic-proxy** - lekki shim Anthropic->OpenAI.

Do samego `curl` z hosta wystarczy port `8000` wystawiony przez ten compose.

## Strategia DEP - co tu się dzieje

`single_node_dep` = jeden węzeł, **8 rank-ów Data Parallel** (po jednej GPU
na rank), **Expert Parallel** rozłożony na wszystkie 8 GPU
(`--enable-expert-parallel`), TP=1. Dla MoE jak Kimi-K2.6 daje to wyższą
przepustowość niż czyste TP=8, kosztem nieco większego narzutu komunikacji
między ekspertami. Recipe Kimi-K2.5/K2.6 używa też:

- `--mm-encoder-tp-mode data` - vision encoder w trybie DP,
- `--tool-call-parser kimi_k2` + `--reasoning-parser kimi_k2` - obowiązkowe
  dla tool-calling i reasoning mode w K2.x,
- `--enable-auto-tool-choice`,
- `--trust-remote-code`.

## Tuning / parametry

W `.env`:

- `MAX_MODEL_LEN` - domyślnie 65536. Zwiększ tylko jeśli widzisz, że
  workload wymaga (większy KV cache).
- `MAX_NUM_BATCHED_TOKENS` - 16384 to bezpieczny start; 32768 dla
  prompt-heavy, 8192 dla niskich latencji.
- `MAX_NUM_SEQS` - 256 dla wysokiego concurrency.
- `GPU_MEMORY_UTILIZATION` - 0.90 -> 0.95 jeśli chcesz maksymalny KV cache.

## Sprzątanie

```bash
docker compose -f docker-compose.kimi-k2.6.yml down
# wagi zostają w wolumenie:
docker volume rm nanoserve-hf-cache   # tylko jeśli chcesz skasować cache
```
