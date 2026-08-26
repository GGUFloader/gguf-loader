"""HuggingFace model search and download dialog.

Provides a search interface to find GGUF models on HuggingFace,
browse available quantizations, and download with progress tracking.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QProgressBar,
    QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from ggufloader.config import FONT_FAMILY


class HFDownloadDialog(QDialog):
    """Dialog for searching and downloading GGUF models from HuggingFace."""

    model_downloaded = Signal(str)  # emits the local path of the downloaded model

    def __init__(self, parent: QWidget, models_dir: str | Path) -> None:
        super().__init__(parent)
        self.setWindowTitle("HuggingFace Model Explorer")
        self.setMinimumSize(800, 600)
        self._models_dir = Path(models_dir)
        self._hf_service = None
        self._current_models = []
        self._selected_model = None
        self._download_thread: Optional[threading.Thread] = None
        self._cancelled = False
        self._build_ui()
        self._init_service()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Search bar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search GGUF models on HuggingFace...")
        self.search_input.setMinimumHeight(36)
        self.search_input.returnPressed.connect(self._do_search)
        search_row.addWidget(self.search_input, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Most Liked", "Most Downloaded", "Recently Updated"])
        self.sort_combo.setMinimumHeight(36)
        self.sort_combo.setMaximumWidth(160)
        search_row.addWidget(self.sort_combo)

        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.setObjectName("primaryButton")
        self.search_btn.setMinimumHeight(36)
        self.search_btn.clicked.connect(self._do_search)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        # Main content: model list + details
        splitter = QSplitter(Qt.Horizontal)

        # Left: model list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_label = QLabel("Models")
        left_label.setObjectName("sectionEyebrow")
        left_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        left_layout.addWidget(left_label)

        self.model_list = QListWidget()
        self.model_list.setMinimumWidth(250)
        self.model_list.currentItemChanged.connect(self._on_model_selected)
        left_layout.addWidget(self.model_list, 1)
        splitter.addWidget(left)

        # Right: model details + files
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_label = QLabel("Details")
        right_label.setObjectName("sectionEyebrow")
        right_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        right_layout.addWidget(right_label)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(150)
        right_layout.addWidget(self.detail_text)

        files_label = QLabel("GGUF Files")
        files_label.setObjectName("sectionEyebrow")
        files_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        right_layout.addWidget(files_label)

        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(150)
        right_layout.addWidget(self.file_list, 1)
        splitter.addWidget(right)

        splitter.setSizes([300, 500])
        layout.addWidget(splitter, 1)

        # Progress bar (hidden until download starts)
        self.progress_frame = QFrame()
        progress_layout = QHBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(24)
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar, 1)
        self.progress_label = QLabel("")
        self.progress_label.setMinimumWidth(120)
        progress_layout.addWidget(self.progress_label)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_download)
        progress_layout.addWidget(self.cancel_btn)
        layout.addWidget(self.progress_frame)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.status_label = QLabel("Search for models to get started")
        self.status_label.setObjectName("mutedLabel")
        btn_row.addWidget(self.status_label, 1)
        self.download_btn = QPushButton("⬇ Download")
        self.download_btn.setObjectName("primaryButton")
        self.download_btn.setMinimumHeight(36)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.download_btn)
        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(36)
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _init_service(self) -> None:
        try:
            from ggufloader.services.hf_service import HFService
            self._hf_service = HFService(self._models_dir)
        except Exception as e:  # noqa: BLE001
            self.status_label.setText(f"❌ Failed to init HF service: {e}")

    def _do_search(self) -> None:
        query = self.search_input.text().strip()
        if not query and self._hf_service is None:
            return

        sort_map = {
            "Most Liked": "likes",
            "Most Downloaded": "downloads",
            "Recently Updated": "lastModified",
        }
        sort_by = sort_map.get(self.sort_combo.currentText(), "likes")

        self.search_btn.setEnabled(False)
        self.status_label.setText("🔍 Searching...")
        self.model_list.clear()
        self._current_models = []

        def _worker() -> None:
            try:
                models = self._hf_service.search(query, sort=sort_by, limit=20)
                QTimer.singleShot(0, lambda: self._on_search_done(models))
            except Exception as e:  # noqa: BLE001
                QTimer.singleShot(0, lambda: self._on_search_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_search_done(self, models: list) -> None:
        self._current_models = models
        self.search_btn.setEnabled(True)
        self.model_list.clear()

        if not models:
            self.status_label.setText("No GGUF models found")
            return

        self.status_label.setText(f"Found {len(models)} models")
        for model in models:
            label = f"{model.display_name}\n❤ {model.likes}  ⬇ {model.downloads}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, model)
            item.setToolTip(model.repo_id)
            self.model_list.addItem(item)

    def _on_search_error(self, error: str) -> None:
        self.search_btn.setEnabled(True)
        self.status_label.setText(f"❌ Search failed: {error}")

    def _on_model_selected(self, current: QListWidgetItem, _previous: QListWidgetItem) -> None:
        if current is None:
            self._selected_model = None
            self.detail_text.clear()
            self.file_list.clear()
            self.download_btn.setEnabled(False)
            return

        model = current.data(Qt.UserRole)
        self._selected_model = model

        # Show details
        desc = model.description[:500] if model.description else "No description"
        self.detail_text.setPlainText(
            f"Repository: {model.repo_id}\n"
            f"Likes: {model.likes}  |  Downloads: {model.downloads}\n"
            f"Modified: {model.last_modified}\n\n"
            f"{desc}"
        )

        # Show GGUF files
        self.file_list.clear()
        for f in model.gguf_files:
            size_mb = f.get("size", 0) / (1024 * 1024)
            label = f"{f['path'].split('/')[-1]}  ({size_mb:.0f} MB)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, f)
            self.file_list.addItem(item)

        self.download_btn.setEnabled(bool(model.gguf_files))

    def _start_download(self) -> None:
        if self._selected_model is None or self._hf_service is None:
            return

        # Get selected file
        current_file_item = self.file_list.currentItem()
        if current_file_item is None:
            # Auto-select the first (largest) file
            if self.file_list.count() > 0:
                current_file_item = self.file_list.item(0)
            else:
                QMessageBox.warning(self, "No File", "Select a GGUF file to download.")
                return

        file_info = current_file_item.data(Qt.UserRole)
        if file_info is None:
            return

        file_path = file_info.get("path", "")
        if not file_path:
            return

        # Check if already downloaded
        local_path = self._models_dir / file_path.split("/")[-1]
        if local_path.exists():
            reply = QMessageBox.question(
                self, "File Exists",
                f"{local_path.name} already exists.\n\nOverwrite?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._cancelled = False
        self.download_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting...")

        def _worker() -> None:
            try:
                result = self._hf_service.download(
                    self._selected_model.repo_id,
                    file_path,
                    on_progress=self._on_progress,
                    should_cancel=lambda: self._cancelled,
                )
                QTimer.singleShot(0, lambda: self._on_download_done(str(result)))
            except Exception as e:  # noqa: BLE001
                QTimer.singleShot(0, lambda: self._on_download_error(str(e)))

        self._download_thread = threading.Thread(target=_worker, daemon=True)
        self._download_thread.start()

    def _on_progress(self, progress) -> None:
        if progress.status == "verifying":
            self.progress_label.setText("Verifying hash...")
            self.progress_bar.setRange(0, 0)  # indeterminate
        elif progress.status == "downloading":
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(progress.percent))
            speed = progress.speed_mbps
            self.progress_label.setText(f"{speed:.1f} MB/s")
        elif progress.status == "done":
            self.progress_bar.setValue(100)
            self.progress_label.setText("Done!")

    def _on_download_done(self, path: str) -> None:
        self.download_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"✅ Downloaded: {Path(path).name}")
        self.model_downloaded.emit(path)

    def _on_download_error(self, error: str) -> None:
        self.download_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"❌ {error}")
        QMessageBox.warning(self, "Download Failed", error)

    def _cancel_download(self) -> None:
        self._cancelled = True
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling...")
