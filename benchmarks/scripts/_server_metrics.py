"""Helpers for server-side metric collection.

Two pure data extractors live here:

- ``parse_prometheus_text``: minimal Prometheus exposition-format parser, just
  enough to read vLLM's ``/metrics`` without pulling in ``prometheus_client``.
- ``parse_nvidia_smi_csv``: ``nvidia-smi --query-gpu=... --format=csv,noheader,nounits``
  parser that returns one dict per GPU.

Both functions are pure and testable. The actual subprocess / HTTP calls live
in the snapshot/sample scripts so the parsers can be exercised with canned
inputs.
"""

from __future__ import annotations

import math
import re
from typing import Any, Final

# Field order used by both the snapshot script and the sampler. Keeping the
# order in one place means the CSV header in `sample_gpu_metrics.py` and the
# JSON keys in `collect_metrics_snapshot.py` stay in sync.
NVIDIA_SMI_QUERY_FIELDS: tuple[str, ...] = (
    "index",
    "name",
    "utilization.gpu",
    "utilization.memory",
    "memory.used",
    "memory.free",
    "memory.total",
    "temperature.gpu",
    "power.draw",
    "clocks.current.sm",
    "clocks.current.memory",
)

# Mapping from the raw query field to the JSON/CSV key we want to expose.
# Keys are typed at parse time when they look numeric; "index" stays an int,
# "name" stays a string.
NVIDIA_SMI_FIELD_MAP: dict[str, str] = {
    "index": "gpu_index",
    "name": "gpu_name",
    "utilization.gpu": "utilization_gpu_pct",
    "utilization.memory": "utilization_memory_pct",
    "memory.used": "memory_used_mib",
    "memory.free": "memory_free_mib",
    "memory.total": "memory_total_mib",
    "temperature.gpu": "temperature_c",
    "power.draw": "power_draw_w",
    "clocks.current.sm": "clocks_sm_mhz",
    "clocks.current.memory": "clocks_memory_mhz",
}

CSV_COLUMNS: tuple[str, ...] = (
    "timestamp_iso",
    "timestamp_unix",
    *(NVIDIA_SMI_FIELD_MAP[f] for f in NVIDIA_SMI_QUERY_FIELDS),
)

# vLLM gauges/counters we want to surface in the `aggregate` block. Each
# benchmark result file has a `server_metrics` stub with these same three keys
# so the aggregator/dashboard can join them by run_id without renaming.
_VLLM_GAUGES_KV_USAGE: Final = "vllm:gpu_cache_usage_perc"
_VLLM_GAUGES_PREFIX_HIT: Final = "vllm:gpu_prefix_cache_hit_rate"


_LINE_RE = re.compile(
    r"""^
    (?P<name>[a-zA-Z_:][\w:]*)            # metric name
    (?:\{(?P<labels>[^}]*)\})?            # optional {label="value",...}
    \s+
    (?P<value>[+\-]?(?:\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?|NaN|\+?Inf|-Inf))
    \s*$
    """,
    re.VERBOSE,
)
_LABEL_RE = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')


def _parse_value(raw: str) -> float | None:
    """Convert a Prometheus value token to a JSON-friendly float or None.

    NaN and ±Inf are returned as ``None`` so downstream JSON stays strict
    (we always serialize with ``allow_nan=False``).
    """
    s = raw.strip()
    if s in ("NaN", "+Inf", "Inf", "-Inf"):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _parse_labels(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    out: dict[str, str] = {}
    for m in _LABEL_RE.finditer(raw):
        key, value = m.group(1), m.group(2)
        out[key] = value.encode().decode("unicode_escape")
    return out


def parse_prometheus_text(text: str) -> dict[str, list[dict[str, Any]]]:
    """Parse a Prometheus exposition-format payload into a nested dict.

    Result shape::

        {
          "vllm:num_requests_running": [
            {"labels": {"model_name": "..."}, "value": 0.0},
            ...
          ],
          ...
        }

    Comment lines (``# HELP`` / ``# TYPE``) are ignored. Lines that don't match
    the basic Prometheus shape are skipped silently — this is best-effort
    scraping, not a strict parser.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE_RE.match(line)
        if m is None:
            continue
        name = m.group("name")
        labels = _parse_labels(m.group("labels"))
        value = _parse_value(m.group("value"))
        out.setdefault(name, []).append({"labels": labels, "value": value})
    return out


def first_value(
    metrics: dict[str, list[dict[str, Any]]],
    name: str,
) -> float | None:
    """Return the first non-None numeric value for ``name`` if present."""
    samples = metrics.get(name) or []
    for sample in samples:
        v = sample.get("value")
        if isinstance(v, int | float):
            return float(v)
    return None


def select_vllm_aggregate(
    metrics: dict[str, list[dict[str, Any]]],
    *,
    gpu_memory_used_gb: float | None = None,
) -> dict[str, float | None]:
    """Build the 3-field aggregate that mirrors the per-result `server_metrics` stub.

    `gpu_memory_used_gb` is supplied by the caller (from nvidia-smi output)
    because vLLM's exposition does not report device memory directly.
    """
    return {
        "gpu_memory_used_gb": gpu_memory_used_gb,
        "kv_cache_usage": first_value(metrics, _VLLM_GAUGES_KV_USAGE),
        "prefix_cache_hit_rate": first_value(metrics, _VLLM_GAUGES_PREFIX_HIT),
    }


def _coerce(field: str, raw: str) -> Any:
    """Type-coerce a raw nvidia-smi CSV cell based on its source field."""
    s = raw.strip()
    if field == "name":
        return s
    if field == "index":
        try:
            return int(s)
        except ValueError:
            return None
    # numeric fields; nvidia-smi sometimes returns "[Not Supported]" or "N/A"
    if not s or s.startswith("[") or s == "N/A":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_nvidia_smi_csv(
    text: str,
    *,
    fields: tuple[str, ...] = NVIDIA_SMI_QUERY_FIELDS,
) -> list[dict[str, Any]]:
    """Parse ``nvidia-smi --query-gpu=... --format=csv,noheader,nounits`` output.

    One dict per GPU row. Keys are taken from ``NVIDIA_SMI_FIELD_MAP``.
    Numeric fields are returned as floats (or ``int`` for ``index``); unknown
    or unsupported cells become ``None``.
    """
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        cells = [c.strip() for c in line.split(",")]
        if len(cells) != len(fields):
            continue
        row: dict[str, Any] = {}
        for field, cell in zip(fields, cells, strict=True):
            row[NVIDIA_SMI_FIELD_MAP[field]] = _coerce(field, cell)
        out.append(row)
    return out


def total_gpu_memory_used_gb(rows: list[dict[str, Any]]) -> float | None:
    """Sum visible GPU memory.used (MiB) and convert to GiB-equivalent floats.

    Returns ``None`` if no row reports a numeric `memory_used_mib`.
    """
    used: list[float] = []
    for row in rows:
        v = row.get("memory_used_mib")
        if isinstance(v, int | float):
            used.append(float(v))
    if not used:
        return None
    # nvidia-smi reports MiB. We expose GB-as-GiB rounded to 3 decimals so the
    # JSON is human-readable; the dashboard can multiply if it needs raw bytes.
    return round(sum(used) / 1024.0, 3)
