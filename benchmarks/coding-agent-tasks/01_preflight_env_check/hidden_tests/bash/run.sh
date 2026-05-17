#!/usr/bin/env bash
# Hidden test runner for preflight.sh.
#
# Reads ../cases.json from this hidden_tests tree, substitutes placeholders
# ({TMP}, {EMPTY_DIR}), runs the agent's preflight.sh, validates expected exit
# codes and JSON/JSONL assertions, and emits one machine-readable SUMMARY_JSON
# line consumed by run_eval.py.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CASES_PATH="${SCRIPT_DIR}/../cases.json"
PREFLIGHT_PATH=""

usage() {
    echo "usage: $0 --preflight <path> [--cases <path>]" >&2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --preflight)
            PREFLIGHT_PATH="${2:-}"
            shift 2
            ;;
        --cases)
            CASES_PATH="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[error] unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

if [[ -z "$PREFLIGHT_PATH" ]]; then
    echo "[error] missing required --preflight" >&2
    usage
    exit 2
fi

if [[ ! -f "$PREFLIGHT_PATH" ]]; then
    echo "[error] preflight not found: $PREFLIGHT_PATH" >&2
    exit 2
fi

if [[ ! -f "$CASES_PATH" ]]; then
    echo "[error] cases file not found: $CASES_PATH" >&2
    exit 2
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "[error] jq is required for bash hidden tests" >&2
    exit 2
fi

BASH_BIN="$(command -v bash)"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/preflight-hidden-XXXXXXXX")"
EMPTY_DIR="${TMP_ROOT}/empty"
mkdir -p "$EMPTY_DIR"
# Populate EMPTY_DIR with the core tools the bash scaffold needs (but NOT
# docker), so the "PATH={EMPTY_DIR}" docker-missing case still produces
# JSON. Symlink, fall back to copy on platforms that lack symlink support.
for tool in bash jq df tr head tail timeout; do
    src="$(command -v "$tool" 2>/dev/null || true)"
    if [[ -n "$src" ]]; then
        ln -sf "$src" "${EMPTY_DIR}/${tool}" 2>/dev/null || cp -f "$src" "${EMPTY_DIR}/${tool}"
    fi
done

