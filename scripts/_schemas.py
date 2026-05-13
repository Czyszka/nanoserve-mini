"""Shared schema, methodology, and benchmark-mode constants.

All benchmark scripts and downstream consumers (aggregator, future dashboard)
should import identifiers from here so the contract has a single source of truth.

Bump a schema version when the JSON shape of that result type changes in a way
that is not purely additive at the leaf level.
"""

from __future__ import annotations

from typing import Final

# Methodology label written into every result file.
METHODOLOGY: Final[str] = "mlperf_inspired_lite"

# Benchmark mode identifiers (per `docs/benchmark-methodology.md`).
MODE_SINGLESTREAM_LITE_CORRECTNESS: Final[str] = "singlestream_lite_correctness"
MODE_SINGLESTREAM_LITE_LATENCY: Final[str] = "singlestream_lite_latency"
MODE_SINGLESTREAM_LITE_REPEATED: Final[str] = "singlestream_lite_repeated"
MODE_CODING_AGENT_EVAL: Final[str] = "coding_agent_eval"

# Result schema versions.
SCHEMA_REQUEST_ONCE: Final[str] = "nanoserve-mini.request-once.v2"
SCHEMA_TTFT_ONCE: Final[str] = "nanoserve-mini.ttft-once.v2"
SCHEMA_SEQUENTIAL_BENCH: Final[str] = "nanoserve-mini.sequential-bench.v3"
SCHEMA_SEQUENTIAL_BENCH_ROW: Final[str] = "nanoserve-mini.sequential-bench-row.v3"

# Server-side observability artifacts.
SCHEMA_SERVER_METRICS_SNAPSHOT: Final[str] = "nanoserve-mini.server-metrics-snapshot.v1"
SCHEMA_GPU_SAMPLES_META: Final[str] = "nanoserve-mini.gpu-samples-meta.v1"

# Coding-agent evaluation row schema (one row per task × agent × model run).
SCHEMA_CODING_AGENT_EVAL_ROW: Final[str] = "nanoserve-mini.coding-agent-eval-row.v1"
