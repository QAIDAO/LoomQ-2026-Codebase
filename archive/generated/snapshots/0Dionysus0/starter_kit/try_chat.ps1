# One-click launcher for LoomQ zero-foundation chat (Windows / Cursor Terminal)
#
# 1) Open Cursor Terminal (Ctrl+`)
# 2) Run:
#      cd starter_kit
#      $env:LOOMQ_LLM_KEY_FILE = "C:\path\to\key.txt"
#      powershell -ExecutionPolicy Bypass -File .\try_chat.ps1
#
# Or if LOOMQ_LLM_API_KEY is already set, just:
#      powershell -ExecutionPolicy Bypass -File .\try_chat.ps1

$ErrorActionPreference = "Stop"
$kit = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $kit

if (-not $env:LOOMQ_LLM_API_KEY) {
    if (-not $env:LOOMQ_LLM_KEY_FILE) {
        Write-Host "Set a key first, either:"
        Write-Host '  $env:LOOMQ_LLM_API_KEY = "your-key"'
        Write-Host '  $env:LOOMQ_LLM_KEY_FILE = "C:\path\to\key.txt"'
        exit 2
    }
    if (-not (Test-Path $env:LOOMQ_LLM_KEY_FILE)) {
        Write-Host "Key file not found: $($env:LOOMQ_LLM_KEY_FILE)"
        exit 2
    }
    $env:LOOMQ_LLM_API_KEY = (Get-Content -Raw $env:LOOMQ_LLM_KEY_FILE).Trim()
}

if (-not $env:LOOMQ_LLM_BASE_URL) { $env:LOOMQ_LLM_BASE_URL = "https://api.deepseek.com" }
if (-not $env:LOOMQ_LLM_MODEL) { $env:LOOMQ_LLM_MODEL = "deepseek-v4-flash" }
if (-not $env:LOOMQ_LLM_TIMEOUT_SECONDS) { $env:LOOMQ_LLM_TIMEOUT_SECONDS = "120" }
$env:PYTHONIOENCODING = "utf-8"

$py = Join-Path $kit "..\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "Starting LoomQ chat. Try: 1 / 2 / 3 / help / quit"
& $py .\chat.py @args
