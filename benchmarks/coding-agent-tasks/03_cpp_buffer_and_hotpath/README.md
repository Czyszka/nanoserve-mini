# Task 03 starter

Specification: see `TASK.md`.

Layout: `starter/` (agent edits), `public/` (visible tests), `hidden/` (harness only).

Harness:

    uv run python -m scripts.run_coding_agent_task \
      --task-id 03_cpp_buffer_and_hotpath \
      --agent claude_code --agent-command "claude -p {prompt_file}" \
      --model <model-id> --base-url http://127.0.0.1:8001 \
      --run-id <run-id>

Local smoke (requires `cmake` + a C++17 compiler):

    cd benchmarks/coding-agent-tasks/03_cpp_buffer_and_hotpath
    WORK_DIR="$(pwd)" bash public/run.sh
