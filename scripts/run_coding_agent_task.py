"""Coding-agent evaluation harness.

Per-task on-disk layout:

    benchmarks/coding-agent-tasks/<task-id>/
      TASK.md
      README.md
      starter/       # copied into the agent's temp work_dir
      public/        # copied alongside starter; agent may read these
      hidden/        # NOT copied into work_dir; harness runs after agent

Output layout per harness run:

    results/runs/<run_id>/coding_agent_eval/
      results.jsonl                       # one CodingAgentEvalRow per task run
      tasks_summary.md
      transcripts/
        <task_id>__prompt.txt
        <task_id>__stdout.log
        <task_id>__stderr.log
      server_metrics/<task_id>/
        pre_server_metrics.json
        pre_nvidia_smi.json
        post_server_metrics.json
        post_nvidia_smi.json

Run-row schema is `SCHEMA_CODING_AGENT_EVAL_ROW`
(``nanoserve-mini.coding-agent-eval-row.v1``).
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from scripts._metrics import make_run_uuid
from scripts._schemas import (
    METHODOLOGY,
    MODE_CODING_AGENT_EVAL,
    SCHEMA_CODING_AGENT_EVAL_ROW,
)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

TASKS_ROOT: Final[str] = "benchmarks/coding-agent-tasks"
STARTER_SUBDIR: Final[str] = "starter"
PUBLIC_SUBDIR: Final[str] = "public"
HIDDEN_SUBDIR: Final[str] = "hidden"

RUN_SCRIPT_BASENAME: Final[str] = "run"

DEFAULT_AGENT_TIMEOUT_S: Final[float] = 1800.0

EXIT_OK: Final[int] = 0
EXIT_INVALID_ARGS: Final[int] = 1
EXIT_AGENT_TIMEOUT: Final[int] = 124
EXIT_HARNESS_ERROR: Final[int] = 3


# ---------------------------------------------------------------------------
# Result-row dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TestRunResult:
    """One public-or-hidden test-suite execution."""

    ran: bool
    exit_code: int | None = None
    log_path: str | None = None
    duration_s: float | None = None


@dataclass
class TokenUsage:
    """Token usage parsed from agent stdout/transcript when available."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    num_turns: int | None = None


@dataclass
class CodingAgentEvalRow:
    """One row in ``results/runs/<run_id>/coding_agent_eval/results.jsonl``."""

    run_id: str
    run_uuid: str
    task_id: str
    agent: str
    model: str
    base_url: str
    started_at: str
    ended_at: str
    wall_clock_seconds: float
    timed_out: bool
    agent_exit_code: int | None
    public_tests: TestRunResult
    hidden_tests: TestRunResult
    changed_files: int | None
    baseline_commit: str | None
    final_commit: str | None
    tokens: TokenUsage
    server_metrics: dict[str, Any]
    transcript_path: str | None
    error: str | None = None
    agent_version: str | None = None
    schema: str = SCHEMA_CODING_AGENT_EVAL_ROW
    methodology: str = METHODOLOGY
    benchmark_mode: str = MODE_CODING_AGENT_EVAL
    notes: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        """Stable JSON shape — strict-JSON friendly (no NaN/Infinity)."""
        return asdict(self)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_coding_agent_task",
        description=(
            "Run a coding-agent CLI against a starter task in a temp work-dir, "
            "run public+hidden tests, append a row to results.jsonl."
        ),
    )
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--agent", required=True, help="claude_code|opencode|fake")
    parser.add_argument(
        "--agent-command",
        required=True,
        help=(
            "Shell command template. May include {prompt_file} which is "
            "substituted with the path to the rendered prompt."
        ),
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--work-dir",
        default=None,
        help="Optional explicit work-dir; mktemp by default.",
    )
    parser.add_argument(
        "--timeout-s", type=float, default=DEFAULT_AGENT_TIMEOUT_S
    )
    parser.add_argument(
        "--skip-server-metrics", action="store_true", default=False
    )
    parser.add_argument(
        "--require-hidden", action="store_true", default=False,
        help="Fail (non-zero) if the task has no hidden/ directory.",
    )
    parser.add_argument(
        "--tasks-root", default=TASKS_ROOT,
        help="Override for tests; default is the repo-relative tasks dir.",
    )
    parser.add_argument(
        "--agent-version", default=None,
        help="Optional agent version string recorded in the result row.",
    )
    parser.add_argument("--notes", default=None)
    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_agent_prompt(task_md: str) -> str:
    """Extract content of the ``## Agent prompt`` section.

    Returns the full TASK.md if the heading is not present.
    """
    lines = task_md.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        if line.strip() == "## Agent prompt":
            start = i + 1
            break
    if start is None:
        return task_md
    end = len(lines)
    for j in range(start, len(lines)):
        s = lines[j].lstrip()
        if s.startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end]).strip() + "\n"


