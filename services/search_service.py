"""
SearchService - Qt bridge for paragraph search without RAG.

Runs a :class:`~core.search.paragraph_search.ParagraphSearcher` scan on a
worker thread (the model calls are blocking, so they must never run on the
GUI thread), forwarding progress and hits via signals. Supports cooperative
stop, following the services worker pattern (see services/chat_service.py):
arguments are assigned as attributes before the thread starts and
:meth:`process` is a zero-arg slot.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot
from shiboken6 import isValid

from core.agent.tool_registry import ToolRegistry
from core.llm.model_backend import ModelBackend
from core.search.paragraph_search import ParagraphSearcher
from core.search.planner import READ_ONLY_TOOLS, SearchPlanner

logger = logging.getLogger(__name__)


class SearchWorker(QObject):
    """Scans one document for a query; runs inside a QThread."""

    progress = Signal(int, int)   # (done_chunks, total_chunks) within one file
    file_started = Signal(str, int, int)  # (path, 1-based index, file count)
    planned = Signal(dict)        # the full SearchPlan: query/keywords/files/steps
    tool_called = Signal(dict)    # one planner tool call: {"tool", "target"}, live
    hit_found = Signal(dict)      # one quoted passage: {"text", "source", ...}
    finished = Signal(list)       # deduped hits, list of {"text", "source", ...}
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop_event = threading.Event()
        self.backend: Optional[ModelBackend] = None
        self.query: str = ""
        self.text: str = ""
        self.folder: Optional[str] = None   # folder mode when set
        self.patterns: Optional[str] = None
        self.exhaustive: bool = False
        self.use_plan: bool = True
        self.params: dict = {}

    @Slot()
    def process(self) -> None:
        try:
            searcher = ParagraphSearcher(self.backend.generate, **self.params)
            query = self.query
            keywords = None
            target_files = None
            if self.use_plan and not self._stop_event.is_set():
                # The planner inspects the folder with read-only tools only
                # (workspace-jailed) and returns an ordered decision tree.
                tools = ToolRegistry(self.folder, only=READ_ONLY_TOOLS) if self.folder else None
                planner = SearchPlanner(self.backend.generate, tools=tools)
                plan = planner.plan(
                    self.query,
                    should_cancel=self._stop_event.is_set,
                    on_tool_call=lambda call: self.tool_called.emit(call),
                )
                query = plan.query
                keywords = plan.keywords or None
                target_files = plan.files or None
                if not self._stop_event.is_set():
                    self.planned.emit(plan.to_dict())
            if self.folder:
                hits = searcher.search_folder(
                    query,
                    self.folder,
                    patterns=self.patterns,
                    exhaustive=self.exhaustive,
                    keywords=keywords,
                    files=target_files,
                    on_progress=lambda done, total: self.progress.emit(done, total),
                    on_hit=lambda hit: self.hit_found.emit(hit.to_dict()),
                    should_cancel=self._stop_event.is_set,
                    on_file_started=lambda p, i, n: self.file_started.emit(p, i, n),
                )
            else:
                hits = searcher.search(
                    query,
                    self.text,
                    on_progress=lambda done, total: self.progress.emit(done, total),
                    on_hit=lambda hit: self.hit_found.emit(hit.to_dict()),
                    should_cancel=self._stop_event.is_set,
                )
            cancelled = self._stop_event.is_set()
            self.finished.emit([] if cancelled else [h.to_dict() for h in hits])
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            logger.error("Paragraph search failed: %s", e)
            self.error.emit(str(e))

    def stop(self) -> None:
        self._stop_event.set()


class SearchService(QObject):
    """Runs paragraph searches in the background and reports via signals."""

    progress = Signal(int, int)
    file_started = Signal(str, int, int)
    planned = Signal(dict)
    tool_called = Signal(dict)
    hit_found = Signal(dict)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[SearchWorker] = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None

    def search(
        self,
        backend: ModelBackend,
        query: str,
        text: str = "",
        *,
        folder: Optional[str] = None,
        patterns: Optional[str] = None,
        exhaustive: bool = False,
        use_plan: bool = True,
        **params: object,
    ) -> None:
        """Start scanning for *query*: *text*, or every matching file in *folder*."""
        self.stop()

        worker = SearchWorker()
        worker.backend = backend
        worker.query = query
        worker.text = text
        worker.folder = folder
        worker.patterns = patterns
        worker.exhaustive = exhaustive
        worker.use_plan = use_plan
        worker.params = params

        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.process)
        worker.progress.connect(self.progress.emit)
        worker.file_started.connect(self.file_started.emit)
        worker.planned.connect(self.planned.emit)
        worker.tool_called.connect(self.tool_called.emit)
        worker.hit_found.connect(self.hit_found.emit)
        worker.finished.connect(self.finished.emit)
        worker.error.connect(self.error.emit)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._clear_refs(thread, worker))

        self._worker = worker
        self._thread = thread
        thread.start()

    def _clear_refs(self, thread: QThread, worker: SearchWorker) -> None:
        """Drop references once a finished thread is gone (avoids stale handles)."""
        if self._thread is thread:
            self._thread = None
        if self._worker is worker:
            self._worker = None

    def stop(self) -> None:
        """Cooperatively stop the in-flight scan, if any."""
        worker = self._worker
        if worker is not None and isValid(worker):
            worker.stop()
        thread = self._thread
        if thread is not None and isValid(thread) and thread.isRunning():
            thread.quit()
            thread.wait(2000)
        self._worker = None
        self._thread = None
