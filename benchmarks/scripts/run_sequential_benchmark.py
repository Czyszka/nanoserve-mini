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
  max/mean for TTFT, E2E, TPOT, and per-request input/output tokens.

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
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmarks.scripts._client import CompletionRequest, chat_completion_stream
from benchmarks.scripts._metrics import (
    RunControls,
    build_workload_spec,
    get_git_commit,
    make_run_uuid,
    now_iso,
    null_server_metrics,
    resolve_output_path,
    summarize,
)
from benchmarks.scripts._schemas import (
    METHODOLOGY,
    MODE_SINGLESTREAM_LITE_REPEATED,
    SCHEMA_SEQUENTIAL_BENCH,
    SCHEMA_SEQUENTIAL_BENCH_ROW,
)
from benchmarks.scripts.measure_ttft_once import (
    StreamRunResult,
    compute_output_tokens_per_second,
    compute_tpot_seconds,
    measure_stream,
)

_SCRIPT_NAME = "run_sequential_benchmark.py"
_FALLBACK_JSONL = "results/raw/sequential_bench.jsonl"
_FALLBACK_SUMMARY = "results/raw/sequential_bench_summary.json"


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
    # Token-level fields (v3 schema). Defaulted so callers that only know about
    # latency fields can still construct a valid row.
    tpot_seconds: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    output_tokens_per_second: float | None = None


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


def _row_from_result(
    *,
    index: int,
    phase: str,
    timestamp: str,
    result: StreamRunResult,
) -> RunRow:
    usage = result.usage or {}
    completion_tokens = usage.get("completion_tokens")
    prompt_tokens = usage.get("prompt_tokens")
    tpot = compute_tpot_seconds(
        ttft_seconds=result.ttft_seconds,
        e2e_seconds=result.e2e_seconds,
        completion_tokens=completion_tokens,
    )
    output_tps = compute_output_tokens_per_second(
        e2e_seconds=result.e2e_seconds,
        completion_tokens=completion_tokens,
    )
    return RunRow(
        index=index,
        phase=phase,
        timestamp=timestamp,
        ttft_seconds=result.ttft_seconds,
        e2e_seconds=result.e2e_seconds,
        tpot_seconds=tpot,
        chunks_received=result.chunks_received,
        output_chars=len(result.output_text),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        output_tokens_per_second=output_tps,
        error=None,
    )


def _row_from_error(
    *,
    index: int,
    phase: str,
    timestamp: str,
    error: str,
) -> RunRow:
    return RunRow(
        index=index,
        phase=phase,
        timestamp=timestamp,
        ttft_seconds=None,
        e2e_seconds=None,
        tpot_seconds=None,
        chunks_received=0,
        output_chars=0,
        prompt_tokens=None,
        completion_tokens=None,
        output_tokens_per_second=None,
        error=error,
    )


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
            row = _row_from_result(
                index=index, phase=phase, timestamp=ts, result=result,
            )
        except Exception as exc:  # noqa: BLE001 - we want any failure to be a row
            row = _row_from_error(
                index=index,
                phase=phase,
                timestamp=ts,
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
        "schema": SCHEMA_SEQUENTIAL_BENCH_ROW,
        "methodology": METHODOLOGY,
        "benchmark_mode": MODE_SINGLESTREAM_LITE_REPEATED,
        "index": row.index,
        "phase": row.phase,
        "timestamp": row.timestamp,
        "ttft_seconds": row.ttft_seconds,
        "e2e_seconds": row.e2e_seconds,
        "tpot_seconds": row.tpot_seconds,
        "chunks_received": row.chunks_received,
        "output_chars": row.output_chars,
        "prompt_tokens": row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "output_tokens_per_second": row.output_tokens_per_second,
        "error": row.error,
    }


