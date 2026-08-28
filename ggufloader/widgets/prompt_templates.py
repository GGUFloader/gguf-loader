"""
PromptTemplates - Pre-built prompt templates for common agent tasks.

Shows a grid of clickable template cards. Each card inserts a ready-made
prompt into the chat input.

Pattern from: Aider's /ask command presets + ChatGPT prompt starters.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


TEMPLATES = [
    {
        "category": "Code",
        "items": [
            {
                "icon": "🐛",
                "title": "Debug Error",
                "prompt": "I'm getting an error. Here's the traceback:\n\n[paste error]\n\nFind the root cause and fix it.",
            },
            {
                "icon": "♻️",
                "title": "Refactor Code",
                "prompt": "Review this code for improvements. Suggest refactoring for readability, performance, and maintainability.",
            },
            {
                "icon": "📝",
                "title": "Write Tests",
                "prompt": "Write comprehensive unit tests for this code. Cover edge cases and error handling.",
            },
            {
                "icon": "📖",
                "title": "Explain Code",
                "prompt": "Explain this code step by step. What does each part do? What's the overall architecture?",
            },
        ],
    },
    {
        "category": "Files",
        "items": [
            {
                "icon": "🔍",
                "title": "Find & Fix",
                "prompt": "Search the workspace for all files related to [topic]. Analyze them and suggest fixes.",
            },
            {
                "icon": "📊",
                "title": "Project Overview",
                "prompt": "Give me a complete overview of this project. List all files, their purposes, and the architecture.",
            },
            {
                "icon": "🗑",
                "title": "Clean Up",
                "prompt": "Find unused files, dead code, and outdated dependencies. Suggest what to remove.",
            },
            {
                "icon": "📦",
                "title": "Package Files",
                "prompt": "Create a new Python package/module at [path]. Include __init__.py, setup.py, and basic structure.",
            },
        ],
    },
    {
        "category": "Git",
        "items": [
            {
                "icon": "📝",
                "title": "Write Commit",
                "prompt": "Stage all changes and write a clear, concise commit message following conventional commits.",
            },
            {
                "icon": "🔍",
                "title": "Review Changes",
                "prompt": "Show me all uncommitted changes. Review them for issues and suggest improvements.",
            },
            {
                "icon": "🔀",
                "title": "Merge Conflict",
                "prompt": "Help me resolve the merge conflict in [file]. Understand both sides and choose the best resolution.",
            },
        ],
    },
    {
        "category": "Docs",
        "items": [
            {
                "icon": "📄",
                "title": "Write README",
                "prompt": "Write a comprehensive README.md for this project. Include installation, usage, and examples.",
            },
            {
                "icon": "📝",
                "title": "Add Docstrings",
                "prompt": "Add detailed docstrings to all public functions and classes in this file.",
            },
            {
                "icon": "🔄",
                "title": "Update Docs",
                "prompt": "Review the documentation for accuracy. Update any outdated information and add missing sections.",
            },
        ],
    },
]


class PromptTemplateCard(QFrame):
    """A single clickable prompt template card."""

    template_selected = Signal(str)

    def __init__(self, template: dict, parent=None):
        super().__init__(parent)
        self._template = template
        self.setObjectName("templateCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(60)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        icon = QLabel(self._template["icon"])
        icon.setFont(QFont(FONT_FAMILY, 16))
        layout.addWidget(icon)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title = QLabel(self._template["title"])
        title.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        text_layout.addWidget(title)

        # Show first line of prompt as description
        desc = self._template["prompt"].split("\n")[0][:60]
        desc_label = QLabel(desc)
        desc_label.setObjectName("mutedLabel")
        desc_label.setStyleSheet("font-size: 9px; color: #6b7280;")
        text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        # Hover effect
        self.setStyleSheet(
            "QFrame { background: #1f2937; border-radius: 6px; border: 1px solid #374151; }"
            "QFrame:hover { background: #283040; border: 1px solid #4b5563; }"
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.template_selected.emit(self._template["prompt"])


class PromptTemplates(QWidget):
    """Prompt template selector with categorized cards.

    Usage:
        templates = PromptTemplates()
        templates.prompt_selected.connect(lambda text: input.setText(text))
    """

    prompt_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("promptTemplates")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("📋 Prompt Templates")
        title.setObjectName("sectionEyebrow")
        title.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        header.addWidget(title)
        header.addStretch()

        self._toggle_btn = QPushButton("▼")
        self._toggle_btn.setFixedSize(20, 20)
        self._toggle_btn.setStyleSheet("border: none; font-size: 8px;")
        self._toggle_btn.clicked.connect(self._toggle)
        header.addWidget(self._toggle_btn)
        layout.addLayout(header)

        # Scrollable content
        self._content = QScrollArea()
        self._content.setWidgetResizable(True)
        self._content.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._content.setMaximumHeight(400)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(8)

        for category in TEMPLATES:
            cat_label = QLabel(category["category"].upper())
            cat_label.setObjectName("sectionEyebrow")
            cat_label.setFont(QFont(FONT_FAMILY, 8, QFont.Bold))
            content_layout.addWidget(cat_label)

            grid = QGridLayout()
            grid.setSpacing(4)
            for i, template in enumerate(category["items"]):
                card = PromptTemplateCard(template)
                card.template_selected.connect(self.prompt_selected.emit)
                row, col = divmod(i, 2)
                grid.addWidget(card, row, col)

            content_layout.addLayout(grid)

        content_layout.addStretch()
        self._content.setWidget(content_widget)
        layout.addWidget(self._content)

        self._expanded = True

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._toggle_btn.setText("▼" if self._expanded else "▶")
