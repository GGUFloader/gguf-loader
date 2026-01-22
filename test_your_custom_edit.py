#!/usr/bin/env python3
"""
Test the exact CustomTextEdit from your application
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

# Copy the exact CustomTextEdit from your application
class YourCustomTextEdit(QTextEdit):
    """Exact copy of your CustomTextEdit"""
    send_message = Signal()
    
    def keyPressEvent(self, event):
        """Handle only Enter key, let Qt handle everything else"""
        # Only intercept Enter/Return keys
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                # Shift+Enter: use default behavior
                super().keyPressEvent(event)
            else:
                # Enter only: send message
                self.send_message.emit()
                return  # Don't call super()
        else:
            # For ALL other keys, use default Qt behavior
            super().keyPressEvent(event)

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Your Exact CustomTextEdit")
        self.setGeometry(100, 100, 500, 300)
        
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("🎯 Testing Your Exact CustomTextEdit Implementation"))
        
        # Standard QTextEdit for comparison
        layout.addWidget(QLabel("📝 Standard QTextEdit (should work):"))
        self.standard_edit = QTextEdit()
        self.standard_edit.setPlaceholderText("Standard QTextEdit - Ctrl+V reference")
        self.standard_edit.setMaximumHeight(50)
        layout.addWidget(self.standard_edit)
        
        # Your CustomTextEdit
        layout.addWidget(QLabel("🎯 Your CustomTextEdit (test this):"))
        self.custom_edit = YourCustomTextEdit()
        self.custom_edit.setPlaceholderText("Your CustomTextEdit - does Ctrl+V work?")
        self.custom_edit.setMaximumHeight(50)
        self.custom_edit.send_message.connect(lambda: self.status.setText("📤 Send message triggered"))
        layout.addWidget(self.custom_edit)
        
        # Copy button
        copy_btn = QPushButton("📋 Copy Test Text")
        copy_btn.clicked.connect(self.copy_text)
        layout.addWidget(copy_btn)
        
        # Status
        self.status = QLabel("Click 'Copy Test Text' then try Ctrl+V in both text areas")
        layout.addWidget(self.status)
        
    def copy_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText("🧪 Test text for your CustomTextEdit")
        self.status.setText("✅ Text copied - try Ctrl+V in both text areas above")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("🎯 Testing Your Exact CustomTextEdit")
    print("If Ctrl+V works in standard but not custom, the issue is in your keyPressEvent")
    print("If both fail, the issue is system-wide")
    
    sys.exit(app.exec())