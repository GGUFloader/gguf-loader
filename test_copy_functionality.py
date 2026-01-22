#!/usr/bin/env python3
"""
Test script to verify text selection and copy functionality
"""

import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QLabel, QTextEdit, QPushButton, QHBoxLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard

class CopyTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Copy Functionality Test")
        self.setGeometry(100, 100, 500, 400)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Test QLabel with proper text selection
        layout.addWidget(QLabel("Test QLabel (should be selectable and copyable):"))
        self.test_label = QLabel("This is a test QLabel. Select this text and try Ctrl+C or right-click -> Copy")
        self.test_label.setWordWrap(True)
        self.test_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.test_label.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.test_label.setStyleSheet("border: 1px solid #ccc; padding: 10px; background: #f9f9f9;")
        layout.addWidget(self.test_label)
        
        # Test QTextEdit (should work by default)
        layout.addWidget(QLabel("Test QTextEdit (should work by default):"))
        self.test_textedit = QTextEdit()
        self.test_textedit.setPlainText("This is a test QTextEdit. Select this text and try Ctrl+C or right-click -> Copy")
        self.test_textedit.setMaximumHeight(80)
        layout.addWidget(self.test_textedit)
        
        # Test readonly QTextEdit
        layout.addWidget(QLabel("Test readonly QTextEdit:"))
        self.test_readonly = QTextEdit()
        self.test_readonly.setPlainText("This is a readonly QTextEdit. Select this text and try Ctrl+C or right-click -> Copy")
        self.test_readonly.setReadOnly(True)
        self.test_readonly.setMaximumHeight(80)
        layout.addWidget(self.test_readonly)
        
        # Button to check clipboard
        button_layout = QHBoxLayout()
        check_clipboard_btn = QPushButton("Check Clipboard Content")
        check_clipboard_btn.clicked.connect(self.check_clipboard)
        button_layout.addWidget(check_clipboard_btn)
        
        clear_clipboard_btn = QPushButton("Clear Clipboard")
        clear_clipboard_btn.clicked.connect(self.clear_clipboard)
        button_layout.addWidget(clear_clipboard_btn)
        
        layout.addLayout(button_layout)
        
        # Clipboard display
        layout.addWidget(QLabel("Current clipboard content:"))
        self.clipboard_display = QTextEdit()
        self.clipboard_display.setMaximumHeight(100)
        self.clipboard_display.setReadOnly(True)
        layout.addWidget(self.clipboard_display)
        
        # Instructions
        instructions = QLabel("""
Instructions:
1. Select text in any of the widgets above
2. Try Ctrl+C to copy
3. Try right-click -> Copy
4. Click 'Check Clipboard Content' to see if it worked
        """)
        instructions.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(instructions)
        
    def check_clipboard(self):
        """Check and display current clipboard content"""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.clipboard_display.setPlainText(f"Clipboard contains: {text}")
            print(f"Clipboard content: {text}")
        else:
            self.clipboard_display.setPlainText("Clipboard is empty")
            print("Clipboard is empty")
    
    def clear_clipboard(self):
        """Clear the clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.clear()
        self.clipboard_display.setPlainText("Clipboard cleared")
        print("Clipboard cleared")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CopyTestWindow()
    window.show()
    
    print("Copy Functionality Test")
    print("- Select text in any widget")
    print("- Try Ctrl+C or right-click -> Copy")
    print("- Click 'Check Clipboard Content' to verify")
    
    sys.exit(app.exec())