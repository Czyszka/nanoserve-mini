#!/usr/bin/env pwsh
# Hand-rolled public tests for Export-RunArtifacts.ps1.
#
# Exits non-zero if any test fails. Prints a short PASS/FAIL line per test.

[CmdletBinding()]
param(
    [string] $WorkDir
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $WorkDir) {
    $WorkDir = (Resolve-Path "$PSScriptRoot/../..").Path
}

$script:Failed  = 0
$script:Passed  = 0
$script:Results = New-Object System.Collections.Generic.List[string]

function Assert-True {
    param(
        [string] $Name,
        [bool]   $Condition,
        [string] $Detail = ''
    )
    if ($Condition) {
        $script:Passed++
        $script:Results.Add("PASS  $Name")
        Write-Host "PASS  $Name"
    } else {
        $script:Failed++
        $line = "FAIL  $Name"
        if ($Detail) { $line += " -- $Detail" }
        $script:Results.Add($line)
        Write-Host $line
    }
}

function Invoke-ExportScript {
    param([string[]] $ScriptArgs)
    $scriptPath = Join-Path $WorkDir 'starter/Export-RunArtifacts.ps1'
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        throw "Export-RunArtifacts.ps1 not found at $scriptPath"
    }
    $allArgs = @('-NoProfile', '-File', $scriptPath) + $ScriptArgs
    $proc = Start-Process -FilePath 'pwsh' -ArgumentList $allArgs `
        -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput ([System.IO.Path]::GetTempFileName()) `
        -RedirectStandardError  ([System.IO.Path]::GetTempFileName())
    return $proc.ExitCode
}

# ---------------------------------------------------------------------------
# Test 1: missing -RunDirectory -> exit 1
# ---------------------------------------------------------------------------
$outRoot = Join-Path $WorkDir 'out-public'
if (Test-Path -LiteralPath $outRoot) {
    Remove-Item -LiteralPath $outRoot -Recurse -Force
}
$code = Invoke-ExportScript -ScriptArgs @('-OutputDirectory', $outRoot)
Assert-True 'missing_run_directory_exits_1' ($code -eq 1) "got exit code $code"

# ---------------------------------------------------------------------------
# Test 2: invalid -Timestamp -> exit 1
# ---------------------------------------------------------------------------
$runDir = Join-Path $WorkDir 'starter/fixtures/sample-run'
$code = Invoke-ExportScript -ScriptArgs @(
    '-RunDirectory',    $runDir,
    '-OutputDirectory', $outRoot,
    '-Timestamp',       'not-a-timestamp'
)
Assert-True 'invalid_timestamp_exits_1' ($code -eq 1) "got exit code $code"

# ---------------------------------------------------------------------------
# Test 3: happy-path export
# ---------------------------------------------------------------------------
if (Test-Path -LiteralPath $outRoot) {
    Remove-Item -LiteralPath $outRoot -Recurse -Force
}
$code = Invoke-ExportScript -ScriptArgs @(
    '-RunDirectory',    $runDir,
    '-OutputDirectory', $outRoot,
    '-Timestamp',       '20260508-101530Z'
)
Assert-True 'happy_path_exits_0' ($code -eq 0) "got exit code $code"

# Deterministic backup directory name (EXPECTED RED with starter bug A).
$expectedBackup = Join-Path $outRoot 'sample-run__20260508-101530Z'
Assert-True 'deterministic_backup_dir' (Test-Path -LiteralPath $expectedBackup) `
    "expected $expectedBackup"

# Locate whatever backup directory was actually produced (so subsequent
# assertions can still run when bug A renames the directory).
$produced = @(Get-ChildItem -LiteralPath $outRoot -Directory -ErrorAction SilentlyContinue)
$backupDir = if (Test-Path -LiteralPath $expectedBackup) {
    $expectedBackup
} elseif ($produced.Count -ge 1) {
    $produced[0].FullName
} else {
    $null
}

Assert-True 'backup_directory_created' ($null -ne $backupDir) 'no backup directory found'

if ($backupDir) {
    $summaryPath = Join-Path $backupDir 'export-summary.json'
    Assert-True 'summary_json_exists' (Test-Path -LiteralPath $summaryPath) `
        "expected $summaryPath"

    if (Test-Path -LiteralPath $summaryPath) {
        $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json

        Assert-True 'summary_schema_v1' `
            ($summary.schema -eq 'coding-agent-task.powershell-export.v1') `
            "got '$($summary.schema)'"

        # large.log and model-cache.bin must not be copied.
        $copied = @($summary.copied_files)
        $hasLog = ($copied | Where-Object { $_ -like '*large.log' }).Count -gt 0
        $hasBin = ($copied | Where-Object { $_ -like '*model-cache.bin' }).Count -gt 0
        Assert-True 'large_log_not_copied'      (-not $hasLog) 'large.log was copied'
        Assert-True 'model_cache_not_copied'    (-not $hasBin) 'model-cache.bin was copied'

        # Required artifacts present.
        $hasConfig  = ($copied | Where-Object { $_ -like '*config.json' }).Count -gt 0
        $hasSummary = ($copied | Where-Object { $_ -like '*summary.md' }).Count -gt 0
        $hasTtft    = ($copied | Where-Object {
                          $_ -like '*singlestream_lite_latency/minimax_ttft.json'
                      }).Count -gt 0
        Assert-True 'config_json_copied'  $hasConfig  'config.json missing from copied_files'
        Assert-True 'summary_md_copied'   $hasSummary 'summary.md missing from copied_files'
        Assert-True 'nested_ttft_copied'  $hasTtft    'nested ttft json missing from copied_files'

        # skipped_reasons must include all 4 keys, even when zero (EXPECTED RED
        # with starter bug B).
        $requiredReasons = @('too_large', 'extension_excluded',
                             'directory_excluded', 'pattern_not_included')
        $reasonKeys = @()
        if ($summary.skipped_reasons) {
            $reasonKeys = @($summary.skipped_reasons.PSObject.Properties.Name)
        }
        $missing = $requiredReasons | Where-Object { $reasonKeys -notcontains $_ }
        Assert-True 'skipped_reasons_full_schema' ($missing.Count -eq 0) `
            ("missing keys: " + ($missing -join ','))
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Public tests: $script:Passed passed, $script:Failed failed"
if ($script:Failed -gt 0) { exit 1 } else { exit 0 }
