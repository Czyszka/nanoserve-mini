# Task 02 starter

Specification: see `TASK.md`.

Layout: `starter/` (agent edits), `public/` (visible tests), `hidden/` (harness only).

Harness:

    uv run python -m scripts.run_coding_agent_task \
      --task-id 02_python_cli_and_streaming_client \
      --agent claude_code --agent-command "claude -p {prompt_file}" \
      --model <model-id> --base-url http://127.0.0.1:8001 \
      --run-id <run-id>
