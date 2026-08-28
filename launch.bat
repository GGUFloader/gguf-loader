@echo off
title GGUF Loader
echo ================================
echo    GGUF Loader - Starting...
echo ================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

REM Check if Node.js is available (for development mode)
node --version >nul 2>&1
if errorlevel 1 (
    goto :production_mode
)

REM Development mode: check if frontend is built
if exist "frontend\dist\index.html" (
    goto :dev_mode
) else (
    goto :production_mode
)

:dev_mode
echo [DEV] Starting in development mode...
echo.

REM Start FastAPI backend
echo [1/3] Starting backend server...
start "GGUFLoader-Backend" cmd /c "cd /d %~dp0 && python -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --reload"

REM Wait for backend to be ready
echo [2/3] Waiting for backend...
timeout /t 3 /nobreak >nul

REM Start Vite dev server
echo [3/3] Starting frontend dev server...
start "GGUFLoader-Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

echo.
echo ================================
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:5173
echo ================================
echo.
echo Close this window or press Ctrl+C to stop.
pause
goto :end

:production_mode
echo [PROD] Starting in production mode...
echo.

REM Build frontend if needed
if not exist "frontend\dist\index.html" (
    echo Building frontend...
    cd /d %~dp0frontend
    call npm install
    call npm run build
    cd /d %~dp0
)

REM Start FastAPI backend (serves built frontend)
echo Starting server...
python -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --host 0.0.0.0

echo.
echo Server stopped.
pause
goto :end

:end
