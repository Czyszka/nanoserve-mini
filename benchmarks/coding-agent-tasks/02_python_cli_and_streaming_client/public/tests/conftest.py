"""Pytest config — make the agent's ``starter/`` importable.

The harness sets ``WORK_DIR`` to the temp work-dir containing ``starter/``.
When run in-repo (smoke check), fall back to the repo task directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _starter_dir() -> Path:
    work_dir = os.environ.get("WORK_DIR")
    if work_dir:
        return Path(work_dir) / "starter"
    # Fall back to the repo location of this task.
    return Path(__file__).resolve().parents[2] / "starter"


_STARTER = _starter_dir()
if _STARTER.is_dir():
    sys.path.insert(0, str(_STARTER))
