#!/usr/bin/env python3
"""
Test script to verify Enter key behavior in QTextEdit
"""
import sys
from PySide6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent

class TestTextEdit(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setPlaceholderText("Press Enter to send, Shift+Enter for new line")
        
    def eventFilter(self, obj, event):
        """Handle Enter key press in input field"""
        if obj == self and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                # Check if Shift is pressed
                if event.modifiers() & Qt.ShiftModifier:
                    # Shift+Enter: insert new line
                    cursor = self.textCursor()
                    cursor.insertText('\n')
                    return True  # Event handled, don't propagate
                else:
                    # Enter only: send message
                    print("Message sent:", self.toPlainText())
                    self.clear()
                    return True  # Event handled, don't propagate
        return super().eventFilter(obj, event)

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enter Key Behavior Test")
        layout = QVBoxLayout(self)
        
        label = QLabel("Test Enter key behavior:\n- Enter: Send message\n- Shift+Enter: New line")
        layout.addWidget(label)
        
        self.text_edit = TestTextEdit()
        self.text_edit.installEventFilter(self.text_edit)
        layout.addWidget(self.text_edit)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())