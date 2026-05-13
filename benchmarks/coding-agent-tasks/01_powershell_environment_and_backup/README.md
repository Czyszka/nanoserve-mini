# Task 01 — PowerShell environment status and results export

See `TASK.md` for the full specification (this is the source of truth for agents).

Layout:

- `starter/` — partially implemented `Export-RunArtifacts.ps1` plus fixtures; copied into the agent's work dir.
- `public/` — public test runner the agent may execute.
- `hidden/` — hidden tests executed by the harness after the agent finishes.

Harness invocation example:

```bash
uv run python -m scripts.run_coding_agent_task \
  --task-id 01_powershell_environment_and_backup \
  --agent claude_code --agent-command "claude -p {prompt_file}" \
  --model <model-id> --base-url http://127.0.0.1:8001 \
  --run-id <run-id>
```
