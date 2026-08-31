param([int]$Shots = 100, [int]$TimeoutSeconds = 3600)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
if ([string]::IsNullOrWhiteSpace($env:LOOMQ_ORIGINQ_TOKEN)) {
    throw "LOOMQ_ORIGINQ_TOKEN is not set. Keep the token local; never paste it into chat."
}
$env:PYTHONUTF8 = "1"
Push-Location $root
try {
    & $python -m starter_kit.hardware.originq_real --shots $Shots --timeout $TimeoutSeconds --confirm-real-hardware
    if ($LASTEXITCODE -ne 0) { throw "Origin Quantum hardware runner failed" }
} finally { Pop-Location }
