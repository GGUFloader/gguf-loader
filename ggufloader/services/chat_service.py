"""
ChatService - Qt bridge for streaming chat generation.

Each request spawns a worker thread that iterates
:meth:`ModelBackend.generate_stream`, forwarding tokens to the UI via
signals. Supports cooperative stop.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot
from shiboken6 import isValid

from ggufloader.core.llm.model_backend import ModelBackend
from ggufloader.core.llm.prompt_builder import CHAT_STOP_TOKENS

logger = logging.getLogger(__name__)


class ChatWorker(QObject):
    """Streams one generation request; runs inside a QThread.

    Arguments are assigned as plain attributes before the thread starts;
    :meth:`process` is a zero-argument slot so Qt can invoke it reliably
    across threads (lambdas break queued signal delivery in PySide6).
    """

    token_received = Signal(str)
    rate_update = Signal(float)  # tokens per second
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
        self._token_count = 0
        self._start_time = 0.0
        self._last_rate_time = 0.0

    @Slot()
    def process(self) -> None:
        self._token_count = 0
        self._start_time = time.monotonic()
        self._last_rate_time = self._start_time
        try:
            kwargs = dict(self.params)
            if self.messages is not None:
                kwargs["stop"] = CHAT_STOP_TOKENS
                for token in self.backend.chat_stream(self.messages, **kwargs):
                    if self._stop_event.is_set():
                        break
                    if token:
                        self._token_count += 1
                        self.token_received.emit(token)
                        self._maybe_emit_rate()
            else:
                kwargs["stream"] = True
                kwargs["stop"] = self.stop_tokens
                for token in self.backend.generate_stream(self.prompt, **kwargs):
                    if self._stop_event.is_set():
                        break
                    if token:
                        self._token_count += 1
                        self.token_received.emit(token)
                        self._maybe_emit_rate()
            self.finished.emit()
        except Exception as e:  # noqa: BLE001
            err_msg = str(e)
            # Suppress template validation errors that don't prevent generation
            # (e.g. Mistral "Conversation roles must alternate" when system prompt
            # was incorrectly included but the model still generates fine)
            if "Conversation roles must alternate" in err_msg or \
               "Only user and assistant roles are supported" in err_msg:
                logger.debug("Template validation error (suppressed): %s", err_msg)
                # Don't emit error - model may still work
                self.finished.emit()
            else:
                logger.error("Chat generation failed: %s", err_msg)
                self.error.emit(err_msg)

    def _maybe_emit_rate(self) -> None:
        """Emit tokens/sec every ~1 second (GPT4All TokenTimer parity)."""
        now = time.monotonic()
        elapsed = now - self._last_rate_time
        if elapsed >= 1.0:
            tps = self._token_count / max(0.001, now - self._start_time)
            self.rate_update.emit(round(tps, 1))
            self._last_rate_time = now

    def stop(self) -> None:
        self._stop_event.set()

    def get_token_count(self) -> int:
        return self._token_count


class ChatService(QObject):
    """Streams assistant responses token-by-token."""

    started = Signal()
    token_received = Signal(str)
    rate_update = Signal(float)  # tokens per second
    finished = Signal()
    error = Signal(str)
    token_count_updated = Signal(int)  # total tokens for this response

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
        worker.finished.connect(lambda: self.token_count_updated.emit(worker.get_token_count()))
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
