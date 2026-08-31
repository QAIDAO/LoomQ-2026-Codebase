$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pythonPath = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
$reportPath = Join-Path $repositoryRoot "starter_kit\evidence\files\l1-public-report.json"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Missing .venv. Run starter_kit\scripts\setup.ps1 first."
}

$env:PYTHONUTF8 = "1"
Push-Location $repositoryRoot
try {
    & $pythonPath -m pip check
    if ($LASTEXITCODE -ne 0) { throw "pip check failed" }

    & $pythonPath -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "organizer tests failed" }

    & $pythonPath -m unittest discover -s starter_kit\tests -v
    if ($LASTEXITCODE -ne 0) { throw "submission tests failed" }

    & $pythonPath starter_kit\evaluator.py --level l1 --target spinq,originq,braket --json-out $reportPath
    if ($LASTEXITCODE -ne 0) { throw "public L1 evaluator failed" }

    & $pythonPath starter_kit\tests\public_l2_fake.py
    if ($LASTEXITCODE -ne 0) { throw "public L2 fake-endpoint check failed" }

    & $pythonPath starter_kit\evaluator.py --level l3
    if ($LASTEXITCODE -ne 0) { throw "public L3 evaluator failed" }

    & $pythonPath -m unittest starter_kit.tests.test_hybrid_compiler starter_kit.tests.test_quantum_riscv_extension -v
    if ($LASTEXITCODE -ne 0) { throw "L3 or custom quantum RISC-V verification failed" }

    & $pythonPath -m unittest starter_kit.tests.test_hardware_tools -v
    if ($LASTEXITCODE -ne 0) { throw "hardware readiness tools verification failed" }

    git diff --check
    if ($LASTEXITCODE -ne 0) { throw "git diff --check failed" }

    $bytes = 0
    $paths = git ls-files --cached --others --exclude-standard -- starter_kit
    foreach ($path in $paths) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $bytes += (Get-Item -LiteralPath $path).Length
        }
    }
    if ($bytes -ge 100MB) { throw "starter_kit archive projection exceeds 100 MiB" }
    Write-Output "VERIFICATION PASS: starter_kit projection $bytes bytes"
} finally {
    Pop-Location
}
