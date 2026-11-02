# Perliczka — DeepSeek V4.1 + MiniMax M3.1 za LiteLLM

| usługa | GPU | port | model (nazwa w LiteLLM) |
|---|---|---|---|
| `litellm-perliczka` | — | 8100 | proxy, `/v1/messages` + `/v1/chat/completions` |
| `vllm-minimax` | 4–7 | 8102 | `minimax-m3.1-flash` |
| `vllm-dsv41` | 0–3 | 8104 | `deepseek-v4.1-flash` |

Sieć: `perliczka_net`. Modele: `/sasraid/models/vllm_models`.

## Start (serwer)

```bash
cd serving/perliczka
cp .env.example .env          # uzupełnij HF_TOKEN i LITELLM_MASTER_KEY
mkdir -p /home/ubuntusrv2/.vllm/kv_cache
docker compose up -d
docker compose ps             # oba vLLM: start do ~60 min (healthcheck start_period)
```

Stack Kimi (`serving/compose/docker-compose.kimi-k2.6.yml`) zajmuje wszystkie 8 GPU —
przed startem perliczki: `docker compose -f ../compose/docker-compose.kimi-k2.6.yml down`.

Test przez proxy:

```bash
curl http://localhost:8100/v1/chat/completions -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"minimax-m3.1-flash","messages":[{"role":"user","content":"2+2?"}],"max_tokens":32}'
```

## Claude Code (klient)

Zmienne w `claude-code.env.example` — ustaw na stałe (`setx` na Windows), otwórz nowy
terminal, uruchom `claude`. Opus → DeepSeek, Sonnet/Haiku i domyślny → MiniMax.

## Zastrzeżenia (do sprawdzenia przy pierwszym starcie)

- **MiniMax TP4 niezweryfikowane.** Recepta Hopper zakłada TP8; checkpoint ~250 GB
  (górna granica w recepcie 533 GB) — na 4×141 GB powinien wejść, ale nikt tego nie
  potwierdził. OOM → zmniejsz `MINIMAX_MAX_MODEL_LEN` / `MINIMAX_MAX_NUM_SEQS`.
- **DSpark na Hopperze niezweryfikowany.** Upstream wyłącza go dla H100/H200; użyta
  konfiguracja 3-tokenowa pochodzi z benchmarku H200 (InferenceX #4423). Błąd startu
  draftera → usuń linię `--speculative-config` w usłudze `vllm-minimax`.
- **Obraz MiniMax to build cu134**, a sterownik serwera (595.58.03) wspiera CUDA 13.2.
  Sprawdź przed startem:
  `docker run --rm --gpus all --entrypoint python3 vllm/vllm-openai:minimax-m31-flash-x86_64-cu134 -c "import torch;print(torch.ones(1).cuda())"`.
  Błąd sterownika = potrzebny nowszy driver albo obraz cu130/cu129, gdy się pojawi.
