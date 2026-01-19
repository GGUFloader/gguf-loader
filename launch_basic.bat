@echo off
REM GGUF Loader Basic Launcher Script
REM This script will create a virtual environment if it doesn't exist,
REM install dependencies, and launch the basic application.

REM Set the name of the virtual environment
set VENV_NAME=venv

REM Check if virtual environment exists
if not exist "%VENV_NAME%\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv %VENV_NAME%
    
    if errorlevel 1 (
        echo Failed to create virtual environment. Please ensure Python is installed.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call %VENV_NAME%\Scripts\activate.bat

if errorlevel 1 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Check if requirements are installed by trying to import a key module
python -c "import PySide6" >nul 2>&1

if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    echo Dependencies already installed.
)

REM Launch the basic application
echo Starting GGUF Loader Basic...
python main.py

if errorlevel 1 (
    echo Failed to start the application.
    pause
    exit /b 1
)

REM Deactivate virtual environment when done
call deactivate