#!/usr/bin/env python3
"""
Minimal test to isolate the Ctrl key issue
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence

# Test 1: Completely standard QTextEdit
class StandardTextEdit(QTextEdit):
    """Standard QTextEdit with no modifications"""
    pass

# Test 2: QTextEdit with minimal keyPressEvent override
class MinimalCustomTextEdit(QTextEdit):
    """QTextEdit with minimal custom keyPressEvent"""
    send_message = Signal()
    
    def keyPressEvent(self, event):
        print(f"MinimalCustomTextEdit.keyPressEvent: key={event.key()}, modifiers={event.modifiers()}")
        
        # Only handle Enter, everything else goes to Qt
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            print("Enter pressed - emitting send_message")
            self.send_message.emit()
            return
        
        print("Calling super().keyPressEvent()")
        super().keyPressEvent(event)

# Test 3: QTextEdit that logs but doesn't interfere
class LoggingTextEdit(QTextEdit):
    """QTextEdit that logs all events but doesn't interfere"""
    
    def keyPressEvent(self, event):
        print(f"LoggingTextEdit.keyPressEvent: key={event.key()}, modifiers={event.modifiers()}")
        print("Always calling super().keyPressEvent()")
        super().keyPressEvent(event)

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ctrl Key Issue Test")
        self.setGeometry(100, 100, 600, 500)
        
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        
        # Instructions
        instructions = QLabel("""
🔍 CTRL KEY ISSUE DIAGNOSIS

Test Ctrl+V in each text area below. Watch console output.

Expected behavior: Ctrl+V should paste in ALL text areas.
If it doesn't work in some but works in others, we've found the issue.
        """)
        instructions.setStyleSheet("background: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(instructions)
        
        # Test 1: Standard QTextEdit
        layout.addWidget(QLabel("1️⃣ Standard QTextEdit (baseline):"))
        self.standard_edit = StandardTextEdit()
        self.standard_edit.setPlaceholderText("Standard QTextEdit - Ctrl+V should work")
        self.standard_edit.setMaximumHeight(50)
        layout.addWidget(self.standard_edit)
        
        # Test 2: Logging QTextEdit
        layout.addWidget(QLabel("2️⃣ Logging QTextEdit (logs but doesn't interfere):"))
        self.logging_edit = LoggingTextEdit()
        self.logging_edit.setPlaceholderText("Logging QTextEdit - Ctrl+V should work")
        self.logging_edit.setMaximumHeight(50)
        layout.addWidget(self.logging_edit)
        
        # Test 3: Minimal Custom QTextEdit
        layout.addWidget(QLabel("3️⃣ Minimal Custom QTextEdit (only handles Enter):"))
        self.minimal_edit = MinimalCustomTextEdit()
        self.minimal_edit.setPlaceholderText("Minimal Custom QTextEdit - test Ctrl+V")
        self.minimal_edit.setMaximumHeight(50)
        self.minimal_edit.send_message.connect(lambda: print("Send message signal emitted"))
        layout.addWidget(self.minimal_edit)
        
        # Copy button
        copy_btn = QPushButton("📋 Copy Test Text to Clipboard")
        copy_btn.clicked.connect(self.copy_text)
        layout.addWidget(copy_btn)
        
        # Status
        self.status = QLabel("Click 'Copy Test Text' then try Ctrl+V in each text area above")
        self.status.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status)
        
    def copy_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText("🧪 Test text for Ctrl+V diagnosis")
        self.status.setText("✅ Text copied - now try Ctrl+V in each text area above")
        self.status.setStyleSheet("color: green;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("🔍 CTRL KEY ISSUE DIAGNOSIS")
    print("=" * 40)
    print("Watch console output when you press keys")
    print("Test Ctrl+V in each text area")
    print("If Ctrl+V works in #1 but not #3, the issue is in the keyPressEvent override")
    print("=" * 40)
    
    sys.exit(app.exec())