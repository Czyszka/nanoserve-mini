"""Public tests for stream_probe.reporting."""

from __future__ import annotations

import json
from pathlib import Path

from stream_probe import reporting


def _sample_kwargs() -> dict:
    return dict(
        base_url="http://h:8000",
        url="http://h:8000/v1/chat/completions",
        model="m",
        prompt="hi",
        max_tokens=64,
        temperature=0.0,
        timeout=30.0,
        ttft_ms=12.3,
        e2e_ms=45.6,
        chunks_total=3,
        content_chunks=2,
        output_text="hi there",
        completed=True,
    )


def test_build_report_shape_and_schema():
    rep = reporting.build_report(**_sample_kwargs())
    assert rep["schema"] == "coding-agent-task.stream-probe.v1"
    assert isinstance(rep["timestamp"], str)
    assert set(rep["request"]) >= {
        "base_url", "url", "model", "prompt",
        "max_tokens", "temperature", "timeout",
    }
    assert set(rep["metrics"]) == {
        "ttft_ms", "e2e_ms", "chunks_total", "content_chunks",
        "output_chars", "completed",
    }
    assert rep["metrics"]["output_chars"] == len("hi there")
    assert rep["error"] is None


def test_write_json_creates_parent_and_round_trips(tmp_path: Path):
    out = tmp_path / "nested" / "deep" / "report.json"
    rep = reporting.build_report(**_sample_kwargs())
    reporting.write_json(str(out), rep)
    assert out.is_file()
    loaded = json.loads(out.read_text("utf-8"))
    assert loaded["schema"] == rep["schema"]


def test_write_jsonl_appends_exactly_one_line(tmp_path: Path):
    out = tmp_path / "appended.jsonl"
    rep = reporting.build_report(**_sample_kwargs())
    reporting.write_jsonl_line(str(out), rep)
    reporting.write_jsonl_line(str(out), rep)
    text = out.read_text("utf-8")
    lines = text.splitlines()
    assert len(lines) == 2
    # Each line must be compact (no embedded newline / pretty indent).
    for line in lines:
        assert "\n" not in line
        json.loads(line)  # valid JSON per line
