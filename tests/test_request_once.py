"""Smoke tests for ``scripts.request_once``.

We don't hit a real server. We just verify the CLI parses arguments correctly
and that ``main()`` wires the parsed args into the HTTP client and prints the
expected summary.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scripts import _client, request_once


def _mock_transport(response_payload: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_payload)
    return httpx.MockTransport(handler)


def _patch_client(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    real_client_cls = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs.pop("timeout", None)
        return real_client_cls(transport=transport)

    monkeypatch.setattr(_client.httpx, "Client", fake_client)


_GOOD_PAYLOAD = {
    "id": "cmpl-xyz",
    "model": "m",
    "choices": [{"message": {"role": "assistant", "content": "hi there"}}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
}


def test_parse_args_defaults() -> None:
    args = request_once.parse_args(["--model", "m"])
    assert args.base_url == "http://127.0.0.1:8000"
    assert args.model == "m"
    assert args.max_tokens == 64
    assert args.temperature == 0.0
    assert args.raw is False
    assert args.output is None
    assert args.run_id is None


def test_parse_args_required_model() -> None:
    with pytest.raises(SystemExit):
        request_once.parse_args([])


def test_main_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "m"
        assert body["messages"] == [{"role": "user", "content": "hello"}]
        return httpx.Response(200, json=_GOOD_PAYLOAD)

    _patch_client(monkeypatch, httpx.MockTransport(handler))

    rc = request_once.main(["--model", "m", "--prompt", "hello"])
    assert rc == 0

    out = capsys.readouterr().out
    assert "id:    cmpl-xyz" in out
    assert "completion=2" in out
    assert "hi there" in out


def test_main_raw_prints_full_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = {
        "id": "cmpl-1",
        "model": "m",
        "choices": [{"message": {"role": "assistant", "content": "x"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }

    _patch_client(monkeypatch, _mock_transport(payload))

    rc = request_once.main(["--model", "m", "--raw"])
    assert rc == 0

    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed == payload


def test_main_writes_json_when_output_provided(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _mock_transport(_GOOD_PAYLOAD))
    monkeypatch.setattr(request_once, "get_git_commit", lambda: "abc123")

    out_file = tmp_path / "result.json"
    rc = request_once.main(["--model", "m", "--output", str(out_file)])
    assert rc == 0
    assert out_file.exists()

    record = json.loads(out_file.read_text(encoding="utf-8"))
    assert record["schema"] == "nanoserve-mini.request-once.v1"
    assert record["methodology"] == "mlperf_inspired_lite"
    assert record["benchmark_mode"] == "singlestream_lite_correctness"
    assert record["error"] is None
    assert record["metrics"]["completed"] is True
    assert record["metrics"]["e2e_seconds"] is not None
    assert record["metrics"]["output_chars"] == len("hi there")
    assert record["metrics"]["prompt_tokens"] == 1
    assert record["metrics"]["completion_tokens"] == 2
    assert record["output_text"] == "hi there"
    assert record["response"]["id"] == "cmpl-xyz"
    assert record["controls"]["script_name"] == "request_once.py"
    assert record["controls"]["git_commit"] == "abc123"


def test_main_uses_run_id_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _mock_transport(_GOOD_PAYLOAD))

    import os
    orig_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        rc = request_once.main(["--model", "m", "--run-id", "run-001"])
        assert rc == 0
    finally:
        os.chdir(orig_dir)

    expected = (
        tmp_path / "results" / "runs" / "run-001" / "singlestream_lite_correctness" / "result.json"
    )
    assert expected.exists()
    record = json.loads(expected.read_text(encoding="utf-8"))
    assert record["benchmark_mode"] == "singlestream_lite_correctness"
    assert record["controls"]["run_id"] == "run-001"


def test_main_output_overrides_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _mock_transport(_GOOD_PAYLOAD))

    explicit = tmp_path / "explicit.json"
    rc = request_once.main(["--model", "m", "--run-id", "run-999", "--output", str(explicit)])
    assert rc == 0
    assert explicit.exists()


def test_main_json_is_strict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _mock_transport(_GOOD_PAYLOAD))

    out_file = tmp_path / "result.json"
    request_once.main(["--model", "m", "--output", str(out_file)])
    raw = out_file.read_text(encoding="utf-8")
    assert "NaN" not in raw
    assert "Infinity" not in raw
    json.loads(raw)  # must not raise


def test_main_no_output_prints_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_client(monkeypatch, _mock_transport(_GOOD_PAYLOAD))
    rc = request_once.main(["--model", "m"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "hi there" in out
    assert "saved:" not in out
