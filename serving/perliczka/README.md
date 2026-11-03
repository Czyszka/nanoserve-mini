# Perliczka — DeepSeek V4.1 + MiniMax M3.1 za LiteLLM

| usługa | GPU | port | model (nazwa w LiteLLM) |
|---|---|---|---|
| `litellm-perliczka` | — | 8100 | proxy, `/v1/messages` + `/v1/chat/completions` |
| `vllm-minimax` | 4–7 | 8102 | `minimax-m3.1-flash` |
| `vllm-dsv41` | 0–3 | 8104 | `deepseek-v4.1-flash` |
| `grafana-perliczka` | — | 3101 | dashboardy (vLLM, GPU/DCGM, korelacja) |
| `prometheus-perliczka` | — | 9190 | scrape co 5 s: oba vLLM + DCGM |
| `dcgm-exporter-perliczka` | wszystkie | — | liczniki GPU (tylko w sieci dockera) |

Sieć: `perliczka_net`. Modele: `/SASRAID/models/vllm_models`.

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
D=/home/ubuntusrv2/perliczka_proj
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

Najpewniej: skopiuj `claude-code-settings.example.json` do `~/.claude/settings.json`
(Windows: `%USERPROFILE%\.claude\settings.json`; istniejący plik — dopisz sekcję `env`)
i podmień adres serwera oraz token (`LITELLM_MASTER_KEY`). Alternatywa: zmienne z
`claude-code.env.example` przez `setx` + nowe okno terminala. Jeśli przy starcie pojawia
się ekran logowania: w `~/.claude.json` ustaw `"hasCompletedOnboarding": true` (albo
zmień nazwę tego pliku, gdy zawiera stary login OAuth) i uruchom `claude` ponownie. Na razie wszystkie klasy → DeepSeek; docelowo Opus → DeepSeek,
Sonnet/Haiku i domyślny → MiniMax (gdy MiniMax wystartuje).

## Zastrzeżenia (do sprawdzenia przy pierwszym starcie)

- **MiniMax na DP4 + EP, nie TP4.** Przy TP4 model pada (niezgodność podziału tensorów
  192 vs 384), także bez spekulacji. Domyślny układ: `--data-parallel-size 4
  --enable-expert-parallel` (`MINIMAX_PARALLEL_ARGS` w `.env`). OOM → zmniejsz
  `MINIMAX_MAX_MODEL_LEN` / `MINIMAX_MAX_NUM_SEQS` (limit liczony na rank DP).
- **MiniMax bez spekulacji.** DSpark na Hopperze niezweryfikowany (upstream go wyłącza);
  wyłączony do czasu uruchomienia samego modelu.
- **Obrazy na ruchomych tagach** (`latest`, LiteLLM `main-stable`): `docker compose pull`
  potrafi podnieść wersję bez zmian w repo. Przy problemie przypnij tag wersji, np.
  `vllm/vllm-openai:v0.33.0`. Sprawdź przy pierwszym starcie zgodność obrazu vLLM ze
  sterownikiem (595.58.03, CUDA 13.2):
  `docker run --rm --gpus all --entrypoint python3 vllm/vllm-openai:latest -c "import torch;print(torch.ones(1).cuda())"`.
  Błąd sterownika → wariant `v0.33.0-cu129` albo nowszy driver.
