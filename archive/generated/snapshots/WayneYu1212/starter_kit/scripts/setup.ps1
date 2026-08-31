$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$venvPath = Join-Path $repositoryRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"
$requirementsPath = Join-Path $repositoryRoot "starter_kit\requirements.txt"

$env:PYTHONUTF8 = "1"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    py -3.10 -m venv $venvPath
}

& $pythonPath -c "import sys; assert sys.version_info[:2] == (3, 10), sys.version"
& $pythonPath -m pip install --upgrade "pip==26.2"
& $pythonPath -m pip install --requirement $requirementsPath
& $pythonPath -m pip check

Write-Output "LoomQ environment ready: $pythonPath"
Write-Output "Public evaluator: $pythonPath starter_kit\evaluator.py --level l1 --target spinq,originq,braket"
Write-Output "LoomQ Lab: .\starter_kit\scripts\run_web.ps1 -Port 8765"
