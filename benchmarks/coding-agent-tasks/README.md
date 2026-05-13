# Coding agent task suite

Synthetic programming tasks for evaluating local coding-agent workflows against vLLM-served models.

These tasks are intentionally independent from `nanoserve-mini`. The agent works in a temporary task repository, not in this project repository. For each model/agent run, the final task repository state should be committed so results can be compared by commit diff.

## Design goals

- Evaluate practical programming usefulness, not just chat quality.
- Use open task prompts and hidden tests/evaluation.
- Allow the agent to edit files, run commands, run tests, and iterate after failures.
- Make each task multi-stage, with increasing difficulty inside the task.
- Keep tasks small enough to run during a server session, but rich enough to expose real coding weaknesses.

## Agent policy

The agent may:

- read and edit project files,
- run tests and shell commands,
- inspect error output,
- make multiple attempts,
- commit the final solution in the temporary task repository.

The agent should not:

- modify hidden tests,
- use network access unless the task explicitly allows it,
- change public task requirements,
- replace the task with a trivial hard-coded answer.

## Evaluation model

Each task has:

- an open prompt/README visible to the coding agent,
- public starter tests where useful,
- hidden tests for correctness and edge cases,
- optional LLM-as-judge quality review,
- system metrics gathered outside the task repository.

Core scoring dimensions:

| Dimension | Meaning |
|---|---|
| Correctness | Hidden and public tests pass. |
| Minimality | Solution changes only what is necessary. |
| Robustness | Handles edge cases, bad inputs, and errors. |
| Maintainability | Code remains readable and idiomatic. |
| Iteration | Agent can recover from failed tests. |
| Efficiency | Avoids unnecessary allocations, slow paths, or brittle shelling out. |

## Task list

| ID | Language | Difficulty | Focus |
|---|---|---:|---|
| `01_powershell_environment_and_backup` | PowerShell | A | Docker/vLLM status, validation, export/backup. |
| `02_python_cli_and_streaming_client` | Python | B | CLI parser, streaming OpenAI-compatible client, JSON/JSONL reporting. |
| `03_cpp_buffer_and_hotpath` | C++ | B | Buffer/allocator-like bug, correctness, hot path performance. |
| `04_csharp_allocation_aware_refactor` | C# | C | Allocation-aware refactor, public API preservation, performance-sensitive tests. |

## Layout

Each task has the following per-task directory layout:

```text
benchmarks/coding-agent-tasks/<task_id>/
  TASK.md
  README.md
  starter/   # source code the agent edits in its temp work-dir
  public/    # test runner visible to the agent (run.sh or run.ps1)
  hidden/    # test runner the harness runs separately; never copied into the agent's work-dir
```

Rule: the harness copies `starter/` + `public/` into the agent's temp work-dir, then
runs `hidden/run.{sh,ps1}` separately against the agent's solution. The agent
cannot read or modify `hidden/`.

## Harness

Tasks are executed by `scripts/run_coding_agent_task.py`. Canonical invocation:

```bash
uv run python -m scripts.run_coding_agent_task \
  --task-id <id> \
  --agent claude_code \
  --agent-command "claude -p {prompt_file}" \
  --model <model-id> \
  --base-url http://127.0.0.1:8001 \
  --run-id <run-id>
```

Output goes to `results/runs/<run_id>/coding_agent_eval/`:

```text
results/runs/<run_id>/coding_agent_eval/
  results.jsonl                 # one CodingAgentEvalRow per task x agent x model run
  tasks_summary.md
  transcripts/
    <task_id>__prompt.txt
    <task_id>__stdout.log
    <task_id>__stderr.log
    <task_id>__public_tests.log
    <task_id>__hidden_tests.log
  server_metrics/<task_id>/
    pre_server_metrics.json
    pre_nvidia_smi.json
    post_server_metrics.json
    post_nvidia_smi.json
```

## Expected run artifact per model

For each `(task_id, agent, model)` execution, the harness appends one row to
`results/runs/<run_id>/coding_agent_eval/results.jsonl` with schema
`nanoserve-mini.coding-agent-eval-row.v1` (defined as
`SCHEMA_CODING_AGENT_EVAL_ROW` in `scripts/_schemas.py`).

The row is a serialized `CodingAgentEvalRow` (see
`scripts/run_coding_agent_task.py`) with the following fields:

- `schema`, `methodology`, `benchmark_mode`
- `run_id`, `run_uuid`, `task_id`, `agent`, `model`, `base_url`
- `started_at`, `ended_at`, `wall_clock_seconds`, `timed_out`
- `agent_exit_code`, `agent_version`, `error`, `notes`
- `public_tests`, `hidden_tests` — each a `TestRunResult`
  (`ran`, `exit_code`, `log_path`, `duration_s`)
- `changed_files`, `baseline_commit`, `final_commit`
- `tokens` — `TokenUsage` (`input_tokens`, `output_tokens`, `num_turns`)
- `server_metrics` — paths to the pre/post snapshot JSONs
- `transcript_path` — path to the captured agent stdout log
- `extras` — free-form bag for future fields

GPU and vLLM `/metrics` snapshots are stored outside the temp task work-dir,
under `results/runs/<run_id>/coding_agent_eval/server_metrics/<task_id>/`.
