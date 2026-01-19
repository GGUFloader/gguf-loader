#!/bin/bash

# GGUF Loader Launcher Script
# This script will create a virtual environment if it doesn't exist,
# install dependencies, and launch the application.

# Set the name of the virtual environment
VENV_NAME="venv"

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

# Check if requirements are installed by trying to import a key module
python -c "import PySide6" >/dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt || error_exit "Failed to install dependencies."
else
    echo "Dependencies already installed."
fi

# Launch the application
echo "Starting GGUF Loader..."
python gguf_loader_main.py || error_exit "Failed to start the application."

# Deactivate virtual environment when done
deactivate