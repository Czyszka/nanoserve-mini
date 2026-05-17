"""Tests for ``benchmarks.scripts._server_metrics`` parsers."""

from __future__ import annotations

from benchmarks.scripts._server_metrics import (
    NVIDIA_SMI_QUERY_FIELDS,
    first_value,
    parse_nvidia_smi_csv,
    parse_prometheus_text,
    select_vllm_aggregate,
    total_gpu_memory_used_gb,
)

_VLLM_SAMPLE = """\
# HELP vllm:num_requests_running Running.
# TYPE vllm:num_requests_running gauge
vllm:num_requests_running{model_name="kimi"} 2.0
# HELP vllm:gpu_cache_usage_perc KV cache usage.
# TYPE vllm:gpu_cache_usage_perc gauge
vllm:gpu_cache_usage_perc{model_name="kimi"} 0.45
vllm:gpu_prefix_cache_hit_rate{model_name="kimi"} 0.78
vllm:prompt_tokens_total{model_name="kimi"} 12345
vllm:e2e_request_latency_seconds_bucket{le="0.5",model_name="kimi"} 100
vllm:e2e_request_latency_seconds_bucket{le="+Inf",model_name="kimi"} 200
vllm:weird_value{model_name="kimi"} NaN
broken line
"""


def test_parse_prometheus_text_basic_gauges() -> None:
    metrics = parse_prometheus_text(_VLLM_SAMPLE)
    assert metrics["vllm:num_requests_running"][0]["value"] == 2.0
    assert metrics["vllm:num_requests_running"][0]["labels"] == {"model_name": "kimi"}
    assert metrics["vllm:gpu_cache_usage_perc"][0]["value"] == 0.45
    assert metrics["vllm:gpu_prefix_cache_hit_rate"][0]["value"] == 0.78
    assert metrics["vllm:prompt_tokens_total"][0]["value"] == 12345


def test_parse_prometheus_text_handles_histogram_buckets_and_inf() -> None:
    metrics = parse_prometheus_text(_VLLM_SAMPLE)
    buckets = metrics["vllm:e2e_request_latency_seconds_bucket"]
    assert len(buckets) == 2
    le_values = {b["labels"]["le"] for b in buckets}
    assert le_values == {"0.5", "+Inf"}
    # +Inf and NaN are converted to None (strict-JSON friendly)
    nan_metric = metrics["vllm:weird_value"][0]
    assert nan_metric["value"] is None


def test_parse_prometheus_text_skips_malformed_lines() -> None:
    metrics = parse_prometheus_text(_VLLM_SAMPLE)
    # The "broken line" should be silently dropped
    assert "broken" not in metrics
    assert "line" not in metrics


def test_first_value_returns_first_numeric_or_none() -> None:
    metrics = parse_prometheus_text(_VLLM_SAMPLE)
    assert first_value(metrics, "vllm:gpu_cache_usage_perc") == 0.45
    assert first_value(metrics, "does_not_exist") is None
    # NaN value falls through to None
    assert first_value(metrics, "vllm:weird_value") is None


def test_select_vllm_aggregate_uses_caller_supplied_gpu_memory() -> None:
    metrics = parse_prometheus_text(_VLLM_SAMPLE)
    agg = select_vllm_aggregate(metrics, gpu_memory_used_gb=137.5)
    assert agg["gpu_memory_used_gb"] == 137.5
    assert agg["kv_cache_usage"] == 0.45
    assert agg["prefix_cache_hit_rate"] == 0.78


def test_select_vllm_aggregate_handles_missing_keys() -> None:
    agg = select_vllm_aggregate({}, gpu_memory_used_gb=None)
    assert agg == {
        "gpu_memory_used_gb": None,
        "kv_cache_usage": None,
        "prefix_cache_hit_rate": None,
    }


_NVIDIA_SMI_SAMPLE = (
    "0, NVIDIA H200 NVL, 35, 12, 18000, 125000, 143000, 62, 350.5, 1980, 2619\n"
    "1, NVIDIA H200 NVL, [Not Supported], 0, 1024, 142000, 143000, 50, 70.0, 210, 2619\n"
)


def test_parse_nvidia_smi_csv_basic() -> None:
    rows = parse_nvidia_smi_csv(_NVIDIA_SMI_SAMPLE)
    assert len(rows) == 2
    first = rows[0]
    assert first["gpu_index"] == 0
    assert first["gpu_name"] == "NVIDIA H200 NVL"
    assert first["utilization_gpu_pct"] == 35.0
    assert first["memory_used_mib"] == 18000.0
    assert first["temperature_c"] == 62.0
    assert first["power_draw_w"] == 350.5

    second = rows[1]
    # "[Not Supported]" must become None, not raise
    assert second["utilization_gpu_pct"] is None
    assert second["memory_used_mib"] == 1024.0


def test_parse_nvidia_smi_csv_skips_short_rows() -> None:
    bad = "0, NVIDIA H200 NVL\n0, name, 1, 2, 3, 4, 5, 6, 7, 8, 9\n"
    rows = parse_nvidia_smi_csv(bad)
    assert len(rows) == 1
    assert rows[0]["gpu_index"] == 0


def test_total_gpu_memory_used_gb_sums_visible_rows() -> None:
    rows = parse_nvidia_smi_csv(_NVIDIA_SMI_SAMPLE)
    # 18000 + 1024 = 19024 MiB -> 19024 / 1024 = 18.578... GiB rounded to 3 dp
    assert total_gpu_memory_used_gb(rows) == round(19024 / 1024.0, 3)


def test_total_gpu_memory_used_gb_returns_none_for_no_data() -> None:
    assert total_gpu_memory_used_gb([]) is None
    assert total_gpu_memory_used_gb([{"memory_used_mib": None}]) is None


def test_nvidia_smi_query_fields_match_csv_columns() -> None:
    """Every queried field must end up in the exported CSV column list."""
    from benchmarks.scripts._server_metrics import CSV_COLUMNS, NVIDIA_SMI_FIELD_MAP

    for field in NVIDIA_SMI_QUERY_FIELDS:
        assert NVIDIA_SMI_FIELD_MAP[field] in CSV_COLUMNS
    assert CSV_COLUMNS[0] == "timestamp_iso"
    assert CSV_COLUMNS[1] == "timestamp_unix"
