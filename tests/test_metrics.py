"""Tests for ``scripts._metrics``."""

from __future__ import annotations

import math

import pytest

from scripts._metrics import RunControls, percentile, summarize


def test_percentile_single_value() -> None:
    assert percentile([5.0], 50.0) == 5.0
    assert percentile([5.0], 95.0) == 5.0


def test_percentile_known_values() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    # rank 50 -> index 1.5 -> 2 + 0.5*(3-2) = 2.5
    assert percentile(values, 50.0) == pytest.approx(2.5)
    assert percentile(values, 0.0) == 1.0
    assert percentile(values, 100.0) == 4.0


def test_percentile_empty_is_nan() -> None:
    assert math.isnan(percentile([], 50.0))


def test_percentile_invalid_p() -> None:
    with pytest.raises(ValueError):
        percentile([1.0], 150.0)


def test_summarize_non_empty() -> None:
    summary = summarize([1.0, 2.0, 3.0, 4.0])
    assert summary["count"] == 4
    assert summary["min"] == 1.0
    assert summary["max"] == 4.0
    assert summary["mean"] == pytest.approx(2.5)
    assert summary["p50"] == pytest.approx(2.5)
    assert summary["p95"] == pytest.approx(3.85)


def test_summarize_empty() -> None:
    summary = summarize([])
    assert summary["count"] == 0
    for key in ("min", "p50", "p95", "max", "mean"):
        assert math.isnan(summary[key])


def test_run_controls_as_dict_roundtrip() -> None:
    controls = RunControls(
        model="m",
        base_url="http://x",
        dtype="bfloat16",
        gpu_model="H200 NVL",
        vllm_version="0.6.0",
        max_model_len=8192,
        decoding={"temperature": 0.0},
        warmup_runs=1,
        measured_runs=5,
        workload="smoke",
    )
    data = controls.as_dict()
    assert data["model"] == "m"
    assert data["dtype"] == "bfloat16"
    assert data["decoding"] == {"temperature": 0.0}
    assert data["measured_runs"] == 5
    # all expected keys are present even if None
    for key in (
        "model", "base_url", "dtype", "quantization", "gpu_model",
        "vllm_version", "max_model_len", "max_num_seqs",
        "max_num_batched_tokens", "decoding", "warmup_runs",
        "measured_runs", "workload", "notes",
    ):
        assert key in data
