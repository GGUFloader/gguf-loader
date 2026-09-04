@echo off
title GGUF Loader
color 0A
echo ===============================================
echo    GGUF Loader - Local AI Workstation
echo ===============================================
echo.

REM ============================================
REM  Check system Python (needed to create venv)
REM ============================================
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo         Install Python 3.10+ and add to PATH.
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [OK] System Python %PYVER%

REM ============================================
REM  Create .venv if it doesn't exist
REM ============================================
if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment found.
)

REM Use venv Python from now on
set "PY=.venv\Scripts\python.exe"
set "PIP=.venv\Scripts\pip.exe"

REM ============================================
REM  Install/Update Python dependencies in venv
REM ============================================
if not exist "requirements.txt" goto :skip_requirements
%PY% -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing Python dependencies...
    %PIP% install -r requirements.txt -q
    if errorlevel 1 (
        echo [ERROR] Failed to install Python dependencies.
        pause
        exit /b 1
    )
    echo [OK] Python dependencies installed.
) else (
    echo [OK] Python dependencies ready.
)
:skip_requirements

REM ============================================
REM  Check Node.js
REM ============================================
node --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Node.js not found. Starting in production mode...
    goto :production
)

for /f %%i in ('node --version 2^>^&1') do set NODEVER=%%i
echo [OK] Node.js %NODEVER%

REM ============================================
REM  Check/Install frontend dependencies
REM ============================================
if not exist "frontend\node_modules" (
    echo [SETUP] Installing frontend dependencies...
    cd /d "%~dp0frontend"
    call npm install
    if errorlevel 1 (
        echo [ERROR] Failed to install frontend dependencies.
        cd /d "%~dp0"
        goto :production
    )
    cd /d "%~dp0"
    echo [OK] Frontend dependencies installed.
) else (
    echo [OK] Frontend dependencies ready.
)

REM ============================================
REM  Ask launch mode
REM ============================================
echo.
echo   Choose launch mode:
echo     [1] Browser  - Opens in your web browser (default)
echo     [2] Desktop  - Opens in Electron native window
echo     [3] Production - Built app, single server
echo.
set /p CHOICE="  Enter choice (1/2/3): "
if "%CHOICE%"=="" set CHOICE=1
if "%CHOICE%"=="2" goto :electron
if "%CHOICE%"=="3" goto :production
goto :development

REM ============================================
REM  Electron mode
REM ============================================
:electron
echo.
echo [ELECTRON] Starting desktop app...
echo.

REM Kill any existing backend on port 8000
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1

REM Check if Electron is compiled
if not exist "electron\dist\main.js" (
    echo [BUILD] Compiling Electron...
    cd /d "%~dp0electron"
    call npx tsc
    if errorlevel 1 (
        echo [ERROR] Electron compilation failed.
        echo         Falling back to browser mode.
        cd /d "%~dp0"
        goto :development
    )
    cd /d "%~dp0"
    echo [OK] Electron compiled.
)

REM Electron spawns and owns its own backend on :8000 (see electron/main.ts).
REM Do NOT pre-start one here - a second uvicorn would fail to bind :8000.
echo [1/1] Launching Electron window (Electron starts the backend itself)...
cd /d "%~dp0electron"
start "" node_modules\.bin\electron.cmd .
cd /d "%~dp0"

echo.
echo ===============================================
echo   GGUF Loader is running in Desktop mode!
echo.
echo   Backend: http://localhost:8000
echo   Frontend: http://localhost:5173 (Vite)
echo ===============================================
echo.
echo   Close this window or press Ctrl+C to stop.
echo.
pause >nul
echo Stopping all processes...
REM Kill backend (python/uvicorn on port 8000)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
REM Kill Vite dev server (node on port 5173)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
REM Kill any remaining GGUFLoader processes
taskkill /FI "WINDOWTITLE eq GGUFLoader-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GGUFLoader-Frontend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GGUFLoader-Electron*" /F >nul 2>&1
echo All processes stopped.
goto :end

REM ============================================
REM  Development mode (browser + vite)
REM ============================================
:development
echo.
echo [DEV] Starting in development mode...
echo.

REM Kill any existing backend on port 8000
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1

echo [1/3] Starting backend (FastAPI on :8000)...
start "GGUFLoader-Backend" cmd /c "cd /d "%~dp0" && .venv\Scripts\python.exe -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --reload"

REM Wait for backend
echo [2/3] Waiting for backend to be ready...
timeout /t 4 /nobreak >nul

REM Quick health check
curl -s http://localhost:8000/api/health >nul 2>&1
if errorlevel 1 (
    echo [WARN] Backend may not be ready yet, continuing anyway...
)

echo [3/3] Starting frontend (Vite on :5173)...
start "GGUFLoader-Frontend" cmd /c "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ===============================================
echo   GGUF Loader is running!
echo.
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo ===============================================
echo.
echo   Close this window to keep servers running.
echo   Or press any key to stop both servers.
echo.
pause >nul

REM Kill all processes on exit
echo Stopping all processes...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GGUFLoader-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GGUFLoader-Frontend*" /F >nul 2>&1
echo All processes stopped.
goto :end

REM ============================================
REM  Production mode (built frontend only)
REM ============================================
:production
echo.
echo [PROD] Starting in production mode...
echo.

REM Kill any existing backend on port 8000
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1

REM Build frontend if missing OR stale (any frontend\src file newer than
REM dist\index.html) - otherwise production mode silently serves an old UI.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=Get-ChildItem 'frontend\src' -Recurse -File -ErrorAction SilentlyContinue|Sort-Object LastWriteTime -Descending|Select-Object -First 1; $d=Get-Item 'frontend\dist\index.html' -ErrorAction SilentlyContinue; if (-not $d -or ($s -and $s.LastWriteTime -gt $d.LastWriteTime)) { exit 1 } else { exit 0 }" >nul 2>&1
if errorlevel 1 (
    echo [BUILD] Building frontend (missing or source newer than dist)...
    if not exist "frontend\node_modules" (
        cd /d "%~dp0frontend"
        call npm install
        cd /d "%~dp0"
    )
    cd /d "%~dp0frontend"
    call npm run build
    cd /d "%~dp0"
    if errorlevel 1 (
        echo [ERROR] Frontend build failed.
        pause
        exit /b 1
    )
    echo [OK] Frontend built.
)

echo [START] Starting server (serves frontend + API on :8000)...
echo.
echo ===============================================
echo   GGUF Loader is running!
echo.
echo   App:  http://localhost:8000
echo   API:  http://localhost:8000/docs
echo ===============================================
echo.
.venv\Scripts\python.exe -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --host 0.0.0.0
echo.
echo Server stopped.
pause

:end
