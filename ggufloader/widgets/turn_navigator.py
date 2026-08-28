"""
TurnNavigator - Vertical rail for turn-by-turn navigation.

Inspired by DeepSeek Harness's TurnNavigator which provides a visual
rail on the right edge showing each conversation turn as a dot that
you can click to jump to.

Source: deepseek-harness/packages/client/ui-chat/src/client/chat/TurnNavigator.tsx
"""

from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout, QWidget


class TurnMark(QWidget):
    """A single turn mark (dot) on the navigator rail."""

    clicked = Signal(int)

    def __init__(self, turn_number: int, is_active: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.turn_number = turn_number
        self.is_active = is_active
        self.setFixedSize(12, 12)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Turn {turn_number}")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.is_active:
            painter.setBrush(QPen(Qt.GlobalColor.green).color())
        else:
            painter.setBrush(QPen(Qt.GlobalColor.gray).color())
        painter.drawEllipse(2, 2, 8, 8)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.clicked.emit(self.turn_number)
        super().mousePressEvent(event)


class TurnNavigator(QWidget):
    """Vertical rail showing conversation turns as clickable dots.

    Usage:
        navigator = TurnNavigator()
        navigator.set_turns(5)  # 5 turns
        navigator.set_active_turn(3)  # highlight turn 3
        navigator.turn_clicked.connect(lambda turn: jump_to(turn))
    """

    turn_clicked = Signal(int)

    TURN_SPACING = 14  # pixels between marks
    RAIL_INSET = 6     # padding at top/bottom

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._marks: List[TurnMark] = []
        self._active_turn: int = 0
        self.setFixedWidth(24)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def set_turns(self, count: int) -> None:
        """Set the number of turns to display."""
        # Clear existing marks
        for mark in self._marks:
            mark.setParent(None)
        self._marks.clear()

        # Create new marks
        for i in range(count):
            mark = TurnMark(i, is_active=(i == self._active_turn))
            mark.clicked.connect(self._on_mark_clicked)
            self._marks.append(mark)

        self._layout_marks()

    def set_active_turn(self, turn: int) -> None:
        """Highlight the active turn."""
        self._active_turn = turn
        for mark in self._marks:
            mark.is_active = (mark.turn_number == turn)
            mark.update()

    def add_turn(self) -> int:
        """Add a new turn and return its index."""
        turn = len(self._marks)
        mark = TurnMark(turn, is_active=False)
        mark.clicked.connect(self._on_mark_clicked)
        self._marks.append(mark)
        self._layout_marks()
        return turn

    def _layout_marks(self) -> None:
        """Position marks vertically."""
        # Remove old marks from layout
        for mark in self._marks:
            if mark.parentWidget() == self:
                mark.setParent(None)

        # Reparent and position
        y = self.RAIL_INSET
        for mark in self._marks:
            mark.setParent(self)
            mark.move(6, y)
            mark.show()
            y += self.TURN_SPACING

        self.setFixedHeight(y + self.RAIL_INSET)
        self.update()

    def _on_mark_clicked(self, turn: int) -> None:
        """Handle click on a turn mark."""
        self.set_active_turn(turn)
        self.turn_clicked.emit(turn)

    def paintEvent(self, event) -> None:  # noqa: N802
        """Draw the connecting rail line."""
        if len(self._marks) < 2:
            return
        painter = QPainter(self)
        painter.setPen(QPen(Qt.GlobalColor.gray, 1))
        x = 11  # center of marks
        y_start = self.RAIL_INSET + 6  # center of first mark
        y_end = self.RAIL_INSET + (len(self._marks) - 1) * self.TURN_SPACING + 6
        painter.drawLine(x, y_start, x, y_end)
        painter.end()
