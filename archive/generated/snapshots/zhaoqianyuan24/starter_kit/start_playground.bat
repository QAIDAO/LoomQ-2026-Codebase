@echo off
setlocal
cd /d "%~dp0"

if not defined LOOMQ_PORT set "LOOMQ_PORT=4173"
set "LOOMQ_URL=http://127.0.0.1:%LOOMQ_PORT%/"
set "LOOMQ_PYTHON_EXE="
set "LOOMQ_PYTHON_ARGS="
set "LOOMQ_PYTHON_LABEL="
set "LOOMQ_BOOTSTRAP_EXE="
set "LOOMQ_BOOTSTRAP_ARGS="
set "LOOMQ_BOOTSTRAP_LABEL="
set "LOOMQ_SERVICE_ALREADY_RUNNING=0"

call :service_http_ready
if not errorlevel 1 (
  call :service_runtime_ready
  if not errorlevel 1 (
    set "LOOMQ_SERVICE_ALREADY_RUNNING=1"
    goto open_browser
  )
  echo [LoomQ] Port %LOOMQ_PORT% already has a Product Service without a complete backend runtime.
  echo [LoomQ] Close that service, then run start_playground.bat again from a complete Python 3.10 environment.
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" call :try_python "%CD%\.venv\Scripts\python.exe" "" "repository .venv"
if defined LOOMQ_PYTHON_EXE goto start_service

echo [LoomQ] A complete repository .venv is not available.
call :find_bootstrap_python

if not defined LOOMQ_BOOTSTRAP_EXE (
  echo [LoomQ] Python 3.10 was not found, so the local environment cannot be initialized.
  echo [LoomQ] Install Python 3.10 from https://www.python.org/downloads/ and run this file again.
  pause
  exit /b 1
)

echo [LoomQ] First-time setup will create or repair starter_kit\.venv and install runtime requirements.
echo [LoomQ] Python: %LOOMQ_BOOTSTRAP_LABEL%
echo [LoomQ] This may take several minutes and requires network access.
choice /C YN /N /M "[LoomQ] Continue? [Y/N]: "
if errorlevel 2 (
  echo [LoomQ] Setup cancelled. No service was started.
  exit /b 1
)

echo [LoomQ] Creating repository-local Python environment...
"%LOOMQ_BOOTSTRAP_EXE%" %LOOMQ_BOOTSTRAP_ARGS% -m venv ".venv"
if errorlevel 1 goto venv_create_failed

if not exist ".venv\Scripts\python.exe" goto venv_create_failed

rem Keep the repository-local runtime out of Git without changing project files.
> ".venv\.gitignore" echo *

echo [LoomQ] Installing runtime dependencies...
".venv\Scripts\python.exe" -m pip install -r "requirements.txt"
if errorlevel 1 goto dependency_install_failed

set "LOOMQ_PYTHON_EXE="
set "LOOMQ_PYTHON_ARGS="
set "LOOMQ_PYTHON_LABEL="
call :try_python "%CD%\.venv\Scripts\python.exe" "" "repository .venv"

if not defined LOOMQ_PYTHON_EXE (
  echo [LoomQ] Setup finished, but the repository .venv failed runtime preflight.
  echo [LoomQ] Required imports: adapter, spinqit, pyqpanda, braket.
  echo [LoomQ] Review the installation output above, then run this file again.
  pause
  exit /b 1
)

:start_service
echo [LoomQ] Runtime ready: %LOOMQ_PYTHON_LABEL%
echo [LoomQ] Starting Product Service with %LOOMQ_PYTHON_EXE% %LOOMQ_PYTHON_ARGS% ...
start "LoomQ Product Service" cmd /k ""%LOOMQ_PYTHON_EXE%" %LOOMQ_PYTHON_ARGS% -B product_service.py --port %LOOMQ_PORT%"

set /a LOOMQ_ATTEMPT=0
:wait_for_service
call :service_runtime_ready
if not errorlevel 1 goto open_browser
set /a LOOMQ_ATTEMPT+=1
if %LOOMQ_ATTEMPT% GEQ 30 goto start_failed
timeout /t 1 /nobreak >nul
goto wait_for_service

:open_browser
if "%LOOMQ_SERVICE_ALREADY_RUNNING%"=="1" echo [LoomQ] Product Service is already running.
echo [LoomQ] Ready: %LOOMQ_URL%
if defined LOOMQ_NO_BROWSER (
  echo [LoomQ] Browser opening skipped for this test run.
) else (
  start "" "%LOOMQ_URL%"
  echo [LoomQ] Browser opened. The service runs in the Product Service window.
)
timeout /t 3 /nobreak >nul
exit /b 0

:start_failed
echo [LoomQ] Product Service did not become ready within 30 seconds.
echo Check the Product Service window for the detailed error.
pause
exit /b 1

:venv_create_failed
echo [LoomQ] Failed to create the repository .venv.
echo [LoomQ] Check that Python 3.10 includes the venv module and that this folder is writable.
pause
exit /b 1

:dependency_install_failed
echo [LoomQ] Failed to install requirements into starter_kit\.venv.
echo [LoomQ] Check the network connection and the pip error above. No service was started.
pause
exit /b 1

:service_http_ready
powershell -NoProfile -NonInteractive -Command "$ProgressPreference = 'SilentlyContinue'; try { $response = Invoke-WebRequest -UseBasicParsing -Uri '%LOOMQ_URL%' -TimeoutSec 1; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
exit /b %errorlevel%

:service_runtime_ready
powershell -NoProfile -NonInteractive -Command "$ProgressPreference = 'SilentlyContinue'; try { $response = Invoke-RestMethod -Uri '%LOOMQ_URL%api/runtime-readiness' -TimeoutSec 2; if ($response.ready -eq $true) { exit 0 } } catch {}; exit 1" >nul 2>&1
exit /b %errorlevel%

:try_python
set "LOOMQ_CANDIDATE_EXE=%~1"
set "LOOMQ_CANDIDATE_ARGS=%~2"
set "LOOMQ_CANDIDATE_LABEL=%~3"
"%LOOMQ_CANDIDATE_EXE%" %LOOMQ_CANDIDATE_ARGS% -c "import sys; assert sys.version_info[:2] == (3, 10); import adapter, spinqit, pyqpanda, braket; from braket.devices import LocalSimulator" >nul 2>&1
if errorlevel 1 (
  echo [LoomQ] Skipping %LOOMQ_CANDIDATE_LABEL%: Python 3.10 or runtime dependencies are incomplete.
  exit /b 0
)
set "LOOMQ_PYTHON_EXE=%LOOMQ_CANDIDATE_EXE%"
set "LOOMQ_PYTHON_ARGS=%LOOMQ_CANDIDATE_ARGS%"
set "LOOMQ_PYTHON_LABEL=%LOOMQ_CANDIDATE_LABEL%"
exit /b 0

:find_bootstrap_python
if not defined LOOMQ_BOOTSTRAP_EXE call :try_bootstrap_python "py" "-3.10" "Python launcher 3.10"
if not defined LOOMQ_BOOTSTRAP_EXE if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\Scripts\python.exe" call :try_bootstrap_python "%VIRTUAL_ENV%\Scripts\python.exe" "" "active Python 3.10 environment"
if not defined LOOMQ_BOOTSTRAP_EXE if exist "%LocalAppData%\Programs\Python\Python310\python.exe" call :try_bootstrap_python "%LocalAppData%\Programs\Python\Python310\python.exe" "" "per-user Python 3.10"
if not defined LOOMQ_BOOTSTRAP_EXE if exist "%ProgramFiles%\Python310\python.exe" call :try_bootstrap_python "%ProgramFiles%\Python310\python.exe" "" "system Python 3.10"
if not defined LOOMQ_BOOTSTRAP_EXE call :try_bootstrap_python "python" "" "PATH Python 3.10"
exit /b 0

:try_bootstrap_python
set "LOOMQ_CANDIDATE_EXE=%~1"
set "LOOMQ_CANDIDATE_ARGS=%~2"
set "LOOMQ_CANDIDATE_LABEL=%~3"
"%LOOMQ_CANDIDATE_EXE%" %LOOMQ_CANDIDATE_ARGS% -c "import sys; assert sys.version_info[:2] == (3, 10)" >nul 2>&1
if errorlevel 1 exit /b 0
set "LOOMQ_BOOTSTRAP_EXE=%LOOMQ_CANDIDATE_EXE%"
set "LOOMQ_BOOTSTRAP_ARGS=%LOOMQ_CANDIDATE_ARGS%"
set "LOOMQ_BOOTSTRAP_LABEL=%LOOMQ_CANDIDATE_LABEL%"
exit /b 0
