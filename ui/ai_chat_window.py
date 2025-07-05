"""
Main application window - English only
"""
from pathlib import Path

# Single comprehensive import from config
from config import (
    MAX_TOKENS,
    WINDOW_TITLE,
    WINDOW_SIZE,
    MIN_WINDOW_SIZE,
    GPU_OPTIONS,
    DEFAULT_CONTEXT_SIZES,
    FONT_FAMILY,
    BUBBLE_FONT_SIZE
)

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QFileDialog, QLabel,
    QComboBox, QCheckBox, QSplitter, QFrame, QScrollArea,
    QMessageBox, QProgressBar, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QIcon

from models.model_loader import ModelLoader, LLAMA_AVAILABLE
from models.chat_generator import ChatGenerator
from widgets.chat_bubble import ChatBubble
import os
import sys


class AIChat(QMainWindow):
    """Main AI Chat Application Window - English Only"""
    # Define signals
    model_loaded = Signal(object)
    generation_finished = Signal()
    generation_error = Signal(str)

    def safe_update_ui(self, func, *args, **kwargs):
        """Safely update UI from worker threads"""
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(f"UI update error: {e}")  # Or use proper logging

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

    def __init__(self):
        super().__init__()
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")

        icon_path = os.path.join(base_path, "icon.ico")
        self.setWindowIcon(QIcon(icon_path))
        self.model = None
        self.model_loader = None
        self.chat_generator = None
        self.conversation_history = []
        self.is_dark_mode = False
        self.chat_bubbles = []
        self.current_ai_bubble = None
        self.current_ai_text = ""

        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        """Setup the main user interface"""
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(*MIN_WINDOW_SIZE)
        self.resize(*WINDOW_SIZE)
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Setup sidebar and chat area
        self.setup_sidebar(splitter)
        self.setup_chat_area(splitter)

        # Set splitter proportions
        splitter.setSizes([300, 900])

    def setup_sidebar(self, parent):
        """Setup the left sidebar with controls"""
        sidebar = QFrame()
        sidebar.setFixedWidth(320)
        sidebar.setFrameStyle(QFrame.StyledPanel)

        layout = QVBoxLayout(sidebar)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # Title
        title = QLabel("🤖 AI Chat Settings")
        title.setFont(QFont(FONT_FAMILY, 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Model section
        model_label = QLabel("📁 Model Configuration")
        model_label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        layout.addWidget(model_label)

        # Load model button
        self.load_model_btn = QPushButton("Select GGUF Model")
        self.load_model_btn.setMinimumHeight(40)
        self.load_model_btn.clicked.connect(self.load_model)
        layout.addWidget(self.load_model_btn)

        # Model info
        self.model_info = QLabel("No model loaded")
        self.model_info.setWordWrap(True)
        self.model_info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.model_info)

        # Processing mode
        processing_label = QLabel("⚡ Processing Mode")
        processing_label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        layout.addWidget(processing_label)

        self.processing_combo = QComboBox()
        self.processing_combo.addItems(GPU_OPTIONS)
        self.processing_combo.setMinimumHeight(35)
        layout.addWidget(self.processing_combo)

        # Context length
        context_label = QLabel("📏 Context Length")
        context_label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        layout.addWidget(context_label)

        self.context_combo = QComboBox()
        self.context_combo.addItems(DEFAULT_CONTEXT_SIZES)
        self.context_combo.setCurrentIndex(1)  # Default to 2048
        self.context_combo.setMinimumHeight(35)
        layout.addWidget(self.context_combo)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready to load model")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Appearance section
        appearance_label = QLabel("🎨 Appearance")
        appearance_label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        layout.addWidget(appearance_label)

        # Dark mode toggle
        self.dark_mode_cb = QCheckBox("🌙 Dark Mode")
        self.dark_mode_cb.setMinimumHeight(30)
        self.dark_mode_cb.toggled.connect(self.toggle_dark_mode)
        layout.addWidget(self.dark_mode_cb)

        # Clear chat button
        self.clear_chat_btn = QPushButton("🗑️ Clear Chat")
        self.clear_chat_btn.setMinimumHeight(35)
        self.clear_chat_btn.clicked.connect(self.clear_chat)
        layout.addWidget(self.clear_chat_btn)

        # Spacer
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # About section
        about_label = QLabel("ℹ️ About")
        about_label.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        layout.addWidget(about_label)

        about_text= QLabel("Developed by Hussain Nazary\nGithub ID:@hussainnazary2")
        about_text.setWordWrap(True)
        about_text.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(about_text)

        parent.addWidget(sidebar)

    def setup_chat_area(self, parent):
        """Setup the main chat area"""
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.setSpacing(0)
        chat_layout.setContentsMargins(0, 0, 0, 0)

        # Chat history area
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Chat container
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setSpacing(10)
        self.chat_layout.setContentsMargins(20, 20, 20, 20)
        self.chat_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.chat_scroll.setWidget(self.chat_container)
        chat_layout.addWidget(self.chat_scroll)

        # Input area
        input_frame = QFrame()
        input_frame.setFrameStyle(QFrame.StyledPanel)
        input_frame.setMaximumHeight(150)

        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(15, 10, 15, 10)

        # Input text area
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Type your message here...")
        self.input_text.setMaximumHeight(80)
        self.input_text.setFont(QFont(FONT_FAMILY, BUBBLE_FONT_SIZE))
        self.input_text.setLayoutDirection(Qt.LeftToRight)  # Always left-to-right for English

        # Send button
        button_layout = QHBoxLayout()
        button_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumSize(100, 35)
        self.send_btn.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setEnabled(False)

        button_layout.addWidget(self.send_btn)

        input_layout.addWidget(self.input_text)
        input_layout.addLayout(button_layout)

        chat_layout.addWidget(input_frame)

        # Connect Enter key to send
        self.input_text.installEventFilter(self)

        parent.addWidget(chat_widget)

    def eventFilter(self, obj, event):
        """Handle Enter key press in input field"""
        if obj == self.input_text:
            if event.type() == event.Type.KeyPress:
                if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                    if not event.modifiers() & Qt.ShiftModifier:
                        self.send_message()
                        return True
        return super().eventFilter(obj, event)

    def load_model(self):
        """Load a GGUF model file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select GGUF Model File",
            "",
            "GGUF Files (*.gguf);;All Files (*)"
        )

        if not file_path:
            return

        if not LLAMA_AVAILABLE:
            QMessageBox.critical(
                self,
                "Missing Dependency",
                "llama-cpp-python is required but not installed.\n\n"
                "Install it with: pip install llama-cpp-python"
            )
            return

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.load_model_btn.setEnabled(False)
        self.status_label.setText("Loading model...")

        # Get settings
        use_gpu = self.processing_combo.currentText() == "GPU Accelerated"
        n_ctx = int(self.context_combo.currentText())

        # Start loading in thread
        self.model_loader = ModelLoader(file_path, use_gpu, n_ctx)
        self.model_loader.progress.connect(self.on_loading_progress)
        self.model_loader.finished.connect(self.on_model_loaded)
        self.model_loader.error.connect(self.on_loading_error)
        self.model_loader.start()

    def closeEvent(self, event):
        """Handle application close event"""
        try:
            # Stop any running generation
            if hasattr(self, 'chat_generator') and self.chat_generator:
                if self.chat_generator.isRunning():
                    self.chat_generator.terminate()
                    self.chat_generator.wait(3000)  # Wait up to 3 seconds

            # Stop model loader if running
            if hasattr(self, 'model_loader') and self.model_loader:
                if self.model_loader.isRunning():
                    self.model_loader.terminate()
                    self.model_loader.wait(3000)

            event.accept()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            event.accept()

    def on_loading_progress(self, message: str):
        """Handle loading progress updates"""
        self.status_label.setText(message)

    def on_model_loaded(self, model):
        """Handle successful model loading"""
        self.model = model
        self.progress_bar.setVisible(False)
        self.load_model_btn.setEnabled(True)
        self.send_btn.setEnabled(True)

        model_name = Path(self.model_loader.model_path).name
        self.model_info.setText(f"✅ Loaded: {model_name}")
        self.status_label.setText("Model ready! Start chatting...")

        # Add system message
        self.add_system_message("🤖 AI Assistant loaded and ready to help!")

    def on_loading_error(self, error_msg: str):
        """Handle model loading errors"""
        self.progress_bar.setVisible(False)
        self.load_model_btn.setEnabled(True)
        self.status_label.setText(f"❌ Error: {error_msg}")

        QMessageBox.critical(self, "Model Loading Error", error_msg)

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

    def send_message(self):
        """Send user message and get AI response"""
        if not self.model:
            QMessageBox.warning(self, "No Model", "Please load a model first.")
            return

        user_message = self.input_text.toPlainText().strip()
        if not user_message:
            return

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

    def start_ai_response(self):
        """Start a new AI response bubble"""
        # Reset current AI text
        self.current_ai_text = ""

        # Create single AI bubble instance
        self.current_ai_bubble = ChatBubble("", is_user=False)
        self.current_ai_bubble.update_style(self.is_dark_mode)

        # Create container for the bubble
        bubble_container = QWidget()
        bubble_layout = QHBoxLayout(bubble_container)
        bubble_layout.setContentsMargins(0, 0, 0, 0)

        # Add the bubble to layout (left-aligned for AI)
        bubble_layout.addWidget(self.current_ai_bubble, 0, Qt.AlignmentFlag.AlignTop)
        bubble_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Insert before spacer in chat layout
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble_container)
        self.chat_bubbles.append((bubble_container, self.current_ai_bubble))

        self.scroll_to_bottom()

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

        # Create container with proper alignment
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        if is_user:
            # User messages on the right
            layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
            layout.addWidget(bubble)
        else:
            # AI messages on the left
            layout.addWidget(bubble)
            layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Insert before spacer
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, container)
        self.chat_bubbles.append((container, bubble))

        self.scroll_to_bottom()

    def add_system_message(self, message: str):
        """Add a system message"""
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        font = QFont(FONT_FAMILY, 12)
        font.setItalic(True)
        label.setFont(font)
        label.setStyleSheet("color: #888; margin: 10px; padding: 10px;")

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, label)
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        """Scroll chat to bottom"""
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))

    def toggle_dark_mode(self, enabled: bool):
        """Toggle dark mode"""
        self.is_dark_mode = enabled
        self.apply_styles()

        # Update all chat bubbles
        for container, bubble in self.chat_bubbles:
            bubble.update_style(self.is_dark_mode)

    def apply_styles(self):
        """Apply comprehensive dark/light theme to entire application"""
        if self.is_dark_mode:
            # Complete dark theme
            self.setStyleSheet("""
                /* Main Window */
                QMainWindow { 
                    background-color: #1e1e1e; 
                    color: #ffffff; 
                }

                /* Text Input */
                QTextEdit, QLineEdit { 
                    background-color: #2d2d2d; 
                    color: #ffffff; 
                    border: 1px solid #404040; 
                    border-radius: 8px;
                    padding: 8px;
                }

                /* Scroll Areas */
                QScrollArea { 
                    background-color: #1e1e1e; 
                    border: none;
                }
                
                QScrollArea QWidget {
                    background-color: #1e1e1e;
                }

                /* Buttons */
                QPushButton {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 6px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }

                /* Labels */
                QLabel {
                    color: #ffffff;
                    background-color: transparent;
                }

                /* Checkboxes */
                QCheckBox {
                    color: #ffffff;
                    background-color: transparent;
                }

                /* Combo Boxes */
                QComboBox {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #404040;
                    border-radius: 6px;
                    padding: 4px 8px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    color: #ffffff;
                }

                /* Frames */
                QFrame {
                    background-color: #1e1e1e;
                    color: #ffffff;
                }

                /* Splitters */
                QSplitter::handle {
                    background-color: #404040;
                }

                /* Scroll Bars */
                QScrollBar:vertical {
                    background-color: #2d2d2d;
                    width: 12px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background-color: #555555;
                    border-radius: 6px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #666666;
                }
            """)
        else:
            # Light theme
            self.setStyleSheet("""
                QMainWindow { 
                    background-color: #ffffff; 
                    color: #000000; 
                }
                QTextEdit, QLineEdit { 
                    background-color: #ffffff; 
                    color: #000000; 
                    border: 1px solid #cccccc; 
                    border-radius: 8px;
                    padding: 8px;
                }
                QScrollArea { 
                    background-color: #ffffff; 
                    border: none;
                }
                QPushButton {
                    background-color: #f0f0f0;
                    color: #000000;
                    border: 1px solid #cccccc;
                    border-radius: 6px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)