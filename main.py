#!/usr/bin/env python3
"""
GGUF Loader - Application entry point.

Bootstrap only: configure logging, set up the llama.cpp library path,
create the QApplication and show the MainWindow. All application logic
lives in core/, services/ and ui/.
"""

import logging
import os
import platform
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from resource_manager import find_icon, get_dll_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_library_path() -> None:
    """Add the llama.cpp DLL/library directory to the process search path."""
    try:
        dll_path = get_dll_path()
        if not dll_path or not os.path.exists(dll_path):
            return

        system = platform.system()
        if system == "Windows" and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(dll_path)
            logger.info("Added Windows DLL directory: %s", dll_path)
        elif system == "Linux":
            env_var = "LD_LIBRARY_PATH"
            components = os.environ.get(env_var, "").split(os.pathsep)
            if dll_path not in components:
                os.environ[env_var] = os.pathsep.join([dll_path, *components])
                logger.info("Added to %s: %s", env_var, dll_path)
        elif system == "Darwin":
            env_var = "DYLD_LIBRARY_PATH"
            components = os.environ.get(env_var, "").split(os.pathsep)
            if dll_path not in components:
                os.environ[env_var] = os.pathsep.join([dll_path, *components])
                logger.info("Added to %s: %s", env_var, dll_path)
    except Exception as e:  # noqa: BLE001 - never block startup on this
        logger.warning("Could not set up library path: %s", e)


def _print_version() -> None:
    from __init__ import __version__
    print(f"GGUF Loader version {__version__}")


def _print_help() -> None:
    print("GGUF Loader - Advanced GGUF Model Loader")
    print("\nUsage: python main.py [options]")
    print("\nOptions:")
    print("  --version, -v    Show version information")
    print("  --help, -h       Show this help message")


def main() -> int:
    if len(sys.argv) > 1:
        if sys.argv[1] in ("--version", "-v"):
            _print_version()
            return 0
        if sys.argv[1] in ("--help", "-h"):
            _print_help()
            return 0

    setup_library_path()

    app = QApplication(sys.argv)
    app.setApplicationName("GGUF Loader")
    app.setApplicationVersion("2.0.1")
    app.setOrganizationName("GGUF Loader Team")

    icon_path = find_icon("icon.ico")
    if os.path.exists(icon_path):
        icon = QIcon(icon_path)
        if not icon.isNull():
            app.setWindowIcon(icon)

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
