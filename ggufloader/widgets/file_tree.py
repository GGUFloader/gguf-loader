"""
FileTree - Workspace file browser for the sidebar.

Inspired by OpenHands' file explorer which provides a visual workspace
browser with click-to-add-to-context functionality.

Source: openhands/src/components/features/file-explorer/
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

# Directories to skip
SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".idea", ".vscode", ".eggs", "*.egg-info",
})

# File icons by extension
FILE_ICONS = {
    ".py": "🐍", ".js": "📜", ".ts": "📜", ".tsx": "📜",
    ".jsx": "📜", ".json": "📋", ".yaml": "📋", ".yml": "📋",
    ".md": "📝", ".txt": "📄", ".rs": "🦀", ".go": "🔵",
    ".java": "☕", ".c": "🔧", ".cpp": "🔧", ".h": "🔧",
    ".css": "🎨", ".html": "🌐", ".sh": "⚙️", ".bat": "⚙️",
    ".toml": "⚙️", ".cfg": "⚙️", ".ini": "⚙️",
}


class FileTree(QWidget):
    """Workspace file browser with search and click-to-add.

    Signals:
        file_selected(str): Emitted when a file is clicked
        file_added(str): Emitted when a file is added to context
    """

    file_selected = Signal(str)
    file_added = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace: Optional[Path] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Filter files...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter_files)
        layout.addWidget(self._search)

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(16)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._tree, 1)

    def set_workspace(self, workspace: Path) -> None:
        """Set the workspace root and populate the tree."""
        self._workspace = workspace
        self._populate_tree()

    def _populate_tree(self) -> None:
        """Populate the tree with workspace files."""
        self._tree.clear()
        if self._workspace is None or not self._workspace.is_dir():
            return

        root_item = QTreeWidgetItem(self._tree)
        root_item.setText(0, f"📁 {self._workspace.name}")
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(self._workspace))
        root_item.setExpanded(True)

        self._add_children(root_item, self._workspace)

    def _add_children(self, parent: QTreeWidgetItem, path: Path) -> None:
        """Recursively add files and directories."""
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        count = 0
        for entry in entries:
            if entry.name.startswith(".") and entry.name != ".env":
                continue
            if entry.is_dir() and entry.name in SKIP_DIRS:
                continue

            item = QTreeWidgetItem(parent)
            item.setData(0, Qt.ItemDataRole.UserRole, str(entry))

            if entry.is_dir():
                icon = "📁"
                item.setText(0, f"{icon} {entry.name}")
                self._add_children(item, entry)
                if item.childCount() == 0:
                    parent.removeChild(item)
                    continue
            else:
                ext = entry.suffix.lower()
                icon = FILE_ICONS.get(ext, "📄")
                item.setText(0, f"{icon} {entry.name}")

            count += 1
            if count > 200:
                item = QTreeWidgetItem(parent)
                item.setText(0, f"... ({len(list(path.iterdir())) - count} more)")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                break

    def _filter_files(self, text: str) -> None:
        """Filter tree items by search text."""
        if not text:
            for i in range(self._tree.topLevelItemCount()):
                self._show_item(self._tree.topLevelItem(i), True)
            return

        text_lower = text.lower()
        for i in range(self._tree.topLevelItemCount()):
            self._filter_item(self._tree.topLevelItem(i), text_lower)

    def _filter_item(self, item: QTreeWidgetItem, text: str) -> bool:
        """Filter an item and its children. Returns True if visible."""
        visible = False
        for i in range(item.childCount()):
            if self._filter_item(item.child(i), text):
                visible = True

        item_text = item.text(0).lower()
        if text in item_text or visible:
            item.setHidden(False)
            if visible:
                item.setExpanded(True)
            return True
        else:
            item.setHidden(True)
            return False

    def _show_item(self, item: QTreeWidgetItem, show: bool) -> None:
        """Show/hide an item and its children."""
        item.setHidden(not show)
        for i in range(item.childCount()):
            self._show_item(item.child(i), show)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle file click."""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            self.file_selected.emit(path)

    def _show_context_menu(self, pos) -> None:
        """Show context menu for file operations."""
        item = self._tree.itemAt(pos)
        if item is None:
            return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path is None or not os.path.isfile(path):
            return

        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        add_action = menu.addAction("➕ Add to context")
        copy_path = menu.addAction("📋 Copy path")
        action = menu.exec(self._tree.viewport().mapToGlobal(pos))

        if action == add_action:
            self.file_added.emit(path)
        elif action == copy_path:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(path)
