"""
EnvironmentService - Launcher for the app's venv and dependencies.

Replicates what ``launch.bat`` does from the shell, but inside the
app: it reports whether the app is running from ``.venv`` and which packages
from ``requirements.txt`` are missing, then runs ``pip install`` (or a full
``python -m venv`` bootstrap) in a worker thread, streaming pip output to
the UI. Long-running work follows the services worker pattern (QObject +
QThread, zero-arg ``@Slot()``, args as attributes).
"""

from __future__ import annotations

import importlib.metadata
import logging
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot
from shiboken6 import isValid

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"
VENV_DIR = PROJECT_ROOT / ".venv"


# ---------------------------------------------------------------------------
# Pure helpers (no Qt) — unit testable in isolation
# ---------------------------------------------------------------------------
def _normalize(name: str) -> str:
    """Normalize a distribution name: 'Llama-Cpp-Python' -> 'llama_cpp_python'."""
    return re.sub(r"[-_.]+", "_", name).lower()


def parse_requirements(path: Path) -> list[str]:
    """Extract bare package names from a requirements file (version specs stripped)."""
    names: list[str] = []
    if not path.exists():
        return names
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip()
        if name:
            names.append(name)
    return names


def installed_distributions() -> set[str]:
    """Set of normalized names of every distribution installed in this interpreter."""
    dists: set[str] = set()
    try:
        for dist in importlib.metadata.distributions():
            name = dist.metadata.get("Name", "") or ""
            if name:
                dists.add(_normalize(name))
    except Exception:  # pragma: no cover - defensive
        logger.warning("Could not enumerate installed distributions", exc_info=True)
    return dists


def venv_python_path() -> Optional[str]:
    """Path to the .venv interpreter, or None if the venv has not been created."""
    if os.name == "nt":
        candidate = VENV_DIR / "Scripts" / "python.exe"
    else:
        candidate = VENV_DIR / "bin" / "python"
    return str(candidate) if candidate.exists() else None


def check_environment() -> dict:
    """Gather interpreter + dependency status. Fast; safe on the UI thread."""
    is_venv = sys.prefix != sys.base_prefix
    reqs = parse_requirements(REQUIREMENTS_PATH)
    installed = installed_distributions()
    status = [
        {"name": name, "installed": _normalize(name) in installed}
        for name in reqs
    ]
    return {
        "python_version": platform.python_version(),
        "python_path": sys.executable,
        "prefix": sys.prefix,
        "is_venv": is_venv,
        "venv_python": venv_python_path(),
        "requirements": status,
        "missing": [s["name"] for s in status if not s["installed"]],
        "total": len(reqs),
    }


def _stream_command(worker: "EnvironmentWorker", command: list[str], label: str, env: Optional[dict] = None) -> tuple[bool, str]:
    """Run *command*, forwarding each output line through the worker's signal."""
    worker.output.emit(f"▶ {label}: {' '.join(command)}")
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_ROOT),
            env=env,
        )
    except OSError as e:
        worker.output.emit(f"✗ could not start process: {e}")
        return False, str(e)
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            worker.output.emit(line)
    code = proc.wait()
    if code != 0:
        worker.output.emit(f"✗ exited with code {code}")
        return False, f"command exited with code {code}"
    worker.output.emit(f"✔ {label} complete")
    return True, f"{label} complete"


# ---------------------------------------------------------------------------
# Worker + service
# ---------------------------------------------------------------------------
class EnvironmentWorker(QObject):
    """Runs pip (or venv bootstrap + pip) inside a worker thread."""

    output = Signal(str)
    done = Signal(bool, str)  # success, message

    def __init__(self) -> None:
        super().__init__()
        self.task = "install"  # 'install' | 'bootstrap'
        self.command: Optional[list[str]] = None  # test override

    @Slot()
    def process(self) -> None:
        try:
            if self.task == "bootstrap":
                ok, msg = _stream_command(
                    self,
                    [sys.executable, "-m", "venv", str(VENV_DIR)],
                    "Creating virtual environment",
                )
                if not ok:
                    self.done.emit(False, "Failed to create .venv: " + msg)
                    return
                python = venv_python_path()
                if python is None:
                    self.done.emit(False, ".venv was created but its interpreter is missing")
                    return
                installer = [python, "-m", "pip"]
            else:
                installer = [sys.executable, "-m", "pip"]

            command = self.command or installer + [
                "install", "--disable-pip-version-check", "-r", str(REQUIREMENTS_PATH),
            ]
            ok, msg = _stream_command(self, command, "Installing dependencies")
            if not ok:
                self.done.emit(False, "Dependency installation failed: " + msg)
                return
            self.done.emit(True, "Dependencies installed")
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            logger.error("Environment task failed: %s", e)
            self.done.emit(False, str(e))


class EnvironmentService(QObject):
    """Owns environment checks and background install/bootstrap tasks."""

    output = Signal(str)
    finished = Signal(bool, str)  # success, message

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[EnvironmentWorker] = None
        self.last_task = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def check(self) -> dict:
        return check_environment()

    @property
    def is_busy(self) -> bool:
        return self._thread is not None and isValid(self._thread) and self._thread.isRunning()

    def run_task(self, task: str) -> bool:
        """Start 'install' or 'bootstrap' in the background. No-op if busy."""
        if self.is_busy:
            return False
        self.last_task = task

        thread = QThread(self)
        worker = EnvironmentWorker()
        worker.task = task
        worker.moveToThread(thread)

        thread.started.connect(worker.process)
        worker.output.connect(self.output)
        worker.done.connect(self._on_done)
        worker.done.connect(thread.quit)
        worker.done.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()
        return True

    def stop(self) -> None:
        """Wait (bounded) for any in-flight task; safe to call on shutdown."""
        thread = self._thread
        if thread is not None and isValid(thread) and thread.isRunning():
            thread.quit()
            thread.wait(1000)
        self._thread = None
        self._worker = None

    def relaunch(self) -> Optional[str]:
        """Launch the app with the .venv interpreter; returns its path, or None."""
        python = venv_python_path()
        if python is None:
            return None
        subprocess.Popen([python, "main.py"], cwd=str(PROJECT_ROOT))
        return python

    # ------------------------------------------------------------------
    # Slots (main thread)
    # ------------------------------------------------------------------
    @Slot(bool, str)
    def _on_done(self, success: bool, message: str) -> None:
        self._thread = None
        self._worker = None
        self.finished.emit(success, message)
