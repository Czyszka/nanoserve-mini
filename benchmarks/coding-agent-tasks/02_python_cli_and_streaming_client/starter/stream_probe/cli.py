"""CLI entry point for stream-probe."""

from __future__ import annotations

import argparse
import math
import sys
import time
from typing import Any

import httpx

from . import client as client_mod
from . import reporting

EXIT_OK = 0
EXIT_INVALID_ARGS = 1
EXIT_HTTP_FAIL = 2
EXIT_STREAM_FAIL = 3
EXIT_WRITE_FAIL = 4
EXIT_UNEXPECTED = 5


def _positive_int(value: str) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            f"expected positive integer, got {value!r}"
        ) from exc
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(
            f"expected positive integer, got {ivalue}"
        )
    return ivalue


def _temperature(value: str) -> float:
    try:
        fvalue = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            f"expected float in [0, 2], got {value!r}"
        ) from exc
    if not math.isfinite(fvalue) or fvalue < 0.0 or fvalue > 2.0:
        raise argparse.ArgumentTypeError(
            f"temperature must be finite in [0, 2], got {fvalue}"
        )
    return fvalue


def _positive_float(value: str) -> float:
    try:
        fvalue = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            f"expected positive float, got {value!r}"
        ) from exc
    if not math.isfinite(fvalue) or fvalue <= 0.0:
        raise argparse.ArgumentTypeError(
            f"timeout must be a positive finite number, got {fvalue}"
        )
    return fvalue


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stream-probe",
        description=(
            "Probe an OpenAI-compatible streaming chat-completions endpoint "
            "and emit a strict JSON metrics report."
        ),
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-tokens", type=_positive_int, default=64)
    parser.add_argument("--temperature", type=_temperature, default=0.0)
    parser.add_argument("--timeout", type=_positive_float, default=30.0)
    parser.add_argument("--jsonl", default=None)
    return parser


def _consume_stream(
    payloads: Any,
    started_at: float,
) -> tuple[int, int, float | None, str, bool]:
    """Iterate parsed SSE payloads and accumulate metrics.

    NOTE: Deliberate starter bug — role-only chunks are counted as
    content_chunks (and trigger TTFT). See TASK.md.
    """
    chunks_total = 0
    content_chunks = 0
    ttft_ms: float | None = None
    output_parts: list[str] = []
    completed = False

    for item in payloads:
        if item == "[DONE]":
            completed = True
            break
        chunks_total += 1
        # BUG: treats any delta (including role-only) as a content chunk.
        try:
            delta = item["choices"][0].get("delta", {}) or {}
        except (KeyError, IndexError, TypeError):
            continue
        # role-only chunk passes through here as "content".
        content = delta.get("content")
        if ttft_ms is None:
            ttft_ms = (time.perf_counter() - started_at) * 1000.0
        content_chunks += 1
        if isinstance(content, str) and content:
            output_parts.append(content)
    return chunks_total, content_chunks, ttft_ms, "".join(output_parts), completed


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse uses 2 for usage errors; normalize to our invalid-args code.
        code = exc.code if isinstance(exc.code, int) else EXIT_INVALID_ARGS
        return EXIT_INVALID_ARGS if code != 0 else 0

    url = client_mod.build_url(args.base_url)
    body = client_mod.build_request_body(
        model=args.model,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )

    error: dict[str, str] | None = None
    exit_code = EXIT_OK
    chunks_total = 0
    content_chunks = 0
    ttft_ms: float | None = None
    output_text = ""
    completed = False

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=args.timeout) as http_client:
            payloads = client_mod.stream_chat_completion(http_client, url, body)
            chunks_total, content_chunks, ttft_ms, output_text, completed = (
                _consume_stream(payloads, started)
            )
        if completed and not output_text:
            error = {
                "code": "no_content",
                "message": "stream completed without any content chunks",
                "type": "RuntimeError",
            }
            exit_code = EXIT_HTTP_FAIL
        elif not completed:
            error = {
                "code": "no_content",
                "message": "stream ended without [DONE] sentinel",
                "type": "RuntimeError",
            }
            exit_code = EXIT_HTTP_FAIL
    except httpx.TimeoutException as exc:
        error = {
            "code": "timeout",
            "message": f"request timed out after {args.timeout} seconds",
            "type": type(exc).__name__,
        }
        exit_code = EXIT_HTTP_FAIL
    except httpx.HTTPStatusError as exc:
        error = {
            "code": "http_error",
            "message": str(exc),
            "type": type(exc).__name__,
        }
        exit_code = EXIT_HTTP_FAIL
    except httpx.TransportError as exc:
        error = {
            "code": "transport_error",
            "message": str(exc),
            "type": type(exc).__name__,
        }
        exit_code = EXIT_HTTP_FAIL
    # NOTE: json.JSONDecodeError is intentionally NOT caught here.

    e2e_ms = (time.perf_counter() - started) * 1000.0

    report = reporting.build_report(
        base_url=args.base_url,
        url=url,
        model=args.model,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        timeout=args.timeout,
        ttft_ms=ttft_ms,
        e2e_ms=e2e_ms,
        chunks_total=chunks_total,
        content_chunks=content_chunks,
        output_text=output_text,
        completed=completed and not error,
        error=error,
    )

    try:
        reporting.write_json(args.output, report)
        if args.jsonl:
            reporting.write_jsonl_line(args.jsonl, report)
    except OSError as exc:
        sys.stderr.write(f"report-write failure: {exc}\n")
        return EXIT_WRITE_FAIL

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
