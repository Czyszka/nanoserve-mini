"""One-shot snapshot of server-side metrics around a benchmark run.

Captures, in a single JSON file:

- vLLM ``/metrics`` (Prometheus exposition) — full parsed map plus a
  selected ``aggregate`` block matching the per-result ``server_metrics``
  stub (``gpu_memory_used_gb``, ``kv_cache_usage``, ``prefix_cache_hit_rate``).
- ``nvidia-smi --query-gpu=...`` — one row per visible GPU.

Usage:

    uv run python -m scripts.collect_metrics_snapshot \
        --base-url http://127.0.0.1:8000 \
        --run-id 2026-05-11_kimi_tp8_baseline \
        --phase pre

Output paths:
- with ``--run-id``: ``results/runs/<run_id>/server_metrics/snapshot_<phase>.json``
- with ``--output``: explicit
- fallback: ``results/raw/server_metrics_snapshot.json``

Both data sources are best-effort: if vLLM is not reachable or nvidia-smi is
not installed, the file is still written with the failure recorded inline so a
dashboard can tell the difference between "not collected" and "zero".
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

from scripts._metrics import make_run_uuid, now_iso, resolve_output_path
from scripts._schemas import METHODOLOGY, SCHEMA_SERVER_METRICS_SNAPSHOT
from scripts._server_metrics import (
    NVIDIA_SMI_QUERY_FIELDS,
    parse_nvidia_smi_csv,
    parse_prometheus_text,
    select_vllm_aggregate,
    total_gpu_memory_used_gb,
)

_FALLBACK_OUTPUT = "results/raw/server_metrics_snapshot.json"
_PHASES = ("pre", "mid", "post", "adhoc")


def scrape_vllm_metrics(
    base_url: str,
    *,
    timeout: float = 5.0,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Fetch and parse vLLM ``/metrics``. Returns a result block, never raises."""
    url = base_url.rstrip("/") + "/metrics"
    block: dict[str, Any] = {
        "endpoint": url,
        "scrape_ok": False,
        "scrape_error": None,
        "metrics": {},
    }
    owns_client = client is None
    http = client if client is not None else httpx.Client(timeout=timeout)
    try:
        try:
            response = http.get(url)
            response.raise_for_status()
            block["metrics"] = parse_prometheus_text(response.text)
            block["scrape_ok"] = True
        except Exception as exc:  # noqa: BLE001 - best-effort scraping
            block["scrape_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if owns_client:
            http.close()
    return block


def run_nvidia_smi(
    *,
    timeout: float = 10.0,
    runner: Any = None,
) -> dict[str, Any]:
    """Invoke ``nvidia-smi`` once and parse output.

    ``runner`` is injectable for tests (defaults to ``subprocess.run``).
    Returns a structured block; never raises.
    """
    query = ",".join(NVIDIA_SMI_QUERY_FIELDS)
    cmd = [
        "nvidia-smi",
        f"--query-gpu={query}",
        "--format=csv,noheader,nounits",
    ]
    block: dict[str, Any] = {
        "available": False,
        "command": cmd,
        "rows": [],
        "error": None,
    }
    run = runner if runner is not None else subprocess.run
    try:
        completed = run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        if completed.returncode != 0:
            block["error"] = (
                f"nvidia-smi exit {completed.returncode}: {(completed.stderr or '').strip()}"
            )
            return block
        block["rows"] = parse_nvidia_smi_csv(completed.stdout)
        block["available"] = True
    except FileNotFoundError as exc:
        block["error"] = f"command not found: {exc}"
    except subprocess.TimeoutExpired as exc:
        block["error"] = f"timeout: {exc}"
    except Exception as exc:  # noqa: BLE001
        block["error"] = f"{type(exc).__name__}: {exc}"
    return block


def build_snapshot(
    *,
    run_id: str | None,
    run_uuid: str,
    phase: str,
    base_url: str,
    notes: str | None,
    vllm_block: dict[str, Any],
    gpu_block: dict[str, Any],
) -> dict[str, Any]:
    gpu_used_gb = total_gpu_memory_used_gb(gpu_block.get("rows", []))
    aggregate = select_vllm_aggregate(
        vllm_block.get("metrics") or {},
        gpu_memory_used_gb=gpu_used_gb,
    )
    return {
        "schema": SCHEMA_SERVER_METRICS_SNAPSHOT,
        "methodology": METHODOLOGY,
        "timestamp": now_iso(),
        "run_id": run_id,
        "run_uuid": run_uuid,
        "phase": phase,
        "base_url": base_url,
        "notes": notes,
        "vllm": vllm_block,
        "gpu": gpu_block,
        "aggregate": aggregate,
        "error": None,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-shot vLLM /metrics + nvidia-smi snapshot.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--phase",
        choices=_PHASES,
        default="adhoc",
        help="Where in the run lifecycle this snapshot was taken.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=f"Explicit output path. Overrides --run-id (legacy default: {_FALLBACK_OUTPUT}).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier. Sets output to "
             "results/runs/<run_id>/server_metrics/snapshot_<phase>.json.",
    )
    parser.add_argument("--notes", default=None)
    return parser.parse_args(argv)


def _resolve_path(args: argparse.Namespace) -> str:
    return resolve_output_path(
        run_id=args.run_id,
        explicit_path=args.output,
        benchmark_mode="server_metrics",
        filename=f"snapshot_{args.phase}.json",
        fallback=_FALLBACK_OUTPUT,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    output_path = Path(_resolve_path(args))

    vllm_block = scrape_vllm_metrics(args.base_url, timeout=args.timeout)
    gpu_block = run_nvidia_smi()

    snapshot = build_snapshot(
        run_id=args.run_id,
        run_uuid=make_run_uuid(),
        phase=args.phase,
        base_url=args.base_url,
        notes=args.notes,
        vllm_block=vllm_block,
        gpu_block=gpu_block,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )

    agg = snapshot["aggregate"]
    print(f"phase:    {args.phase}")
    print(f"vllm:     scrape_ok={vllm_block['scrape_ok']} "
          f"metrics={len(vllm_block.get('metrics') or {})}")
    print(f"gpu:      available={gpu_block['available']} rows={len(gpu_block.get('rows') or [])}")
    print(
        "aggregate: "
        f"gpu_memory_used_gb={agg['gpu_memory_used_gb']} "
        f"kv_cache_usage={agg['kv_cache_usage']} "
        f"prefix_cache_hit_rate={agg['prefix_cache_hit_rate']}"
    )
    print(f"saved:    {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
