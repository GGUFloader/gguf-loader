#!/usr/bin/env python3
"""
Test to check if global shortcuts are interfering with text input
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShortcut, QKeySequence

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shortcut Interference Test")
        self.setGeometry(100, 100, 500, 300)
        
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        
        # Instructions
        layout.addWidget(QLabel("🧪 Testing if global shortcuts interfere with text input"))
        
        # Regular QTextEdit (should always work)
        layout.addWidget(QLabel("📝 Regular QTextEdit (baseline):"))
        self.regular_edit = QTextEdit()
        self.regular_edit.setPlaceholderText("Regular QTextEdit - Ctrl+V should work here")
        self.regular_edit.setMaximumHeight(60)
        layout.addWidget(self.regular_edit)
        
        # Test with global shortcuts
        layout.addWidget(QLabel("⚠️ QTextEdit with global shortcuts:"))
        self.shortcut_edit = QTextEdit()
        self.shortcut_edit.setPlaceholderText("QTextEdit with global shortcuts - test Ctrl+V")
        self.shortcut_edit.setMaximumHeight(60)
        layout.addWidget(self.shortcut_edit)
        
        # Setup some global shortcuts that might interfere
        self.setup_potentially_interfering_shortcuts()
        
        # Test buttons
        copy_btn = QPushButton("📋 Copy Test Text")
        copy_btn.clicked.connect(self.copy_text)
        layout.addWidget(copy_btn)
        
        # Status
        self.status = QLabel("Click 'Copy Test Text' then try Ctrl+V in both text areas")
        self.status.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status)
        
    def setup_potentially_interfering_shortcuts(self):
        """Setup shortcuts that might interfere"""
        # These are similar to the ones in the main app
        shortcut1 = QShortcut(QKeySequence("Ctrl++"), self)
        shortcut1.activated.connect(lambda: self.status.setText("🔍 Ctrl++ shortcut triggered"))
        
        shortcut2 = QShortcut(QKeySequence("Ctrl+-"), self)
        shortcut2.activated.connect(lambda: self.status.setText("🔍 Ctrl+- shortcut triggered"))
        
        shortcut3 = QShortcut(QKeySequence("Ctrl+0"), self)
        shortcut3.activated.connect(lambda: self.status.setText("🔍 Ctrl+0 shortcut triggered"))
        
        # Test if these interfere with Ctrl+V
        print("🔍 Global shortcuts set up:")
        print("  - Ctrl++")
        print("  - Ctrl+-") 
        print("  - Ctrl+0")
        print("If Ctrl+V doesn't work in the second text area, shortcuts are interfering")
        
    def copy_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText("Test text for Ctrl+V - check if it works in both text areas")
        self.status.setText("✅ Test text copied - try Ctrl+V in both text areas")
        self.status.setStyleSheet("color: green;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("🧪 Shortcut Interference Test")
    print("Compare Ctrl+V behavior in both text areas")
    print("If they behave differently, global shortcuts are the problem")
    
    sys.exit(app.exec())