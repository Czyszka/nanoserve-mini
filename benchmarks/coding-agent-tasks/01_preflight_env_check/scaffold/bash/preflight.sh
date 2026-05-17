#!/usr/bin/env bash
# Preflight environment check for a GPU server (bash variant).
# Emits one JSON document on stdout and sets exit code.
#
# Contains 4 seeded bugs (documented in PROMPT.md, Stage 1):
#   1. docker check reports available=true even when docker is missing
#   2. disk free comparison is lexicographic instead of numeric
#   3. port timeout is reported as free=true (should be free=false)
#   4. main always exits 0, ignoring all_ok
#
# Stage 2 (--watch) is intentionally not yet implemented.

set -uo pipefail

PATH_ARG=""
MIN_FREE_MB=0
HOST="127.0.0.1"
PORTS=()
WATCH=0
INTERVAL_S=0
DURATION_S=0
OUTPUT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --path)         PATH_ARG="${2:-}"; shift 2 ;;
        --min-free-mb)  MIN_FREE_MB="${2:-0}"; shift 2 ;;
        --host)         HOST="${2:-}"; shift 2 ;;
        --port)         PORTS+=("${2:-}"); shift 2 ;;
        --watch)        WATCH=1; shift 1 ;;
        --interval-s)   INTERVAL_S="${2:-0}"; shift 2 ;;
        --duration-s)   DURATION_S="${2:-0}"; shift 2 ;;
        --output)       OUTPUT="${2:-}"; shift 2 ;;
        *)              echo "[error] unknown argument: $1" >&2; exit 2 ;;
    esac
done

check_docker() {
    # BUG 1: available defaults to true and is never flipped to false when
    # docker is not on PATH.
    local available=true
    local version=""
    local error=""
    if command -v docker >/dev/null 2>&1; then
        version="$(docker --version 2>&1 | head -n 1)"
    else
        error="docker not on PATH"
    fi
    jq -nc \
        --argjson available "$available" \
        --arg version "$version" \
        --arg error "$error" \
        '{available: $available,
          version: (if $version=="" then null else $version end),
          error:   (if $error==""   then null else $error end)}'
}

check_gpus() {
    local out=""
    local rc=0
    if command -v nvidia-smi >/dev/null 2>&1; then
        out="$(nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null)" || rc=$?
    else
        rc=127
    fi
    if [[ "$rc" -ne 0 || -z "$out" ]]; then
        jq -nc '{available: false, gpus: [], error: "nvidia-smi failed or absent"}'
        return
    fi
    local gpus_json
    gpus_json="$(printf '%s\n' "$out" | jq -Rn '
        [inputs
         | split(",")
         | map(gsub("^ +| +$"; ""))
         | select(length >= 3)
         | {name: .[0], memory_total: .[1], memory_free: .[2]}]
    ')"
    jq -nc --argjson gpus "$gpus_json" '{available: true, gpus: $gpus, error: null}'
}

check_disk() {
    local path="$1"
    local min_free="$2"
    local free_mb_json=null
    local ok=false
    local error=""
    if [[ -z "$path" ]]; then
        error="no --path provided"
    elif [[ ! -e "$path" ]]; then
        error="path does not exist: $path"
    else
        local free_mb
        free_mb="$(df -B 1M --output=avail "$path" 2>/dev/null | tail -n 1 | tr -d ' ')"
        if [[ -z "$free_mb" ]]; then
            error="df returned no value"
        else
            free_mb_json="$free_mb"
            # BUG 2: string comparison instead of numeric. Inside [[ ]] the
            # `>` operator is lexicographic, so "100000" > "9" is false
            # (because "1" < "9"). Numeric -ge would correctly return true.
            if [[ "$free_mb" > "$min_free" || "$free_mb" == "$min_free" ]]; then
                ok=true
            fi
        fi
    fi
    jq -nc \
        --argjson free "$free_mb_json" \
        --argjson min "$min_free" \
        --argjson ok "$ok" \
        --arg path "$path" \
        --arg error "$error" \
        '{path: $path, free_mb: $free, min_free_mb: $min, ok: $ok,
          error: (if $error=="" then null else $error end)}'
}

check_port() {
    local host="$1"
    local port="$2"
    local free=true
    local error=""
    if timeout 1 bash -c "exec 3<>/dev/tcp/${host}/${port}" 2>/dev/null; then
        free=false
        error="in_use"
    else
        local rc=$?
        if [[ $rc -eq 124 ]]; then
            # BUG 3: timeout means we do not know (often firewalled); buggy
            # code keeps free=true, but it should be false with error=timeout.
            free=true
            error="timeout"
        else
            # connect refused -> nothing listening -> port is free
            free=true
            error=""
        fi
    fi
    jq -nc \
        --arg host "$host" \
        --argjson port "$port" \
        --argjson free "$free" \
        --arg error "$error" \
        '{host: $host, port: $port, free: $free,
          error: (if $error=="" then null else $error end)}'
}

get_tool_version() {
    local name="$1"; shift
    if command -v "$name" >/dev/null 2>&1; then
        "$name" "$@" 2>&1 | head -n 1
    fi
}

check_versions() {
    local py uv compose
    py="$(get_tool_version python --version)"
    uv="$(get_tool_version uv --version)"
    compose="$(get_tool_version docker compose version)"
    jq -nc \
        --arg python "$py" --arg uv "$uv" --arg compose "$compose" \
        '{python:  (if $python==""  then null else $python  end),
          uv:      (if $uv==""      then null else $uv      end),
          compose: (if $compose=="" then null else $compose end)}'
}

run_checks() {
    local docker_j gpus_j disk_j versions_j ports_j
    docker_j="$(check_docker)"
    gpus_j="$(check_gpus)"
    disk_j="$(check_disk "$PATH_ARG" "$MIN_FREE_MB")"
    versions_j="$(check_versions)"

    local parts=()
    if [[ "${#PORTS[@]}" -gt 0 ]]; then
        local p
        for p in "${PORTS[@]}"; do
            [[ -z "$p" ]] && continue
            parts+=("$(check_port "$HOST" "$p")")
        done
    fi
    if [[ "${#parts[@]}" -gt 0 ]]; then
        ports_j="$(printf '%s\n' "${parts[@]}" | jq -cs '.')"
    else
        ports_j="[]"
    fi

    local checks
    checks="$(jq -nc \
        --argjson docker   "$docker_j" \
        --argjson gpus     "$gpus_j" \
        --argjson disk     "$disk_j" \
        --argjson ports    "$ports_j" \
        --argjson versions "$versions_j" \
        '{docker: $docker, gpus: $gpus, disk: $disk, ports: $ports, versions: $versions}')"

    local all_ok
    all_ok="$(jq -nc --argjson c "$checks" --arg path "$PATH_ARG" '
        (($c.docker.available == true)
         and ($c.gpus.available == true)
         and (if $path == "" then true else $c.disk.ok == true end)
         and (all($c.ports[]; .free == true)))
    ')"

    jq -nc --argjson checks "$checks" --argjson all_ok "$all_ok" \
        '{checks: $checks, all_ok: $all_ok}'
}

invoke_single_shot() {
    local result
    result="$(run_checks)"
    echo "$result"
    # BUG 4: always exit 0; should follow all_ok.
    exit 0
}

invoke_watch() {
    echo "[error] watch mode not yet implemented (Stage 2)" >&2
    exit 2
}

if [[ "$WATCH" -eq 1 ]]; then
    invoke_watch
else
    invoke_single_shot
fi
