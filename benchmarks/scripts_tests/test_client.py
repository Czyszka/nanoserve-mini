"""Tests for ``benchmarks.scripts._client``.

We can't talk to a real vLLM on the laptop, so all tests use ``httpx.MockTransport``
to fake the server. The point is to keep the request-shaping code honest:
- correct URL,
- correct payload,
- correct parsing of both non-streaming and streaming responses.
"""

from __future__ import annotations

import json

import httpx
import pytest

from benchmarks.scripts._client import (
    CompletionRequest,
    build_payload,
    chat_completion,
    chat_completion_stream,
    extract_assistant_text,
    extract_stream_delta_text,
    extract_stream_reasoning_text,
    extract_stream_usage,
)


def _request() -> CompletionRequest:
    return CompletionRequest(
        base_url="http://example.test:8000",
        model="test-model",
        prompt="hello",
        max_tokens=8,
        temperature=0.0,
    )


def test_build_payload_non_stream() -> None:
    payload = build_payload(_request(), stream=False)
    assert payload == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 8,
        "temperature": 0.0,
        "stream": False,
    }


def test_build_payload_stream_with_extra() -> None:
    request = CompletionRequest(
        base_url="http://x",
        model="m",
        prompt="p",
        max_tokens=1,
        extra={"top_p": 0.9, "stop": ["\n"]},
    )
    payload = build_payload(request, stream=True)
    assert payload["stream"] is True
    assert payload["top_p"] == 0.9
    assert payload["stop"] == ["\n"]


def test_chat_completion_hits_correct_url_and_parses_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "cmpl-1",
                "model": "test-model",
                "choices": [
                    {"message": {"role": "assistant", "content": "hi there"}},
                ],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        response = chat_completion(_request(), client=client)
    finally:
        client.close()

    assert captured["url"] == "http://example.test:8000/v1/chat/completions"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "test-model"
    assert body["stream"] is False
    assert extract_assistant_text(response) == "hi there"


def test_chat_completion_adds_authorization_header_with_api_key() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "id": "cmpl-1",
                "model": "test-model",
                "choices": [{"message": {"role": "assistant", "content": "hi"}}],
            },
        )

    req = CompletionRequest(
        base_url="http://example.test:8000",
        model="test-model",
        prompt="hello",
        api_key="sk-test",
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        chat_completion(req, client=client)
    finally:
        client.close()

    assert captured["authorization"] == "Bearer sk-test"


def test_chat_completion_omits_authorization_header_without_api_key() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "id": "cmpl-1",
                "model": "test-model",
                "choices": [{"message": {"role": "assistant", "content": "hi"}}],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        chat_completion(_request(), client=client)
    finally:
        client.close()

    assert captured["authorization"] is None


def test_chat_completion_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(httpx.HTTPStatusError):
            chat_completion(_request(), client=client)
    finally:
        client.close()


def test_chat_completion_stream_yields_chunks_and_stops_on_done() -> None:
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

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        chunks = list(chat_completion_stream(_request(), client=client))
    finally:
        client.close()

    assert len(chunks) == 3
    text = "".join(extract_stream_delta_text(c) for c in chunks)
    assert text == "hi there"


def test_chat_completion_stream_adds_authorization_header_with_api_key() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            content=b"data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    req = CompletionRequest(
        base_url="http://example.test:8000",
        model="test-model",
        prompt="hello",
        api_key="sk-stream",
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        list(chat_completion_stream(req, client=client))
    finally:
        client.close()

    assert captured["authorization"] == "Bearer sk-stream"


def test_extract_assistant_text_handles_missing_fields() -> None:
    assert extract_assistant_text({}) == ""
    assert extract_assistant_text({"choices": []}) == ""
    assert extract_assistant_text({"choices": [{"message": {}}]}) == ""


def test_extract_stream_delta_text_handles_missing_fields() -> None:
    assert extract_stream_delta_text({}) == ""
    assert extract_stream_delta_text({"choices": [{"delta": {}}]}) == ""
    assert extract_stream_delta_text({"choices": [{"delta": {"role": "assistant"}}]}) == ""


def test_extract_stream_reasoning_text_handles_missing_fields() -> None:
    assert extract_stream_reasoning_text({}) == ""
    assert extract_stream_reasoning_text({"choices": []}) == ""
    assert extract_stream_reasoning_text({"choices": [{"delta": {}}]}) == ""
    # a plain content chunk carries no reasoning
    assert extract_stream_reasoning_text({"choices": [{"delta": {"content": "hi"}}]}) == ""


def test_extract_stream_reasoning_text_reads_kimi_reasoning_field() -> None:
    # Kimi K2.6 streams chain-of-thought via delta.reasoning
    chunk = {"choices": [{"delta": {"reasoning": " The user wants"}}]}
    assert extract_stream_reasoning_text(chunk) == " The user wants"
    # ...and content stays empty for that chunk
    assert extract_stream_delta_text(chunk) == ""


def test_extract_stream_reasoning_text_reads_reasoning_content_field() -> None:
    # DeepSeek-style models use delta.reasoning_content
    chunk = {"choices": [{"delta": {"reasoning_content": "step 1"}}]}
    assert extract_stream_reasoning_text(chunk) == "step 1"


def test_extract_stream_reasoning_text_ignores_non_string() -> None:
    assert extract_stream_reasoning_text({"choices": [{"delta": {"reasoning": None}}]}) == ""
    assert extract_stream_reasoning_text({"choices": [{"delta": {"reasoning": 123}}]}) == ""


def test_extract_stream_usage_returns_dict_or_none() -> None:
    assert extract_stream_usage({}) is None
    assert extract_stream_usage({"choices": []}) is None
    usage = {"prompt_tokens": 3, "completion_tokens": 7, "total_tokens": 10}
    assert extract_stream_usage({"choices": [], "usage": usage}) == usage
    # malformed usage is rejected
    assert extract_stream_usage({"usage": "nope"}) is None


def test_chat_completion_stream_injects_include_usage_by_default() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            content=b"data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        list(chat_completion_stream(_request(), client=client))
    finally:
        client.close()

    body = captured["body"]
    assert isinstance(body, dict)
    assert body["stream"] is True
    assert body.get("stream_options") == {"include_usage": True}


def test_chat_completion_stream_caller_stream_options_wins() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            content=b"data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    request = CompletionRequest(
        base_url="http://x",
        model="m",
        prompt="p",
        max_tokens=1,
        extra={"stream_options": {"include_usage": False}},
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        list(chat_completion_stream(request, client=client))
    finally:
        client.close()

    body = captured["body"]
    assert isinstance(body, dict)
    # caller-provided stream_options must not be overwritten
    assert body["stream_options"] == {"include_usage": False}


def test_chat_completion_stream_include_usage_false_omits_field() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            content=b"data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        list(chat_completion_stream(_request(), client=client, include_usage=False))
    finally:
        client.close()

    body = captured["body"]
    assert isinstance(body, dict)
    assert "stream_options" not in body
