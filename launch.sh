#!/bin/bash

# GGUF Loader Launcher Script
# This script will create a virtual environment if it doesn't exist,
# verify that every dependency from requirements.txt is installed,
# install anything that's missing, and then launch the application.

# Change to the project root so relative paths work from anywhere
cd "$(dirname "$0")"

# Set the name of the virtual environment
VENV_NAME=".venv"

# Function to print error messages and exit
error_exit() {
    echo "Error: $1" >&2
    exit 1
}

# Check if virtual environment exists
if [ ! -f "$VENV_NAME/bin/activate" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_NAME" || error_exit "Failed to create virtual environment. Please ensure Python is installed."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_NAME/bin/activate" || error_exit "Failed to activate virtual environment."

# Verify that every requirement in requirements.txt is installed
python - <<'PY'
import importlib.metadata
import re
import sys


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


installed = {
    normalize(dist.metadata.get("Name", ""))
    for dist in importlib.metadata.distributions()
}

missing = []
with open("requirements.txt", encoding="utf-8") as fh:
    for raw in fh:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name = re.split(r"[<>=!~;\[ ]", line, maxsplit=1)[0].strip()
        if name and normalize(name) not in installed:
            missing.append(name)

if missing:
    print("Missing dependencies: " + ", ".join(missing))
    sys.exit(1)
print("All dependencies are installed.")
PY

if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip install --disable-pip-version-check -r requirements.txt || error_exit "Failed to install dependencies."
else
    echo "Dependencies already installed."
fi

# Launch the application
echo "Starting GGUF Loader..."
python main.py || error_exit "Failed to start the application."

# Deactivate virtual environment when done
deactivate
