$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Missing .venv; run starter_kit\scripts\setup.ps1" }
$env:PYTHONUTF8 = "1"
Push-Location $root
try {
    & $python -m starter_kit.hardware.originq_real --doctor
    $originStatus = $LASTEXITCODE
    & $python -m starter_kit.hardware.braket_qpu --doctor
    $braketStatus = $LASTEXITCODE
    if ($originStatus -ne 0 -or $braketStatus -ne 0) {
        Write-Output "HARDWARE DOCTOR: human account/credential setup is still required."
        exit 2
    }
    Write-Output "HARDWARE DOCTOR PASS"
} finally { Pop-Location }
