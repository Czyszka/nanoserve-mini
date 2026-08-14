"""Tests for bench_ollama.py — no network, no real sleeping.

The script is stdlib-only; its HTTP layer is a single injectable ``transport``
callable (``post_stream``). Tests monkeypatch ``bench_ollama.post_stream``
with a canned SSE line stream so the script's own parsing and measurement
code runs end to end.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import bench_ollama

_NOW = datetime(2026, 8, 14, 10, 0, 0)

_SSE_NO_USAGE = (
    'data: {"choices":[{"delta":{"role":"assistant"}}]}\n'
    '\n'
    'data: {"choices":[{"delta":{"content":"Hello"}}]}\n'
    '\n'
    'data: {"choices":[{"delta":{"content":" world"}}]}\n'
    '\n'
    "data: [DONE]\n"
)

_SSE_WITH_USAGE = (
    'data: {"choices":[{"delta":{"role":"assistant"}}]}\n'
    '\n'
    'data: {"choices":[{"delta":{"content":"Hello"}}]}\n'
    '\n'
    'data: {"choices":[{"delta":{"content":" world"}}]}\n'
    '\n'
    'data: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":6}}\n'
    '\n'
    "data: [DONE]\n"
)


def _fake_transport(monkeypatch, *, sse: str, seen_requests: list | None = None):
    lines = sse.splitlines(keepends=True)

    def transport(url, payload, headers, timeout):
        if seen_requests is not None:
            seen_requests.append({"url": url, "payload": payload, "headers": headers})
        assert url.endswith("/v1/chat/completions")
        yield from lines

    monkeypatch.setattr(bench_ollama, "post_stream", transport)


# ---------------------------------------------------------------------------
# parse_start_at
# ---------------------------------------------------------------------------


def test_parse_start_at_hhmm_future_today():
    target = bench_ollama.parse_start_at("18:30", now=_NOW)
    assert target == _NOW.replace(hour=18, minute=30, second=0, microsecond=0)


def test_parse_start_at_hhmm_past_rolls_to_tomorrow():
    target = bench_ollama.parse_start_at("08:30", now=_NOW)
    assert target == _NOW.replace(hour=8, minute=30) + timedelta(days=1)


def test_parse_start_at_hhmm_equal_now_rolls_to_tomorrow():
    target = bench_ollama.parse_start_at("10:00", now=_NOW)
    assert target == _NOW + timedelta(days=1)


def test_parse_start_at_iso_verbatim():
    target = bench_ollama.parse_start_at("2026-08-15T06:00", now=_NOW)
    assert target == datetime(2026, 8, 15, 6, 0)


@pytest.mark.parametrize("value", ["25:99", "soon", "8h30"])
def test_parse_start_at_invalid_raises(value):
    with pytest.raises(ValueError):
        bench_ollama.parse_start_at(value, now=_NOW)


# ---------------------------------------------------------------------------
# wait_until
# ---------------------------------------------------------------------------


def test_wait_until_sleeps_in_chunks():
    target = _NOW + timedelta(seconds=70)
    current = [_NOW]
    sleeps: list[float] = []

    def clock() -> datetime:
        return current[0]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        current[0] += timedelta(seconds=seconds)

    bench_ollama.wait_until(target, clock=clock, sleep=sleep, log=lambda _msg: None)
    assert sleeps == [30.0, 30.0, 10.0]
    assert current[0] >= target


def test_wait_until_past_target_returns_immediately():
    sleeps: list[float] = []
    bench_ollama.wait_until(
        _NOW - timedelta(seconds=1),
        clock=lambda: _NOW,
        sleep=sleeps.append,
        log=lambda _msg: None,
    )
    assert sleeps == []


# ---------------------------------------------------------------------------
# normalize_base_url / load_prompts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://h:11434",
        "http://h:11434/",
        "http://h:11434/v1",
        "http://h:11434/v1/",
    ],
)
def test_normalize_base_url(url):
    assert bench_ollama.normalize_base_url(url) == "http://h:11434"


def _write_dataset(path: Path, prompts: list[str]) -> None:
    path.write_text(
        "".join(json.dumps({"prompt": p}) + "\n" for p in prompts), encoding="utf-8"
    )


def test_load_prompts_reads_offset_slice(tmp_path):
    dataset = tmp_path / "d.jsonl"
    _write_dataset(dataset, ["a", "b", "c", "d"])
    assert bench_ollama.load_prompts(dataset, offset=1, count=2) == ["b", "c"]


def test_load_prompts_errors_when_not_enough_rows(tmp_path):
    dataset = tmp_path / "d.jsonl"
    _write_dataset(dataset, ["a", "b"])
    with pytest.raises(ValueError, match="lower --num-requests"):
        bench_ollama.load_prompts(dataset, offset=1, count=2)


def test_load_prompts_errors_on_malformed_row(tmp_path):
    dataset = tmp_path / "d.jsonl"
    dataset.write_text('{"prompt": "ok"}\n{"text": "no prompt"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="d.jsonl:2"):
        bench_ollama.load_prompts(dataset, offset=0, count=2)


# ---------------------------------------------------------------------------
# post_stream (urllib transport)
# ---------------------------------------------------------------------------


def test_post_stream_posts_json_and_yields_lines(monkeypatch):
    captured: dict = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def __iter__(self):
            return iter([b"data: [DONE]\n"])

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["content_type"] = request.get_header("Content-type")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(bench_ollama.urllib.request, "urlopen", fake_urlopen)
    lines = list(
        bench_ollama.post_stream(
            "http://h:11434/v1/chat/completions",
            {"a": 1},
            {"Content-Type": "application/json"},
            5.0,
        )
    )
    assert lines == ["data: [DONE]\n"]
    assert captured["url"] == "http://h:11434/v1/chat/completions"
    assert captured["body"] == {"a": 1}
    assert captured["content_type"] == "application/json"
    assert captured["timeout"] == 5.0


# ---------------------------------------------------------------------------
# main() end-to-end against canned SSE
# ---------------------------------------------------------------------------


def _run_main(tmp_path, extra_args: list[str]) -> tuple[int, dict, list[dict]]:
    out_dir = tmp_path / "out"
    code = bench_ollama.main(
        [
            "--base-url",
            "http://h:11434/v1",
            "--model",
            "test-model",
            "--output-dir",
            str(out_dir),
            *extra_args,
        ]
    )
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (out_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return code, summary, rows


def test_main_with_usage_chunk_computes_tokens(monkeypatch, tmp_path):
    _fake_transport(monkeypatch, sse=_SSE_WITH_USAGE)
    code, summary, rows = _run_main(tmp_path, ["--num-requests", "2", "--warmup", "1"])
    assert code == 0
    measured = [r for r in rows if r["phase"] == "measured"]
    assert len(measured) == 2 and len(rows) == 3
    for row in measured:
        assert row["completion_tokens"] == 6
        assert row["prompt_tokens"] == 4
        assert row["tpot_seconds"] is not None
        assert row["error"] is None
    assert summary["metrics"]["tpot_seconds"]["count"] == 2
    assert summary["throughput"]["output_tokens_per_second"] is not None
    assert summary["requests"] == {
        "warmup": 1,
        "measured": 2,
        "measured_ok": 2,
        "measured_errors": 0,
    }


def test_main_without_usage_falls_back_to_chars(monkeypatch, tmp_path):
    _fake_transport(monkeypatch, sse=_SSE_NO_USAGE)
    code, summary, rows = _run_main(tmp_path, ["--num-requests", "1", "--warmup", "0"])
    assert code == 0
    (row,) = rows
    assert row["completion_tokens"] is None
    assert row["tpot_seconds"] is None
    assert row["output_chars"] == len("Hello world")
    assert summary["throughput"]["output_tokens_per_second"] is None
    assert summary["throughput"]["output_chars_per_second"] is not None
    assert summary["metrics"]["e2e_seconds"]["count"] == 1


def test_main_dataset_mode_varies_prompts(monkeypatch, tmp_path):
    seen: list[dict] = []
    _fake_transport(monkeypatch, sse=_SSE_WITH_USAGE, seen_requests=seen)
    dataset = tmp_path / "d.jsonl"
    _write_dataset(dataset, ["p0", "p1", "p2"])
    code, _summary, rows = _run_main(
        tmp_path,
        [
            "--dataset",
            str(dataset),
            "--dataset-offset",
            "1",
            "--num-requests",
            "2",
            "--warmup",
            "0",
        ],
    )
    assert code == 0
    sent = [entry["payload"]["messages"][0]["content"] for entry in seen]
    assert sent == ["p1", "p2"]
    assert [(r["prompt_index"], r["prompt_chars"]) for r in rows] == [(1, 2), (2, 2)]


def test_run_prompts_continues_after_error(monkeypatch):
    calls = {"n": 0}
    good = bench_ollama.StreamRunResult(
        ttft_seconds=0.1,
        e2e_seconds=0.5,
        chunks_received=3,
        output_text="ok",
        completed=True,
        usage={"prompt_tokens": 2, "completion_tokens": 4},
    )

    def fake_execute_one(request, *, timeout, include_usage, clock=bench_ollama._now):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return good

    monkeypatch.setattr(bench_ollama, "execute_one", fake_execute_one)
    base_request = bench_ollama.CompletionRequest(
        base_url="http://h:11434", model="m", prompt=""
    )
    rows = bench_ollama.run_prompts(
        [(0, "a"), (1, "b"), (2, "c")],
        phase="measured",
        base_request=base_request,
        timeout=1.0,
        include_usage=True,
        log=lambda _msg: None,
    )
    assert [row.error for row in rows] == [None, "RuntimeError: boom", None]
    assert rows[1].ttft_seconds is None and rows[1].e2e_seconds is None
    assert rows[0].tpot_seconds is not None


def test_main_start_at_is_wired(monkeypatch, tmp_path):
    _fake_transport(monkeypatch, sse=_SSE_WITH_USAGE)
    captured: list[datetime] = []
    monkeypatch.setattr(
        bench_ollama, "wait_until", lambda target, **kwargs: captured.append(target)
    )
    code, summary, _rows = _run_main(
        tmp_path, ["--num-requests", "1", "--warmup", "0", "--start-at", "00:01"]
    )
    assert code == 0
    assert len(captured) == 1
    expected = bench_ollama.parse_start_at("00:01", now=datetime.now())
    assert abs((captured[0] - expected).total_seconds()) < 120
    assert summary["client"]["scheduled_start_local"] == captured[0].isoformat(
        timespec="seconds"
    )
    assert summary["client"]["start_delay_seconds"] is not None


def test_main_rejects_num_requests_lt_1(tmp_path, capsys):
    code = bench_ollama.main(
        ["--base-url", "http://h:11434", "--model", "m", "--num-requests", "0"]
    )
    assert code == 2
    assert "--num-requests" in capsys.readouterr().err


def test_prompt_and_dataset_mutually_exclusive():
    with pytest.raises(SystemExit):
        bench_ollama.parse_args(
            ["--base-url", "u", "--model", "m", "--prompt", "p", "--dataset", "d"]
        )


def test_no_include_usage_omits_stream_options(monkeypatch, tmp_path):
    seen: list[dict] = []
    _fake_transport(monkeypatch, sse=_SSE_NO_USAGE, seen_requests=seen)
    code, _summary, _rows = _run_main(
        tmp_path, ["--num-requests", "1", "--warmup", "0", "--no-include-usage"]
    )
    assert code == 0
    assert all("stream_options" not in entry["payload"] for entry in seen)


def test_include_usage_sends_stream_options(monkeypatch, tmp_path):
    seen: list[dict] = []
    _fake_transport(monkeypatch, sse=_SSE_WITH_USAGE, seen_requests=seen)
    _run_main(tmp_path, ["--num-requests", "1", "--warmup", "0"])
    assert all(
        entry["payload"]["stream_options"] == {"include_usage": True} for entry in seen
    )


def test_summary_client_block_and_row_hostname(monkeypatch, tmp_path):
    import socket

    _fake_transport(monkeypatch, sse=_SSE_WITH_USAGE)
    _code, summary, rows = _run_main(tmp_path, ["--num-requests", "1", "--warmup", "0"])
    hostname = socket.gethostname()
    assert summary["schema"] == bench_ollama.SCHEMA_SUMMARY
    assert summary["client"]["hostname"] == hostname
    assert summary["client"]["base_url"] == "http://h:11434"
    assert summary["controls"]["base_url"] == "http://h:11434"
    assert summary["client"]["scheduled_start_local"] is None
    assert all(row["schema"] == bench_ollama.SCHEMA_ROW for row in rows)
    assert all(row["client_hostname"] == hostname for row in rows)
