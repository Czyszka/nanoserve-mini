#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Validate a local LLM serving environment and export small benchmark
    artifacts into a timestamped backup directory.

.DESCRIPTION
    Partial implementation. See TASK.md for the full specification. The
    agent's job is to fix outstanding issues so public and hidden tests pass.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string] $RunDirectory,

    [Parameter(Mandatory = $false)]
    [string] $OutputDirectory,

    [string[]] $Endpoint = @(),

    [long] $MaxFileSizeBytes = 1048576,

    [string[]] $IncludePatterns = @('*.json', '*.jsonl', '*.md', '*.txt', '*.csv', '*.prom'),

    [string] $Timestamp,

    [switch] $DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Exit codes
$EXIT_OK            = 0
$EXIT_INVALID_INPUT = 1
$EXIT_EXPORT_FAIL   = 2
$EXIT_RUNTIME       = 3

$ExcludedExtensions  = @('.bin', '.pt', '.safetensors', '.log')
$ExcludedDirectories = @('cache', '.cache', 'hf_cache', 'models')

function Write-Err {
    param([string] $Message)
    [Console]::Error.WriteLine("ERROR: $Message")
}

function Test-TimestampFormat {
    param([string] $Value)
    return ($Value -match '^\d{8}-\d{6}Z$')
}

function ConvertTo-ForwardSlash {
    param([string] $Path)
    return ($Path -replace '\\', '/')
}

function Get-DockerStatus {
    $cmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $cmd) {
        return [pscustomobject]@{
            available = $false
            version   = $null
            error     = 'docker not found on PATH'
        }
    }
    try {
        $version = & docker --version 2>&1 | Out-String
        return [pscustomobject]@{
            available = $true
            version   = $version.Trim()
            error     = $null
        }
    } catch {
        return [pscustomobject]@{
            available = $false
            version   = $null
            error     = $_.Exception.Message
        }
    }
}

