@echo off
title GGUF Loader
color 0A
echo ===============================================
echo    GGUF Loader - Local AI Workstation
echo ===============================================
echo.

REM ============================================
REM  Check Python
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
echo [OK] Python %PYVER%

REM ============================================
REM  Check/Install Python dependencies
REM ============================================
if not exist "requirements.txt" goto :skip_requirements
python -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing Python dependencies...
    pip install -r requirements.txt -q
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

REM Start backend first
echo [1/2] Starting backend (FastAPI on :8000)...
start "GGUFLoader-Backend" cmd /c "cd /d "%~dp0" && python -m uvicorn ggufloader.api.app:create_app --factory --port 8000"
timeout /t 3 /nobreak >nul

REM Launch Electron
echo [2/2] Launching Electron window...
start "GGUFLoader-Electron" cmd /c "cd /d "%~dp0electron" && npx electron ."

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
taskkill /FI "WINDOWTITLE eq GGUFLoader-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GGUFLoader-Frontend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GGUFLoader-Electron*" /F >nul 2>&1
echo Servers stopped.
goto :end

REM ============================================
REM  Development mode (browser + vite)
REM ============================================
:development
echo.
echo [DEV] Starting in development mode...
echo.

echo [1/3] Starting backend (FastAPI on :8000)...
start "GGUFLoader-Backend" cmd /c "cd /d "%~dp0" && python -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --reload"

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

REM Kill both servers on exit
taskkill /FI "WINDOWTITLE eq GGUFLoader-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GGUFLoader-Frontend*" /F >nul 2>&1
echo Servers stopped.
goto :end

REM ============================================
REM  Production mode (built frontend only)
REM ============================================
:production
echo.
echo [PROD] Starting in production mode...
echo.

REM Build frontend if needed
if not exist "frontend\dist\index.html" (
    echo [BUILD] Building frontend...
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
python -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --host 0.0.0.0
echo.
echo Server stopped.
pause

:end
