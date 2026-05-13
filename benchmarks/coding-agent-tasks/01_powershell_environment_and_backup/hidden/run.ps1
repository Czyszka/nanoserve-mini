#!/usr/bin/env pwsh
# Hidden test runner. Executed by the harness AFTER the agent finishes.
#
# $env:WORK_DIR points at the agent's solution directory, which must contain
# starter/Export-RunArtifacts.ps1.

$ErrorActionPreference = 'Stop'

$WorkDir = if ($env:WORK_DIR) {
    $env:WORK_DIR
} else {
    (Resolve-Path "$PSScriptRoot/..").Path
}

Write-Host "Running hidden tests against $WorkDir"
& "$PSScriptRoot/tests/Export-RunArtifacts.Hidden.Tests.ps1" -WorkDir $WorkDir
exit $LASTEXITCODE
