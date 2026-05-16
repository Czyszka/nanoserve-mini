#requires -Version 5.1
<#
.SYNOPSIS
  Preflight environment check for a GPU server. Outputs JSON to stdout and sets exit code.

.DESCRIPTION
  Checks 5 things:
    - docker             (docker --version)
    - GPUs               (nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader)
    - disk free          (parameter --path <dir>, --min-free-mb <N>)
    - TCP port available (parameter --host <ip> [default 127.0.0.1], --port <p>, may repeat)
    - tool versions      (python --version, uv --version, docker compose version)

  Exit code:
    0 = all checks ok
    1 = at least one check failed
    2 = invocation error (bad args, etc.)

  --watch mode (Stage 2 - NOT YET IMPLEMENTED):
    --watch --interval-s <N> --duration-s <M> --output <path>
    Repeatedly runs the full check set, appending one JSON line per tick to --output.
#>
$ErrorActionPreference = "Continue"

# -----------------------------------------------------------------------------
# Manual arg parsing supporting GNU-style flags: --path, --min-free-mb,
# --host, --port, --watch, --interval-s, --duration-s, --output.
# Multiple --port flags accumulate. --host defaults to 127.0.0.1.
# -----------------------------------------------------------------------------
function Parse-Args {
    param([string[]]$Argv)
    $result = @{
        Path      = ""
        MinFreeMb = 0
        Host_     = "127.0.0.1"
        Ports     = @()
        Watch     = $false
        IntervalS = 0
        DurationS = 0
        Output    = ""
    }
    $i = 0
    while ($i -lt $Argv.Count) {
        $a = $Argv[$i]
        switch ($a) {
            "--path"        { $result.Path = $Argv[$i+1]; $i += 2 }
            "--min-free-mb" { $result.MinFreeMb = [int]$Argv[$i+1]; $i += 2 }
            "--host"        { $result.Host_ = $Argv[$i+1]; $i += 2 }
            "--port"        { $result.Ports += $Argv[$i+1]; $i += 2 }
            "--watch"       { $result.Watch = $true; $i += 1 }
            "--interval-s"  { $result.IntervalS = [int]$Argv[$i+1]; $i += 2 }
            "--duration-s"  { $result.DurationS = [int]$Argv[$i+1]; $i += 2 }
            "--output"      { $result.Output = $Argv[$i+1]; $i += 2 }
            default {
                Write-Error "unknown argument: $a"
                exit 2
            }
        }
    }
    return $result
}

# -----------------------------------------------------------------------------
# Check: docker
# -----------------------------------------------------------------------------
function Check-Docker {
    $result = [ordered]@{ available = $false; version = $null; error = $null }
    try {
        $out = & docker --version 2>&1
        # BUG 1: we set available=true here unconditionally inside try. When the
        # docker command does not exist, PowerShell raises an exception which we
        # catch below; but on some shells a missing native exec still completes
        # the pipeline without throwing, leaving us with $out as an ErrorRecord
        # while available stays true. Either way, the version field is filled
        # from $out which may be an error string.
        $result.available = $true
        $result.version = ($out | Select-Object -First 1).ToString().Trim()
    } catch {
        $result.available = $true
        $result.error = $_.Exception.Message
    }
    return $result
}

# -----------------------------------------------------------------------------
# Check: GPUs via nvidia-smi
# -----------------------------------------------------------------------------
function Check-Gpus {
    $gpus = @()
    try {
        $out = & nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out) {
            return @{ available = $false; gpus = @(); error = "nvidia-smi failed or absent" }
        }
        foreach ($line in $out) {
            $parts = $line -split ","
            if ($parts.Count -ge 3) {
                $gpus += [ordered]@{
                    name        = $parts[0].Trim()
                    memory_total = $parts[1].Trim()
                    memory_free  = $parts[2].Trim()
                }
            }
        }
        return @{ available = $true; gpus = $gpus; error = $null }
    } catch {
        return @{ available = $false; gpus = @(); error = $_.Exception.Message }
    }
}

# -----------------------------------------------------------------------------
# Check: disk free space
# -----------------------------------------------------------------------------
function Check-Disk {
    param([string]$DiskPath, [int]$MinFreeMb)
    $r = [ordered]@{ path = $DiskPath; free_mb = $null; min_free_mb = $MinFreeMb; ok = $false; error = $null }
    if (-not $DiskPath) {
        $r.error = "no --path provided"
        return $r
    }
    try {
        $resolved = Resolve-Path -LiteralPath $DiskPath -ErrorAction Stop
        $driveLetter = (Split-Path -Qualifier $resolved.Path).TrimEnd(":")
        $drive = Get-PSDrive -Name $driveLetter -ErrorAction Stop
        $freeMb = [math]::Floor($drive.Free / 1MB)
        $r.free_mb = $freeMb
        # BUG 2: string comparison instead of numeric. PowerShell -ge on strings
        # does lexicographic comparison, so e.g. "9" -ge "10" is $true, and
        # "15000" -ge "9000" is $false (because "1" < "9" lexicographically).
        $freeStr = "$freeMb"
        $minStr = "$MinFreeMb"
        $r.ok = ($freeStr -ge $minStr)
    } catch {
        $r.error = $_.Exception.Message
    }
    return $r
}

