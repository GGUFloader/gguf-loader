#!/usr/bin/env python3
"""
Test script to verify paste functionality in CustomTextEdit
"""

import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QLabel, QPushButton, QHBoxLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

# Import the custom text edit
from mixins.ui_setup_mixin import CustomTextEdit

class PasteTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Paste Functionality Test")
        self.setGeometry(100, 100, 600, 400)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Instructions
        instructions = QLabel("""
🧪 PASTE FUNCTIONALITY TEST

Instructions:
1. Copy some text from anywhere (Ctrl+C)
2. Click in the text area below
3. Try Ctrl+V to paste
4. Test other shortcuts: Ctrl+A (select all), Ctrl+Z (undo), etc.
5. Test Enter vs Shift+Enter behavior

Expected behavior:
✅ Ctrl+V should paste clipboard content
✅ Ctrl+C should copy selected text
✅ Ctrl+A should select all text
✅ Ctrl+Z should undo last action
✅ Enter should trigger send (simulated)
✅ Shift+Enter should insert new line
        """)
        instructions.setStyleSheet("""
            QLabel {
                background-color: #f0f8ff;
                border: 2px solid #4a90e2;
                border-radius: 8px;
                padding: 15px;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(instructions)
        
        # Test CustomTextEdit
        layout.addWidget(QLabel("📝 CustomTextEdit (Input Area):"))
        self.custom_text_edit = CustomTextEdit()
        self.custom_text_edit.setPlaceholderText("Type here or paste with Ctrl+V...")
        self.custom_text_edit.setMaximumHeight(100)
        self.custom_text_edit.send_message.connect(self.on_send_message)
        layout.addWidget(self.custom_text_edit)
        
        # Test buttons
        button_layout = QHBoxLayout()
        
        copy_test_btn = QPushButton("📋 Copy Test Text to Clipboard")
        copy_test_btn.clicked.connect(self.copy_test_text)
        button_layout.addWidget(copy_test_btn)
        
        paste_btn = QPushButton("📝 Programmatic Paste")
        paste_btn.clicked.connect(self.programmatic_paste)
        button_layout.addWidget(paste_btn)
        
        clear_btn = QPushButton("🗑️ Clear Text Area")
        clear_btn.clicked.connect(self.clear_text)
        button_layout.addWidget(clear_btn)
        
        check_clipboard_btn = QPushButton("👀 Check Clipboard")
        check_clipboard_btn.clicked.connect(self.check_clipboard)
        button_layout.addWidget(check_clipboard_btn)
        
        layout.addLayout(button_layout)
        
        # Status area
        self.status_label = QLabel("Ready to test paste functionality")
        self.status_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # Event log
        layout.addWidget(QLabel("📋 Event Log:"))
        self.event_log = CustomTextEdit()
        self.event_log.setMaximumHeight(100)
        self.event_log.setReadOnly(True)
        self.event_log.setPlainText("Event log will appear here...")
        layout.addWidget(self.event_log)
        
    def programmatic_paste(self):
        """Test programmatic paste"""
        self.custom_text_edit.paste()
        self.status_label.setText("📝 Programmatic paste executed")
        self.status_label.setStyleSheet("color: blue; font-weight: bold; padding: 5px;")
        self.log_event("📝 Programmatic paste() method called")
        
    def copy_test_text(self):
        """Copy test text to clipboard"""
        test_text = "This is test text for pasting! Try Ctrl+V in the text area above."
        clipboard = QApplication.clipboard()
        clipboard.setText(test_text)
        self.status_label.setText(f"✅ Copied test text to clipboard: '{test_text[:30]}...'")
        self.status_label.setStyleSheet("color: green; font-weight: bold; padding: 5px;")
        self.log_event(f"📋 Copied to clipboard: {test_text}")
        
    def clear_text(self):
        """Clear the text area"""
        self.custom_text_edit.clear()
        self.status_label.setText("🗑️ Text area cleared")
        self.status_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        self.log_event("🗑️ Text area cleared")
        
    def check_clipboard(self):
        """Check clipboard content"""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.status_label.setText(f"📋 Clipboard: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            self.status_label.setStyleSheet("color: blue; font-weight: bold; padding: 5px;")
            self.log_event(f"👀 Clipboard contains: {text}")
        else:
            self.status_label.setText("❌ Clipboard is empty")
            self.status_label.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
            self.log_event("❌ Clipboard is empty")
    
    def on_send_message(self):
        """Handle send message signal"""
        text = self.custom_text_edit.toPlainText()
        self.log_event(f"📤 Send message triggered: '{text}'")
        self.status_label.setText("📤 Send message triggered (Enter pressed)")
        self.status_label.setStyleSheet("color: purple; font-weight: bold; padding: 5px;")
        
    def log_event(self, message):
        """Log an event to the event log"""
        current_text = self.event_log.toPlainText()
        if current_text == "Event log will appear here...":
            self.event_log.setPlainText(message)
        else:
            self.event_log.setPlainText(current_text + "\n" + message)
        
        # Scroll to bottom
        cursor = self.event_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.event_log.setTextCursor(cursor)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PasteTestWindow()
    window.show()
    
    print("🧪 Paste Functionality Test")
    print("=" * 40)
    print("Test the following shortcuts:")
    print("• Ctrl+V - Paste")
    print("• Ctrl+C - Copy")
    print("• Ctrl+A - Select All")
    print("• Ctrl+Z - Undo")
    print("• Enter - Send Message")
    print("• Shift+Enter - New Line")
    print("=" * 40)
    
    sys.exit(app.exec())