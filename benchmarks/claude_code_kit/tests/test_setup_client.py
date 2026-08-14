"""Tests for setup_client.py — offline, fake runners, fake HOME."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import setup_client


def _make_kit(tmp_path: Path, monkeypatch) -> Path:
    """Point setup_client at a fake kit directory."""
    kit = tmp_path / "kit"
    userdir = kit / "userdir" / ".claude"
    userdir.mkdir(parents=True)
    (userdir / "settings.json").write_text('{"kit": true}\n', encoding="utf-8")
    (kit / "claude.bat").write_text("@echo off\r\n", encoding="utf-8")
    config = {
        "model": "qwen-coder",
        "smoke_prompt": "Zaplanuj prace",
        "env": {"ANTHROPIC_BASE_URL": "http://gw:4000", "ANTHROPIC_MODEL": "qwen-coder"},
    }
    (kit / "kit_config.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(setup_client, "_KIT_DIR", kit)
    return kit


def _ok_runner(calls: list):
    def runner(command, capture_output=True, text=True, timeout=None):
        calls.append({"command": command, "timeout": timeout})
        return SimpleNamespace(returncode=0, stdout="plan: ...", stderr="")

    return runner


# ---------------------------------------------------------------------------
# install_userdir
# ---------------------------------------------------------------------------


def test_install_userdir_copies_config(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path, monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    target, backup = setup_client.install_userdir(kit / "userdir" / ".claude", home=home)
    assert backup is None
    assert (target / "settings.json").read_text(encoding="utf-8") == '{"kit": true}\n'


def test_install_userdir_backs_up_existing(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path, monkeypatch)
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "old.json").write_text("old\n", encoding="utf-8")
    now = datetime(2026, 8, 14, 12, 30, 45)
    target, backup = setup_client.install_userdir(
        kit / "userdir" / ".claude", home=home, now=now
    )
    assert backup == home / ".claude.backup-20260814-123045"
    assert (backup / "old.json").read_text(encoding="utf-8") == "old\n"
    assert (target / "settings.json").is_file()


def test_install_userdir_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        setup_client.install_userdir(tmp_path / "missing", home=tmp_path)


# ---------------------------------------------------------------------------
# persist_env / run_smoke
# ---------------------------------------------------------------------------


def test_persist_env_calls_setx_per_var():
    calls: list = []
    failed = setup_client.persist_env(
        {"A": "1", "B": "2"},
        runner=lambda cmd, **kw: (calls.append(cmd), SimpleNamespace(returncode=0))[1],
    )
    assert failed == []
    assert calls == [["setx", "A", "1"], ["setx", "B", "2"]]


def test_persist_env_reports_failures():
    def runner(cmd, **kw):
        return SimpleNamespace(returncode=1 if cmd[1] == "B" else 0, stdout="", stderr="")

    failed = setup_client.persist_env({"A": "1", "B": "2"}, runner=runner)
    assert failed == ["B"]


def test_run_smoke_success(tmp_path):
    calls: list = []
    code = setup_client.run_smoke(
        tmp_path,
        model="qwen-coder",
        prompt="Zaplanuj prace",
        timeout=5.0,
        runner=_ok_runner(calls),
        log=lambda _msg: None,
    )
    assert code == 0
    (call,) = calls
    assert call["command"] == [
        str(tmp_path / "claude.bat"),
        "--model",
        "qwen-coder",
        "-p",
        "Zaplanuj prace",
    ]
    assert call["timeout"] == 5.0


def test_run_smoke_failure_exit_code(tmp_path):
    def runner(command, **kw):
        return SimpleNamespace(returncode=3, stdout="", stderr="connection refused")

    messages: list[str] = []
    code = setup_client.run_smoke(
        tmp_path,
        model="m",
        prompt="p",
        timeout=5.0,
        runner=runner,
        log=messages.append,
    )
    assert code == 1
    assert any("connection refused" in message for message in messages)


def test_run_smoke_timeout(tmp_path):
    def runner(command, **kw):
        raise subprocess.TimeoutExpired(cmd=command, timeout=kw.get("timeout"))

    messages: list[str] = []
    code = setup_client.run_smoke(
        tmp_path, model="m", prompt="p", timeout=1.0, runner=runner, log=messages.append
    )
    assert code == 1
    assert any("TIMEOUT" in message for message in messages)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_full_flow(tmp_path, monkeypatch):
    _make_kit(tmp_path, monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    calls: list = []
    monkeypatch.setattr(setup_client, "_run", _ok_runner(calls))
    code = setup_client.main(["--home", str(home)])
    assert code == 0
    assert (home / ".claude" / "settings.json").is_file()
    assert len(calls) == 1  # smoke test only, no setx without --persist
    assert calls[0]["command"][1:] == ["--model", "qwen-coder", "-p", "Zaplanuj prace"]


def test_main_persist_runs_setx(tmp_path, monkeypatch):
    _make_kit(tmp_path, monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    commands: list = []

    def runner(command, capture_output=True, text=True, timeout=None):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(setup_client, "_run", runner)
    code = setup_client.main(["--home", str(home), "--persist", "--skip-smoke"])
    assert code == 0
    assert ["setx", "ANTHROPIC_BASE_URL", "http://gw:4000"] in commands
    assert ["setx", "ANTHROPIC_MODEL", "qwen-coder"] in commands


def test_main_skip_userdir_leaves_home_alone(tmp_path, monkeypatch):
    _make_kit(tmp_path, monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(setup_client, "_run", _ok_runner([]))
    code = setup_client.main(["--home", str(home), "--skip-userdir", "--skip-smoke"])
    assert code == 0
    assert not (home / ".claude").exists()


def test_main_broken_kit_config(tmp_path, monkeypatch, capsys):
    kit = tmp_path / "kit"
    kit.mkdir()
    monkeypatch.setattr(setup_client, "_KIT_DIR", kit)
    code = setup_client.main(["--home", str(tmp_path)])
    assert code == 2
    assert "kit_config.json" in capsys.readouterr().err
