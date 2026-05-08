"""Interval CSV sampling of GPU state via ``nvidia-smi``.

Loops ``nvidia-smi --query-gpu=...`` at a fixed interval for a fixed duration
(or a fixed sample count) and writes one row per GPU per tick.

Usage:

    uv run python -m scripts.sample_gpu_metrics \
        --run-id 2026-05-11_kimi_tp8_baseline \
        --interval-ms 500 \
        --duration-s 60

Output paths:
- with ``--run-id``: ``results/runs/<run_id>/server_metrics/gpu_samples.csv`` plus a
  sidecar ``gpu_samples_meta.json`` describing the run.
- with ``--output``: explicit CSV path (sidecar lives next to it as ``<stem>_meta.json``).
- fallback: ``results/raw/gpu_samples.csv``.

This is intentionally simple: one synchronous ``nvidia-smi`` invocation per
tick. For high-frequency sampling later we can switch to ``nvidia-smi -lms``
streaming, but the current loop is easy to test and good enough for
order-of-seconds intervals during a benchmark.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts._metrics import make_run_uuid, now_iso, resolve_output_path
from scripts._schemas import METHODOLOGY, SCHEMA_GPU_SAMPLES_META
from scripts._server_metrics import (
    CSV_COLUMNS,
    NVIDIA_SMI_QUERY_FIELDS,
    parse_nvidia_smi_csv,
)

_FALLBACK_CSV = "results/raw/gpu_samples.csv"


def _now_unix() -> float:
    return time.time()


def _now_perf() -> float:
    return time.perf_counter()


def _run_nvidia_smi_once(
    *,
    timeout: float,
    runner: Any,
) -> tuple[list[dict[str, Any]], str | None]:
    """Single nvidia-smi invocation. Returns (rows, error)."""
    query = ",".join(NVIDIA_SMI_QUERY_FIELDS)
    cmd = [
        "nvidia-smi",
        f"--query-gpu={query}",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = runner(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except FileNotFoundError as exc:
        return [], f"command not found: {exc}"
    except subprocess.TimeoutExpired as exc:
        return [], f"timeout: {exc}"
    except Exception as exc:  # noqa: BLE001
        return [], f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        return [], (
            f"nvidia-smi exit {completed.returncode}: {(completed.stderr or '').strip()}"
        )
    return parse_nvidia_smi_csv(completed.stdout), None


def sample_loop(
    *,
    csv_writer: csv.DictWriter,
    interval_s: float,
    deadline_perf: float | None,
    max_samples: int | None,
    timeout: float,
    runner: Any | None = None,
    sleeper: Any | None = None,
    perf_clock: Any | None = None,
    wall_clock: Any | None = None,
) -> dict[str, Any]:
    """Drive the sampling loop. Returns a summary dict.

    All clocks/sleepers/runners are injectable so the loop can be exercised
    deterministically in tests.
    """
    run = runner if runner is not None else subprocess.run
    sleep = sleeper if sleeper is not None else time.sleep
    perf = perf_clock if perf_clock is not None else _now_perf
    wall = wall_clock if wall_clock is not None else _now_unix

    samples_written = 0
    ticks = 0
    errors: list[str] = []

    started_perf = perf()
    started_unix = wall()

    while True:
        if max_samples is not None and ticks >= max_samples:
            break
        if deadline_perf is not None and perf() >= deadline_perf:
            break

        ts_unix = wall()
        ts_iso = datetime.fromtimestamp(ts_unix, tz=UTC).isoformat()
        rows, error = _run_nvidia_smi_once(timeout=timeout, runner=run)
        if error is not None:
            errors.append(error)
        for row in rows:
            csv_writer.writerow({
                "timestamp_iso": ts_iso,
                "timestamp_unix": ts_unix,
                **row,
            })
            samples_written += 1
        ticks += 1

        # Stop before sleeping if the next tick would exceed the deadline,
        # otherwise we'd block past the requested duration.
        if max_samples is not None and ticks >= max_samples:
            break
        if deadline_perf is not None and perf() + interval_s > deadline_perf:
            break
        sleep(interval_s)

    ended_unix = wall()
    return {
        "ticks": ticks,
        "samples_written": samples_written,
        "errors": errors,
        "started_unix": started_unix,
        "ended_unix": ended_unix,
        "duration_seconds": max(0.0, perf() - started_perf),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interval CSV sampling of nvidia-smi GPU metrics.",
    )
    parser.add_argument("--interval-ms", type=int, default=1000)
    parser.add_argument(
        "--duration-s",
        type=float,
        default=None,
        help="Total wall time to sample. Mutually exclusive with --samples; "
             "if both are set, sampling stops at whichever fires first.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=None,
        help="Maximum number of ticks to record.",
    )
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--output",
        default=None,
        help=f"Explicit CSV path. Overrides --run-id (legacy default: {_FALLBACK_CSV}).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier. Sets CSV path to "
             "results/runs/<run_id>/server_metrics/gpu_samples.csv.",
    )
    parser.add_argument("--notes", default=None)
    return parser.parse_args(argv)


def _resolve_csv_path(args: argparse.Namespace) -> str:
    return resolve_output_path(
        run_id=args.run_id,
        explicit_path=args.output,
        benchmark_mode="server_metrics",
        filename="gpu_samples.csv",
        fallback=_FALLBACK_CSV,
    )


def write_meta_sidecar(
    *,
    csv_path: Path,
    args: argparse.Namespace,
    summary: dict[str, Any],
    run_uuid: str,
) -> Path:
    meta_path = csv_path.with_name(csv_path.stem + "_meta.json")
    meta = {
        "schema": SCHEMA_GPU_SAMPLES_META,
        "methodology": METHODOLOGY,
        "timestamp": now_iso(),
        "run_id": args.run_id,
        "run_uuid": run_uuid,
        "csv_path": str(csv_path),
        "csv_columns": list(CSV_COLUMNS),
        "command": [
            "nvidia-smi",
            f"--query-gpu={','.join(NVIDIA_SMI_QUERY_FIELDS)}",
            "--format=csv,noheader,nounits",
        ],
        "interval_ms": args.interval_ms,
        "duration_s": args.duration_s,
        "samples_requested": args.samples,
        "notes": args.notes,
        "summary": summary,
        "error": None,
    }
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return meta_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.interval_ms <= 0:
        print("--interval-ms must be > 0", file=sys.stderr)
        return 2
    if args.duration_s is None and args.samples is None:
        print(
            "must specify at least one of --duration-s or --samples",
            file=sys.stderr,
        )
        return 2

    csv_path = Path(_resolve_csv_path(args))
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    interval_s = args.interval_ms / 1000.0
    deadline_perf = (
        _now_perf() + args.duration_s if args.duration_s is not None else None
    )
    run_uuid = make_run_uuid()

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        summary = sample_loop(
            csv_writer=writer,
            interval_s=interval_s,
            deadline_perf=deadline_perf,
            max_samples=args.samples,
            timeout=args.timeout,
        )

    meta_path = write_meta_sidecar(
        csv_path=csv_path, args=args, summary=summary, run_uuid=run_uuid,
    )

    print(f"ticks:    {summary['ticks']}")
    print(f"samples:  {summary['samples_written']}")
    print(f"errors:   {len(summary['errors'])}")
    print(f"duration: {summary['duration_seconds']:.2f}s")
    print(f"csv:      {csv_path}")
    print(f"meta:     {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
