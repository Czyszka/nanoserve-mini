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

## Expected run artifact per model

For each model/agent pair, save a row in:

```text
results/runs/<run_id>/coding_agent_eval/results.jsonl
```

Suggested fields:

```json
{
  "agent": "claude_code|opencode",
  "model": "MiniMaxAI/MiniMax-M2.7",
  "task_id": "02_python_cli_and_streaming_client",
  "start_time": "...",
  "end_time": "...",
  "wall_clock_seconds": 0,
  "pass_public_tests": true,
  "pass_hidden_tests": null,
  "changed_files": 0,
  "test_runs_observed": 0,
  "final_commit": "...",
  "notes": "..."
}
```

System metrics should be stored outside the temporary task repository, under the same `results/runs/<run_id>/` tree.
