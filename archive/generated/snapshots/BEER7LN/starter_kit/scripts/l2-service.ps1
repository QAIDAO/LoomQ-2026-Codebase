[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Action = "status",

    [ValidateRange(1, 65535)]
    [int]$Port = 8765,

    [ValidateSet("127.0.0.1", "localhost")]
    [string]$BindAddress = "127.0.0.1",

    [string]$EnvFile = "",

    [string]$HardwareEnvFile = "",

    [switch]$NoPrompt
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$starterKitRoot = Split-Path -Parent $PSScriptRoot
$repositoryRoot = Split-Path -Parent $starterKitRoot
if (-not $EnvFile) {
    $EnvFile = Join-Path $starterKitRoot ".env.l2.local"
}
if (-not $HardwareEnvFile) {
    $HardwareEnvFile = Join-Path $repositoryRoot ".env.hardware.local"
}
$pidFile = Join-Path $starterKitRoot ".l2-service-$Port.pid"
$serviceUrl = "http://${BindAddress}:$Port"
$requiredVariables = @(
    "LOOMQ_LLM_BASE_URL",
    "LOOMQ_LLM_API_KEY",
    "LOOMQ_LLM_MODEL"
)

function Import-LoomQEnvironment {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "配置文件不存在：$Path。请复制 .env.l2.example 为 .env.l2.local 并填写。"
    }

    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            continue
        }
        if ($line.StartsWith("export ")) {
            $line = $line.Substring(7).Trim()
        }
        $match = [regex]::Match($line, '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$')
        if (-not $match.Success) {
            throw "无法解析配置行；请使用 NAME=value 格式。"
        }
        $name = $match.Groups[1].Value
        $value = $match.Groups[2].Value.Trim()
        if ($value.Length -ge 2) {
            $firstCharacter = [int][char]$value[0]
            $lastCharacter = [int][char]$value[$value.Length - 1]
            $quotedWithDouble = $firstCharacter -eq 34 -and $lastCharacter -eq 34
            $quotedWithSingle = $firstCharacter -eq 39 -and $lastCharacter -eq 39
            if ($quotedWithDouble -or $quotedWithSingle) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        [Environment]::SetEnvironmentVariable(
            $name,
            $value,
            [EnvironmentVariableTarget]::Process
        )
    }
}

