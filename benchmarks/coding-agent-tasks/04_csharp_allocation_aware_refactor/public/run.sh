#!/usr/bin/env bash
set -eo pipefail
WORK_DIR="${WORK_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
dotnet test "$(dirname "$0")/tests/LogQueryParser.PublicTests.csproj" \
  -c Release -p:WorkDir="$WORK_DIR" --nologo --verbosity minimal
