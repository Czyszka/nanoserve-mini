"""Tests for ``benchmarks.scripts.run_sequential_benchmark``.

The end-to-end CLI test uses an httpx.MockTransport that returns a deterministic
SSE stream for every request, so the JSONL + summary write paths are covered
without a real vLLM.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from benchmarks.scripts import _client, run_sequential_benchmark
from benchmarks.scripts._client import CompletionRequest
from benchmarks.scripts._metrics import RunControls
from benchmarks.scripts.run_sequential_benchmark import (
    RunRow,
    build_summary,
    run_sequential,
    write_jsonl,
)

_SSE = (
    b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
    b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
    b"data: [DONE]\n\n"
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


def _mock_streaming_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    expected_authorization: str | None = None,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["stream"] is True
        assert request.headers.get("authorization") == expected_authorization
        return httpx.Response(200, content=_SSE, headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs.pop("timeout", None)
        return real_client_cls(transport=transport)

    monkeypatch.setattr(_client.httpx, "Client", fake_client)


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

    assert summary["schema"] == "nanoserve-mini.sequential-bench.v3"
    assert summary["methodology"] == "mlperf_inspired_lite"
    assert summary["benchmark_mode"] == "singlestream_lite_repeated"
    assert summary["error"] is None
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
            ttft_seconds=None, e2e_seconds=None,
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


def test_write_jsonl_one_line_per_row_with_schema(tmp_path: Path) -> None:
    rows = [_ok_row(0), _ok_row(1)]
    path = tmp_path / "out.jsonl"
    write_jsonl(path, rows)

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["index"] == 0
    assert parsed[1]["index"] == 1
    assert all(p["phase"] == "measured" for p in parsed)
    # v3 schema fields
    assert parsed[0]["schema"] == "nanoserve-mini.sequential-bench-row.v3"
    assert parsed[0]["methodology"] == "mlperf_inspired_lite"
    assert parsed[0]["benchmark_mode"] == "singlestream_lite_repeated"


def test_run_sequential_continues_after_per_run_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_execute_run(_request, *, timeout, clock=None):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated transient")
        from benchmarks.scripts.measure_ttft_once import StreamRunResult
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
    _mock_streaming_client(monkeypatch, expected_authorization="Bearer sk-test")

    jsonl = tmp_path / "bench.jsonl"
    summary_path = tmp_path / "bench_summary.json"

    rc = run_sequential_benchmark.main([
        "--model", "m",
        "--prompt", "hi",
        "--warmup", "1",
        "--runs", "3",
        "--max-tokens", "4",
        "--api-key", "sk-test",
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
    # v3 row fields
    assert parsed[0]["schema"] == "nanoserve-mini.sequential-bench-row.v3"
    assert parsed[0]["benchmark_mode"] == "singlestream_lite_repeated"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["schema"] == "nanoserve-mini.sequential-bench.v3"
    assert summary["methodology"] == "mlperf_inspired_lite"
    assert summary["benchmark_mode"] == "singlestream_lite_repeated"
    assert summary["error"] is None
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


def test_parse_args_accepts_api_key() -> None:
    args = run_sequential_benchmark.parse_args(["--model", "m", "--api-key", "sk-test"])
    assert args.api_key == "sk-test"


def test_main_uses_run_id_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_streaming_client(monkeypatch)

    orig_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        rc = run_sequential_benchmark.main([
            "--model", "m",
            "--warmup", "0",
            "--runs", "2",
            "--run-id", "run-xyz",
        ])
        assert rc == 0
    finally:
        os.chdir(orig_dir)

    base = tmp_path / "results" / "runs" / "run-xyz" / "singlestream_lite_repeated"
    assert (base / "results.jsonl").exists()
    assert (base / "summary.json").exists()

    summary = json.loads((base / "summary.json").read_text(encoding="utf-8"))
    assert summary["benchmark_mode"] == "singlestream_lite_repeated"
    assert summary["controls"]["run_id"] == "run-xyz"

    lines = (base / "results.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    row = json.loads(lines[0])
    assert row["benchmark_mode"] == "singlestream_lite_repeated"


def test_main_rejects_zero_runs(capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_sequential_benchmark.main([
        "--model", "m",
        "--runs", "0",
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "--runs must be >= 1" in err


def test_summary_with_zero_measured_is_safe_and_strict_json() -> None:
    rows = [_ok_row(0, phase="warmup")]
    request = CompletionRequest(base_url="http://x", model="m", prompt="p", max_tokens=8)
    controls = RunControls(model="m", base_url="http://x", warmup_runs=1, measured_runs=0)
    summary = build_summary(request=request, controls=controls, rows=rows)
    s = summary["summary"]
    assert s["measured_runs"] == 0
    assert s["errors"] == 0
    for key in ("min", "p50", "p95", "max", "mean"):
        assert s["ttft_seconds"][key] is None
        assert s["e2e_seconds"][key] is None
    # The whole record must serialize under strict JSON (no NaN tokens).
    encoded = json.dumps(summary, allow_nan=False)
    assert "NaN" not in encoded


def test_error_run_jsonl_row_is_strict_json(tmp_path: Path) -> None:
    """Errored rows carry None, not NaN, and the JSONL line is strict JSON."""
    rows = [
        RunRow(
            index=0, phase="measured", timestamp="t",
            ttft_seconds=None, e2e_seconds=None,
            chunks_received=0, output_chars=0,
            error="ConnectError: boom",
        ),
    ]
    path = tmp_path / "errored.jsonl"
    write_jsonl(path, rows)
    line = path.read_text(encoding="utf-8").strip()
    # strict load must succeed
    parsed = json.loads(line)
    assert parsed["e2e_seconds"] is None
    assert parsed["ttft_seconds"] is None
    # NaN is not valid JSON, so this also acts as a regression check
    assert "NaN" not in line
    # v2 schema
    assert parsed["schema"] == "nanoserve-mini.sequential-bench-row.v3"


def test_build_summary_includes_measured_only_throughput() -> None:
    rows = [
        _ok_row(0, phase="warmup", e2e=5.0),  # warmup excluded from denominator
        _ok_row(0, phase="measured", e2e=0.5),
        _ok_row(1, phase="measured", e2e=0.5),
    ]
    request = CompletionRequest(base_url="http://x", model="m", prompt="p", max_tokens=8)
    controls = RunControls(model="m", base_url="http://x", warmup_runs=1, measured_runs=2)
    # measured_wall_clock_seconds reflects only the measured phase wall time
    summary = build_summary(
        request=request, controls=controls, rows=rows, measured_wall_clock_seconds=2.0,
    )
    s = summary["summary"]
    assert "measured_wall_clock_seconds" in s
    assert "wall_clock_seconds" not in s  # old ambiguous name must not appear
    assert s["measured_wall_clock_seconds"] == pytest.approx(2.0)
    assert s["request_throughput"] == pytest.approx(1.0)  # 2 measured runs / 2.0 s
    assert s["output_chars_per_second"] is not None


def test_build_summary_aggregates_token_metrics_when_available() -> None:
    rows = [
        # warmup row excluded from aggregates
        RunRow(
            index=0, phase="warmup", timestamp="t",
            ttft_seconds=0.1, e2e_seconds=0.6, chunks_received=3,
            output_chars=8, error=None,
            tpot_seconds=0.05, prompt_tokens=4, completion_tokens=11,
            output_tokens_per_second=18.3,
        ),
        RunRow(
            index=0, phase="measured", timestamp="t",
            ttft_seconds=0.1, e2e_seconds=0.6, chunks_received=3,
            output_chars=8, error=None,
            tpot_seconds=0.10, prompt_tokens=4, completion_tokens=6,
            output_tokens_per_second=10.0,
        ),
        RunRow(
            index=1, phase="measured", timestamp="t",
            ttft_seconds=0.2, e2e_seconds=1.2, chunks_received=3,
            output_chars=8, error=None,
            tpot_seconds=0.20, prompt_tokens=4, completion_tokens=6,
            output_tokens_per_second=5.0,
        ),
    ]
    request = CompletionRequest(base_url="http://x", model="m", prompt="p", max_tokens=8)
    controls = RunControls(model="m", base_url="http://x", warmup_runs=1, measured_runs=2)
    summary = build_summary(
        request=request, controls=controls, rows=rows, measured_wall_clock_seconds=2.0,
    )
    s = summary["summary"]
    assert s["tpot_seconds"]["count"] == 2
    assert s["tpot_seconds"]["min"] == pytest.approx(0.10)
    assert s["tpot_seconds"]["max"] == pytest.approx(0.20)
    assert s["prompt_tokens"]["count"] == 2
    assert s["prompt_tokens"]["mean"] == pytest.approx(4.0)
    assert s["completion_tokens"]["count"] == 2
    assert s["completion_tokens"]["mean"] == pytest.approx(6.0)
    # output tokens/s = total measured completion tokens / measured wall clock
    assert s["output_tokens_per_second"] == pytest.approx(12 / 2.0)


def test_build_summary_token_aggregates_are_none_when_usage_missing() -> None:
    rows = [_ok_row(0, phase="measured"), _ok_row(1, phase="measured")]
    request = CompletionRequest(base_url="http://x", model="m", prompt="p", max_tokens=8)
    controls = RunControls(model="m", base_url="http://x", measured_runs=2)
    summary = build_summary(
        request=request, controls=controls, rows=rows, measured_wall_clock_seconds=1.0,
    )
    s = summary["summary"]
    assert s["tpot_seconds"]["count"] == 0
    assert s["prompt_tokens"]["count"] == 0
    assert s["completion_tokens"]["count"] == 0
    # No completion tokens recorded => tokens-per-second is None (not 0)
    assert s["output_tokens_per_second"] is None


def test_build_summary_includes_server_metrics_stub() -> None:
    rows = [_ok_row(0)]
    request = CompletionRequest(base_url="http://x", model="m", prompt="p", max_tokens=8)
    controls = RunControls(model="m", base_url="http://x", measured_runs=1)
    summary = build_summary(request=request, controls=controls, rows=rows)
    assert summary["server_metrics"] == {
        "gpu_memory_used_gb": None,
        "kv_cache_usage": None,
        "prefix_cache_hit_rate": None,
    }


def test_main_summary_includes_token_blocks_and_server_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_streaming_client(monkeypatch)
    summary_path = tmp_path / "summary.json"
    rc = run_sequential_benchmark.main([
        "--model", "m",
        "--warmup", "0",
        "--runs", "2",
        "--output-jsonl", str(tmp_path / "rows.jsonl"),
        "--output-summary", str(summary_path),
    ])
    assert rc == 0
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    s = summary["summary"]
    # Mock SSE has no usage chunk, so token blocks exist with count=0
    for key in ("tpot_seconds", "prompt_tokens", "completion_tokens"):
        assert key in s
        assert s[key]["count"] == 0
    assert "output_tokens_per_second" in s
    # server_metrics stub at the top level of summary
    assert summary["server_metrics"]["gpu_memory_used_gb"] is None
    # controls carry workload_spec and run_uuid
    assert summary["controls"]["workload_spec"]["arrival_process"] == "sequential"
    assert summary["controls"]["concurrency"] == 1
    assert summary["controls"]["run_uuid"] is not None
