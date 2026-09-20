@echo off
setlocal enabledelayedexpansion

title APS Chess AI - Stand Launcher
cd /d "%~dp0"

echo ======================================================================
echo                APS CHESS AI - KIOSK STAND LAUNCHER
echo              Developed by the APS Machine Learning Team
echo ======================================================================
echo.

if not exist logs mkdir logs

:: ----------------------------------------------------------------------
:: 1. PREREQUISITE CHECKS
:: ----------------------------------------------------------------------

echo [1/5] Verifying system prerequisites...

:: Check model file
if not exist "chess_value_model.keras.zip" (
    echo [ERROR] Neural model file not found: chess_value_model.keras.zip
    echo Please verify that the repository was fully cloned with all assets.
    goto ON_ERROR
)

:: Check frontend project file
if not exist "stage5_ui\frontend\package.json" (
    echo [ERROR] Frontend project definition not found: stage5_ui\frontend\package.json
    goto ON_ERROR
)

:: Check Python 3.11
py -3.11 --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.11 is required but was not found via 'py -3.11'.
    echo Please install Python 3.11 and ensure it is registered in the Windows Python launcher.
    goto ON_ERROR
)

:: Check Node.js
cmd.exe /c "node --version" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js is required but was not found on PATH.
    echo Please install Node.js v20 or higher.
    goto ON_ERROR
)

:: Check npm
cmd.exe /c "npm --version" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm was not found on PATH.
    echo Please verify your Node.js installation.
    goto ON_ERROR
)

:: Check Python dependencies
py -3.11 -c "import tensorflow, chess, fastapi, uvicorn, pydantic, numpy" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARN] One or more Python runtime dependencies are missing.
    echo [INFO] Installing dependencies from requirements.txt...
    py -3.11 -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install Python dependencies from requirements.txt.
        goto ON_ERROR
    )
)

echo [OK] All prerequisites verified.
echo.

:: ----------------------------------------------------------------------
:: 2. FRONTEND PRODUCTION BUILD CHECK
:: ----------------------------------------------------------------------

echo [2/5] Checking frontend distribution...

if exist "stage5_ui\frontend\dist\index.html" goto DIST_READY

echo [INFO] Production build not found. Preparing distribution...
if not exist "stage5_ui\frontend\node_modules" (
    echo [INFO] Installing frontend npm packages...
    pushd stage5_ui\frontend
    cmd.exe /c "npm install"
    if %ERRORLEVEL% neq 0 (
        popd
        echo [ERROR] 'npm install' failed.
        goto ON_ERROR
    )
    popd
)

echo [INFO] Building frontend production bundle...
pushd stage5_ui\frontend
cmd.exe /c "npm run build"
if %ERRORLEVEL% neq 0 (
    popd
    echo [ERROR] 'npm run build' failed.
    goto ON_ERROR
)
popd

:DIST_READY
echo [OK] Production distribution is ready.
echo.

:: ----------------------------------------------------------------------
:: 3. BACKEND ENGINE INITIALIZATION
:: ----------------------------------------------------------------------

echo [3/5] Initializing engine backend...

:: Check port 8000 state: 0=free, 1=already healthy, 2=occupied by conflict
py -3.11 stage5_ui\check_port.py 8000 http://127.0.0.1:8000/api/health healthy
set PORT8000_STATE=%ERRORLEVEL%

if %PORT8000_STATE% equ 1 (
    echo [INFO] Existing healthy APS Chess AI backend detected on port 8000.
    goto BACKEND_HEALTHY
)

if %PORT8000_STATE% equ 2 (
    echo [ERROR] Port 8000 is occupied by an unrelated application or unresponsive process.
    echo Please terminate the conflicting process or free port 8000 and try again.
    goto ON_ERROR
)

echo [INFO] Starting engine server on http://127.0.0.1:8000...
echo [INFO] Startup logs redirected to: logs\backend.log
type nul > logs\backend.log
type nul > logs\backend_err.log
powershell -NoProfile -Command "Start-Process -FilePath 'py' -ArgumentList '-3.11 -m uvicorn stage5_ui.backend.main:app --host 127.0.0.1 --port 8000' -WindowStyle Minimized -RedirectStandardOutput 'logs\backend.log' -RedirectStandardError 'logs\backend_err.log'"

:: Wait for backend health with timeout (60 seconds)
echo [INFO] Waiting for engine warmup and model load...
set /a RETRIES=0

:WAIT_BACKEND_LOOP
py -3.11 -c "import urllib.request; data = urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1.5).read().decode(); assert 'healthy' in data" >nul 2>&1
if %ERRORLEVEL% equ 0 goto BACKEND_HEALTHY

:: Early failure detection if backend crashed
if %RETRIES% geq 5 (
    findstr /C:"Traceback (most recent call last)" logs\backend.log logs\backend_err.log >nul 2>&1
    if !ERRORLEVEL! equ 0 goto BACKEND_CRASHED
    findstr /C:"ERROR:" logs\backend.log logs\backend_err.log >nul 2>&1
    if !ERRORLEVEL! equ 0 goto BACKEND_CRASHED
)

