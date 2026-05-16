#requires -Version 5.1
<#
.SYNOPSIS
  Inicjalizuje srodowisko testowe dla zadania 01_preflight_env_check (wariant PowerShell).

.DESCRIPTION
  1. Sprawdza dostepnosc narzedzi (OS, claude, git, python, uv). Sam PowerShell pomijamy - skoro skrypt sie uruchomil, jest dostepny.
  2. Tworzy work-dir <BaseDir>/<YYYY-MM-DD>_<Model>_run<RunNumber>/.
  3. Kopiuje PROMPT.md, preflight.ps1, public_tests/{cases.json,run.ps1}.
  4. Inicjalizuje git + initial commit.
  5. Wypisuje gotowa komende uruchomienia harnessu.

.PARAMETER Model
  Identyfikator modelu (np. minimax-m2.7). Slashe sa zamieniane na myslniki.

.PARAMETER RunNumber
  Numer runu (np. "01", "02").

.PARAMETER BaseDir
  Katalog bazowy dla work-dirow. Default: .\runs
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
        Write-Host "[brak] $Name"
        return $false
    }
    try {
        $ver = & $Name $VersionArg 2>&1 | Select-Object -First 1
    } catch {
        $ver = "(brak wersji)"
    }
    Write-Host "[ok]   $Name $ver"
    return $true
}

# --- 1. Check srodowiska -----------------------------------------------------
Write-Host "== check srodowiska =="
Write-Host "[ok]   OS Windows ($([System.Environment]::OSVersion.VersionString))"

$missing = 0
foreach ($t in @(
    @{ Name = "claude"; Arg = "--version" },
    @{ Name = "git";    Arg = "--version" },
    @{ Name = "python"; Arg = "--version" },
    @{ Name = "uv";     Arg = "--version" }
)) {
    if (-not (Test-Tool -Name $t.Name -VersionArg $t.Arg)) { $missing++ }
}

if ($missing -gt 0) {
    Write-Host ""
    Write-Host "[error] brakuje $missing narzedzi - przerywam."
    exit 1
}

# --- 2. Konstrukcja i walidacja work-dir -------------------------------------
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
        Write-Host "[error] work-dir $WorkDir istnieje i nie jest pusty; usun go lub podaj inny -RunNumber"
        exit 1
    }
} else {
    New-Item -ItemType Directory -Path $WorkDir | Out-Null
}

# --- 3. Kopiowanie scaffoldu -------------------------------------------------
Write-Host ""
Write-Host "== kopiowanie scaffoldu =="

$Src = @{
    Prompt    = Join-Path $ScriptRoot "PROMPT.md"
    Preflight = Join-Path $ScriptRoot "scaffold\powershell\preflight.ps1"
    Cases     = Join-Path $ScriptRoot "public_tests\cases.json"
    Runner    = Join-Path $ScriptRoot "public_tests\powershell\run.ps1"
}

foreach ($k in $Src.Keys) {
    if (-not (Test-Path -LiteralPath $Src[$k])) {
        Write-Host "[error] brak pliku zrodlowego: $($Src[$k])"
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
$RunId = $WorkDirName
$Cmd = @"
uv run python -m scripts.run_coding_agent_task ``
  --task-id $TaskId ``
  --work-dir $WorkDir ``
  --agent claude_code ``
  --model $Model ``
  --run-id $RunId
"@
Write-Host $Cmd
exit 0
