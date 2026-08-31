[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Action = "start",

    [ValidateRange(1, 65535)]
    [int]$Port = 8766,

    [switch]$NoBrowser
)


$ErrorActionPreference = "Stop"

# LoomQ L2 一键入口。双击或运行 .\start.ps1 即可启动并打开网页。
# 默认使用 8766，避免与其他常见本地开发服务的 8765 端口冲突。
$repositoryRoot = $PSScriptRoot
$serviceScript = Join-Path $repositoryRoot "starter_kit\scripts\l2-service.ps1"
if (-not (Test-Path -LiteralPath $serviceScript)) {
    throw "找不到 L2 服务脚本：$serviceScript"
}

& $serviceScript -Action $Action -Port $Port

if (($Action -eq "start" -or $Action -eq "restart") -and -not $NoBrowser) {
    $url = "http://127.0.0.1:$Port/"
    Start-Process $url
    Write-Output "已在默认浏览器打开：$url"
}
