#requires -Version 5.1
<#
.SYNOPSIS
  Initializes the test environment for task 01_preflight_env_check (PowerShell variant).

.DESCRIPTION
  1. Checks for required tools (OS, claude, git, uv). PowerShell itself is skipped - if the script started, it is available.
  2. Creates work-dir <BaseDir>/<YYYY-MM-DD>_<Model>_run<RunNumber>/.
  3. Copies PROMPT.md, preflight.ps1, public_tests/{cases.json,run.ps1}.
  4. Initializes git + initial commit.
  5. Prints the ready-to-run harness command.

.PARAMETER Model
  Model identifier (e.g. minimax-m2.7). Slashes are replaced with dashes.

.PARAMETER RunNumber
  Run number (e.g. "01", "02").

.PARAMETER BaseDir
  Base directory for work-dirs. Default: .\runs
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Model,

    [Parameter(Mandatory = $true)]
    [string]$RunNumber,

    [Parameter(Mandatory = $false)]
    [string]$BaseDir = ".\runs"
)

$ErrorActionPreference = "Stop"
$TaskId = "01_preflight_env_check"
$ScriptRoot = $PSScriptRoot

function Test-Tool {
    param([string]$Name, [string]$VersionArg = "--version")
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $cmd) {
        Write-Host "[missing] $Name"
        return $false
    }
    try {
        $ver = & $Name $VersionArg 2>&1 | Select-Object -First 1
    } catch {
        $ver = "(no version)"
    }
    Write-Host "[ok]      $Name $ver"
    return $true
}

# --- 1. Environment check ----------------------------------------------------
Write-Host "== environment check =="
Write-Host "[ok]      OS Windows ($([System.Environment]::OSVersion.VersionString))"

$missing = 0
foreach ($t in @(
    @{ Name = "claude"; Arg = "--version" },
    @{ Name = "git";    Arg = "--version" },
    @{ Name = "uv";     Arg = "--version" }
)) {
    if (-not (Test-Tool -Name $t.Name -VersionArg $t.Arg)) { $missing++ }
}

if ($missing -gt 0) {
    Write-Host ""
    Write-Host "[error] missing $missing tool(s) - aborting."
    exit 1
}

try {
    $uvPythonOutput = & uv run python --version 2>&1
    $uvPythonExitCode = $LASTEXITCODE
    $uvPython = $uvPythonOutput | Select-Object -First 1
    if ($uvPythonExitCode -ne 0) {
        Write-Host "[error] uv run python --version failed: $uvPython"
        exit 1
    }
    Write-Host "[ok]      uv python $uvPython"
} catch {
    Write-Host "[error] uv run python --version failed: $($_.Exception.Message)"
    exit 1
}

# --- 2. Construct and validate work-dir --------------------------------------
$ModelSan = $Model -replace "[\\/]", "-"
$DateUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd")
$WorkDirName = "${DateUtc}_${ModelSan}_run${RunNumber}"

if (-not (Test-Path -LiteralPath $BaseDir)) {
    New-Item -ItemType Directory -Path $BaseDir | Out-Null
}
$BaseDirAbs = (Resolve-Path -LiteralPath $BaseDir).Path
$WorkDir = Join-Path $BaseDirAbs $WorkDirName

Write-Host ""
Write-Host "== work-dir =="
Write-Host "  $WorkDir"

if (Test-Path -LiteralPath $WorkDir) {
    $children = Get-ChildItem -LiteralPath $WorkDir -Force
    if ($children.Count -gt 0) {
        Write-Host ""
        Write-Host "[error] work-dir $WorkDir exists and is not empty; remove it or pass a different -RunNumber"
        exit 1
    }
} else {
    New-Item -ItemType Directory -Path $WorkDir | Out-Null
}

# --- 3. Copy scaffold --------------------------------------------------------
Write-Host ""
Write-Host "== copying scaffold =="

$Src = @{
    Prompt    = Join-Path $ScriptRoot "PROMPT.md"
    Preflight = Join-Path $ScriptRoot "scaffold\powershell\preflight.ps1"
    Cases     = Join-Path $ScriptRoot "public_tests\cases.json"
    Runner    = Join-Path $ScriptRoot "public_tests\powershell\run.ps1"
}

foreach ($k in $Src.Keys) {
    if (-not (Test-Path -LiteralPath $Src[$k])) {
        Write-Host "[error] missing source file: $($Src[$k])"
        exit 1
    }
}

$PublicTestsDir = Join-Path $WorkDir "public_tests"
New-Item -ItemType Directory -Path $PublicTestsDir | Out-Null

Copy-Item -LiteralPath $Src.Prompt    -Destination (Join-Path $WorkDir "PROMPT.md")
Copy-Item -LiteralPath $Src.Preflight -Destination (Join-Path $WorkDir "preflight.ps1")
Copy-Item -LiteralPath $Src.Cases     -Destination (Join-Path $PublicTestsDir "cases.json")
Copy-Item -LiteralPath $Src.Runner    -Destination (Join-Path $PublicTestsDir "run.ps1")

Write-Host "  PROMPT.md"
Write-Host "  preflight.ps1"
Write-Host "  public_tests\cases.json"
Write-Host "  public_tests\run.ps1"

# --- 4. git init + initial commit --------------------------------------------
Write-Host ""
Write-Host "== git init =="
Push-Location $WorkDir
try {
    git init --quiet
    git add -A
    git -c user.name="nanoserve-init" -c user.email="init@nanoserve.local" commit --quiet -m "baseline: $TaskId scaffold for $Model run$RunNumber"
    $Commit = (git rev-parse HEAD).Trim()
    Write-Host "  baseline_commit: $Commit"
} finally {
    Pop-Location
}

# --- 5. Next step ------------------------------------------------------------
Write-Host ""
Write-Host "== next step =="
$RunnerPath = Join-Path $ScriptRoot "run_eval.py"
$Cmd = @"
uv run python "$RunnerPath" ``
  --work-dir "$WorkDir" ``
  --model $Model
"@
Write-Host $Cmd
exit 0
