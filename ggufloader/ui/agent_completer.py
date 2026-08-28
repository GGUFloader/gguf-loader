"""
AgentCompleter - Tab-completion for filenames, commands, and tool names.

Inspired by Aider's AutoCompleter which uses tree-sitter to tokenize code
files and complete symbols. This implementation scans the workspace for
filenames and provides slash command completion.

Source: aider/aider/io.py AutoCompleter class
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QTextEdit


# Slash commands available in agent mode
SLASH_COMMANDS = [
    "/add",      # Add file to context
    "/drop",     # Remove file from context
    "/clear",    # Clear conversation
    "/undo",     # Undo last exchange
    "/help",     # Show available commands
    "/map",      # Show workspace file map
    "/diff",     # Show recent changes
    "/memory",   # Show working memory
    "/status",   # Show session status
    "/export",   # Export conversation
]


class AgentCompleter:
    """Provides tab-completion suggestions for the chat input.

    Scans workspace for filenames and provides slash command completion.
    """

    def __init__(self, workspace: Optional[Path] = None) -> None:
        self.workspace = workspace
        self._file_cache: List[str] = []
        self._cache_time: float = 0
        self._scan_workspace()

    def _scan_workspace(self) -> None:
        """Scan workspace for completable filenames."""
        if self.workspace is None or not self.workspace.is_dir():
            return
        try:
            files = []
            for root, dirs, names in os.walk(self.workspace):
                # Skip hidden dirs and common ignore patterns
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d not in ("__pycache__", "node_modules", ".venv", "venv",
                                  "dist", "build", ".git", ".idea", ".vscode")
                ]
                for name in names:
                    path = Path(root) / name
                    rel = str(path.relative_to(self.workspace))
                    files.append(rel)
                if len(files) > 500:
                    break
            self._file_cache = sorted(files)
        except Exception:  # noqa: BLE001
            self._file_cache = []

    def set_workspace(self, workspace: Path) -> None:
        """Update the workspace and rescan."""
        self.workspace = workspace
        self._scan_workspace()

    def get_completions(self, text: str, cursor_pos: int) -> List[str]:
        """Get completion suggestions for the current text.

        Args:
            text: The full text in the input
            cursor_pos: Cursor position

        Returns:
            List of completion strings
        """
        # Get the word being typed
        before = text[:cursor_pos]
        words = before.split()
        if not words:
            return []

        current_word = words[-1]

        # Slash command completion
        if current_word.startswith("/"):
            return self._complete_command(current_word)

        # If the last character is a space after /add or /drop, complete filenames
        if len(words) >= 2 and words[-2] in ("/add", "/drop"):
            return self._complete_filename(current_word)

        return []

    def _complete_command(self, prefix: str) -> List[str]:
        """Complete slash commands."""
        return [cmd for cmd in SLASH_COMMANDS if cmd.startswith(prefix)]

    def _complete_filename(self, prefix: str) -> List[str]:
        """Complete filenames from workspace."""
        if not self._file_cache:
            return []
        # Normalize prefix for matching
        prefix_lower = prefix.lower().replace("\\", "/")
        matches = []
        for f in self._file_cache:
            f_lower = f.lower()
            if f_lower.startswith(prefix_lower) or prefix_lower in f_lower:
                matches.append(f)
            if len(matches) >= 20:
                break
        return matches


class InputCompleter(QTextEdit):
    """QTextEdit with tab-completion support for the chat input."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._completer: Optional[AgentCompleter] = None
        self._showing_completions = False
        self._completion_popup = None

    def set_completer(self, completer: AgentCompleter) -> None:
        """Set the completer for this input."""
        self._completer = completer

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Handle Tab key for completion."""
        if event.key() == Qt.Key_Tab and self._completer is not None:
            text = self.toPlainText()
            cursor = self.textCursor().position()
            completions = self._completer.get_completions(text, cursor)
            if completions:
                self._apply_completion(text, cursor, completions[0])
                return
        super().keyPressEvent(event)

    def _apply_completion(self, text: str, cursor_pos: int, completion: str) -> None:
        """Apply a completion to the text."""
        before = text[:cursor_pos]
        words = before.split()
        if not words:
            return

        # Find the start of the current word
        current_word = words[-1]
        word_start = cursor_pos - len(current_word)

        # Replace the current word with the completion
        new_text = text[:word_start] + completion + text[cursor_pos:]
        self.setPlainText(new_text)
        # Position cursor after the completion
        cursor = self.textCursor()
        cursor.setPosition(word_start + len(completion))
        self.setTextCursor(cursor)
