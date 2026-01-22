#!/usr/bin/env python3
"""
Comprehensive test for copy functionality across all widget types
"""

import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QLabel, QTextEdit, QPushButton, QHBoxLayout, QScrollArea)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

# Import the widgets we're testing
from widgets.chat_bubble import ChatBubble

class ComprehensiveCopyTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Comprehensive Copy Functionality Test")
        self.setGeometry(100, 100, 700, 600)
        
        # Create scroll area for all tests
        scroll = QScrollArea()
        self.setCentralWidget(scroll)
        
        central_widget = QWidget()
        scroll.setWidget(central_widget)
        scroll.setWidgetResizable(True)
        
        layout = QVBoxLayout(central_widget)
        
        # Instructions
        instructions = QLabel("""
🧪 COPY FUNCTIONALITY TEST

Instructions:
1. Select text in any widget below
2. Try Ctrl+C to copy
3. Try right-click → Copy (context menu)
4. Click 'Check Clipboard' to verify
5. Test both keyboard and mouse selection

Expected behavior:
✅ Text should be selectable (highlighted when dragged)
✅ Ctrl+C should copy selected text
✅ Right-click should show context menu with Copy option
✅ Copied text should appear in clipboard check
        """)
        instructions.setStyleSheet("""
            QLabel {
                background-color: #f0f8ff;
                border: 2px solid #4a90e2;
                border-radius: 8px;
                padding: 15px;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(instructions)
        
        # Test 1: QLabel with text selection
        layout.addWidget(QLabel("🏷️ Test 1: QLabel with Text Selection"))
        test_label = QLabel("This is a QLabel with text selection enabled. Try selecting this text and copying it with Ctrl+C or right-click → Copy.")
        test_label.setWordWrap(True)
        test_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        test_label.setContextMenuPolicy(Qt.DefaultContextMenu)
        test_label.setStyleSheet("border: 1px solid #ccc; padding: 10px; background: #f9f9f9;")
        layout.addWidget(test_label)
        
        # Test 2: QTextEdit (editable)
        layout.addWidget(QLabel("📝 Test 2: QTextEdit (Editable)"))
        test_textedit = QTextEdit()
        test_textedit.setPlainText("This is an editable QTextEdit. You can select, copy, and even edit this text. Copy functionality should work by default.")
        test_textedit.setMaximumHeight(80)
        test_textedit.setContextMenuPolicy(Qt.DefaultContextMenu)
        layout.addWidget(test_textedit)
        
        # Test 3: QTextEdit (readonly)
        layout.addWidget(QLabel("📖 Test 3: QTextEdit (Read-only)"))
        test_readonly = QTextEdit()
        test_readonly.setPlainText("This is a read-only QTextEdit. You can select and copy this text, but cannot edit it. This simulates chat message display.")
        test_readonly.setReadOnly(True)
        test_readonly.setMaximumHeight(80)
        test_readonly.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        test_readonly.setContextMenuPolicy(Qt.DefaultContextMenu)
        layout.addWidget(test_readonly)
        
        # Test 4: Chat Bubble
        layout.addWidget(QLabel("💬 Test 4: Chat Bubble (User Message)"))
        user_bubble = ChatBubble("This is a user chat bubble. Select this text and try copying it. This tests the actual chat bubble widget used in the application.", is_user=True)
        layout.addWidget(user_bubble)
        
        layout.addWidget(QLabel("🤖 Test 5: Chat Bubble (AI Message)"))
        ai_bubble = ChatBubble("This is an AI chat bubble with some longer text to test text selection and copying functionality. The text should be selectable and copyable using both keyboard shortcuts and context menu.", is_user=False)
        layout.addWidget(ai_bubble)
        
        # Test 6: Multi-line label
        layout.addWidget(QLabel("📄 Test 6: Multi-line QLabel"))
        multiline_label = QLabel("""This is a multi-line QLabel.
It contains several lines of text.
Each line should be selectable.
You should be able to select across lines.
Try selecting part of this text and copying it.""")
        multiline_label.setWordWrap(True)
        multiline_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        multiline_label.setContextMenuPolicy(Qt.DefaultContextMenu)
        multiline_label.setStyleSheet("border: 1px solid #ccc; padding: 10px; background: #f9f9f9;")
        layout.addWidget(multiline_label)
        
        # Clipboard test area
        layout.addWidget(QLabel("📋 Clipboard Test Area"))
        button_layout = QHBoxLayout()
        
        check_btn = QPushButton("📋 Check Clipboard Content")
        check_btn.clicked.connect(self.check_clipboard)
        button_layout.addWidget(check_btn)
        
        clear_btn = QPushButton("🗑️ Clear Clipboard")
        clear_btn.clicked.connect(self.clear_clipboard)
        button_layout.addWidget(clear_btn)
        
        test_copy_btn = QPushButton("🧪 Test Programmatic Copy")
        test_copy_btn.clicked.connect(self.test_programmatic_copy)
        button_layout.addWidget(test_copy_btn)
        
        layout.addLayout(button_layout)
        
        # Clipboard display
        self.clipboard_display = QTextEdit()
        self.clipboard_display.setMaximumHeight(100)
        self.clipboard_display.setReadOnly(True)
        self.clipboard_display.setPlaceholderText("Clipboard content will appear here...")
        layout.addWidget(self.clipboard_display)
        
        # Status area
        self.status_label = QLabel("Ready to test copy functionality")
        self.status_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(self.status_label)
        
    def check_clipboard(self):
        """Check and display current clipboard content"""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.clipboard_display.setPlainText(f"✅ Clipboard contains:\n{text}")
            self.status_label.setText(f"✅ Found {len(text)} characters in clipboard")
            self.status_label.setStyleSheet("color: green; font-weight: bold; padding: 5px;")
            print(f"✅ Clipboard content ({len(text)} chars): {text[:100]}{'...' if len(text) > 100 else ''}")
        else:
            self.clipboard_display.setPlainText("❌ Clipboard is empty")
            self.status_label.setText("❌ Clipboard is empty")
            self.status_label.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
            print("❌ Clipboard is empty")
    
    def clear_clipboard(self):
        """Clear the clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.clear()
        self.clipboard_display.setPlainText("🗑️ Clipboard cleared")
        self.status_label.setText("🗑️ Clipboard cleared")
        self.status_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        print("🗑️ Clipboard cleared")
    
    def test_programmatic_copy(self):
        """Test programmatic copying"""
        test_text = "This text was copied programmatically to test clipboard functionality."
        clipboard = QApplication.clipboard()
        clipboard.setText(test_text)
        self.clipboard_display.setPlainText(f"🧪 Programmatically copied:\n{test_text}")
        self.status_label.setText("🧪 Programmatic copy successful")
        self.status_label.setStyleSheet("color: blue; font-weight: bold; padding: 5px;")
        print(f"🧪 Programmatically copied: {test_text}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ComprehensiveCopyTest()
    window.show()
    
    print("🧪 Comprehensive Copy Functionality Test")
    print("=" * 50)
    print("Test each widget type:")
    print("1. Select text with mouse")
    print("2. Try Ctrl+C")
    print("3. Try right-click → Copy")
    print("4. Check clipboard content")
    print("=" * 50)
    
    sys.exit(app.exec())