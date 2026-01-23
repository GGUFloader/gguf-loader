@echo off
REM Build script for creating GGUF Loader executable on Windows (WITH ADDON SUPPORT)

echo ========================================
echo GGUF Loader - Executable Builder
echo WITH ADDON SUPPORT (Floating Chat)
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv venv
    echo Then activate it and install requirements
    pause
    exit /b 1
)

REM Activate virtual environment
echo [1/4] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install PyInstaller if not already installed
echo.
echo [2/4] Installing PyInstaller...
pip install pyinstaller

REM Clean previous builds
echo.
echo [3/4] Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Build executable
echo.
echo [4/4] Building executable...
pyinstaller build_exe.spec

REM Check if build was successful
if exist "dist\GGUFLoader_WithAddons.exe" (
    echo.
    echo ========================================
    echo BUILD SUCCESSFUL!
    echo ========================================
    echo.
    echo Your SINGLE EXECUTABLE file is located at:
    echo dist\GGUFLoader_WithAddons.exe
    echo.
    echo This is a STANDALONE executable that includes:
    echo - Full GGUF Loader functionality
    echo - Addon system support
    echo - Floating Chat addon
    echo - All Python dependencies
    echo - All DLL files
    echo - No installation required!
    echo.
    echo Just share this ONE file - users can run it directly!
    echo File size: Large (100-300 MB) but completely portable
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
