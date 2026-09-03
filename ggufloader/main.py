#!/usr/bin/env python3
"""
GGUF Loader - Application entry point.

Supports two modes:
  1. React/FastAPI mode (default): Launches the Python backend + serves React UI
  2. PySide6 mode (--qt flag): Launches the original Qt desktop UI

Set GGUFLOADER_UI=react or GGUFLOADER_UI=qt to override auto-detection.
"""

import logging
import os
import platform
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_library_path() -> None:
    """Add the llama.cpp DLL/library directory to the process search path."""
    try:
        from ggufloader.resource_manager import get_dll_path
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
    from ggufloader import __version__
    print(f"GGUF Loader version {__version__}")


def _print_help() -> None:
    print("GGUF Loader - Advanced GGUF Model Loader")
    print("\nUsage: python main.py [options]")
    print("\nOptions:")
    print("  --version, -v    Show version information")
    print("  --help, -h       Show this help message")
    print("  --qt             Launch with PySide6 desktop UI (legacy)")
    print("  --react          Launch with React web UI (default)")
    print("  --port PORT      Backend port (default: 8000)")
    print("  --no-browser     Don't open browser automatically")


def _detect_ui_mode() -> str:
    """Detect which UI mode to use."""
    env_mode = os.environ.get("GGUFLOADER_UI", "").lower()
    if env_mode in ("react", "web"):
        return "react"
    if env_mode in ("qt", "pyside6"):
        return "qt"

    # The React web UI is the documented default (see --help); the Qt
    # desktop UI stays available on request via --qt / GGUFLOADER_UI=qt.
    return "react"


def _launch_react(port: int = 8000, open_browser: bool = True) -> int:
    """Launch the React/FastAPI backend."""
    import threading
    import time

    logger.info("Starting GGUF Loader in React mode on port %d", port)

    # Start FastAPI in background thread
    def run_server():
        import uvicorn
        uvicorn.run(
            "ggufloader.api.app:create_app",
            factory=True,
            host="127.0.0.1",
            port=port,
            log_level="info",
        )

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    import socket
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                break
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    else:
        logger.error("Backend server failed to start")
        return 1

    url = f"http://localhost:{port}"
    logger.info("Backend ready at %s", url)

    if open_browser:
        import webbrowser
        webbrowser.open(url)
        logger.info("Opened browser at %s", url)

    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        return 0


def _launch_qt() -> int:
    """Launch the PySide6 desktop UI."""
    try:
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
    except ImportError:
        logger.error("PySide6 is not installed. Install it with: pip install PySide6")
        return 1

    from ggufloader.resource_manager import find_config_dir, find_icon, find_logs_dir

    from ggufloader import __version__

    app = QApplication(sys.argv)
    app.setApplicationName("GGUF Loader")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("GGUF Loader Team")

    icon_path = find_icon("icon.ico")
    if os.path.exists(icon_path):
        icon = QIcon(icon_path)
        if not icon.isNull():
            app.setWindowIcon(icon)

    # File logging
    try:
        from ggufloader.logging_setup import setup_file_logging
        log_file = setup_file_logging(find_logs_dir())
        logger.info("Logging to %s", log_file)
    except Exception as e:  # noqa: BLE001
        print(f"File logging unavailable: {e}")

    from ggufloader.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    return app.exec()


def main() -> int:
    # Parse arguments
    port = 8000
    open_browser = True
    ui_override = None

    args = sys.argv[1:]
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] in ("--version", "-v"):
            _print_version()
            return 0
        elif args[i] in ("--help", "-h"):
            _print_help()
            return 0
        elif args[i] == "--qt":
            ui_override = "qt"
        elif args[i] == "--react":
            ui_override = "react"
        elif args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 1
        elif args[i] == "--no-browser":
            open_browser = False
        else:
            filtered_args.append(args[i])
        i += 1

    sys.argv = [sys.argv[0]] + filtered_args

    setup_library_path()

    mode = ui_override or _detect_ui_mode()
    logger.info("UI mode: %s", mode)

    if mode == "react":
        return _launch_react(port=port, open_browser=open_browser)
    else:
        return _launch_qt()


if __name__ == "__main__":
    sys.exit(main())