set /a RETRIES+=1
if %RETRIES% geq 60 goto BACKEND_TIMEOUT

ping -n 2 127.0.0.1 >nul
goto WAIT_BACKEND_LOOP

:BACKEND_CRASHED
echo.
echo [ERROR] Engine backend process terminated unexpectedly during startup!
echo Backend log output:
echo ----------------------------------------------------------------------
if exist logs\backend.log type logs\backend.log
if exist logs\backend_err.log type logs\backend_err.log
echo ----------------------------------------------------------------------
goto ON_ERROR

:BACKEND_TIMEOUT
echo.
echo [ERROR] Engine backend startup timed out after 60 seconds!
echo Backend log output:
echo ----------------------------------------------------------------------
if exist logs\backend.log type logs\backend.log
if exist logs\backend_err.log type logs\backend_err.log
echo ----------------------------------------------------------------------
goto ON_ERROR

:BACKEND_HEALTHY
echo [OK] Engine backend is active and healthy.
echo.

:: ----------------------------------------------------------------------
:: 4. FRONTEND SERVER INITIALIZATION
:: ----------------------------------------------------------------------

echo [4/5] Initializing kiosk UI server...

:: Check port 5173 state: 0=free, 1=already healthy, 2=occupied by conflict
py -3.11 stage5_ui\check_port.py 5173 http://127.0.0.1:5173 "APS CHESS AI"
set PORT5173_STATE=%ERRORLEVEL%

if %PORT5173_STATE% equ 1 (
    echo [INFO] Existing healthy APS Chess AI frontend detected on port 5173.
    goto FRONTEND_HEALTHY
)

if %PORT5173_STATE% equ 2 (
    echo [ERROR] Port 5173 is occupied by an unrelated application.
    echo Please free port 5173 and try again.
    goto ON_ERROR
)

echo [INFO] Serving production build on http://127.0.0.1:5173...
echo [INFO] Startup logs redirected to: logs\frontend.log
type nul > logs\frontend.log
type nul > logs\frontend_err.log
powershell -NoProfile -Command "Start-Process -FilePath 'node' -ArgumentList 'stage5_ui\serve_production.cjs' -WindowStyle Minimized -RedirectStandardOutput 'logs\frontend.log' -RedirectStandardError 'logs\frontend_err.log'"

:: Wait for frontend readiness with timeout (20 seconds)
echo [INFO] Waiting for frontend server readiness...
set /a F_RETRIES=0

:WAIT_FRONTEND_LOOP
py -3.11 -c "import urllib.request; data = urllib.request.urlopen('http://127.0.0.1:5173/', timeout=1.5).read().decode(); assert 'APS CHESS AI' in data" >nul 2>&1
if %ERRORLEVEL% equ 0 goto FRONTEND_HEALTHY

if %F_RETRIES% geq 3 (
    findstr /C:"[ERROR]" logs\frontend.log logs\frontend_err.log >nul 2>&1
    if !ERRORLEVEL! equ 0 goto FRONTEND_CRASHED
)

set /a F_RETRIES+=1
if %F_RETRIES% geq 20 goto FRONTEND_TIMEOUT

ping -n 2 127.0.0.1 >nul
goto WAIT_FRONTEND_LOOP

:FRONTEND_CRASHED
echo.
echo [ERROR] Kiosk UI server failed during startup!
echo Frontend log output:
echo ----------------------------------------------------------------------
if exist logs\frontend.log type logs\frontend.log
if exist logs\frontend_err.log type logs\frontend_err.log
echo ----------------------------------------------------------------------
goto ON_ERROR

:FRONTEND_TIMEOUT
echo.
echo [ERROR] Frontend server startup timed out after 20 seconds!
echo Frontend log output:
echo ----------------------------------------------------------------------
if exist logs\frontend.log type logs\frontend.log
if exist logs\frontend_err.log type logs\frontend_err.log
echo ----------------------------------------------------------------------
goto ON_ERROR

:FRONTEND_HEALTHY
echo [OK] Kiosk UI server is active and ready.
echo.

:: ----------------------------------------------------------------------
:: 5. BROWSER LAUNCH
:: ----------------------------------------------------------------------

echo [5/5] Launching APS Chess AI in your browser...
start http://localhost:5173

echo.
echo ======================================================================
echo                APS CHESS AI IS READY FOR PLAY
echo                     http://localhost:5173
echo ======================================================================
echo Backend logs : logs\backend.log
echo Frontend logs: logs\frontend.log
echo.
echo You may minimize or close this window at any time.
ping -n 6 127.0.0.1 >nul
exit /b 0

:ON_ERROR
echo.
echo ======================================================================
echo                       STARTUP FAILED
echo ======================================================================
echo Please review the messages above.
echo Backend log : logs\backend.log
echo Frontend log: logs\frontend.log
echo.
pause
exit /b 1