def _parse_token_usage(stdout: str) -> TokenUsage:
    """Best-effort parse: scan stdout lines for JSON objects with a ``usage`` key."""
    usage_obj: dict[str, Any] | None = None
    num_turns: int | None = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line or not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(obj, dict):
            continue
        if "num_turns" in obj and isinstance(obj["num_turns"], int):
            num_turns = obj["num_turns"]
        if "usage" in obj and isinstance(obj["usage"], dict):
            usage_obj = obj["usage"]
    if usage_obj is None:
        return TokenUsage(num_turns=num_turns)
    inp = usage_obj.get("input_tokens")
    out = usage_obj.get("output_tokens")
    return TokenUsage(
        input_tokens=inp if isinstance(inp, int) else None,
        output_tokens=out if isinstance(out, int) else None,
        num_turns=num_turns,
    )


def _find_runner(directory: Path) -> Path | None:
    """Probe for ``run.sh`` first, then ``run.ps1``."""
    sh = directory / f"{RUN_SCRIPT_BASENAME}.sh"
    if sh.exists():
        return sh
    ps1 = directory / f"{RUN_SCRIPT_BASENAME}.ps1"
    if ps1.exists():
        return ps1
    return None


def _runner_command(runner: Path) -> list[str]:
    if runner.suffix == ".ps1":
        return ["pwsh", "-NoProfile", "-File", str(runner)]
    return ["bash", str(runner)]


