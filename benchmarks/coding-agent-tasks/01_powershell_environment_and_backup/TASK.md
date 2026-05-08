# Task 01 — PowerShell environment status and results export

Difficulty: A

Goal: implement a small PowerShell utility that validates a local LLM serving environment and exports small benchmark artifacts into a timestamped backup directory.

This task is intentionally synthetic. It should be solved in a temporary task repository, not in `nanoserve-mini`.

---

## Agent prompt

You are given a partially implemented PowerShell script called `Export-RunArtifacts.ps1`.

Your job is to make it production-usable for a small local benchmark workflow.

The script should:

1. Validate that a results directory exists.
2. Validate Docker availability (non-fatal diagnostic).
3. Optionally check that one or more vLLM endpoints expose `/metrics`.
4. Export selected small files from a run directory into a timestamped backup directory.
5. Produce a machine-readable summary JSON.
6. Fail clearly on invalid inputs.

You may edit the script and add tests/helpers if useful. You may run PowerShell commands and tests.

---

## Starter repository layout

```text
01_powershell_environment_and_backup/
  README.md
  Export-RunArtifacts.ps1
  tests/
    public/
      run-public-tests.ps1
    hidden/
      run-hidden-tests.ps1        # not visible to agent during run
  fixtures/
    sample-run/
      config.json
      summary.md
      singlestream_lite_latency/
        minimax_ttft.json
      large.log
      model-cache.bin
```

---

## Required behavior

### Stage 1 — argument validation

The script must accept:

```powershell
./Export-RunArtifacts.ps1 \
  -RunDirectory ./fixtures/sample-run \
  -OutputDirectory ./out \
  -Endpoint http://127.0.0.1:8000 \
  -Endpoint http://127.0.0.1:8001 \
  -Timestamp 20260508-101530Z
```

Required parameters:

- `-RunDirectory`
- `-OutputDirectory`

Optional parameters:

- `-Endpoint` as zero or more endpoint URLs.
- `-MaxFileSizeBytes`, default `1048576`.
- `-IncludePatterns`, default should include small benchmark artifacts such as `*.json`, `*.jsonl`, `*.md`, `*.txt`, `*.csv`, `*.prom`.
- `-Timestamp`, format `yyyyMMdd-HHmmssZ` (for deterministic tests).
- `-DryRun` (optional/bonus stage; not required for core public tests).

Backup directory naming must be deterministic:

```text
<OutputDirectory>/<RunDirectory leaf name>__<Timestamp>/
```

Example:

```text
./out/sample-run__20260508-101530Z/
```

Rules:

- If `-Timestamp` is provided, use it exactly in the backup directory name.
- If `-Timestamp` is omitted, generate current UTC timestamp in `yyyyMMdd-HHmmssZ`.
- Invalid timestamp format is a fatal input validation error.

The script should fail with input-validation exit code `1` for invalid input, including:

- `RunDirectory` does not exist,
- `MaxFileSizeBytes` is less than or equal to zero,
- `Timestamp` format is invalid,
- endpoint URL is malformed.

### Stage 2 — Docker and endpoint status

Docker check behavior:

- Docker check is non-fatal.
- If Docker is available, record version/status.
- If Docker is unavailable, record `docker.available = false` and `docker.error`, and continue.
- If artifact export succeeds, Docker failure alone must still result in exit code `0`.

Endpoint check behavior:

- For each endpoint, query `<endpoint>/metrics`.
- Malformed endpoint URL is a fatal input validation error.
- Well-formed but unreachable endpoint is non-fatal and must be recorded.
- `/metrics` returning non-2xx is non-fatal and must be recorded.
- Endpoint failures must not stop artifact export.

Endpoint summary entries should follow this shape:

```json
{
  "url": "http://127.0.0.1:8000",
  "metrics_url": "http://127.0.0.1:8000/metrics",
  "ok": true,
  "status_code": 200,
  "error": null
}
```

Failure example:

```json
{
  "url": "http://127.0.0.1:8001",
  "metrics_url": "http://127.0.0.1:8001/metrics",
  "ok": false,
  "status_code": null,
  "error": "connection refused"
}
```

### Stage 3 — artifact export

The script should copy only small, useful files from `RunDirectory` into the timestamped backup directory under `OutputDirectory`.

Default include set:

