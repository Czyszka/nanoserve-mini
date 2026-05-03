"""Run N sequential streaming requests against a vLLM server and summarize.

This is the minimal version of the benchmark harness:
- one prompt, repeated,
- no concurrency,
- no workload matrix,
- no metrics scraping from /metrics.

What it does:
- ``--warmup`` runs are executed and discarded (their results are still recorded
  in the JSONL with ``"phase": "warmup"`` for traceability).
- ``--runs`` runs are executed and feed the summary.
- Every run produces one JSONL line in ``--output-jsonl``.
- A summary JSON is written to ``--output-summary`` with controls + p50/p95/min/
  max/mean for TTFT and E2E.

The output shape follows the same Benchmark Contract style as
``scripts/measure_ttft_once.py`` so we can later aggregate across files.

Usage on the server:

    uv run python -m scripts.run_sequential_benchmark \
        --base-url http://127.0.0.1:8000 \
        --model meta-llama/Llama-3.1-8B-Instruct \
        --warmup 1 --runs 5 \
        --gpu-model "H200 NVL" --vllm-version 0.6.x
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts._client import CompletionRequest, chat_completion_stream
from scripts._metrics import RunControls, now_iso, summarize
from scripts.measure_ttft_once import StreamRunResult, measure_stream


@dataclass
class RunRow:
    index: int
    phase: str  # "warmup" | "measured"
    timestamp: str
    ttft_seconds: float | None
    e2e_seconds: float | None
    chunks_received: int
    output_chars: int
    error: str | None


def _now() -> float:
    return time.perf_counter()


def execute_run(
    request: CompletionRequest,
    *,
    timeout: float,
    clock: Any = _now,
) -> StreamRunResult:
    start = clock()
    stream = chat_completion_stream(request, timeout=timeout)
    return measure_stream(stream, start_time=start, clock=clock)


def run_sequential(
    request: CompletionRequest,
    *,
    warmup: int,
    runs: int,
    timeout: float,
    on_run: Any = None,
) -> list[RunRow]:
    """Run warmup + measured runs sequentially. Returns one row per run.

    On error, the row records ``error`` with ``ttft_seconds=None`` and
    ``e2e_seconds=None`` (kept out of the summary aggregates and JSON-strict).
    We continue to the next run — one bad request shouldn't kill a 5-run
    smoke benchmark.
    """
    rows: list[RunRow] = []

    plan: list[tuple[int, str]] = []
    for i in range(warmup):
        plan.append((i, "warmup"))
    for i in range(runs):
        plan.append((i, "measured"))

    for index, phase in plan:
        ts = now_iso()
        try:
            result = execute_run(request, timeout=timeout)
            row = RunRow(
                index=index,
                phase=phase,
                timestamp=ts,
                ttft_seconds=result.ttft_seconds,
                e2e_seconds=result.e2e_seconds,
                chunks_received=result.chunks_received,
                output_chars=len(result.output_text),
                error=None,
            )
        except Exception as exc:  # noqa: BLE001 - we want any failure to be a row
            row = RunRow(
                index=index,
                phase=phase,
                timestamp=ts,
                ttft_seconds=None,
                e2e_seconds=None,
                chunks_received=0,
                output_chars=0,
                error=f"{type(exc).__name__}: {exc}",
            )

        rows.append(row)
        if on_run is not None:
            on_run(row)

    return rows


def write_jsonl(path: Path, rows: list[RunRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            # allow_nan=False makes any future regression that tries to write
            # NaN/Infinity raise here instead of silently producing invalid JSON.
            fh.write(
                json.dumps(_row_as_dict(row), ensure_ascii=False, allow_nan=False) + "\n"
            )


def _row_as_dict(row: RunRow) -> dict[str, Any]:
    return {
        "index": row.index,
        "phase": row.phase,
        "timestamp": row.timestamp,
        "ttft_seconds": row.ttft_seconds,
        "e2e_seconds": row.e2e_seconds,
        "chunks_received": row.chunks_received,
        "output_chars": row.output_chars,
        "error": row.error,
    }


def build_summary(
    *,
    request: CompletionRequest,
    controls: RunControls,
    rows: list[RunRow],
) -> dict[str, Any]:
    measured = [r for r in rows if r.phase == "measured" and r.error is None]
    ttfts = [r.ttft_seconds for r in measured if r.ttft_seconds is not None]
    e2es = [r.e2e_seconds for r in measured if r.e2e_seconds is not None]

    error_count = sum(1 for r in rows if r.phase == "measured" and r.error is not None)

    return {
        "schema": "nanoserve-mini.sequential-bench.v1",
        "timestamp": now_iso(),
        "controls": controls.as_dict(),
        "request": {
            "prompt": request.prompt,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        },
        "summary": {
            "measured_runs": len(measured),
            "errors": error_count,
            "ttft_seconds": summarize(ttfts),
            "e2e_seconds": summarize(e2es),
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run N sequential streaming requests and summarize TTFT / E2E.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", default="Say hi in one short sentence.")
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument(
        "--output-jsonl",
        default="results/raw/sequential_bench.jsonl",
    )
    parser.add_argument(
        "--output-summary",
        default="results/raw/sequential_bench_summary.json",
    )
    parser.add_argument("--dtype", default=None)
    parser.add_argument("--quantization", default=None)
    parser.add_argument("--gpu-model", default=None)
    parser.add_argument("--vllm-version", default=None)
    parser.add_argument("--max-model-len", type=int, default=None)
    parser.add_argument("--max-num-seqs", type=int, default=None)
    parser.add_argument("--max-num-batched-tokens", type=int, default=None)
    parser.add_argument("--workload", default="single-prompt-sequential")
    parser.add_argument("--notes", default=None)
    return parser.parse_args(argv)


def _format_ms(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 1000:.1f} ms"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.runs < 1:
        print("--runs must be >= 1", file=sys.stderr)
        return 2

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
        warmup_runs=args.warmup,
        measured_runs=args.runs,
        workload=args.workload,
        notes=args.notes,
    )

    def progress(row: RunRow) -> None:
        ttft_str = _format_ms(row.ttft_seconds)
        e2e_str = _format_ms(row.e2e_seconds)
        marker = "W" if row.phase == "warmup" else "M"
        err = f" ERROR={row.error}" if row.error else ""
        print(f"[{marker}{row.index}] TTFT={ttft_str:>10}  E2E={e2e_str:>10}{err}")

    rows = run_sequential(
        request,
        warmup=args.warmup,
        runs=args.runs,
        timeout=args.timeout,
        on_run=progress,
    )

    jsonl_path = Path(args.output_jsonl)
    summary_path = Path(args.output_summary)
    write_jsonl(jsonl_path, rows)
    summary = build_summary(request=request, controls=controls, rows=rows)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )

    s = summary["summary"]
    ttft = s["ttft_seconds"]
    e2e = s["e2e_seconds"]
    print("---")
    print(f"measured runs: {s['measured_runs']}  errors: {s['errors']}")
    print(f"TTFT  p50={_format_ms(ttft['p50'])}  p95={_format_ms(ttft['p95'])}  "
          f"min={_format_ms(ttft['min'])}  max={_format_ms(ttft['max'])}")
    print(f"E2E   p50={_format_ms(e2e['p50'])}  p95={_format_ms(e2e['p95'])}  "
          f"min={_format_ms(e2e['min'])}  max={_format_ms(e2e['max'])}")
    print(f"jsonl:   {jsonl_path}")
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