function Get-ManagedProcess {
    if (-not (Test-Path -LiteralPath $pidFile)) {
        return $null
    }
    $pidText = (Get-Content -Raw -LiteralPath $pidFile).Trim()
    $managedPid = 0
    if (-not [int]::TryParse($pidText, [ref]$managedPid)) {
        throw "PID 文件损坏：$pidFile"
    }
    try {
        $managedProcess = Get-Process -Id $managedPid -ErrorAction Stop
    }
    catch {
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
    if ($managedProcess.ProcessName -notmatch '^pythonw?$') {
        throw "PID $managedPid 当前属于 $($managedProcess.ProcessName)，为安全起见拒绝关闭。"
    }
    return $managedProcess
}

function Test-LoomQHealth {
    try {
        $health = Invoke-RestMethod -Uri "$serviceUrl/api/health" -TimeoutSec 2
        if (
            $health.status -ne "ok" -or
            $health.service -ne "loomq-studio" -or
            $health.ui_revision -ne "remotion-hyperframes-1" -or
            $health.agent_revision -ne "validated-live-llm-2"
        ) {
            return $false
        }
        $motionScript = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "$serviceUrl/motion/loomq-motion.iife.js" `
            -TimeoutSec 2
        $motionStyle = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "$serviceUrl/motion/loomq-motion.css" `
            -TimeoutSec 2
        return (
            $motionScript.StatusCode -eq 200 -and
            $motionScript.RawContentLength -gt 1000 -and
            $motionStyle.StatusCode -eq 200 -and
            $motionStyle.RawContentLength -gt 1000
        )
    }
    catch {
        return $false
    }
}

function Assert-LoomQConfiguration {
    $missing = @()
    foreach ($name in $requiredVariables) {
        $value = [Environment]::GetEnvironmentVariable(
            $name,
            [EnvironmentVariableTarget]::Process
        )
        if ([string]::IsNullOrWhiteSpace($value) -or $value -match '^(REPLACE_ME|CHANGE_ME)$') {
            $missing += $name
        }
    }

    if ($missing -contains "LOOMQ_LLM_API_KEY" -and -not $NoPrompt) {
        $secureKey = Read-Host "请输入 L2 API Key（不会回显）" -AsSecureString
        $plainKey = [System.Net.NetworkCredential]::new("", $secureKey).Password
        if (-not [string]::IsNullOrWhiteSpace($plainKey)) {
            [Environment]::SetEnvironmentVariable(
                "LOOMQ_LLM_API_KEY",
                $plainKey,
                [EnvironmentVariableTarget]::Process
            )
            $missing = @($missing | Where-Object { $_ -ne "LOOMQ_LLM_API_KEY" })
        }
    }

    if ($missing.Count -gt 0) {
        throw "缺少配置：$($missing -join ', ')。请编辑 $EnvFile。"
    }
}

function Start-LoomQService {
    $existingProcess = Get-ManagedProcess
    if ($null -ne $existingProcess) {
        if (Test-LoomQHealth) {
            Write-Output "LoomQ L2 已运行：$serviceUrl（PID $($existingProcess.Id)）"
            return
        }
        throw "PID $($existingProcess.Id) 仍存在，但健康检查失败。请先运行 stop。"
    }
    if (Test-LoomQHealth) {
        throw "端口 $Port 已有 LoomQ 服务，但不是由本脚本启动；请先关闭旧服务。"
    }

    Import-LoomQEnvironment -Path $EnvFile
    if (Test-Path -LiteralPath $HardwareEnvFile) {
        Import-LoomQEnvironment -Path $HardwareEnvFile
    }
    Assert-LoomQConfiguration

    $nativePython = Join-Path $repositoryRoot ".venv-l1-native\Scripts\python.exe"
    $pythonExecutable = if (Test-Path -LiteralPath $nativePython) {
        $nativePython
    }
    else {
        (Get-Command python -ErrorAction Stop).Source
    }
    $application = Join-Path $starterKitRoot "l2_app.py"
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $pythonExecutable
    $startInfo.Arguments = "`"$application`" --host $BindAddress --port $Port"
    $startInfo.WorkingDirectory = $starterKitRoot
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $serviceProcess = [System.Diagnostics.Process]::Start($startInfo)
    Set-Content -LiteralPath $pidFile -Value $serviceProcess.Id -Encoding ASCII

    $healthy = $false
    for ($attempt = 0; $attempt -lt 15; $attempt += 1) {
        Start-Sleep -Milliseconds 200
        if ($serviceProcess.HasExited) {
            break
        }
        if (Test-LoomQHealth) {
            $healthy = $true
            break
        }
    }
    if (-not $healthy) {
        if (-not $serviceProcess.HasExited) {
            Stop-Process -Id $serviceProcess.Id -ErrorAction SilentlyContinue
        }
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        throw "LoomQ L2 启动失败；请用前台命令 python l2_app.py 查看详细错误。"
    }
    Write-Output "LoomQ L2 已启动：$serviceUrl（PID $($serviceProcess.Id)）"
}

function Stop-LoomQService {
    $managedProcess = Get-ManagedProcess
    if ($null -eq $managedProcess) {
        Write-Output "LoomQ L2 已停止。"
        return
    }
    $managedPid = $managedProcess.Id
    Stop-Process -Id $managedPid
    try {
        Wait-Process -Id $managedPid -Timeout 5 -ErrorAction Stop
    }
    catch {
        if (Get-Process -Id $managedPid -ErrorAction SilentlyContinue) {
            throw "无法在 5 秒内关闭 PID $managedPid。"
        }
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Write-Output "LoomQ L2 已关闭（PID $managedPid）。"
}

function Show-LoomQStatus {
    $managedProcess = Get-ManagedProcess
    if ($null -eq $managedProcess) {
        Write-Output "状态：已停止"
        return
    }
    $healthText = if (Test-LoomQHealth) { "健康" } else { "异常" }
    Write-Output "状态：$healthText；地址：$serviceUrl；PID：$($managedProcess.Id)"
}

switch ($Action) {
    "start" { Start-LoomQService }
    "stop" { Stop-LoomQService }
    "restart" {
        Stop-LoomQService
        Start-LoomQService
    }
    "status" { Show-LoomQStatus }
}
