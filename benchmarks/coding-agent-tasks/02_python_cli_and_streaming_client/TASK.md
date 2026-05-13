# Task 02 — Python CLI and streaming client

Difficulty: B

Goal: implement and harden a small Python CLI (`stream-probe`) that exercises an OpenAI-compatible streaming chat-completions endpoint and writes strict benchmark-style JSON outputs.

This task is intentionally synthetic. It should be solved in a temporary task repository, not in `nanoserve-mini`.

---

## Agent prompt

You are given a partially implemented Python package called `stream_probe`.

Your job is to make the CLI and streaming client production-usable for local model serving checks.

The tool should:

1. Parse and validate CLI arguments.
2. Send a streaming OpenAI-compatible chat completion request.
3. Parse SSE-style stream chunks robustly.
4. Measure latency and output metrics.
5. Write strict JSON report output and optional JSONL append output.
6. Return clear, machine-usable error records on failure.

You may edit package files and tests. You may run commands and tests.

---

## Starter repository layout

```text
02_python_cli_and_streaming_client/
  README.md
  pyproject.toml
  stream_probe/
    __init__.py
    cli.py
    client.py
    reporting.py
  tests/
    public/
      test_cli_public.py
      test_reporting_public.py
    hidden/
      test_streaming_hidden.py      # not visible to agent during run
      test_error_handling_hidden.py # not visible to agent during run
```

---

## Required behavior

### Stage 1 — CLI argument parsing and validation

CLI should support:

- `--base-url`
- `--model`
- `--prompt`
- `--max-tokens`
- `--temperature`
- `--timeout`
- `--output`
- `--jsonl`

Validation requirements:

- `--base-url`, `--model`, `--prompt`, `--output` are required.
- `--max-tokens` must be a positive integer.
- `--temperature` must be finite and within accepted range (for example `0 <= t <= 2`).
- `--timeout` must be a positive finite number.
- Parent directories for `--output` and optional `--jsonl` must be created if missing.
- Validation failures must produce clear non-zero-exit errors.

### Stage 2 — HTTP request contract and robust streaming parsing

The tool must send this OpenAI-compatible request:

```text
POST <base-url>/v1/chat/completions
Content-Type: application/json
```

Request body:

```json
{
  "model": "<model>",
  "messages": [
    {
      "role": "user",
      "content": "<prompt>"
    }
  ],
  "max_tokens": 64,
  "temperature": 0.0,
  "stream": true
}
```

Request rules:

- `base_url` may include or omit a trailing slash.
- URL construction must be normalized so malformed URLs are not produced, including:
  - `http://host:8000v1/chat/completions`
  - `http://host:8000/v1/v1/chat/completions`
- `--base-url` points to API base (for example `http://127.0.0.1:8000` or `http://127.0.0.1:8000/`).
- Do not hard-code endpoint host/port, model name, or prompt.

SSE parsing rules:

- Ignore blank lines.
- Ignore SSE comment lines starting with `:`.
- Parse only lines beginning with `data:`.
- Stop cleanly on:

```text
data: [DONE]
```

- A parsable JSON payload chunk is any valid JSON object after `data:`.
- A content chunk is a parsable payload where `choices[0].delta.content` is a non-empty string.
- Role-only chunks (for example `{"choices":[{"delta":{"role":"assistant"}}]}`) must not count as first token/content.
- Empty content strings must not count as first token/content.
- Multiple content deltas must be concatenated in order.
- Malformed JSON after `data:` is a stream protocol error.
- Stream ending without any non-empty content is a failure record, not success.

### Stage 3 — latency and output metric semantics

Metrics definitions:

```text
ttft_ms = time from immediately before sending the HTTP request to the first non-empty delta.content
e2e_ms = time from immediately before sending the HTTP request to stream completion or failure
chunks_total = number of parsable JSON payload chunks, excluding [DONE]
content_chunks = number of chunks with non-empty delta.content
output_chars = length of concatenated output_text
completed = true only when [DONE] is received after at least one non-empty content chunk
```

Metric rules:

- Role-only chunks count toward `chunks_total` if parsable, but not `content_chunks`.
- `[DONE]` counts toward neither `chunks_total` nor `content_chunks`.
- If no content is received, `ttft_ms` must be `null`.
- If stream fails after partial content, preserve partial `output_text` when possible and set `completed=false`.

### Stage 4 — strict JSON reporting and error contract

The CLI must always write a strict JSON report to `--output`.

Success example:

```json
{
  "schema": "coding-agent-task.stream-probe.v1",
  "timestamp": "2026-05-08T10:15:30Z",
  "request": {
    "base_url": "http://127.0.0.1:8000",
    "url": "http://127.0.0.1:8000/v1/chat/completions",
    "model": "MiniMaxAI/MiniMax-M2.7",
    "prompt": "Say hi",
    "max_tokens": 64,
    "temperature": 0.0,
    "timeout": 30.0
  },
  "metrics": {
    "ttft_ms": 123.4,
    "e2e_ms": 456.7,
    "chunks_total": 3,
    "content_chunks": 2,
    "output_chars": 8,
    "completed": true
  },
  "output_text": "hi there",
  "error": null
}
```

JSON rules:

- JSON must be valid UTF-8.
- Serialization must be strict (`NaN`, `Infinity`, and `-Infinity` are forbidden).
- Use `null` for unavailable numeric metrics.
- Do not use string placeholders such as `"n/a"` for numeric fields.
- Keep key names and value types stable.

