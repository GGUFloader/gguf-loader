"""
UI Setup Mixin - Handles all UI setup and layout creation
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QComboBox, QCheckBox, QSplitter, QFrame, QScrollArea,
    QProgressBar, QSpacerItem, QSizePolicy, QSlider
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QKeySequence
from PySide6.QtCore import QTimer
from config import (
    GPU_OPTIONS, DEFAULT_CONTEXT_SIZES, FONT_FAMILY, BUBBLE_FONT_SIZE
)
from addon_manager import AddonManager, AddonSidebarFrame


class CustomTextEdit(QTextEdit):
    """Custom QTextEdit with proper Enter/Shift+Enter handling"""
    send_message = Signal()
    
    def keyPressEvent(self, event):
        """Handle Enter key press only, let Qt handle all other shortcuts"""
        # Only intercept Enter/Return keys - let Qt handle everything else
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Check if Shift is pressed
            if event.modifiers() & Qt.ShiftModifier:
                # Shift+Enter: insert new line - use default behavior
                super().keyPressEvent(event)
            else:
                # Enter only: send message
                self.send_message.emit()
                return  # Event handled, don't call super()
        else:
            # For ALL other keys (including Ctrl+V, Ctrl+C, etc.), use default Qt behavior
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
        
        # Setup keyboard shortcuts for text size control
        # Temporarily disabled to test if shortcuts interfere with text input
        # self.setup_text_size_shortcuts()

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
        self.model_info.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.model_info.setContextMenuPolicy(Qt.DefaultContextMenu)
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
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.status_label.setContextMenuPolicy(Qt.DefaultContextMenu)
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

        # Text size slider container
        text_size_container = QWidget()
        text_size_layout = QHBoxLayout(text_size_container)
        text_size_layout.setContentsMargins(0, 5, 0, 5)
        text_size_layout.setSpacing(10)

        # Small size label
        small_label = QLabel("A")
        small_label.setFont(QFont(FONT_FAMILY, 10))
        small_label.setStyleSheet("color: #666;")
        small_label.setFixedWidth(15)
        text_size_layout.addWidget(small_label)

        # Text size slider
        self.text_size_slider = QSlider(Qt.Horizontal)
        self.text_size_slider.setMinimum(10)  # Min font size
        self.text_size_slider.setMaximum(24)  # Max font size
        self.text_size_slider.setValue(14)    # Default font size
        self.text_size_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.text_size_slider.setTickInterval(2)
        self.text_size_slider.valueChanged.connect(self.on_text_size_changed)
        self.text_size_slider.setToolTip("Text Size: 14px (Double-click to reset, Mouse wheel to adjust)")
        # Add double-click to reset functionality
        self.text_size_slider.mouseDoubleClickEvent = lambda event: self.reset_font_size()
        # Enable mouse wheel support
        self.text_size_slider.wheelEvent = self._slider_wheel_event
        self.text_size_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #bbb;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e0e0e0, stop:1 #f0f0f0);
                height: 8px;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a90e2, stop:1 #357abd);
                border: 1px solid #357abd;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::add-page:horizontal {
                background: #e0e0e0;
                border: 1px solid #bbb;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ffffff, stop:1 #e0e0e0);
                border: 2px solid #4a90e2;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ffffff, stop:1 #f0f0f0);
                border: 2px solid #357abd;
            }
            QSlider::handle:horizontal:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e0e0e0, stop:1 #d0d0d0);
                border: 2px solid #2968a3;
            }
        """)
        text_size_layout.addWidget(self.text_size_slider)

        # Large size label
        large_label = QLabel("A")
        large_label.setFont(QFont(FONT_FAMILY, 16, QFont.Bold))
        large_label.setStyleSheet("color: #333;")
        large_label.setFixedWidth(20)
        text_size_layout.addWidget(large_label)

        # Current size display
        self.font_size_display = QLabel("14")
        self.font_size_display.setAlignment(Qt.AlignCenter)
        self.font_size_display.setMinimumWidth(25)
        self.font_size_display.setFont(QFont(FONT_FAMILY, 10))
        self.font_size_display.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 2px 4px;
                color: #333;
            }
        """)
        text_size_layout.addWidget(self.font_size_display)

        layout.addWidget(text_size_container)

        # Clear chat button
        self.clear_chat_btn = QPushButton("🗑️ Clear Chat")
        self.clear_chat_btn.setMinimumHeight(35)
        self.clear_chat_btn.clicked.connect(self.clear_chat)
        layout.addWidget(self.clear_chat_btn)

        # Feedback button
        self.feedback_btn = QPushButton("📧 Send Feedback")
        self.feedback_btn.setMinimumHeight(35)
        self.feedback_btn.clicked.connect(self.show_feedback_dialog)
        self.feedback_btn.setToolTip("Share your thoughts, report bugs, or suggest features")
        layout.addWidget(self.feedback_btn)

        # Spacer
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

    def _setup_about_section(self, layout):
        """Setup about section"""
        about_label = QLabel("ℹ️ About")
        about_label.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        layout.addWidget(about_label)

        about_text = QLabel("Developed by Hussain Nazary\nGithub ID:@hussainnazary2")
        about_text.setWordWrap(True)
        about_text.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        about_text.setContextMenuPolicy(Qt.DefaultContextMenu)
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
        self.input_text.setContextMenuPolicy(Qt.DefaultContextMenu)  # Ensure context menu is enabled
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

    def _slider_wheel_event(self, event):
        """Handle mouse wheel events on the text size slider"""
        from PySide6.QtCore import QPoint
        
        # Get the wheel delta (positive for up, negative for down)
        delta = event.angleDelta().y()
        
        # Adjust slider value based on wheel direction
        current_value = self.text_size_slider.value()
        if delta > 0:  # Wheel up - increase font size
            new_value = min(current_value + 1, self.text_size_slider.maximum())
        else:  # Wheel down - decrease font size
            new_value = max(current_value - 1, self.text_size_slider.minimum())
        
        self.text_size_slider.setValue(new_value)
        event.accept()

    def on_text_size_changed(self, value):
        """Handle text size slider change"""
        self.current_font_size = value
        self.font_size_display.setText(str(value))
        
        # Add a subtle highlight animation to the display
        self.font_size_display.setStyleSheet("""
            QLabel {
                background-color: #e3f2fd;
                border: 1px solid #4a90e2;
                border-radius: 3px;
                padding: 2px 4px;
                color: #1976d2;
                font-weight: bold;
            }
        """)
        
        # Reset to normal style after a short delay
        QTimer.singleShot(200, self._reset_font_display_style)
        
        self._apply_font_size_to_all_bubbles()
        
        # Update tooltip to show current size
        self.text_size_slider.setToolTip(f"Text Size: {value}px (Double-click to reset, Mouse wheel to adjust)")

    def _reset_font_display_style(self):
        """Reset the font size display to normal style"""
        self.font_size_display.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 2px 4px;
                color: #333;
            }
        """)

    def setup_text_size_shortcuts(self):
        """Setup keyboard shortcuts for text size control"""
        from PySide6.QtGui import QShortcut, QKeySequence
        
        # Use more specific shortcuts that won't interfere with text editing
        # Ctrl+Plus to increase font size (use Ctrl+Shift+Plus to avoid conflicts)
        increase_shortcut = QShortcut(QKeySequence("Ctrl+Shift++"), self)
        increase_shortcut.activated.connect(self.increase_font_size)
        
        # Ctrl+Minus to decrease font size (use Ctrl+Shift+Minus to avoid conflicts)
        decrease_shortcut = QShortcut(QKeySequence("Ctrl+Shift+-"), self)
        decrease_shortcut.activated.connect(self.decrease_font_size)
        
        # Ctrl+0 to reset to default size (keep this one as it's less likely to conflict)
        reset_shortcut = QShortcut(QKeySequence("Ctrl+Shift+0"), self)
        reset_shortcut.activated.connect(self.reset_font_size)

    def reset_font_size(self):
        """Reset font size to default (14px)"""
        self.text_size_slider.setValue(14)

    def increase_font_size(self):
        """Increase chat bubble font size (legacy method for compatibility)"""
        current_value = self.text_size_slider.value()
        if current_value < self.text_size_slider.maximum():
            self.text_size_slider.setValue(current_value + 2)

    def decrease_font_size(self):
        """Decrease chat bubble font size (legacy method for compatibility)"""
        current_value = self.text_size_slider.value()
        if current_value > self.text_size_slider.minimum():
            self.text_size_slider.setValue(current_value - 2)

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