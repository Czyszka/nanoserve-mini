"""Thin HTTP client for an OpenAI-compatible vLLM server.

This module is intentionally minimal. It exists so that all measurement
scripts in ``scripts/`` (request_once, measure_ttft_once, run_sequential_benchmark)
share one place that knows how to build and fire ``/v1/chat/completions`` requests.

No retry / backoff / metrics in here. Higher-level scripts add what they need.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class CompletionRequest:
    """Inputs for a single ``/v1/chat/completions`` call."""

    base_url: str
    model: str
    prompt: str
    max_tokens: int = 64
    temperature: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def build_payload(req: CompletionRequest, *, stream: bool) -> dict[str, Any]:
    """Build the JSON body for ``/v1/chat/completions``.

    Uses the chat format (``messages=[{role: user, content: prompt}]``) because
    that is what vLLM exposes by default. ``extra`` is merged last so callers can
    override any field if needed (e.g. ``top_p``, ``stop``, ``stream_options``).
    """
    payload: dict[str, Any] = {
        "model": req.model,
        "messages": [{"role": "user", "content": req.prompt}],
        "max_tokens": req.max_tokens,
        "temperature": req.temperature,
        "stream": stream,
    }
    if req.extra:
        payload.update(req.extra)
    return payload


def _endpoint(base_url: str) -> str:
    return base_url.rstrip("/") + "/v1/chat/completions"


def chat_completion(
    req: CompletionRequest,
    *,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Non-streaming call. Returns the full parsed JSON response."""
    payload = build_payload(req, stream=False)
    url = _endpoint(req.base_url)

    owns_client = client is None
    http = client if client is not None else httpx.Client(timeout=timeout)
    try:
        response = http.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    finally:
        if owns_client:
            http.close()


def chat_completion_stream(
    req: CompletionRequest,
    *,
    client: httpx.Client | None = None,
    timeout: float = 120.0,
) -> Iterator[dict[str, Any]]:
    """Streaming call. Yields each parsed SSE chunk in order.

    Iteration stops cleanly when the server sends ``data: [DONE]`` or closes the
    stream. The ``[DONE]`` sentinel itself is **not** yielded — callers detect
    end-of-stream by the iterator finishing.
    """
    payload = build_payload(req, stream=True)
    url = _endpoint(req.base_url)

    owns_client = client is None
    http = client if client is not None else httpx.Client(timeout=timeout)
    try:
        with http.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    return
                yield json.loads(data)
    finally:
        if owns_client:
            http.close()


def extract_assistant_text(response: dict[str, Any]) -> str:
    """Pull the assistant message content out of a non-streaming response.

    Returns an empty string if the structure is unexpected. Kept tolerant on
    purpose — vLLM can omit fields depending on parameters.
    """
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content if isinstance(content, str) else ""


def extract_stream_delta_text(chunk: dict[str, Any]) -> str:
    """Pull the incremental token text out of a streaming chunk.

    Returns an empty string for chunks that don't carry content (e.g. the first
    chunk that only contains the role).
    """
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    return content if isinstance(content, str) else ""
