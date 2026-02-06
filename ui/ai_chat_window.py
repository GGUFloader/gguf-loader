"""
Main application window - Master class that combines all mixins
"""
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QApplication
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon

from config import WINDOW_TITLE, WINDOW_SIZE, MIN_WINDOW_SIZE, MAX_TOKENS
from models.model_loader import ModelLoader
from models.chat_generator import ChatGenerator
from resource_manager import find_icon
from ui.apply_style import ThemeMixin

# Import all mixin classes
from mixins.ui_setup_mixin import UISetupMixin
from mixins.model_handler_mixin import ModelHandlerMixin
from mixins.chat_handler_mixin import ChatHandlerMixin
from mixins.event_handler_mixin import EventHandlerMixin
from mixins.utils_mixin import UtilsMixin
from mixins.agent_mode_mixin import AgentModeMixin


class AIChat(QMainWindow, ThemeMixin, UISetupMixin, ModelHandlerMixin,
             ChatHandlerMixin, EventHandlerMixin, UtilsMixin, AgentModeMixin):
    """Main AI Chat Application Window - English Only"""

    # Define signals
    model_loaded = Signal(object)
    generation_finished = Signal()
    generation_error = Signal(str)

    def __init__(self):
        super().__init__()

        # Set window icon (inherit from application if available)
        app_icon = QApplication.instance().windowIcon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        else:
            # Fallback to loading icon directly
            icon_path = find_icon("icon.ico")
            if os.path.exists(icon_path):
                window_icon = QIcon(icon_path)
                if not window_icon.isNull():
                    self.setWindowIcon(window_icon)

        # Initialize instance variables
        self.model = None
        self.model_loader = None
        self.chat_generator = None
        self.conversation_history = []
        self.is_dark_mode = False
        self.chat_bubbles = []
        self.current_ai_bubble = None
        self.current_ai_text = ""
        self.current_font_size = 14  # Default font size for chat bubbles
        
        # Initialize agent mode variables
        self.agent_mode_enabled = False
        self.agent_session_id = None
        self.agent_workspace_path = None

        # Setup UI and apply styles
        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        """Setup the main user interface"""
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(*MIN_WINDOW_SIZE)
        self.resize(*WINDOW_SIZE)

        # Call mixin setup methods
        self.setup_main_layout()
        self.setup_sidebar_layout()
        self.setup_chat_area_layout()