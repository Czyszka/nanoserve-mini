"""Hidden tests — strict JSON serialization and JSONL semantics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from stream_probe import reporting


def _kw():
    return dict(
        base_url="http://h:8000",
        url="http://h:8000/v1/chat/completions",
        model="m",
        prompt="hi",
        max_tokens=64,
        temperature=0.0,
        timeout=30.0,
        ttft_ms=None,
        e2e_ms=12.3,
        chunks_total=0,
        content_chunks=0,
        output_text="",
        completed=False,
        error={"code": "timeout", "message": "x", "type": "TimeoutError"},
    )


def test_strict_json_rejects_nan(tmp_path: Path):
    """Bug 4: write_json must reject NaN / Infinity."""
    rep = reporting.build_report(**_kw())
    rep["metrics"]["ttft_ms"] = float("nan")
    out = tmp_path / "out.json"
    with pytest.raises(ValueError):
        reporting.write_json(str(out), rep)


def test_strict_json_rejects_infinity(tmp_path: Path):
    rep = reporting.build_report(**_kw())
    rep["metrics"]["e2e_ms"] = float("inf")
    out = tmp_path / "out.json"
    # Either raise OR produce a file with no Infinity literal.
    raised = False
    try:
        reporting.write_json(str(out), rep)
    except ValueError:
        raised = True
    if not raised:
        text = out.read_text("utf-8")
        assert "Infinity" not in text


def test_jsonl_append_is_single_compact_line(tmp_path: Path):
    rep = reporting.build_report(**_kw())
    out = tmp_path / "rec.jsonl"
    reporting.write_jsonl_line(str(out), rep)
    text = out.read_text("utf-8")
    # Exactly one newline-terminated record.
    assert text.endswith("\n")
    assert text.count("\n") == 1
    # Compact: no two-space indent.
    assert "  " not in text
    parsed = json.loads(text)
    assert parsed["schema"] == "coding-agent-task.stream-probe.v1"


def test_output_dir_with_spaces(tmp_path: Path):
    rep = reporting.build_report(**_kw())
    nested = tmp_path / "dir with spaces" / "deeper"
    out = nested / "rep.json"
    reporting.write_json(str(out), rep)
    assert out.is_file()
