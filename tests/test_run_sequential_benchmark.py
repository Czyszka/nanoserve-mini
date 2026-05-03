"""Tests for ``scripts.run_sequential_benchmark``.

The end-to-end CLI test uses an httpx.MockTransport that returns a deterministic
SSE stream for every request, so the JSONL + summary write paths are covered
without a real vLLM.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import httpx
import pytest

from scripts import _client, run_sequential_benchmark
from scripts._client import CompletionRequest
from scripts._metrics import RunControls
from scripts.run_sequential_benchmark import (
    RunRow,
    build_summary,
    run_sequential,
    write_jsonl,
)


def _ok_row(index: int, phase: str = "measured", e2e: float = 0.5) -> RunRow:
    return RunRow(
        index=index,
        phase=phase,
        timestamp="2026-05-03T00:00:00+00:00",
        ttft_seconds=0.1 * (index + 1),
        e2e_seconds=e2e,
        chunks_received=3,
        output_chars=8,
        error=None,
    )


def test_build_summary_counts_only_measured_runs() -> None:
    rows = [
        _ok_row(0, phase="warmup", e2e=10.0),  # warmup ignored
        _ok_row(0, phase="measured", e2e=0.4),
        _ok_row(1, phase="measured", e2e=0.5),
        _ok_row(2, phase="measured", e2e=0.6),
    ]
    request = CompletionRequest(base_url="http://x", model="m", prompt="p", max_tokens=8)
    controls = RunControls(model="m", base_url="http://x", warmup_runs=1, measured_runs=3)

    summary = build_summary(request=request, controls=controls, rows=rows)

    assert summary["schema"] == "nanoserve-mini.sequential-bench.v1"
    assert summary["summary"]["measured_runs"] == 3
    assert summary["summary"]["errors"] == 0
    assert summary["summary"]["e2e_seconds"]["count"] == 3
    assert summary["summary"]["e2e_seconds"]["min"] == 0.4
    assert summary["summary"]["e2e_seconds"]["max"] == 0.6


def test_build_summary_handles_errors_and_missing_ttft() -> None:
    rows = [
        _ok_row(0, phase="measured"),
        RunRow(
            index=1, phase="measured", timestamp="t",
            ttft_seconds=None, e2e_seconds=float("nan"),
            chunks_received=0, output_chars=0,
            error="ConnectError: boom",
        ),
        # measured row with no TTFT (no content chunks) but successful E2E
        RunRow(
            index=2, phase="measured", timestamp="t",
            ttft_seconds=None, e2e_seconds=0.3,
            chunks_received=1, output_chars=0,
            error=None,
        ),
    ]
    request = CompletionRequest(base_url="http://x", model="m", prompt="p", max_tokens=8)
    controls = RunControls(model="m", base_url="http://x", measured_runs=3)

    summary = build_summary(request=request, controls=controls, rows=rows)
    s = summary["summary"]
    assert s["errors"] == 1
    assert s["measured_runs"] == 2  # only error-free measured rows
    assert s["ttft_seconds"]["count"] == 1  # only the one with non-None ttft


def test_write_jsonl_one_line_per_row(tmp_path: Path) -> None:
    rows = [_ok_row(0), _ok_row(1)]
    path = tmp_path / "out.jsonl"
    write_jsonl(path, rows)

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["index"] == 0
    assert parsed[1]["index"] == 1
    assert all(p["phase"] == "measured" for p in parsed)


def test_run_sequential_continues_after_per_run_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_execute_run(_request, *, timeout, clock=None):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated transient")
        from scripts.measure_ttft_once import StreamRunResult
        return StreamRunResult(
            ttft_seconds=0.05,
            e2e_seconds=0.2,
            chunks_received=2,
            output_text="ok",
            completed=True,
        )

    monkeypatch.setattr(run_sequential_benchmark, "execute_run", fake_execute_run)

    request = CompletionRequest(base_url="http://x", model="m", prompt="p", max_tokens=8)
    rows = run_sequential(request, warmup=0, runs=3, timeout=10.0)

    assert len(rows) == 3
    assert rows[0].error is None
    assert rows[1].error is not None
    assert rows[1].error.startswith("RuntimeError")
    assert rows[2].error is None


def test_main_writes_jsonl_and_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sse = (
        b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["stream"] is True
        return httpx.Response(
            200,
            content=sse,
            headers={"content-type": "text/event-stream"},
        )

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs.pop("timeout", None)
        return real_client_cls(transport=transport)

    monkeypatch.setattr(_client.httpx, "Client", fake_client)

    jsonl = tmp_path / "bench.jsonl"
    summary_path = tmp_path / "bench_summary.json"

    rc = run_sequential_benchmark.main([
        "--model", "m",
        "--prompt", "hi",
        "--warmup", "1",
        "--runs", "3",
        "--max-tokens", "4",
        "--gpu-model", "H200 NVL",
        "--vllm-version", "0.6.0",
        "--output-jsonl", str(jsonl),
        "--output-summary", str(summary_path),
    ])
    assert rc == 0

    lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4  # 1 warmup + 3 measured
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["phase"] == "warmup"
    assert sum(1 for p in parsed if p["phase"] == "measured") == 3

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["schema"] == "nanoserve-mini.sequential-bench.v1"
    assert summary["controls"]["gpu_model"] == "H200 NVL"
    assert summary["controls"]["measured_runs"] == 3
    assert summary["summary"]["measured_runs"] == 3
    assert summary["summary"]["errors"] == 0
    assert summary["summary"]["ttft_seconds"]["count"] == 3
    assert summary["summary"]["e2e_seconds"]["count"] == 3

    out = capsys.readouterr().out
    assert "[W0]" in out
    assert "[M0]" in out
    assert "TTFT  p50=" in out


def test_main_rejects_zero_runs(capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_sequential_benchmark.main([
        "--model", "m",
        "--runs", "0",
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "--runs must be >= 1" in err


def test_summary_with_zero_measured_is_safe() -> None:
    rows = [_ok_row(0, phase="warmup")]
    request = CompletionRequest(base_url="http://x", model="m", prompt="p", max_tokens=8)
    controls = RunControls(model="m", base_url="http://x", warmup_runs=1, measured_runs=0)
    summary = build_summary(request=request, controls=controls, rows=rows)
    s = summary["summary"]
    assert s["measured_runs"] == 0
    assert s["errors"] == 0
    assert math.isnan(s["ttft_seconds"]["p50"])
    assert math.isnan(s["e2e_seconds"]["p50"])
