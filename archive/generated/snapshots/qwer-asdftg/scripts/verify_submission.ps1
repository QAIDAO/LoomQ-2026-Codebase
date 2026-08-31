<#!
.SYNOPSIS
Build the current Starter Kit image and run the reproducible LoomQ checks.

.DESCRIPTION
This script never mounts host source into the container. It stops on the first
failed Docker command and leaves no credentials in output or files.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$starterKit = Join-Path $repositoryRoot 'starter_kit'
$image = 'loomq-l1'

function Invoke-LoomQDocker {
    param([Parameter(Mandatory = $true)][string[]]$DockerArgs)

    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed with exit code ${LASTEXITCODE}: docker $($DockerArgs -join ' ')"
    }
}

Invoke-LoomQDocker @('build', '-t', $image, $starterKit)

foreach ($level in 'l1', 'l2', 'l3') {
    Invoke-LoomQDocker @(
        'run', '--rm', '-w', '/workspace', $image,
        'python', '-m', 'unittest', 'discover', '-s', "starter_kit/tests/$level", '-p', 'test_*.py', '-v'
    )
}

Invoke-LoomQDocker @(
    'run', '--rm', '-w', '/workspace', $image,
    'python', '-m', 'starter_kit.evaluator', '--level', 'l1',
    '--target', 'spinq,originq,braket', '--shots', '8192'
)
Invoke-LoomQDocker @('run', '--rm', '-w', '/workspace', $image, 'python', '-m', 'starter_kit.evaluator', '--level', 'l3')

Write-Host 'LoomQ Docker verification completed.'
