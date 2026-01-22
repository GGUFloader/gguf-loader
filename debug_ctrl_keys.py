#!/usr/bin/env python3
"""
Debug tool to find what's intercepting Ctrl keys
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QLabel
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent

class DebugTextEdit(QTextEdit):
    """Text edit that shows exactly what key events it receives"""
    
    def keyPressEvent(self, event):
        """Debug every single key event"""
        key = event.key()
        modifiers = event.modifiers()
        text = event.text()
        
        # Build modifier string
        mod_parts = []
        if modifiers & Qt.ControlModifier:
            mod_parts.append("Ctrl")
        if modifiers & Qt.ShiftModifier:
            mod_parts.append("Shift")
        if modifiers & Qt.AltModifier:
            mod_parts.append("Alt")
        if modifiers & Qt.MetaModifier:
            mod_parts.append("Meta")
        
        mod_str = "+".join(mod_parts) if mod_parts else "None"
        
        print(f"🔍 DebugTextEdit.keyPressEvent:")
        print(f"    Key: {key} (Qt.Key_{key})")
        print(f"    Modifiers: {modifiers} ({mod_str})")
        print(f"    Text: '{text}'")
        print(f"    Is Ctrl+V: {key == Qt.Key_V and modifiers & Qt.ControlModifier}")
        print(f"    Is Ctrl+C: {key == Qt.Key_C and modifiers & Qt.ControlModifier}")
        print("    Calling super().keyPressEvent()")
        
        # Always call super - no custom handling
        super().keyPressEvent(event)
        print("    super().keyPressEvent() completed")
        print()

class DebugMainWindow(QMainWindow):
    """Main window that also debugs events"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ctrl Key Debug Tool")
        self.setGeometry(100, 100, 600, 400)
        
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        
        # Instructions
        instructions = QLabel("""
🔍 CTRL KEY DEBUGGING TOOL

This tool will show EXACTLY what happens when you press keys.
Watch the console output carefully.

1. Click in the text area below
2. Press Ctrl+V (or any Ctrl combination)
3. Check console to see what events are received
4. If you don't see the key event in console, something is intercepting it BEFORE it reaches the widget

Expected for Ctrl+V:
- Key: 86 (Qt.Key_86)
- Modifiers: 67108864 (Ctrl)
- Text: '' (empty for Ctrl combinations)
        """)
        instructions.setStyleSheet("""
            background: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 8px;
            padding: 15px;
            font-family: monospace;
            font-size: 11px;
        """)
        layout.addWidget(instructions)
        
        # Debug text edit
        layout.addWidget(QLabel("🎯 Debug Text Area (watch console):"))
        self.debug_edit = DebugTextEdit()
        self.debug_edit.setPlaceholderText("Click here and press Ctrl+V - watch console output")
        layout.addWidget(self.debug_edit)
        
        # Status
        self.status = QLabel("Ready - click in text area and press Ctrl+V")
        self.status.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(self.status)
        
        # Copy test text to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText("Test text for debugging Ctrl+V")
        
    def keyPressEvent(self, event):
        """Debug main window key events"""
        key = event.key()
        modifiers = event.modifiers()
        
        print(f"🏠 MainWindow.keyPressEvent:")
        print(f"    Key: {key}")
        print(f"    Modifiers: {modifiers}")
        print(f"    Calling super().keyPressEvent()")
        
        super().keyPressEvent(event)
        print(f"    MainWindow super().keyPressEvent() completed")
        print()
    
    def event(self, event):
        """Debug ALL events to main window"""
        if event.type() == QEvent.Type.KeyPress:
            key_event = event
            print(f"🌍 MainWindow.event() - KeyPress:")
            print(f"    Key: {key_event.key()}")
            print(f"    Modifiers: {key_event.modifiers()}")
            print(f"    Calling super().event()")
        
        result = super().event(event)
        
        if event.type() == QEvent.Type.KeyPress:
            print(f"    MainWindow super().event() returned: {result}")
            print()
        
        return result

class DebugApplication(QApplication):
    """Application that debugs global events"""
    
    def notify(self, obj, event):
        """Debug ALL events in the application"""
        if event.type() == QEvent.Type.KeyPress:
            key_event = event
            print(f"🌐 QApplication.notify() - KeyPress:")
            print(f"    Object: {obj.__class__.__name__}")
            print(f"    Key: {key_event.key()}")
            print(f"    Modifiers: {key_event.modifiers()}")
            print(f"    Calling super().notify()")
        
        result = super().notify(obj, event)
        
        if event.type() == QEvent.Type.KeyPress:
            print(f"    QApplication.notify() returned: {result}")
            print()
        
        return result

if __name__ == "__main__":
    app = DebugApplication(sys.argv)
    window = DebugMainWindow()
    window.show()
    
    print("🔍 CTRL KEY DEBUG TOOL STARTED")
    print("=" * 50)
    print("Watch console output when you press keys")
    print("If you don't see events, something is blocking them")
    print("=" * 50)
    print()
    
    sys.exit(app.exec())