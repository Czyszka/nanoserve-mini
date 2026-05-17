# Task 01 — preflight env check

A coding-agent evaluation task. The agent gets a buggy preflight script
that checks a GPU server's environment (docker, GPUs, free disk, TCP
ports, tool versions), and must:

1. **Stage 1** — fix 4 seeded bugs in the single-shot mode (docker
   availability detection, numeric disk comparison, TCP timeout
   handling, exit-code propagation).
2. **Stage 2** — add a `--watch` mode that writes one JSON line per
   tick to a `--output` file.

The harness scores the agent against hidden tests and records token
usage, wall-clock, and transport status. Use it to compare coding
agents head-to-head on a small, well-defined repair-and-extend task.

The agent-facing prompt lives in `PROMPT.md`. Visible tests for the
agent are in `public_tests/`; hidden scoring tests stay in
`hidden_tests/` and never reach the agent's work-dir.

## Quickstart

### Windows (PowerShell)

```powershell
# 1. Prepare a fresh per-run work-dir
.\init_env.ps1 -Model claude-haiku-4-5 -RunNumber 01

# 2. Run the agent and score it
uv run python .\run_eval.py `
  --work-dir .\runs\<generated-work-dir> `
  --model claude-haiku-4-5
```

### Linux (bash)

```bash
./init_env.sh --model claude-haiku-4-5 --run-number 01

uv run python ./run_eval.py \
  --work-dir ./runs/<generated-work-dir> \
  --model claude-haiku-4-5
```

The work-dir path is printed by `init_env.*` at the end.

### Series of N runs with aggregate

To compare models you usually want several runs:

```bash
uv run python ./run_series.py --model claude-haiku-4-5 --runs 3
```

Each run gets its own work-dir under `./runs/`; the aggregate summary
is written to `./runs/_series/series_<UTC-ts>_<model>_runs<N>.json`
(override with `--summary-dir`).

## Results

`run_eval.py` appends one JSON line to `<work-dir>/results.jsonl`
(schema `preflight-env-check-eval.v2`). Each row carries:

- model, run id, shell variant,
- start/end time and wall-clock duration,
- agent exit code, transport status (`ok` / `transport_crash` /
  `timeout`), crash signature if any, `agent_did_work` flag,
- token counts (with `source` field indicating whether they came from
  the final `result` event or a recovered `last_usage_event`),
- baseline/final Git commit,
- pass rates split by `stage1`, `stage2`, and `total`.

When the agent produced output, transcripts are saved to
`<work-dir>/agent_stdout.log` and `<work-dir>/agent_stderr.log`.

## Layout

```
PROMPT.md         Agent-facing task prompt.
init_env.ps1      Creates a per-run work-dir on Windows.
init_env.sh       Creates a per-run work-dir on Linux.
run_eval.py       Runs the agent + hidden tests, writes results.jsonl.
run_series.py     Runs N evaluations and writes an aggregate summary.
scaffold/         Buggy starting scripts (powershell/ + bash/).
public_tests/     Visible tests + runner copied into the work-dir.
hidden_tests/     Harness-only tests; never copied into the work-dir.
runs/             Per-run work-dirs (gitignored).
```

## Troubleshooting

- **`agent_exit_code != 0` but tests pass.** This is usually the Bun
  runtime (Claude Code's JavaScript runtime) crashing at exit, *after*
  the agent finished its work. `run_eval.py` classifies this as
  `transport_status=transport_crash`, `crash_signature=bun_panic`, and
  recovers tokens from the stream-json events. Treat the row as valid.
- **Hidden tests fail with `stdout not valid JSON`.** Make sure the
  agent did not accidentally write text to stdout from outside the
  JSON payload (e.g. via `Write-Host` in PowerShell or `echo` in bash).
- **Watch mode timing out.** Hidden Stage 2 uses `--interval-s 1
  --duration-s 3`, which assumes each preflight call returns under
  ~1s. On slow hardware (consumer GPU laptops) this can fail to
  produce 3 ticks; the production target is a Linux server with fast
  `nvidia-smi`.
