"""Measure TTFT and end-to-end latency for one streaming request.

Defined timings:

- TTFT (time to first token): from the moment we send the request to the
  arrival of the first streaming chunk that carries non-empty content
  (``delta.content`` is a non-empty string). Chunks that only set ``delta.role``
  are ignored — they are protocol bookkeeping, not generated tokens.
- E2E (end-to-end): from the moment we send the request to the moment the
  stream ends (server sends ``[DONE]`` or closes the connection).
- TPOT (time per output token, decode-only): ``(e2e - ttft) / (completion_tokens - 1)``
  when ``completion_tokens`` is known and >= 2; otherwise ``None``.

Output shape follows the Benchmark Contract (controls + metrics + raw run).
Default output path: ``results/raw/first_ttft.json``.
With --run-id: ``results/runs/<run_id>/singlestream_lite_latency/result.json``.

Usage on the server:

    uv run python -m scripts.measure_ttft_once \
        --base-url http://127.0.0.1:8000 \
        --model meta-llama/Llama-3.1-8B-Instruct \
        --prompt "Say hi in one short sentence." \
        --gpu-model "H200 NVL" \
        --vllm-version 0.6.x
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts._client import (
    CompletionRequest,
    chat_completion_stream,
    extract_stream_delta_text,
    extract_stream_usage,
)
from scripts._metrics import (
    RunControls,
    build_workload_spec,
    get_git_commit,
    make_run_uuid,
    now_iso,
    null_server_metrics,
    resolve_output_path,
)
from scripts._schemas import (
    METHODOLOGY,
    MODE_SINGLESTREAM_LITE_LATENCY,
    SCHEMA_TTFT_ONCE,
)

_SCRIPT_NAME = "measure_ttft_once.py"
_FALLBACK_OUTPUT = "results/raw/first_ttft.json"


@dataclass
class StreamRunResult:
    ttft_seconds: float | None
    e2e_seconds: float
    chunks_received: int
    output_text: str
    completed: bool
    usage: dict[str, Any] | None = field(default=None)


def _now() -> float:
    return time.perf_counter()


def measure_stream(
    chunks: Iterable[dict[str, Any]],
    *,
    start_time: float,
    clock: callable = _now,
) -> StreamRunResult:
    """Walk a stream of chunks, recording TTFT, E2E, and usage if reported.

    ``start_time`` is the wall clock (``perf_counter`` seconds) captured right
    before sending the request. ``clock`` is injectable for tests.

    TTFT is anchored on the first chunk that carries non-empty ``delta.content``.
    Usage is taken from the last chunk that carries a ``usage`` block (vLLM
    emits this when ``stream_options.include_usage`` is set).
    """
    ttft: float | None = None
    chunks_received = 0
    output_parts: list[str] = []
    usage: dict[str, Any] | None = None

    for chunk in chunks:
        chunks_received += 1
        text = extract_stream_delta_text(chunk)
        if text:
            if ttft is None:
                ttft = clock() - start_time
            output_parts.append(text)
        chunk_usage = extract_stream_usage(chunk)
        if chunk_usage is not None:
            usage = chunk_usage

    e2e = clock() - start_time
    # `completed` reflects whether the stream produced any actual content. A
    # role-only stream that ends cleanly is technically a successful HTTP
    # response, but it carries zero generated tokens and so is not a "completed"
    # generation for benchmark purposes. Hard failures during iteration raise
    # and are turned into a failure record by the caller.
    return StreamRunResult(
        ttft_seconds=ttft,
        e2e_seconds=e2e,
        chunks_received=chunks_received,
        output_text="".join(output_parts),
        completed=bool(output_parts),
        usage=usage,
    )


def compute_tpot_seconds(
    *,
    ttft_seconds: float | None,
    e2e_seconds: float | None,
    completion_tokens: int | None,
) -> float | None:
    """Decode-phase time per output token.

    Returns ``None`` when any input is missing or when ``completion_tokens < 2``
    (decode-phase has no inter-token interval to measure with a single output
    token).
    """
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure TTFT + E2E for a single streaming request to vLLM.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", default="Say hi in one short sentence.")
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--output",
        default=None,
        help="Where to write the result JSON. Overrides --run-id path "
             f"(legacy default: {_FALLBACK_OUTPUT}).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier. Sets output to results/runs/<run_id>/"
             f"{MODE_SINGLESTREAM_LITE_LATENCY}/result.json unless --output is also given.",
    )
    parser.add_argument("--dtype", default=None, help="Model dtype, e.g. bfloat16.")
    parser.add_argument("--quantization", default=None)
    parser.add_argument("--gpu-model", default=None, help="e.g. 'H200 NVL'.")
    parser.add_argument("--vllm-version", default=None)
    parser.add_argument("--max-model-len", type=int, default=None)
    parser.add_argument("--max-num-seqs", type=int, default=None)
    parser.add_argument("--max-num-batched-tokens", type=int, default=None)
    parser.add_argument("--workload", default="single-prompt-smoke")
    parser.add_argument("--notes", default=None)
    return parser.parse_args(argv)


def build_record(
    *,
    request: CompletionRequest,
    controls: RunControls,
    result: StreamRunResult,
    error: str | None = None,
) -> dict[str, Any]:
    usage = result.usage or {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")

    tpot_seconds = compute_tpot_seconds(
        ttft_seconds=result.ttft_seconds,
        e2e_seconds=result.e2e_seconds,
        completion_tokens=completion_tokens,
    )
    output_tokens_per_second = compute_output_tokens_per_second(
        e2e_seconds=result.e2e_seconds,
        completion_tokens=completion_tokens,
    )

    return {
        "schema": SCHEMA_TTFT_ONCE,
        "methodology": METHODOLOGY,
        "benchmark_mode": MODE_SINGLESTREAM_LITE_LATENCY,
        "timestamp": now_iso(),
        "controls": controls.as_dict(),
        "request": {
            "prompt": request.prompt,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        },
        "metrics": {
            "ttft_seconds": result.ttft_seconds,
            "e2e_seconds": result.e2e_seconds,
            "tpot_seconds": tpot_seconds,
            "output_tokens_per_second": output_tokens_per_second,
            "chunks_received": result.chunks_received,
            "output_chars": len(result.output_text),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "completed": result.completed,
        },
        "server_metrics": null_server_metrics(),
        "output_text": result.output_text,
        "error": error,
    }


def _failure_result(*, start: float, clock: Any = _now) -> StreamRunResult:
    """Build a StreamRunResult representing a failed/aborted run.

    Used by ``main()`` when ``chat_completion_stream`` or ``measure_stream``
    raises before any content was observed. ``e2e_seconds`` reflects the time
    actually spent before the failure so dashboards can still bucket it.
    """
    return StreamRunResult(
        ttft_seconds=None,
        e2e_seconds=max(0.0, clock() - start),
        chunks_received=0,
        output_text="",
        completed=False,
        usage=None,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    output_path_str = resolve_output_path(
        run_id=args.run_id,
        explicit_path=args.output,
        benchmark_mode=MODE_SINGLESTREAM_LITE_LATENCY,
        filename="result.json",
        fallback=_FALLBACK_OUTPUT,
    )

    request = CompletionRequest(
        base_url=args.base_url,
        model=args.model,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    decoding = {"temperature": args.temperature, "max_tokens": args.max_tokens}
    workload_spec = build_workload_spec(
        name=args.workload,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        decoding=decoding,
        concurrency=1,
        arrival_process="single",
    )
    controls = RunControls(
        model=args.model,
        base_url=args.base_url,
        dtype=args.dtype,
        quantization=args.quantization,
        gpu_model=args.gpu_model,
        vllm_version=args.vllm_version,
        max_model_len=args.max_model_len,
        max_num_seqs=args.max_num_seqs,
        max_num_batched_tokens=args.max_num_batched_tokens,
        decoding=decoding,
        warmup_runs=0,
        measured_runs=1,
        concurrency=1,
        workload=args.workload,
        workload_spec=workload_spec,
        notes=args.notes,
        run_id=args.run_id,
        run_uuid=make_run_uuid(),
        script_name=_SCRIPT_NAME,
        git_commit=get_git_commit(),
    )

    start = _now()
    error: str | None = None
    try:
        stream = chat_completion_stream(request, timeout=args.timeout)
        result = measure_stream(stream, start_time=start)
    except Exception as exc:  # noqa: BLE001 - capture any HTTP/transport/stream failure
        error = f"{type(exc).__name__}: {exc}"
        result = _failure_result(start=start)

    record = build_record(
        request=request, controls=controls, result=result, error=error,
    )

    output_path = Path(output_path_str)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )

    if error is not None:
        print(f"ERROR:  {error}", file=sys.stderr)
        print(f"saved:  {output_path}")
        return 1

    ttft = result.ttft_seconds
    ttft_str = f"{ttft * 1000:.1f} ms" if ttft is not None else "n/a"
    tpot = record["metrics"]["tpot_seconds"]
    tpot_str = f"{tpot * 1000:.2f} ms/tok" if tpot is not None else "n/a"
    print(f"TTFT:   {ttft_str}")
    print(f"E2E:    {result.e2e_seconds * 1000:.1f} ms")
    print(f"TPOT:   {tpot_str}")
    print(f"chunks: {result.chunks_received}")
    print(f"saved:  {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
