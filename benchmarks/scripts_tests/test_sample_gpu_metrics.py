"""Tests for ``benchmarks.scripts.sample_gpu_metrics``."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from benchmarks.scripts import sample_gpu_metrics

_NVIDIA_SMI_TEXT = (
    "0, NVIDIA H200 NVL, 35, 12, 18000, 125000, 143000, 62, 350.5, 1980, 2619\n"
    "1, NVIDIA H200 NVL, 30, 10, 17000, 126000, 143000, 60, 340.0, 1900, 2619\n"
)


def _ok_runner(stdout: str = _NVIDIA_SMI_TEXT) -> Any:
    def runner(cmd: list[str], **kwargs: Any) -> Any:
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")
    return runner


class _FakeClock:
    """Monotonic perf clock that ticks by ``step`` per call."""

    def __init__(self, start: float = 0.0, step: float = 0.5) -> None:
        self.now = start
        self.step = step

    def __call__(self) -> float:
        v = self.now
        self.now += self.step
        return v


class _FakeWall:
    def __init__(self) -> None:
        self.now = 1700000000.0

    def __call__(self) -> float:
        v = self.now
        self.now += 1
        return v


def test_sample_loop_writes_one_row_per_gpu_per_tick(tmp_path: Path) -> None:
    sleeps: list[float] = []

    csv_path = tmp_path / "out.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(sample_gpu_metrics.CSV_COLUMNS))
        writer.writeheader()
        summary = sample_gpu_metrics.sample_loop(
            csv_writer=writer,
            interval_s=0.1,
            deadline_perf=None,
            max_samples=3,
            timeout=5.0,
            runner=_ok_runner(),
            sleeper=sleeps.append,
            perf_clock=_FakeClock(),
            wall_clock=_FakeWall(),
        )

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    assert summary["ticks"] == 3
    # Two GPUs * 3 ticks = 6 rows
    assert summary["samples_written"] == 6
    assert len(rows) == 6
    assert rows[0]["gpu_index"] == "0"
    assert rows[1]["gpu_index"] == "1"
    assert rows[0]["gpu_name"] == "NVIDIA H200 NVL"
    assert summary["errors"] == []
    # Sleep is skipped on the final iteration so we don't overshoot the budget
    assert len(sleeps) == 2


def test_sample_loop_records_runner_errors_without_killing_loop(tmp_path: Path) -> None:
    calls = {"n": 0}

    def flaky_runner(cmd: list[str], **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 2:
            raise FileNotFoundError("nvidia-smi: not found")
        return SimpleNamespace(returncode=0, stdout=_NVIDIA_SMI_TEXT, stderr="")

    csv_path = tmp_path / "out.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(sample_gpu_metrics.CSV_COLUMNS))
        writer.writeheader()
        summary = sample_gpu_metrics.sample_loop(
            csv_writer=writer,
            interval_s=0.1,
            deadline_perf=None,
            max_samples=3,
            timeout=5.0,
            runner=flaky_runner,
            sleeper=lambda _s: None,
            perf_clock=_FakeClock(),
            wall_clock=_FakeWall(),
        )

    assert summary["ticks"] == 3
    # 2 successful ticks * 2 GPUs = 4 rows; the failed tick contributes 0 rows
    assert summary["samples_written"] == 4
    assert len(summary["errors"]) == 1
    assert "command not found" in summary["errors"][0]


def test_sample_loop_stops_at_deadline(tmp_path: Path) -> None:
    csv_path = tmp_path / "out.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(sample_gpu_metrics.CSV_COLUMNS))
        writer.writeheader()
        # FakeClock with step=0.1 advances on every perf() call. The loop calls
        # perf() three times around each successful tick (top-of-loop check,
        # post-tick check, and the final duration capture). With deadline=0.5
        # and interval=0.2 the second tick's post-check sees 0.4+0.2=0.6 > 0.5
        # and breaks, giving exactly 2 ticks.
        summary = sample_gpu_metrics.sample_loop(
            csv_writer=writer,
            interval_s=0.2,
            deadline_perf=0.5,
            max_samples=None,
            timeout=5.0,
            runner=_ok_runner(),
            sleeper=lambda _s: None,
            perf_clock=_FakeClock(start=0.0, step=0.1),
            wall_clock=_FakeWall(),
        )
    assert summary["ticks"] == 2


def test_main_writes_csv_and_meta_with_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sample_gpu_metrics, "subprocess",
        SimpleNamespace(
            run=_ok_runner(),
            TimeoutExpired=Exception,
        ),
    )
    monkeypatch.setattr(sample_gpu_metrics.time, "sleep", lambda _s: None)

    import os
    orig_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        rc = sample_gpu_metrics.main([
            "--run-id", "run-samp",
            "--interval-ms", "10",
            "--samples", "2",
        ])
        assert rc == 0
    finally:
        os.chdir(orig_dir)

    base = tmp_path / "results" / "runs" / "run-samp" / "server_metrics"
    csv_path = base / "gpu_samples.csv"
    meta_path = base / "gpu_samples_meta.json"
    assert csv_path.exists()
    assert meta_path.exists()

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    # 2 GPUs * 2 ticks = 4 rows
    assert len(rows) == 4

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["schema"] == "nanoserve-mini.gpu-samples-meta.v1"
    assert meta["run_id"] == "run-samp"
    assert meta["interval_ms"] == 10
    assert meta["samples_requested"] == 2
    assert meta["summary"]["ticks"] == 2
    assert meta["summary"]["samples_written"] == 4
    assert meta["csv_columns"][:2] == ["timestamp_iso", "timestamp_unix"]


def test_main_rejects_zero_interval(capsys: pytest.CaptureFixture[str]) -> None:
    rc = sample_gpu_metrics.main([
        "--run-id", "x",
        "--interval-ms", "0",
        "--samples", "1",
    ])
    assert rc == 2
    assert "interval-ms" in capsys.readouterr().err


def test_main_rejects_zero_duration(capsys: pytest.CaptureFixture[str]) -> None:
    rc = sample_gpu_metrics.main([
        "--run-id", "x",
        "--interval-ms", "100",
        "--duration-s", "0",
    ])
    assert rc == 2
    assert "duration-s" in capsys.readouterr().err


def test_main_rejects_negative_duration(capsys: pytest.CaptureFixture[str]) -> None:
    rc = sample_gpu_metrics.main([
        "--run-id", "x",
        "--interval-ms", "100",
        "--duration-s", "-2.5",
    ])
    assert rc == 2
    assert "duration-s" in capsys.readouterr().err


def test_main_rejects_zero_samples(capsys: pytest.CaptureFixture[str]) -> None:
    rc = sample_gpu_metrics.main([
        "--run-id", "x",
        "--interval-ms", "100",
        "--samples", "0",
    ])
    assert rc == 2
    assert "samples" in capsys.readouterr().err


def test_main_rejects_negative_samples(capsys: pytest.CaptureFixture[str]) -> None:
    rc = sample_gpu_metrics.main([
        "--run-id", "x",
        "--interval-ms", "100",
        "--samples", "-3",
    ])
    assert rc == 2
    assert "samples" in capsys.readouterr().err


def test_main_rejects_when_neither_duration_nor_samples_given(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = sample_gpu_metrics.main(["--run-id", "x"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "duration-s" in err or "samples" in err


def test_main_meta_strict_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sample_gpu_metrics, "subprocess",
        SimpleNamespace(
            run=_ok_runner(),
            TimeoutExpired=Exception,
        ),
    )
    monkeypatch.setattr(sample_gpu_metrics.time, "sleep", lambda _s: None)

    csv_path = tmp_path / "samples.csv"
    rc = sample_gpu_metrics.main([
        "--output", str(csv_path),
        "--interval-ms", "10",
        "--samples", "1",
    ])
    assert rc == 0
    meta = csv_path.with_name(csv_path.stem + "_meta.json")
    raw = meta.read_text(encoding="utf-8")
    assert "NaN" not in raw
    assert "Infinity" not in raw
    json.loads(raw)