- `.json`
- `.jsonl`
- `.md`
- `.txt`
- `.csv`
- `.prom`

Always-excluded extensions:

- `.bin`
- `.pt`
- `.safetensors`
- `.log`

Always-excluded directory names:

- `cache`
- `.cache`
- `hf_cache`
- `models`

Filtering and precedence rules:

- Exclusion rules always win over include patterns.
- Even if `-IncludePatterns "*.log"` is supplied, `.log` files must still be excluded.
- Directory exclusions apply recursively to all descendants.
- Files larger than `MaxFileSizeBytes` must be skipped.
- Files not matching include patterns should be skipped with reason `pattern_not_included`.
- Do not add an unsafe override flag in this task.

The relative directory structure must be preserved.

### Stage 4 — summary JSON

The script must write `export-summary.json` into the backup directory.

Required fields (minimum schema):

```json
{
  "schema": "coding-agent-task.powershell-export.v1",
  "run_directory": "...",
  "backup_directory": "...",
  "dry_run": false,
  "docker": {
    "available": true,
    "version": "Docker version ...",
    "error": null
  },
  "endpoints": [
    {
      "url": "http://127.0.0.1:8000",
      "metrics_url": "http://127.0.0.1:8000/metrics",
      "ok": true,
      "status_code": 200,
      "error": null
    }
  ],
  "files_copied": 3,
  "files_skipped": 2,
  "copied_files": [
    "config.json",
    "summary.md",
    "singlestream_lite_latency/minimax_ttft.json"
  ],
  "skipped_files": [
    {
      "path": "large.log",
      "reason": "extension_excluded"
    },
    {
      "path": "model-cache.bin",
      "reason": "extension_excluded"
    }
  ],
  "skipped_reasons": {
    "too_large": 0,
    "extension_excluded": 2,
    "directory_excluded": 0,
    "pattern_not_included": 0
  }
}
```

Rules:

- `copied_files` and `skipped_files[].path` must be relative to `RunDirectory`.
- Paths in summary JSON must use forward slashes (`/`) even on Windows.
- `skipped_reasons` must include all known keys, even when zero.

### Stage 5 — exit codes

Exit code contract:

```text
0 = export completed successfully; non-fatal Docker/endpoint failures may be recorded
1 = invalid input, for example missing RunDirectory, invalid Timestamp, malformed endpoint URL, invalid MaxFileSizeBytes
2 = artifact export failed, for example OutputDirectory cannot be created or a selected file cannot be copied
3 = unexpected runtime error
```

Docker unavailability or endpoint unavailability/non-2xx alone must not produce non-zero exit if export succeeds.

### Stage 6 — optional dry run extension

`-DryRun` is an optional extension stage (bonus). If implemented:

- Validate inputs.
- Check Docker and endpoints.
- Compute which files would be copied/skipped.
- Do not copy files.
- Prefer still creating the timestamped backup directory and writing `export-summary.json` for testability.
- Summary should set `"dry_run": true`.

---

## Public tests

Public tests should verify:

- missing `RunDirectory` fails with exit code `1`,
- invalid `Timestamp` fails with exit code `1`,
- sample run exports `config.json`, `summary.md`, and nested TTFT JSON,
- backup directory name uses deterministic `-Timestamp`,
- `large.log` and `model-cache.bin` are not copied,
- summary JSON exists and follows required schema,
- copied/skipped files are listed with relative forward-slash paths,
- relative directory structure is preserved.

---

## Hidden tests

Hidden tests should verify edge cases:

- paths with spaces,
- malformed endpoint URL is fatal,
- unreachable endpoint is non-fatal and recorded,
- Docker unavailable is non-fatal and recorded,
- `MaxFileSizeBytes` boundary behavior,
- nested excluded directories,
- output directory already exists,
- `IncludePatterns "*.log"` still does not copy `.log` because exclusion wins,
- dry-run (if implemented) does not copy artifacts but writes a summary.

---

## Quality review checklist

LLM-as-judge should inspect:

- deterministic behavior when `-Timestamp` is supplied,
- clear separation of fatal input errors vs non-fatal diagnostics,
- safe file filtering where exclusion rules win,
- summary JSON useful for automated review and debugging,
- cross-platform path handling where reasonable in PowerShell,
- no hard-coded endpoint, timestamp, or absolute path.
