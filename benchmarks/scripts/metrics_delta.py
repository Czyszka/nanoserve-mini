"""Per-request server-side latency from two vLLM ``/metrics`` snapshots.

vLLM exposes request latency as Prometheus **histograms** (``_sum`` / ``_count``
/ ``_bucket``). A single snapshot is cumulative, so the per-request latency of an
isolated request is recovered by differencing two snapshots taken around it::

    mean_seconds = (post_sum - pre_sum) / (post_count - pre_count)

This is only meaningful when **at most one request is in flight** between the two
snapshots (single-stream). It is the building block for the **T8** proxy-overhead
attribution. vLLM's server-side latency is identical whether a request arrives
directly or via LiteLLM Proxy — vLLM does not know about the proxy — so it is a
shared reference clock. With ``server`` from this module and ``client`` from the
benchmark client::

    outside_vllm = client_observed - server_side     # transport + proxy + client parse

isolates everything outside vLLM on each path, and the paired difference

    outside_proxy - outside_direct

isolates the proxy's own contribution. On loopback the transport term is tiny and
cancels, leaving the proxy processing cost. See
``docs/writeups/w1/t8-litellm-overhead.md`` and the T8 follow-up plan.

Metric names verified against a real v0.20.0 dump
(``results/raw/observability/vllm-metrics.txt``).

Usage::

    uv run python -m benchmarks.scripts.metrics_delta \
        --pre  results/runs/<id>/server_metrics/snapshot_pre.json \
        --post results/runs/<id>/server_metrics/snapshot_post.json \
        --output results/runs/<id>/server_metrics/delta.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final

from benchmarks.scripts._metrics import now_iso
from benchmarks.scripts._schemas import METHODOLOGY, SCHEMA_METRICS_DELTA
from benchmarks.scripts._server_metrics import first_value

# Base names of the vLLM latency histograms. For all but inter-token latency the
# histogram ``_count`` increments once per finished request, so ``_sum/_count``
# is the mean per-request latency. ``inter_token_latency_seconds`` counts one
# observation per inter-token gap, so its ``_sum/_count`` is the mean per-token
# cadence (ITL), not a per-request value — noted in ``count_unit``.
LATENCY_HISTOGRAMS: Final[tuple[str, ...]] = (
    "vllm:time_to_first_token_seconds",
    "vllm:e2e_request_latency_seconds",
    "vllm:request_queue_time_seconds",
    "vllm:request_prefill_time_seconds",
    "vllm:request_decode_time_seconds",
    "vllm:inter_token_latency_seconds",
)

_PER_TOKEN_HISTOGRAMS: Final[frozenset[str]] = frozenset(
    {"vllm:inter_token_latency_seconds"}
)


def histogram_delta(
    pre_metrics: dict[str, list[dict[str, Any]]],
    post_metrics: dict[str, list[dict[str, Any]]],
    base_name: str,
) -> dict[str, Any]:
    """Δsum/Δcount for one histogram across two parsed ``/metrics`` snapshots.

    Returns a result block; never raises. ``mean_seconds`` is ``None`` when the
    histogram is absent in either snapshot, when no observations occurred
    between them, or when the counter appears to have reset (negative delta).
    """
    count_unit = "token-gap" if base_name in _PER_TOKEN_HISTOGRAMS else "request"
    result: dict[str, Any] = {
        "metric": base_name,
        "delta_sum": None,
        "delta_count": None,
        "mean_seconds": None,
        "count_unit": count_unit,
        "note": None,
    }

    pre_sum = first_value(pre_metrics, f"{base_name}_sum")
    pre_count = first_value(pre_metrics, f"{base_name}_count")
    post_sum = first_value(post_metrics, f"{base_name}_sum")
    post_count = first_value(post_metrics, f"{base_name}_count")

    if None in (pre_sum, pre_count, post_sum, post_count):
        result["note"] = "histogram absent in one or both snapshots"
        return result

    delta_sum = post_sum - pre_sum  # type: ignore[operator]
    delta_count = post_count - pre_count  # type: ignore[operator]
    result["delta_sum"] = delta_sum
    result["delta_count"] = delta_count

    if delta_count < 0 or delta_sum < 0:
        result["note"] = "counter reset between snapshots (negative delta)"
        return result
    if delta_count == 0:
        result["note"] = "no observations between snapshots"
        return result

    result["mean_seconds"] = delta_sum / delta_count
    return result


def per_request_latencies(
    pre_metrics: dict[str, list[dict[str, Any]]],
    post_metrics: dict[str, list[dict[str, Any]]],
    names: tuple[str, ...] = LATENCY_HISTOGRAMS,
) -> dict[str, dict[str, Any]]:
    """``histogram_delta`` for each name in ``names``, keyed by base name."""
    return {name: histogram_delta(pre_metrics, post_metrics, name) for name in names}


def outside_vllm_overhead(
    client_seconds: float | None,
    server_seconds: float | None,
) -> float | None:
    """Client-observed minus vLLM server-side latency = everything outside vLLM.

    Returns ``None`` if either input is missing. May be slightly negative from
    clock-boundary skew between client and server timers; callers should treat
    small negatives as noise, not as the proxy being faster than vLLM.
    """
    if client_seconds is None or server_seconds is None:
        return None
    return client_seconds - server_seconds


def _metrics_from_snapshot(obj: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Extract the parsed ``/metrics`` map from a collect_metrics_snapshot file.

    Accepts either a full snapshot (``{"vllm": {"metrics": {...}}}``) or a bare
    parsed-metrics map. Returns ``{}`` when nothing usable is present.
    """
    vllm = obj.get("vllm")
    if isinstance(vllm, dict) and isinstance(vllm.get("metrics"), dict):
        return vllm["metrics"]
    metrics = obj.get("metrics")
    if isinstance(metrics, dict):
        return metrics
    return {}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Per-request vLLM latency from two /metrics snapshots (Δsum/Δcount).",
    )
    parser.add_argument("--pre", required=True, help="Pre-request snapshot JSON.")
    parser.add_argument("--post", required=True, help="Post-request snapshot JSON.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path. If omitted, prints to stdout only.",
    )
    return parser.parse_args(argv)


def build_delta(
    *,
    pre_obj: dict[str, Any],
    post_obj: dict[str, Any],
    pre_file: str,
    post_file: str,
) -> dict[str, Any]:
    pre_metrics = _metrics_from_snapshot(pre_obj)
    post_metrics = _metrics_from_snapshot(post_obj)
    return {
        "schema": SCHEMA_METRICS_DELTA,
        "methodology": METHODOLOGY,
        "timestamp": now_iso(),
        "pre_file": pre_file,
        "post_file": post_file,
        "pre_timestamp": pre_obj.get("timestamp"),
        "post_timestamp": post_obj.get("timestamp"),
        "per_request": per_request_latencies(pre_metrics, post_metrics),
        "error": None,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    pre_obj = json.loads(Path(args.pre).read_text(encoding="utf-8"))
    post_obj = json.loads(Path(args.post).read_text(encoding="utf-8"))

    delta = build_delta(
        pre_obj=pre_obj,
        post_obj=post_obj,
        pre_file=args.pre,
        post_file=args.post,
    )

    if args.output is not None:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(delta, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )

    for name, block in delta["per_request"].items():
        mean = block["mean_seconds"]
        shown = f"{mean:.6f}s" if mean is not None else f"n/a ({block['note']})"
        print(f"{name:<42} {shown}  (d_count={block['delta_count']} {block['count_unit']})")
    if args.output is not None:
        print(f"saved: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
