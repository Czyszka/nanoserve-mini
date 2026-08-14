#!/usr/bin/env python3
"""Client-side setup for the offline Claude Code kit (run via setup.bat).

Runs with the Python bundled in the kit — stdlib only. Steps, in order:

1. Install the user configuration: copy the kit's ``userdir/.claude`` to
   ``%USERPROFILE%\\.claude``. An existing ``.claude`` is renamed to
   ``.claude.backup-<timestamp>`` first — nothing is overwritten silently.
   Skip with ``--skip-userdir``.
2. Environment variables: the ``claude.bat`` launcher sets them per session,
   so by default nothing is written. ``--persist`` additionally stores the
   same variables in the user profile via ``setx``.
3. Smoke test: run ``claude.bat --model <model> -p "<smoke prompt>"`` (values
   baked into ``kit_config.json`` at build time) and report exit code, wall
   time and the start of the response. Skip with ``--skip-smoke``.

Exit codes: 0 = OK, 1 = smoke test or setx failed, 2 = kit layout broken.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

_KIT_DIR = Path(__file__).resolve().parent

# Injectable subprocess runner (tests substitute a fake; pattern shared with
# the repo's sample_gpu_metrics.py).
_run = subprocess.run


def install_userdir(
    source: Path,
    *,
    home: Path,
    now: datetime | None = None,
) -> tuple[Path, Path | None]:
    """Copy ``.claude`` into the profile; back up an existing one first.

    Returns ``(installed_path, backup_path_or_None)``.
    """
    if not source.is_dir():
        raise FileNotFoundError(f"kit userdir missing: {source}")
    target = home / ".claude"
    backup: Path | None = None
    if target.exists():
        stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
        backup = home / f".claude.backup-{stamp}"
        target.rename(backup)
    shutil.copytree(source, target)
    return target, backup


def persist_env(env: dict[str, str], *, runner=None) -> list[str]:
    """Store env vars in the user profile via setx. Returns failed keys."""
    runner = runner or _run
    failed: list[str] = []
    for key, value in env.items():
        result = runner(["setx", key, value], capture_output=True, text=True)
        if result.returncode != 0:
            failed.append(key)
    return failed


def run_smoke(
    kit_dir: Path,
    *,
    model: str,
    prompt: str,
    timeout: float,
    runner=None,
    log=print,
) -> int:
    """Run one headless Claude Code prompt through claude.bat; 0 on success."""
    runner = runner or _run
    launcher = kit_dir / "claude.bat"
    command = [str(launcher), "--model", model, "-p", prompt]
    log(f"smoke test: {' '.join(command)} (timeout {timeout:.0f}s)")
    started = time.perf_counter()
    try:
        result = runner(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f"smoke test TIMEOUT after {timeout:.0f}s — server not responding? "
            "Check the gateway address in claude.bat and network reachability.")
        return 1
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-500:]
        log(f"smoke test FAILED (exit {result.returncode}, {elapsed:.1f}s):\n{tail}")
        return 1
    head = (result.stdout or "").strip()[:300]
    log(f"smoke test OK ({elapsed:.1f}s). Response starts:\n{head}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare this Windows client for Claude Code "
        "(userdir, optional persistent env vars, smoke test).",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Also store the env vars permanently in the user profile (setx).",
    )
    parser.add_argument("--skip-userdir", action="store_true",
                        help="Do not touch %%USERPROFILE%%\\.claude.")
    parser.add_argument("--skip-smoke", action="store_true",
                        help="Do not run the test prompt.")
    parser.add_argument(
        "--smoke-timeout",
        type=float,
        default=600.0,
        help="Smoke-test timeout in seconds (default: 600 — first response "
        "may include model load on the server).",
    )
    parser.add_argument("--home", default=None, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    config_path = _KIT_DIR / "kit_config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"broken kit: cannot read {config_path} ({exc})", file=sys.stderr)
        return 2

    home = Path(args.home) if args.home else Path.home()

    if not args.skip_userdir:
        try:
            target, backup = install_userdir(_KIT_DIR / "userdir" / ".claude", home=home)
        except (OSError, FileNotFoundError) as exc:
            print(f"userdir install failed: {exc}", file=sys.stderr)
            return 2
        if backup is not None:
            print(f"existing config backed up to {backup}")
        print(f"user config installed at {target}")
    else:
        print("userdir step skipped (--skip-userdir)")

    if args.persist:
        failed = persist_env(config["env"])
        if failed:
            print(f"setx failed for: {', '.join(failed)}", file=sys.stderr)
            return 1
        print("env vars stored permanently in the user profile (setx)")
    else:
        print("env vars are session-only (claude.bat sets them); "
              "use --persist to store them permanently")

    if args.skip_smoke:
        print("smoke test skipped (--skip-smoke)")
        return 0
    return run_smoke(
        _KIT_DIR,
        model=config["model"],
        prompt=config["smoke_prompt"],
        timeout=args.smoke_timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
