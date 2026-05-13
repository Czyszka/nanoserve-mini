"""Hidden-test pytest config — mirror of public conftest."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _starter_dir() -> Path:
    work_dir = os.environ.get("WORK_DIR")
    if work_dir:
        return Path(work_dir) / "starter"
    return Path(__file__).resolve().parents[2] / "starter"


_STARTER = _starter_dir()
if _STARTER.is_dir():
    sys.path.insert(0, str(_STARTER))
