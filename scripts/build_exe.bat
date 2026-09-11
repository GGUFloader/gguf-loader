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

REM Detect the build variant from the installed llama-cpp-python wheel BEFORE
REM the build: the spec needs GGUFLOADER_CUDA to know whether to keep the CUDA
REM runtime, and it refuses to build a CPU bundle from a CUDA wheel (that
REM wheel's llama.dll cannot load without ggml-cuda.dll, so the exe would
REM crash at startup with no UI).
set "VARIANT=CPU"
set "GGUFLOADER_CUDA=0"
if exist ".venv\Lib\site-packages\llama_cpp\lib\ggml-cuda.dll" (
    set "VARIANT=GPU"
    set "GGUFLOADER_CUDA=1"
)

REM Resolve the app version and the final artifact name up front, so %VARIABLE%
REM values are set before the success block below is parsed (cmd expands %VARS%
REM at parse time inside parenthesized blocks).
set "VERSION="
for /f "tokens=2 delims== " %%V in ('findstr /B "__version__" ggufloader\_version.py') do set "VERSION=%%V"
set "VERSION=%VERSION:"=%"
set "FINAL_NAME=GGUFLoader_v%VERSION%_%VARIANT%.exe"

REM Clean previous builds. Keep other dist artifacts (GPU/CPU variant exes,
REM wheels, Linux binaries) - only remove this build's stale output.
echo.
echo [3/4] Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist\GGUFLoader_WithAddons.exe" del /q "dist\GGUFLoader_WithAddons.exe"
if exist "dist\GGUFLoader_WithAddons_GPU.exe" del /q "dist\GGUFLoader_WithAddons_GPU.exe"

REM Build executable
echo.
echo [4/4] Building %VARIANT% executable...
pyinstaller build_exe.spec

REM Check if build was successful. The spec names the CUDA build with a _GPU
REM suffix, so rename from whichever file this variant produced.
set "BUILT=dist\GGUFLoader_WithAddons.exe"
if "%VARIANT%"=="GPU" set "BUILT=dist\GGUFLoader_WithAddons_GPU.exe"
if exist "%BUILT%" (
    move /y "%BUILT%" "dist\%FINAL_NAME%" >nul

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
    echo File size: CPU-only ~145MB, GPU ~930MB (CUDA runtime included)
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
