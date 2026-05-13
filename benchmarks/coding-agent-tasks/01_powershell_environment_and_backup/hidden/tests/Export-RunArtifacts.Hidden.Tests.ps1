#!/usr/bin/env pwsh
# Hand-rolled hidden tests for Export-RunArtifacts.ps1.

[CmdletBinding()]
param(
    [string] $WorkDir
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $WorkDir) {
    $WorkDir = (Resolve-Path "$PSScriptRoot/../..").Path
}

$script:Failed = 0
$script:Passed = 0

function Assert-True {
    param([string] $Name, [bool] $Condition, [string] $Detail = '')
    if ($Condition) {
        $script:Passed++
        Write-Host "PASS  $Name"
    } else {
        $script:Failed++
        $line = "FAIL  $Name"
        if ($Detail) { $line += " -- $Detail" }
        Write-Host $line
    }
}

function Invoke-ExportScript {
    param([string[]] $ScriptArgs)
    $scriptPath = Join-Path $WorkDir 'starter/Export-RunArtifacts.ps1'
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        throw "Export-RunArtifacts.ps1 not found at $scriptPath"
    }
    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    $allArgs = @('-NoProfile', '-File', $scriptPath) + $ScriptArgs
    $proc = Start-Process -FilePath 'pwsh' -ArgumentList $allArgs `
        -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError  $stderrPath
    return [pscustomobject]@{
        ExitCode = $proc.ExitCode
        StdOut   = (Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue)
        StdErr   = (Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue)
    }
}

function Read-Summary {
    param([string] $BackupDir)
    $path = Join-Path $BackupDir 'export-summary.json'
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    return (Get-Content -LiteralPath $path -Raw | ConvertFrom-Json)
}

$fixtureSrc = Join-Path $WorkDir 'starter/fixtures/sample-run'

# ---------------------------------------------------------------------------
# Test: paths with spaces in -RunDirectory and -OutputDirectory
# ---------------------------------------------------------------------------
$spaceRoot = Join-Path $WorkDir 'hidden-tmp/space test'
if (Test-Path -LiteralPath $spaceRoot) {
    Remove-Item -LiteralPath $spaceRoot -Recurse -Force
}
$spaceRun = Join-Path $spaceRoot 'sample run'
New-Item -ItemType Directory -Path $spaceRun -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $fixtureSrc '*') -Destination $spaceRun -Recurse -Force
$spaceOut = Join-Path $spaceRoot 'out dir'

$res = Invoke-ExportScript -ScriptArgs @(
    '-RunDirectory',    $spaceRun,
    '-OutputDirectory', $spaceOut,
    '-Timestamp',       '20260508-101530Z'
)
Assert-True 'paths_with_spaces_exit_0' ($res.ExitCode -eq 0) "exit $($res.ExitCode)"
$spaceBackup = Join-Path $spaceOut 'sample run__20260508-101530Z'
Assert-True 'paths_with_spaces_backup_exists' (Test-Path -LiteralPath $spaceBackup)

# ---------------------------------------------------------------------------
# Test: malformed endpoint URL -> exit 1
# ---------------------------------------------------------------------------
$outRoot = Join-Path $WorkDir 'hidden-tmp/out'
if (Test-Path -LiteralPath $outRoot) {
    Remove-Item -LiteralPath $outRoot -Recurse -Force
}
$res = Invoke-ExportScript -ScriptArgs @(
    '-RunDirectory',    $fixtureSrc,
    '-OutputDirectory', $outRoot,
    '-Timestamp',       '20260508-101530Z',
    '-Endpoint',        'not a url at all'
)
Assert-True 'malformed_endpoint_exits_1' ($res.ExitCode -eq 1) "exit $($res.ExitCode)"

# ---------------------------------------------------------------------------
# Test: unreachable endpoint is non-fatal; export still exit 0, entry ok=false
# ---------------------------------------------------------------------------
if (Test-Path -LiteralPath $outRoot) {
    Remove-Item -LiteralPath $outRoot -Recurse -Force
}
$res = Invoke-ExportScript -ScriptArgs @(
    '-RunDirectory',    $fixtureSrc,
    '-OutputDirectory', $outRoot,
    '-Timestamp',       '20260508-101530Z',
    '-Endpoint',        'http://127.0.0.1:1'
)
Assert-True 'unreachable_endpoint_exit_0' ($res.ExitCode -eq 0) "exit $($res.ExitCode)"
$backup = Join-Path $outRoot 'sample-run__20260508-101530Z'
$summary = Read-Summary $backup
$endpointOk = $null
if ($summary -and $summary.endpoints -and @($summary.endpoints).Count -ge 1) {
    $endpointOk = @($summary.endpoints)[0].ok
}
Assert-True 'unreachable_endpoint_ok_false' ($endpointOk -eq $false) "ok=$endpointOk"

# ---------------------------------------------------------------------------
# Test: -IncludePatterns "*.log" still excludes .log files (exclusion wins)
# ---------------------------------------------------------------------------
$outRoot2 = Join-Path $WorkDir 'hidden-tmp/out-include'
if (Test-Path -LiteralPath $outRoot2) {
    Remove-Item -LiteralPath $outRoot2 -Recurse -Force
}
$res = Invoke-ExportScript -ScriptArgs @(
    '-RunDirectory',    $fixtureSrc,
    '-OutputDirectory', $outRoot2,
    '-Timestamp',       '20260508-101530Z',
    '-IncludePatterns', '*.log'
)
Assert-True 'include_log_still_exit_0' ($res.ExitCode -eq 0) "exit $($res.ExitCode)"
$backup2 = Join-Path $outRoot2 'sample-run__20260508-101530Z'
$summary2 = Read-Summary $backup2
$logCopied = $false
if ($summary2 -and $summary2.copied_files) {
    $logCopied = @($summary2.copied_files | Where-Object { $_ -like '*.log' }).Count -gt 0
}
Assert-True 'include_log_pattern_loses_to_exclusion' (-not $logCopied) `
    'a .log file was copied despite extension exclusion'

# ---------------------------------------------------------------------------
# Test: default timestamp (omitted) matches yyyyMMdd-HHmmssZ
# ---------------------------------------------------------------------------
$outRoot3 = Join-Path $WorkDir 'hidden-tmp/out-default-ts'
if (Test-Path -LiteralPath $outRoot3) {
    Remove-Item -LiteralPath $outRoot3 -Recurse -Force
}
$res = Invoke-ExportScript -ScriptArgs @(
    '-RunDirectory',    $fixtureSrc,
    '-OutputDirectory', $outRoot3
)
Assert-True 'default_timestamp_exit_0' ($res.ExitCode -eq 0) "exit $($res.ExitCode)"
$produced = @(Get-ChildItem -LiteralPath $outRoot3 -Directory -ErrorAction SilentlyContinue)
$tsMatches = $false
if ($produced.Count -ge 1) {
    $tsMatches = $produced[0].Name -match '^sample-run__\d{8}-\d{6}Z$'
}
Assert-True 'default_timestamp_format' $tsMatches `
    ("dir name not yyyyMMdd-HHmmssZ: " + ($produced | ForEach-Object Name -ErrorAction SilentlyContinue))

# Cleanup hidden-tmp.
$tmp = Join-Path $WorkDir 'hidden-tmp'
if (Test-Path -LiteralPath $tmp) {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Hidden tests: $script:Passed passed, $script:Failed failed"
if ($script:Failed -gt 0) { exit 1 } else { exit 0 }
