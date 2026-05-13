"""Report building and JSON/JSONL writing."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

SCHEMA = "coding-agent-task.stream-probe.v1"


def utcnow_iso() -> str:
    """Return current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_report(
    *,
    base_url: str,
    url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    timeout: float,
    ttft_ms: float | None,
    e2e_ms: float | None,
    chunks_total: int,
    content_chunks: int,
    output_text: str,
    completed: bool,
    error: dict[str, str] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Assemble the result dict per ``coding-agent-task.stream-probe.v1``."""
    return {
        "schema": SCHEMA,
        "timestamp": timestamp or utcnow_iso(),
        "request": {
            "base_url": base_url,
            "url": url,
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout": timeout,
        },
        "metrics": {
            "ttft_ms": ttft_ms,
            "e2e_ms": e2e_ms,
            "chunks_total": chunks_total,
            "content_chunks": content_chunks,
            "output_chars": len(output_text),
            "completed": completed,
        },
        "output_text": output_text,
        "error": error,
    }


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def write_json(path: str, payload: dict[str, Any]) -> None:
    """Write ``payload`` to ``path`` as pretty UTF-8 JSON.

    NOTE: ``json.dumps`` is called without ``allow_nan=False`` (intentional
    starter bug — strict JSON requires NaN/Infinity to be rejected).
    """
    _ensure_parent(path)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def write_jsonl_line(path: str, payload: dict[str, Any]) -> None:
    """Append one compact single-line JSON record to ``path``."""
    _ensure_parent(path)
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
