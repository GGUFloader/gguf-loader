# Chat Window
#!/usr/bin/env python3
"""
Floating Chat Window - Chat interface connected to GGUF Loader

Provides a clean, modern chat window that connects to the main GGUF Loader
for AI conversations.
"""

import logging
import threading
from typing import Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QScrollArea, QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import QObject, Qt, Signal, Slot, QTimer, QThread
from PySide6.QtGui import QFont

try:
    from config import FONT_FAMILY
except ImportError:
    FONT_FAMILY = "Segoe UI"

try:
    from widgets.chat_bubble import ChatBubble
except ImportError:
    # Fallback if chat_bubble is not available
    ChatBubble = None

from ui.theme import DARK_TOKENS, LIGHT_TOKENS


class StreamingWorker(QObject):
    """Streams model responses on a worker thread without blocking the UI.

    Follows the services worker pattern (see services/chat_service.py):
    arguments are assigned as attributes before the thread starts and
    :meth:`process` is a zero-arg slot so Qt can invoke it across threads.
    """

    token_received = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop_event = threading.Event()
        self.model = None
        self.prompt = ""
        self.max_tokens = 8192

    @Slot()
    def process(self) -> None:
        """Run streaming generation in the worker thread."""
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
                if self._stop_event.is_set():
                    break

                token = token_data.get('choices', [{}])[0].get('text', '')
                if token:
                    self.token_received.emit(token)

            self.finished.emit()

        except Exception as e:
            self.error.emit(f"Generation error: {str(e)}")

    def stop(self) -> None:
        """Cooperatively stop the streaming generation."""
        self._stop_event.set()


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
        self._current_generator = None  # Active StreamingWorker
        self._current_thread = None     # Its QThread container

        # Theme state (follows the main window)
        self._t = DARK_TOKENS
        self._is_model_loaded = False
        self._styled_widgets = []  # (widget, is_user_or_None, is_fallback)

        # Setup window
        self._setup_window()
        self._setup_ui()
        
        # Connect to model if available
        self._connect_to_model()
    
    def _setup_window(self):
        """Setup window properties."""
        self.setWindowTitle("Floating Chat")
        
        # Set window flags for floating behavior. No minimize button: this is
        # an always-on-top companion window toggled by the floating button, and
        # a minimized window is a trap state (can't be brought back reliably).
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        # Set size
        self.resize(400, 600)
        self.setMinimumSize(300, 400)
        
        # Apply modern styling (theme-aware)
        self.setStyleSheet(self._build_base_stylesheet(self._t))
    
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header
        self.header_label = QLabel("💬 AI Chat")
        self.header_label.setFont(QFont(FONT_FAMILY, 16, QFont.Weight.Bold))
        self.header_label.setStyleSheet(f"color: {self._t['accent']}; padding: 5px;")
        layout.addWidget(self.header_label)
        
        # Model status indicator
        self.status_label = QLabel("⚪ Model: Not loaded")
        self.status_label.setStyleSheet(self._status_style(False))
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
        self.copy_all_btn = QPushButton("📋 Copy All")
        self.copy_all_btn.setStyleSheet(self._ghost_style())
        self.copy_all_btn.clicked.connect(self._copy_all_messages)
        button_layout.addWidget(self.copy_all_btn)
        
        # Clear button
        self.clear_btn = QPushButton("🗑️ Clear")
        self.clear_btn.setStyleSheet(self._ghost_style())
        self.clear_btn.clicked.connect(self._clear_chat)
        button_layout.addWidget(self.clear_btn)
        
        # Stop button (hidden by default)
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setStyleSheet(self._danger_style())
        self.stop_btn.clicked.connect(self._stop_generation)
        self.stop_btn.hide()
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        
        # Send button with icon
        self.send_btn = QPushButton("➤")  # Send arrow icon
        self.send_btn.setFixedSize(45, 45)  # Circular button
        self.send_btn.setStyleSheet(self._send_style())
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

            # Follow the main window's theme (and future changes to it)
            if hasattr(self.gguf_app, 'is_dark_mode'):
                self.apply_theme(bool(self.gguf_app.is_dark_mode))
            if hasattr(self.gguf_app, 'theme_changed'):
                self.gguf_app.theme_changed.connect(self.apply_theme)

        except Exception as e:
            self._logger.error(f"Error connecting to model: {e}")
    
    def set_model_status(self, is_loaded: bool):
        """Update model status indicator."""
        self._is_model_loaded = is_loaded
        if is_loaded:
            self.status_label.setText("🟢 Model: Ready")
            self.send_btn.setEnabled(True)
        else:
            self.status_label.setText("🔴 Model: Not loaded")
            self.send_btn.setEnabled(False)
        self._apply_status_style()

    # ------------------------------------------------------------------
    # Theming (follows the main window's dark/light mode)
    # ------------------------------------------------------------------
    def apply_theme(self, is_dark: bool):
        """Re-style the whole window for dark or light mode."""
        self._t = DARK_TOKENS if is_dark else LIGHT_TOKENS
        self.setStyleSheet(self._build_base_stylesheet(self._t))
        if not hasattr(self, 'header_label'):
            return
        self.header_label.setStyleSheet(f"color: {self._t['accent']}; padding: 5px;")
        self._apply_status_style()
        self.copy_all_btn.setStyleSheet(self._ghost_style())
        self.clear_btn.setStyleSheet(self._ghost_style())
        self.stop_btn.setStyleSheet(self._danger_style())
        self.send_btn.setStyleSheet(self._send_style())
        self._restyle_messages()

    def _apply_status_style(self):
        self.status_label.setStyleSheet(self._status_style(self._is_model_loaded))

    def _restyle_messages(self):
        """Re-apply the current theme to every rendered message."""
        for widget, is_user, is_fallback in self._styled_widgets:
            if is_user is None:
                widget.setStyleSheet(self._system_style())
            elif is_fallback:
                widget.setStyleSheet(self._fallback_bubble_style(is_user))
            else:
                widget.setStyleSheet(self._bubble_style(is_user))

    def _build_base_stylesheet(self, t: dict) -> str:
        return f"""
QWidget {{
    background-color: {t['bg']};
    font-family: 'Segoe UI', Arial, sans-serif;
}}
QTextEdit {{
    background-color: {t['elevated']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
    color: {t['text']};
}}
QPushButton {{
    background-color: {t['elevated']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 10px 20px;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {t['elevatedHover']};
    color: {t['text']};
}}
QPushButton:pressed {{
    background-color: {t['pressedBg']};
}}
QPushButton:disabled {{
    background-color: {t['disabledBg']};
    color: {t['textMuted']};
}}
QLabel {{
    color: {t['textSec']};
    font-size: 12px;
}}
"""

    def _ghost_style(self) -> str:
        t = self._t
        return f"""
QPushButton {{
    background-color: {t['elevated']};
    color: {t['textSec']};
    border: 1px solid {t['border']};
    padding: 8px 15px;
}}
QPushButton:hover {{
    background-color: {t['elevatedHover']};
}}
"""

    def _danger_style(self) -> str:
        t = self._t
        return f"""
QPushButton {{
    background-color: {t['danger']};
    color: white;
    padding: 8px 15px;
}}
QPushButton:hover {{
    background-color: {t['dangerHover']};
}}
"""

    def _send_style(self) -> str:
        t = self._t
        return f"""
QPushButton {{
    background-color: {t['accent']};
    color: {t['onAccent']};
    border: none;
    border-radius: 22px;
    font-size: 18px;
    font-weight: bold;
    padding: 0px;
}}
QPushButton:hover {{ background-color: {t['accentHover']}; }}
QPushButton:pressed {{ background-color: {t['accentPressed']}; }}
QPushButton:disabled {{
    background-color: {t['disabledBg']};
    color: {t['textMuted']};
}}
"""

    def _bubble_style(self, is_user: bool) -> str:
        t = self._t
        if is_user:
            return f"""
QFrame {{
    background-color: {t['accentSoft']};
    border: 1px solid {t['accentBorder']};
    border-radius: 15px;
    margin: 2px;
}}
QLabel {{
    color: {t['text']};
    font-size: 13px;
    padding: 10px 14px;
}}
"""
        return f"""
QFrame {{
    background-color: {t['elevated']};
    border: 1px solid {t['border']};
    border-radius: 15px;
    margin: 2px;
}}
QLabel {{
    color: {t['text']};
    font-size: 13px;
    padding: 10px 14px;
}}
"""

    def _fallback_bubble_style(self, is_user: bool) -> str:
        t = self._t
        if is_user:
            bg, border = t['accentSoft'], t['accentBorder']
        else:
            bg, border = t['elevated'], t['border']
        return f"""
QLabel {{
    background-color: {bg};
    color: {t['text']};
    padding: 10px 14px;
    border: 1px solid {border};
    border-radius: 15px;
    font-size: 13px;
}}
"""

    def _system_style(self) -> str:
        return f"""
color: {self._t['textMuted']};
font-size: 11px;
font-style: italic;
padding: 5px;
"""

    def _status_style(self, is_loaded: bool) -> str:
        color = self._t['success'] if is_loaded else self._t['danger']
        return f"color: {color}; font-size: 11px; padding: 2px;"""
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
            
            # Stop the generator worker if exists
            generator = self._current_generator
            if generator is not None:
                generator.stop()
            
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
            
            # Generate response using the loaded model with streaming
            if hasattr(self.gguf_app, 'model') and self.gguf_app.model:
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
    
    def _generate_with_model_streaming(self, message: str):
        """Generate response directly with model using streaming in background thread."""
        try:
            # Remove "thinking" message
            self._remove_last_message()
            
            # Create empty AI message bubble for streaming
            self._create_streaming_ai_message()
            
            # Build prompt
            prompt = self._build_prompt_for_model(message)
            
            # Build the worker (args as attributes) and run it on a fresh thread
            worker = StreamingWorker()
            worker.model = self.gguf_app.model
            worker.prompt = prompt
            worker.max_tokens = 8192

            thread = QThread(self)
            worker.moveToThread(thread)

            thread.started.connect(worker.process)
            worker.token_received.connect(self._on_token_received)
            worker.finished.connect(self._on_streaming_finished)
            worker.error.connect(self._on_streaming_error)
            worker.finished.connect(thread.quit)
            worker.error.connect(thread.quit)
            thread.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(lambda: self._clear_generator_refs(thread, worker))

            # Store references to prevent garbage collection
            self._current_generator = worker
            self._current_thread = thread

            # Start generation in background
            thread.start()

        except Exception as e:
            self._logger.error(f"Model generation error: {e}")
            self._current_generator = None
            self._current_thread = None
            self._on_streaming_error(f"Error: {str(e)}")

    def _clear_generator_refs(self, thread, worker):
        """Drop references once the finished thread is gone (avoids stale handles)."""
        if self._current_thread is thread:
            self._current_thread = None
        if self._current_generator is worker:
            self._current_generator = None
    
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
            bubble.setStyleSheet(self._bubble_style(False))
            msg_layout.addWidget(bubble, stretch=2)
            self._current_ai_message_widget = bubble
            self._styled_widgets.append((bubble, False, False))
        else:
            # Fallback to simple label
            label = QLabel("")
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            label.setStyleSheet(self._fallback_bubble_style(False))
            msg_layout.addWidget(label, stretch=2)
            self._current_ai_message_widget = label
            self._styled_widgets.append((label, False, True))
        
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
    
    def _on_streaming_finished(self):
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
            bubble.setStyleSheet(self._bubble_style(True))
            msg_layout.addWidget(bubble, stretch=2)  # Takes up to 2/3 of space
            self._styled_widgets.append((bubble, True, False))
        else:
            # Fallback to simple label
            label = QLabel(message)
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            label.setStyleSheet(self._fallback_bubble_style(True))
            msg_layout.addWidget(label, stretch=2)
            self._styled_widgets.append((label, True, True))

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
        label.setStyleSheet(self._system_style())
        msg_layout.addWidget(label)
        self._styled_widgets.append((label, None, False))
        msg_layout.addStretch()
        
        # Insert before the stretch at the end
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_container)
        self._scroll_to_bottom()
    
    def _remove_last_message(self):
        """Remove the last message from chat display."""
        if self._styled_widgets:
            self._styled_widgets.pop()
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
        self._styled_widgets.clear()
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
    
    def _shutdown_generation(self):
        """Stop any in-flight generation before the window is destroyed."""
        worker = self._current_generator
        if worker is not None:
            worker.stop()
        thread = self._current_thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(2000)
        self._current_generator = None
        self._current_thread = None

    def closeEvent(self, event):
        """Handle window close event."""
        self._shutdown_generation()
        self.window_closed.emit()
        super().closeEvent(event)