Error object schema:

- Success: `"error": null`
- Failure: `"error"` is an object with:
  - `code` (machine-usable short code),
  - `message` (human-readable detail),
  - `type` (exception/condition class name).

Recommended error codes:

```text
invalid_args
http_error
timeout
transport_error
stream_protocol_error
no_content
report_write_error
unexpected_error
```

Failure example:

```json
{
  "schema": "coding-agent-task.stream-probe.v1",
  "timestamp": "2026-05-08T10:15:30Z",
  "request": {
    "base_url": "http://127.0.0.1:8000",
    "url": "http://127.0.0.1:8000/v1/chat/completions",
    "model": "MiniMaxAI/MiniMax-M2.7",
    "prompt": "Say hi",
    "max_tokens": 64,
    "temperature": 0.0,
    "timeout": 30.0
  },
  "metrics": {
    "ttft_ms": null,
    "e2e_ms": 2000.1,
    "chunks_total": 0,
    "content_chunks": 0,
    "output_chars": 0,
    "completed": false
  },
  "output_text": "",
  "error": {
    "code": "timeout",
    "message": "request timed out after 30.0 seconds",
    "type": "TimeoutError"
  }
}
```

### Stage 5 — exit code contract

Exit codes:

```text
0 = success; content received, stream completed, report written
1 = invalid CLI arguments
2 = HTTP, transport, or timeout failure; report written if output path is valid
3 = stream protocol/parsing failure; report written if output path is valid
4 = output/report writing failure
5 = unexpected runtime error
```

Clarifications:

- Invalid arguments may fail before report writing if `--output` cannot be trusted.
- HTTP/transport/timeout failures should still emit a valid report when output path is valid.
- Stream protocol failures should still emit a valid report when output path is valid.
- Report writing failure is fatal and must exit with code `4`.

### Stage 6 — JSONL append behavior

If `--jsonl` is provided:

- Append exactly one compact single-line JSON record per run.
- Use the same schema and fields as the main JSON report.
- Create parent directories for `--jsonl` if missing.
- Do not pretty-print JSONL.
- If JSONL writing fails, exit with code `4`.
- If both `--output` and `--jsonl` are provided, both must be written.
- If request/stream fails but output paths are valid, write failure record(s).

### Stage 7 — dependency and testability expectations

Dependency expectations:

- Standard library is allowed.
- `httpx` may be used if already included in starter project.
- OpenAI Python SDK must not be required.
- Unit tests must not require a live vLLM server.
- Public and hidden tests should be able to mock the HTTP layer.

Testability expectations (without over-constraining names/architecture):

- CLI parsing and validation.
- URL construction.
- SSE parsing.
- Report building.
- JSON/JSONL writing.

---

## Public tests

Public tests should verify:

- CLI validation and argument shape.
- Base URL normalization with and without trailing slash.
- Request body contains `model`, `messages`, `max_tokens`, `temperature`, and `stream: true`.
- Deterministic fake stream parsing with:
  - role-only chunk,
  - two content chunks,
  - `[DONE]`.
- JSON report schema/field shape.
- `chunks_total` and `content_chunks` are distinct and correct.
- Output path creation for nested directories.
- JSONL append writes exactly one compact line when requested.

---

## Hidden tests

Hidden tests should verify edge and robustness behavior:

- malformed SSE JSON produces `stream_protocol_error` and exit code `3`.
- role-only chunks before first content do not affect TTFT.
- empty content chunks do not count as content.
- stream ending with `[DONE]` but no content produces `no_content`.
- HTTP 500 produces valid failure report and exit code `2`.
- timeout produces valid failure report and exit code `2`.
- output directory containing spaces.
- base URL with trailing slash and without trailing slash.
- strict JSON serialization: no `NaN` or `Infinity`.
- JSONL append creates one compact single-line record.
- output write failure produces exit code `4`.

---

## Quality review checklist

LLM-as-judge should inspect:

- clear TTFT/E2E semantics,
- robust SSE parser,
- correct handling of `[DONE]`,
- normalized URL construction,
- strict JSON report schema,
- structured error objects (not free-form strings),
- no hard-coded server/model values,
- testable client/parser/reporting design,
- no unnecessary dependency on OpenAI SDK,
- readable failure paths.

---

## Harness invocation

> Layout note: the actual scaffold lives at the task-dir level (`<task>/public/` and `<task>/hidden/`), not under `<task>/starter/tests/public/` and `<task>/starter/tests/hidden/`. The harness runs them outside the agent's work-dir.

This task is run by `scripts/run_coding_agent_task.py`. Example:

    uv run python -m scripts.run_coding_agent_task \
      --task-id 02_python_cli_and_streaming_client \
      --agent claude_code \
      --agent-command "claude -p {prompt_file}" \
      --model <model-id> \
      --base-url http://127.0.0.1:8001 \
      --run-id 2026-05-13_smoke

Layout:

- `starter/` — code the agent edits in the temp work-dir.
- `public/run.{sh|ps1}` — tests visible to the agent.
- `hidden/run.{sh|ps1}` — tests run by the harness only; not copied into the agent's work-dir.

Each invocation appends one row to `results/runs/<run_id>/coding_agent_eval/results.jsonl`
(schema `nanoserve-mini.coding-agent-eval-row.v1`).
