#!/usr/bin/env bash
set -eo pipefail
WORK_DIR="${WORK_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
echo "Running public tests against $WORK_DIR"
cd "$WORK_DIR"
python -m pytest public/tests -q
