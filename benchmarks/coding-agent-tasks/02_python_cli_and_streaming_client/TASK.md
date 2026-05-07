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

### Stage 2 — streaming request and robust chunk parsing

The tool should send an OpenAI-compatible `chat.completions` request with `stream=true`.

Streaming parser requirements:

- Parse SSE-style `data:` lines.
- Accept multiple chunks per response.
- Ignore role-only deltas (for example, chunks that set only `role`).
- Detect the first non-empty content delta.
- Handle multiple content deltas and concatenate in order.
- Count chunks that carry parsable payload.

Metrics to compute:

- TTFT (time to first token/content)
- End-to-end latency
- chunk count
- output character count

### Stage 3 — strict JSON reporting

The CLI should always write a strict JSON report to `--output`.

If `--jsonl` is provided, append one compact JSON record per run.

Report should include at least:

- schema identifier,
- timestamp (UTC ISO-8601),
- request controls (`base_url`, `model`, `max_tokens`, `temperature`, `timeout`),
- metrics (`ttft_ms`, `e2e_ms`, `chunk_count`, `output_chars`),
- generated text,
- error field (`null` on success).

JSON strictness requirements:

- valid UTF-8 JSON,
- no `NaN`, `Infinity`, or `-Infinity`,
- stable key naming and predictable types.

### Stage 4 — error handling and failure records

Handle and report at least:

- timeout,
- HTTP error status,
- malformed chunk payload,
- stream ending without any content.

Failure rules:

- still emit valid JSON output,
- keep schema and request-controls fields present,
- set metrics fields to `null` or safe sentinel values consistently,
- include clear error code/message details.

---

## Public tests

Public tests should verify:

- CLI validation and argument shape,
- JSON report schema/field shape,
- deterministic fake stream parsing,
- output path creation for nested directories.

---

## Hidden tests

Hidden tests should verify edge and robustness behavior:

- malformed SSE chunks,
- role-only chunks before first content chunk,
- timeout behavior,
- strict JSON serialization (no `NaN`/`Infinity`),
- output directory containing spaces,
- stream with multiple content deltas and expected concatenation.

---

## Quality review checklist

LLM-as-judge should inspect:

- idiomatic Python implementation,
- no unnecessary external dependencies,
- parsing logic factored into testable units,
- small pure functions where reasonable,
- no hard-coded model names or server URLs,
- explicit, readable error handling paths.
