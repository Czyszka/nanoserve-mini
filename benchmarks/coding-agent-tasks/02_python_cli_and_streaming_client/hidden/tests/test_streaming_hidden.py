"""Hidden tests — streaming edge cases."""

from __future__ import annotations

import contextlib
import json
from typing import Any

import pytest


class _FakeResponse:
    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            request = httpx.Request("POST", "http://h:8000/v1/chat/completions")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=request, response=response
            )

    def iter_lines(self):
        yield from self._lines


class _FakeClient:
    def __init__(self, *a: Any, **kw: Any):
        self.kwargs = kw

    def __enter__(self):
        return self

    def __exit__(self, *exc: Any):
        return False


def _make_client(lines: list[str], status_code: int = 200):
    class _C(_FakeClient):
        @contextlib.contextmanager
        def stream(self, method: str, url: str, json: dict[str, Any] | None = None, **kw: Any):
            yield _FakeResponse(lines, status_code=status_code)

    return _C


@pytest.fixture
def patch_httpx(monkeypatch):
    import httpx

    def _patch(client_cls):
        monkeypatch.setattr(httpx, "Client", client_cls)

    return _patch


def test_malformed_sse_json_exits_3(monkeypatch, tmp_path, patch_httpx):
    """Bug 3: malformed JSON after data: should produce exit code 3."""
    from stream_probe import cli

    lines = [
        'data: {"choices":[{"delta":{"content":"ok"}}]}',
        'data: {not-json-here',
        'data: [DONE]',
    ]
    patch_httpx(_make_client(lines))
    out = tmp_path / "out.json"
    rc = cli.main(
        [
            "--base-url", "http://h:8000",
            "--model", "m",
            "--prompt", "hi",
            "--output", str(out),
        ]
    )
    assert rc == cli.EXIT_STREAM_FAIL
    payload = json.loads(out.read_text("utf-8"))
    assert payload["error"] is not None
    assert payload["error"]["code"] == "stream_protocol_error"


def test_done_without_content_yields_no_content(monkeypatch, tmp_path, patch_httpx):
    from stream_probe import cli

    lines = ["data: [DONE]"]
    patch_httpx(_make_client(lines))
    out = tmp_path / "out.json"
    rc = cli.main(
        [
            "--base-url", "http://h:8000",
            "--model", "m",
            "--prompt", "hi",
            "--output", str(out),
        ]
    )
    assert rc == cli.EXIT_HTTP_FAIL
    payload = json.loads(out.read_text("utf-8"))
    assert payload["error"]["code"] == "no_content"


def test_http_500_writes_failure_report_exit_2(monkeypatch, tmp_path, patch_httpx):
    from stream_probe import cli

    patch_httpx(_make_client([], status_code=500))
    out = tmp_path / "out.json"
    rc = cli.main(
        [
            "--base-url", "http://h:8000",
            "--model", "m",
            "--prompt", "hi",
            "--output", str(out),
        ]
    )
    assert rc == cli.EXIT_HTTP_FAIL
    payload = json.loads(out.read_text("utf-8"))
    assert payload["error"] is not None
    assert payload["metrics"]["completed"] is False
