#!/usr/bin/env python3
"""
Test Ctrl+V after disabling Smart Floater interference
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

# Import your CustomTextEdit to test
try:
    from mixins.ui_setup_mixin import CustomTextEdit
    CUSTOM_EDIT_AVAILABLE = True
except ImportError:
    CUSTOM_EDIT_AVAILABLE = False
    
    # Fallback CustomTextEdit for testing
    class CustomTextEdit(QTextEdit):
        send_message = Signal()
        
        def keyPressEvent(self, event):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    super().keyPressEvent(event)
                else:
                    self.send_message.emit()
                    return
            else:
                super().keyPressEvent(event)

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test After Smart Floater Fix")
        self.setGeometry(100, 100, 500, 300)
        
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        
        # Title
        title = QLabel("🎉 TESTING AFTER SMART FLOATER FIX")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: green; padding: 10px;")
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel("""
The Smart Floater addon was sending pyautogui.hotkey('ctrl', 'c') every 500ms!
This was intercepting all Ctrl key combinations.

I've disabled the problematic code. Now test:
1. Click 'Copy Test Text'
2. Try Ctrl+V in the text area below
3. It should work now!
        """)
        instructions.setStyleSheet("background: #d4edda; padding: 10px; border-radius: 5px; border: 1px solid #c3e6cb;")
        layout.addWidget(instructions)
        
        # Test area
        layout.addWidget(QLabel("🎯 Test CustomTextEdit (should work now):"))
        self.custom_edit = CustomTextEdit()
        self.custom_edit.setPlaceholderText("Try Ctrl+V here - it should work now!")
        self.custom_edit.send_message.connect(lambda: self.status.setText("📤 Send message triggered (Enter works)"))
        layout.addWidget(self.custom_edit)
        
        # Copy button
        copy_btn = QPushButton("📋 Copy Test Text to Clipboard")
        copy_btn.clicked.connect(self.copy_text)
        layout.addWidget(copy_btn)
        
        # Status
        self.status = QLabel("Click 'Copy Test Text' then try Ctrl+V above")
        self.status.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status)
        
    def copy_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText("🎉 SUCCESS! Ctrl+V is working again after fixing Smart Floater!")
        self.status.setText("✅ Text copied - now try Ctrl+V in the text area")
        self.status.setStyleSheet("color: green; font-weight: bold;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("🎉 TESTING AFTER SMART FLOATER FIX")
    print("=" * 50)
    print("The Smart Floater addon was the culprit!")
    print("It was sending pyautogui.hotkey('ctrl', 'c') every 500ms")
    print("This interfered with all Ctrl key combinations")
    print("I've disabled the problematic code")
    print("Test Ctrl+V now - it should work!")
    print("=" * 50)
    
    sys.exit(app.exec())