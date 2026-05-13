"""Tests for ``scripts.run_coding_agent_task``."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import run_coding_agent_task as harness

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_task(
    root: Path,
    task_id: str,
    *,
    task_md: str = (
        "# Task\n\nblah\n\n## Agent prompt\n\nDo the thing.\n\n## Notes\n\nignored\n"
    ),
    starter_files: dict[str, str] | None = None,
    include_public: bool = True,
    public_exit: int = 0,
    include_hidden: bool = True,
    hidden_exit: int = 0,
) -> Path:
    task_dir = root / task_id
    (task_dir / harness.STARTER_SUBDIR).mkdir(parents=True)
    (task_dir / harness.STARTER_SUBDIR / "starter.py").write_text(
        (starter_files or {}).get("starter.py", "x = 1\n"), encoding="utf-8"
    )
    (task_dir / "TASK.md").write_text(task_md, encoding="utf-8")
    (task_dir / "README.md").write_text("readme\n", encoding="utf-8")
    if include_public:
        (task_dir / harness.PUBLIC_SUBDIR).mkdir()
        (task_dir / harness.PUBLIC_SUBDIR / "run.sh").write_text(
            f"#!/bin/sh\nexit {public_exit}\n", encoding="utf-8"
        )
    if include_hidden:
        (task_dir / harness.HIDDEN_SUBDIR).mkdir()
        (task_dir / harness.HIDDEN_SUBDIR / "run.sh").write_text(
            f"#!/bin/sh\nexit {hidden_exit}\n", encoding="utf-8"
        )
    return task_dir


def _now_iter() -> Any:
    seq = [
        datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        datetime(2026, 1, 1, 12, 0, 5, tzinfo=UTC),
        datetime(2026, 1, 1, 12, 0, 6, tzinfo=UTC),
        datetime(2026, 1, 1, 12, 0, 7, tzinfo=UTC),
    ]
    i = {"n": 0}

    def now() -> datetime:
        v = seq[min(i["n"], len(seq) - 1)]
        i["n"] += 1
        return v
    return now


def _fake_git_runner() -> Any:
    """Real git is fine but slow. Stub returncode=0 and synthesize commits."""
    state = {"commits": 0, "head": "0" * 40}

    def runner(cmd: list[str], **kwargs: Any) -> Any:
        # cmd is like ["git", "init", "-q"]
        sub = cmd[1] if len(cmd) > 1 else ""
        stdout = ""
        if sub == "commit":
            state["commits"] += 1
            state["head"] = format(state["commits"], "040x")
        elif sub == "rev-parse":
            stdout = state["head"] + "\n"
        elif sub == "diff":
            stdout = "a.py\nb.py\n"  # 2 changed files
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")
    return runner


def _runner_factory(
    *,
    agent_exit: int = 0,
    agent_stdout: str = "",
    agent_stderr: str = "",
    agent_timeout: bool = False,
    public_exit: int = 0,
    hidden_exit: int = 0,
    test_runner_missing: bool = False,
) -> Any:
    def runner(cmd: list[str], **kwargs: Any) -> Any:
        # Distinguish: agent commands have no run.sh path; test runners do.
        is_test_runner = any(
            "run.sh" in part or "run.ps1" in part for part in cmd
        )
        if is_test_runner:
            if test_runner_missing:
                raise FileNotFoundError("no bash")
            # Determine public vs hidden by cwd containing 'hidden'
            cwd = str(kwargs.get("cwd", ""))
            rc = hidden_exit if "hidden" in cwd else public_exit
            return SimpleNamespace(returncode=rc, stdout="ok", stderr="")
        # agent
        if agent_timeout:
            raise subprocess.TimeoutExpired(
                cmd=cmd,
                timeout=kwargs.get("timeout", 1.0),
                output=agent_stdout,
                stderr=agent_stderr,
            )
        return SimpleNamespace(
            returncode=agent_exit, stdout=agent_stdout, stderr=agent_stderr
        )
    return runner


def _recording_runner_factory(
    calls: list[dict[str, Any]],
    *,
    agent_exit: int = 0,
    public_exit: int = 0,
    hidden_exit: int = 0,
) -> Any:
    def runner(cmd: list[str], **kwargs: Any) -> Any:
        calls.append({"cmd": cmd, "cwd": str(kwargs.get("cwd", ""))})
        is_test_runner = any(
            "run.sh" in part or "run.ps1" in part for part in cmd
        )
        if is_test_runner:
            cwd = str(kwargs.get("cwd", ""))
            rc = hidden_exit if "hidden" in cwd else public_exit
            return SimpleNamespace(returncode=rc, stdout="ok", stderr="")
        return SimpleNamespace(returncode=agent_exit, stdout="", stderr="")

    return runner


def _no_metrics(**kwargs: Any) -> dict[str, Any]:
    return {
        "server_metrics_path": str(Path(kwargs["out_dir"]) / "stub.json"),
        "nvidia_smi_path": None,
        "errors": [],
    }


def _args(
    *,
    tasks_root: Path,
    task_id: str = "task-01",
    work_dir: Path | None = None,
    run_id: str = "run-x",
    timeout_s: float = 30.0,
    require_hidden: bool = False,
    skip_server_metrics: bool = True,
    agent_command: str = "fake-agent {prompt}",
    notes: str | None = None,
) -> Any:
    return SimpleNamespace(
        task_id=task_id,
        agent="fake",
        agent_command=agent_command,
        model="m1",
        base_url="http://x",
        run_id=run_id,
        work_dir=str(work_dir) if work_dir else None,
        timeout_s=timeout_s,
        skip_server_metrics=skip_server_metrics,
        require_hidden=require_hidden,
        tasks_root=str(tasks_root),
        agent_version=None,
        notes=notes,
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01")
    work = tmp_path / "work"
    monkeypatch.chdir(tmp_path)

    rc = harness.run_one(
        _args(tasks_root=tasks, work_dir=work),
        now=_now_iter(),
        runner=_runner_factory(agent_exit=0, public_exit=0, hidden_exit=0),
        git_runner=_fake_git_runner(),
        server_metrics_collector=_no_metrics,
    )
    assert rc == harness.EXIT_OK
    results = _read_jsonl(tmp_path / "results/runs/run-x/coding_agent_eval/results.jsonl")
    assert len(results) == 1
    row = results[0]
    assert row["agent_exit_code"] == 0
    assert row["timed_out"] is False
    assert row["public_tests"]["ran"] is True
    assert row["public_tests"]["exit_code"] == 0
    assert row["hidden_tests"]["ran"] is True
    assert row["hidden_tests"]["exit_code"] == 0
    # strict JSON re-dumps OK
    json.dumps(row, allow_nan=False)


def test_agent_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01")
    monkeypatch.chdir(tmp_path)

    rc = harness.run_one(
        _args(tasks_root=tasks, work_dir=tmp_path / "w"),
        now=_now_iter(),
        runner=_runner_factory(agent_timeout=True),
        git_runner=_fake_git_runner(),
        server_metrics_collector=_no_metrics,
    )
    assert rc == harness.EXIT_AGENT_TIMEOUT
    results = _read_jsonl(tmp_path / "results/runs/run-x/coding_agent_eval/results.jsonl")
    row = results[0]
    assert row["timed_out"] is True
    assert row["agent_exit_code"] is None
    assert row["public_tests"]["ran"] is False
    assert row["hidden_tests"]["ran"] is False


def test_agent_command_receives_prompt_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01")
    monkeypatch.chdir(tmp_path)
    calls: list[dict[str, Any]] = []

    rc = harness.run_one(
        _args(
            tasks_root=tasks,
            work_dir=tmp_path / "w",
            agent_command="fake-agent --prompt {prompt}",
        ),
        now=_now_iter(),
        runner=_recording_runner_factory(calls),
        git_runner=_fake_git_runner(),
        server_metrics_collector=_no_metrics,
    )

    assert rc == harness.EXIT_OK
    assert calls[0]["cmd"] == ["fake-agent", "--prompt", "Do the thing.\n"]


def test_agent_command_receives_absolute_prompt_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01")
    monkeypatch.chdir(tmp_path)
    calls: list[dict[str, Any]] = []

    rc = harness.run_one(
        _args(
            tasks_root=tasks,
            work_dir=tmp_path / "w",
            agent_command="fake-agent --prompt-file {prompt_file}",
        ),
        now=_now_iter(),
        runner=_recording_runner_factory(calls),
        git_runner=_fake_git_runner(),
        server_metrics_collector=_no_metrics,
    )

    assert rc == harness.EXIT_OK
    prompt_file = Path(calls[0]["cmd"][-1])
    assert prompt_file.is_absolute()
    assert prompt_file.read_text(encoding="utf-8") == "Do the thing.\n"


def test_agent_command_windows_split_preserves_backslashes(tmp_path: Path) -> None:
    prompt_path = tmp_path / "results" / "runs" / "run-x" / "prompt.txt"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("prompt\n", encoding="utf-8")

    cmd = harness._build_agent_command(
        "fake-agent --prompt-file {prompt_file}",
        prompt_path=prompt_path,
        prompt_body="prompt\n",
        posix=False,
    )

    assert cmd == ["fake-agent", "--prompt-file", str(prompt_path.resolve())]


def test_agent_launch_error_returns_harness_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01")
    monkeypatch.chdir(tmp_path)

    def missing_agent(cmd: list[str], **kwargs: Any) -> Any:
        raise FileNotFoundError("fake-agent")

    rc = harness.run_one(
        _args(tasks_root=tasks, work_dir=tmp_path / "w"),
        now=_now_iter(),
        runner=missing_agent,
        git_runner=_fake_git_runner(),
        server_metrics_collector=_no_metrics,
    )

    assert rc == harness.EXIT_HARNESS_ERROR
    row = _read_jsonl(
        tmp_path / "results/runs/run-x/coding_agent_eval/results.jsonl"
    )[0]
    assert row["error"].startswith("agent command not found:")


def test_public_tests_run_from_fresh_canonical_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01")
    work = tmp_path / "w"
    monkeypatch.chdir(tmp_path)
    calls: list[dict[str, Any]] = []

    def runner(cmd: list[str], **kwargs: Any) -> Any:
        calls.append({"cmd": cmd, "cwd": str(kwargs.get("cwd", ""))})
        is_test_runner = any(
            "run.sh" in part or "run.ps1" in part for part in cmd
        )
        if not is_test_runner:
            mutable_public_runner = work / harness.PUBLIC_SUBDIR / "run.sh"
            mutable_public_runner.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    rc = harness.run_one(
        _args(tasks_root=tasks, work_dir=work),
        now=_now_iter(),
        runner=runner,
        git_runner=_fake_git_runner(),
        server_metrics_collector=_no_metrics,
    )

    assert rc == harness.EXIT_OK
    test_cwds = [
        call["cwd"]
        for call in calls
        if any("run.sh" in part or "run.ps1" in part for part in call["cmd"])
    ]
    assert str(work / harness.PUBLIC_SUBDIR) not in test_cwds
    assert any(str(work) + "__public" == cwd for cwd in test_cwds)


def test_test_failures_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01")
    monkeypatch.chdir(tmp_path)

    rc = harness.run_one(
        _args(tasks_root=tasks, work_dir=tmp_path / "w"),
        now=_now_iter(),
        runner=_runner_factory(agent_exit=0, public_exit=1, hidden_exit=2),
        git_runner=_fake_git_runner(),
        server_metrics_collector=_no_metrics,
    )
    assert rc == harness.EXIT_OK
    row = _read_jsonl(tmp_path / "results/runs/run-x/coding_agent_eval/results.jsonl")[0]
    assert row["public_tests"]["exit_code"] == 1
    assert row["hidden_tests"]["exit_code"] == 2


def test_no_hidden_dir_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01", include_hidden=False)
    monkeypatch.chdir(tmp_path)

    rc = harness.run_one(
        _args(tasks_root=tasks, work_dir=tmp_path / "w"),
        now=_now_iter(),
        runner=_runner_factory(),
        git_runner=_fake_git_runner(),
        server_metrics_collector=_no_metrics,
    )
    assert rc == harness.EXIT_OK
    row = _read_jsonl(tmp_path / "results/runs/run-x/coding_agent_eval/results.jsonl")[0]
    assert row["hidden_tests"]["ran"] is False


def test_no_hidden_with_require_hidden_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01", include_hidden=False)
    monkeypatch.chdir(tmp_path)

    rc = harness.run_one(
        _args(tasks_root=tasks, work_dir=tmp_path / "w", require_hidden=True),
        now=_now_iter(),
        runner=_runner_factory(),
        git_runner=_fake_git_runner(),
        server_metrics_collector=_no_metrics,
    )
    assert rc == harness.EXIT_HARNESS_ERROR


def test_agent_prompt_extraction() -> None:
    md = (
        "# Title\n\nintro\n\n"
        "## Agent prompt\n\nPlease build X.\nAnd Y.\n\n"
        "## Hidden notes\n\nshould not appear\n"
    )
    out = harness._extract_agent_prompt(md)
    assert "Please build X." in out
    assert "And Y." in out
    assert "should not appear" not in out


def test_agent_prompt_missing_uses_full_md() -> None:
    md = "# Title\n\nNo headings of that form here.\n"
    out = harness._extract_agent_prompt(md)
    assert out == md


def test_results_jsonl_appended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01")
    monkeypatch.chdir(tmp_path)

    args1 = _args(tasks_root=tasks, work_dir=tmp_path / "w1")
    args2 = _args(tasks_root=tasks, work_dir=tmp_path / "w2")
    for args in (args1, args2):
        harness.run_one(
            args,
            now=_now_iter(),
            runner=_runner_factory(),
            git_runner=_fake_git_runner(),
            server_metrics_collector=_no_metrics,
        )
    rows = _read_jsonl(
        tmp_path / "results/runs/run-x/coding_agent_eval/results.jsonl"
    )
    assert len(rows) == 2


def test_skip_server_metrics_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01")
    monkeypatch.chdir(tmp_path)

    called = {"n": 0}

    def metrics_fn(**kwargs: Any) -> dict[str, Any]:
        called["n"] += 1
        return {"server_metrics_path": "x", "nvidia_smi_path": None, "errors": []}

    rc = harness.run_one(
        _args(tasks_root=tasks, work_dir=tmp_path / "w", skip_server_metrics=True),
        now=_now_iter(),
        runner=_runner_factory(),
        git_runner=_fake_git_runner(),
        server_metrics_collector=metrics_fn,
    )
    assert rc == harness.EXIT_OK
    assert called["n"] == 0
    row = _read_jsonl(
        tmp_path / "results/runs/run-x/coding_agent_eval/results.jsonl"
    )[0]
    assert row["server_metrics"]["skipped"] is True
    assert row["server_metrics"]["pre"] is None
    assert row["server_metrics"]["post"] is None


def test_strict_json_serializable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01")
    monkeypatch.chdir(tmp_path)

    harness.run_one(
        _args(tasks_root=tasks, work_dir=tmp_path / "w", notes=None),
        now=_now_iter(),
        runner=_runner_factory(),
        git_runner=_fake_git_runner(),
        server_metrics_collector=_no_metrics,
    )
    raw = (
        tmp_path / "results/runs/run-x/coding_agent_eval/results.jsonl"
    ).read_text(encoding="utf-8")
    # Round-trip with strict JSON.
    for line in raw.splitlines():
        if line.strip():
            obj = json.loads(line)
            json.dumps(obj, allow_nan=False)
            assert "NaN" not in line
            assert "Infinity" not in line


def test_cli_invalid_task_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _make_task(tasks, "task-01")
    monkeypatch.chdir(tmp_path)

    rc = harness.run_one(
        _args(tasks_root=tasks, task_id="NOT_A_REAL_ID", work_dir=tmp_path / "w"),
        now=_now_iter(),
        runner=_runner_factory(),
        git_runner=_fake_git_runner(),
        server_metrics_collector=_no_metrics,
    )
    assert rc == harness.EXIT_INVALID_ARGS


def test_token_usage_parsed_from_stdout() -> None:
    stdout = (
        "garbage line\n"
        '{"type":"message","num_turns":3,"usage":{"input_tokens":100,"output_tokens":50}}\n'
        "more garbage\n"
    )
    tok = harness._parse_token_usage(stdout)
    assert tok.input_tokens == 100
    assert tok.output_tokens == 50
    assert tok.num_turns == 3
