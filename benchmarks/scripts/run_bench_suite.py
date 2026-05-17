"""Run the standard Phase 1 benchmark sequence for one model target.

The suite is intentionally thin: it reuses the existing benchmark entrypoints
and only coordinates a shared auto-generated run id plus a small manifest.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmarks.scripts import (
    collect_metrics_snapshot,
    measure_ttft_once,
    request_once,
    run_sequential_benchmark,
)
from benchmarks.scripts._metrics import now_iso
from benchmarks.scripts._schemas import (
    MODE_SINGLESTREAM_LITE_CORRECTNESS,
    MODE_SINGLESTREAM_LITE_LATENCY,
    MODE_SINGLESTREAM_LITE_REPEATED,
)

_SCRIPT_NAME = "run_bench_suite.py"
_RUNS_ROOT = Path("results") / "runs"
_SUITE_DIR = "bench_suite"


@dataclass
class StepResult:
    name: str
    argv: list[str]
    exit_code: int
    started_at: str
    ended_at: str
    output_paths: list[str]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "argv": list(self.argv),
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "output_paths": list(self.output_paths),
            "error": self.error,
        }


def slugify_model(model: str) -> str:
    """Convert a model name into a stable path-friendly lowercase slug."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", model).strip("-").lower()
    return slug or "model"


def generate_run_id(
    *,
    model: str,
    runs_root: Path = _RUNS_ROOT,
    today: str | None = None,
) -> str:
    """Return the next YYYY-MM-DD_<model-slug>_run-NN identifier."""
    date_part = today or datetime.now(UTC).date().isoformat()
    prefix = f"{date_part}_{slugify_model(model)}_run-"
    highest = 0
    if runs_root.exists():
        for child in runs_root.iterdir():
            if not child.is_dir() or not child.name.startswith(prefix):
                continue
            suffix = child.name.removeprefix(prefix)
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:02d}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run snapshot/request/TTFT/sequential/post benchmark suite.",
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--metrics-base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", default="Say hi in one short sentence.")
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument(
        "--api-key",
        default=os.environ.get("LITELLM_MASTER_KEY"),
        help="LiteLLM bearer token. Defaults to LITELLM_MASTER_KEY.",
    )
    parser.add_argument("--gpu-model", default=None)
    parser.add_argument("--vllm-version", default=None)
    parser.add_argument("--dtype", default=None)
    parser.add_argument("--quantization", default=None)
    parser.add_argument("--max-model-len", type=int, default=None)
    parser.add_argument("--max-num-seqs", type=int, default=None)
    parser.add_argument("--max-num-batched-tokens", type=int, default=None)
    parser.add_argument("--workload", default="single-target-bench-suite")
    parser.add_argument("--notes", default=None)
    return parser.parse_args(argv)


def _append_option(argv: list[str], flag: str, value: Any) -> None:
    if value is not None:
        argv.extend([flag, str(value)])


def _common_request_args(args: argparse.Namespace, run_id: str) -> list[str]:
    argv = [
        "--base-url", args.base_url,
        "--model", args.model,
        "--prompt", args.prompt,
        "--max-tokens", str(args.max_tokens),
        "--temperature", str(args.temperature),
        "--timeout", str(args.timeout),
        "--run-id", run_id,
        "--api-key", args.api_key,
        "--workload", args.workload,
    ]
    _append_option(argv, "--gpu-model", args.gpu_model)
    _append_option(argv, "--vllm-version", args.vllm_version)
    _append_option(argv, "--dtype", args.dtype)
    _append_option(argv, "--quantization", args.quantization)
    _append_option(argv, "--max-model-len", args.max_model_len)
    _append_option(argv, "--max-num-seqs", args.max_num_seqs)
    _append_option(argv, "--max-num-batched-tokens", args.max_num_batched_tokens)
    _append_option(argv, "--notes", args.notes)
    return argv


def _snapshot_args(args: argparse.Namespace, run_id: str, phase: str) -> list[str]:
    argv = [
        "--base-url", args.metrics_base_url,
        "--timeout", str(args.timeout),
        "--run-id", run_id,
        "--phase", phase,
    ]
    _append_option(argv, "--notes", args.notes)
    return argv


def _sequential_args(args: argparse.Namespace, run_id: str) -> list[str]:
    argv = _common_request_args(args, run_id)
    argv.extend(["--warmup", str(args.warmup), "--runs", str(args.runs)])
    return argv


