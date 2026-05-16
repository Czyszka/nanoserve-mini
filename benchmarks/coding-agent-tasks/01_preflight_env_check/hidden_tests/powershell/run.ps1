#requires -Version 5.1
<#
.SYNOPSIS
  Hidden test runner for preflight.ps1. Same logic as public/run.ps1 but reads ../cases.json from this hidden_tests tree.

.PARAMETER PreflightPath
  Path to preflight.ps1 (the agent's solution). REQUIRED for hidden runs because this script lives in the task repo, not the work-dir.

.PARAMETER CasesPath
  Optional override; default = sibling ../cases.json.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PreflightPath,
    [string]$CasesPath = ""
)

$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot

if (-not $CasesPath) {
    $CasesPath = Join-Path $Here "..\cases.json"
}

$PreflightPath = (Resolve-Path -LiteralPath $PreflightPath).Path
$CasesPath = (Resolve-Path -LiteralPath $CasesPath).Path

$TmpRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("preflight-hidden-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $TmpRoot | Out-Null
$EmptyDir = Join-Path $TmpRoot "empty"
New-Item -ItemType Directory -Path $EmptyDir | Out-Null

function Substitute-Placeholders {
    param([string]$s)
    if ($null -eq $s) { return $s }
    $s = $s -replace [regex]::Escape("{TMP}"), $TmpRoot.Replace("\", "/")
    $s = $s -replace [regex]::Escape("{EMPTY_DIR}"), $EmptyDir.Replace("\", "/")
    return $s
}

function Get-DottedPath {
    param($Obj, [string]$Path)
    $parts = $Path -split "\."
    $cur = $Obj
    foreach ($p in $parts) {
        if ($null -eq $cur) { return @{ found = $false; value = $null } }
        $m = [regex]::Match($p, '^([^\[]+)(?:\[(\d+)\])?$')
        if (-not $m.Success) { return @{ found = $false; value = $null } }
        $name = $m.Groups[1].Value
        $idx = $m.Groups[2].Value
        if (-not ($cur.PSObject.Properties.Name -contains $name)) {
            return @{ found = $false; value = $null }
        }
        $cur = $cur.$name
        if ($idx -ne "") {
            $i = [int]$idx
            if ($null -eq $cur -or $i -ge $cur.Count) {
                return @{ found = $false; value = $null }
            }
            $cur = $cur[$i]
        }
    }
    return @{ found = $true; value = $cur }
}

function Run-Case {
    param($Case)

    $caseId = $Case.id
    $rawArgs = @()
    foreach ($a in $Case.args) {
        $rawArgs += (Substitute-Placeholders -s ([string]$a))
    }

    $oldEnv = @{}
    if ($Case.PSObject.Properties.Name -contains "env" -and $null -ne $Case.env) {
        foreach ($k in $Case.env.PSObject.Properties.Name) {
            $oldEnv[$k] = [System.Environment]::GetEnvironmentVariable($k, "Process")
            $val = Substitute-Placeholders -s ([string]$Case.env.$k)
            [System.Environment]::SetEnvironmentVariable($k, $val, "Process")
        }
    }

    try {
        $invokeArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PreflightPath) + $rawArgs
        $stdout = & powershell.exe @invokeArgs 2>$null
        $exitCode = $LASTEXITCODE
    } finally {
        foreach ($k in $oldEnv.Keys) {
            [System.Environment]::SetEnvironmentVariable($k, $oldEnv[$k], "Process")
        }
    }

    $stdoutText = ($stdout | Out-String).Trim()
    $failures = @()

    if ($Case.PSObject.Properties.Name -contains "expect_exit_code") {
        if ($exitCode -ne $Case.expect_exit_code) {
            $failures += "exit_code expected=$($Case.expect_exit_code) got=$exitCode"
        }
    }

    $needsJson = ($Case.PSObject.Properties.Name -contains "expect_json_path") -or
                 ($Case.PSObject.Properties.Name -contains "expect_json_path_exists")

    if ($needsJson) {
        $parsed = $null
        try { $parsed = $stdoutText | ConvertFrom-Json } catch {
            $failures += "stdout not valid JSON: $($_.Exception.Message)"
        }
        if ($null -ne $parsed) {
            if ($Case.PSObject.Properties.Name -contains "expect_json_path") {
                foreach ($p in $Case.expect_json_path.PSObject.Properties) {
                    $r = Get-DottedPath -Obj $parsed -Path $p.Name
                    if (-not $r.found) {
                        $failures += "json path '$($p.Name)' missing"
                    } elseif ($r.value -ne $p.Value) {
                        $failures += "json path '$($p.Name)' expected='$($p.Value)' got='$($r.value)'"
                    }
                }
            }
            if ($Case.PSObject.Properties.Name -contains "expect_json_path_exists") {
                foreach ($pname in $Case.expect_json_path_exists) {
                    $r = Get-DottedPath -Obj $parsed -Path $pname
                    if (-not $r.found) {
                        $failures += "json path '$pname' missing"
                    }
                }
            }
        }
    }

    if ($Case.PSObject.Properties.Name -contains "expect_jsonl_line_count") {
        $spec = $Case.expect_jsonl_line_count
        $p = Substitute-Placeholders -s ([string]$spec.path)
        if (-not (Test-Path -LiteralPath $p)) {
            $failures += "jsonl file '$p' not found"
        } else {
            $lines = Get-Content -LiteralPath $p | Where-Object { $_.Trim() -ne "" }
            if ($lines.Count -ne $spec.count) {
                $failures += "jsonl line count expected=$($spec.count) got=$($lines.Count) at '$p'"
            }
        }
    }

    if ($Case.PSObject.Properties.Name -contains "expect_jsonl_lines_field") {
        $spec = $Case.expect_jsonl_lines_field
        $p = Substitute-Placeholders -s ([string]$spec.path)
        if (-not (Test-Path -LiteralPath $p)) {
            $failures += "jsonl file '$p' not found"
        } else {
            $lines = Get-Content -LiteralPath $p | Where-Object { $_.Trim() -ne "" }
            $got = @()
            foreach ($ln in $lines) {
                try {
                    $obj = $ln | ConvertFrom-Json
                    $got += $obj.($spec.field)
                } catch {
                    $failures += "jsonl line not valid JSON: $ln"
                }
            }
            $expected = @($spec.expected_values)
            $diff = Compare-Object -ReferenceObject $expected -DifferenceObject $got -PassThru
            if ($null -ne $diff) {
                $failures += "jsonl field '$($spec.field)' expected=[$($expected -join ',')] got=[$($got -join ',')]"
            }
        }
    }

    $stage = 0
    if ($Case.PSObject.Properties.Name -contains "stage") { $stage = [int]$Case.stage }
    return @{ id = $caseId; stage = $stage; failures = $failures }
}

# --- main --------------------------------------------------------------------
$casesRaw = Get-Content -LiteralPath $CasesPath -Raw | ConvertFrom-Json

$results = @()
foreach ($case in $casesRaw) {
    $r = Run-Case -Case $case
    if ($r.failures.Count -eq 0) {
        Write-Host "[PASS] stage$($r.stage) $($r.id)"
    } else {
        Write-Host "[FAIL] stage$($r.stage) $($r.id)"
        foreach ($f in $r.failures) { Write-Host "       - $f" }
    }
    $results += $r
}

# Emit machine-readable summary on a single line at the end (consumed by run_eval.py).
$summary = @{
    schema = "preflight-hidden-tests-summary.v1"
    cases = @()
}
foreach ($r in $results) {
    $summary.cases += @{
        id = $r.id
        stage = $r.stage
        passed = ($r.failures.Count -eq 0)
        failures = $r.failures
    }
}
Write-Host ""
Write-Host ("SUMMARY_JSON " + ($summary | ConvertTo-Json -Depth 6 -Compress))

try { Remove-Item -LiteralPath $TmpRoot -Recurse -Force -ErrorAction SilentlyContinue } catch {}

$failed = ($results | Where-Object { $_.failures.Count -gt 0 }).Count
if ($failed -gt 0) { exit 1 } else { exit 0 }
