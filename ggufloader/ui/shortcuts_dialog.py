"""
ShortcutsDialog - Keyboard shortcuts reference dialog.

Shows all available keyboard shortcuts organized by category.
Pattern from: VS Code Keyboard Shortcuts reference + GitHub shortcuts.

Shortcut: Ctrl+/ (Ctrl+Shift+/)
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
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


# All keyboard shortcuts organized by category
SHORTCUTS = [
    ("General", [
        ("Ctrl+N", "New chat"),
        ("Ctrl+L", "Clear chat"),
        ("Ctrl+F", "Search in conversation"),
        ("Ctrl+/", "Keyboard shortcuts reference"),
        ("Esc", "Stop generation / Close dialogs"),
    ]),
    ("Agent Mode", [
        ("Ctrl+M", "Toggle agent mode ON/OFF"),
        ("Ctrl+,", "Open agent settings"),
        ("Ctrl+Enter", "Submit message (same as Enter)"),
        ("Shift+Enter", "New line in input"),
    ]),
    ("Chat", [
        ("Enter", "Send message"),
        ("Shift+Enter", "Insert newline"),
        ("Ctrl+Shift+C", "Copy conversation"),
        ("Ctrl+E", "Export conversation"),
    ]),
    ("Navigation", [
        ("Ctrl+Tab", "Switch session tabs"),
        ("Ctrl+W", "Close current tab"),
    ]),
    ("Model", [
        ("Ctrl+O", "Load GGUF model"),
        ("Ctrl+G", "Toggle GPU acceleration"),
    ]),
]


class ShortcutsDialog(QDialog):
    """Keyboard shortcuts reference dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(480, 520)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("⌨️ Keyboard Shortcuts")
        title.setObjectName("panelTitle")
        title.setFont(QFont(FONT_FAMILY, 15, QFont.Bold))
        layout.addWidget(title)

        subtitle = QLabel("Press any shortcut to perform the action")
        subtitle.setObjectName("mutedLabel")
        layout.addWidget(subtitle)

        # Scroll area for shortcuts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)

        for category, shortcuts in SHORTCUTS:
            # Category header
            cat_label = QLabel(category.upper())
            cat_label.setObjectName("sectionEyebrow")
            cat_label.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
            content_layout.addWidget(cat_label)

            # Shortcuts grid
            grid = QGridLayout()
            grid.setSpacing(4)
            for i, (key, description) in enumerate(shortcuts):
                key_label = QLabel(key)
                key_label.setObjectName("shortcutKey")
                key_label.setFont(QFont("Consolas", 10))
                key_label.setStyleSheet(
                    "background: #374151; color: #e5e7eb; padding: 3px 8px; "
                    "border-radius: 4px; border: 1px solid #4b5563;"
                )
                key_label.setFixedWidth(120)
                key_label.setAlignment(Qt.AlignCenter)

                desc_label = QLabel(description)
                desc_label.setStyleSheet("color: #d1d5db; font-size: 11px;")

                grid.addWidget(key_label, i, 0)
                grid.addWidget(desc_label, i, 1)

            content_layout.addLayout(grid)

            # Separator
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet("color: #374151;")
            content_layout.addWidget(sep)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryButton")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)
