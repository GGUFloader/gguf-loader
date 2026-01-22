#!/usr/bin/env python3
"""
Minimal test of CustomTextEdit in isolation
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence

class MinimalCustomTextEdit(QTextEdit):
    """Minimal custom text edit for testing"""
    send_message = Signal()
    
    def keyPressEvent(self, event):
        """Handle only Enter key, let Qt handle everything else"""
        print(f"🔍 Key event: key={event.key()}, modifiers={event.modifiers()}, text='{event.text()}'")
        
        # Only intercept Enter/Return keys
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                print("📝 Shift+Enter: Using default behavior")
                super().keyPressEvent(event)
            else:
                print("📤 Enter: Emitting send_message signal")
                self.send_message.emit()
                return  # Don't call super()
        else:
            print("⚡ Other key: Using default Qt behavior")
            super().keyPressEvent(event)

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minimal CustomTextEdit Test")
        self.setGeometry(100, 100, 400, 250)
        
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("🧪 Test Ctrl+V in the text area below:"))
        
        # Test widget
        self.text_edit = MinimalCustomTextEdit()
        self.text_edit.setPlaceholderText("Try Ctrl+V here...")
        self.text_edit.send_message.connect(self.on_send)
        layout.addWidget(self.text_edit)
        
        # Copy button
        copy_btn = QPushButton("Copy Test Text to Clipboard")
        copy_btn.clicked.connect(self.copy_text)
        layout.addWidget(copy_btn)
        
        # Status
        self.status = QLabel("Ready")
        layout.addWidget(self.status)
        
    def copy_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText("This is test text for Ctrl+V")
        self.status.setText("✅ Test text copied to clipboard - now try Ctrl+V")
        
    def on_send(self):
        text = self.text_edit.toPlainText()
        self.status.setText(f"📤 Send triggered: '{text[:30]}'")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("🧪 Minimal CustomTextEdit Test")
    print("Watch console for key event debugging")
    print("Test: Copy text, then Ctrl+V in text area")
    
    sys.exit(app.exec())