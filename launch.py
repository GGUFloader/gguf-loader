#!/usr/bin/env python3
"""
Robust launcher script for GGUF Loader
"""
import sys
import os

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def main():
    try:
        # Try to import and run the main application
        from gguf_loader_main import main as app_main
        app_main()
    except ImportError as e:
        print(f"Import error: {e}")
        print("Trying alternative approach...")
        try:
            # Alternative: try running the basic version
            from main import main as basic_main
            basic_main()
        except ImportError as e2:
            print(f"Alternative import error: {e2}")
            print("Please check that all dependencies are installed:")
            print("pip install PySide6 llama-cpp-python pyautogui pyperclip pywin32")
            sys.exit(1)

if __name__ == "__main__":
    main()