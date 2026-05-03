"""Shared metric helpers and Benchmark Contract record shape.

Kept tiny on purpose. The point is that every measurement script writes
results in the same JSON shape so they can be aggregated later.

Aligned with the "Benchmark Contract" section of ROADMAP_v_1_0.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


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
    workload: str | None = None
    notes: str | None = None

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
            "workload": self.workload,
            "notes": self.notes,
        }


def now_iso() -> str:
    """Timezone-aware ISO 8601 timestamp, UTC, second resolution is fine."""
    return datetime.now(UTC).isoformat()


def percentile(values: list[float], p: float) -> float:
    """Plain linear-interpolated percentile.

    No numpy dependency — keeps the laptop env minimal. ``p`` is in [0, 100].
    Returns ``float('nan')`` for empty input so summary code doesn't crash on
    zero successful runs.
    """
    if not values:
        return float("nan")
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


def summarize(values: list[float]) -> dict[str, float]:
    """Common summary block used in result JSON.

    Includes count, min, p50, p95, max, mean. ``nan`` when empty.
    """
    if not values:
        return {
            "count": 0,
            "min": float("nan"),
            "p50": float("nan"),
            "p95": float("nan"),
            "max": float("nan"),
            "mean": float("nan"),
        }
    return {
        "count": len(values),
        "min": min(values),
        "p50": percentile(values, 50.0),
        "p95": percentile(values, 95.0),
        "max": max(values),
        "mean": sum(values) / len(values),
    }
