"""Tests for ``benchmarks.scripts.metrics_delta`` snapshot-delta logic."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.scripts import metrics_delta
from benchmarks.scripts._server_metrics import parse_prometheus_text


def _snap(ttft_sum: float, ttft_count: int) -> dict[str, list[dict[str, object]]]:
    text = (
        f'vllm:time_to_first_token_seconds_sum{{model_name="k"}} {ttft_sum}\n'
        f'vllm:time_to_first_token_seconds_count{{model_name="k"}} {ttft_count}\n'
    )
    return parse_prometheus_text(text)


def test_histogram_delta_mean_per_request() -> None:
    # Use values exactly representable in IEEE754 to keep == assertions safe:
    # 10.5 - 10.0 = 0.5, 0.5 / 2 = 0.25.
    pre = _snap(10.0, 100)
    post = _snap(10.5, 102)  # 2 more requests, +0.5s total -> 0.25s each
    block = metrics_delta.histogram_delta(pre, post, "vllm:time_to_first_token_seconds")
    assert block["delta_sum"] == 0.5
    assert block["delta_count"] == 2
    assert block["mean_seconds"] == 0.25
    assert block["count_unit"] == "request"
    assert block["note"] is None


def test_histogram_delta_no_observations_is_none() -> None:
    pre = _snap(10.0, 100)
    post = _snap(10.0, 100)  # no requests between snapshots
    block = metrics_delta.histogram_delta(pre, post, "vllm:time_to_first_token_seconds")
    assert block["delta_count"] == 0
    assert block["mean_seconds"] is None
    assert "no observations" in block["note"]


def test_histogram_delta_counter_reset_flagged() -> None:
    pre = _snap(10.0, 100)
    post = _snap(0.3, 1)  # counter went backwards (restart)
    block = metrics_delta.histogram_delta(pre, post, "vllm:time_to_first_token_seconds")
    assert block["mean_seconds"] is None
    assert "reset" in block["note"]


def test_histogram_delta_absent_histogram_is_none() -> None:
    pre = parse_prometheus_text('vllm:num_requests_running{model_name="k"} 0\n')
    post = parse_prometheus_text('vllm:num_requests_running{model_name="k"} 0\n')
    block = metrics_delta.histogram_delta(pre, post, "vllm:e2e_request_latency_seconds")
    assert block["mean_seconds"] is None
    assert "absent" in block["note"]


def test_inter_token_latency_counts_token_gaps() -> None:
    text_pre = (
        'vllm:inter_token_latency_seconds_sum{model_name="k"} 0.0\n'
        'vllm:inter_token_latency_seconds_count{model_name="k"} 0\n'
    )
    text_post = (
        'vllm:inter_token_latency_seconds_sum{model_name="k"} 0.5\n'
        'vllm:inter_token_latency_seconds_count{model_name="k"} 4\n'
    )
    block = metrics_delta.histogram_delta(
        parse_prometheus_text(text_pre),
        parse_prometheus_text(text_post),
        "vllm:inter_token_latency_seconds",
    )
    assert block["mean_seconds"] == 0.125  # 0.5 / 4, exactly representable
    assert block["count_unit"] == "token-gap"


def test_per_request_latencies_covers_all_histograms() -> None:
    pre = _snap(10.0, 100)
    post = _snap(10.5, 102)
    out = metrics_delta.per_request_latencies(pre, post)
    assert set(out) == set(metrics_delta.LATENCY_HISTOGRAMS)
    # The one histogram present is computed; the rest are flagged absent.
    assert out["vllm:time_to_first_token_seconds"]["mean_seconds"] == 0.25
    assert out["vllm:e2e_request_latency_seconds"]["mean_seconds"] is None


def test_outside_vllm_overhead_difference_and_none() -> None:
    assert metrics_delta.outside_vllm_overhead(0.65, 0.59) == 0.65 - 0.59
    assert metrics_delta.outside_vllm_overhead(None, 0.5) is None
    assert metrics_delta.outside_vllm_overhead(0.5, None) is None


def test_metrics_from_snapshot_accepts_full_and_bare() -> None:
    full = {"vllm": {"metrics": {"x": [{"labels": {}, "value": 1.0}]}}}
    bare = {"metrics": {"x": [{"labels": {}, "value": 1.0}]}}
    assert metrics_delta._metrics_from_snapshot(full) == full["vllm"]["metrics"]
    assert metrics_delta._metrics_from_snapshot(bare) == bare["metrics"]
    assert metrics_delta._metrics_from_snapshot({"nothing": True}) == {}


def test_build_delta_and_cli_roundtrip(tmp_path: Path) -> None:
    pre_obj = {"timestamp": "T0", "vllm": {"metrics": _snap(10.0, 100)}}
    post_obj = {"timestamp": "T1", "vllm": {"metrics": _snap(10.5, 102)}}
    pre_file = tmp_path / "pre.json"
    post_file = tmp_path / "post.json"
    out_file = tmp_path / "delta.json"
    pre_file.write_text(json.dumps(pre_obj), encoding="utf-8")
    post_file.write_text(json.dumps(post_obj), encoding="utf-8")

    rc = metrics_delta.main(
        ["--pre", str(pre_file), "--post", str(post_file), "--output", str(out_file)]
    )
    assert rc == 0
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["schema"] == "nanoserve-mini.metrics-delta.v1"
    assert saved["pre_timestamp"] == "T0"
    assert saved["post_timestamp"] == "T1"
    ttft = saved["per_request"]["vllm:time_to_first_token_seconds"]
    assert ttft["mean_seconds"] == 0.25
