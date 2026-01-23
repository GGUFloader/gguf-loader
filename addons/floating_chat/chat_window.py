# Chat Window
#!/usr/bin/env python3
"""
Floating Chat Window - Chat interface connected to GGUF Loader

Provides a clean, modern chat window that connects to the main GGUF Loader
for AI conversations.
"""

import logging
from typing import Optional, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QTextCursor

try:
    from config import FONT_FAMILY
except ImportError:
    FONT_FAMILY = "Segoe UI"


class FloatingChatWindow(QWidget):
    """
    Floating chat window for AI conversations.
    
    Features:
    - Clean, modern UI
    - Connected to GGUF Loader model
    - Message history display
    - Input field with send button
    - Always stays on top
    """
    
    # Signals
    message_sent = Signal(str)
    window_closed = Signal()
    
    def __init__(self, gguf_app_instance: Any):
        super().__init__()
        
        # Store reference to main app
        self.gguf_app = gguf_app_instance
        
        # Setup logging
        self._logger = logging.getLogger(__name__)
        
        # Chat state
        self._conversation_history = []
        self._is_generating = False
        
        # Setup window
        self._setup_window()
        self._setup_ui()
        
        # Connect to model if available
        self._connect_to_model()
    
    def _setup_window(self):
        """Setup window properties."""
        self.setWindowTitle("Floating Chat")
        
        # Set window flags for floating behavior
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )
        
        # Set size
        self.resize(400, 600)
        self.setMinimumSize(300, 400)
        
        # Apply modern styling
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QLabel {
                color: #333;
                font-size: 12px;
            }
        """)
    
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header
        header = QLabel("💬 AI Chat")
        header.setFont(QFont(FONT_FAMILY, 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #0078d4; padding: 5px;")
        layout.addWidget(header)
        
        # Model status indicator
        self.status_label = QLabel("⚪ Model: Not loaded")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
        layout.addWidget(self.status_label)
        
        # Chat display area
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText("Chat messages will appear here...")
        # Enable text selection and context menu for copying
        self.chat_display.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | 
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.chat_display.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        layout.addWidget(self.chat_display, stretch=1)
        
        # Input area
        input_frame = QFrame()
        input_frame.setStyleSheet("background-color: transparent;")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        
        # Input field
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Type your message here...")
        self.input_field.setMaximumHeight(100)
        self.input_field.setMinimumHeight(60)
        # Ensure context menu is enabled for copy/paste/cut
        self.input_field.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        input_layout.addWidget(self.input_field)
        
        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # Clear button
        self.clear_btn = QPushButton("🗑️ Clear")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        self.clear_btn.clicked.connect(self._clear_chat)
        button_layout.addWidget(self.clear_btn)
        
        button_layout.addStretch()
        
        # Send button
        self.send_btn = QPushButton("📤 Send")
        self.send_btn.clicked.connect(self._send_message)
        button_layout.addWidget(self.send_btn)
        
        input_layout.addLayout(button_layout)
        layout.addWidget(input_frame)
        
        # Enable Ctrl+Enter to send
        self.input_field.installEventFilter(self)
    
    def _connect_to_model(self):
        """Connect to the GGUF Loader model."""
        try:
            # Check if model is loaded
            if hasattr(self.gguf_app, 'model') and self.gguf_app.model:
                self.set_model_status(True)
            else:
                self.set_model_status(False)
            
            # Connect to model signals if available
            if hasattr(self.gguf_app, 'model_loaded'):
                self.gguf_app.model_loaded.connect(lambda m: self.set_model_status(True))
            
        except Exception as e:
            self._logger.error(f"Error connecting to model: {e}")
    
    def set_model_status(self, is_loaded: bool):
        """Update model status indicator."""
        if is_loaded:
            self.status_label.setText("🟢 Model: Ready")
            self.status_label.setStyleSheet("color: #28a745; font-size: 11px; padding: 2px;")
            self.send_btn.setEnabled(True)
        else:
            self.status_label.setText("🔴 Model: Not loaded")
            self.status_label.setStyleSheet("color: #dc3545; font-size: 11px; padding: 2px;")
            self.send_btn.setEnabled(False)
    
    def _send_message(self):
        """Send message to AI."""
        message = self.input_field.toPlainText().strip()
        
        if not message:
            return
        
        # Check if model is available
        if not hasattr(self.gguf_app, 'model') or not self.gguf_app.model:
            self._add_system_message("⚠️ Please load a model first in the main window.")
            return
        
        # Disable input while generating
        self._is_generating = True
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        
        # Display user message
        self._add_user_message(message)
        
        # Clear input
        self.input_field.clear()
        
        # Emit signal
        self.message_sent.emit(message)
        
        # Generate response
        self._generate_response(message)
    
    def _generate_response(self, user_message: str):
        """Generate AI response."""
        try:
            # Add to conversation history
            self._conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            # Show "thinking" indicator
            self._add_system_message("🤔 AI is thinking...")
            
            # Generate response using the main app's chat generator
            if hasattr(self.gguf_app, 'chat_generator') and self.gguf_app.chat_generator:
                # Use existing chat generator
                response = self._generate_with_chat_generator(user_message)
            elif hasattr(self.gguf_app, 'model') and self.gguf_app.model:
                # Direct model generation
                response = self._generate_with_model(user_message)
            else:
                response = "Error: No model available"
            
            # Remove "thinking" message
            self._remove_last_message()
            
            # Display AI response
            self._add_ai_message(response)
            
            # Add to history
            self._conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
        except Exception as e:
            self._logger.error(f"Error generating response: {e}")
            self._remove_last_message()
            self._add_system_message(f"❌ Error: {str(e)}")
        
        finally:
            # Re-enable input
            self._is_generating = False
            self.input_field.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.input_field.setFocus()
    
    def _generate_with_chat_generator(self, message: str) -> str:
        """Generate response using chat generator."""
        try:
            # Build conversation context
            conversation = self._conversation_history.copy()
            
            # Generate
            response = self.gguf_app.chat_generator.generate_response(
                conversation,
                max_tokens=512
            )
            
            return response
            
        except Exception as e:
            self._logger.error(f"Chat generator error: {e}")
            return f"Error: {str(e)}"
    
    def _generate_with_model(self, message: str) -> str:
        """Generate response directly with model."""
        try:
            # Simple prompt
            prompt = f"User: {message}\nAssistant:"
            
            # Generate
            response = self.gguf_app.model(
                prompt,
                max_tokens=512,
                stop=["User:", "\n\n"],
                echo=False
            )
            
            return response['choices'][0]['text'].strip()
            
        except Exception as e:
            self._logger.error(f"Model generation error: {e}")
            return f"Error: {str(e)}"
    
    def _add_user_message(self, message: str):
        """Add user message to chat display."""
        self.chat_display.append(f'<div style="margin: 10px 0; text-align: right;">'
                                 f'<span style="background-color: #0078d4; color: white; '
                                 f'padding: 8px 12px; border-radius: 12px; display: inline-block; '
                                 f'max-width: 70%;">{self._escape_html(message)}</span></div>')
        self._scroll_to_bottom()
    
    def _add_ai_message(self, message: str):
        """Add AI message to chat display."""
        self.chat_display.append(f'<div style="margin: 10px 0;">'
                                 f'<span style="background-color: #e9ecef; color: #333; '
                                 f'padding: 8px 12px; border-radius: 12px; display: inline-block; '
                                 f'max-width: 70%;">{self._escape_html(message)}</span></div>')
        self._scroll_to_bottom()
    
    def _add_system_message(self, message: str):
        """Add system message to chat display."""
        self.chat_display.append(f'<div style="margin: 10px 0; text-align: center;">'
                                 f'<span style="color: #6c757d; font-size: 11px; font-style: italic;">'
                                 f'{self._escape_html(message)}</span></div>')
        self._scroll_to_bottom()
    
    def _remove_last_message(self):
        """Remove the last message from chat display."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar()  # Remove the newline
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#39;')
                   .replace('\n', '<br>'))
    
    def _scroll_to_bottom(self):
        """Scroll chat display to bottom."""
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _clear_chat(self):
        """Clear chat history."""
        self.chat_display.clear()
        self._conversation_history.clear()
        self._add_system_message("Chat cleared")
    
    def on_generation_finished(self):
        """Handle generation finished event."""
        self._is_generating = False
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
    
    def on_generation_error(self, error_message: str):
        """Handle generation error event."""
        self._is_generating = False
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self._add_system_message(f"❌ Error: {error_message}")
    
    def eventFilter(self, obj, event):
        """Event filter for Ctrl+Enter to send - allows all other shortcuts."""
        if obj == self.input_field and event.type() == event.Type.KeyPress:
            # Only intercept Ctrl+Enter for sending
            if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self._send_message()
                return True
            # Let all other keys pass through (including Ctrl+V, Ctrl+C, Ctrl+X, Ctrl+A, etc.)
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.window_closed.emit()
        super().closeEvent(event)
