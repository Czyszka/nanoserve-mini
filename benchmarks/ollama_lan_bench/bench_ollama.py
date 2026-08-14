# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Standalone sequential LAN benchmark against a remote Ollama server.

Sends N strictly sequential streaming requests to Ollama's OpenAI-compatible
``/v1/chat/completions`` endpoint and records, per request and in aggregate:

- TTFT (time to first token): from the moment the request is sent to the first
  streaming chunk carrying non-empty final-answer text (``delta.content``).
  A separate ``ttft_any_token_seconds`` anchor also counts reasoning-trace
  text (``delta.reasoning`` / ``delta.reasoning_content``).
- E2E (end-to-end latency): request sent -> stream fully drained.
- TPOT (time per output token, decode-only):
  ``(e2e - ttft) / (completion_tokens - 1)``; ``None`` when the server does
  not report usage or ``completion_tokens < 2``.
- Throughput over the measured phase wall clock: requests/s, output chars/s,
  output tokens/s (token-based numbers require the server to report usage).

The run can be scheduled: ``--start-at HH:MM`` waits until the next occurrence
of that local system time (today or tomorrow); a full ISO timestamp
(``YYYY-MM-DDTHH:MM``) is also accepted. Prompts come either from ``--prompt``
(one literal repeated N times) or ``--dataset`` (JSONL with a ``prompt`` key
per line, e.g. the repo's SWE-bench Lite export); ``--dataset-offset`` lets
several client machines take disjoint slices of the same dataset.

This file is intentionally self-contained and **stdlib-only** (no third-party
packages) so it runs on offline clients with any Python 3.12+ — including the
Windows "embeddable package" shipped in the offline kit (see build_kit.py) —
or via ``uv run bench_ollama.py ...`` on a dev machine. HTTP uses
``urllib.request``; note its ``timeout`` bounds each socket operation
(connect / single read), not the whole response. The measurement logic mirrors
``benchmarks/scripts/`` in the nanoserve-mini repo (same metric definitions);
if the methodology changes there, update both places.

Example:

    uv run bench_ollama.py \
        --base-url http://192.168.1.50:11434 \
        --model llama3.3:70b \
        --dataset ./swe_bench_vllm.jsonl --num-requests 10 \
        --start-at 08:30
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_SCRIPT_NAME = "bench_ollama.py"
SCHEMA_SUMMARY = "ollama-lan-bench.v1"
SCHEMA_ROW = "ollama-lan-bench-row.v1"
_DEFAULT_PROMPT = "Say hi in one short sentence."
_MAX_SLEEP_CHUNK_SECONDS = 30.0

# ---------------------------------------------------------------------------
# HTTP client (protocol vendored from benchmarks/scripts/_client.py,
# transport rewritten on stdlib urllib so offline clients need no packages)
# ---------------------------------------------------------------------------


@dataclass
class CompletionRequest:
    """Inputs for a single ``/v1/chat/completions`` call."""

    base_url: str
    model: str
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.0
    api_key: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def normalize_base_url(url: str) -> str:
    """Accept both ``http://host:11434`` and ``http://host:11434/v1``.

    The endpoint builder appends ``/v1/chat/completions`` itself, so a trailing
    ``/v1`` in the user-supplied base URL would otherwise double up.
    """
    trimmed = url.strip().rstrip("/")
    if trimmed.lower().endswith("/v1"):
        trimmed = trimmed[: -len("/v1")].rstrip("/")
    return trimmed


def build_payload(req: CompletionRequest, *, stream: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": req.model,
        "messages": [{"role": "user", "content": req.prompt}],
        "max_tokens": req.max_tokens,
        "temperature": req.temperature,
        "stream": stream,
    }
    if req.extra:
        payload.update(req.extra)
    return payload


def _endpoint(base_url: str) -> str:
    return base_url.rstrip("/") + "/v1/chat/completions"


def _headers(req: CompletionRequest) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if req.api_key is not None:
        headers["Authorization"] = f"Bearer {req.api_key}"
    return headers


def post_stream(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> Iterator[str]:
    """POST JSON and yield decoded response lines (stdlib urllib transport).

    ``urllib.error.HTTPError`` (4xx/5xx), ``URLError`` and ``TimeoutError``
    propagate to the caller. ``timeout`` bounds each socket operation, not the
    whole response.
    """
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw_line in response:
            yield raw_line.decode("utf-8", errors="replace")


def chat_completion_stream(
    req: CompletionRequest,
    *,
    timeout: float = 300.0,
    include_usage: bool = True,
    transport: Callable[[str, dict[str, Any], dict[str, str], float], Iterator[str]]
    | None = None,
) -> Iterator[dict[str, Any]]:
    """Streaming call. Yields each parsed SSE chunk; ``[DONE]`` is not yielded.

    With ``include_usage`` (default) the request carries
    ``stream_options.include_usage = true`` so a modern Ollama emits a final
    chunk with a populated ``usage`` block. Older Ollama versions ignore the
    field — callers must tolerate ``usage`` never arriving. ``transport`` is
    resolved at call time (module-level ``post_stream`` by default) so tests
    can substitute a canned stream.
    """
    payload = build_payload(req, stream=True)
    if include_usage and "stream_options" not in payload:
        payload["stream_options"] = {"include_usage": True}
    url = _endpoint(req.base_url)
    if transport is None:
        transport = post_stream
    for raw_line in transport(url, payload, _headers(req), timeout):
        line = raw_line.strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            return
        yield json.loads(data)


def extract_stream_delta_text(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    return content if isinstance(content, str) else ""


_REASONING_DELTA_FIELDS = ("reasoning_content", "reasoning")


def extract_stream_reasoning_text(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    for field_name in _REASONING_DELTA_FIELDS:
        value = delta.get(field_name)
        if isinstance(value, str) and value:
            return value
    return ""


def extract_stream_usage(chunk: dict[str, Any]) -> dict[str, Any] | None:
    usage = chunk.get("usage")
    return usage if isinstance(usage, dict) else None


# ---------------------------------------------------------------------------
# Stream measurement (vendored from benchmarks/scripts/measure_ttft_once.py)
# ---------------------------------------------------------------------------


@dataclass
class StreamRunResult:
    ttft_seconds: float | None
    e2e_seconds: float
    chunks_received: int
    output_text: str
    completed: bool
    usage: dict[str, Any] | None = field(default=None)
    ttft_any_token_seconds: float | None = field(default=None)
    reasoning_chars: int = field(default=0)


def _now() -> float:
    return time.perf_counter()


def measure_stream(
    chunks: Iterable[dict[str, Any]],
    *,
    start_time: float,
    clock: Callable[[], float] = _now,
) -> StreamRunResult:
    """Walk a stream of chunks, recording TTFT, E2E, and usage if reported."""
    ttft: float | None = None
    ttft_any: float | None = None
    reasoning_chars = 0
    chunks_received = 0
    output_parts: list[str] = []
    usage: dict[str, Any] | None = None

    for chunk in chunks:
        chunks_received += 1
        text = extract_stream_delta_text(chunk)
        reasoning = extract_stream_reasoning_text(chunk)
        if reasoning:
            reasoning_chars += len(reasoning)
        # Take one timestamp for this chunk only if it advances an anchor.
        if (text or reasoning) and (ttft_any is None or (text and ttft is None)):
            stamp = clock() - start_time
            if ttft_any is None:
                ttft_any = stamp
            if text and ttft is None:
                ttft = stamp
        if text:
            output_parts.append(text)
        chunk_usage = extract_stream_usage(chunk)
        if chunk_usage is not None:
            usage = chunk_usage

    e2e = clock() - start_time
    return StreamRunResult(
        ttft_seconds=ttft,
        e2e_seconds=e2e,
        chunks_received=chunks_received,
        output_text="".join(output_parts),
        completed=bool(output_parts) or reasoning_chars > 0,
        usage=usage,
        ttft_any_token_seconds=ttft_any,
        reasoning_chars=reasoning_chars,
    )


def compute_tpot_seconds(
    *,
    ttft_seconds: float | None,
    e2e_seconds: float | None,
    completion_tokens: int | None,
) -> float | None:
    if ttft_seconds is None or e2e_seconds is None or completion_tokens is None:
        return None
    if completion_tokens < 2:
        return None
    decode_seconds = e2e_seconds - ttft_seconds
    if decode_seconds <= 0:
        return None
    return decode_seconds / (completion_tokens - 1)


def compute_output_tokens_per_second(
    *,
    e2e_seconds: float | None,
    completion_tokens: int | None,
) -> float | None:
    if e2e_seconds is None or completion_tokens is None or e2e_seconds <= 0:
        return None
    return completion_tokens / e2e_seconds


# ---------------------------------------------------------------------------
# Statistics (vendored from benchmarks/scripts/_metrics.py)
# ---------------------------------------------------------------------------


def percentile(values: list[float], p: float) -> float | None:
    """Plain linear-interpolated percentile; ``None`` for empty input."""
    if not values:
        return None
    if not 0.0 <= p <= 100.0:
        raise ValueError("p must be in [0, 100]")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (p / 100.0) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize(values: list[float]) -> dict[str, float | int | None]:
    """Summary block: count, min, p50, p95, max, mean; ``None`` never NaN."""
    if not values:
        return {"count": 0, "min": None, "p50": None, "p95": None, "max": None, "mean": None}
    return {
        "count": len(values),
        "min": min(values),
        "p50": percentile(values, 50.0),
        "p95": percentile(values, 95.0),
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

_HHMM_RE = re.compile(r"\d{1,2}:\d{2}")


def parse_start_at(value: str, *, now: datetime) -> datetime:
    """Parse ``--start-at`` into a local naive datetime.

    ``HH:MM`` means the next occurrence of that wall-clock time: today if it is
    still ahead, otherwise tomorrow. A full ISO timestamp (``YYYY-MM-DDTHH:MM``)
    is taken verbatim — a past ISO timestamp means "start immediately".
    """
    if _HHMM_RE.fullmatch(value):
        try:
            parsed = datetime.strptime(value, "%H:%M")
        except ValueError:
            raise ValueError(f"--start-at {value!r}: invalid time of day") from None
        target = now.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"--start-at {value!r}: expected HH:MM or ISO format YYYY-MM-DDTHH:MM"
        ) from None


def wait_until(
    target: datetime,
    *,
    clock: Callable[[], datetime] = datetime.now,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> None:
    """Sleep in short chunks until the system clock reaches ``target``.

    The clock is re-read every iteration so suspend/resume and clock drift are
    self-correcting; progress is logged at most every chunk.
    """
    while True:
        remaining = (target - clock()).total_seconds()
        if remaining <= 0:
            return
        log(f"waiting {remaining:.0f}s until {target.isoformat(timespec='seconds')}")
        sleep(min(remaining, _MAX_SLEEP_CHUNK_SECONDS))


# ---------------------------------------------------------------------------
# Prompt sources
# ---------------------------------------------------------------------------


def load_prompts(path: Path, *, offset: int, count: int) -> list[str]:
    """Read ``count`` prompts from a JSONL file starting at ``offset``.

    Each non-blank line must be a JSON object with a non-empty string
    ``prompt`` key. Raises ``ValueError`` when the file cannot supply
    ``offset + count`` prompts — cycling would silently duplicate prompts,
    which changes server-side caching behaviour and skews latency stats.
    """
    prompts: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON ({exc})") from None
            prompt = row.get("prompt") if isinstance(row, dict) else None
            if not isinstance(prompt, str) or not prompt:
                raise ValueError(f"{path}:{line_number}: missing non-empty 'prompt' key")
            prompts.append(prompt)
            if len(prompts) >= offset + count:
                break
    if len(prompts) < offset + count:
        raise ValueError(
            f"{path}: dataset has {len(prompts)} usable prompts, "
            f"need offset {offset} + count {count} = {offset + count}; "
            "lower --num-requests or --dataset-offset"
        )
    return prompts[offset : offset + count]


# ---------------------------------------------------------------------------
# Benchmark loop
# ---------------------------------------------------------------------------


@dataclass
class RunRow:
    index: int
    phase: str  # "warmup" | "measured"
    timestamp: str
    prompt_index: int
    prompt_chars: int
    ttft_seconds: float | None
    ttft_any_token_seconds: float | None
    e2e_seconds: float | None
    tpot_seconds: float | None
    chunks_received: int
    output_chars: int
    prompt_tokens: int | None
    completion_tokens: int | None
    output_tokens_per_second: float | None
    error: str | None


def execute_one(
    request: CompletionRequest,
    *,
    timeout: float,
    include_usage: bool,
    clock: Callable[[], float] = _now,
) -> StreamRunResult:
    start = clock()
    stream = chat_completion_stream(request, timeout=timeout, include_usage=include_usage)
    return measure_stream(stream, start_time=start, clock=clock)


def _usage_int(usage: dict[str, Any] | None, key: str) -> int | None:
    if usage is None:
        return None
    value = usage.get(key)
    return value if isinstance(value, int) else None


def run_prompts(
    indexed_prompts: list[tuple[int, str]],
    *,
    phase: str,
    base_request: CompletionRequest,
    timeout: float,
    include_usage: bool,
    log: Callable[[str], None] = print,
) -> list[RunRow]:
    """Send prompts strictly sequentially; a failed request becomes an error row.

    Sequentiality is inherent: each stream is fully drained by
    ``measure_stream`` before the next request is built. One bad request never
    kills the run — it is recorded with ``error=`` and the loop continues.
    """
    tag = "W" if phase == "warmup" else "M"
    rows: list[RunRow] = []
    for i, (prompt_index, prompt) in enumerate(indexed_prompts):
        request = replace(base_request, prompt=prompt)
        timestamp = now_iso()
        try:
            result = execute_one(request, timeout=timeout, include_usage=include_usage)
        except Exception as exc:  # noqa: BLE001 — any failure becomes a row
            log(f"[{tag}{i}] ERROR {type(exc).__name__}: {exc}")
            rows.append(
                RunRow(
                    index=i,
                    phase=phase,
                    timestamp=timestamp,
                    prompt_index=prompt_index,
                    prompt_chars=len(prompt),
                    ttft_seconds=None,
                    ttft_any_token_seconds=None,
                    e2e_seconds=None,
                    tpot_seconds=None,
                    chunks_received=0,
                    output_chars=0,
                    prompt_tokens=None,
                    completion_tokens=None,
                    output_tokens_per_second=None,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        completion_tokens = _usage_int(result.usage, "completion_tokens")
        tpot = compute_tpot_seconds(
            ttft_seconds=result.ttft_seconds,
            e2e_seconds=result.e2e_seconds,
            completion_tokens=completion_tokens,
        )
        tokens_per_second = compute_output_tokens_per_second(
            e2e_seconds=result.e2e_seconds,
            completion_tokens=completion_tokens,
        )
        row = RunRow(
            index=i,
            phase=phase,
            timestamp=timestamp,
            prompt_index=prompt_index,
            prompt_chars=len(prompt),
            ttft_seconds=result.ttft_seconds,
            ttft_any_token_seconds=result.ttft_any_token_seconds,
            e2e_seconds=result.e2e_seconds,
            tpot_seconds=tpot,
            chunks_received=result.chunks_received,
            output_chars=len(result.output_text),
            prompt_tokens=_usage_int(result.usage, "prompt_tokens"),
            completion_tokens=completion_tokens,
            output_tokens_per_second=tokens_per_second,
            error=None,
        )
        rows.append(row)
        ttft_txt = f"{row.ttft_seconds:.3f}s" if row.ttft_seconds is not None else "-"
        tps_txt = (
            f"{row.output_tokens_per_second:.1f}"
            if row.output_tokens_per_second is not None
            else "-"
        )
        log(f"[{tag}{i}] TTFT={ttft_txt} E2E={row.e2e_seconds:.3f}s tok/s={tps_txt}")
    return rows


# ---------------------------------------------------------------------------
# Output artifacts
# ---------------------------------------------------------------------------


def _row_as_dict(row: RunRow, *, client_hostname: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA_ROW,
        "client_hostname": client_hostname,
        "index": row.index,
        "phase": row.phase,
        "timestamp": row.timestamp,
        "prompt_index": row.prompt_index,
        "prompt_chars": row.prompt_chars,
        "ttft_seconds": row.ttft_seconds,
        "ttft_any_token_seconds": row.ttft_any_token_seconds,
        "e2e_seconds": row.e2e_seconds,
        "tpot_seconds": row.tpot_seconds,
        "chunks_received": row.chunks_received,
        "output_chars": row.output_chars,
        "prompt_tokens": row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "output_tokens_per_second": row.output_tokens_per_second,
        "error": row.error,
    }


def write_jsonl(path: Path, rows: list[RunRow], *, client_hostname: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(_row_as_dict(row, client_hostname=client_hostname), allow_nan=False)
            )
            handle.write("\n")


def build_summary(
    *,
    controls: dict[str, Any],
    client: dict[str, Any],
    rows: list[RunRow],
    measured_wall_clock_seconds: float | None,
) -> dict[str, Any]:
    """Aggregate measured, error-free rows; throughput over measured wall clock."""
    measured = [row for row in rows if row.phase == "measured"]
    ok = [row for row in measured if row.error is None]

    def _values(getter: Callable[[RunRow], float | int | None]) -> list[float]:
        return [float(v) for row in ok if (v := getter(row)) is not None]

    total_output_chars = sum(row.output_chars for row in ok)
    known_completion_tokens = [
        row.completion_tokens for row in ok if row.completion_tokens is not None
    ]
    total_completion_tokens = sum(known_completion_tokens) if known_completion_tokens else None

    wall = measured_wall_clock_seconds
    throughput: dict[str, Any] = {
        "measured_wall_clock_seconds": wall,
        "request_throughput": (len(ok) / wall) if wall and wall > 0 else None,
        "output_chars_per_second": (total_output_chars / wall) if wall and wall > 0 else None,
        "output_tokens_per_second": (
            total_completion_tokens / wall
            if wall and wall > 0 and total_completion_tokens is not None
            else None
        ),
    }
    return {
        "schema": SCHEMA_SUMMARY,
        "controls": controls,
        "client": client,
        "requests": {
            "warmup": sum(1 for row in rows if row.phase == "warmup"),
            "measured": len(measured),
            "measured_ok": len(ok),
            "measured_errors": len(measured) - len(ok),
        },
        "metrics": {
            "ttft_seconds": summarize(_values(lambda r: r.ttft_seconds)),
            "e2e_seconds": summarize(_values(lambda r: r.e2e_seconds)),
            "tpot_seconds": summarize(_values(lambda r: r.tpot_seconds)),
            "prompt_tokens": summarize(_values(lambda r: r.prompt_tokens)),
            "completion_tokens": summarize(_values(lambda r: r.completion_tokens)),
        },
        "throughput": throughput,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sequential streaming benchmark against a remote Ollama server "
        "(OpenAI-compatible /v1/chat/completions).",
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Ollama endpoint, e.g. http://192.168.1.50:11434 "
        "(a trailing /v1 is accepted and stripped).",
    )
    parser.add_argument("--model", required=True, help="Model tag as known to Ollama.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--prompt",
        default=None,
        help=f"Literal prompt repeated for every request (default: {_DEFAULT_PROMPT!r}).",
    )
    source.add_argument(
        "--dataset",
        default=None,
        help="Path to a JSONL file with one {'prompt': ...} object per line.",
    )
    parser.add_argument(
        "--dataset-offset",
        type=int,
        default=0,
        help="Skip this many dataset prompts first — lets several clients take "
        "disjoint slices of the same dataset (default: 0).",
    )
    parser.add_argument(
        "--num-requests",
        type=int,
        default=5,
        help="Number of measured sequential requests (default: 5).",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warm-up requests before measurement; absorbs Ollama model load "
        "into VRAM after idleness (default: 1).",
    )
    parser.add_argument(
        "--start-at",
        default=None,
        help="Scheduled start: HH:MM (next occurrence, local system time) or "
        "ISO YYYY-MM-DDTHH:MM. Omit to start immediately.",
    )
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Per-request HTTP timeout in seconds (default: 300).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Bearer token; not needed for plain Ollama, kept for proxies.",
    )
    parser.add_argument(
        "--no-include-usage",
        action="store_true",
        help="Do not send stream_options.include_usage (escape hatch for "
        "Ollama versions that reject it; token metrics become null).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run label; defaults to the local start timestamp.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Where to write results.jsonl + summary.json "
        "(default: ./results/<run-id>/).",
    )
    parser.add_argument("--notes", default=None, help="Free-form note stored in controls.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.num_requests < 1:
        print("--num-requests must be >= 1", file=sys.stderr)
        return 2
    if args.warmup < 0:
        print("--warmup must be >= 0", file=sys.stderr)
        return 2
    if args.dataset_offset < 0:
        print("--dataset-offset must be >= 0", file=sys.stderr)
        return 2

    base_url = normalize_base_url(args.base_url)
    include_usage = not args.no_include_usage

    if args.dataset is not None:
        try:
            prompts = load_prompts(
                Path(args.dataset), offset=args.dataset_offset, count=args.num_requests
            )
        except (OSError, ValueError) as exc:
            print(f"failed to load dataset: {exc}", file=sys.stderr)
            return 2
        indexed_prompts = list(enumerate(prompts, start=args.dataset_offset))
        prompt_source = "dataset_jsonl"
    else:
        prompt = args.prompt if args.prompt is not None else _DEFAULT_PROMPT
        indexed_prompts = [(0, prompt)] * args.num_requests
        prompt_source = "literal"

    scheduled_start: datetime | None = None
    if args.start_at is not None:
        try:
            scheduled_start = parse_start_at(args.start_at, now=datetime.now())
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"scheduled start: {scheduled_start.isoformat(timespec='seconds')}")
        wait_until(scheduled_start)

    actual_start_local = datetime.now()
    run_id = args.run_id or actual_start_local.strftime("%Y-%m-%d_%H%M%S")
    output_dir = Path(args.output_dir) if args.output_dir else Path("results") / run_id
    hostname = socket.gethostname()

    controls: dict[str, Any] = {
        "run_id": run_id,
        "run_uuid": uuid.uuid4().hex,
        "script_name": _SCRIPT_NAME,
        "model": args.model,
        "base_url": base_url,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "timeout_seconds": args.timeout,
        "warmup_runs": args.warmup,
        "measured_runs": args.num_requests,
        "concurrency": 1,
        "arrival_process": "sequential",
        "include_usage": include_usage,
        "notes": args.notes,
    }
    client_info: dict[str, Any] = {
        "hostname": hostname,
        "base_url": base_url,
        # scheduled_start is local wall-clock time (what --start-at means);
        # actual_start_utc is UTC for cross-client comparability.
        "scheduled_start_local": (
            scheduled_start.isoformat(timespec="seconds") if scheduled_start else None
        ),
        "actual_start_local": actual_start_local.isoformat(timespec="seconds"),
        "actual_start_utc": now_iso(),
        "start_delay_seconds": (
            (actual_start_local - scheduled_start).total_seconds() if scheduled_start else None
        ),
        "dataset_path": args.dataset,
        "dataset_offset": args.dataset_offset if args.dataset is not None else None,
        "prompt_source": prompt_source,
    }

    base_request = CompletionRequest(
        base_url=base_url,
        model=args.model,
        prompt="",
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        api_key=args.api_key,
    )

    print(f"target: {base_url} model={args.model} host={hostname}")
    warmup_prompts = [indexed_prompts[0]] * args.warmup
    rows = run_prompts(
        warmup_prompts,
        phase="warmup",
        base_request=base_request,
        timeout=args.timeout,
        include_usage=include_usage,
    )

    measured_wall_start = time.perf_counter()
    rows += run_prompts(
        indexed_prompts,
        phase="measured",
        base_request=base_request,
        timeout=args.timeout,
        include_usage=include_usage,
    )
    measured_wall_clock = time.perf_counter() - measured_wall_start

    summary = build_summary(
        controls=controls,
        client=client_info,
        rows=rows,
        measured_wall_clock_seconds=measured_wall_clock,
    )
    jsonl_path = output_dir / "results.jsonl"
    summary_path = output_dir / "summary.json"
    write_jsonl(jsonl_path, rows, client_hostname=hostname)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )

    metrics = summary["metrics"]
    throughput = summary["throughput"]

    def _fmt(block: dict[str, Any], key: str) -> str:
        value = block[key]
        return f"{value:.3f}" if isinstance(value, float) else "-"

    print(f"wrote {jsonl_path} and {summary_path}")
    for name in ("ttft_seconds", "e2e_seconds", "tpot_seconds"):
        block = metrics[name]
        print(f"{name}: p50={_fmt(block, 'p50')} p95={_fmt(block, 'p95')} n={block['count']}")
    rps = throughput["request_throughput"]
    tps = throughput["output_tokens_per_second"]
    print(
        f"throughput: {rps:.3f} req/s" + (f", {tps:.1f} tok/s" if tps is not None else "")
        if rps is not None
        else "throughput: - (no successful measured requests)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
