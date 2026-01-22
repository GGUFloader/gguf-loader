#!/usr/bin/env python3
"""
Quick test script to verify the text size slider functionality
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

# Import the mixin to test
from mixins.ui_setup_mixin import UISetupMixin

class TestWindow(QMainWindow, UISetupMixin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Text Size Slider Test")
        self.setGeometry(100, 100, 400, 300)
        
        # Initialize required attributes
        self.current_font_size = 14
        self.chat_bubbles = []
        
        # Create test UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add a test label
        self.test_label = QLabel("This is a test text that will change size with the slider!")
        self.test_label.setWordWrap(True)
        self.test_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.test_label)
        
        # Add the text size controls from the mixin
        self._setup_appearance_section(layout)
        
        # Setup shortcuts
        self.setup_text_size_shortcuts()
        
    def _apply_font_size_to_all_bubbles(self):
        """Override to update our test label instead of chat bubbles"""
        font = self.test_label.font()
        font.setPointSize(self.current_font_size)
        self.test_label.setFont(font)
        print(f"Font size changed to: {self.current_font_size}px")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("Text Size Slider Test")
    print("- Use the slider to change text size")
    print("- Double-click slider to reset to default")
    print("- Use Ctrl+Plus/Minus to adjust with keyboard")
    print("- Use Ctrl+0 to reset to default")
    print("- Scroll mouse wheel over slider to adjust")
    
    sys.exit(app.exec())