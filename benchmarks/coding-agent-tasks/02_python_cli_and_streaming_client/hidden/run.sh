#!/usr/bin/env bash
set -eo pipefail
WORK_DIR="${WORK_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
echo "Running hidden tests against $WORK_DIR"
cd "$WORK_DIR"
python -m pytest hidden/tests -q
