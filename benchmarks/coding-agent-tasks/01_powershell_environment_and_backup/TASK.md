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
2. Validate that Docker is available.
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
  -Endpoint http://127.0.0.1:8001
```

Required parameters:

- `-RunDirectory`
- `-OutputDirectory`

Optional parameters:

- `-Endpoint` as zero or more endpoint URLs.
- `-MaxFileSizeBytes`, default `1048576`.
- `-IncludePatterns`, default should include small benchmark artifacts such as `*.json`, `*.jsonl`, `*.md`, `*.txt`, `*.csv`, `*.prom`.

The script should fail with a non-zero exit code if:

- `RunDirectory` does not exist,
- `OutputDirectory` cannot be created,
- `MaxFileSizeBytes` is less than or equal to zero,
- endpoint URL is malformed.

### Stage 2 — Docker and endpoint status

The script should check whether Docker is available by invoking `docker --version` or equivalent.

Endpoint check:

- For each endpoint, query `<endpoint>/metrics`.
- Record HTTP success/failure in summary JSON.
- Endpoint failure should not prevent artifact export unless a strict flag is added. For this task, endpoint failure should be recorded but not fatal.

### Stage 3 — artifact export

The script should copy only small, useful files from `RunDirectory` into a new timestamped backup directory under `OutputDirectory`.

It should include:

- `.json`
- `.jsonl`
- `.md`
- `.txt`
- `.csv`
- `.prom`

It should exclude:

- files larger than `MaxFileSizeBytes`,
- `.bin`, `.pt`, `.safetensors`, `.log` by default,
- directories named `cache`, `.cache`, `hf_cache`, `models`.

The relative directory structure should be preserved.

### Stage 4 — summary JSON

The script must write `export-summary.json` into the backup directory.

Required fields:

```json
{
  "schema": "coding-agent-task.powershell-export.v1",
  "run_directory": "...",
  "backup_directory": "...",
  "docker_available": true,
  "endpoints": [
    {
      "url": "http://127.0.0.1:8000",
      "metrics_url": "http://127.0.0.1:8000/metrics",
      "ok": true,
      "error": null
    }
  ],
  "files_copied": 0,
  "files_skipped": 0,
  "skipped_reasons": {
    "too_large": 0,
    "extension_excluded": 0,
    "directory_excluded": 0
  }
}
```

---

## Public tests

Public tests should verify:

- missing `RunDirectory` fails,
- sample run exports `config.json`, `summary.md`, and TTFT JSON,
- `large.log` and `model-cache.bin` are not copied,
- summary JSON exists and has valid schema,
- relative paths are preserved.

---

## Hidden tests

Hidden tests should verify edge cases:

- paths with spaces,
- malformed endpoint URL,
- `MaxFileSizeBytes` boundary behavior,
- nested excluded directories,
- endpoint failure is non-fatal and recorded,
- output directory already exists.

---

## Quality review checklist

LLM-as-judge should inspect:

- idiomatic PowerShell parameter handling,
- clear error messages,
- no hard-coded absolute paths,
- no copying of large/model/cache files,
- readable summary schema,
- safe behavior on invalid input.
