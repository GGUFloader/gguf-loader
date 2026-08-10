@echo off
REM Build script for creating GGUF Loader executable on Windows (WITH ADDON SUPPORT)
REM Change to the project root so relative paths work from anywhere
cd /d "%~dp0.."

echo ========================================
echo GGUF Loader - Executable Builder
echo WITH ADDON SUPPORT (Floating Chat)
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv .venv
    echo Then activate it and install requirements
    pause
    exit /b 1
)

REM Activate virtual environment
echo [1/4] Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install PyInstaller if not already installed
echo.
echo [2/4] Installing PyInstaller...
pip install pyinstaller

REM Clean previous builds. Keep other dist artifacts (GPU/CPU variant exes,
REM wheels, Linux binaries) - only remove this build's stale output.
echo.
echo [3/4] Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist\GGUFLoader_WithAddons.exe" del /q "dist\GGUFLoader_WithAddons.exe"

REM Build executable
echo.
echo [4/4] Building executable...
pyinstaller build_exe.spec

REM Resolve the app version and the GPU/CPU variant BEFORE the success block
REM below, so %VARIABLE% values are set before that block is parsed (cmd
REM expands %VARS% at parse time inside parenthesized blocks).
set "VARIANT=CPU"
if exist ".venv\Lib\site-packages\llama_cpp\lib\ggml-cuda.dll" set "VARIANT=GPU"
set "VERSION="
for /f "tokens=2 delims== " %%V in ('findstr /B "__version__" ggufloader\_version.py') do set "VERSION=%%V"
set "VERSION=%VERSION:"=%"
set "FINAL_NAME=GGUFLoader_v%VERSION%_%VARIANT%.exe"

REM Check if build was successful
if exist "dist\GGUFLoader_WithAddons.exe" (
    move /y "dist\GGUFLoader_WithAddons.exe" "dist\%FINAL_NAME%" >nul

    echo.
    echo ========================================
    echo BUILD SUCCESSFUL!
    echo ========================================
    echo.
    echo Your SINGLE EXECUTABLE file is located at:
    echo dist\%FINAL_NAME%
    echo.
    echo This is a STANDALONE %VARIANT%-only executable that includes:
    echo - Full GGUF Loader functionality
    echo - Addon system support
    echo - Floating Chat addon
    echo - All Python dependencies
    echo - All DLL files
    echo - No installation required
    echo.
    echo Just share this ONE file - users can run it directly
    echo File size: CPU-only ~70MB, GPU ~850MB (CUDA runtime included)
    echo.
) else (
    echo.
    echo ========================================
    echo BUILD FAILED!
    echo ========================================
    echo Please check the error messages above.
    echo.
)

pause
