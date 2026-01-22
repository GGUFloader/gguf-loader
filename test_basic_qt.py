#!/usr/bin/env python3
"""
Most basic Qt test possible - just QTextEdit with no customization
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QLabel, QPushButton

class BasicTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Basic Qt Test - No Custom Code")
        self.setGeometry(100, 100, 400, 200)
        
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("🧪 BASIC QT TEST - NO CUSTOM CODE"))
        layout.addWidget(QLabel("This is a completely standard QTextEdit with ZERO customization"))
        
        # Completely standard QTextEdit - no custom anything
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Standard QTextEdit - Ctrl+V MUST work here")
        layout.addWidget(self.text_edit)
        
        # Copy button
        copy_btn = QPushButton("Copy Test Text to Clipboard")
        copy_btn.clicked.connect(self.copy_text)
        layout.addWidget(copy_btn)
        
        self.status = QLabel("Click 'Copy Test Text' then try Ctrl+V above")
        layout.addWidget(self.status)
        
    def copy_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText("🧪 Basic test text for Ctrl+V")
        self.status.setText("✅ Text copied - try Ctrl+V in the text area")

if __name__ == "__main__":
    # Completely standard Qt application
    app = QApplication(sys.argv)
    window = BasicTestWindow()
    window.show()
    
    print("🧪 BASIC QT TEST")
    print("If Ctrl+V doesn't work here, the problem is with your Qt installation or system")
    print("If it works here but not in your app, something in your app is interfering")
    
    sys.exit(app.exec())