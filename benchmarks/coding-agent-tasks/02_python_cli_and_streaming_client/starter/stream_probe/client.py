"""HTTP streaming client for OpenAI-compatible chat completions.

Partially implemented — see TASK.md for the full required behavior.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx


def build_url(base_url: str) -> str:
    """Build the chat-completions URL.

    NOTE: This implementation does not strip a trailing slash from ``base_url``,
    so passing ``http://h:8000/`` produces ``http://h:8000//v1/chat/completions``.
    """
    return f"{base_url}/v1/chat/completions"


def build_request_body(
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    """Construct the JSON body for a streaming chat completion."""
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }


def iter_sse_payloads(lines: Iterator[str]) -> Iterator[dict[str, Any] | str]:
    """Iterate SSE lines, yielding parsed JSON payload dicts or the sentinel "[DONE]".

    Blank lines and SSE comment lines (starting with ``:``) are skipped.
    Malformed JSON after ``data:`` raises ``json.JSONDecodeError`` (intentional
    starter bug — should instead surface as a stream protocol error).
    """
    for raw in lines:
        if raw is None:
            continue
        line = raw.strip()
        if not line:
            continue
        if line.startswith(":"):
            continue
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if data == "[DONE]":
            yield "[DONE]"
            return
        # NOTE: deliberate — no try/except around json.loads.
        yield json.loads(data)


def stream_chat_completion(
    client: httpx.Client,
    url: str,
    body: dict[str, Any],
) -> Iterator[dict[str, Any] | str]:
    """POST a streaming chat completion and yield parsed payloads.

    The caller is responsible for constructing the ``httpx.Client`` (so the
    timeout policy is configurable from the CLI).
    """
    with client.stream("POST", url, json=body) as response:
        response.raise_for_status()
        yield from iter_sse_payloads(response.iter_lines())
