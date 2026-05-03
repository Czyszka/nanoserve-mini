"""Smoke tests for ``scripts.request_once``.

We don't hit a real server. We just verify the CLI parses arguments correctly
and that ``main()`` wires the parsed args into the HTTP client and prints the
expected summary.
"""

from __future__ import annotations

import json

import httpx
import pytest

from scripts import _client, request_once


def test_parse_args_defaults() -> None:
    args = request_once.parse_args(["--model", "m"])
    assert args.base_url == "http://127.0.0.1:8000"
    assert args.model == "m"
    assert args.max_tokens == 64
    assert args.temperature == 0.0
    assert args.raw is False


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
        return httpx.Response(
            200,
            json={
                "id": "cmpl-xyz",
                "model": "m",
                "choices": [{"message": {"role": "assistant", "content": "hi there"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        )

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs.pop("timeout", None)
        return real_client_cls(transport=transport)

    monkeypatch.setattr(_client.httpx, "Client", fake_client)

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

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs.pop("timeout", None)
        return real_client_cls(transport=transport)

    monkeypatch.setattr(_client.httpx, "Client", fake_client)

    rc = request_once.main(["--model", "m", "--raw"])
    assert rc == 0

    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed == payload
