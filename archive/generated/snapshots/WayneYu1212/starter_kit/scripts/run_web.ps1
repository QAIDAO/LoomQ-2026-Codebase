param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8765,
    [Alias("Host")]
    [string]$BindAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$venvPath = Join-Path $repositoryRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"
# Required interpreter path: .venv\Scripts\python.exe
$setupCommand = ".\starter_kit\scripts\setup.ps1"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Missing $pythonPath. Run $setupCommand from the repository root first."
}

$pythonVersion = (& $pythonPath -X utf8 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne "3.10") {
    throw "The repository .venv must use Python 3.10; run $setupCommand from the repository root."
}

$spinqitVersion = (& $pythonPath -X utf8 -c "import importlib.metadata as metadata; import spinqit; print(metadata.version('spinqit'))").Trim()
if ($LASTEXITCODE -ne 0 -or $spinqitVersion -ne "0.2.4") {
    throw "The repository .venv must provide spinqit==0.2.4; run $setupCommand from the repository root."
}

# Default local URL: http://127.0.0.1:8765/
$localUrl = "http://$($BindAddress):$Port/"
Write-Output "LoomQ Lab: $localUrl"
& $pythonPath -X utf8 -m starter_kit.loomq.web.server --host $BindAddress --port $Port
exit $LASTEXITCODE
