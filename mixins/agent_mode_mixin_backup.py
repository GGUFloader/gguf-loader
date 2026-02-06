"""
Chat Handler Mixin - Handles chat functionality and message processing
"""
from PySide6.QtWidgets import QMessageBox, QWidget, QHBoxLayout, QSpacerItem, QSizePolicy, QLabel, QVBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from config import MAX_TOKENS, FONT_FAMILY
from models.chat_generator import ChatGenerator
from widgets.chat_bubble import ChatBubble


class ChatHandlerMixin:
    """Mixin class for handling chat functionality and message processing"""

    def send_message(self):
        """Send user message and get AI response"""
        if not self.model:
            QMessageBox.warning(self, "No Model", "Please load a model first.")
            return

        user_message = self.input_text.toPlainText().strip()
        if not user_message:
            return

        # Check if agent mode is enabled
        if hasattr(self, 'agent_mode_enabled') and self.agent_mode_enabled:
            # Route message through agent mode
            if hasattr(self, 'send_message_to_agent'):
                # Add user message to chat first
                self.add_chat_message(user_message, is_user=True)
                self.input_text.clear()
                
                # Send to agent
                handled = self.send_message_to_agent(user_message)
                if handled:
                    return  # Agent handled the message
            # If agent mode failed, fall through to regular chat
        
        # Regular chat mode (non-agent)
        # Disable send button during generation
        self.send_btn.setEnabled(False)

        # Add user message to chat
        self.add_chat_message(user_message, is_user=True)
        self.input_text.clear()

        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Start generating response
        self.start_ai_response()

        # Create and start chat generator
        self.chat_generator = ChatGenerator(
            model=self.model,
            prompt=user_message,
            chat_history=self.conversation_history,
            max_tokens=MAX_TOKENS,
            system_prompt_name="assistant"
        )

        # Connect signals
        self.chat_generator.token_received.connect(self.on_token_received)
        self.chat_generator.finished.connect(self.on_generation_finished)
        self.chat_generator.error.connect(self.on_generation_error)
        self.chat_generator.start()

    def on_input_text_changed(self):
        """Enable/disable send button based on input text and model status"""
        has_text = bool(self.input_text.toPlainText().strip())
        has_model = self.model is not None
        self.send_btn.setEnabled(has_text and has_model)

    def start_ai_response(self):
        """Start a new AI response bubble"""
        # Reset current AI text
        self.current_ai_text = ""

        # Create single AI bubble instance
        self.current_ai_bubble = ChatBubble("", is_user=False)
        self.current_ai_bubble.update_style(self.is_dark_mode)
        # Apply current font size setting
        if hasattr(self, 'current_font_size'):
            self.current_ai_bubble.set_font_size(self.current_font_size)

        # Create container for the bubble with responsive layout
        bubble_container = QWidget()
        bubble_layout = QHBoxLayout(bubble_container)
        bubble_layout.setContentsMargins(0, 0, 0, 0)
        bubble_layout.setSpacing(0)

        # Add the bubble to layout (left-aligned for AI) with stretch for responsiveness
        # Use stretch factors: bubble takes 3 parts, spacer takes 1 part (~75% width)
        bubble_layout.addWidget(self.current_ai_bubble, 3, Qt.AlignmentFlag.AlignTop)
        bubble_layout.addStretch(1)

        # Insert before spacer in chat layout
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble_container)
        self.chat_bubbles.append((bubble_container, self.current_ai_bubble))

        self.scroll_to_bottom()

    def on_token_received(self, token: str):
        """Handle new token from AI"""
        try:
            if not self.current_ai_bubble:
                return

            self.current_ai_text += token
            self.current_ai_bubble.update_text(self.current_ai_text)
            self.scroll_to_bottom()

        except Exception as e:
            print(f"Error updating token: {e}")

    def on_generation_finished(self):
        """Handle completion of AI response"""
        if self.current_ai_bubble:
            final_text = self.current_ai_text.strip()
            # Add to conversation history
            self.conversation_history.append({"role": "assistant", "content": final_text})

        self.current_ai_bubble = None
        self.current_ai_text = ""
        self.send_btn.setEnabled(True)

    def on_generation_error(self, error_msg: str):
        """Handle AI generation errors"""
        if self.current_ai_bubble:
            self.current_ai_bubble.update_text(f"❌ Error: {error_msg}")

        self.current_ai_bubble = None
        self.current_ai_text = ""
        self.send_btn.setEnabled(True)

    def add_chat_message(self, message: str, is_user: bool):
        """Add a chat message bubble"""
        bubble = ChatBubble(message, is_user)
        bubble.update_style(self.is_dark_mode)
        # Apply current font size setting
        if hasattr(self, 'current_font_size'):
            bubble.set_font_size(self.current_font_size)

        # Create container with responsive alignment
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if is_user:
            # User messages on the right with responsive sizing
            # Spacer takes 1 part, bubble takes 3 parts (~75% width)
            layout.addStretch(1)
            layout.addWidget(bubble, 3)
        else:
            # AI messages on the left with responsive sizing
            layout.addWidget(bubble, 3)
            layout.addStretch(1)

        # Insert before spacer
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, container)
        self.chat_bubbles.append((container, bubble))

        self.scroll_to_bottom()

    def add_system_message(self, message: str):
        """Add a system message"""
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        font = QFont(FONT_FAMILY, 12)
        font.setItalic(True)
        label.setFont(font)
        label.setStyleSheet("color: #888; margin: 10px; padding: 10px;")

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, label)
        self.scroll_to_bottom()

    def clear_chat(self):
        """Clear the chat history"""
        # Clear conversation history
        self.conversation_history = []

        # Remove all chat bubbles
        for container, bubble in self.chat_bubbles:
            container.setParent(None)
        self.chat_bubbles.clear()

        # Add welcome message
        if self.model:
            self.add_system_message("🤖 Chat cleared. Ready for new conversation!")

    def toggle_dark_mode(self, enabled: bool):
        """Toggle dark mode"""
        self.is_dark_mode = enabled
        self.apply_styles()

        # Update all chat bubbles
        for container, bubble in self.chat_bubbles:
            bubble.update_style(self.is_dark_mode)

    def safe_update_ui(self, func, *args, **kwargs):
        """Safely update UI from worker threads"""
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(f"UI update error: {e}")  # Or use proper logging