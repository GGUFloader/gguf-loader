"""
GpuInstallService - Installs the GPU-enabled llama-cpp-python build.

Downloads a prebuilt CUDA wheel from abetlen's GitHub releases using
urllib (pip can't follow the GitHub redirect chain and gets 0 bytes),
then installs from the local file.

- Windows / Linux : prebuilt CUDA wheel (abetlen, pinned 0.3.34)
- macOS           : Metal build from source

The new build only takes effect after the app restarts, so the UI offers
to relaunch on success.
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Optional

from ggufloader.core.system_probe import llama_supports_gpu_offload, llama_supports_metal

from PySide6.QtCore import QObject, QThread, Signal, Slot
from shiboken6 import isValid

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CUDA_INDEX_URL = "https://abetlen.github.io/llama-cpp-python/whl/cu124"

# Only this version is safe for consumer CPUs.  Newer builds may contain
# AMX / AVX-512 instructions that crash with STATUS_ILLEGAL_INSTRUCTION
# on hardware that lacks those extensions (e.g. i5-13400).
PINNED_VERSION = "0.3.34"


# ---------------------------------------------------------------------------
# Pure helpers (no Qt) - unit testable in isolation
# ---------------------------------------------------------------------------
def is_gpu_support_installed() -> bool:
    """True when the installed llama-cpp-python build can offload to a GPU.

    Uses the official runtime probes (``llama_supports_gpu_offload`` for
    CUDA, ``llama_supports_metal`` for Apple Metal), so it reflects the
    actually installed wheel - not just what the UI thinks was installed.
    Returns False if llama-cpp-python is missing entirely.
    """
    return llama_supports_gpu_offload() or llama_supports_metal()


def _get_wheel_url() -> str:
    """Build the direct download URL for the CUDA wheel."""
    suffix = "win_amd64" if platform.system() == "Windows" else "manylinux_2_35_x86_64"
    return (
        f"https://github.com/abetlen/llama-cpp-python/releases/download/"
        f"v{PINNED_VERSION}-cu124/"
        f"llama_cpp_python-{PINNED_VERSION}-py3-none-{suffix}.whl"
    )


def _wheel_cache_dir() -> Path:
    """Persistent cache directory for downloaded CUDA wheels.

    Lives in the user's home directory so wheels survive app restarts.
    ``~/.ggufloader/cache/wheels/``
    """
    d = Path.home() / ".ggufloader" / "cache" / "wheels"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cached_wheel_path() -> Path:
    """Return the expected cache path for the current platform + version."""
    filename = _get_wheel_url().rsplit("/", 1)[-1]
    return _wheel_cache_dir() / filename


def _validate_cached_wheel(path: Path) -> bool:
    """True if the cached wheel exists and looks valid (>= 1 MB)."""
    try:
        return path.exists() and path.stat().st_size >= 1024 * 1024
    except OSError:
        return False


def _download_wheel(progress_callback=None) -> str:
    """Download the CUDA wheel, using the local cache when available.

    Uses urllib instead of pip because pip gets 0 bytes from GitHub
    release redirect chains.  Successful downloads are cached in
    ``~/.ggufloader/cache/wheels/`` so subsequent installs are instant.

    Supports resume via HTTP Range headers — interrupted 511 MB downloads
    pick up where they left off instead of restarting from zero.

    Args:
        progress_callback: Optional callable(downloaded_bytes, total_bytes).

    Returns:
        Path to the downloaded .whl file.

    Raises:
        RuntimeError: If the download fails.
    """
    cached = _cached_wheel_path()
    if _validate_cached_wheel(cached):
        logger.info("Using cached wheel: %s", cached)
        if progress_callback:
            size = cached.stat().st_size
            progress_callback(size, size)
        return str(cached)

    url = _get_wheel_url()
    filename = url.rsplit("/", 1)[-1]
    dest = str(_wheel_cache_dir() / filename)

    # Resume from partial download if it exists
    existing_size = 0
    if os.path.exists(dest):
        existing_size = os.path.getsize(dest)
        if existing_size < 1024 * 1024:
            # Partial file too small — start fresh
            existing_size = 0
            try:
                os.remove(dest)
            except OSError:
                pass

    try:
        req = urllib.request.Request(url)
        if existing_size > 0:
            req.add_header("Range", f"bytes={existing_size}-")
            logger.info("Resuming download from byte %d", existing_size)

        resp = urllib.request.urlopen(req, timeout=30)  # noqa: S310
        total = int(resp.headers.get("Content-Length", 0))

        # If server supports range, total is remaining bytes
        code = resp.getcode()
        if code == 206 and existing_size > 0:
            # Partial content — total is remaining, not full size
            total = existing_size + total
            downloaded = existing_size
            mode = "ab"  # append to existing partial file
        else:
            # Server doesn't support range or fresh download
            downloaded = 0
            mode = "wb"
            existing_size = 0

        chunk_size = 1024 * 1024  # 1 MB chunks
        with open(dest, mode) as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total)
    except Exception as e:
        # Keep partial download for resume on next attempt
        logger.warning("Download interrupted at %d bytes — will resume next time", existing_size)
        raise RuntimeError(f"Failed to download CUDA wheel: {e}") from e

    # Verify the file is not empty/corrupt
    size = os.path.getsize(dest)
    if size < 1024 * 1024:  # less than 1 MB — definitely corrupt
        os.remove(dest)
        raise RuntimeError(
            f"Downloaded wheel is too small ({size} bytes) — "
            "the download may have been interrupted."
        )

    logger.info("Cached wheel: %s (%d MB)", dest, size // (1024 * 1024))
    return dest


def _install_wheel(wheel_path: str) -> tuple[bool, str]:
    """Install a local .whl file with pip. Returns (success, message)."""
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--force-reinstall",
        "--find-links", os.path.dirname(wheel_path),
        f"llama-cpp-python=={PINNED_VERSION}",
    ]
    logger.info("Installing local wheel: %s", cmd)
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=300,
    )
    if result.returncode == 0:
        return True, result.stdout
    return False, result.stdout + "\n" + result.stderr


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
            # macOS: Metal build from source
            if platform.system() == "Darwin":
                self.output.emit("Installing Metal support (macOS)...\n")
                cmd = [
                    sys.executable, "-m", "pip", "install",
                    "--force-reinstall", f"llama-cpp-python=={PINNED_VERSION}",
                ]
                env = dict(os.environ)
                env["CMAKE_ARGS"] = "-DGGML_METAL=on"
                env["FORCE_CMAKE"] = "1"
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=600, env=env,
                )
                if result.returncode == 0:
                    self.done.emit(True, "Metal support installed. Restart the app to use it.")
                else:
                    self.done.emit(False, "Metal install failed: " + result.stderr)
                return

            # --- Windows / Linux: download prebuilt CUDA wheel ---
            self.output.emit(f"Downloading GPU wheel (llama-cpp-python=={PINNED_VERSION})...\n")
            wheel_path = _download_wheel(
                progress_callback=lambda dl, total: self.output.emit(
                    f"  Downloaded: {dl // (1024*1024)}MB / {total // (1024*1024)}MB\n"
                )
            )
            self.output.emit("Download complete. Installing...\n")

            ok, msg = _install_wheel(wheel_path)
            # Wheel stays cached in ~/.ggufloader/cache/wheels/
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
