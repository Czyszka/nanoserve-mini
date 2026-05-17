#requires -Version 5.1
<#
.SYNOPSIS
  Public test runner for preflight.ps1.

.DESCRIPTION
  Reads ../cases.json (or sibling cases.json), substitutes placeholders
  ({TMP}, {EMPTY_DIR}) and runs preflight.ps1 with each case's args/env.
  Validates expect_exit_code and several JSON-shape assertions.
  Exits 0 if all cases pass, 1 otherwise.

.PARAMETER PreflightPath
  Path to preflight.ps1. Default: ../../preflight.ps1 (relative to this runner).

.PARAMETER CasesPath
  Path to cases.json. Default: sibling ../cases.json.
#>
[CmdletBinding()]
param(
    [string]$PreflightPath = "",
    [string]$CasesPath = ""
)

$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
$PowerShellExe = Join-Path $PSHOME "powershell.exe"

if (-not $PreflightPath) {
    # Two valid layouts:
    #   source tree: .../public_tests/powershell/run.ps1 -> ..\..\preflight.ps1
    #   work-dir:    .../public_tests/run.ps1            -> ..\preflight.ps1   (init_env flattens)
    $candidates = @(
        (Join-Path $Here "..\preflight.ps1"),
        (Join-Path $Here "..\..\preflight.ps1")
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { $PreflightPath = $c; break }
    }
    if (-not $PreflightPath) {
        Write-Error "preflight.ps1 not found near runner; pass -PreflightPath explicitly"
        exit 2
    }
}
if (-not $CasesPath) {
    # source tree: public_tests/powershell/run.ps1 -> ..\cases.json
    # work-dir:    public_tests/run.ps1            -> cases.json (sibling)
    $candidates = @(
        (Join-Path $Here "cases.json"),
        (Join-Path $Here "..\cases.json")
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { $CasesPath = $c; break }
    }
    if (-not $CasesPath) {
        Write-Error "cases.json not found near runner; pass -CasesPath explicitly"
        exit 2
    }
}

$PreflightPath = (Resolve-Path -LiteralPath $PreflightPath).Path
$CasesPath = (Resolve-Path -LiteralPath $CasesPath).Path

# Create per-run scratch dir for {TMP} substitution.
$TmpRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("preflight-tests-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
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
        # array index like ports[0]?
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

function Join-ProcessArguments {
    param([string[]]$Values)
    $quoted = @()
    foreach ($v in $Values) {
        if ($v -match '[\s"]') {
            $quoted += '"' + ($v -replace '"', '\"') + '"'
        } else {
            $quoted += $v
        }
    }
    return ($quoted -join " ")
}

function Invoke-Preflight {
    param([string[]]$RawArgs)
    $invokeArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PreflightPath) + $RawArgs
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $PowerShellExe
    $psi.Arguments = Join-ProcessArguments -Values $invokeArgs
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    [void]$proc.Start()
    $stdoutText = $proc.StandardOutput.ReadToEnd()
    [void]$proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    return @{ stdout = $stdoutText.Trim(); exit_code = $proc.ExitCode }
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
        $procResult = Invoke-Preflight -RawArgs $rawArgs
        $stdoutText = $procResult.stdout
        $exitCode = $procResult.exit_code
    } finally {
        foreach ($k in $oldEnv.Keys) {
            [System.Environment]::SetEnvironmentVariable($k, $oldEnv[$k], "Process")
        }
    }

    $failures = @()

    # expect_exit_code
    if ($Case.PSObject.Properties.Name -contains "expect_exit_code") {
        if ($exitCode -ne $Case.expect_exit_code) {
            $failures += "exit_code expected=$($Case.expect_exit_code) got=$exitCode"
        }
    }

    # JSON-based assertions (only parse if we need them)
    $needsJson = ($Case.PSObject.Properties.Name -contains "expect_json_path") -or
                 ($Case.PSObject.Properties.Name -contains "expect_json_path_exists")

    if ($needsJson) {
        $parsed = $null
        try {
            $parsed = $stdoutText | ConvertFrom-Json
        } catch {
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

    # expect_jsonl_line_count
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

    # expect_jsonl_lines_field
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

    return @{ id = $caseId; failures = $failures }
}

# --- main --------------------------------------------------------------------
$casesRaw = Get-Content -LiteralPath $CasesPath -Raw | ConvertFrom-Json

$pass = 0
$fail = 0
$results = @()

foreach ($case in $casesRaw) {
    $r = Run-Case -Case $case
    if ($r.failures.Count -eq 0) {
        Write-Host "[PASS] $($r.id)"
        $pass++
    } else {
        Write-Host "[FAIL] $($r.id)"
        foreach ($f in $r.failures) { Write-Host "       - $f" }
        $fail++
    }
    $results += $r
}

$total = $pass + $fail
Write-Host ""
Write-Host "$pass/$total passed"

# Cleanup scratch dir (best-effort)
try { Remove-Item -LiteralPath $TmpRoot -Recurse -Force -ErrorAction SilentlyContinue } catch {}

if ($fail -gt 0) { exit 1 } else { exit 0 }
