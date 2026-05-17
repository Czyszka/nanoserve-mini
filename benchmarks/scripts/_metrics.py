"""Shared metric helpers and Benchmark Contract record shape.

Kept tiny on purpose. The point is that every measurement script writes
results in the same JSON shape so they can be aggregated later.

Aligned with the "Benchmark Contract" section of ROADMAP_v_1_0.md.
"""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def get_git_commit() -> str | None:
    """Return the current HEAD commit hash, or None if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception:  # noqa: BLE001
        pass
    return None


def make_run_uuid() -> str:
    """Hex uuid4 — unique per script invocation.

    `run_id` is a human-friendly group label (e.g. ``2026-05-11_kimi_tp8_baseline``)
    and may collide across re-runs that overwrite the same output path.
    `run_uuid` is the unique key for a single execution and lets a dashboard
    deduplicate when aggregating.
    """
    return uuid.uuid4().hex


def null_server_metrics() -> dict[str, Any]:
    """Stub block for vLLM/GPU-side metrics.

    Always written with `None` values until ``scripts/collect_metrics_snapshot.py``
    or ``/metrics`` scraping is wired up. Keeping the keys present (rather than
    omitting the block entirely) gives downstream consumers a stable shape.
    """
    return {
        "gpu_memory_used_gb": None,
        "kv_cache_usage": None,
        "prefix_cache_hit_rate": None,
    }


def build_workload_spec(
    *,
    name: str | None,
    prompt: str,
    max_tokens: int,
    decoding: dict[str, Any],
    concurrency: int,
    arrival_process: str,
    shared_prefixes: bool = False,
    prompt_source: str = "literal",
) -> dict[str, Any]:
    """Structured workload definition matching the ROADMAP Benchmark Contract.

    `prompt_chars` is included as a cheap proxy for input size when no tokenizer
    is available client-side. Real input/output token counts come from the server
    `usage` block when available.
    """
    return {
        "name": name,
        "prompt_source": prompt_source,
        "prompt_chars": len(prompt),
        "max_tokens": max_tokens,
        "decoding": dict(decoding),
        "concurrency": concurrency,
        "arrival_process": arrival_process,
        "shared_prefixes": shared_prefixes,
    }


@dataclass
class RunControls:
    """Reproduction context for a benchmark run."""

    model: str
    base_url: str
    dtype: str | None = None
    quantization: str | None = None
    gpu_model: str | None = None
    vllm_version: str | None = None
    max_model_len: int | None = None
    max_num_seqs: int | None = None
    max_num_batched_tokens: int | None = None
    decoding: dict[str, Any] = field(default_factory=dict)
    warmup_runs: int = 0
    measured_runs: int = 1
    concurrency: int = 1
    workload: str | None = None
    workload_spec: dict[str, Any] | None = None
    notes: str | None = None
    run_id: str | None = None
    run_uuid: str | None = None
    script_name: str | None = None
    git_commit: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "base_url": self.base_url,
            "dtype": self.dtype,
            "quantization": self.quantization,
            "gpu_model": self.gpu_model,
            "vllm_version": self.vllm_version,
            "max_model_len": self.max_model_len,
            "max_num_seqs": self.max_num_seqs,
            "max_num_batched_tokens": self.max_num_batched_tokens,
            "decoding": dict(self.decoding),
            "warmup_runs": self.warmup_runs,
            "measured_runs": self.measured_runs,
            "concurrency": self.concurrency,
            "workload": self.workload,
            "workload_spec": (
                dict(self.workload_spec) if self.workload_spec is not None else None
            ),
            "notes": self.notes,
            "run_id": self.run_id,
            "run_uuid": self.run_uuid,
            "script_name": self.script_name,
            "git_commit": self.git_commit,
        }


def now_iso() -> str:
    """Timezone-aware ISO 8601 timestamp, UTC, second resolution is fine."""
    return datetime.now(UTC).isoformat()


def percentile(values: list[float], p: float) -> float | None:
    """Plain linear-interpolated percentile.

    No numpy dependency — keeps the laptop env minimal. ``p`` is in [0, 100].
    Returns ``None`` for empty input so summary code can serialize cleanly to
    strict JSON (NaN is not valid JSON; ``json.dumps(float('nan'))`` produces
    invalid output that many parsers reject).
    """
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
    """Common summary block used in result JSON.

    Includes count, min, p50, p95, max, mean. ``None`` for every aggregate when
    the input is empty so the resulting JSON stays strict (no NaN tokens).
    ``count`` is always an integer.
    """
    if not values:
        return {
            "count": 0,
            "min": None,
            "p50": None,
            "p95": None,
            "max": None,
            "mean": None,
        }
    return {
        "count": len(values),
        "min": min(values),
        "p50": percentile(values, 50.0),
        "p95": percentile(values, 95.0),
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def resolve_output_path(
    *,
    run_id: str | None,
    explicit_path: str | None,
    benchmark_mode: str,
    filename: str,
    fallback: str | None,
) -> str | None:
    """Determine the output path for a benchmark result file.

    Priority:
    1. explicit_path if provided
    2. results/runs/<run_id>/<benchmark_mode>/<filename> if run_id provided
    3. fallback (legacy default, may be None)
    """
    if explicit_path is not None:
        return explicit_path
    if run_id is not None:
        return f"results/runs/{run_id}/{benchmark_mode}/{filename}"
    return fallback
