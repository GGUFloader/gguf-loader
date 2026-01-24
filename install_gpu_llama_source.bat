@echo off
echo Building llama-cpp-python from source with CUDA support...
echo This requires Visual Studio Build Tools and CUDA Toolkit installed
echo.

REM Activate virtual environment
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
) else (
    echo ERROR: Virtual environment not found at venv\Scripts\activate.bat
    echo Please create a virtual environment first or run from the correct directory
    pause
    exit /b 1
)

echo.
echo Uninstalling existing version...
pip uninstall -y llama-cpp-python

echo.
echo Building from source with CUDA support (this may take 5-10 minutes)...
set CMAKE_ARGS=-DGGML_CUDA=on
set FORCE_CMAKE=1

pip install llama-cpp-python --no-cache-dir --force-reinstall

echo.
echo Build complete!
echo.
echo To verify GPU support, run: python verify_gpu_support.py
pause