# -----------------------------------------------------------------------------
# Check: TCP ports
# -----------------------------------------------------------------------------
function Check-Port {
    param([int]$PortNum, [string]$HostName)
    $r = [ordered]@{ host = $HostName; port = $PortNum; free = $true; error = $null }
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($HostName, $PortNum, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(500, $false)
        if (-not $ok) {
            # BUG 3: timeout means the host did not answer; we assume the port
            # is free. In reality timeout means we do not know (often firewalled).
            $r.free = $true
            $r.error = "timeout"
            return $r
        }
        try {
            $client.EndConnect($iar)
            # connect succeeded: something IS listening -> port is NOT free
            $r.free = $false
            $r.error = "in_use"
        } catch [System.Net.Sockets.SocketException] {
            # ECONNREFUSED -> nothing listening -> port is free
            $r.free = $true
            $r.error = $null
        }
    } catch {
        $r.free = $true
        $r.error = $_.Exception.Message
    } finally {
        $client.Close()
    }
    return $r
}

# -----------------------------------------------------------------------------
# Check: tool versions
# -----------------------------------------------------------------------------
function Get-ToolVersion {
    param([string]$Name, [string[]]$VerArgs)
    try {
        if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) { return $null }
        $out = & $Name @VerArgs 2>&1
        if ($LASTEXITCODE -ne 0) { return $null }
        return (($out | Select-Object -First 1).ToString().Trim())
    } catch {
        return $null
    }
}

function Check-Versions {
    return [ordered]@{
        python  = Get-ToolVersion "python" @("--version")
        uv      = Get-ToolVersion "uv" @("--version")
        compose = Get-ToolVersion "docker" @("compose", "version")
    }
}

# -----------------------------------------------------------------------------
# Aggregator: run all checks once, return ordered hashtable + overall ok flag.
# -----------------------------------------------------------------------------
function Run-Checks {
    param([string]$DiskPath, [int]$MinFreeMb, [string]$HostName, [string[]]$Ports)

    $checks = [ordered]@{}
    $checks.docker   = Check-Docker
    $gpu             = Check-Gpus
    $checks.gpus     = $gpu
    $checks.disk     = Check-Disk -DiskPath $DiskPath -MinFreeMb $MinFreeMb
    $portResults = @()
    foreach ($p in $Ports) {
        $portResults += Check-Port -PortNum ([int]$p) -HostName $HostName
    }
    $checks.ports    = $portResults
    $checks.versions = Check-Versions

    $allOk = $true
    if (-not $checks.docker.available) { $allOk = $false }
    if ($Ports.Count -gt 0 -or $DiskPath) {
        if ($DiskPath -and -not $checks.disk.ok) { $allOk = $false }
        foreach ($pr in $portResults) {
            if (-not $pr.free) { $allOk = $false }
        }
    }
    if (-not $gpu.available) { $allOk = $false }

    return @{ checks = $checks; all_ok = $allOk }
}

# -----------------------------------------------------------------------------
# Single-shot mode: print JSON and exit.
# -----------------------------------------------------------------------------
function Invoke-SingleShot {
    param($Parsed)
    $r = Run-Checks -DiskPath $Parsed.Path -MinFreeMb $Parsed.MinFreeMb -HostName $Parsed.Host_ -Ports $Parsed.Ports
    $payload = [ordered]@{
        checks = $r.checks
        all_ok = $r.all_ok
    }
    $json = $payload | ConvertTo-Json -Depth 8 -Compress
    Write-Output $json
    # BUG 4: exit code is always 0; we ignore $r.all_ok.
    exit 0
}

# -----------------------------------------------------------------------------
# Watch mode (Stage 2): NOT YET IMPLEMENTED - to be added by the agent.
# Intended behavior:
#   - tick at t=0, then every IntervalS seconds, until t >= DurationS
#   - each tick appends one JSON line to Output:
#       {"tick": <i>, "timestamp": "...", "checks": {...}, "all_ok": <bool>}
#   - exit 0 if all ticks ok, 1 if any tick had a failed check, 2 on error
# -----------------------------------------------------------------------------
function Invoke-Watch {
    param($Parsed)
    Write-Error "watch mode not yet implemented (Stage 2)"
    exit 2
}

# --- main --------------------------------------------------------------------
$parsed = Parse-Args -Argv $args

if ($parsed.Watch) {
    Invoke-Watch -Parsed $parsed
} else {
    Invoke-SingleShot -Parsed $parsed
}
