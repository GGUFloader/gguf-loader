"""
LauncherService - Brings the shell launcher scripts into the app.

Every entry mirrors a script in ``scripts/`` (GPU install, GPU monitor,
GPU verification, EXE build). ``launch_script`` opens the matching script
in a new console window on Windows (``cmd /k``) or a terminal emulator on
POSIX, falling back to a detached background run. This is fire-and-forget
— no worker thread is needed and the app never blocks.

Not a QObject service: nothing here is long-running or signal-based. See
``EnvironmentService`` for the pip/venv installer, which is threaded.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# key -> (label, windows .bat, posix .sh, python script)
_CATALOG = [
    ("gpu_install", "Install GPU Support", "install_gpu_llama.bat", "install_gpu_llama.sh", None),
    ("gpu_source", "Install GPU (Source)", "install_gpu_llama_source.bat", "install_gpu_llama_source.sh", None),
    ("gpu_verify", "Verify GPU Support", None, None, "verify_gpu_support.py"),
    ("gpu_monitor", "Monitor GPU", "monitor_gpu.bat", None, None),
    ("build_exe", "Build EXE", "build_exe.bat", None, None),
]


def available_scripts() -> list[tuple[str, str]]:
    """``[(key, label)]`` for the scripts that exist on this platform."""
    result: list[tuple[str, str]] = []
    for key, label, bat, sh, py in _CATALOG:
        if py is not None and (SCRIPTS_DIR / py).exists():
            result.append((key, label))
        elif os.name == "nt" and bat is not None and (SCRIPTS_DIR / bat).exists():
            result.append((key, label))
        elif os.name != "nt" and sh is not None and (SCRIPTS_DIR / sh).exists():
            result.append((key, label))
    return result


def _windows_command(entry: tuple) -> Optional[list[str]]:
    _, _, bat, _, py = entry
    if py is not None and (SCRIPTS_DIR / py).exists():
        return ["cmd", "/k", sys.executable, str(SCRIPTS_DIR / py)]
    if bat is not None and (SCRIPTS_DIR / bat).exists():
        return ["cmd", "/k", str(SCRIPTS_DIR / bat)]
    return None


def _posix_command(entry: tuple) -> Optional[list[str]]:
    _, _, _, sh, py = entry
    if py is not None and (SCRIPTS_DIR / py).exists():
        target = [sys.executable, str(SCRIPTS_DIR / py)]
    elif sh is not None and (SCRIPTS_DIR / sh).exists():
        target = ["bash", str(SCRIPTS_DIR / sh)]
    else:
        return None
    for terminal in ("x-terminal-emulator", "gnome-terminal", "konsole",
                     "xfce4-terminal", "mate-terminal", "xterm"):
        if shutil.which(terminal):
            return [terminal, "-e"] + target
    return target  # fallback: detached background run


def launch_script(key: str) -> tuple[bool, str]:
    """Open the script for *key* in a console window. Returns (ok, error)."""
    entry = next((e for e in _CATALOG if e[0] == key), None)
    if entry is None:
        return False, f"unknown launcher '{key}'"

    if os.name == "nt":
        command = _windows_command(entry)
        kwargs = {"creationflags": subprocess.CREATE_NEW_CONSOLE}
    else:
        command = _posix_command(entry)
        kwargs = {"start_new_session": True}

    if command is None:
        return False, f"'{entry[1]}' is not available on this platform"

    try:
        subprocess.Popen(command, cwd=str(PROJECT_ROOT), **kwargs)
        return True, ""
    except OSError as e:
        return False, str(e)
