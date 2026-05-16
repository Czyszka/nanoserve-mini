# Task 01: preflight env check

Human-facing guide for the first coding-agent evaluation task.

The canonical prompt shown to the coding agent is `PROMPT.md`. This file explains
how to prepare and run the task.

## Goal

The agent receives a small preflight script for a GPU server environment. It must:

1. Fix 4 seeded bugs in the single-shot checks:
   - Docker availability detection.
   - Numeric disk-free comparison.
   - TCP timeout handling.
   - Exit code propagation from `all_ok`.
2. Add `--watch` mode, which writes one JSONL record per tick.

The output is scored with hidden tests and token/wall-clock metadata from the eval
runner.

## Directory roles

```text
PROMPT.md       Agent-facing task prompt.
init_env.ps1    Creates a Windows/PowerShell work-dir for one model run.
init_env.sh     Creates a Linux/bash work-dir for one model run.
run_eval.py     Runs the agent, hidden tests, and writes results.jsonl.
scaffold/       Buggy starting scripts copied into the temporary work-dir.
public_tests/   Visible tests copied into the temporary work-dir.
hidden_tests/   Harness-only tests; never copied into the agent work-dir.
```

Current status: the PowerShell variant has a real scaffold, public tests, hidden
tests, and `run_eval.py` support. The bash hidden-test runner exists and uses the
same `hidden_tests/cases.json`, but the bash scaffold and public-test runner are
still placeholders.

## Windows quickstart

From this task directory:

```powershell
.\init_env.ps1 -Model claude-haiku-4-5 -RunNumber 01
```

The script creates a clean work-dir under `.\runs\...`, copies `PROMPT.md`,
`preflight.ps1`, and public tests, initializes Git, and prints the next eval
command.

To run the visible tests manually in the generated work-dir:

```powershell
.\public_tests\run.ps1
```

To smoke-test the harness without invoking an agent:

```powershell
uv run python .\run_eval.py `
  --work-dir .\runs\<generated-work-dir> `
  --model claude-haiku-4-5 `
  --skip-agent
```

To run the normal agent eval:

```powershell
uv run python .\run_eval.py `
  --work-dir .\runs\<generated-work-dir> `
  --model claude-haiku-4-5
```

## Linux quickstart

From this task directory:

```bash
./init_env.sh --model claude-haiku-4-5 --run-number 01
```

The script creates a clean work-dir under `./runs/...`, copies `PROMPT.md`,
`preflight.sh`, and public tests, initializes Git, and prints the next eval
command.

To run the visible tests manually in the generated work-dir:

```bash
./public_tests/run.sh
```

Hidden scoring can be invoked by `run_eval.py --shell bash`, but the bash task
variant still needs a real scaffold and public-test runner before it is useful for
model comparison.

## Outputs

`run_eval.py` appends one JSON line to:

```text
<work-dir>/results.jsonl
```

Each row includes:

- model and run id,
- shell variant,
- start/end time and wall-clock duration,
- agent exit code and timeout flag,
- baseline/final Git commit,
- token counts parsed from the agent JSON output,
- stage 1, stage 2, and total hidden-test pass rates.

When the agent produced output, transcripts are also saved as:

```text
<work-dir>/agent_stdout.log
<work-dir>/agent_stderr.log
```

The generated work-dir is intentionally separate from `nanoserve-mini`; the agent
edits only the task copy.
