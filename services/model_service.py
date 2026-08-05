"""
ModelService - Qt bridge that loads and unloads models in the background.

A fresh ``QThread`` + worker is created per load request (the
professional Qt pattern; we never subclass ``QThread``). The loaded
:class:`~core.llm.model_backend.ModelBackend` is returned via signal and
owned by the service afterwards.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

from core.llm.model_backend import ModelBackend

logger = logging.getLogger(__name__)


class ModelLoadWorker(QObject):
    """Does the actual loading; runs inside a dedicated QThread.

    Args are assigned as attributes before the thread starts; :meth:`process`
    is a zero-arg slot so Qt can invoke it across threads reliably.
    """

    loaded = Signal(object)   # ModelBackend
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.model_path: str = ""
        self.use_gpu: bool = False
        self.n_ctx: int = 32768

    @Slot()
    def process(self) -> None:
        try:
            backend = ModelBackend(self.model_path, use_gpu=self.use_gpu, n_ctx=self.n_ctx)
            backend.load()
            self.loaded.emit(backend)
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            logger.error("Model load failed: %s", e)
            self.error.emit(str(e))


class ModelService(QObject):
    """Owns the current ModelBackend and exposes load/unload over signals."""

    loading = Signal(str)
    loaded = Signal(object)   # ModelBackend
    error = Signal(str)
    unloaded = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._backend: Optional[ModelBackend] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[ModelLoadWorker] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def backend(self) -> Optional[ModelBackend]:
        return self._backend

    @property
    def model(self) -> Optional[ModelBackend]:
        """Callable-compatible view used by the UI and addons."""
        return self._backend

    @property
    def is_loaded(self) -> bool:
        return self._backend is not None

    def load(self, model_path: str, use_gpu: bool = False, n_ctx: int = 32768) -> None:
        """Load *model_path* in the background."""
        self.unload()

        thread = QThread(self)
        worker = ModelLoadWorker()
        worker.model_path = model_path
        worker.use_gpu = use_gpu
        worker.n_ctx = n_ctx
        worker.moveToThread(thread)

        thread.started.connect(worker.process)
        worker.loaded.connect(self._on_loaded)
        worker.error.connect(self._on_error)
        worker.loaded.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        self.loading.emit(f"Loading model...")
        thread.start()

    def unload(self) -> None:
        """Stop any pending load and release the current model."""
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        self._thread = None
        self._worker = None
        if self._backend is not None:
            self._backend.unload()
            self._backend = None
            self.unloaded.emit()

    # ------------------------------------------------------------------
    # Slots (main thread)
    # ------------------------------------------------------------------
    @Slot(object)
    def _on_loaded(self, backend: ModelBackend) -> None:
        self._backend = backend
        self._thread = None
        self._worker = None
        logger.info("Model loaded: %s", backend.model_path)
        self.loaded.emit(backend)

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self._thread = None
        self._worker = None
        self.error.emit(message)
