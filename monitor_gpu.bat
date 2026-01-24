@echo off
echo Monitoring GPU usage in real-time...
echo Press Ctrl+C to stop
echo.
echo Watch the "GPU-Util" column - it should increase when generating responses
echo.

:loop
nvidia-smi --query-gpu=timestamp,name,utilization.gpu,utilization.memory,memory.used,memory.total --format=csv
timeout /t 1 /nobreak > nul
cls
goto loop
