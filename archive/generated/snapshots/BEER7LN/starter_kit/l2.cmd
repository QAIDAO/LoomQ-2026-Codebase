@echo off
setlocal
if "%~1"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\l2-service.ps1" start
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\l2-service.ps1" %*
)
exit /b %ERRORLEVEL%
