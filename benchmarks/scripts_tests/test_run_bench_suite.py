"""Tests for ``benchmarks.scripts.run_bench_suite``."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from benchmarks.scripts import run_bench_suite


def _args(extra: list[str] | None = None) -> Any:
    argv = [
        "--base-url", "http://proxy:4000",
        "--metrics-base-url", "http://vllm:8000",
        "--model", "kimi-k2.6",
        "--api-key", "sk-test",
    ]
    if extra:
        argv.extend(extra)
    return run_bench_suite.parse_args(argv)


def test_slugify_model_is_path_friendly() -> None:
    assert run_bench_suite.slugify_model("moonshotai/Kimi-K2.6") == "moonshotai-kimi-k2-6"
    assert run_bench_suite.slugify_model("DeepSeek-V4-Flash") == "deepseek-v4-flash"


def test_generate_run_id_uses_next_number(tmp_path: Path) -> None:
    runs_root = tmp_path / "results" / "runs"
    (runs_root / "2026-05-17_moonshotai-kimi-k2-6_run-01").mkdir(parents=True)
    (runs_root / "2026-05-17_moonshotai-kimi-k2-6_run-09").mkdir()
    (runs_root / "2026-05-17_other-model_run-99").mkdir()

    run_id = run_bench_suite.generate_run_id(
        model="moonshotai/Kimi-K2.6",
        runs_root=runs_root,
        today="2026-05-17",
    )

    assert run_id == "2026-05-17_moonshotai-kimi-k2-6_run-10"


def test_run_suite_calls_steps_in_order_and_writes_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_step(name: str):
        def run(argv: list[str]) -> int:
            calls.append((name, list(argv)))
            return 0
        return run

    monkeypatch.setattr(run_bench_suite.collect_metrics_snapshot, "main", fake_step("snapshot"))
    monkeypatch.setattr(run_bench_suite.request_once, "main", fake_step("request"))
    monkeypatch.setattr(run_bench_suite.measure_ttft_once, "main", fake_step("ttft"))
    monkeypatch.setattr(run_bench_suite.run_sequential_benchmark, "main", fake_step("sequential"))

    orig_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        rc = run_bench_suite.run_suite(_args(), run_id="run-suite-01")
    finally:
        os.chdir(orig_dir)

    assert rc == 0
    assert [name for name, _argv in calls] == [
        "snapshot", "request", "ttft", "sequential", "snapshot",
    ]
    for _name, argv in calls:
        assert "--run-id" in argv
        assert argv[argv.index("--run-id") + 1] == "run-suite-01"
    request_argv = calls[1][1]
    assert request_argv[request_argv.index("--api-key") + 1] == "sk-test"
    sequential_argv = calls[3][1]
    assert sequential_argv[sequential_argv.index("--warmup") + 1] == "1"
    assert sequential_argv[sequential_argv.index("--runs") + 1] == "5"

    manifest_path = (
        tmp_path / "results" / "runs" / "run-suite-01" / "bench_suite" / "summary.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "nanoserve-mini.bench-suite.v1"
    assert manifest["completed"] is True
    assert manifest["error"] is None
    assert [step["name"] for step in manifest["steps"]] == [
        "snapshot_pre", "request_once", "measure_ttft_once",
        "run_sequential_benchmark", "snapshot_post",
    ]
    json.dumps(manifest, allow_nan=False)


def test_run_suite_runs_post_snapshot_after_client_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[str] = []

    def snapshot(argv: list[str]) -> int:
        calls.append("snapshot")
        return 0

    def request(argv: list[str]) -> int:
        calls.append("request")
        return 1

    def should_not_run(argv: list[str]) -> int:
        calls.append("unexpected")
        return 0

    monkeypatch.setattr(run_bench_suite.collect_metrics_snapshot, "main", snapshot)
    monkeypatch.setattr(run_bench_suite.request_once, "main", request)
    monkeypatch.setattr(run_bench_suite.measure_ttft_once, "main", should_not_run)
    monkeypatch.setattr(run_bench_suite.run_sequential_benchmark, "main", should_not_run)

    orig_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        rc = run_bench_suite.run_suite(_args(), run_id="run-suite-fail")
    finally:
        os.chdir(orig_dir)

    assert rc == 1
    assert calls == ["snapshot", "request", "snapshot"]
    manifest_path = (
        tmp_path / "results" / "runs" / "run-suite-fail" / "bench_suite" / "summary.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["completed"] is False
    assert manifest["error"] == "request_once exited with 1"
    assert [step["name"] for step in manifest["steps"]] == [
        "snapshot_pre", "request_once", "snapshot_post",
    ]


def test_run_suite_requires_api_key(capsys) -> None:
    args = run_bench_suite.parse_args([
        "--base-url", "http://proxy:4000",
        "--metrics-base-url", "http://vllm:8000",
        "--model", "kimi-k2.6",
        "--api-key", "",
    ])
    rc = run_bench_suite.run_suite(args, run_id="run-suite-no-key")
    assert rc == 2
    assert "api-key" in capsys.readouterr().err
