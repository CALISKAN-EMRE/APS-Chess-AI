@echo off
setlocal enabledelayedexpansion

echo ======================================================================
echo                APS CHESS AI - KIOSK STAND LAUNCHER
echo              Developed by the APS Machine Learning Team
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Check Python 3.11 availability
py -3.11 --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.11 is required but was not found via 'py -3.11'.
    echo Please install Python 3.11 and ensure it is registered in the Python launcher.
    pause
    exit /b 1
)

:: 2. Check Node.js availability
cmd.exe /c "node --version" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js is required but was not found on PATH.
    echo Please install Node.js (v20+ recommended).
    pause
    exit /b 1
)

:: 3. Check if backend is already running on port 8000
set BACKEND_RUNNING=0
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [INFO] Backend is already active on port 8000.
    set BACKEND_RUNNING=1
) else (
    echo [INFO] Starting APS Deep Value Engine backend on port 8000...
    start "APS Chess AI - Backend (Port 8000)" /min py -3.11 -m uvicorn stage5_ui.backend.main:app --host 127.0.0.1 --port 8000
)

:: 4. Wait for backend health readiness
echo [INFO] Waiting for engine backend readiness...
:WAIT_HEALTH
powershell -NoProfile -Command "(Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2 -ErrorAction SilentlyContinue).status" 2>nul | findstr "healthy" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    timeout /t 1 /nobreak >nul
    goto WAIT_HEALTH
)
echo [OK] Backend is healthy and engine is warmed up!

:: 5. Check if frontend is already running on port 5173
set FRONTEND_RUNNING=0
netstat -ano | findstr /R /C:":5173 .*LISTENING" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [INFO] Frontend server is already active on port 5173.
    set FRONTEND_RUNNING=1
) else (
    echo [INFO] Starting APS Chess AI Kiosk UI on port 5173...
    pushd stage5_ui\frontend
    if not exist node_modules (
        echo [INFO] Installing frontend dependencies...
        cmd.exe /c npm install
    )
    start "APS Chess AI - Frontend (Port 5173)" /min cmd.exe /c npm run dev
    popd
)

:: 6. Wait for frontend readiness
echo [INFO] Waiting for frontend server...
:WAIT_FRONTEND
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://localhost:5173' -TimeoutSec 2 -UseBasicParsing).StatusCode } catch { 0 }" 2>nul | findstr "200" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    timeout /t 1 /nobreak >nul
    goto WAIT_FRONTEND
)
echo [OK] Frontend is ready!

:: 7. Launch browser
echo [INFO] Opening APS Chess AI Stand in browser...
start http://localhost:5173

echo.
echo ======================================================================
echo APS Chess AI is now running at: http://localhost:5173
echo Close this window at any time.
echo ======================================================================
timeout /t 3 /nobreak >nul
exit /b 0
