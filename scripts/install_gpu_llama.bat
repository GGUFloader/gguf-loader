@echo off
cd /d "%~dp0.."
echo Installing GPU-enabled llama-cpp-python...
echo.

REM Activate virtual environment
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo Virtual environment activated
) else (
    echo ERROR: Virtual environment not found at .venv\Scripts\activate.bat
    echo Please create a virtual environment first or run from the correct directory
    pause
    exit /b 1
)

echo.
echo Uninstalling existing CPU version...
pip uninstall -y llama-cpp-python

echo.
echo Installing GPU version with CUDA support (prebuilt wheel)...
pip install llama-cpp-python==0.3.34 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: GPU install failed.
    echo.
    echo Possible causes:
    echo   - No internet connection (cannot reach the download server)
    echo   - The CUDA wheel server may be temporarily down, try again later
    echo.
)

echo.
echo To verify GPU support, run: python scripts/verify_gpu_support.py
pause
