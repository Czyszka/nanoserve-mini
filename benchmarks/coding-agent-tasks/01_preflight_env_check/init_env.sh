#!/usr/bin/env bash
# init_env.sh - initializes the test environment for task 01_preflight_env_check (bash variant).
#
# Usage:
#   ./init_env.sh --model <model> --run-number <NN> [--base-dir <path>]
#
# 1. Checks for required tools (OS, claude, git, python, uv, jq). Bash itself is skipped - if the script started, it is available.
# 2. Creates work-dir <base-dir>/<YYYY-MM-DD>_<model>_run<NN>/.
# 3. Copies PROMPT.md, preflight.sh, public_tests/{cases.json,run.sh}.
# 4. Initializes git + initial commit.
# 5. Prints the ready-to-run harness command.

set -euo pipefail

TASK_ID="01_preflight_env_check"
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODEL=""
RUN_NUMBER=""
BASE_DIR="./runs"

usage() {
    echo "usage: $0 --model <model> --run-number <NN> [--base-dir <path>]" >&2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)       MODEL="${2:-}"; shift 2 ;;
        --run-number)  RUN_NUMBER="${2:-}"; shift 2 ;;
        --base-dir)    BASE_DIR="${2:-}"; shift 2 ;;
        -h|--help)     usage; exit 0 ;;
        *)             echo "[error] unknown argument: $1" >&2; usage; exit 1 ;;
    esac
done

if [[ -z "$MODEL" ]]; then
    echo "[error] missing required --model" >&2; usage; exit 1
fi
if [[ -z "$RUN_NUMBER" ]]; then
    echo "[error] missing required --run-number" >&2; usage; exit 1
fi

check_tool() {
    local name="$1"
    local version_arg="${2:---version}"
    if ! command -v "$name" >/dev/null 2>&1; then
        echo "[missing] $name"
        return 1
    fi
    local ver
    ver="$("$name" "$version_arg" 2>&1 | head -n 1 || echo '(no version)')"
    echo "[ok]      $name $ver"
    return 0
}

# --- 1. Environment check ----------------------------------------------------
echo "== environment check =="
echo "[ok]      OS $(uname -srm)"

missing=0
check_tool claude --version || missing=$((missing+1))
check_tool git    --version || missing=$((missing+1))
check_tool python --version || missing=$((missing+1))
check_tool uv     --version || missing=$((missing+1))
check_tool jq     --version || missing=$((missing+1))

if [[ $missing -gt 0 ]]; then
    echo ""
    echo "[error] missing $missing tool(s) - aborting." >&2
    exit 1
fi

# --- 2. Construct and validate work-dir --------------------------------------
MODEL_SAN="${MODEL//\//-}"
MODEL_SAN="${MODEL_SAN//\\/-}"
DATE_UTC="$(date -u +%Y-%m-%d)"
WORK_DIR_NAME="${DATE_UTC}_${MODEL_SAN}_run${RUN_NUMBER}"

mkdir -p "$BASE_DIR"
BASE_DIR_ABS="$(cd "$BASE_DIR" && pwd)"
WORK_DIR="${BASE_DIR_ABS}/${WORK_DIR_NAME}"

echo ""
echo "== work-dir =="
echo "  $WORK_DIR"

if [[ -d "$WORK_DIR" ]]; then
    if [[ -n "$(ls -A "$WORK_DIR" 2>/dev/null)" ]]; then
        echo ""
        echo "[error] work-dir $WORK_DIR exists and is not empty; remove it or pass a different --run-number" >&2
        exit 1
    fi
else
    mkdir -p "$WORK_DIR"
fi

# --- 3. Copy scaffold --------------------------------------------------------
echo ""
echo "== copying scaffold =="

SRC_PROMPT="${SCRIPT_ROOT}/PROMPT.md"
SRC_PREFLIGHT="${SCRIPT_ROOT}/scaffold/bash/preflight.sh"
SRC_CASES="${SCRIPT_ROOT}/public_tests/cases.json"
SRC_RUNNER="${SCRIPT_ROOT}/public_tests/bash/run.sh"

for f in "$SRC_PROMPT" "$SRC_PREFLIGHT" "$SRC_CASES" "$SRC_RUNNER"; do
    if [[ ! -f "$f" ]]; then
        echo "[error] missing source file: $f" >&2
        exit 1
    fi
done

mkdir -p "${WORK_DIR}/public_tests"
cp "$SRC_PROMPT"    "${WORK_DIR}/PROMPT.md"
cp "$SRC_PREFLIGHT" "${WORK_DIR}/preflight.sh"
cp "$SRC_CASES"     "${WORK_DIR}/public_tests/cases.json"
cp "$SRC_RUNNER"    "${WORK_DIR}/public_tests/run.sh"
chmod +x "${WORK_DIR}/preflight.sh" "${WORK_DIR}/public_tests/run.sh"

echo "  PROMPT.md"
echo "  preflight.sh"
echo "  public_tests/cases.json"
echo "  public_tests/run.sh"

# --- 4. git init + initial commit --------------------------------------------
echo ""
echo "== git init =="
(
    cd "$WORK_DIR"
    git init --quiet
    git add -A
    git -c user.name="nanoserve-init" -c user.email="init@nanoserve.local" \
        commit --quiet -m "baseline: ${TASK_ID} scaffold for ${MODEL} run${RUN_NUMBER}"
    echo "  baseline_commit: $(git rev-parse HEAD)"
)

# --- 5. Next step ------------------------------------------------------------
echo ""
echo "== next step =="
RUN_ID="$WORK_DIR_NAME"
RUNNER_PATH="${SCRIPT_ROOT}/run_eval.py"
cat <<EOF
uv run python ${RUNNER_PATH} \\
  --work-dir ${WORK_DIR} \\
  --model ${MODEL}
EOF

exit 0
