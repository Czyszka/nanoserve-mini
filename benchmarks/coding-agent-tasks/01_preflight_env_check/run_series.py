"""Run N evaluations of the 01_preflight_env_check task and aggregate results.

For each run i in 1..runs:
  1. Invoke init_env.ps1 (Windows) or init_env.sh (Linux) with --RunNumber i
     to create an isolated work-dir under <base-dir>.
  2. Invoke run_eval.py against that work-dir.
  3. Read the most recent line from <work-dir>/results.jsonl.

After all runs, compute aggregate statistics across rows (ignoring rows
whose agent stage was skipped) and write a summary JSON to
<summary-dir>/series_<UTC-ts>_<model-san>_runs<N>.json.

Usage:
    uv run python run_series.py --model claude-haiku-4-5 --runs 3 \\
        [--shell powershell|bash] [--timeout-s 900] \\
        [--base-dir ./runs] [--summary-dir <path>] [--claude-bin claude]

Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

TASK_ROOT = Path(__file__).resolve().parent


def detect_shell() -> str:
    return "powershell" if sys.platform == "win32" else "bash"


def sanitize_model(model: str) -> str:
    return re.sub(r"[\\/]", "-", model)


def work_dir_for(base_dir: Path, model: str, run_number: int) -> Path:
    date_utc = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
    name = f"{date_utc}_{sanitize_model(model)}_run{run_number:02d}"
    return (base_dir / name).resolve()


def run_init(shell: str, model: str, run_number: int, base_dir: Path) -> int:
    if shell == "powershell":
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(TASK_ROOT / "init_env.ps1"),
            "-Model",
            model,
            "-RunNumber",
            f"{run_number:02d}",
            "-BaseDir",
            str(base_dir),
        ]
    else:
        cmd = [
            "bash",
            str(TASK_ROOT / "init_env.sh"),
            "--model",
            model,
            "--run-number",
            f"{run_number:02d}",
            "--base-dir",
            str(base_dir),
        ]
    proc = subprocess.run(cmd, encoding="utf-8", errors="replace")
    return proc.returncode


def run_eval(
    *,
    work_dir: Path,
    model: str,
    shell: str,
    timeout_s: int,
    claude_bin: str,
    skip_agent: bool = False,
) -> int:
    cmd = [
        sys.executable,
        str(TASK_ROOT / "run_eval.py"),
        "--work-dir",
        str(work_dir),
        "--model",
        model,
        "--shell",
        shell,
        "--timeout-s",
        str(timeout_s),
        "--claude-bin",
        claude_bin,
    ]
    if skip_agent:
        cmd.append("--skip-agent")
    proc = subprocess.run(cmd, encoding="utf-8", errors="replace")
    return proc.returncode


def read_last_row(results_path: Path) -> dict | None:
    if not results_path.is_file():
        return None
    last: dict | None = None
    with results_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                last = json.loads(line)
            except json.JSONDecodeError:
                continue
    return last


def aggregate(rows: list[dict]) -> dict:
    """Compute aggregate metrics across run rows.

    Rows with `agent_transport_status == "skipped"` or `skipped_agent: true`
    are excluded from token/exit-code stats but still contribute to test
    pass-rate stats (since hidden tests still ran).
    """
    def pct(key_a: str, key_b: str) -> list[float]:
        return [float(r.get(key_a, {}).get(key_b, 0.0) or 0.0) for r in rows]

    total_pct = [float(r.get("total", {}).get("pct", 0.0) or 0.0) for r in rows]
    stage1_pct = [float(r.get("stage1", {}).get("pct", 0.0) or 0.0) for r in rows]
    stage2_pct = [float(r.get("stage2", {}).get("pct", 0.0) or 0.0) for r in rows]
    wall = [float(r.get("wall_clock_s", 0.0) or 0.0) for r in rows]

    agent_rows = [r for r in rows if not r.get("skipped_agent")]
    tokens_in = [int(r.get("tokens", {}).get("input", 0) or 0) for r in agent_rows]
    tokens_out = [int(r.get("tokens", {}).get("output", 0) or 0) for r in agent_rows]
    tokens_total = [int(r.get("tokens", {}).get("total", 0) or 0) for r in agent_rows]

    transport_counts = Counter(
        r.get("agent_transport_status", "unknown") for r in agent_rows
    )
    exit_counts = Counter(r.get("agent_exit_code") for r in agent_rows)
    did_work = [bool(r.get("agent_did_work")) for r in agent_rows]

    def _stat(values: list[float] | list[int]) -> dict:
        if not values:
            return {"mean": None, "min": None, "max": None, "n": 0}
        return {
            "mean": round(float(mean(values)), 2),
            "min": min(values),
            "max": max(values),
            "n": len(values),
        }

    return {
        "total_pct": _stat(total_pct),
        "stage1_pct": _stat(stage1_pct),
        "stage2_pct": _stat(stage2_pct),
        "wall_clock_s": _stat(wall),
        "tokens_input": _stat(tokens_in),
        "tokens_output": _stat(tokens_out),
        "tokens_total": _stat(tokens_total),
        "transport_status": dict(transport_counts),
        "agent_exit_code": {str(k): v for k, v in exit_counts.items()},
        "did_work_rate": round(
            (sum(did_work) / len(did_work)) if did_work else 0.0, 2
        ),
    }


def per_run_view(row: dict) -> dict:
    return {
        "run_id": row.get("run_id"),
        "total_pct": row.get("total", {}).get("pct"),
        "stage1_pct": row.get("stage1", {}).get("pct"),
        "stage2_pct": row.get("stage2", {}).get("pct"),
        "wall_clock_s": row.get("wall_clock_s"),
        "agent_exit_code": row.get("agent_exit_code"),
        "agent_transport_status": row.get("agent_transport_status"),
        "agent_did_work": row.get("agent_did_work"),
        "tokens_total": row.get("tokens", {}).get("total"),
    }


def print_table(rows: list[dict], agg: dict) -> None:
    print()
    print("== per-run ==")
    print(
        f"{'run_id':<48} {'total':>7} {'s1':>6} {'s2':>6} {'wall_s':>7} "
        f"{'rc':>4} {'transport':>16} {'work':>5} {'tok':>7}"
    )
    for r in rows:
        v = per_run_view(r)
        print(
            f"{str(v['run_id']):<48} "
            f"{v['total_pct']!s:>7} "
            f"{v['stage1_pct']!s:>6} "
            f"{v['stage2_pct']!s:>6} "
            f"{v['wall_clock_s']!s:>7} "
            f"{v['agent_exit_code']!s:>4} "
            f"{(v['agent_transport_status'] or '')!s:>16} "
            f"{('yes' if v['agent_did_work'] else 'no'):>5} "
            f"{v['tokens_total']!s:>7}"
        )

    print()
    print("== aggregate ==")
    for key in ("total_pct", "stage1_pct", "stage2_pct", "wall_clock_s",
                "tokens_input", "tokens_output", "tokens_total"):
        s = agg[key]
        print(
            f"  {key:<14}: mean={s['mean']} min={s['min']} max={s['max']} "
            f"n={s['n']}"
        )
    print(f"  transport     : {agg['transport_status']}")
    print(f"  exit codes    : {agg['agent_exit_code']}")
    print(f"  did_work rate : {agg['did_work_rate']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a series of task-01 evals")
    parser.add_argument("--model", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--shell", choices=["powershell", "bash"], default=None)
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=TASK_ROOT / "runs",
        help="Where per-run work-dirs are created (default: ./runs).",
    )
    parser.add_argument(
        "--summary-dir",
        type=Path,
        default=None,
        help="Where to write the aggregate summary JSON "
        "(default: <base-dir>/_series).",
    )
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        help="Pass --skip-agent through to run_eval.py (no agent invocation; "
        "for harness smoke testing).",
    )
    args = parser.parse_args(argv)

    if args.runs < 1:
        raise SystemExit("[error] --runs must be >= 1")

    shell = args.shell or detect_shell()
    base_dir: Path = args.base_dir.resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    summary_dir: Path = (args.summary_dir or (base_dir / "_series")).resolve()
    summary_dir.mkdir(parents=True, exist_ok=True)

    started_at = dt.datetime.now(dt.UTC).isoformat()
    rows: list[dict] = []

    for i in range(1, args.runs + 1):
        wd = work_dir_for(base_dir, args.model, i)
        print(f"\n=== run {i}/{args.runs} : {wd.name} ===")

        rc = run_init(shell, args.model, i, base_dir)
        if rc != 0:
            print(f"[warn] init_env exit code {rc}; skipping run {i}")
            continue

        rc = run_eval(
            work_dir=wd,
            model=args.model,
            shell=shell,
            timeout_s=args.timeout_s,
            claude_bin=args.claude_bin,
            skip_agent=args.skip_agent,
        )
        if rc != 0:
            print(f"[warn] run_eval exit code {rc} for run {i}")

        row = read_last_row(wd / "results.jsonl")
        if row is None:
            print(f"[warn] no results.jsonl row found in {wd}; skipping aggregate")
            continue
        rows.append(row)

    ended_at = dt.datetime.now(dt.UTC).isoformat()
    agg = aggregate(rows)
    print_table(rows, agg)

    summary = {
        "schema": "preflight-series-summary.v1",
        "model": args.model,
        "shell": shell,
        "runs_requested": args.runs,
        "runs_collected": len(rows),
        "started_at": started_at,
        "ended_at": ended_at,
        "base_dir": str(base_dir),
        "per_run": [per_run_view(r) for r in rows],
        "aggregate": agg,
    }
    ts = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_name = f"series_{ts}_{sanitize_model(args.model)}_runs{args.runs}.json"
    out_path = summary_dir / out_name
    out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"\nsummary: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
