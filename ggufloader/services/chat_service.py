"""
ChatService - Qt bridge for streaming chat generation.

Each request spawns a worker thread that iterates
:meth:`ModelBackend.generate_stream`, forwarding tokens to the UI via
signals. Supports cooperative stop.
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot
from shiboken6 import isValid

from ggufloader.core.llm.model_backend import ModelBackend

logger = logging.getLogger(__name__)


class ChatWorker(QObject):
    """Streams one generation request; runs inside a QThread.

    Arguments are assigned as plain attributes before the thread starts;
    :meth:`process` is a zero-argument slot so Qt can invoke it reliably
    across threads (lambdas break queued signal delivery in PySide6).
    """

    token_received = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop_event = threading.Event()
        self.backend: Optional[ModelBackend] = None
        self.prompt: str = ""
        self.messages: Optional[List[dict]] = None
        self.stop_tokens: List[str] = []
        self.params: dict = {}

    @Slot()
    def process(self) -> None:
        try:
            kwargs = dict(self.params)
            if self.messages is not None:
                # Template-aware path: llama.cpp applies the model's own
                # chat template; EOS handling comes from the template, so
                # no generic text stop sequences are injected.
                for token in self.backend.chat_stream(self.messages, **kwargs):
                    if self._stop_event.is_set():
                        break
                    if token:
                        self.token_received.emit(token)
            else:
                kwargs["stream"] = True
                kwargs["stop"] = self.stop_tokens
                for token in self.backend.generate_stream(self.prompt, **kwargs):
                    if self._stop_event.is_set():
                        break
                    if token:
                        self.token_received.emit(token)
            self.finished.emit()
        except Exception as e:  # noqa: BLE001
            logger.error("Chat generation failed: %s", e)
            self.error.emit(str(e))

    def stop(self) -> None:
        self._stop_event.set()


class ChatService(QObject):
    """Streams assistant responses token-by-token."""

    started = Signal()
    token_received = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[ChatWorker] = None

    def generate(
        self,
        backend: ModelBackend,
        prompt: str = "",
        stop_tokens: Optional[List[str]] = None,
        messages: Optional[List[dict]] = None,
        **params: object,
    ) -> None:
        """Start streaming a response.

        Pass *messages* (role/content dicts) for the template-aware chat
        path, or *prompt* for the legacy raw-completion path.
        """
        self.stop()

        worker = ChatWorker()
        worker.backend = backend
        worker.prompt = prompt
        worker.messages = messages
        worker.stop_tokens = stop_tokens or []
        worker.params = params

        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.process)
        worker.token_received.connect(self.token_received.emit)
        worker.finished.connect(self.finished.emit)
        worker.error.connect(self.error.emit)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._clear_refs(thread, worker))

        self._worker = worker
        self._thread = thread
        self.started.emit()
        thread.start()

    def _clear_refs(self, thread: QThread, worker: ChatWorker) -> None:
        """Drop references once a finished thread is gone (avoids stale handles)."""
        if self._thread is thread:
            self._thread = None
        if self._worker is worker:
            self._worker = None

    def stop(self) -> None:
        """Cooperatively stop the in-flight generation, if any."""
        worker = self._worker
        if worker is not None and isValid(worker):
            worker.stop()
        thread = self._thread
        if thread is not None and isValid(thread) and thread.isRunning():
            thread.quit()
            thread.wait(2000)
        self._worker = None
        self._thread = None
