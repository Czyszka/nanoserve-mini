# Task 04 starter

Specification: see `TASK.md`.

Layout: `starter/` (agent edits), `public/` (visible tests), `hidden/` (harness only).

Harness:

    uv run python -m scripts.run_coding_agent_task \
      --task-id 04_csharp_allocation_aware_refactor \
      --agent claude_code --agent-command "claude -p {prompt_file}" \
      --model <model-id> --base-url http://127.0.0.1:8001 \
      --run-id <run-id>

Local smoke (requires .NET 8 SDK):

    cd benchmarks/coding-agent-tasks/04_csharp_allocation_aware_refactor
    dotnet build starter/LogQueryParser.sln -c Debug
    WORK_DIR="$(pwd)" bash public/run.sh
