"""
UI Setup Mixin - Handles all UI setup and layout creation
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QComboBox, QCheckBox, QSplitter, QFrame, QScrollArea,
    QProgressBar, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from config import (
    GPU_OPTIONS, DEFAULT_CONTEXT_SIZES, FONT_FAMILY, BUBBLE_FONT_SIZE
)
from addon_manager import AddonManager, AddonSidebarFrame


class CustomTextEdit(QTextEdit):
    """Custom QTextEdit with proper Enter/Shift+Enter handling"""
    send_message = Signal()
    
    def keyPressEvent(self, event):
        """Handle Enter key press"""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Check if Shift is pressed
            if event.modifiers() & Qt.ShiftModifier:
                # Shift+Enter: insert new line
                self.insertPlainText("\n")
            else:
                # Enter only: send message
                self.send_message.emit()
                return  # Event handled
        # For all other keys, use default behavior
        super().keyPressEvent(event)


class UISetupMixin:
    """Mixin class for handling UI setup and layout creation"""

    def setup_main_layout(self):
        """Setup the main layout with splitter"""
        # Initialize addon manager
        self.addon_manager = AddonManager()
        
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

        # Setup main sidebar and chat area (addon sidebar handled by parent app)
        self.setup_sidebar(splitter)
        self.setup_chat_area(splitter)

        # Set splitter proportions (main sidebar, chat area)
        splitter.setSizes([300, 900])

    def setup_addon_sidebar(self, parent):
        """Setup the addon sidebar - DISABLED: handled by parent app"""
        # This method is disabled because the parent GGUFLoaderApp handles addon sidebar
        pass

    def setup_sidebar_layout(self):
        """Additional sidebar layout setup if needed"""
        pass

    def setup_chat_area_layout(self):
        """Additional chat area layout setup if needed"""
        pass

    def setup_sidebar(self, parent):
        """Setup the left sidebar with controls"""
        sidebar = QFrame()
        # Use min/max instead of fixed width for responsive sizing
        sidebar.setMinimumWidth(280)
        sidebar.setMaximumWidth(400)
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
        self._setup_model_section(layout)

        # Processing section
        self._setup_processing_section(layout)

        # Context section
        self._setup_context_section(layout)

        # Progress and status
        self._setup_progress_section(layout)

        # Appearance section
        self._setup_appearance_section(layout)

        # About section
        self._setup_about_section(layout)

        parent.addWidget(sidebar)

    def _setup_model_section(self, layout):
        """Setup model configuration section"""
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

    def _setup_processing_section(self, layout):
        """Setup processing mode section"""
        processing_label = QLabel("⚡ Processing Mode")
        processing_label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        layout.addWidget(processing_label)

        self.processing_combo = QComboBox()
        self.processing_combo.addItems(GPU_OPTIONS)
        self.processing_combo.setMinimumHeight(35)
        layout.addWidget(self.processing_combo)

    def _setup_context_section(self, layout):
        """Setup context length section"""
        context_label = QLabel("📏 Context Length")
        context_label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        layout.addWidget(context_label)

        self.context_combo = QComboBox()
        self.context_combo.addItems(DEFAULT_CONTEXT_SIZES)
        self.context_combo.setCurrentIndex(1)  # Default to 2048
        self.context_combo.setMinimumHeight(35)
        layout.addWidget(self.context_combo)

    def _setup_progress_section(self, layout):
        """Setup progress bar and status"""
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready to load model")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _setup_appearance_section(self, layout):
        """Setup appearance controls"""
        appearance_label = QLabel("🎨 Appearance")
        appearance_label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        layout.addWidget(appearance_label)

        # Dark mode toggle
        self.dark_mode_cb = QCheckBox("🌙 Dark Mode")
        self.dark_mode_cb.setMinimumHeight(30)
        self.dark_mode_cb.toggled.connect(self.toggle_dark_mode)
        layout.addWidget(self.dark_mode_cb)

        # Text size controls
        text_size_label = QLabel("📝 Text Size")
        text_size_label.setFont(QFont(FONT_FAMILY, 11))
        layout.addWidget(text_size_label)

        # Text size control row
        text_size_row = QWidget()
        text_size_layout = QHBoxLayout(text_size_row)
        text_size_layout.setContentsMargins(0, 0, 0, 0)
        text_size_layout.setSpacing(10)

        # Decrease button
        self.decrease_font_btn = QPushButton("A-")
        self.decrease_font_btn.setFixedSize(40, 35)
        self.decrease_font_btn.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.decrease_font_btn.clicked.connect(self.decrease_font_size)
        text_size_layout.addWidget(self.decrease_font_btn)

        # Current size label
        self.font_size_label = QLabel("14")
        self.font_size_label.setAlignment(Qt.AlignCenter)
        self.font_size_label.setMinimumWidth(40)
        self.font_size_label.setFont(QFont(FONT_FAMILY, 12))
        text_size_layout.addWidget(self.font_size_label)

        # Increase button
        self.increase_font_btn = QPushButton("A+")
        self.increase_font_btn.setFixedSize(40, 35)
        self.increase_font_btn.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.increase_font_btn.clicked.connect(self.increase_font_size)
        text_size_layout.addWidget(self.increase_font_btn)

        text_size_layout.addStretch()
        layout.addWidget(text_size_row)

        # Clear chat button
        self.clear_chat_btn = QPushButton("🗑️ Clear Chat")
        self.clear_chat_btn.setMinimumHeight(35)
        self.clear_chat_btn.clicked.connect(self.clear_chat)
        layout.addWidget(self.clear_chat_btn)

        # Spacer
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

    def _setup_about_section(self, layout):
        """Setup about section"""
        about_label = QLabel("ℹ️ About")
        about_label.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        layout.addWidget(about_label)

        about_text = QLabel("Developed by Hussain Nazary\nGithub ID:@hussainnazary2")
        about_text.setWordWrap(True)
        about_text.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(about_text)

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
        self._setup_input_area(chat_layout)

        parent.addWidget(chat_widget)

    def _setup_input_area(self, parent_layout):
        """Setup the input area with text field and send button"""
        input_frame = QFrame()
        input_frame.setFrameStyle(QFrame.StyledPanel)
        input_frame.setMaximumHeight(150)

        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(15, 10, 15, 10)

        # Input text area
        self.input_text = CustomTextEdit()
        self.input_text.setPlaceholderText("Type your message here...")
        self.input_text.setMaximumHeight(80)
        self.input_text.setFont(QFont(FONT_FAMILY, BUBBLE_FONT_SIZE))
        self.input_text.setLayoutDirection(Qt.LeftToRight)  # Always left-to-right for English
        self.input_text.textChanged.connect(self.on_input_text_changed)
        self.input_text.send_message.connect(self.send_message)

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

        parent_layout.addWidget(input_frame)

    def increase_font_size(self):
        """Increase chat bubble font size"""
        if not hasattr(self, 'current_font_size'):
            self.current_font_size = 14
        
        if self.current_font_size < 24:  # Max font size
            self.current_font_size += 2
            self._apply_font_size_to_all_bubbles()
            if hasattr(self, 'font_size_label'):
                self.font_size_label.setText(str(self.current_font_size))

    def decrease_font_size(self):
        """Decrease chat bubble font size"""
        if not hasattr(self, 'current_font_size'):
            self.current_font_size = 14
        
        if self.current_font_size > 10:  # Min font size
            self.current_font_size -= 2
            self._apply_font_size_to_all_bubbles()
            if hasattr(self, 'font_size_label'):
                self.font_size_label.setText(str(self.current_font_size))

    def _apply_font_size_to_all_bubbles(self):
        """Apply current font size to all existing chat bubbles"""
        if not hasattr(self, 'chat_bubbles'):
            return
            
        for container, bubble in self.chat_bubbles:
            try:
                bubble.set_font_size(self.current_font_size)
            except Exception as e:
                print(f"Error updating bubble font: {e}")
        
        # Force layout update
        if hasattr(self, 'chat_container'):
            self.chat_container.updateGeometry()
            self.chat_container.update()
        
        if hasattr(self, 'chat_scroll'):
            self.chat_scroll.update()