def _git(
    git_runner: Callable[..., Any],
    args: list[str],
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return git_runner(
        ["git", *args],
        cwd=str(cwd),
        env=None,
        timeout=30,
        capture_output=True,
        text=True,
    )


def _default_server_metrics_collector(
    *,
    base_url: str,
    phase: str,
    run_id: str,
    task_id: str,
    out_dir: Path,
) -> dict[str, Any]:
    """Best-effort vLLM /metrics + nvidia-smi snapshot.

    Reuses ``scripts.collect_metrics_snapshot`` helpers. Failures are recorded
    inline and do NOT raise.
    """
    from scripts import collect_metrics_snapshot as cms

    out_dir.mkdir(parents=True, exist_ok=True)
    server_path = out_dir / f"{phase}_server_metrics.json"
    nvidia_path = out_dir / f"{phase}_nvidia_smi.json"
    result: dict[str, Any] = {
        "server_metrics_path": str(server_path),
        "nvidia_smi_path": str(nvidia_path),
        "errors": [],
    }
    try:
        vllm_block = cms.scrape_vllm_metrics(base_url)
    except Exception as exc:  # noqa: BLE001
        vllm_block = {
            "endpoint": base_url,
            "scrape_ok": False,
            "scrape_error": f"{type(exc).__name__}: {exc}",
            "metrics": {},
        }
        result["errors"].append(str(exc))
    try:
        gpu_block = cms.run_nvidia_smi()
    except Exception as exc:  # noqa: BLE001
        gpu_block = {
            "available": False,
            "command": [],
            "rows": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
        result["errors"].append(str(exc))

    snapshot = cms.build_snapshot(
        run_id=run_id,
        run_uuid=make_run_uuid(),
        phase=phase,
        base_url=base_url,
        notes=f"task={task_id}",
        vllm_block=vllm_block,
        gpu_block=gpu_block,
    )
    try:
        server_path.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"write server_metrics: {exc}")
        result["server_metrics_path"] = None
    try:
        nvidia_path.write_text(
            json.dumps(gpu_block, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"write nvidia_smi: {exc}")
        result["nvidia_smi_path"] = None
    return result


# ---------------------------------------------------------------------------
# Main body
# ---------------------------------------------------------------------------


def run_one(
    args: argparse.Namespace,
    *,
    now: Callable[[], datetime] | None = None,
    runner: Callable[..., Any] | None = None,
    git_runner: Callable[..., Any] | None = None,
    server_metrics_collector: Callable[..., dict[str, Any]] | None = None,
) -> int:
    now_fn = now if now is not None else (lambda: datetime.now(UTC))
    run_subproc = runner if runner is not None else subprocess.run
    git_run = git_runner if git_runner is not None else subprocess.run
    metrics_fn = (
        server_metrics_collector
        if server_metrics_collector is not None
        else _default_server_metrics_collector
    )

    tasks_root = Path(args.tasks_root)
    task_dir = tasks_root / args.task_id
    if not task_dir.is_dir():
        print(
            f"error: task-id '{args.task_id}' not found under {tasks_root}",
            file=sys.stderr,
        )
        return EXIT_INVALID_ARGS

    starter_src = task_dir / STARTER_SUBDIR
    public_src = task_dir / PUBLIC_SUBDIR
    hidden_src = task_dir / HIDDEN_SUBDIR
    task_md = task_dir / "TASK.md"

    if args.require_hidden and not hidden_src.is_dir():
        print(
            f"error: --require-hidden but no hidden/ in {task_dir}",
            file=sys.stderr,
        )
        return EXIT_HARNESS_ERROR

    # ----- Output dirs --------------------------------------------------
    eval_root = Path("results/runs") / args.run_id / "coding_agent_eval"
    transcripts_dir = eval_root / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    server_metrics_dir = eval_root / "server_metrics" / args.task_id

    # ----- Work dir -----------------------------------------------------
    if args.work_dir:
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        work_dir = Path(
            tempfile.mkdtemp(prefix=f"coding-agent-{args.task_id}-")
        )

    if starter_src.is_dir():
        shutil.copytree(starter_src, work_dir, dirs_exist_ok=True)
    if public_src.is_dir():
        shutil.copytree(public_src, work_dir / PUBLIC_SUBDIR, dirs_exist_ok=True)

    # git init + baseline commit
    baseline_commit: str | None = None
    try:
        _git(git_run, ["init", "-q"], work_dir)
        _git(git_run, ["config", "user.email", "harness@local"], work_dir)
        _git(git_run, ["config", "user.name", "harness"], work_dir)
        _git(git_run, ["add", "-A"], work_dir)
        _git(
            git_run,
            ["commit", "-q", "--allow-empty", "-m", "harness baseline"],
            work_dir,
        )
        rev = _git(git_run, ["rev-parse", "HEAD"], work_dir)
        if rev.returncode == 0:
            baseline_commit = (rev.stdout or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        print(f"warning: git baseline failed: {exc}", file=sys.stderr)

    # ----- Pre-snapshot -------------------------------------------------
    server_metrics: dict[str, Any] = {"pre": None, "post": None, "skipped": False}
    if args.skip_server_metrics:
        server_metrics["skipped"] = True
    else:
        try:
            pre = metrics_fn(
                base_url=args.base_url,
                phase="pre",
                run_id=args.run_id,
                task_id=args.task_id,
                out_dir=server_metrics_dir,
            )
            server_metrics["pre"] = pre.get("server_metrics_path")
        except Exception as exc:  # noqa: BLE001
            server_metrics["pre"] = None
            print(f"warning: pre snapshot failed: {exc}", file=sys.stderr)

    # ----- Prompt -------------------------------------------------------
    if task_md.is_file():
        prompt_body = _extract_agent_prompt(
            task_md.read_text(encoding="utf-8")
        )
    else:
        prompt_body = ""
    prompt_path = transcripts_dir / f"{args.task_id}__prompt.txt"
    prompt_path.write_text(prompt_body, encoding="utf-8")

    # ----- Run agent ----------------------------------------------------
    started_dt = now_fn()
    started_at = started_dt.isoformat()
    cmd_str = args.agent_command.replace("{prompt_file}", str(prompt_path))
    cmd_list = shlex.split(cmd_str, posix=True)

    stdout_path = transcripts_dir / f"{args.task_id}__stdout.log"
    stderr_path = transcripts_dir / f"{args.task_id}__stderr.log"

    agent_exit_code: int | None = None
    timed_out = False
    agent_stdout = ""
    agent_stderr = ""
    error: str | None = None
    t0 = time.monotonic()
    try:
        completed = run_subproc(
            cmd_list,
            cwd=str(work_dir),
            env=os.environ.copy(),
            timeout=args.timeout_s,
            capture_output=True,
        )
        agent_stdout = _as_text(getattr(completed, "stdout", "") or "")
        agent_stderr = _as_text(getattr(completed, "stderr", "") or "")
        agent_exit_code = int(getattr(completed, "returncode", 0))
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        agent_stdout = _as_text(getattr(exc, "stdout", "") or "")
        agent_stderr = _as_text(getattr(exc, "stderr", "") or "")
    except FileNotFoundError as exc:
        error = f"agent command not found: {exc}"
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    wall_clock = time.monotonic() - t0
    ended_dt = now_fn()
    ended_at = ended_dt.isoformat()

    stdout_path.write_text(agent_stdout, encoding="utf-8")
    stderr_path.write_text(agent_stderr, encoding="utf-8")

    tokens = _parse_token_usage(agent_stdout)

    # ----- Post-agent git commit ---------------------------------------
    final_commit: str | None = None
    changed_files: int | None = None
    try:
        _git(git_run, ["add", "-A"], work_dir)
        _git(
            git_run,
            ["commit", "-q", "--allow-empty", "-m", "agent solution"],
            work_dir,
        )
        rev = _git(git_run, ["rev-parse", "HEAD"], work_dir)
        if rev.returncode == 0:
            final_commit = (rev.stdout or "").strip() or None
        if baseline_commit and final_commit:
            diff = _git(
                git_run,
                ["diff", "--name-only", f"{baseline_commit}..{final_commit}"],
                work_dir,
            )
            if diff.returncode == 0:
                changed_files = len(
                    [ln for ln in (diff.stdout or "").splitlines() if ln.strip()]
                )
    except Exception as exc:  # noqa: BLE001
        print(f"warning: git post-commit failed: {exc}", file=sys.stderr)

    # ----- Public tests -------------------------------------------------
    public_result = TestRunResult(ran=False)
    public_work = work_dir / PUBLIC_SUBDIR
    public_runner = _find_runner(public_work) if public_work.is_dir() else None
    if public_runner is not None and not timed_out:
        log_path = transcripts_dir / f"{args.task_id}__public_tests.log"
        env = os.environ.copy()
        env["WORK_DIR"] = str(work_dir)
        t = time.monotonic()
        try:
            completed = run_subproc(
                _runner_command(public_runner),
                cwd=str(public_work),
                env=env,
                timeout=args.timeout_s,
                capture_output=True,
            )
            out = _as_text(getattr(completed, "stdout", "") or "")
            err = _as_text(getattr(completed, "stderr", "") or "")
            rc = int(getattr(completed, "returncode", 0))
            log_path.write_text(out + "\n--- stderr ---\n" + err, encoding="utf-8")
            public_result = TestRunResult(
                ran=True,
                exit_code=rc,
                log_path=str(log_path),
                duration_s=time.monotonic() - t,
            )
        except Exception as exc:  # noqa: BLE001
            log_path.write_text(f"runner error: {exc}", encoding="utf-8")
            public_result = TestRunResult(
                ran=True,
                exit_code=None,
                log_path=str(log_path),
                duration_s=time.monotonic() - t,
            )

    # ----- Hidden tests -------------------------------------------------
    hidden_result = TestRunResult(ran=False)
    if hidden_src.is_dir() and not timed_out:
        hidden_work = Path(str(work_dir) + "__hidden")
        if hidden_work.exists():
            shutil.rmtree(hidden_work, ignore_errors=True)
        shutil.copytree(hidden_src, hidden_work)
        hidden_runner = _find_runner(hidden_work)
        if hidden_runner is not None:
            log_path = transcripts_dir / f"{args.task_id}__hidden_tests.log"
            env = os.environ.copy()
            env["WORK_DIR"] = str(work_dir)
            t = time.monotonic()
            try:
                completed = run_subproc(
                    _runner_command(hidden_runner),
                    cwd=str(hidden_work),
                    env=env,
                    timeout=args.timeout_s,
                    capture_output=True,
                )
                out = _as_text(getattr(completed, "stdout", "") or "")
                err = _as_text(getattr(completed, "stderr", "") or "")
                rc = int(getattr(completed, "returncode", 0))
                log_path.write_text(
                    out + "\n--- stderr ---\n" + err, encoding="utf-8"
                )
                hidden_result = TestRunResult(
                    ran=True,
                    exit_code=rc,
                    log_path=str(log_path),
                    duration_s=time.monotonic() - t,
                )
            except Exception as exc:  # noqa: BLE001
                log_path.write_text(f"runner error: {exc}", encoding="utf-8")
                hidden_result = TestRunResult(
                    ran=True,
                    exit_code=None,
                    log_path=str(log_path),
                    duration_s=time.monotonic() - t,
                )

    # ----- Post-snapshot ------------------------------------------------
    if not args.skip_server_metrics:
        try:
            post = metrics_fn(
                base_url=args.base_url,
                phase="post",
                run_id=args.run_id,
                task_id=args.task_id,
                out_dir=server_metrics_dir,
            )
            server_metrics["post"] = post.get("server_metrics_path")
        except Exception as exc:  # noqa: BLE001
            server_metrics["post"] = None
            print(f"warning: post snapshot failed: {exc}", file=sys.stderr)

    # ----- Row ----------------------------------------------------------
    row = CodingAgentEvalRow(
        run_id=args.run_id,
        run_uuid=make_run_uuid(),
        task_id=args.task_id,
        agent=args.agent,
        model=args.model,
        base_url=args.base_url,
        started_at=started_at,
        ended_at=ended_at,
        wall_clock_seconds=round(wall_clock, 6),
        timed_out=timed_out,
        agent_exit_code=agent_exit_code,
        public_tests=public_result,
        hidden_tests=hidden_result,
        changed_files=changed_files,
        baseline_commit=baseline_commit,
        final_commit=final_commit,
        tokens=tokens,
        server_metrics=server_metrics,
        transcript_path=str(stdout_path),
        error=error,
        agent_version=args.agent_version,
        notes=args.notes,
    )

    results_path = eval_root / "results.jsonl"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row.to_json_dict(), ensure_ascii=False, allow_nan=False)
    with results_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")

    summary_path = eval_root / "tasks_summary.md"
    public_str = (
        f"exit={public_result.exit_code}" if public_result.ran else "skipped"
    )
    hidden_str = (
        f"exit={hidden_result.exit_code}" if hidden_result.ran else "skipped"
    )
    agent_status = "timeout" if timed_out else f"exit={agent_exit_code}"
    summary_lines = [
        f"- task `{args.task_id}` ({args.agent}/{args.model}): "
        f"agent={agent_status} public={public_str} hidden={hidden_str}",
        f"  wall_clock={wall_clock:.2f}s changed_files={changed_files} "
        f"started={started_at}",
        "",
    ]
    with summary_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(summary_lines))

    print(
        f"task={args.task_id} agent={agent_status} "
        f"public={public_str} hidden={hidden_str} "
        f"wall={wall_clock:.2f}s -> {results_path}"
    )

    if timed_out:
        return EXIT_OK
    return EXIT_OK


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return ""
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run_one(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
