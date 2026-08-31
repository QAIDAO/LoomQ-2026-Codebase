param(
    [Parameter(Mandatory = $true)][decimal]$MaxEstimatedUsd,
    [int]$Shots = 100,
    [int]$TimeoutSeconds = 7200
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
if ([string]::IsNullOrWhiteSpace($env:LOOMQ_BRAKET_S3_BUCKET)) {
    throw "LOOMQ_BRAKET_S3_BUCKET is not set. Configure AWS locally before continuing."
}
$env:PYTHONUTF8 = "1"
Push-Location $root
try {
    & $python -m starter_kit.hardware.braket_qpu --shots $Shots --timeout $TimeoutSeconds --max-estimated-usd $MaxEstimatedUsd --confirm-paid-hardware
    if ($LASTEXITCODE -ne 0) { throw "AWS Braket hardware runner failed" }
} finally { Pop-Location }
