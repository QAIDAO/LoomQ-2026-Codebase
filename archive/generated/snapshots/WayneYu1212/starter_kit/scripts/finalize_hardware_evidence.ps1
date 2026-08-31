$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$origin = Join-Path $root "starter_kit\evidence\files\originq-hardware-metadata.json"
$braket = Join-Path $root "starter_kit\evidence\files\braket-hardware-metadata.json"
$spinq = Join-Path $root "starter_kit\evidence\files\spinq-hardware-metadata.json"
if (-not (Test-Path -LiteralPath $origin)) {
    throw "Genuine OriginQ metadata is required."
}
$second = if (Test-Path -LiteralPath $braket) { $braket } elseif (Test-Path -LiteralPath $spinq) { $spinq } else { $null }
if ($null -eq $second) { throw "A second genuine Braket or SpinQ metadata file is required." }
$env:PYTHONUTF8 = "1"
Push-Location $root
try {
    & $python -m starter_kit.hardware.validate_evidence $origin $second
    if ($LASTEXITCODE -ne 0) { throw "Hardware evidence validation failed" }
    & $python -m starter_kit.hardware.finalize_evidence $origin $second
    if ($LASTEXITCODE -ne 0) { throw "Hardware evidence finalization failed" }
} finally { Pop-Location }
