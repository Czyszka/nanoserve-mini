"""Measure TTFT and end-to-end latency for one streaming request.

Defined timings:

- TTFT (time to first token): from the moment we send the request to the
  arrival of the first streaming chunk that carries non-empty content
  (``delta.content`` is a non-empty string). Chunks that only set ``delta.role``
  are ignored — they are protocol bookkeeping, not generated tokens.
- E2E (end-to-end): from the moment we send the request to the moment the
  stream ends (server sends ``[DONE]`` or closes the connection).

Output shape follows the Benchmark Contract (controls + metrics + raw run).
Default output path: ``results/raw/first_ttft.json``.

Usage on the server:

    uv run python scripts/measure_ttft_once.py \
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts._client import (
    CompletionRequest,
    chat_completion_stream,
    extract_stream_delta_text,
)
from scripts._metrics import RunControls, now_iso


@dataclass
class StreamRunResult:
    ttft_seconds: float | None
    e2e_seconds: float
    chunks_received: int
    output_text: str
    completed: bool


def _now() -> float:
    return time.perf_counter()


def measure_stream(
    chunks: Iterable[dict[str, Any]],
    *,
    start_time: float,
    clock: callable = _now,
) -> StreamRunResult:
    """Walk a stream of chunks, recording TTFT and E2E.

    ``start_time`` is the wall clock (``perf_counter`` seconds) captured right
    before sending the request. ``clock`` is injectable for tests.

    TTFT is anchored on the first chunk that carries non-empty ``delta.content``.
    """
    ttft: float | None = None
    chunks_received = 0
    output_parts: list[str] = []

    for chunk in chunks:
        chunks_received += 1
        text = extract_stream_delta_text(chunk)
        if text:
            if ttft is None:
                ttft = clock() - start_time
            output_parts.append(text)

    e2e = clock() - start_time
    return StreamRunResult(
        ttft_seconds=ttft,
        e2e_seconds=e2e,
        chunks_received=chunks_received,
        output_text="".join(output_parts),
        completed=True,
    )


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
        default="results/raw/first_ttft.json",
        help="Where to write the result JSON (default: %(default)s).",
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
) -> dict[str, Any]:
    return {
        "schema": "nanoserve-mini.ttft-once.v1",
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
            "chunks_received": result.chunks_received,
            "output_chars": len(result.output_text),
            "completed": result.completed,
        },
        "output_text": result.output_text,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    request = CompletionRequest(
        base_url=args.base_url,
        model=args.model,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
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
        decoding={"temperature": args.temperature, "max_tokens": args.max_tokens},
        warmup_runs=0,
        measured_runs=1,
        workload=args.workload,
        notes=args.notes,
    )

    start = _now()
    stream = chat_completion_stream(request, timeout=args.timeout)
    result = measure_stream(stream, start_time=start)

    record = build_record(request=request, controls=controls, result=result)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    ttft = result.ttft_seconds
    ttft_str = f"{ttft * 1000:.1f} ms" if ttft is not None else "n/a"
    print(f"TTFT:   {ttft_str}")
    print(f"E2E:    {result.e2e_seconds * 1000:.1f} ms")
    print(f"chunks: {result.chunks_received}")
    print(f"saved:  {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