cleanup() {
    rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

substitute_placeholders() {
    local value="$1"
    value="${value//\{TMP\}/$TMP_ROOT}"
    value="${value//\{EMPTY_DIR\}/$EMPTY_DIR}"
    printf '%s' "$value"
}

jq_path() {
    local dotted="$1"
    printf '.%s' "$dotted"
}

json_array_from_lines() {
    jq -Rn '[inputs]'
}

run_case() {
    local case_json="$1"
    local case_id stage
    case_id="$(jq -r '.id' <<<"$case_json")"
    stage="$(jq -r '.stage // 0' <<<"$case_json")"

    local -a args=()
    while IFS= read -r arg; do
        arg="${arg%$'\r'}"  # strip CR injected by jq on MSYS/MINGW
        args+=("$(substitute_placeholders "$arg")")
    done < <(jq -r '.args[]?' <<<"$case_json")

    local -a env_names=()
    local -a env_old_values=()
    local -a env_was_set=()
    while IFS=$'\t' read -r name value; do
        name="${name%$'\r'}"
        value="${value%$'\r'}"
        [[ -z "$name" ]] && continue
        env_names+=("$name")
        if [[ -v "$name" ]]; then
            env_was_set+=("1")
            env_old_values+=("${!name}")
        else
            env_was_set+=("0")
            env_old_values+=("")
        fi
        printf -v "$name" '%s' "$(substitute_placeholders "$value")"
        export "$name"
    done < <(jq -r '.env // {} | to_entries[] | [.key, (.value | tostring)] | @tsv' <<<"$case_json")

    local stdout exit_code
    stdout="$("$BASH_BIN" "$PREFLIGHT_PATH" "${args[@]}" 2>/dev/null)"
    exit_code=$?

    local idx
    for idx in "${!env_names[@]}"; do
        if [[ "${env_was_set[$idx]}" == "1" ]]; then
            printf -v "${env_names[$idx]}" '%s' "${env_old_values[$idx]}"
            export "${env_names[$idx]}"
        else
            unset "${env_names[$idx]}"
        fi
    done

    local -a failures=()

    if jq -e 'has("expect_exit_code")' <<<"$case_json" >/dev/null; then
        local expected_exit
        expected_exit="$(jq -r '.expect_exit_code' <<<"$case_json")"
        if [[ "$exit_code" != "$expected_exit" ]]; then
            failures+=("exit_code expected=${expected_exit} got=${exit_code}")
        fi
    fi

    if jq -e 'has("expect_json_path") or has("expect_json_path_exists")' <<<"$case_json" >/dev/null; then
        if ! jq -e . >/dev/null 2>&1 <<<"$stdout"; then
            failures+=("stdout not valid JSON")
        else
            while IFS=$'\t' read -r path expected_json; do
                path="${path%$'\r'}"
                expected_json="${expected_json%$'\r'}"
                [[ -z "$path" ]] && continue
                local expr actual_json
                expr="$(jq_path "$path")"
                if ! jq -e "$expr != null" <<<"$stdout" >/dev/null 2>&1; then
                    failures+=("json path '${path}' missing")
                elif ! actual_json="$(jq -c "$expr" <<<"$stdout" 2>/dev/null)"; then
                    failures+=("json path '${path}' missing")
                elif [[ "$actual_json" != "$expected_json" ]]; then
                    failures+=("json path '${path}' expected=${expected_json} got=${actual_json}")
                fi
            done < <(jq -r '.expect_json_path // {} | to_entries[] | [.key, (.value | tojson)] | @tsv' <<<"$case_json")

            while IFS= read -r path; do
                path="${path%$'\r'}"
                [[ -z "$path" ]] && continue
                local expr
                expr="$(jq_path "$path")"
                if ! jq -e "$expr != null" <<<"$stdout" >/dev/null 2>&1; then
                    failures+=("json path '${path}' missing")
                fi
            done < <(jq -r '.expect_json_path_exists[]?' <<<"$case_json")
        fi
    fi

    if jq -e 'has("expect_jsonl_line_count")' <<<"$case_json" >/dev/null; then
        local path count line_count
        path="$(substitute_placeholders "$(jq -r '.expect_jsonl_line_count.path' <<<"$case_json")")"
        count="$(jq -r '.expect_jsonl_line_count.count' <<<"$case_json")"
        if [[ ! -f "$path" ]]; then
            failures+=("jsonl file '${path}' not found")
        else
            line_count="$(grep -cve '^[[:space:]]*$' "$path" || true)"
            if [[ "$line_count" != "$count" ]]; then
                failures+=("jsonl line count expected=${count} got=${line_count} at '${path}'")
            fi
        fi
    fi

    if jq -e 'has("expect_jsonl_lines_field")' <<<"$case_json" >/dev/null; then
        local path field expected_values got_values
        path="$(substitute_placeholders "$(jq -r '.expect_jsonl_lines_field.path' <<<"$case_json")")"
        field="$(jq -r '.expect_jsonl_lines_field.field' <<<"$case_json")"
        expected_values="$(jq -c '.expect_jsonl_lines_field.expected_values' <<<"$case_json")"
        if [[ ! -f "$path" ]]; then
            failures+=("jsonl file '${path}' not found")
        else
            got_values="$(jq -s -c --arg field "$field" '[.[] | .[$field]]' "$path" 2>/dev/null)"
            if [[ $? -ne 0 ]]; then
                failures+=("jsonl line not valid JSON")
            elif [[ "$got_values" != "$expected_values" ]]; then
                failures+=("jsonl field '${field}' expected=${expected_values} got=${got_values}")
            fi
        fi
    fi

    if [[ "${#failures[@]}" -eq 0 ]]; then
        echo "[PASS] stage${stage} ${case_id}" >&2
    else
        echo "[FAIL] stage${stage} ${case_id}" >&2
        for failure in "${failures[@]}"; do
            echo "       - ${failure}" >&2
        done
    fi

    local failures_json
    if [[ "${#failures[@]}" -eq 0 ]]; then
        failures_json="[]"
    else
        failures_json="$(printf '%s\n' "${failures[@]}" | json_array_from_lines)"
    fi
    jq -cn \
        --arg id "$case_id" \
        --argjson stage "$stage" \
        --argjson passed "$([[ "${#failures[@]}" -eq 0 ]] && echo true || echo false)" \
        --argjson failures "$failures_json" \
        '{id: $id, stage: $stage, passed: $passed, failures: $failures}'
}

results_file="${TMP_ROOT}/results.jsonl"
while IFS= read -r case_json; do
    case_json="${case_json%$'\r'}"
    run_case "$case_json" >>"$results_file"
done < <(jq -c '.[]' "$CASES_PATH")

summary="$(jq -s -c '{schema: "preflight-hidden-tests-summary.v1", cases: .}' "$results_file")"
echo
echo "SUMMARY_JSON ${summary}"

failed="$(jq '[.cases[] | select(.passed == false)] | length' <<<"$summary")"
if [[ "$failed" -gt 0 ]]; then
    exit 1
fi
exit 0
