#!/usr/bin/env python3
"""
Floating Chat Button Addon - Cross-platform floating chat button like Facebook Messenger

Features:
- Draggable floating button that stays on top
- Cross-platform compatibility (Windows, Linux, macOS)
- Opens chat window connected to GGUF Loader
- Remembers position between sessions
- Clean, modern UI design
"""

import os
import json
import logging
from typing import Optional, Any
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QLabel, QFrame, QScrollArea, QApplication, QSizePolicy
)
from PySide6.QtCore import (
    QObject, Signal, QTimer, Qt, QPoint, QPropertyAnimation, 
    QEasingCurve, QRect, QSettings
)
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QPixmap, QIcon,
    QLinearGradient, QRadialGradient, QPainterPath
)

from .floating_button import FloatingChatButton
from .chat_window import FloatingChatWindow


class FloatingChatAddon(QObject):
    """
    Main addon class for the floating chat button.
    
    Provides a Facebook Messenger-like floating button that:
    - Stays on top of all windows
    - Can be dragged anywhere on screen
    - Opens a chat window when clicked
    - Connects to the GGUF Loader for AI chat
    """
    
    # Signals
    addon_started = Signal()
    addon_stopped = Signal()
    chat_message_sent = Signal(str)  # Emitted when user sends a message
    
    def __init__(self, gguf_app_instance: Any):
        """
        Initialize the floating chat addon.
        
        Args:
            gguf_app_instance: Reference to the main GGUF Loader application
        """
        super().__init__()
        
        # Store reference to main app
        self.gguf_app = gguf_app_instance
        
        # Setup logging
        self._logger = logging.getLogger(__name__)
        
        # Initialize components
        self._floating_button: Optional[FloatingChatButton] = None
        self._chat_window: Optional[FloatingChatWindow] = None
        self._is_running = False
        
        # Settings for persistence
        self._settings = QSettings("GGUFLoader", "FloatingChat")
        
        # Connect to main app signals if available
        self._connect_to_main_app()
    
    def _connect_to_main_app(self):
        """Connect to main application signals for model status updates."""
        try:
            if hasattr(self.gguf_app, 'model_loaded'):
                self.gguf_app.model_loaded.connect(self._on_model_loaded)
            if hasattr(self.gguf_app, 'generation_finished'):
                self.gguf_app.generation_finished.connect(self._on_generation_finished)
            if hasattr(self.gguf_app, 'generation_error'):
                self.gguf_app.generation_error.connect(self._on_generation_error)
        except Exception as e:
            self._logger.debug(f"Could not connect to main app signals: {e}")
    
    def start(self) -> bool:
        """
        Start the floating chat addon.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self._is_running:
            self._logger.warning("Addon is already running")
            return True
        
        try:
            self._logger.info("Starting Floating Chat addon")
            
            # Create floating button
            self._floating_button = FloatingChatButton()
            self._floating_button.clicked.connect(self._on_button_clicked)
            
            # Load saved position
            self._load_button_position()
            
            # Show the button
            self._floating_button.show()
            
            self._is_running = True
            self.addon_started.emit()
            self._logger.info("Floating Chat addon started successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to start Floating Chat addon: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the floating chat addon and cleanup resources.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self._is_running:
            self._logger.warning("Addon is not running")
            return True
        
        try:
            self._logger.info("Stopping Floating Chat addon")
            
            # Save button position
            self._save_button_position()
            
            # Close chat window if open
            if self._chat_window:
                self._chat_window.close()
                self._chat_window = None
            
            # Close floating button
            if self._floating_button:
                self._floating_button.close()
                self._floating_button = None
            
            self._is_running = False
            self.addon_stopped.emit()
            self._logger.info("Floating Chat addon stopped successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to stop Floating Chat addon: {e}")
            return False
    
    def _on_button_clicked(self):
        """Handle floating button click - show/hide chat window."""
        try:
            if self._chat_window and self._chat_window.isVisible():
                # Chat window is open, close it
                self._chat_window.hide()
            else:
                # Chat window is closed, open it
                self._show_chat_window()
        except Exception as e:
            self._logger.error(f"Error handling button click: {e}")
    
    def _show_chat_window(self):
        """Show the floating chat window."""
        try:
            if not self._chat_window:
                # Create chat window
                self._chat_window = FloatingChatWindow(self.gguf_app)
                self._chat_window.message_sent.connect(self._on_message_sent)
                self._chat_window.window_closed.connect(self._on_chat_window_closed)
            
            # Position window near the button
            self._position_chat_window()
            
            # Show window
            self._chat_window.show()
            self._chat_window.raise_()
            self._chat_window.activateWindow()
            
        except Exception as e:
            self._logger.error(f"Error showing chat window: {e}")
    
    def _position_chat_window(self):
        """Position chat window near the floating button."""
        if not self._floating_button or not self._chat_window:
            return
        
        try:
            # Get button position and size
            button_pos = self._floating_button.pos()
            button_size = self._floating_button.size()
            
            # Get screen geometry
            screen = QApplication.primaryScreen()
            screen_rect = screen.geometry()
            
            # Calculate window position
            window_size = self._chat_window.size()
            
            # Try to position to the right of button
            x = button_pos.x() + button_size.width() + 10
            y = button_pos.y()
            
            # Ensure window stays on screen
            if x + window_size.width() > screen_rect.right():
                # Position to the left of button instead
                x = button_pos.x() - window_size.width() - 10
            
            if y + window_size.height() > screen_rect.bottom():
                # Move up to fit on screen
                y = screen_rect.bottom() - window_size.height() - 10
            
            # Ensure minimum position
            x = max(10, x)
            y = max(10, y)
            
            self._chat_window.move(x, y)
            
        except Exception as e:
            self._logger.error(f"Error positioning chat window: {e}")
    
    def _on_message_sent(self, message: str):
        """Handle message sent from chat window."""
        try:
            self._logger.info(f"Message sent from floating chat: {message[:50]}...")
            self.chat_message_sent.emit(message)
        except Exception as e:
            self._logger.error(f"Error handling sent message: {e}")
    
    def _on_chat_window_closed(self):
        """Handle chat window being closed."""
        try:
            self._logger.debug("Chat window closed")
        except Exception as e:
            self._logger.error(f"Error handling chat window close: {e}")
    
    def _load_button_position(self):
        """Load saved button position from settings."""
        if not self._floating_button:
            return
        
        try:
            # Get saved position
            pos = self._settings.value("button_position", QPoint(100, 100))
            
            # Ensure position is on screen
            screen = QApplication.primaryScreen()
            screen_rect = screen.geometry()
            
            x = max(0, min(pos.x(), screen_rect.width() - self._floating_button.width()))
            y = max(0, min(pos.y(), screen_rect.height() - self._floating_button.height()))
            
            self._floating_button.move(x, y)
            
        except Exception as e:
            self._logger.debug(f"Could not load button position: {e}")
            # Use default position
            self._floating_button.move(100, 100)
    
    def _save_button_position(self):
        """Save current button position to settings."""
        if not self._floating_button:
            return
        
        try:
            pos = self._floating_button.pos()
            self._settings.setValue("button_position", pos)
        except Exception as e:
            self._logger.debug(f"Could not save button position: {e}")
    
    def _on_model_loaded(self, model):
        """Handle model loaded event from main app."""
        try:
            self._logger.info("Model loaded - floating chat is ready")
            if self._chat_window:
                self._chat_window.set_model_status(True)
        except Exception as e:
            self._logger.error(f"Error handling model loaded: {e}")
    
    def _on_generation_finished(self):
        """Handle generation finished event from main app."""
        try:
            if self._chat_window:
                self._chat_window.on_generation_finished()
        except Exception as e:
            self._logger.error(f"Error handling generation finished: {e}")
    
    def _on_generation_error(self, error_message: str):
        """Handle generation error event from main app."""
        try:
            if self._chat_window:
                self._chat_window.on_generation_error(error_message)
        except Exception as e:
            self._logger.error(f"Error handling generation error: {e}")
    
    def is_running(self) -> bool:
        """
        Check if the addon is currently running.
        
        Returns:
            bool: True if addon is running, False otherwise
        """
        return self._is_running
    
    def get_button_position(self) -> QPoint:
        """
        Get current button position.
        
        Returns:
            QPoint: Current button position
        """
        if self._floating_button:
            return self._floating_button.pos()
        return QPoint(0, 0)
    
    def set_button_position(self, position: QPoint):
        """
        Set button position.
        
        Args:
            position: New button position
        """
        if self._floating_button:
            self._floating_button.move(position)
    
    def is_chat_window_visible(self) -> bool:
        """
        Check if chat window is currently visible.
        
        Returns:
            bool: True if chat window is visible, False otherwise
        """
        return self._chat_window and self._chat_window.isVisible()


# Addon registration function for GGUF Loader addon system
def register(parent=None):
    """
    Register function called by the GGUF Loader addon system.
    
    Args:
        parent: Parent widget (might be dialog or main window)
        
    Returns:
        QWidget: Status widget for the addon sidebar, or None for background addons
    """
    try:
        # Find the main GGUF Loader application
        gguf_app = None
        
        # First, try to use parent directly if it's the main app
        if parent and hasattr(parent, 'model') and hasattr(parent, 'model_loaded'):
            gguf_app = parent
        else:
            # If parent is a dialog or other widget, try to find the main window
            current_widget = parent
            while current_widget is not None:
                # Check if this widget is the main AIChat window
                if hasattr(current_widget, 'model') and hasattr(current_widget, 'model_loaded'):
                    gguf_app = current_widget
                    break
                
                # Try parent widget
                current_widget = current_widget.parent() if hasattr(current_widget, 'parent') else None
            
            # If still not found, try to get it from QApplication
            if gguf_app is None:
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    # Look through all top-level widgets
                    for widget in app.topLevelWidgets():
                        if hasattr(widget, 'model') and hasattr(widget, 'model_loaded'):
                            gguf_app = widget
                            break
        
        if gguf_app is None:
            logging.error("Could not find main GGUF Loader application instance")
            return None
        
        logging.info(f"Found GGUF app: {type(gguf_app).__name__}")
        
        # Stop existing addon if running
        if hasattr(gguf_app, '_floating_chat_addon') and gguf_app._floating_chat_addon:
            gguf_app._floating_chat_addon.stop()
        
        # Create and start the addon
        addon = FloatingChatAddon(gguf_app)
        success = addon.start()
        
        if success:
            # Store addon reference in gguf_app for lifecycle management
            gguf_app._floating_chat_addon = addon
            
            # Create status widget for addon sidebar
            from .status_widget import FloatingChatStatusWidget
            status_widget = FloatingChatStatusWidget(addon)
            
            return status_widget
        else:
            logging.error("Failed to start Floating Chat addon")
            return None
        
    except Exception as e:
        logging.error(f"Failed to register Floating Chat addon: {e}")
        return None