def build_summary(
    *,
    request: CompletionRequest,
    controls: RunControls,
    rows: list[RunRow],
    measured_wall_clock_seconds: float | None = None,
) -> dict[str, Any]:
    measured = [r for r in rows if r.phase == "measured" and r.error is None]
    ttfts = [r.ttft_seconds for r in measured if r.ttft_seconds is not None]
    e2es = [r.e2e_seconds for r in measured if r.e2e_seconds is not None]
    tpots = [r.tpot_seconds for r in measured if r.tpot_seconds is not None]
    prompt_token_counts = [
        float(r.prompt_tokens) for r in measured if r.prompt_tokens is not None
    ]
    completion_token_counts = [
        float(r.completion_tokens) for r in measured if r.completion_tokens is not None
    ]

    error_count = sum(1 for r in rows if r.phase == "measured" and r.error is not None)

    total_output_chars = sum(r.output_chars for r in measured)
    total_output_tokens = sum(
        r.completion_tokens or 0 for r in measured if r.completion_tokens is not None
    )

    throughput: dict[str, Any] = {}
    if measured_wall_clock_seconds is not None and measured_wall_clock_seconds > 0:
        n_ok = len(measured)
        throughput["measured_wall_clock_seconds"] = measured_wall_clock_seconds
        throughput["request_throughput"] = (
            n_ok / measured_wall_clock_seconds if n_ok > 0 else None
        )
        throughput["output_chars_per_second"] = (
            total_output_chars / measured_wall_clock_seconds
            if total_output_chars > 0 else None
        )
        throughput["output_tokens_per_second"] = (
            total_output_tokens / measured_wall_clock_seconds
            if total_output_tokens > 0 else None
        )
    else:
        throughput["measured_wall_clock_seconds"] = None
        throughput["request_throughput"] = None
        throughput["output_chars_per_second"] = None
        throughput["output_tokens_per_second"] = None

    return {
        "schema": SCHEMA_SEQUENTIAL_BENCH,
        "methodology": METHODOLOGY,
        "benchmark_mode": MODE_SINGLESTREAM_LITE_REPEATED,
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
            "tpot_seconds": summarize(tpots),
            "prompt_tokens": summarize(prompt_token_counts),
            "completion_tokens": summarize(completion_token_counts),
            **throughput,
        },
        "server_metrics": null_server_metrics(),
        "error": None,
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
    parser.add_argument(
        "--api-key",
        default=os.environ.get("LITELLM_MASTER_KEY"),
        help="Bearer token for OpenAI-compatible proxies. Defaults to LITELLM_MASTER_KEY.",
    )
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument(
        "--output-jsonl",
        default=None,
        help=f"Path for JSONL rows. Overrides --run-id path (legacy default: {_FALLBACK_JSONL}).",
    )
    parser.add_argument(
        "--output-summary",
        default=None,
        help=(
            "Path for summary JSON. Overrides --run-id path "
            f"(legacy default: {_FALLBACK_SUMMARY})."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier. Sets output paths under results/runs/<run_id>/"
             f"{MODE_SINGLESTREAM_LITE_REPEATED}/ unless explicit --output-* flags are given.",
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

    jsonl_path_str = resolve_output_path(
        run_id=args.run_id,
        explicit_path=args.output_jsonl,
        benchmark_mode=MODE_SINGLESTREAM_LITE_REPEATED,
        filename="results.jsonl",
        fallback=_FALLBACK_JSONL,
    )
    summary_path_str = resolve_output_path(
        run_id=args.run_id,
        explicit_path=args.output_summary,
        benchmark_mode=MODE_SINGLESTREAM_LITE_REPEATED,
        filename="summary.json",
        fallback=_FALLBACK_SUMMARY,
    )

    request = CompletionRequest(
        base_url=args.base_url,
        model=args.model,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        api_key=args.api_key,
    )
    decoding = {"temperature": args.temperature, "max_tokens": args.max_tokens}
    workload_spec = build_workload_spec(
        name=args.workload,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        decoding=decoding,
        concurrency=1,
        arrival_process="sequential",
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
        warmup_runs=args.warmup,
        measured_runs=args.runs,
        concurrency=1,
        workload=args.workload,
        workload_spec=workload_spec,
        notes=args.notes,
        run_id=args.run_id,
        run_uuid=make_run_uuid(),
        script_name=_SCRIPT_NAME,
        git_commit=get_git_commit(),
    )

    def progress(row: RunRow) -> None:
        ttft_str = _format_ms(row.ttft_seconds)
        e2e_str = _format_ms(row.e2e_seconds)
        marker = "W" if row.phase == "warmup" else "M"
        err = f" ERROR={row.error}" if row.error else ""
        print(f"[{marker}{row.index}] TTFT={ttft_str:>10}  E2E={e2e_str:>10}{err}")

    # Run warmup and measured phases separately so we can time the measured
    # phase alone. Throughput computed over the warmup window would be
    # meaningless because the denominator would include cache/JIT warm-up time.
    warmup_rows = run_sequential(
        request,
        warmup=args.warmup,
        runs=0,
        timeout=args.timeout,
        on_run=progress,
    )
    measured_wall_start = _now()
    measured_rows = run_sequential(
        request,
        warmup=0,
        runs=args.runs,
        timeout=args.timeout,
        on_run=progress,
    )
    measured_wall_clock_seconds = _now() - measured_wall_start
    rows = warmup_rows + measured_rows

    jsonl_path = Path(jsonl_path_str)
    summary_path = Path(summary_path_str)
    write_jsonl(jsonl_path, rows)
    summary = build_summary(
        request=request,
        controls=controls,
        rows=rows,
        measured_wall_clock_seconds=measured_wall_clock_seconds,
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )

    s = summary["summary"]
    ttft = s["ttft_seconds"]
    e2e = s["e2e_seconds"]
    tpot = s["tpot_seconds"]
    print("---")
    print(f"measured runs: {s['measured_runs']}  errors: {s['errors']}")
    print(f"TTFT  p50={_format_ms(ttft['p50'])}  p95={_format_ms(ttft['p95'])}  "
          f"min={_format_ms(ttft['min'])}  max={_format_ms(ttft['max'])}")
    print(f"E2E   p50={_format_ms(e2e['p50'])}  p95={_format_ms(e2e['p95'])}  "
          f"min={_format_ms(e2e['min'])}  max={_format_ms(e2e['max'])}")
    print(f"TPOT  p50={_format_ms(tpot['p50'])}  p95={_format_ms(tpot['p95'])}")
    print(f"jsonl:   {jsonl_path}")
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
