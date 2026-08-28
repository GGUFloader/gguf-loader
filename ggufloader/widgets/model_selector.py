"""
ModelSelector - Model browsing and quick-switch panel.

Shows available GGUF models in a list with:
- File name, size, quantization
- Currently loaded indicator
- Double-click to load
- Right-click context menu (load, delete, rename)

Pattern from: Ollama model list + LM Studio model browser.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY, get_paths


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _guess_quant(filename: str) -> str:
    name = filename.lower()
    for q in ["q2_k", "q3_k_s", "q3_k_m", "q3_k_l", "q4_0", "q4_k_s", "q4_k_m",
              "q5_0", "q5_k_s", "q5_k_m", "q6_k", "q8_0", "f16", "f32"]:
        if q in name:
            return q.upper()
    return "?"


class ModelSelector(QWidget):
    """Model browsing and quick-switch panel.

    Usage:
        selector = ModelSelector()
        selector.model_selected.connect(load_model)
        selector.refresh()
    """

    model_selected = Signal(str)  # file path
    model_deleted = Signal(str)  # file path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("modelSelector")
        self._models_dir = get_paths()["models"]
        self._current_model = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        header.setSpacing(6)

        title = QLabel("📦 Available Models")
        title.setObjectName("sectionEyebrow")
        title.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        header.addWidget(title)

        header.addStretch()

        self._count_label = QLabel("0 models")
        self._count_label.setStyleSheet("font-size: 9px; color: #6b7280;")
        header.addWidget(self._count_label)

        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(20, 20)
        refresh_btn.setStyleSheet("border: none; font-size: 10px;")
        refresh_btn.setToolTip("Refresh model list")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Model list
        self._list = QListWidget()
        self._list.setObjectName("modelList")
        self._list.setMinimumHeight(100)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list, 1)

    def refresh(self) -> None:
        """Scan the models directory and update the list."""
        self._list.clear()
        if not self._models_dir.is_dir():
            self._count_label.setText("0 models")
            return

        models = []
        for f in sorted(self._models_dir.rglob("*.gguf")):
            try:
                size = f.stat().st_size
                models.append((f, size))
            except OSError:
                continue

        for path, size in models:
            name = path.stem
            quant = _guess_quant(path.name)
            size_str = _format_size(size)
            is_loaded = str(path) == self._current_model

            label = f"{'▸ ' if is_loaded else ''}{name}\n    {quant} · {size_str}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, str(path))
            if is_loaded:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self._list.addItem(item)

        self._count_label.setText(f"{len(models)} model{'s' if len(models) != 1 else ''}")

    def set_current_model(self, path: str) -> None:
        """Mark a model as currently loaded."""
        self._current_model = path
        self.refresh()

    def _on_double_click(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self.model_selected.emit(path)

    def _show_context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if not item:
            return
        path = item.data(Qt.UserRole)
        if not path:
            return

        menu = QMenu()
        load_action = menu.addAction("🚀 Load Model")
        load_action.triggered.connect(lambda: self.model_selected.emit(path))

        menu.addSeparator()

        info_action = menu.addAction("ℹ️ Show Info")
        info_action.triggered.connect(lambda: self._show_info(path))

        menu.addSeparator()

        delete_action = menu.addAction("🗑 Delete")
        delete_action.triggered.connect(lambda: self._delete_model(path))

        menu.exec(self._list.mapToGlobal(pos))

    def _show_info(self, path: str) -> None:
        p = Path(path)
        size = _format_size(p.stat().st_size)
        quant = _guess_quant(p.name)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Model Info",
            f"Name: {p.stem}\n"
            f"Path: {p}\n"
            f"Size: {size}\n"
            f"Quantization: {quant}",
        )

    def _delete_model(self, path: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Delete Model",
            f"Delete {Path(path).name}?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                os.remove(path)
                self.model_deleted.emit(path)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete: {e}")
