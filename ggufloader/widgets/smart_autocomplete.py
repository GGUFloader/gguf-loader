"""
SmartAutocomplete - Context-aware autocomplete for agent input.

Pattern from: Aider's AutoCompleter + VS Code IntelliSense.
Provides intelligent suggestions as the user types:
- File path completion (relative to workspace)
- Command completion (git, python, pip, etc.)
- Slash command completion
- Recent file suggestions
- Model-aware suggestions (e.g., /add for files the model mentioned)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Set

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


class SuggestionItem:
    """A single autocomplete suggestion."""

    def __init__(self, text: str, category: str, description: str = "",
                 icon: str = "") -> None:
        self.text = text
        self.category = category
        self.description = description
        self.icon = icon or self._default_icon(category)

    def _default_icon(self, category: str) -> str:
        icons = {
            "file": "📄",
            "directory": "📁",
            "command": "⚡",
            "slash": "🔧",
            "history": "🕐",
        }
        return icons.get(category, "•")


class SmartAutocomplete(QWidget):
    """Context-aware autocomplete dropdown.

    Usage:
        autocomplete = SmartAutocomplete(workspace_path)
        autocomplete.update_context(workspace_files, recent_commands)
        suggestions = autocomplete.get_suggestions("rea")
        # Returns: [("read_file", "file", "README.md"), ...]
    """

    suggestion_selected = Signal(str)

    def __init__(self, workspace: Path = None, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        self._files: List[str] = []
        self._directories: List[str] = []
        self._commands: List[str] = [
            "git status", "git diff", "git log", "git add", "git commit",
            "python", "pip install", "pip list",
            "ls", "pwd", "cat", "grep", "find",
            "npm test", "npm install", "npm run",
            "cargo build", "cargo test",
            "go test", "go build",
        ]
        self._slash_commands: List[str] = [
            "/add", "/drop", "/clear", "/undo", "/help",
            "/map", "/diff", "/memory", "/status", "/export",
            "/workspace", "/mode", "/debug", "/review",
        ]
        self._recent_files: List[str] = []
        self._build_ui()
        self.setVisible(False)

    def _build_ui(self) -> None:
        self.setObjectName("smartAutocomplete")
        self.setFixedHeight(200)
        self.setFixedWidth(350)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._list = QListWidget()
        self._list.setObjectName("autocompleteList")
        self._list.setAlternatingRowColors(True)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

    def update_context(self, files: List[str] = None,
                       directories: List[str] = None,
                       recent_files: List[str] = None) -> None:
        """Update the autocomplete context."""
        if files is not None:
            self._files = files
        if directories is not None:
            self._directories = directories
        if recent_files is not None:
            self._recent_files = recent_files

    def scan_workspace(self) -> None:
        """Scan the workspace for files and directories."""
        if not self.workspace:
            return

        self._files.clear()
        self._directories.clear()

        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                       ("__pycache__", "node_modules", ".venv", "venv", ".git")]

            rel_root = os.path.relpath(root, self.workspace)
            if rel_root != ".":
                self._directories.append(rel_root.replace("\\", "/"))

            for f in files:
                if f.startswith("."):
                    continue
                rel_path = os.path.join(rel_root, f).replace("\\", "/")
                if rel_path.startswith("./"):
                    rel_path = rel_path[2:]
                self._files.append(rel_path)

    def get_suggestions(self, text: str, limit: int = 10) -> List[SuggestionItem]:
        """Get autocomplete suggestions for the given text."""
        if not text:
            return self._get_default_suggestions()

        text_lower = text.lower()
        suggestions: List[SuggestionItem] = []

        # Slash commands
        if text.startswith("/"):
            for cmd in self._slash_commands:
                if cmd.lower().startswith(text_lower):
                    suggestions.append(SuggestionItem(cmd, "slash"))

        # File paths
        for f in self._files:
            if text_lower in f.lower():
                suggestions.append(SuggestionItem(f, "file"))
                if len(suggestions) >= limit:
                    break

        # Directories
        for d in self._directories:
            if text_lower in d.lower():
                suggestions.append(SuggestionItem(d, "directory"))

        # Commands
        for cmd in self._commands:
            if text_lower in cmd.lower():
                suggestions.append(SuggestionItem(cmd, "command"))

        # Recent files
        for f in self._recent_files:
            if text_lower in f.lower() and not any(s.text == f for s in suggestions):
                suggestions.append(SuggestionItem(f, "history"))

        return suggestions[:limit]

    def _get_default_suggestions(self) -> List[SuggestionItem]:
        """Show recent files and common commands when input is empty."""
        suggestions = []
        for f in self._recent_files[:5]:
            suggestions.append(SuggestionItem(f, "history"))
        for cmd in ["git status", "python", "pip install"][:3]:
            suggestions.append(SuggestionItem(cmd, "command"))
        return suggestions

    def show_suggestions(self, suggestions: List[SuggestionItem]) -> None:
        """Display suggestions in the dropdown."""
        self._list.clear()
        if not suggestions:
            self.setVisible(False)
            return

        for item in suggestions:
            display = f"{item.icon} {item.text}"
            list_item = QListWidgetItem(display)
            list_item.setData(Qt.UserRole, item.text)
            self._list.addItem(list_item)

        self._list.setCurrentRow(0)
        self.setVisible(True)

    def get_selected(self) -> Optional[str]:
        """Get the currently selected suggestion text."""
        item = self._list.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None

    def _on_row_changed(self, row: int) -> None:
        pass

    def _on_double_click(self, item: QListWidgetItem) -> None:
        text = item.data(Qt.UserRole)
        if text:
            self.suggestion_selected.emit(text)
            self.setVisible(False)

    def key_press_event(self, event) -> bool:
        """Handle key navigation in the autocomplete list."""
        if not self.isVisible():
            return False

        if event.key() == Qt.Key_Down:
            row = self._list.currentRow()
            if row < self._list.count() - 1:
                self._list.setCurrentRow(row + 1)
            return True
        elif event.key() == Qt.Key_Up:
            row = self._list.currentRow()
            if row > 0:
                self._list.setCurrentRow(row - 1)
            return True
        elif event.key() in (Qt.Key_Return, Qt.Key_Tab):
            text = self.get_selected()
            if text:
                self.suggestion_selected.emit(text)
                self.setVisible(False)
            return True
        elif event.key() == Qt.Key_Escape:
            self.setVisible(False)
            return True

        return False