def expected_output_paths(run_id: str) -> dict[str, list[str]]:
    base = Path("results") / "runs" / run_id
    return {
        "snapshot_pre": [str(base / "server_metrics" / "snapshot_pre.json")],
        "request_once": [
            str(base / MODE_SINGLESTREAM_LITE_CORRECTNESS / "result.json")
        ],
        "measure_ttft_once": [
            str(base / MODE_SINGLESTREAM_LITE_LATENCY / "result.json")
        ],
        "run_sequential_benchmark": [
            str(base / MODE_SINGLESTREAM_LITE_REPEATED / "results.jsonl"),
            str(base / MODE_SINGLESTREAM_LITE_REPEATED / "summary.json"),
        ],
        "snapshot_post": [str(base / "server_metrics" / "snapshot_post.json")],
        "manifest": [str(base / _SUITE_DIR / "summary.json")],
    }


def run_step(
    *,
    name: str,
    argv: list[str],
    entrypoint: Callable[[list[str]], int],
    output_paths: list[str],
) -> StepResult:
    started_at = now_iso()
    error: str | None = None
    try:
        exit_code = entrypoint(argv)
    except Exception as exc:  # noqa: BLE001 - manifest should record unexpected failures
        exit_code = 1
        error = f"{type(exc).__name__}: {exc}"
    ended_at = now_iso()
    return StepResult(
        name=name,
        argv=argv,
        exit_code=exit_code,
        started_at=started_at,
        ended_at=ended_at,
        output_paths=output_paths,
        error=error,
    )


def build_manifest(
    *,
    args: argparse.Namespace,
    run_id: str,
    started_at: str,
    ended_at: str,
    steps: list[StepResult],
    completed: bool,
    error: str | None,
) -> dict[str, Any]:
    return {
        "schema": "nanoserve-mini.bench-suite.v1",
        "script_name": _SCRIPT_NAME,
        "run_id": run_id,
        "model": args.model,
        "base_url": args.base_url,
        "metrics_base_url": args.metrics_base_url,
        "started_at": started_at,
        "ended_at": ended_at,
        "generated_run_id": True,
        "completed": completed,
        "error": error,
        "steps": [step.as_dict() for step in steps],
    }


def write_manifest(manifest: dict[str, Any], run_id: str) -> Path:
    path = Path("results") / "runs" / run_id / _SUITE_DIR / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return path


def run_suite(args: argparse.Namespace, *, run_id: str | None = None) -> int:
    if not args.api_key:
        print("ERROR: --api-key or LITELLM_MASTER_KEY is required for the suite", file=sys.stderr)
        return 2
    if args.runs < 1:
        print("ERROR: --runs must be >= 1", file=sys.stderr)
        return 2
    if args.warmup < 0:
        print("ERROR: --warmup must be >= 0", file=sys.stderr)
        return 2

    resolved_run_id = run_id or generate_run_id(model=args.model)
    paths = expected_output_paths(resolved_run_id)
    started_at = now_iso()
    steps: list[StepResult] = []
    error: str | None = None

    pre = run_step(
        name="snapshot_pre",
        argv=_snapshot_args(args, resolved_run_id, "pre"),
        entrypoint=collect_metrics_snapshot.main,
        output_paths=paths["snapshot_pre"],
    )
    steps.append(pre)

    client_steps: list[tuple[str, list[str], Callable[[list[str]], int]]] = [
        ("request_once", _common_request_args(args, resolved_run_id), request_once.main),
        (
            "measure_ttft_once",
            _common_request_args(args, resolved_run_id),
            measure_ttft_once.main,
        ),
        (
            "run_sequential_benchmark",
            _sequential_args(args, resolved_run_id),
            run_sequential_benchmark.main,
        ),
    ]
    for name, argv, entrypoint in client_steps:
        step = run_step(
            name=name,
            argv=argv,
            entrypoint=entrypoint,
            output_paths=paths[name],
        )
        steps.append(step)
        if step.exit_code != 0:
            error = f"{name} exited with {step.exit_code}"
            break

    post = run_step(
        name="snapshot_post",
        argv=_snapshot_args(args, resolved_run_id, "post"),
        entrypoint=collect_metrics_snapshot.main,
        output_paths=paths["snapshot_post"],
    )
    steps.append(post)

    completed = error is None and all(step.exit_code == 0 for step in steps)
    if error is None and not completed:
        failed = next(step for step in steps if step.exit_code != 0)
        error = f"{failed.name} exited with {failed.exit_code}"
    manifest = build_manifest(
        args=args,
        run_id=resolved_run_id,
        started_at=started_at,
        ended_at=now_iso(),
        steps=steps,
        completed=completed,
        error=error,
    )
    manifest_path = write_manifest(manifest, resolved_run_id)

    print(f"run_id:   {resolved_run_id}")
    print(f"manifest: {manifest_path}")
    print(f"completed: {completed}")
    return 0 if completed else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_suite(args)


if __name__ == "__main__":
    sys.exit(main())
