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
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _show_error_dialog(message: str) -> None:
    """Surface a fatal startup error to the user.

    When the app is frozen as a windowed (console-less) exe and the user
    double-clicks it, a crash would otherwise exit silently - "nothing
    happens". The launcher shim routes stdout/stderr to devnull (uvicorn
    needs real streams), so ``sys.stderr is None`` can no longer gate the
    dialog: show the native message box for EVERY frozen Windows failure.
    Print too, so terminal launches and redirected logs still get the
    traceback.
    """
    try:
        print(message, file=sys.stderr if sys.stderr is not None else sys.__stderr__)
    except Exception:  # noqa: BLE001 - printing must never be the crash
        pass
    try:
        if os.name == "nt" and getattr(sys, "frozen", False):
            import ctypes

            # MB_ICONERROR = 0x10; always-on-top so it is not missed.
            ctypes.windll.user32.MessageBoxW(
                None, message, "GGUF Loader - Error", 0x10 | 0x40000
            )
    except Exception:  # noqa: BLE001 - the dialog must never be the crash
        pass


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
                logger.info("Added to %s: %s", env_var, components)
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

    # Capture crashes from the server thread so a windowed exe can show
    # them instead of dying silently (uvicorn swallows the traceback into
    # logging, and with no console there is nothing to log to).
    server_error: list[BaseException] = []

    # Start FastAPI in background thread
    def run_server():
        try:
            import uvicorn
            uvicorn.run(
                "ggufloader.api.app:create_app",
                factory=True,
                host="127.0.0.1",
                port=port,
                log_level="info",
            )
        except BaseException as exc:  # noqa: BLE001 - reported below
            server_error.append(exc)
            logger.exception("Backend server crashed")

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
        if server_error:
            tb = "".join(
                traceback.format_exception(
                    type(server_error[0]), server_error[0], server_error[0].__traceback__
                )
            )
            _show_error_dialog(
                f"GGUF Loader failed to start (backend on port {port}):\n\n{tb}"
            )
        else:
            _show_error_dialog(
                f"GGUF Loader failed to start: the backend on port {port} did not "
                "become ready. Another application may be using that port - "
                "close it or start GGUF Loader with:  --port 8010"
            )
        return 1

    url = f"http://localhost:{port}"
    logger.info("Backend ready at %s", url)

    if open_browser:
        _open_ui(url)

    # Keep running (the server is in a daemon thread; main must stay alive)
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        return 0


def _open_ui(url: str) -> None:
    """Open the UI in Electron (frozen) or a browser (dev)."""
    if getattr(sys, "frozen", False):
        # Frozen exe: launch the bundled Electron standalone launcher
        import subprocess
        electron_dir = os.path.join(sys._MEIPASS, "electron")
        electron_exe = os.path.join(electron_dir, "electron.exe")
        if os.path.isfile(electron_exe):
            logger.info("Launching Electron: %s", electron_exe)
            subprocess.Popen(
                [electron_exe, electron_dir, f"--url={url}"],
                cwd=electron_dir,
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        else:
            # Electron not bundled (e.g. CI build without Electron) - fall back
            logger.warning("Electron not found at %s, opening in browser", electron_exe)
            import webbrowser
            webbrowser.open(url)
    else:
        import webbrowser
        webbrowser.open(url)
        logger.info("Opened browser at %s", url)


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


def run() -> int:
    """Entry wrapper: turn any fatal startup error into a visible dialog."""
    try:
        return main()
    except SystemExit:
        raise
    except BaseException:
        _show_error_dialog(
            "GGUF Loader failed to start:\n\n" + traceback.format_exc()
        )
        return 1


if __name__ == "__main__":
    sys.exit(run())
