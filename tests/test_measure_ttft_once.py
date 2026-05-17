"""Tests for ``benchmarks.scripts.measure_ttft_once``.

We feed the ``measure_stream`` helper a synthetic chunk stream and a controlled
clock so timing is deterministic. The full ``main()`` entry point is exercised
with a mocked HTTP transport so the CLI -> JSON write path is covered.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from benchmarks.scripts import _client, measure_ttft_once
from benchmarks.scripts._client import CompletionRequest
from benchmarks.scripts._metrics import RunControls
from benchmarks.scripts.measure_ttft_once import (
    build_record,
    compute_output_tokens_per_second,
    compute_tpot_seconds,
    measure_stream,
)


class _FakeClock:
    def __init__(self, ticks: list[float]) -> None:
        self._ticks = list(ticks)

    def __call__(self) -> float:
        return self._ticks.pop(0)


def _chunks() -> Iterator[dict[str, Any]]:
    # First chunk has only role — should NOT count as TTFT.
    yield {"choices": [{"delta": {"role": "assistant"}}]}
    yield {"choices": [{"delta": {"content": "hi"}}]}
    yield {"choices": [{"delta": {"content": " there"}}]}


_SSE = (
    b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
    b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
    b'data: {"choices":[{"delta":{"content":" there"}}]}\n\n'
    b"data: [DONE]\n\n"
)


def _mock_streaming_client(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["stream"] is True
        return httpx.Response(200, content=_SSE, headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs.pop("timeout", None)
        return real_client_cls(transport=transport)

    monkeypatch.setattr(_client.httpx, "Client", fake_client)


def test_measure_stream_anchors_ttft_on_first_content_chunk() -> None:
    # The clock is only consulted twice in the happy path:
    # once on the first content chunk (TTFT anchor) and once after iteration
    # ends (E2E anchor). The role-only first chunk and subsequent content
    # chunks do not consume clock ticks.
    clock = _FakeClock([0.10, 0.20])
    result = measure_stream(_chunks(), start_time=0.0, clock=clock)

    assert result.ttft_seconds == pytest.approx(0.10)
    assert result.e2e_seconds == pytest.approx(0.20)
    assert result.chunks_received == 3
    assert result.output_text == "hi there"
    assert result.completed is True


def test_measure_stream_handles_no_content_chunks() -> None:
    clock = _FakeClock([0.05])

    def only_role() -> Iterator[dict[str, Any]]:
        yield {"choices": [{"delta": {"role": "assistant"}}]}

    result = measure_stream(only_role(), start_time=0.0, clock=clock)
    assert result.ttft_seconds is None
    assert result.e2e_seconds == pytest.approx(0.05)
    assert result.output_text == ""
    assert result.usage is None
    # A role-only stream is not a "completed" generation — it produced zero
    # tokens. completed must be False so dashboards don't count it as a hit.
    assert result.completed is False


def test_measure_stream_handles_empty_stream() -> None:
    clock = _FakeClock([0.01])

    def empty() -> Iterator[dict[str, Any]]:
        return
        yield  # pragma: no cover - keeps this a generator function

    result = measure_stream(empty(), start_time=0.0, clock=clock)
    assert result.chunks_received == 0
    assert result.ttft_seconds is None
    assert result.completed is False


def test_measure_stream_captures_usage_when_present() -> None:
    clock = _FakeClock([0.10, 0.30])

    def chunks_with_usage() -> Iterator[dict[str, Any]]:
        yield {"choices": [{"delta": {"role": "assistant"}}]}
        yield {"choices": [{"delta": {"content": "hi"}}]}
        yield {"choices": [{"delta": {"content": " there"}}]}
        yield {
            "choices": [],
            "usage": {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9},
        }

    result = measure_stream(chunks_with_usage(), start_time=0.0, clock=clock)
    assert result.usage == {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9}
    assert result.ttft_seconds == pytest.approx(0.10)
    assert result.e2e_seconds == pytest.approx(0.30)


def test_compute_tpot_seconds_basic() -> None:
    # 100 ms TTFT, 600 ms E2E, 6 tokens => 500 ms / 5 = 100 ms per token
    assert compute_tpot_seconds(
        ttft_seconds=0.1, e2e_seconds=0.6, completion_tokens=6,
    ) == pytest.approx(0.1)


def test_compute_tpot_seconds_returns_none_when_inputs_missing() -> None:
    assert compute_tpot_seconds(ttft_seconds=None, e2e_seconds=0.5, completion_tokens=2) is None
    assert compute_tpot_seconds(ttft_seconds=0.1, e2e_seconds=None, completion_tokens=2) is None
    assert compute_tpot_seconds(ttft_seconds=0.1, e2e_seconds=0.5, completion_tokens=None) is None


def test_compute_tpot_seconds_returns_none_for_one_or_zero_tokens() -> None:
    assert compute_tpot_seconds(ttft_seconds=0.1, e2e_seconds=0.5, completion_tokens=1) is None
    assert compute_tpot_seconds(ttft_seconds=0.1, e2e_seconds=0.5, completion_tokens=0) is None


def test_compute_tpot_seconds_returns_none_for_nonpositive_decode_window() -> None:
    # ttft >= e2e means we have no decode window — guard against pathological data
    assert compute_tpot_seconds(ttft_seconds=0.5, e2e_seconds=0.5, completion_tokens=4) is None


def test_compute_output_tokens_per_second_basic() -> None:
    assert compute_output_tokens_per_second(
        e2e_seconds=2.0, completion_tokens=10,
    ) == pytest.approx(5.0)
    assert compute_output_tokens_per_second(e2e_seconds=None, completion_tokens=10) is None
    assert compute_output_tokens_per_second(e2e_seconds=2.0, completion_tokens=None) is None
    assert compute_output_tokens_per_second(e2e_seconds=0.0, completion_tokens=10) is None


def test_build_record_shape() -> None:
    request = CompletionRequest(
        base_url="http://x", model="m", prompt="p", max_tokens=8,
    )
    controls = RunControls(
        model="m", base_url="http://x", measured_runs=1, warmup_runs=0,
        decoding={"temperature": 0.0, "max_tokens": 8},
    )
    from benchmarks.scripts.measure_ttft_once import StreamRunResult

    result = StreamRunResult(
        ttft_seconds=0.1,
        e2e_seconds=0.5,
        chunks_received=3,
        output_text="hi",
        completed=True,
    )
    record = build_record(request=request, controls=controls, result=result)

    assert record["schema"] == "nanoserve-mini.ttft-once.v2"
    assert record["methodology"] == "mlperf_inspired_lite"
    assert record["benchmark_mode"] == "singlestream_lite_latency"
    assert record["error"] is None
    assert "timestamp" in record
    assert record["controls"]["model"] == "m"
    assert record["request"]["max_tokens"] == 8
    assert record["metrics"]["ttft_seconds"] == 0.1
    assert record["metrics"]["e2e_seconds"] == 0.5
    assert record["metrics"]["chunks_received"] == 3
    assert record["metrics"]["completed"] is True
    assert record["output_text"] == "hi"


def test_main_writes_result_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _mock_streaming_client(monkeypatch)

    output = tmp_path / "first_ttft.json"
    rc = measure_ttft_once.main([
        "--model", "m",
        "--prompt", "hello",
        "--max-tokens", "8",
        "--gpu-model", "H200 NVL",
        "--vllm-version", "0.6.0",
        "--output", str(output),
    ])
    assert rc == 0
    assert output.exists()

    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["schema"] == "nanoserve-mini.ttft-once.v2"
    assert record["methodology"] == "mlperf_inspired_lite"
    assert record["benchmark_mode"] == "singlestream_lite_latency"
    assert record["error"] is None
    assert record["controls"]["gpu_model"] == "H200 NVL"
    assert record["controls"]["vllm_version"] == "0.6.0"
    assert record["metrics"]["completed"] is True
    assert record["metrics"]["ttft_seconds"] is not None
    assert record["metrics"]["e2e_seconds"] >= record["metrics"]["ttft_seconds"]
    # mock SSE has no usage chunk; token-derived metrics fall back to None
    assert record["metrics"]["prompt_tokens"] is None
    assert record["metrics"]["completion_tokens"] is None
    assert record["metrics"]["tpot_seconds"] is None
    assert record["metrics"]["output_tokens_per_second"] is None
    # server_metrics stub is always present with null values for now
    assert record["server_metrics"] == {
        "gpu_memory_used_gb": None,
        "kv_cache_usage": None,
        "prefix_cache_hit_rate": None,
    }
    # controls carry the new contract fields
    assert record["controls"]["concurrency"] == 1
    assert record["controls"]["run_uuid"] is not None
    assert record["controls"]["workload_spec"]["arrival_process"] == "single"
    assert record["controls"]["workload_spec"]["concurrency"] == 1
    assert record["output_text"] == "hi there"

    out = capsys.readouterr().out
    assert "TTFT:" in out
    assert "E2E:" in out
    assert "TPOT:" in out


def test_main_uses_run_id_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_streaming_client(monkeypatch)

    orig_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        rc = measure_ttft_once.main(["--model", "m", "--run-id", "run-abc"])
        assert rc == 0
    finally:
        os.chdir(orig_dir)

    expected = (
        tmp_path / "results" / "runs" / "run-abc" / "singlestream_lite_latency" / "result.json"
    )
    assert expected.exists()
    record = json.loads(expected.read_text(encoding="utf-8"))
    assert record["benchmark_mode"] == "singlestream_lite_latency"
    assert record["controls"]["run_id"] == "run-abc"


def test_main_output_overrides_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_streaming_client(monkeypatch)
    explicit = tmp_path / "explicit.json"
    rc = measure_ttft_once.main(["--model", "m", "--run-id", "run-999", "--output", str(explicit)])
    assert rc == 0
    assert explicit.exists()


def test_main_json_is_strict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_streaming_client(monkeypatch)
    output = tmp_path / "out.json"
    measure_ttft_once.main(["--model", "m", "--output", str(output)])
    raw = output.read_text(encoding="utf-8")
    assert "NaN" not in raw
    assert "Infinity" not in raw
    json.loads(raw)


def _mock_failing_client(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    """Patch httpx.Client so any POST raises ``exc``.

    Lets us exercise the failure-record path without a live server.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs.pop("timeout", None)
        return real_client_cls(transport=transport)

    monkeypatch.setattr(_client.httpx, "Client", fake_client)


