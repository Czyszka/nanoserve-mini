# Perliczka — DeepSeek V4.1 + MiniMax M3.1 za LiteLLM

| usługa | GPU | port | model (nazwa w LiteLLM) |
|---|---|---|---|
| `litellm-perliczka` | — | 8100 | proxy, `/v1/messages` + `/v1/chat/completions` |
| `vllm-minimax` | 4–7 | 8102 | `minimax-m3.1-flash` |
| `vllm-dsv41` | 0–3 | 8104 | `deepseek-v4.1-flash` |
| `grafana-perliczka` | — | 3101 | dashboardy (vLLM, GPU/DCGM, korelacja) |
| `prometheus-perliczka` | — | 9190 | scrape co 5 s: oba vLLM + DCGM |
| `dcgm-exporter-perliczka` | wszystkie | — | liczniki GPU (tylko w sieci dockera) |

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

## Monitoring

Monitoring ma profil `observability` i **domyślnie się nie uruchamia**:

```bash
docker compose up -d                              # tylko modele + LiteLLM
docker compose --profile observability up -d      # modele + LiteLLM + monitoring
docker compose --profile observability stop prometheus grafana dcgm-exporter   # wyłącz sam monitoring
```

Stałe włączenie: `COMPOSE_PROFILES=observability` w `.env`. Zatrzymanie wszystkiego
razem z monitoringiem: `docker compose --profile observability down` (samo `down`
pominie usługi z profilu).

Konfiguracja w `monitoring/` — kopia sprawdzonego stacku z `serving/compose/`
(te same dashboardy i lista liczników DCGM). Przed pierwszym startem (jednorazowo):

```bash
D=/home/ubuntusrv2/working/perliczka-observability
sudo mkdir -p $D/prometheus-data $D/grafana-data
sudo chown 65534:65534 $D/prometheus-data   # prometheus = nobody
sudo chown 472:472 $D/grafana-data          # grafana
```

Wymagany jest **jeden** dcgm-exporter na maszynie (pola profilingowe GPU trzyma jeden
klient naraz). Jeśli działa stary stack obserwacji z `serving/compose/`, zatrzymaj go:
`docker compose -f ../compose/docker-compose.observability.yml down`.

Grafana: `http://<adres-serwera>:3101` (login z `.env`). Dashboardy:
*vLLM Phase 1* (ruch, latencje, KV, spec decode per model), *GPU hardware (DCGM)*
(per GPU — wyspa 0–3 to DeepSeek, 4–7 MiniMax) i *Serving ↔ GPU hardware*
(korelacja; panele DCGM uśredniają wszystkie 8 GPU). Sprawdzenie celów scrape:
`http://<adres-serwera>:9190/targets` — wszystkie trzy mają być `UP`.

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
- **Obrazy na ruchomych tagach** (`latest`, LiteLLM `main-stable`): `docker compose pull`
  potrafi podnieść wersję bez zmian w repo. Przy problemie przypnij tag wersji, np.
  `vllm/vllm-openai:v0.33.0`. Sprawdź przy pierwszym starcie zgodność obrazu vLLM ze
  sterownikiem (595.58.03, CUDA 13.2):
  `docker run --rm --gpus all --entrypoint python3 vllm/vllm-openai:latest -c "import torch;print(torch.ones(1).cuda())"`.
  Błąd sterownika → wariant `v0.33.0-cu129` albo nowszy driver.
