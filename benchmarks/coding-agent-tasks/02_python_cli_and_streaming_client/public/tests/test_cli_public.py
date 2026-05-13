"""Public tests for the stream-probe CLI.

These tests use a fake ``httpx.Client`` so no network is required.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

import pytest
from stream_probe import cli, client

# ---------------------------------------------------------------------------
# Fake httpx wiring
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_lines(self):
        yield from self._lines


class _FakeClient:
    instances: list[_FakeClient] = []

    def __init__(self, *args: Any, **kwargs: Any):
        self.kwargs = kwargs
        self.calls: list[dict[str, Any]] = []
        self.lines: list[str] = []
        _FakeClient.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc: Any):
        return False

    @contextlib.contextmanager
    def stream(self, method: str, url: str, json: dict[str, Any] | None = None, **kw: Any):
        self.calls.append({"method": method, "url": url, "json": json})
        yield _FakeResponse(self.lines)


@pytest.fixture
def fake_httpx(monkeypatch):
    _FakeClient.instances.clear()
    import httpx

    monkeypatch.setattr(httpx, "Client", _FakeClient)
    return _FakeClient


# ---------------------------------------------------------------------------
# 1. CLI validation
# ---------------------------------------------------------------------------


def test_cli_rejects_non_positive_max_tokens(tmp_path):
    rc = cli.main(
        [
            "--base-url", "http://h:8000",
            "--model", "m",
            "--prompt", "hi",
            "--output", str(tmp_path / "out.json"),
            "--max-tokens", "0",
        ]
    )
    assert rc == cli.EXIT_INVALID_ARGS


def test_cli_rejects_out_of_range_temperature(tmp_path):
    rc = cli.main(
        [
            "--base-url", "http://h:8000",
            "--model", "m",
            "--prompt", "hi",
            "--output", str(tmp_path / "out.json"),
            "--temperature", "2.5",
        ]
    )
    assert rc == cli.EXIT_INVALID_ARGS


# ---------------------------------------------------------------------------
# 2. Base URL normalization (FAILS due to bug 1)
# ---------------------------------------------------------------------------


def test_base_url_normalization_with_and_without_trailing_slash():
    expected = "http://host:8000/v1/chat/completions"
    assert client.build_url("http://host:8000") == expected
    assert client.build_url("http://host:8000/") == expected


# ---------------------------------------------------------------------------
# 3. Request body shape
# ---------------------------------------------------------------------------


def test_request_body_shape():
    body = client.build_request_body(
        model="gpt-x", prompt="hi", max_tokens=32, temperature=0.0
    )
    assert body["model"] == "gpt-x"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["max_tokens"] == 32
    assert body["temperature"] == 0.0
    assert body["stream"] is True


def test_cli_sends_expected_body(fake_httpx, tmp_path):
    out = tmp_path / "out.json"
    lines = [
        'data: {"choices":[{"delta":{"role":"assistant"}}]}',
        'data: {"choices":[{"delta":{"content":"hi"}}]}',
        'data: [DONE]',
    ]
    # The next instantiated client gets these lines.
    def _patched_init(self, *a, **kw):
        self.kwargs = kw
        self.calls = []
        self.lines = lines
        fake_httpx.instances.append(self)

    fake_httpx.__init__ = _patched_init  # type: ignore[assignment]

    rc = cli.main(
        [
            "--base-url", "http://h:8000",
            "--model", "m",
            "--prompt", "hi",
            "--output", str(out),
            "--max-tokens", "5",
            "--temperature", "0.0",
        ]
    )
    assert rc == 0
    inst = fake_httpx.instances[-1]
    assert inst.calls, "stream() was never called"
    sent = inst.calls[0]["json"]
    assert sent["model"] == "m"
    assert sent["stream"] is True
    assert sent["max_tokens"] == 5


# ---------------------------------------------------------------------------
# 4. Deterministic fake stream (FAILS due to bug 2)
# ---------------------------------------------------------------------------


def test_deterministic_stream_counts(fake_httpx, tmp_path):
    out = tmp_path / "out.json"
    lines = [
        'data: {"choices":[{"delta":{"role":"assistant"}}]}',
        'data: {"choices":[{"delta":{"content":"he"}}]}',
        'data: {"choices":[{"delta":{"content":"llo"}}]}',
        'data: [DONE]',
    ]

    def _patched_init(self, *a, **kw):
        self.kwargs = kw
        self.calls = []
        self.lines = lines
        fake_httpx.instances.append(self)

    fake_httpx.__init__ = _patched_init  # type: ignore[assignment]

    rc = cli.main(
        [
            "--base-url", "http://h:8000",
            "--model", "m",
            "--prompt", "hi",
            "--output", str(out),
        ]
    )
    assert rc == 0
    report = json.loads(out.read_text("utf-8"))
    metrics = report["metrics"]
    assert metrics["chunks_total"] == 3
    # Role-only chunk must NOT count toward content_chunks.
    assert metrics["content_chunks"] == 2
    assert report["output_text"] == "hello"
