#!/usr/bin/env bash
set -eo pipefail
WORK_DIR="${WORK_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
BUILD="$WORK_DIR/build-hidden"
cmake -S "$HERE" -B "$BUILD" -DCMAKE_BUILD_TYPE=Debug -DWORK_DIR="$WORK_DIR" >/dev/null
cmake --build "$BUILD" --target test_token_buffer_hidden
"$BUILD/test_token_buffer_hidden"