function Test-EndpointWellFormed {
    param([string] $Url)
    $out = $null
    return [Uri]::TryCreate($Url, [UriKind]::Absolute, [ref] $out) `
        -and ($out.Scheme -in @('http', 'https'))
}

function Get-EndpointStatus {
    param([string] $Url)
    $metricsUrl = ($Url.TrimEnd('/')) + '/metrics'
    $entry = [ordered]@{
        url         = $Url
        metrics_url = $metricsUrl
        ok          = $false
        status_code = $null
        error       = $null
    }
    try {
        $resp = Invoke-WebRequest -Uri $metricsUrl -TimeoutSec 5 -UseBasicParsing
        $entry.status_code = [int] $resp.StatusCode
        $entry.ok = ($entry.status_code -ge 200 -and $entry.status_code -lt 300)
        if (-not $entry.ok) {
            $entry.error = "non-2xx status $($entry.status_code)"
        }
    } catch [System.Net.WebException] {
        $entry.error = $_.Exception.Message
        try {
            if ($_.Exception.Response) {
                $entry.status_code = [int] $_.Exception.Response.StatusCode
            }
        } catch {
            # ignore
        }
    } catch {
        $entry.error = $_.Exception.Message
    }
    return [pscustomobject] $entry
}

function Test-PathMatchesAnyPattern {
    param(
        [string] $Name,
        [string[]] $Patterns
    )
    foreach ($p in $Patterns) {
        if ($Name -like $p) { return $true }
    }
    return $false
}

function Test-PathInExcludedDirectory {
    param(
        [string] $RelativePath
    )
    $parts = $RelativePath -split '[\\/]+'
    # Drop the last element (file name); only check directory segments.
    if ($parts.Length -le 1) { return $false }
    $dirs = $parts[0..($parts.Length - 2)]
    foreach ($d in $dirs) {
        if ($ExcludedDirectories -contains $d) { return $true }
    }
    return $false
}

try {
    # --- Stage 1: input validation ---
    if (-not $RunDirectory) {
        Write-Err "Missing required parameter -RunDirectory"
        exit $EXIT_INVALID_INPUT
    }
    if (-not $OutputDirectory) {
        Write-Err "Missing required parameter -OutputDirectory"
        exit $EXIT_INVALID_INPUT
    }
    if (-not (Test-Path -LiteralPath $RunDirectory -PathType Container)) {
        Write-Err "RunDirectory does not exist: $RunDirectory"
        exit $EXIT_INVALID_INPUT
    }
    if ($MaxFileSizeBytes -le 0) {
        Write-Err "MaxFileSizeBytes must be > 0 (got $MaxFileSizeBytes)"
        exit $EXIT_INVALID_INPUT
    }

    # BUG A: even if a timestamp was supplied in the correct format,
    # we parse-and-reformat it via [DateTime]::Parse, which loses the
    # exact 'yyyyMMdd-HHmmssZ' shape and instead produces an ISO-ish form.
    # When omitted, we also fail to produce the documented format.
    if ($Timestamp) {
        if (-not (Test-TimestampFormat $Timestamp)) {
            Write-Err "Invalid -Timestamp format (expected yyyyMMdd-HHmmssZ): $Timestamp"
            exit $EXIT_INVALID_INPUT
        }
        # Re-format the (already valid) timestamp -- this is the deliberate bug.
        $parsed = [DateTime]::Parse(
            $Timestamp.Substring(0, 8) + ' ' + $Timestamp.Substring(9, 6),
            [System.Globalization.CultureInfo]::InvariantCulture
        )
        $resolvedTimestamp = $parsed.ToString('yyyy-MM-ddTHHmmssZ')
    } else {
        # Non-deterministic and non-canonical default format.
        $resolvedTimestamp = (Get-Date).ToString('o')
    }

    foreach ($u in $Endpoint) {
        if (-not (Test-EndpointWellFormed $u)) {
            Write-Err "Malformed endpoint URL: $u"
            exit $EXIT_INVALID_INPUT
        }
    }

    $runDirItem = Get-Item -LiteralPath $RunDirectory
    $leaf       = $runDirItem.Name
    $backupDir  = Join-Path $OutputDirectory ("${leaf}__${resolvedTimestamp}")

    # --- Stage 2: docker + endpoints ---
    $docker    = Get-DockerStatus
    $endpoints = @()
    foreach ($u in $Endpoint) {
        $endpoints += Get-EndpointStatus $u
    }

    # --- Stage 3: artifact export ---
    try {
        if (-not (Test-Path -LiteralPath $backupDir)) {
            New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        }
    } catch {
        Write-Err "Failed to create backup directory: $backupDir ($($_.Exception.Message))"
        exit $EXIT_EXPORT_FAIL
    }

    $copied  = New-Object System.Collections.Generic.List[string]
    $skipped = New-Object System.Collections.Generic.List[object]
    $reasonCounts = @{}

    $runFull = $runDirItem.FullName
    $files   = Get-ChildItem -LiteralPath $runFull -Recurse -File -Force

    foreach ($f in $files) {
        $rel = $f.FullName.Substring($runFull.Length).TrimStart('\', '/')
        $relFwd = ConvertTo-ForwardSlash $rel
        $ext = $f.Extension.ToLowerInvariant()

        # Directory exclusion (recursive)
        if (Test-PathInExcludedDirectory $rel) {
            $skipped.Add([pscustomobject]@{ path = $relFwd; reason = 'directory_excluded' })
            $reasonCounts['directory_excluded'] = ($reasonCounts['directory_excluded'] | ForEach-Object { if ($null -eq $_) { 0 } else { $_ } }) + 1
            continue
        }

        # BUG C: include patterns are checked BEFORE extension exclusion,
        # so a user passing -IncludePatterns "*.log" causes .log files to
        # be copied even though they should remain excluded.
        $matchedInclude = Test-PathMatchesAnyPattern -Name $f.Name -Patterns $IncludePatterns
        if ($matchedInclude) {
            if ($f.Length -gt $MaxFileSizeBytes) {
                $skipped.Add([pscustomobject]@{ path = $relFwd; reason = 'too_large' })
                $reasonCounts['too_large'] = ($reasonCounts['too_large'] | ForEach-Object { if ($null -eq $_) { 0 } else { $_ } }) + 1
                continue
            }
            $dest = Join-Path $backupDir $rel
            $destDir = Split-Path -Parent $dest
            if (-not (Test-Path -LiteralPath $destDir)) {
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            }
            if (-not $DryRun) {
                Copy-Item -LiteralPath $f.FullName -Destination $dest -Force
            }
            $copied.Add($relFwd)
            continue
        }

        # Extension exclusion
        if ($ExcludedExtensions -contains $ext) {
            $skipped.Add([pscustomobject]@{ path = $relFwd; reason = 'extension_excluded' })
            $reasonCounts['extension_excluded'] = ($reasonCounts['extension_excluded'] | ForEach-Object { if ($null -eq $_) { 0 } else { $_ } }) + 1
            continue
        }

        # Pattern not included
        $skipped.Add([pscustomobject]@{ path = $relFwd; reason = 'pattern_not_included' })
        $reasonCounts['pattern_not_included'] = ($reasonCounts['pattern_not_included'] | ForEach-Object { if ($null -eq $_) { 0 } else { $_ } }) + 1
    }

    # --- Stage 4: summary JSON ---
    # BUG B: only emit keys for reasons that actually fired (zero keys dropped).
    $reasons = [ordered]@{}
    foreach ($k in $reasonCounts.Keys) {
        $reasons[$k] = $reasonCounts[$k]
    }

    $summary = [ordered]@{
        schema           = 'coding-agent-task.powershell-export.v1'
        run_directory    = ConvertTo-ForwardSlash $runFull
        backup_directory = ConvertTo-ForwardSlash ((Resolve-Path -LiteralPath $backupDir).Path)
        dry_run          = [bool] $DryRun
        docker           = $docker
        endpoints        = $endpoints
        files_copied     = $copied.Count
        files_skipped    = $skipped.Count
        copied_files     = @($copied)
        skipped_files    = @($skipped)
        skipped_reasons  = $reasons
    }

    $summaryPath = Join-Path $backupDir 'export-summary.json'
    $json = $summary | ConvertTo-Json -Depth 8
    Set-Content -LiteralPath $summaryPath -Value $json -Encoding utf8

    exit $EXIT_OK
} catch {
    Write-Err "Unexpected error: $($_.Exception.Message)"
    exit $EXIT_RUNTIME
}
