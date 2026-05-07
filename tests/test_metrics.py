"""Tests for ``scripts._metrics``."""

from __future__ import annotations

import json

import pytest

from scripts._metrics import RunControls, get_git_commit, percentile, resolve_output_path, summarize


def test_percentile_single_value() -> None:
    assert percentile([5.0], 50.0) == 5.0
    assert percentile([5.0], 95.0) == 5.0


def test_percentile_known_values() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    # rank 50 -> index 1.5 -> 2 + 0.5*(3-2) = 2.5
    assert percentile(values, 50.0) == pytest.approx(2.5)
    assert percentile(values, 0.0) == 1.0
    assert percentile(values, 100.0) == 4.0


def test_percentile_empty_is_none() -> None:
    assert percentile([], 50.0) is None


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


def test_summarize_empty_uses_none_not_nan() -> None:
    summary = summarize([])
    assert summary["count"] == 0
    for key in ("min", "p50", "p95", "max", "mean"):
        assert summary[key] is None


def test_summarize_empty_round_trips_through_strict_json() -> None:
    """Strict JSON parsers reject NaN; ``None`` -> ``null`` survives a round-trip."""
    summary = summarize([])
    encoded = json.dumps(summary)  # default allow_nan=True wouldn't catch this
    encoded_strict = json.dumps(summary, allow_nan=False)
    decoded = json.loads(encoded_strict)
    assert decoded == summary
    assert "NaN" not in encoded


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
        run_id="r1",
        script_name="foo.py",
        git_commit="deadbeef",
    )
    data = controls.as_dict()
    assert data["model"] == "m"
    assert data["dtype"] == "bfloat16"
    assert data["decoding"] == {"temperature": 0.0}
    assert data["measured_runs"] == 5
    assert data["run_id"] == "r1"
    assert data["script_name"] == "foo.py"
    assert data["git_commit"] == "deadbeef"
    # all expected keys are present even if None
    for key in (
        "model", "base_url", "dtype", "quantization", "gpu_model",
        "vllm_version", "max_model_len", "max_num_seqs",
        "max_num_batched_tokens", "decoding", "warmup_runs",
        "measured_runs", "workload", "notes",
        "run_id", "script_name", "git_commit",
    ):
        assert key in data


def test_get_git_commit_returns_string_or_none() -> None:
    result = get_git_commit()
    assert result is None or isinstance(result, str)
    if result is not None:
        assert len(result) > 0


def test_resolve_output_path_explicit_wins() -> None:
    path = resolve_output_path(
        run_id="r1",
        explicit_path="/tmp/out.json",
        benchmark_mode="singlestream_lite_correctness",
        filename="result.json",
        fallback="results/raw/fallback.json",
    )
    assert path == "/tmp/out.json"


def test_resolve_output_path_run_id() -> None:
    path = resolve_output_path(
        run_id="run-001",
        explicit_path=None,
        benchmark_mode="singlestream_lite_latency",
        filename="result.json",
        fallback="results/raw/fallback.json",
    )
    assert path == "results/runs/run-001/singlestream_lite_latency/result.json"


def test_resolve_output_path_fallback() -> None:
    path = resolve_output_path(
        run_id=None,
        explicit_path=None,
        benchmark_mode="singlestream_lite_latency",
        filename="result.json",
        fallback="results/raw/fallback.json",
    )
    assert path == "results/raw/fallback.json"


def test_resolve_output_path_none_fallback() -> None:
    path = resolve_output_path(
        run_id=None,
        explicit_path=None,
        benchmark_mode="singlestream_lite_correctness",
        filename="result.json",
        fallback=None,
    )
    assert path is None
