"""Tests for ``scripts.measure_ttft_once``.

We feed the ``measure_stream`` helper a synthetic chunk stream and a controlled
clock so timing is deterministic. The full ``main()`` entry point is exercised
with a mocked HTTP transport so the CLI -> JSON write path is covered.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts import _client, measure_ttft_once
from scripts._client import CompletionRequest
from scripts._metrics import RunControls
from scripts.measure_ttft_once import build_record, measure_stream


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


def test_build_record_shape() -> None:
    request = CompletionRequest(
        base_url="http://x", model="m", prompt="p", max_tokens=8,
    )
    controls = RunControls(
        model="m", base_url="http://x", measured_runs=1, warmup_runs=0,
        decoding={"temperature": 0.0, "max_tokens": 8},
    )
    from scripts.measure_ttft_once import StreamRunResult

    result = StreamRunResult(
        ttft_seconds=0.1,
        e2e_seconds=0.5,
        chunks_received=3,
        output_text="hi",
        completed=True,
    )
    record = build_record(request=request, controls=controls, result=result)

    assert record["schema"] == "nanoserve-mini.ttft-once.v1"
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
    sse = (
        b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":" there"}}]}\n\n'
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
    assert record["schema"] == "nanoserve-mini.ttft-once.v1"
    assert record["controls"]["gpu_model"] == "H200 NVL"
    assert record["controls"]["vllm_version"] == "0.6.0"
    assert record["metrics"]["completed"] is True
    assert record["metrics"]["ttft_seconds"] is not None
    assert record["metrics"]["e2e_seconds"] >= record["metrics"]["ttft_seconds"]
    assert record["output_text"] == "hi there"

    out = capsys.readouterr().out
    assert "TTFT:" in out
    assert "E2E:" in out
