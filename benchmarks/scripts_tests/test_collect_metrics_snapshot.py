"""Tests for ``benchmarks.scripts.collect_metrics_snapshot``."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from benchmarks.scripts import _client, collect_metrics_snapshot

_VLLM_TEXT = """\
# HELP vllm:num_requests_running Running.
# TYPE vllm:num_requests_running gauge
vllm:num_requests_running{model_name="kimi"} 1.0
vllm:kv_cache_usage_perc{model_name="kimi"} 0.42
vllm:prefix_cache_queries_total{model_name="kimi"} 200
vllm:prefix_cache_hits_total{model_name="kimi"} 110
"""

_NVIDIA_SMI_TEXT = (
    "0, NVIDIA H200 NVL, 35, 12, 18000, 125000, 143000, 62, 350.5, 1980, 2619\n"
)


def _vllm_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        text=_VLLM_TEXT,
        headers={"content-type": "text/plain; version=0.0.4"},
    )


def _patch_httpx(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs.pop("timeout", None)
        return real_client_cls(transport=transport)

    # The snapshot script uses httpx directly; patch the module attr it imports.
    monkeypatch.setattr(collect_metrics_snapshot.httpx, "Client", fake_client)
    # Be safe in case any indirection touches the shared client module too.
    monkeypatch.setattr(_client.httpx, "Client", fake_client, raising=False)


def _ok_runner(stdout: str = _NVIDIA_SMI_TEXT) -> Any:
    def runner(cmd: list[str], **kwargs: Any) -> Any:
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")
    return runner


def test_scrape_vllm_metrics_parses_when_endpoint_responds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _vllm_handler)
    block = collect_metrics_snapshot.scrape_vllm_metrics("http://x")
    assert block["scrape_ok"] is True
    assert block["scrape_error"] is None
    assert block["metrics"]["vllm:kv_cache_usage_perc"][0]["value"] == 0.42


def test_scrape_vllm_metrics_records_failure_on_5xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def bad_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")
    _patch_httpx(monkeypatch, bad_handler)
    block = collect_metrics_snapshot.scrape_vllm_metrics("http://x")
    assert block["scrape_ok"] is False
    assert "HTTPStatusError" in (block["scrape_error"] or "")
    assert block["metrics"] == {}


def test_run_nvidia_smi_returns_rows_on_success() -> None:
    block = collect_metrics_snapshot.run_nvidia_smi(runner=_ok_runner())
    assert block["available"] is True
    assert block["error"] is None
    assert len(block["rows"]) == 1
    assert block["rows"][0]["gpu_index"] == 0


def test_run_nvidia_smi_handles_missing_command() -> None:
    def runner(cmd: list[str], **kwargs: Any) -> Any:
        raise FileNotFoundError("nvidia-smi: not found")
    block = collect_metrics_snapshot.run_nvidia_smi(runner=runner)
    assert block["available"] is False
    assert "command not found" in (block["error"] or "")
    assert block["rows"] == []


def test_run_nvidia_smi_handles_nonzero_exit() -> None:
    def runner(cmd: list[str], **kwargs: Any) -> Any:
        return SimpleNamespace(returncode=9, stdout="", stderr="ECC error")
    block = collect_metrics_snapshot.run_nvidia_smi(runner=runner)
    assert block["available"] is False
    assert "exit 9" in (block["error"] or "")
    assert "ECC error" in (block["error"] or "")


def test_run_nvidia_smi_handles_timeout() -> None:
    def runner(cmd: list[str], **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)
    block = collect_metrics_snapshot.run_nvidia_smi(runner=runner)
    assert block["available"] is False
    assert "timeout" in (block["error"] or "").lower()


def test_build_snapshot_aggregate_joins_vllm_and_gpu() -> None:
    from benchmarks.scripts._server_metrics import parse_nvidia_smi_csv, parse_prometheus_text

    vllm_block = {
        "endpoint": "http://x/metrics",
        "scrape_ok": True,
        "scrape_error": None,
        "metrics": parse_prometheus_text(_VLLM_TEXT),
    }
    gpu_block = {
        "available": True,
        "command": [],
        "rows": parse_nvidia_smi_csv(_NVIDIA_SMI_TEXT),
        "error": None,
    }
    snapshot = collect_metrics_snapshot.build_snapshot(
        run_id="r1", run_uuid="u1", phase="pre",
        base_url="http://x", notes=None,
        vllm_block=vllm_block, gpu_block=gpu_block,
    )
    assert snapshot["aggregate"]["kv_cache_usage"] == 0.42
    assert snapshot["aggregate"]["prefix_cache_hit_rate"] == 0.55
    # 18000 MiB / 1024 = 17.578 GiB
    assert snapshot["aggregate"]["gpu_memory_used_gb"] == round(18000 / 1024.0, 3)
    assert snapshot["schema"] == "nanoserve-mini.server-metrics-snapshot.v1"
    assert snapshot["phase"] == "pre"
    assert snapshot["run_id"] == "r1"


def test_main_writes_snapshot_with_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_httpx(monkeypatch, _vllm_handler)
    monkeypatch.setattr(
        collect_metrics_snapshot, "subprocess",
        SimpleNamespace(
            run=_ok_runner(),
            TimeoutExpired=subprocess.TimeoutExpired,
        ),
    )
    # We patched the `subprocess` module reference inside the script, so
    # `run_nvidia_smi` defaults must pick up the fake.
    orig_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        rc = collect_metrics_snapshot.main([
            "--base-url", "http://x",
            "--run-id", "run-snap",
            "--phase", "pre",
        ])
        assert rc == 0
    finally:
        os.chdir(orig_dir)

    expected = (
        tmp_path / "results" / "runs" / "run-snap" / "server_metrics" / "snapshot_pre.json"
    )
    assert expected.exists()
    snap = json.loads(expected.read_text(encoding="utf-8"))
    assert snap["schema"] == "nanoserve-mini.server-metrics-snapshot.v1"
    assert snap["phase"] == "pre"
    assert snap["run_id"] == "run-snap"
    assert snap["vllm"]["scrape_ok"] is True
    assert snap["gpu"]["available"] is True
    assert snap["aggregate"]["kv_cache_usage"] == 0.42

    out = capsys.readouterr().out
    assert "saved:" in out
    assert "aggregate:" in out


def test_main_writes_snapshot_when_vllm_unreachable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refusing(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")
    _patch_httpx(monkeypatch, refusing)
    monkeypatch.setattr(
        collect_metrics_snapshot, "subprocess",
        SimpleNamespace(
            run=_ok_runner(),
            TimeoutExpired=subprocess.TimeoutExpired,
        ),
    )
    output = tmp_path / "snap.json"
    rc = collect_metrics_snapshot.main([
        "--base-url", "http://nope",
        "--output", str(output),
        "--phase", "post",
    ])
    assert rc == 0
    assert output.exists()
    snap = json.loads(output.read_text(encoding="utf-8"))
    assert snap["vllm"]["scrape_ok"] is False
    assert "ConnectError" in (snap["vllm"]["scrape_error"] or "")
    # GPU side still populated; aggregate has GPU memory but null KV/prefix
    assert snap["aggregate"]["gpu_memory_used_gb"] is not None
    assert snap["aggregate"]["kv_cache_usage"] is None


def test_main_strict_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _vllm_handler)
    monkeypatch.setattr(
        collect_metrics_snapshot, "subprocess",
        SimpleNamespace(
            run=_ok_runner(),
            TimeoutExpired=subprocess.TimeoutExpired,
        ),
    )
    output = tmp_path / "snap.json"
    collect_metrics_snapshot.main([
        "--base-url", "http://x",
        "--output", str(output),
    ])
    raw = output.read_text(encoding="utf-8")
    assert "NaN" not in raw
    assert "Infinity" not in raw
    json.loads(raw)
