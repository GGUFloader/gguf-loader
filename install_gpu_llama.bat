@echo off
echo Installing GPU-enabled llama-cpp-python...
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
echo Uninstalling existing CPU version...
pip uninstall -y llama-cpp-python

echo.
echo Installing GPU version with CUDA support...
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124

echo.
echo Installation complete!
echo.
echo To verify GPU support, run: python verify_gpu_support.py
pause
