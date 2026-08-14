# claude-code-kit

Pakiet startowy **Claude Code** dla offline'owych klientów Windows w sieci
LAN. Osobny stack względem benchmarku Ollamy (`../ollama_lan_bench/`), ale ten
sam wzorzec: kit składany z gotowych narzędzi na maszynie mającej do nich
dostęp, przenoszony pendrive'em, zero instalacji i zero internetu na kliencie.

Architektura docelowa:

```text
klient Windows (Claude Code) → gateway w LAN (Anthropic-compat /v1/messages, np. LiteLLM) → Ollama
```

## Budowa kitu

Wejściem jest **istniejący katalog z narzędziami offline** (nic nie jest
pobierane): Node.js dla Windows, drzewo npm z zainstalowanym
`@anthropic-ai/claude-code`, Python 3.12 dla Windows, opcjonalnie `uv.exe`
oraz userdir z `.claude`.

```bash
python3 build_kit.py \
    --tools-dir /sciezka/do/narzedzi-offline \
    --base-url http://<adres-gatewaya>:4000 \
    --auth-token <klucz> \
    --model <nazwa-modelu-w-gatewayu>
```

Skrypt sam znajduje w `--tools-dir` kotwice: `node.exe`,
`node_modules/@anthropic-ai/claude-code/cli.js`, `python.exe`, `uv.exe`
(opcjonalnie) i katalog `.claude`. Gdy znajdzie kilka kandydatów albo czegoś
brakuje — przerywa z czytelnym komunikatem; lokalizacje można wskazać ręcznie
flagami `--node-dir`, `--claude-dir`, `--python-dir`, `--userdir`, `--uv-exe`.
Dodatkowe flagi: `--small-fast-model` (default = `--model`), `--smoke-prompt`
(default „Zaplanuj pracę"), `--dist`.

Wynik: `dist/claude_code_kit.zip` — w środku nodejs/, claude/, python/,
userdir/.claude/, `claude.bat` (launcher z wpisaną konfiguracją), `setup.bat`,
`setup_client.py`, `kit_config.json`, `README_KIT.txt` (instrukcja PL dla
osoby przy kliencie).

## Na kliencie

1. Rozpakuj zip w dowolne miejsce (np. `C:\claude_kit`).
2. `setup.bat` — kopiuje `.claude` do `%USERPROFILE%` (istniejąca konfiguracja
   dostaje backup `.claude.backup-<timestamp>`), opcjonalnie `--persist`
   zapisuje zmienne środowiskowe na stałe (setx), na końcu odpala smoke test:
   `claude --model <model> -p "Zaplanuj pracę"` (timeout `--smoke-timeout`,
   default 600 s). Inne flagi: `--skip-userdir`, `--skip-smoke`.
3. Praca: `claude.bat <argumenty>` — ustawia na czas sesji
   `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL`,
   `ANTHROPIC_SMALL_FAST_MODEL`, `DISABLE_AUTOUPDATER=1`,
   `DISABLE_TELEMETRY=1`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`
   i uruchamia `node.exe cli.js` z kitu.

## Uwagi operacyjne

- Gateway musi wystawiać endpoint zgodny z Anthropic Messages API
  (`/v1/messages`) — LiteLLM Proxy to potrafi, tłumacząc na backend Ollamy.
- Na serwerze Ollamy podnieś okno kontekstu (`num_ctx` /
  `OLLAMA_CONTEXT_LENGTH`): system prompt Claude Code to dziesiątki tysięcy
  tokenów — domyślne kilka tysięcy utnie prompt i wyniki będą bezużyteczne.
- Jakość pracy agentowej zależy od tool-callingu modelu; smoke test `-p`
  sprawdza łączność i generację, nie pełną pętlę narzędziową.
- Smoke test i budowa kitu są w pełni przetestowane na atrapach (`uv run
  pytest`); realny przebieg z prawdziwym node/claude wymaga Windowsa
  i działającego gatewaya.

## Dev (laptop/serwer)

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```
