#!/usr/bin/env python3
"""
Status Widget for Floating Chat Addon

Displays addon status in the GGUF Loader sidebar.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt


class FloatingChatStatusWidget(QWidget):
    """Status widget for the floating chat addon."""
    
    def __init__(self, addon_instance):
        super().__init__()
        
        self.addon = addon_instance
        
        # Setup UI
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Title
        title = QLabel("💬 Floating Chat")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Status
        self.status_label = QLabel("🟢 Active")
        self.status_label.setStyleSheet("color: #28a745; font-size: 12px;")
        layout.addWidget(self.status_label)
        
        # Description
        desc = QLabel("Floating chat button is active. Click the button to open chat window.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc)
        
        # Button row
        button_layout = QHBoxLayout()
        
        # Show/Hide button
        self.toggle_btn = QPushButton("Show Chat")
        self.toggle_btn.clicked.connect(self._toggle_chat)
        button_layout.addWidget(self.toggle_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        # Update button state
        self._update_button_state()
    
    def _toggle_chat(self):
        """Toggle chat window visibility."""
        if self.addon.is_chat_window_visible():
            self.addon._chat_window.hide()
        else:
            self.addon._show_chat_window()
        
        self._update_button_state()
    
    def _update_button_state(self):
        """Update button text based on chat window state."""
        if self.addon.is_chat_window_visible():
            self.toggle_btn.setText("Hide Chat")
        else:
            self.toggle_btn.setText("Show Chat")
