"""
Production version of CustomTextEdit without debug prints
Use this to replace the debug version once paste functionality is confirmed working
"""

from PySide6.QtWidgets import QTextEdit
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence

class CustomTextEdit(QTextEdit):
    """Custom QTextEdit with proper Enter/Shift+Enter handling"""
    send_message = Signal()
    
    def keyPressEvent(self, event):
        """Handle Enter key press and preserve other shortcuts"""
        # Handle Enter/Return keys first
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Check if Shift is pressed
            if event.modifiers() & Qt.ShiftModifier:
                # Shift+Enter: insert new line
                self.insertPlainText("\n")
            else:
                # Enter only: send message
                self.send_message.emit()
                return  # Event handled
        
        # Handle standard shortcuts using QKeySequence matching
        elif event.matches(QKeySequence.StandardKey.Paste):
            # Handle Ctrl+V (paste)
            super().keyPressEvent(event)
            return
        elif event.matches(QKeySequence.StandardKey.Copy):
            # Handle Ctrl+C (copy)
            super().keyPressEvent(event)
            return
        elif event.matches(QKeySequence.StandardKey.Cut):
            # Handle Ctrl+X (cut)
            super().keyPressEvent(event)
            return
        elif event.matches(QKeySequence.StandardKey.Undo):
            # Handle Ctrl+Z (undo)
            super().keyPressEvent(event)
            return
        elif event.matches(QKeySequence.StandardKey.Redo):
            # Handle Ctrl+Y (redo)
            super().keyPressEvent(event)
            return
        elif event.matches(QKeySequence.StandardKey.SelectAll):
            # Handle Ctrl+A (select all)
            super().keyPressEvent(event)
            return
        
        # Fallback: Handle common shortcuts manually for better compatibility
        elif event.modifiers() & Qt.ControlModifier:
            key = event.key()
            if key == Qt.Key_V:  # Ctrl+V
                self.paste()
                return
            elif key == Qt.Key_C:  # Ctrl+C
                self.copy()
                return
            elif key == Qt.Key_X:  # Ctrl+X
                self.cut()
                return
            elif key == Qt.Key_A:  # Ctrl+A
                self.selectAll()
                return
            elif key == Qt.Key_Z:  # Ctrl+Z
                self.undo()
                return
            elif key == Qt.Key_Y:  # Ctrl+Y
                self.redo()
                return
        
        # For all other keys, use default behavior
        super().keyPressEvent(event)