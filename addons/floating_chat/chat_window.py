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
    QLabel, QScrollArea, QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QFont, QTextCursor

try:
    from config import FONT_FAMILY
except ImportError:
    FONT_FAMILY = "Segoe UI"

try:
    from widgets.chat_bubble import ChatBubble
except ImportError:
    # Fallback if chat_bubble is not available
    ChatBubble = None


class StreamingThread(QThread):
    """Thread for streaming model responses without blocking UI."""
    token_received = Signal(str)
    finished = Signal()
    error = Signal(str)
    
    def __init__(self, model, prompt, max_tokens=8192):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.max_tokens = max_tokens
        self._stop_flag = False
    
    def run(self):
        """Run streaming generation in background thread."""
        try:
            stream = self.model(
                self.prompt,
                max_tokens=self.max_tokens,
                stream=True,
                stop=["User:", "\nUser:", "user:", "\nuser:"],
                echo=False,
                temperature=0.7,
                top_p=0.9,
                repeat_penalty=1.1,
                top_k=40
            )
            
            for token_data in stream:
                if self._stop_flag:
                    break
                
                token = token_data.get('choices', [{}])[0].get('text', '')
                if token:
                    self.token_received.emit(token)
            
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(f"Generation error: {str(e)}")
    
    def stop(self):
        """Stop the streaming generation."""
        self._stop_flag = True


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
        self._current_ai_message_widget = None  # Track current streaming message
        self._current_response_text = ""  # Accumulate streaming response
        
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
        
        # Chat display area with scroll
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
            }
        """)
        
        # Container for chat bubbles
        self.chat_container = QWidget()
        self.chat_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(5, 10, 5, 10)
        self.chat_layout.setSpacing(5)
        self.chat_layout.addStretch()  # Push messages to top
        
        self.chat_scroll.setWidget(self.chat_container)
        layout.addWidget(self.chat_scroll, stretch=1)
        
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
        
        # Copy All button
        copy_all_btn = QPushButton("📋 Copy All")
        copy_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        copy_all_btn.clicked.connect(self._copy_all_messages)
        button_layout.addWidget(copy_all_btn)
        
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
        
        # Stop button (hidden by default)
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.stop_btn.clicked.connect(self._stop_generation)
        self.stop_btn.hide()
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        
        # Send button with icon
        self.send_btn = QPushButton("➤")  # Send arrow icon
        self.send_btn.setFixedSize(45, 45)  # Circular button
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 22px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
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
        """)
        self.send_btn.clicked.connect(self._send_message)
        button_layout.addWidget(self.send_btn)
        
        input_layout.addLayout(button_layout)
        layout.addWidget(input_frame)
        
        # Enable Enter to send, Shift+Enter for new line
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
        self.send_btn.hide()
        self.stop_btn.show()
        
        # Display user message
        self._add_user_message(message)
        
        # Clear input
        self.input_field.clear()
        
        # Emit signal
        self.message_sent.emit(message)
        
        # Generate response
        self._generate_response(message)
    
    def _stop_generation(self):
        """Stop the current generation."""
        try:
            self._is_generating = False
            
            # Stop the generator thread if exists
            if hasattr(self, '_current_generator'):
                self._current_generator.stop()
            
            # Add incomplete message to history if exists
            if self._current_response_text:
                self._conversation_history.append({
                    "role": "assistant",
                    "content": self._current_response_text + " [stopped]"
                })
            
            # Cleanup
            self._current_ai_message_widget = None
            self._current_response_text = ""
            
            # Re-enable input
            self.input_field.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.send_btn.show()
            self.stop_btn.hide()
            self.input_field.setFocus()
            
            self._add_system_message("⏹ Generation stopped")
            
        except Exception as e:
            self._logger.error(f"Error stopping generation: {e}")
    
    def _generate_response(self, user_message: str):
        """Generate AI response with streaming."""
        try:
            # Add to conversation history
            self._conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            # Show "thinking" indicator
            self._add_system_message("🤔 AI is thinking...")
            
            # Initialize streaming response
            self._current_response_text = ""
            
            # Generate response using the main app's chat generator with streaming
            if hasattr(self.gguf_app, 'chat_generator') and self.gguf_app.chat_generator:
                # Use existing chat generator
                self._generate_with_chat_generator_streaming(user_message)
            elif hasattr(self.gguf_app, 'model') and self.gguf_app.model:
                # Direct model generation with streaming
                self._generate_with_model_streaming(user_message)
            else:
                self._remove_last_message()
                self._add_system_message("Error: No model available")
                self._is_generating = False
                self.input_field.setEnabled(True)
                self.send_btn.setEnabled(True)
            
        except Exception as e:
            self._logger.error(f"Error generating response: {e}")
            self._remove_last_message()
            self._add_system_message(f"❌ Error: {str(e)}")
            self._is_generating = False
            self.input_field.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.input_field.setFocus()
    
    def _generate_with_chat_generator_streaming(self, message: str):
        """Generate response using chat generator with streaming."""
        try:
            from models.chat_generator import ChatGenerator
            
            # Remove "thinking" message
            self._remove_last_message()
            
            # Create empty AI message bubble for streaming
            self._create_streaming_ai_message()
            
            # Create chat generator thread
            generator = ChatGenerator(
                model=self.gguf_app.model,
                prompt=message,
                chat_history=self._conversation_history[:-1],  # Exclude current user message
                max_tokens=8192,
                temperature=0.7,
                top_p=0.9,
                repeat_penalty=1.1,
                top_k=40
            )
            
            # Connect signals
            generator.token_received.connect(self._on_token_received)
            generator.finished.connect(lambda: self._on_streaming_finished(generator))
            generator.error.connect(self._on_streaming_error)
            
            # Store reference to prevent garbage collection
            self._current_generator = generator
            
            # Start generation
            generator.start()
            
        except Exception as e:
            self._logger.error(f"Chat generator error: {e}")
            self._add_system_message(f"❌ Error: {str(e)}")
            self._is_generating = False
            self.input_field.setEnabled(True)
            self.send_btn.setEnabled(True)
    
    def _generate_with_model_streaming(self, message: str):
        """Generate response directly with model using streaming in background thread."""
        try:
            # Remove "thinking" message
            self._remove_last_message()
            
            # Create empty AI message bubble for streaming
            self._create_streaming_ai_message()
            
            # Build prompt
            prompt = self._build_prompt_for_model(message)
            
            # Create streaming thread
            streaming_thread = StreamingThread(
                model=self.gguf_app.model,
                prompt=prompt,
                max_tokens=8192
            )
            
            # Connect signals
            streaming_thread.token_received.connect(self._on_token_received)
            streaming_thread.finished.connect(lambda: self._on_streaming_finished(streaming_thread))
            streaming_thread.error.connect(self._on_streaming_error)
            
            # Store reference to prevent garbage collection
            self._current_generator = streaming_thread
            
            # Start generation in background
            streaming_thread.start()
            
        except Exception as e:
            self._logger.error(f"Model generation error: {e}")
            self._on_streaming_error(f"Error: {str(e)}")
    
    def _build_prompt_for_model(self, message: str) -> str:
        """Build prompt from conversation history."""
        prompt = "You are a helpful AI assistant. Answer questions clearly and thoroughly.\n\n"
        
        # Add conversation history
        for msg in self._conversation_history[:-1]:  # Exclude current user message
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'user':
                prompt += f"User: {content}\n"
            elif role == 'assistant':
                prompt += f"Assistant: {content}\n"
        
        # Add current message
        prompt += f"User: {message}\nAssistant:"
        
        return prompt
    
    def _create_streaming_ai_message(self):
        """Create an empty AI message bubble for streaming updates."""
        # Create container for left-aligned message
        msg_container = QWidget()
        msg_layout = QHBoxLayout(msg_container)
        msg_layout.setContentsMargins(5, 2, 5, 2)
        msg_layout.setSpacing(0)
        
        if ChatBubble:
            # Use chat bubble widget
            bubble = ChatBubble("", is_user=False)
            bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            bubble.setStyleSheet("""
                QFrame {
                    background-color: #e9ecef;
                    border-radius: 15px;
                    margin: 2px;
                }
                QLabel {
                    color: #333;
                    font-size: 13px;
                    padding: 10px 14px;
                }
            """)
            msg_layout.addWidget(bubble, stretch=2)
            self._current_ai_message_widget = bubble
        else:
            # Fallback to simple label
            label = QLabel("")
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            label.setStyleSheet("""
                background-color: #e9ecef;
                color: #333;
                padding: 10px 14px;
                border-radius: 15px;
                font-size: 13px;
            """)
            msg_layout.addWidget(label, stretch=2)
            self._current_ai_message_widget = label
        
        # Add spacer
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        msg_layout.addItem(spacer)
        
        # Insert before the stretch at the end
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_container)
        self._scroll_to_bottom()
    
    def _on_token_received(self, token: str):
        """Handle received token from streaming generation."""
        try:
            # Accumulate response
            self._current_response_text += token
            
            # Update the message widget
            if self._current_ai_message_widget:
                if ChatBubble and isinstance(self._current_ai_message_widget, ChatBubble):
                    # Update chat bubble
                    self._current_ai_message_widget.update_text(self._current_response_text)
                else:
                    # Update label
                    self._current_ai_message_widget.setText(self._current_response_text)
            
            # Auto-scroll to bottom
            self._scroll_to_bottom()
            
        except Exception as e:
            self._logger.error(f"Error updating token: {e}")
    
    def _on_streaming_finished(self, generator):
        """Handle streaming generation finished."""
        try:
            # Add to history
            if self._current_response_text:
                self._conversation_history.append({
                    "role": "assistant",
                    "content": self._current_response_text
                })
            
            # Cleanup
            self._current_ai_message_widget = None
            self._current_response_text = ""
            
            if hasattr(self, '_current_generator'):
                delattr(self, '_current_generator')
            
        except Exception as e:
            self._logger.error(f"Error finishing streaming: {e}")
        
        finally:
            # Re-enable input
            self._is_generating = False
            self.input_field.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.send_btn.show()
            self.stop_btn.hide()
            self.input_field.setFocus()
    
    def _on_streaming_error(self, error_message: str):
        """Handle streaming generation error."""
        try:
            self._logger.error(f"Streaming error: {error_message}")
            
            # Remove incomplete message if exists
            if self._current_ai_message_widget:
                self._remove_last_message()
            
            self._add_system_message(f"❌ {error_message}")
            
            # Cleanup
            self._current_ai_message_widget = None
            self._current_response_text = ""
            
        except Exception as e:
            self._logger.error(f"Error handling streaming error: {e}")
        
        finally:
            # Re-enable input
            self._is_generating = False
            self.input_field.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.send_btn.show()
            self.stop_btn.hide()
            self.input_field.setFocus()
    
    def _generate_with_chat_generator(self, message: str) -> str:
        """Generate response using chat generator (deprecated - use streaming version)."""
        try:
            # Build conversation context
            conversation = self._conversation_history.copy()
            
            # Generate with very high token limit for unlimited length responses
            response = self.gguf_app.chat_generator.generate_response(
                conversation,
                max_tokens=8192  # Very high limit for long responses
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
            
            # Generate with very high token limit for unlimited length responses
            response = self.gguf_app.model(
                prompt,
                max_tokens=8192,  # Very high limit for long responses
                stop=["User:", "\nUser:"],  # Better stop sequences
                echo=False
            )
            
            return response['choices'][0]['text'].strip()
            
        except Exception as e:
            self._logger.error(f"Model generation error: {e}")
            return f"Error: {str(e)}"
    
    def _add_user_message(self, message: str):
        """Add user message to chat display (right side)."""
        # Create container for right-aligned message
        msg_container = QWidget()
        msg_layout = QHBoxLayout(msg_container)
        msg_layout.setContentsMargins(5, 2, 5, 2)
        msg_layout.setSpacing(0)
        
        # Add spacer (30% minimum on left for right-aligned messages)
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        msg_layout.addItem(spacer)
        
        if ChatBubble:
            # Use chat bubble widget
            bubble = ChatBubble(message, is_user=True)
            bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            bubble.setStyleSheet("""
                QFrame {
                    background-color: #0078d4;
                    border-radius: 15px;
                    margin: 2px;
                }
                QLabel {
                    color: white;
                    font-size: 13px;
                    padding: 10px 14px;
                }
            """)
            msg_layout.addWidget(bubble, stretch=2)  # Takes up to 2/3 of space
        else:
            # Fallback to simple label
            label = QLabel(message)
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            label.setStyleSheet("""
                background-color: #0078d4;
                color: white;
                padding: 10px 14px;
                border-radius: 15px;
                font-size: 13px;
            """)
            msg_layout.addWidget(label, stretch=2)
        
        # Insert before the stretch at the end
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_container)
        self._scroll_to_bottom()
    
    def _add_ai_message(self, message: str):
        """Add AI message to chat display (left side)."""
        # Create container for left-aligned message
        msg_container = QWidget()
        msg_layout = QHBoxLayout(msg_container)
        msg_layout.setContentsMargins(5, 2, 5, 2)
        msg_layout.setSpacing(0)
        
        if ChatBubble:
            # Use chat bubble widget
            bubble = ChatBubble(message, is_user=False)
            bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            bubble.setStyleSheet("""
                QFrame {
                    background-color: #e9ecef;
                    border-radius: 15px;
                    margin: 2px;
                }
                QLabel {
                    color: #333;
                    font-size: 13px;
                    padding: 10px 14px;
                }
            """)
            msg_layout.addWidget(bubble, stretch=2)  # Takes up to 2/3 of space
        else:
            # Fallback to simple label
            label = QLabel(message)
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            label.setStyleSheet("""
                background-color: #e9ecef;
                color: #333;
                padding: 10px 14px;
                border-radius: 15px;
                font-size: 13px;
            """)
            msg_layout.addWidget(label, stretch=2)
        
        # Add spacer (30% minimum on right for left-aligned messages)
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        msg_layout.addItem(spacer)
        
        # Insert before the stretch at the end
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_container)
        self._scroll_to_bottom()
    
    def _add_system_message(self, message: str):
        """Add system message to chat display (centered)."""
        # Create container for centered message
        msg_container = QWidget()
        msg_layout = QHBoxLayout(msg_container)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.addStretch()
        
        label = QLabel(message)
        label.setStyleSheet("""
            color: #6c757d;
            font-size: 11px;
            font-style: italic;
            padding: 5px;
        """)
        msg_layout.addWidget(label)
        msg_layout.addStretch()
        
        # Insert before the stretch at the end
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_container)
        self._scroll_to_bottom()
    
    def _remove_last_message(self):
        """Remove the last message from chat display."""
        # Get the last widget before the stretch
        count = self.chat_layout.count()
        if count > 1:  # Keep the stretch
            item = self.chat_layout.takeAt(count - 2)
            if item and item.widget():
                item.widget().deleteLater()
    
    def _scroll_to_bottom(self):
        """Scroll chat display to bottom."""
        QTimer.singleShot(100, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))
    
    def _copy_all_messages(self):
        """Copy all messages to clipboard."""
        try:
            from PySide6.QtGui import QClipboard
            from PySide6.QtWidgets import QApplication
            
            # Build text from conversation history
            all_text = []
            for msg in self._conversation_history:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                
                if role == 'user':
                    all_text.append(f"User: {content}")
                elif role == 'assistant':
                    all_text.append(f"Assistant: {content}")
                else:
                    all_text.append(f"{role}: {content}")
                
                all_text.append("")  # Empty line between messages
            
            # Join all text
            full_text = "\n".join(all_text)
            
            if full_text.strip():
                # Copy to clipboard
                clipboard = QApplication.clipboard()
                clipboard.setText(full_text)
                self._add_system_message("📋 All messages copied to clipboard!")
            else:
                self._add_system_message("⚠️ No messages to copy")
                
        except Exception as e:
            self._logger.error(f"Error copying messages: {e}")
            self._add_system_message(f"❌ Error copying messages: {e}")
    
    def _clear_chat(self):
        """Clear chat history."""
        # Remove all widgets except the stretch
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        
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
        """Event filter for Enter to send, Shift+Enter for new line."""
        if obj == self.input_field and event.type() == event.Type.KeyPress:
            # Enter without Shift sends the message
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                    # Shift+Enter: insert new line (default behavior)
                    return False
                else:
                    # Plain Enter: send message
                    self._send_message()
                    return True
            # Let all other keys pass through (including Ctrl+V, Ctrl+C, Ctrl+X, Ctrl+A, etc.)
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.window_closed.emit()
        super().closeEvent(event)
