#!/usr/bin/env python3
"""
Test script for the new chat bubble interface in floating chat window
"""

import sys
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

# Mock GGUF app for testing
class MockGGUFApp:
    def __init__(self):
        self.model = None
        self.chat_generator = None

def test_chat_window():
    """Test the floating chat window with bubble interface"""
    app = QApplication(sys.argv)
    
    # Create mock app instance
    mock_app = MockGGUFApp()
    
    # Import and create chat window
    from addons.floating_chat.chat_window import FloatingChatWindow
    
    chat_window = FloatingChatWindow(mock_app)
    
    # Add test messages with varying lengths to demonstrate responsiveness
    chat_window._add_system_message("Welcome to the chat!")
    
    # Short messages
    chat_window._add_user_message("Hi!")
    chat_window._add_ai_message("Hello!")
    
    # Medium messages
    chat_window._add_user_message("Can you help me with something?")
    chat_window._add_ai_message("Of course! I'd be happy to help. What do you need?")
    
    # Long messages to test wrapping and responsiveness
    chat_window._add_user_message("This is a longer message to test how the bubbles handle text wrapping and responsiveness. The bubbles should expand to take as much width as needed, just like in modern messenger apps like WhatsApp or Telegram.")
    chat_window._add_ai_message("This is also a longer AI response to demonstrate text wrapping on the left side. The bubble should maintain its styling and readability even with multiple lines of text. Notice how it takes up the available space while leaving room on the right side.")
    
    # Very short
    chat_window._add_user_message("OK")
    chat_window._add_ai_message("Great!")
    
    # Code-like content
    chat_window._add_user_message("Can you show me a Python function?")
    chat_window._add_ai_message("Sure! Here's an example:\n\ndef hello_world():\n    print('Hello, World!')\n    return True")
    
    chat_window.show()
    
    print("✅ Chat window opened with RESPONSIVE bubble interface")
    print("📝 User messages appear on the RIGHT (blue bubbles)")
    print("🤖 AI messages appear on the LEFT (gray bubbles)")
    print("📏 Bubbles are RESPONSIVE and take up to ~70% of available width")
    print("🔄 Try resizing the window to see responsive behavior!")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    test_chat_window()
