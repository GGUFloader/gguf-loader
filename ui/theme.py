"""
Theme - Dark/light application theming.
"""

from __future__ import annotations

DARK_STYLESHEET = """
QMainWindow { background-color: #1e1e1e; color: #ffffff; }
QTextEdit, QLineEdit {
    background-color: #2d2d2d; color: #ffffff;
    border: 1px solid #404040; border-radius: 8px; padding: 8px;
}
QScrollArea { background-color: #1e1e1e; border: none; }
QScrollArea QWidget { background-color: #1e1e1e; }
QPushButton {
    background-color: #404040; color: #ffffff;
    border: 1px solid #555555; border-radius: 6px; padding: 6px 12px;
}
QPushButton:hover { background-color: #4a4a4a; }
QPushButton:pressed { background-color: #2a2a2a; }
QLabel { color: #ffffff; background-color: transparent; }
QCheckBox { color: #ffffff; background-color: transparent; }
QComboBox {
    background-color: #2d2d2d; color: #ffffff;
    border: 1px solid #404040; border-radius: 6px; padding: 4px 8px;
}
QComboBox::drop-down { border: none; }
QComboBox::down-arrow { color: #ffffff; }
QFrame { background-color: #1e1e1e; color: #ffffff; }
QSplitter::handle { background-color: #404040; }
QScrollBar:vertical { background-color: #2d2d2d; width: 12px; border-radius: 6px; }
QScrollBar::handle:vertical {
    background-color: #555555; border-radius: 6px; min-height: 20px;
}
QScrollBar::handle:vertical:hover { background-color: #666666; }
"""

LIGHT_STYLESHEET = """
QMainWindow { background-color: #ffffff; color: #000000; }
QTextEdit, QLineEdit {
    background-color: #ffffff; color: #000000;
    border: 1px solid #cccccc; border-radius: 8px; padding: 8px;
}
QScrollArea { background-color: #ffffff; border: none; }
QPushButton {
    background-color: #f0f0f0; color: #000000;
    border: 1px solid #cccccc; border-radius: 6px; padding: 6px 12px;
}
QPushButton:hover { background-color: #e0e0e0; }
"""


class ThemeMixin:
    """Mixin providing :meth:`apply_styles` for dark/light mode."""

    def apply_styles(self) -> None:
        stylesheet = DARK_STYLESHEET if getattr(self, "is_dark_mode", False) else LIGHT_STYLESHEET
        self.setStyleSheet(stylesheet)
