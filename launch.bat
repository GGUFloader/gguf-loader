@echo off
REM GGUF Loader Launcher Script
REM This script will create a virtual environment if it doesn't exist,
REM verify that every dependency from requirements.txt is installed,
REM install anything that's missing, and then launch the application.

REM Change to the project root so relative paths work from anywhere
cd /d "%~dp0"

REM Set the name of the virtual environment
set VENV_NAME=.venv

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

REM Verify that every requirement in requirements.txt is installed
python -c "import importlib.metadata,re,sys; norm=lambda n: re.sub(r'[-_.]+','_',n).lower(); installed={norm(d.metadata.get('Name','')) for d in importlib.metadata.distributions()}; missing=[re.split(r'[<>=!~;\[ ]',l.split('#',1)[0].strip(),maxsplit=1)[0].strip() for l in open('requirements.txt',encoding='utf-8') if l.split('#',1)[0].strip()]; missing=[n for n in missing if n and norm(n) not in installed]; print(('Missing: '+', '.join(missing)) if missing else 'All dependencies are installed.'); sys.exit(1 if missing else 0)"

if errorlevel 1 (
    echo Installing dependencies...
    pip install --disable-pip-version-check -r requirements.txt

    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    echo Dependencies already installed.
)

REM Launch the application
echo Starting GGUF Loader...
python main.py

if errorlevel 1 (
    echo Failed to start the application.
    pause
    exit /b 1
)

REM Deactivate virtual environment when done
call deactivate
