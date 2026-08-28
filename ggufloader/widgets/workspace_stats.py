"""
WorkspaceStats - Compact workspace statistics display.

Shows:
- Total files, total size
- Language breakdown (file counts by extension)
- Total lines of code
- Git status (branch, uncommitted changes)

Pattern from: GitHub repo sidebar + VS Code status bar.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY

# Extension to language mapping
_EXT_MAP = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "React", ".tsx": "React TS",
    ".rs": "Rust", ".go": "Go", ".java": "Java",
    ".c": "C", ".cpp": "C++", ".h": "C/C++", ".hpp": "C++",
    ".rb": "Ruby", ".php": "PHP",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML", ".xml": "XML",
    ".md": "Markdown", ".txt": "Text", ".rst": "RST",
    ".sql": "SQL", ".sh": "Shell", ".bat": "Batch",
    ".r": "R", ".swift": "Swift", ".kt": "Kotlin",
}

_SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".idea", ".vscode", ".eggs",
})


class WorkspaceStats(QWidget):
    """Compact workspace statistics display.

    Usage:
        stats = WorkspaceStats()
        stats.update_workspace(Path("/path/to/project"))
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workspaceStats")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QLabel("📊 Workspace Stats")
        header.setObjectName("sectionEyebrow")
        header.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        layout.addWidget(header)

        # Grid of stats
        grid = QGridLayout()
        grid.setSpacing(3)
        grid.setContentsMargins(8, 4, 8, 4)

        self._total_files = self._stat_row("Files", "—", grid, 0)
        self._total_loc = self._stat_row("Lines", "—", grid, 1)
        self._total_size = self._stat_row("Size", "—", grid, 2)
        self._git_branch = self._stat_row("Git", "—", grid, 3)

        layout.addLayout(grid)

        # Language breakdown
        self._lang_label = QLabel("")
        self._lang_label.setObjectName("mutedLabel")
        self._lang_label.setWordWrap(True)
        self._lang_label.setStyleSheet("font-size: 9px; padding: 0 8px;")
        layout.addWidget(self._lang_label)

    def _stat_row(self, name: str, value: str,
                  grid: QGridLayout, row: int) -> QLabel:
        label_name = QLabel(f"{name}:")
        label_name.setStyleSheet("color: #9ca3af; font-size: 9px;")
        label_value = QLabel(value)
        label_value.setStyleSheet("font-size: 9px; font-weight: bold;")
        grid.addWidget(label_name, row, 0)
        grid.addWidget(label_value, row, 1)
        return label_value

    def update_workspace(self, workspace: Path) -> None:
        """Scan workspace and update statistics."""
        if not workspace.is_dir():
            self._total_files.setText("—")
            self._total_loc.setText("—")
            self._total_size.setText("—")
            self._lang_label.setText("")
            return

        total_files = 0
        total_loc = 0
        total_size = 0
        lang_counts: dict[str, int] = {}

        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
            for name in files:
                if name.startswith("."):
                    continue
                path = Path(root) / name
                total_files += 1
                try:
                    size = path.stat().st_size
                    total_size += size
                except OSError:
                    continue

                ext = path.suffix.lower()
                lang = _EXT_MAP.get(ext, ext.lstrip(".").upper() if ext else "Other")
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

                # Count lines for text files
                if ext in {".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go",
                           ".java", ".c", ".cpp", ".h", ".rb", ".php", ".sql",
                           ".sh", ".html", ".css", ".scss", ".json", ".yaml",
                           ".yml", ".toml", ".md", ".txt", ".r", ".swift"}:
                    try:
                        with open(path, "r", encoding="utf-8", errors="replace") as f:
                            total_loc += sum(1 for _ in f)
                    except (OSError, UnicodeDecodeError):
                        pass

        self._total_files.setText(str(total_files))
        self._total_loc.setText(f"{total_loc:,}")
        self._total_size.setText(self._format_size(total_size))

        # Git branch
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=workspace, capture_output=True, text=True, timeout=5,
            )
            branch = result.stdout.strip()
            self._git_branch.setText(branch if branch else "detached")
        except Exception:
            self._git_branch.setText("—")

        # Language breakdown (top 5)
        sorted_langs = sorted(lang_counts.items(), key=lambda x: -x[1])[:5]
        if sorted_langs:
            lang_text = " · ".join(f"{lang}: {count}" for lang, count in sorted_langs)
            self._lang_label.setText(lang_text)
        else:
            self._lang_label.setText("")

    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.1f} GB"
