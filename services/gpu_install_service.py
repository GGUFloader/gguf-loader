"""
GpuInstallService - Installs the GPU-enabled llama-cpp-python build.

Replaces the CPU-only wheel with a GPU build in a worker thread so the UI
never blocks, streaming pip output to the sidebar. Platform-aware:

- Windows / Linux : prebuilt CUDA wheels from the abetlen index
- macOS           : Metal build from source (no NVIDIA/CUDA on Apple silicon)

The new build only takes effect after the app restarts, so the UI offers
to relaunch on success.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot
from shiboken6 import isValid

from services.environment_service import _stream_command

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CUDA_INDEX_URL = "https://abetlen.github.io/llama-cpp-python/whl/cu124"


# ---------------------------------------------------------------------------
# Pure helpers (no Qt) - unit testable in isolation
# ---------------------------------------------------------------------------
def is_gpu_support_installed() -> bool:
    """True when the installed llama-cpp-python build can offload to a GPU.

    Uses the official runtime probe (``llama_supports_gpu_offload`` for
    CUDA, ``llama_supports_metal`` for Apple Metal), so it reflects the
    actually installed wheel - not just what the UI thinks was installed.
    Returns False if llama-cpp-python is missing entirely.
    """
    try:
        from llama_cpp import llama_cpp as _llama_cpp
    except Exception:  # pragma: no cover - package missing
        return False
    for probe in ("llama_supports_gpu_offload", "llama_supports_metal"):
        fn = getattr(_llama_cpp, probe, None)
        if callable(fn):
            try:
                return bool(fn())
            except Exception:  # pragma: no cover - backend init failure
                return False
    return False


def gpu_install_command() -> list[str]:
    """Pip command that replaces the current build with a GPU-enabled one."""
    pip = [
        sys.executable, "-m", "pip", "install",
        "--force-reinstall", "llama-cpp-python",
    ]
    if platform.system() == "Darwin":
        return pip  # Metal build is selected via CMAKE_ARGS in the environment
    return pip + ["--extra-index-url", CUDA_INDEX_URL]


def gpu_install_env() -> dict[str, str]:
    """Environment for the install; Metal flags on macOS, otherwise unchanged."""
    env = dict(os.environ)
    if platform.system() == "Darwin":
        env["CMAKE_ARGS"] = "-DGGML_METAL=on"
        env["FORCE_CMAKE"] = "1"
    return env


# ---------------------------------------------------------------------------
# Worker + service
# ---------------------------------------------------------------------------
class GpuInstallWorker(QObject):
    """Runs the GPU install inside a worker thread."""

    output = Signal(str)
    done = Signal(bool, str)  # success, message

    @Slot()
    def process(self) -> None:
        try:
            ok, msg = _stream_command(
                self,
                gpu_install_command(),
                "Installing GPU support",
                env=gpu_install_env(),
            )
            if ok:
                self.done.emit(True, "GPU support installed. Restart the app to use it.")
            else:
                self.done.emit(False, "GPU install failed: " + msg)
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            logger.error("GPU install task failed: %s", e)
            self.done.emit(False, str(e))


class GpuInstallService(QObject):
    """Owns the background GPU install task."""

    output = Signal(str)
    finished = Signal(bool, str)  # success, message

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[GpuInstallWorker] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def is_busy(self) -> bool:
        return self._thread is not None and isValid(self._thread) and self._thread.isRunning()

    def run_install(self) -> bool:
        """Start the GPU install in the background. No-op if busy."""
        if self.is_busy:
            return False

        thread = QThread(self)
        worker = GpuInstallWorker()
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

    # ------------------------------------------------------------------
    # Slots (main thread)
    # ------------------------------------------------------------------
    @Slot(bool, str)
    def _on_done(self, success: bool, message: str) -> None:
        self._thread = None
        self._worker = None
        self.finished.emit(success, message)
