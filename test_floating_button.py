#!/usr/bin/env python3
"""
Test script for the floating chat button addon.
Tests cross-platform compatibility and basic functionality.
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt

# Import the floating chat addon
from addons.floating_chat.floating_button import FloatingChatButton
from addons.floating_chat.chat_window import FloatingChatWindow


class MockGGUFApp:
    """Mock GGUF app for testing"""
    def __init__(self):
        self.model = None
        self.chat_generator = None


class TestWindow(QMainWindow):
    """Test window to demonstrate floating button"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Floating Button Test")
        self.resize(600, 400)
        
        # Create mock app
        self.mock_app = MockGGUFApp()
        
        # Setup UI
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Info label
        info = QLabel(
            "Floating Button Test\n\n"
            "✓ Blue floating button should appear on screen\n"
            "✓ You can drag it anywhere\n"
            "✓ Click it to open chat window\n"
            "✓ Works on Windows, Linux, and macOS\n\n"
            "Close this window to exit."
        )
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        
        # Control buttons
        show_btn = QPushButton("Show Floating Button")
        show_btn.clicked.connect(self.show_floating_button)
        layout.addWidget(show_btn)
        
        hide_btn = QPushButton("Hide Floating Button")
        hide_btn.clicked.connect(self.hide_floating_button)
        layout.addWidget(hide_btn)
        
        test_chat_btn = QPushButton("Test Chat Window")
        test_chat_btn.clicked.connect(self.test_chat_window)
        layout.addWidget(test_chat_btn)
        
        # Create floating button
        self.floating_button = FloatingChatButton()
        self.floating_button.clicked.connect(self.on_button_clicked)
        self.floating_button.move(100, 100)
        self.floating_button.show()
        
        # Chat window reference
        self.chat_window = None
        
        print("✓ Floating button created and shown")
        print(f"✓ Platform: {sys.platform}")
        print(f"✓ Qt version: {QApplication.instance().applicationVersion()}")
    
    def show_floating_button(self):
        """Show the floating button"""
        self.floating_button.show()
        print("✓ Floating button shown")
    
    def hide_floating_button(self):
        """Hide the floating button"""
        self.floating_button.hide()
        print("✓ Floating button hidden")
    
    def on_button_clicked(self):
        """Handle floating button click"""
        print("✓ Floating button clicked!")
        
        if self.chat_window and self.chat_window.isVisible():
            self.chat_window.hide()
            print("✓ Chat window hidden")
        else:
            self.test_chat_window()
    
    def test_chat_window(self):
        """Test the chat window"""
        if not self.chat_window:
            self.chat_window = FloatingChatWindow(self.mock_app)
            print("✓ Chat window created")
        
        # Position near button
        button_pos = self.floating_button.pos()
        self.chat_window.move(
            button_pos.x() + self.floating_button.width() + 10,
            button_pos.y()
        )
        
        self.chat_window.show()
        self.chat_window.raise_()
        self.chat_window.activateWindow()
        print("✓ Chat window shown")
    
    def closeEvent(self, event):
        """Clean up on close"""
        if self.floating_button:
            self.floating_button.close()
        if self.chat_window:
            self.chat_window.close()
        print("✓ Test completed, windows closed")
        super().closeEvent(event)


def main():
    """Run the test"""
    print("=" * 50)
    print("Floating Chat Button Test")
    print("=" * 50)
    print()
    
    app = QApplication(sys.argv)
    app.setApplicationName("FloatingChatTest")
    
    window = TestWindow()
    window.show()
    
    print()
    print("Test window opened. Try the following:")
    print("1. Drag the blue floating button around")
    print("2. Click it to open chat window")
    print("3. Test on different screens if you have multiple monitors")
    print()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