def test_main_writes_failure_record_on_connect_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _mock_failing_client(monkeypatch, httpx.ConnectError("connection refused"))

    output = tmp_path / "fail.json"
    rc = measure_ttft_once.main([
        "--model", "m",
        "--prompt", "hello",
        "--max-tokens", "8",
        "--output", str(output),
    ])
    # Non-zero exit on failure
    assert rc == 1
    # File still written so an aggregator can see the failure
    assert output.exists()

    record = json.loads(output.read_text(encoding="utf-8"))
    # Schema and contract still v2
    assert record["schema"] == "nanoserve-mini.ttft-once.v2"
    assert record["methodology"] == "mlperf_inspired_lite"
    assert record["benchmark_mode"] == "singlestream_lite_latency"
    # Controls + request preserved
    assert record["controls"]["model"] == "m"
    assert record["controls"]["concurrency"] == 1
    assert record["controls"]["workload_spec"] is not None
    assert record["request"]["prompt"] == "hello"
    assert record["request"]["max_tokens"] == 8
    # Server-metrics stub still present
    assert record["server_metrics"] == {
        "gpu_memory_used_gb": None,
        "kv_cache_usage": None,
        "prefix_cache_hit_rate": None,
    }
    # Metrics: completed=False, all token-derived metrics null
    metrics = record["metrics"]
    assert metrics["completed"] is False
    assert metrics["ttft_seconds"] is None
    assert metrics["tpot_seconds"] is None
    assert metrics["output_tokens_per_second"] is None
    assert metrics["prompt_tokens"] is None
    assert metrics["completion_tokens"] is None
    assert metrics["total_tokens"] is None
    # E2E recorded as elapsed-until-failure (non-negative float)
    assert isinstance(metrics["e2e_seconds"], float)
    assert metrics["e2e_seconds"] >= 0.0
    # Error string present and informative
    assert isinstance(record["error"], str)
    assert "ConnectError" in record["error"]
    assert "connection refused" in record["error"]
    # Strict JSON
    raw = output.read_text(encoding="utf-8")
    assert "NaN" not in raw
    assert "Infinity" not in raw

    err = capsys.readouterr().err
    assert "ConnectError" in err


def test_main_writes_failure_record_on_http_5xx(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 5xx during streaming must also produce a failure record."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream busy")

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs.pop("timeout", None)
        return real_client_cls(transport=transport)

    monkeypatch.setattr(_client.httpx, "Client", fake_client)

    output = tmp_path / "fail.json"
    rc = measure_ttft_once.main(["--model", "m", "--output", str(output)])
    assert rc == 1
    assert output.exists()

    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["error"] is not None
    assert "HTTPStatusError" in record["error"]
    assert record["metrics"]["completed"] is False
    assert record["metrics"]["ttft_seconds"] is None
