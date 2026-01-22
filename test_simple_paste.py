#!/usr/bin/env python3
"""
Simple test to verify Ctrl+V and other shortcuts work in CustomTextEdit
"""

import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QLabel, QPushButton, QHBoxLayout, QTextEdit)
from PySide6.QtCore import Qt

# Import the custom text edit
from mixins.ui_setup_mixin import CustomTextEdit

class SimpleTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Paste Test")
        self.setGeometry(100, 100, 500, 300)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Instructions
        instructions = QLabel("""
🧪 SIMPLE SHORTCUT TEST

1. Click 'Copy Test Text' to put text in clipboard
2. Click in the CustomTextEdit below
3. Press Ctrl+V to paste
4. Try other shortcuts: Ctrl+A, Ctrl+C, Ctrl+Z
5. Test Enter (should trigger send) vs Shift+Enter (new line)
        """)
        instructions.setStyleSheet("background: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(instructions)
        
        # Regular QTextEdit for comparison
        layout.addWidget(QLabel("📝 Regular QTextEdit (for comparison):"))
        self.regular_edit = QTextEdit()
        self.regular_edit.setPlaceholderText("Regular QTextEdit - all shortcuts should work here")
        self.regular_edit.setMaximumHeight(60)
        layout.addWidget(self.regular_edit)
        
        # Custom QTextEdit
        layout.addWidget(QLabel("🎯 CustomTextEdit (the one with issues):"))
        self.custom_edit = CustomTextEdit()
        self.custom_edit.setPlaceholderText("CustomTextEdit - test Ctrl+V here")
        self.custom_edit.setMaximumHeight(60)
        self.custom_edit.send_message.connect(self.on_send_message)
        layout.addWidget(self.custom_edit)
        
        # Test buttons
        button_layout = QHBoxLayout()
        
        copy_btn = QPushButton("📋 Copy Test Text")
        copy_btn.clicked.connect(self.copy_test_text)
        button_layout.addWidget(copy_btn)
        
        check_btn = QPushButton("👀 Check Clipboard")
        check_btn.clicked.connect(self.check_clipboard)
        button_layout.addWidget(check_btn)
        
        layout.addLayout(button_layout)
        
        # Status
        self.status = QLabel("Click 'Copy Test Text' then try Ctrl+V in the text areas")
        self.status.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status)
        
    def copy_test_text(self):
        """Copy test text to clipboard"""
        test_text = "Hello! This is test text for pasting with Ctrl+V."
        clipboard = QApplication.clipboard()
        clipboard.setText(test_text)
        self.status.setText(f"✅ Copied: '{test_text}'")
        self.status.setStyleSheet("color: green;")
        
    def check_clipboard(self):
        """Check clipboard content"""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.status.setText(f"📋 Clipboard: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            self.status.setStyleSheet("color: blue;")
        else:
            self.status.setText("❌ Clipboard is empty")
            self.status.setStyleSheet("color: red;")
    
    def on_send_message(self):
        """Handle send message from CustomTextEdit"""
        text = self.custom_edit.toPlainText()
        self.status.setText(f"📤 Send triggered: '{text[:30]}{'...' if len(text) > 30 else ''}'")
        self.status.setStyleSheet("color: purple;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleTestWindow()
    window.show()
    
    print("🧪 Simple Paste Test")
    print("Compare behavior between regular QTextEdit and CustomTextEdit")
    print("Both should support Ctrl+V, Ctrl+C, Ctrl+A, etc.")
    
    sys.exit(app.exec())