#!/usr/bin/env python3
"""
Test CustomTextEdit in complete isolation from the main application
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence

# Define CustomTextEdit directly here to avoid any imports from main app
class IsolatedCustomTextEdit(QTextEdit):
    """Isolated version of CustomTextEdit for testing"""
    send_message = Signal()
    
    def keyPressEvent(self, event):
        """Handle only Enter key, let Qt handle everything else"""
        # Only intercept Enter/Return keys
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                # Shift+Enter: use default behavior (new line)
                super().keyPressEvent(event)
            else:
                # Enter only: send message
                self.send_message.emit()
                return  # Don't call super()
        else:
            # For ALL other keys, use default Qt behavior
            super().keyPressEvent(event)

class IsolatedTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Isolated CustomTextEdit Test")
        self.setGeometry(100, 100, 500, 350)
        
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        
        # Title
        title = QLabel("🧪 ISOLATED CUSTOMTEXTEDIT TEST")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel("""
This test uses a completely isolated CustomTextEdit class.
No imports from the main application, no global shortcuts, no mixins.

Test steps:
1. Click 'Copy Test Text'
2. Try Ctrl+V in each text area below
3. Compare behavior

Expected: Both should support Ctrl+V equally
        """)
        instructions.setStyleSheet("background: #f0f0f0; padding: 10px; border-radius: 5px; font-size: 11px;")
        layout.addWidget(instructions)
        
        # Regular QTextEdit
        layout.addWidget(QLabel("📝 Standard QTextEdit:"))
        self.standard_edit = QTextEdit()
        self.standard_edit.setPlaceholderText("Standard QTextEdit - Ctrl+V should work")
        self.standard_edit.setMaximumHeight(50)
        layout.addWidget(self.standard_edit)
        
        # Isolated CustomTextEdit
        layout.addWidget(QLabel("🎯 Isolated CustomTextEdit:"))
        self.custom_edit = IsolatedCustomTextEdit()
        self.custom_edit.setPlaceholderText("Isolated CustomTextEdit - test Ctrl+V")
        self.custom_edit.setMaximumHeight(50)
        self.custom_edit.send_message.connect(self.on_send)
        layout.addWidget(self.custom_edit)
        
        # Test controls
        button_layout = QVBoxLayout()
        
        copy_btn = QPushButton("📋 Copy Test Text to Clipboard")
        copy_btn.clicked.connect(self.copy_test_text)
        button_layout.addWidget(copy_btn)
        
        test_shortcuts_btn = QPushButton("🧪 Test All Shortcuts")
        test_shortcuts_btn.clicked.connect(self.test_shortcuts)
        button_layout.addWidget(test_shortcuts_btn)
        
        layout.addLayout(button_layout)
        
        # Status
        self.status = QLabel("Ready - click 'Copy Test Text' then try Ctrl+V")
        self.status.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(self.status)
        
    def copy_test_text(self):
        """Copy test text to clipboard"""
        test_text = "🧪 This is test text for Ctrl+V paste testing!"
        clipboard = QApplication.clipboard()
        clipboard.setText(test_text)
        self.status.setText(f"✅ Copied: '{test_text}'")
        self.status.setStyleSheet("color: green; padding: 5px;")
        
    def test_shortcuts(self):
        """Test various shortcuts programmatically"""
        self.status.setText("🧪 Testing shortcuts - check console for results")
        self.status.setStyleSheet("color: blue; padding: 5px;")
        
        # Test clipboard operations
        clipboard = QApplication.clipboard()
        original_text = clipboard.text()
        
        # Test copy/paste cycle
        test_text = "Programmatic test"
        clipboard.setText(test_text)
        
        # Focus custom edit and try paste
        self.custom_edit.setFocus()
        self.custom_edit.paste()
        
        result_text = self.custom_edit.toPlainText()
        if test_text in result_text:
            print("✅ Programmatic paste() works")
            self.status.setText("✅ Programmatic paste() works - try manual Ctrl+V")
            self.status.setStyleSheet("color: green; padding: 5px;")
        else:
            print("❌ Programmatic paste() failed")
            self.status.setText("❌ Programmatic paste() failed")
            self.status.setStyleSheet("color: red; padding: 5px;")
        
        # Restore original clipboard
        clipboard.setText(original_text)
        
    def on_send(self):
        """Handle send message signal"""
        text = self.custom_edit.toPlainText()
        self.status.setText(f"📤 Send triggered: '{text[:30]}{'...' if len(text) > 30 else ''}'")
        self.status.setStyleSheet("color: purple; padding: 5px;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IsolatedTestWindow()
    window.show()
    
    print("🧪 Isolated CustomTextEdit Test")
    print("=" * 40)
    print("This test isolates CustomTextEdit completely")
    print("If Ctrl+V doesn't work here, the issue is in the CustomTextEdit class itself")
    print("If it works here but not in the main app, the issue is with global shortcuts/events")
    print("=" * 40)
    
    sys.exit(app.exec())