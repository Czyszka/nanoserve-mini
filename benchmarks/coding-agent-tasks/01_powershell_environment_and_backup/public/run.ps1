#!/usr/bin/env pwsh
# Public test runner. Uses hand-rolled asserts (no Pester required).
#
# $env:WORK_DIR points at the agent's working copy of the task directory,
# which must contain starter/Export-RunArtifacts.ps1. Defaults to the parent
# of this script for local smoke testing.

$ErrorActionPreference = 'Stop'

$WorkDir = if ($env:WORK_DIR) {
    $env:WORK_DIR
} else {
    (Resolve-Path "$PSScriptRoot/..").Path
}

Write-Host "Running public tests against $WorkDir"
& "$PSScriptRoot/tests/Export-RunArtifacts.Public.Tests.ps1" -WorkDir $WorkDir
exit $LASTEXITCODE
