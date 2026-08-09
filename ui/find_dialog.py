"""
Find Paragraph dialog - locate a passage in a document with the loaded
model, no RAG required. The model scans the text in overlapping chunks and
quotes matching passages verbatim; results stream in live with progress.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from core.search.paragraph_search import DEFAULT_PATTERNS
import re

from services.search_service import SearchService


def _starts_numbered(step: str) -> bool:
    """True when a plan step already begins with a number ("1. " / "1)")."""
    return bool(re.match(r"^\s*\d+[.)]", step))


class FindParagraphDialog(QDialog):
    """Search a file or pasted text for the passage answering a query."""

    def __init__(
        self,
        model_service,
        parent: Optional[QWidget] = None,
        default_folder: str = "",
        settings: Optional[QSettings] = None,
    ) -> None:
        super().__init__(parent)
        self._model_service = model_service
        self._search_service = SearchService(self)
        self._settings = settings or QSettings("GGUFLoader", "FindParagraph")
        self._file_path: Optional[str] = None
        self._folder_path: Optional[str] = default_folder or None
        self._folder_mode = False
        self._hits: List[str] = []
        self._cancelled = False
        self._current_file = ""
        self._file_index = 0
        self._file_total = 0
        self._live_trace: List[dict] = []

        self.setWindowTitle("Find Paragraph")
        self.setMinimumSize(560, 520)
        self.resize(640, 580)

        self._setup_ui()
        self._wire_signals()
        self._load_settings()
        self._update_run_state()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("\U0001F50E Find Paragraph")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        hint = QLabel(
            "Search a document with the loaded model \u2014 no RAG, no setup. "
            "The model scans the text in chunks and quotes matching passages."
        )
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Query
        query_row = QHBoxLayout()
        query_label = QLabel("Query:")
        query_label.setMinimumWidth(60)
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText(
            "Describe what you're looking for, e.g. \"explain how GPU offloading works\""
        )
        query_row.addWidget(query_label)
        query_row.addWidget(self.query_edit, 1)
        layout.addLayout(query_row)

        # Source picker
        source_row = QHBoxLayout()
        source_label = QLabel("Source:")
        source_label.setMinimumWidth(60)
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Workspace file\u2026", "Pasted text", "Workspace folder\u2026"])
        self.browse_btn = QPushButton("Browse\u2026")
        self.file_path_label = QLabel("No file chosen")
        self.file_path_label.setObjectName("mutedLabel")
        source_row.addWidget(source_label)
        source_row.addWidget(self.source_combo)
        source_row.addWidget(self.browse_btn)
        source_row.addWidget(self.file_path_label, 1)
        layout.addLayout(source_row)

        # Source pages: file hint vs. paste area
        self.source_stack = QStackedWidget()
        file_page = QWidget()
        file_note = QLabel("Select a text document (txt, md, code, logs, \u2026) and it will be read when you run the search.")
        file_note.setObjectName("mutedLabel")
        file_note.setWordWrap(True)
        file_layout = QVBoxLayout(file_page)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.addWidget(file_note)
        file_layout.addStretch()
        self.source_stack.addWidget(file_page)

        text_page = QWidget()
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Paste the document text here\u2026")
        text_layout = QVBoxLayout(text_page)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.addWidget(self.text_edit)
        self.source_stack.addWidget(text_page)

        folder_page = QWidget()
        folder_note = QLabel(
            "Scans matching files recursively (skipping .git, __pycache__, "
            "node_modules, \u2026). Files with no keyword match are skipped "
            "automatically, so the model only reads the chunks that mention "
            "your query. Each hit shows the file it came from."
        )
        folder_note.setObjectName("mutedLabel")
        folder_note.setWordWrap(True)
        pattern_row = QHBoxLayout()
        pattern_label = QLabel("Pattern:")
        self.pattern_edit = QLineEdit(DEFAULT_PATTERNS)
        self.pattern_edit.setToolTip("Space-separated file patterns to scan")
        pattern_row.addWidget(pattern_label)
        pattern_row.addWidget(self.pattern_edit, 1)
        self.exhaustive_check = QCheckBox(
            "Scan every chunk (slow, catches pure paraphrases)"
        )
        self.exhaustive_check.setToolTip(
            "By default only chunks containing a query keyword are read by "
            "the model. Enable this to scan every chunk of every file."
        )
        folder_layout = QVBoxLayout(folder_page)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.addWidget(folder_note)
        folder_layout.addLayout(pattern_row)
        folder_layout.addWidget(self.exhaustive_check)
        folder_layout.addStretch()
        self.source_stack.addWidget(folder_page)
        layout.addWidget(self.source_stack, 1)

        # Status
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        # Planner decision tree (shown once the plan is ready)
        self.plan_label = QLabel("")
        self.plan_label.setObjectName("mutedLabel")
        self.plan_label.setWordWrap(True)
        self.plan_label.hide()
        layout.addWidget(self.plan_label)

        # Results
        self.results = QListWidget()
        self.results.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.results, 2)

        # Buttons
        button_row = QHBoxLayout()
        button_row.addStretch()
        self.cancel_btn = QPushButton("Stop")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.hide()
        self.run_btn = QPushButton("Find")
        self.run_btn.setObjectName("primaryButton")
        self.close_btn = QPushButton("Close")
        button_row.addWidget(self.cancel_btn)
        button_row.addWidget(self.run_btn)
        button_row.addWidget(self.close_btn)
        layout.addLayout(button_row)

    def _wire_signals(self) -> None:
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.browse_btn.clicked.connect(self._browse)
        self.query_edit.textChanged.connect(self._update_run_state)
        self.source_stack.currentChanged.connect(self._update_run_state)
        self.run_btn.clicked.connect(self._on_run)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.close_btn.clicked.connect(self.close)
        self.results.itemDoubleClicked.connect(self._copy_hit)

        svc = self._search_service
        svc.progress.connect(self._on_progress)
        svc.file_started.connect(self._on_file_started)
        svc.planned.connect(self._on_planned)
        svc.tool_called.connect(self._on_tool_called)
        svc.hit_found.connect(self._on_hit_found)
        svc.finished.connect(self._on_finished)
        svc.error.connect(self._on_error)

    # ------------------------------------------------------------------
    # Behavior
    # ------------------------------------------------------------------
    def _on_source_changed(self) -> None:
        idx = self.source_combo.currentIndex()
        self.source_stack.setCurrentIndex(idx)  # file=0, text=1, folder=2
        is_browse = idx in (0, 2)
        self.browse_btn.setVisible(is_browse)
        self.file_path_label.setVisible(is_browse)
        self._update_run_state()

    def _browse(self) -> None:
        if self.source_combo.currentIndex() == 2:
            folder = QFileDialog.getExistingDirectory(
                self, "Select workspace folder",
                self._folder_path or str(Path.home()),
                QFileDialog.Option.ShowDirsOnly,
            )
            if folder:
                self._folder_path = folder
                self.file_path_label.setText(folder)
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Choose a document", "",
                "Text files (*.txt *.md *.py *.json *.log *.csv *.html);;All files (*)",
            )
            if path:
                self._file_path = path
                self.file_path_label.setText(path)
        self._update_run_state()

    def _current_text(self) -> str:
        if self.source_combo.currentIndex() == 0:
            if not self._file_path:
                return ""
            try:
                return Path(self._file_path).read_text(encoding="utf-8-sig")
            except (UnicodeDecodeError, OSError):
                try:
                    return Path(self._file_path).read_text(encoding="latin-1")
                except OSError:
                    return ""
        return self.text_edit.toPlainText()

    def _update_run_state(self) -> None:
        idx = self.source_combo.currentIndex()
        if idx == 0:
            has_source = bool(self._file_path)
        elif idx == 2:
            has_source = bool(self._folder_path)
        else:
            has_source = bool(self.text_edit.toPlainText().strip())
        self.run_btn.setEnabled(bool(self.query_edit.text().strip()) and has_source)

    # ------------------------------------------------------------------
    # Persistence (last query, source, folder, pattern, exhaustive)
    # ------------------------------------------------------------------
    def _load_settings(self) -> None:
        """Restore the last search's query, source, and options."""
        s = self._settings
        self.query_edit.setText(str(s.value("query", "") or ""))
        self.pattern_edit.setText(str(s.value("pattern", DEFAULT_PATTERNS) or DEFAULT_PATTERNS))
        self.exhaustive_check.setChecked(self._get_bool(s.value("exhaustive", False)))
        self._file_path = str(s.value("filePath", "") or "") or None
        saved_folder = str(s.value("folderPath", "") or "") or None
        # A saved folder wins; otherwise keep the __init__ default workspace.
        self._folder_path = saved_folder or self._folder_path
        idx = int(s.value("source", 0) or 0)
        if 0 <= idx < self.source_combo.count():
            self.source_combo.setCurrentIndex(idx)  # also switches the page
        if self._folder_path:
            self.file_path_label.setText(self._folder_path)
        elif self._file_path:
            self.file_path_label.setText(self._file_path)

    def _save_settings(self) -> None:
        """Persist the current query, source, and options."""
        s = self._settings
        s.setValue("query", self.query_edit.text().strip())
        s.setValue("source", self.source_combo.currentIndex())
        s.setValue("filePath", self._file_path or "")
        s.setValue("folderPath", self._folder_path or "")
        s.setValue("pattern", self.pattern_edit.text().strip())
        s.setValue("exhaustive", self.exhaustive_check.isChecked())
        s.sync()

    @staticmethod
    def _get_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "on")

    def _on_run(self) -> None:
        query = self.query_edit.text().strip()
        if not query:
            self._set_status("Enter a query first.", err=True)
            return
        backend = self._model_service.backend
        if backend is None:
            self._set_status("Load a model first (File > Load Model\u2026).", err=True)
            return

        if self.source_combo.currentIndex() == 2:
            if not self._folder_path:
                self._set_status("Choose a workspace folder first.", err=True)
                return
            self._save_settings()
            self._folder_mode = True
            self.results.clear()
            self._hits = []
            self._cancelled = False
            self._current_file = ""
            self._live_trace = []
            self.plan_label.hide()
            self._set_running(True)
            self._set_status("Planning the search\u2026")
            self._search_service.search(
                backend, query,
                folder=self._folder_path,
                patterns=self.pattern_edit.text().strip(),
                exhaustive=self.exhaustive_check.isChecked(),
            )
            return

        self._save_settings()
        self._folder_mode = False
        text = self._current_text()
        if not text.strip():
            self._set_status("Choose a file or paste some text first.", err=True)
            return

        self.results.clear()
        self._hits = []
        self._cancelled = False
        self._current_file = ""
        self._live_trace = []
        self.plan_label.hide()
        self._set_running(True)
        self._set_status("Planning the search\u2026")
        self._search_service.search(backend, query, text)

    def _on_cancel(self) -> None:
        self._cancelled = True
        self._search_service.stop()

    # ------------------------------------------------------------------
    # Service slots
    # ------------------------------------------------------------------
    _TRACE_VERBS = {"list_directory": "listed", "read_file": "read",
                    "search_files": "searched"}

    @classmethod
    def _render_inspected(cls, calls) -> str:
        """Human-readable trace line: 'listed workspace · read notes.txt'."""
        parts = []
        for call in calls[:6]:
            tool = call.get("tool", "")
            target = call.get("target", "")
            if tool == "list_directory" and target in (".", ""):
                target = "workspace"
            parts.append(f"{cls._TRACE_VERBS.get(tool, tool)} {target}")
        line = " \u00B7 ".join(parts)
        if len(calls) > 6:
            line += f" (+{len(calls) - 6} more)"
        return line

    def _on_tool_called(self, call: dict) -> None:
        """A planner tool just ran - stream it into the inspected line."""
        self._live_trace.append(call)
        line = self._render_inspected(self._live_trace)
        self._set_status(f"Planning\u2026 {line}")
        self.plan_label.setText(f"\U0001F50D Inspected: {line}")
        self.plan_label.show()

    def _on_planned(self, plan: dict) -> None:
        """The planner's decision tree is ready; show the target, steps, trace."""
        self._set_status(f"Searching for: {plan.get('query', '')}")
        self._live_trace = []
        text = ""
        steps = [s for s in plan.get("steps", []) if s]
        if steps:
            shown = steps[:4]
            parts = []
            for i, s in enumerate(shown):
                if _starts_numbered(s):  # model already numbered it
                    parts.append(s)
                else:
                    parts.append(f"{i + 1}. {s}")
            text = " ".join(parts)
            if len(steps) > len(shown):
                text += f" (+{len(steps) - len(shown)} more)"
            text = f"\U0001F9ED Plan: {text}"
        trace = [t for t in plan.get("trace", []) if isinstance(t, dict)]
        if trace:
            text += ("\n" if text else "") + f"\U0001F50D Inspected: {self._render_inspected(trace)}"
        if text:
            self.plan_label.setText(text)
            self.plan_label.show()

    def _on_file_started(self, path: str, index: int, total: int) -> None:
        self._current_file = Path(path).name
        self._file_index = index
        self._file_total = total
        self._set_status(
            f"Scanning file {index}/{total}: {self._current_file} \u2026 {len(self._hits)} hit(s)"
        )

    def _on_progress(self, done: int, total: int) -> None:
        if self._current_file:
            self._set_status(
                f"Scanning file {self._file_index}/{self._file_total}: "
                f"{self._current_file} \u2014 chunk {done}/{total} \u2026 {len(self._hits)} hit(s)"
            )
        else:
            self._set_status(f"Scanning chunk {done}/{total} \u2026 {len(self._hits)} hit(s)")

    def _on_hit_found(self, hit: dict) -> None:
        text = hit.get("text", "")
        self._hits.append(text)
        self._add_item(text, hit.get("source", ""))

    def _on_finished(self, hits: list) -> None:
        if self._cancelled:
            self._set_status("Stopped.")
        elif hits:
            self.results.clear()
            self._hits = [h["text"] for h in hits]
            for h in hits:
                self._add_item(h["text"], h.get("source", ""))
            self._set_status(f"Found {len(hits)} passage(s). Double-click a result to copy it.", ok=True)
        else:
            self._set_status("No matching passages found.")
        self._set_running(False)

    def _on_error(self, message: str) -> None:
        self._set_status(f"\u274c {message}", err=True)
        self._set_running(False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _add_item(self, text: str, source: str = "") -> None:
        label = self._elide(text)
        if source:
            label = f"{Path(source).name} \u2014 {label}"
            tip = f"{text}\n\n\U0001F4C4 {source}"
        else:
            tip = text
        item = QListWidgetItem(label)
        item.setToolTip(tip)
        item.setData(Qt.ItemDataRole.UserRole, text)
        self.results.addItem(item)

    @staticmethod
    def _elide(text: str, limit: int = 150) -> str:
        one_line = " ".join(text.split())
        return one_line if len(one_line) <= limit else one_line[:limit] + "\u2026"

    def _copy_hit(self, item: QListWidgetItem) -> None:
        text = item.data(Qt.ItemDataRole.UserRole) or ""
        if text:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
            self._set_status("Copied to clipboard.", ok=True)

    def _set_running(self, running: bool) -> None:
        self.run_btn.setVisible(not running)
        self.cancel_btn.setVisible(running)
        self.source_combo.setEnabled(not running)
        self.query_edit.setEnabled(not running)
        self.text_edit.setEnabled(not running)
        self.pattern_edit.setEnabled(not running)
        self.exhaustive_check.setEnabled(not running)
        self.browse_btn.setEnabled(not running)

    def _set_status(self, message: str, *, err: bool = False, ok: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("state", "err" if err else ("ok" if ok else ""))
        style = self.status_label.style()
        style.unpolish(self.status_label)
        style.polish(self.status_label)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._search_service.stop()
        self._save_settings()  # persist the source/options even without a run
        super().closeEvent(event)
