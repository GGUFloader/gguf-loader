#!/usr/bin/env python3
"""
Main entry point for the Advanced Local AI Chat Application
"""
import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from models.model_loader import ModelLoader
from utils import load_fonts
from ui.ai_chat_window import AIChat

def resource_path(relative_path: str) -> str:
    """Get absolute path for bundled resources, works for dev and PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def add_dll_folder():
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
        dll_path = os.path.join(base_path, "llama_cpp", "lib")
        os.add_dll_directory(dll_path)


def main():
    add_dll_folder()

    app = QApplication(sys.argv)

    # Set application icon for taskbar & alt-tab
    icon_path = resource_path("icon.ico")  # Adjust if your icon is elsewhere
    print(f"[DEBUG] Loading icon from: {icon_path}")
    app.setWindowIcon(QIcon(icon_path))

    # Load fonts
    load_fonts()

    # Create and show main window
    window = AIChat()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
    
