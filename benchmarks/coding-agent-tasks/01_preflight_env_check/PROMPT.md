# Task: preflight env check (PowerShell / bash)

The file `preflight.ps1` (or `preflight.sh`) is a script that checks the
environment of a GPU server (docker, nvidia-smi, free disk, TCP ports,
versions of python/uv/docker compose). It prints JSON to stdout and sets
an exit code.

The task has 2 stages. Work in the current directory.
You can run `public_tests/run.ps1` (or `public_tests/run.sh`) to check
your progress against the visible subset of tests.

## CLI surface

Single-shot mode:

```
preflight --path <dir> --min-free-mb <N> [--host <ip>] --port <p> [--port <p2> ...]
```

- `--host <ip>` is optional and defaults to `127.0.0.1`. It applies to all
  `--port` checks in the invocation.

Output: one JSON document on stdout with shape:

```json
{
  "checks": {
    "docker":   {"available": true, "version": "..."},
    "gpus":     {"available": true, "gpus": [{"name": "...", "memory_total": "...", "memory_free": "..."}], "error": null},
    "disk":     {"path": "...", "free_mb": 42000, "min_free_mb": 10000, "ok": true, "error": null},
    "ports":    [{"host": "127.0.0.1", "port": 8000, "free": true, "error": null}],
    "versions": {"python": "...", "uv": "...", "compose": "..."}
  },
  "all_ok": true
}
```

Exit code:

- 0 = all checks ok
- 1 = at least one check failed
- 2 = invocation error (bad args, etc.)

## Stage 1 — fix 4 bugs

1. The `docker` check reports `available=true` even when the `docker` command
   is missing.
2. The `disk` check compares free space as strings, so the comparison is
   lexicographic instead of numeric. For example `"15000" -ge "9000"` is
   `$false` (because `"1" < "9"`), so 15000 MB free with `--min-free-mb 9000`
   is incorrectly reported as `ok=false`. Use numeric comparison.
3. The `ports` check treats a connect timeout as "port free". A timeout means
   we do not know (typically firewalled); it must NOT be reported as free.
   Expected for a firewalled / unreachable host:
   `{"host": "<ip>", "port": <n>, "free": false, "error": "timeout"}`.
4. The `main` path always ends with `exit 0`, ignoring the aggregated
   `all_ok` value. It should exit 1 when any check failed.

Fix all 4. Do not add new checks or flags in Stage 1.

## Stage 2 — add `--watch` mode

Once Stage 1 passes, add the following flags:

- `--watch` (switch)
- `--interval-s <N>` (int, seconds)
- `--duration-s <M>` (int, seconds)
- `--output <path>` (path to a JSONL file)

Semantics:

- Tick at t=0, then every `interval-s` seconds, until `t >= duration-s`.
  Example: `--interval-s 1 --duration-s 3` produces 3 ticks (t=0, t=1, t=2).
- Each tick runs the full check set (same as single-shot) and appends ONE
  JSON line to `--output`:
  `{"tick": <i>, "timestamp": "<ISO-8601>", "checks": {...}, "all_ok": <bool>}`.
- Exit code:
  - 0 if all ticks had `all_ok=true`,
  - 1 if any tick had a failed check,
  - 2 on invocation error.
- Clean shutdown on Ctrl+C is acceptable.

## Notes

- Keep the single-shot JSON shape unchanged.
- Comments and messages in English.
- The script must remain Windows PowerShell 5.1 compatible (no `?.`, `??`,
  ternary `?:`, `pwsh`-only features).
