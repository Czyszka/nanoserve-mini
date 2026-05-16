"""Runner for the 01_preflight_env_check coding-agent eval task.

Invokes the Claude Code CLI against a prepared work-dir (created by
init_env.ps1 / init_env.sh), then runs the hidden test suite from this
task directory against the agent's solution. Writes a single JSON line
to <work-dir>/results.jsonl with the schema
``preflight-env-check-eval.v1``.

Usage:
    uv run python benchmarks/coding-agent-tasks/01_preflight_env_check/run_eval.py \\
        --work-dir <path created by init_env.*> \\
        --model <model-id> \\
        [--shell powershell|bash] \\
        [--timeout-s 900] \\
        [--claude-bin claude] \\
        [--permission-mode acceptEdits] \\
        [--skip-agent]      # for pipeline smoke testing without invoking claude

Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parent


def git_cmd(work_dir: Path, *args: str) -> list[str]:
    """Build a git command that accepts sandbox-owned work directories."""
    return ["git", "-c", f"safe.directory={work_dir}", *args]


def detect_shell(work_dir: Path) -> str:
    if (work_dir / "preflight.ps1").is_file():
        return "powershell"
    if (work_dir / "preflight.sh").is_file():
        return "bash"
    raise SystemExit(
        f"[error] could not detect shell variant: no preflight.ps1 or preflight.sh in {work_dir}"
    )


def read_prompt(work_dir: Path) -> str:
    p = work_dir / "PROMPT.md"
    if not p.is_file():
        raise SystemExit(f"[error] PROMPT.md missing in {work_dir}")
    return p.read_text(encoding="utf-8")


def git_rev(work_dir: Path) -> str | None:
    try:
        out = subprocess.run(
            git_cmd(work_dir, "rev-parse", "HEAD"),
            cwd=work_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def git_auto_commit_final(work_dir: Path) -> None:
    """Stage any agent changes and commit them so we can record final_commit."""
    try:
        subprocess.run(git_cmd(work_dir, "add", "-A"), cwd=work_dir, check=True)
        status = subprocess.run(
            git_cmd(work_dir, "status", "--porcelain"),
            cwd=work_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        if status.stdout.strip():
            subprocess.run(
                git_cmd(
                    work_dir,
                    "-c",
                    "user.name=nanoserve-eval",
                    "-c",
                    "user.email=eval@nanoserve.local",
                    "commit",
                    "--quiet",
                    "-m",
                    "final: agent solution",
                ),
                cwd=work_dir,
                check=True,
            )
    except Exception as exc:
        print(f"[warn] git auto-commit failed: {exc}", file=sys.stderr)


def run_agent(
    *,
    claude_bin: str,
    prompt: str,
    work_dir: Path,
    model: str,
    permission_mode: str,
    timeout_s: int,
) -> dict:
    """Invoke claude in non-interactive print mode. Returns a dict with
    keys: returncode, stdout, stderr, parsed (claude JSON or None),
    timed_out, wall_clock_s.
    """
    cmd = [
        claude_bin,
        "-p",
        "--output-format",
        "json",
        "--model",
        model,
        "--permission-mode",
        permission_mode,
    ]
    print(
        "[info] invoking: "
        f"{claude_bin} -p <stdin prompt> --output-format json "
        f"--model {model} --permission-mode {permission_mode}"
    )
    start = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            cwd=work_dir,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        stdout = proc.stdout
        stderr = proc.stderr
        rc = proc.returncode
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout or ""
        stderr = (e.stderr or "") + f"\n[timeout after {timeout_s}s]"
        rc = -1
        timed_out = True
    elapsed = time.time() - start

    parsed = None
    if stdout.strip():
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            # claude --output-format json sometimes prints non-JSON warnings first; try last line
            last = stdout.strip().splitlines()[-1]
            try:
                parsed = json.loads(last)
            except json.JSONDecodeError:
                parsed = None

    return {
        "returncode": rc,
        "stdout": stdout,
        "stderr": stderr,
        "parsed": parsed,
        "timed_out": timed_out,
        "wall_clock_s": elapsed,
    }


def extract_tokens(parsed: dict | None) -> dict:
    """Pull token usage out of claude's --output-format json response.

    Schema (observed): {"usage": {"input_tokens": N, "output_tokens": N,
    "cache_creation_input_tokens": N, "cache_read_input_tokens": N}, ...}
    Be defensive: anything missing -> 0.
    """
    if not isinstance(parsed, dict):
        return {"input": 0, "output": 0, "total": 0}
    usage = parsed.get("usage") or {}
    if not isinstance(usage, dict):
        return {"input": 0, "output": 0, "total": 0}
    inp = int(usage.get("input_tokens", 0) or 0)
    out = int(usage.get("output_tokens", 0) or 0)
    return {"input": inp, "output": out, "total": inp + out}


def run_hidden_tests(
    *,
    shell: str,
    work_dir: Path,
) -> dict:
    """Run the hidden test runner against the agent solution in work_dir.

    Returns dict with stage1/stage2/total pass counts + raw summary.
    """
    if shell == "powershell":
        runner = TASK_ROOT / "hidden_tests" / "powershell" / "run.ps1"
        preflight = work_dir / "preflight.ps1"
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(runner),
            "-PreflightPath",
            str(preflight),
        ]
    elif shell == "bash":
        runner = TASK_ROOT / "hidden_tests" / "bash" / "run.sh"
        cmd = ["bash", str(runner), "--preflight", str(work_dir / "preflight.sh")]
    else:
        raise SystemExit(f"[error] unknown shell: {shell}")

    if not runner.is_file():
        print(f"[warn] hidden runner not found at {runner}; skipping hidden tests")
        return _empty_test_result()

    proc = subprocess.run(cmd, capture_output=True, text=True)
    stdout = proc.stdout
    stderr = proc.stderr

    # Parse SUMMARY_JSON line from runner.
    summary = None
    for line in stdout.splitlines():
        if line.startswith("SUMMARY_JSON "):
            try:
                summary = json.loads(line[len("SUMMARY_JSON "):])
            except json.JSONDecodeError:
                summary = None
            break

    if summary is None:
        print("[warn] hidden runner did not emit SUMMARY_JSON line")
        print("--- hidden stdout ---")
        print(stdout)
        print("--- hidden stderr ---")
        print(stderr)
        return _empty_test_result()

    cases = summary.get("cases", [])
    s1 = [c for c in cases if c.get("stage") == 1]
    s2 = [c for c in cases if c.get("stage") == 2]
    return {
        "stage1": _bucket(s1),
        "stage2": _bucket(s2),
        "total": _bucket(cases),
        "runner_exit_code": proc.returncode,
        "raw_summary": summary,
    }


def _bucket(cases: list[dict]) -> dict:
    total = len(cases)
    passed = sum(1 for c in cases if c.get("passed"))
    pct = round(100.0 * passed / total, 1) if total else 0.0
    return {"passed": passed, "total": total, "pct": pct}


def _empty_test_result() -> dict:
    z = {"passed": 0, "total": 0, "pct": 0.0}
    return {"stage1": z, "stage2": z, "total": z, "runner_exit_code": None, "raw_summary": None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="run_eval for 01_preflight_env_check")
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--shell", choices=["powershell", "bash"], default=None)
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--permission-mode", default="acceptEdits")
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        help="Skip invoking the agent; just run hidden tests against the current work-dir state.",
    )
    args = parser.parse_args(argv)

    work_dir: Path = args.work_dir.resolve()
    if not work_dir.is_dir():
        raise SystemExit(f"[error] work-dir not found: {work_dir}")

    shell = args.shell or detect_shell(work_dir)
    prompt = read_prompt(work_dir)
    baseline_commit = git_rev(work_dir)

    run_id = work_dir.name
    started_at = dt.datetime.now(dt.UTC).isoformat()
    wall_start = time.time()

    agent_result: dict
    if args.skip_agent:
        print("[info] --skip-agent set; not invoking claude")
        agent_result = {
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "parsed": None,
            "timed_out": False,
            "wall_clock_s": 0.0,
        }
    else:
        agent_result = run_agent(
            claude_bin=args.claude_bin,
            prompt=prompt,
            work_dir=work_dir,
            model=args.model,
            permission_mode=args.permission_mode,
            timeout_s=args.timeout_s,
        )

    # Auto-commit any agent edits as final_commit.
    git_auto_commit_final(work_dir)
    final_commit = git_rev(work_dir)

    # Run hidden tests against the work-dir.
    hidden = run_hidden_tests(shell=shell, work_dir=work_dir)

    ended_at = dt.datetime.now(dt.UTC).isoformat()
    wall_clock_s = round(time.time() - wall_start, 2)

    tokens = extract_tokens(agent_result["parsed"])

    row = {
        "schema": "preflight-env-check-eval.v1",
        "model": args.model,
        "run_id": run_id,
        "shell": shell,
        "started_at": started_at,
        "ended_at": ended_at,
        "wall_clock_s": wall_clock_s,
        "agent_wall_clock_s": round(agent_result["wall_clock_s"], 2),
        "agent_exit_code": agent_result["returncode"],
        "timed_out": agent_result["timed_out"],
        "baseline_commit": baseline_commit,
        "final_commit": final_commit,
        "tokens": tokens,
        "stage1": hidden["stage1"],
        "stage2": hidden["stage2"],
        "total": hidden["total"],
        "hidden_runner_exit_code": hidden["runner_exit_code"],
        "skipped_agent": args.skip_agent,
    }

    results_path = work_dir / "results.jsonl"
    with results_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")

    # Save transcripts (best-effort).
    if agent_result["stdout"] or agent_result["stderr"]:
        (work_dir / "agent_stdout.log").write_text(agent_result["stdout"], encoding="utf-8")
        (work_dir / "agent_stderr.log").write_text(agent_result["stderr"], encoding="utf-8")

    # Short stdout summary.
    print()
    print("== summary ==")
    print(f"  model        : {args.model}")
    print(f"  shell        : {shell}")
    print(f"  agent_exit   : {agent_result['returncode']}  timed_out={agent_result['timed_out']}")
    print(f"  tokens       : in={tokens['input']} out={tokens['output']} total={tokens['total']}")
    print(
        "  stage1       : "
        f"{hidden['stage1']['passed']}/{hidden['stage1']['total']} "
        f"({hidden['stage1']['pct']}%)"
    )
    print(
        "  stage2       : "
        f"{hidden['stage2']['passed']}/{hidden['stage2']['total']} "
        f"({hidden['stage2']['pct']}%)"
    )
    print(
        "  total        : "
        f"{hidden['total']['passed']}/{hidden['total']['total']} "
        f"({hidden['total']['pct']}%)"
    )
    print(f"  results.jsonl: {results_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
