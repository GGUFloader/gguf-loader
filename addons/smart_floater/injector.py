"""
Text injection and clipboard operations for the Smart Floating Assistant addon.

This module handles inserting generated text at cursor positions and clipboard operations
with comprehensive error handling and user feedback.
"""

import time
import logging
from typing import Optional, Callable
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QWidget
from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtGui import QClipboard, QIcon
import pyautogui

from .performance_optimizer import PerformanceOptimizer


class NotificationSystem(QObject):
    """Handles user notifications and feedback."""
    
    # Signals for notification events
    notification_shown = Signal(str, bool)  # message, success
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._tray_icon = None
        self._setup_tray_icon()
    
    def _setup_tray_icon(self):
        """Setup system tray icon for notifications."""
        try:
            if QSystemTrayIcon.isSystemTrayAvailable():
                self._tray_icon = QSystemTrayIcon()
                # Set a default icon (you might want to use a custom icon)
                self._tray_icon.setToolTip("Smart Floating Assistant")
        except Exception as e:
            self.logger.warning(f"Could not setup system tray icon: {e}")
    
    def show_notification(self, title: str, message: str, success: bool = True, duration: int = 3000):
        """
        Show a system notification.
        
        Args:
            title: Notification title
            message: Notification message
            success: Whether this is a success (True) or error (False) notification
            duration: Duration in milliseconds
        """
        try:
            if self._tray_icon and QSystemTrayIcon.isSystemTrayAvailable():
                icon_type = QSystemTrayIcon.Information if success else QSystemTrayIcon.Warning
                self._tray_icon.showMessage(title, message, icon_type, duration)
            else:
                # Fallback to message box for important messages
                if not success:
                    self._show_message_box(title, message, duration)
            
            self.notification_shown.emit(message, success)
            self.logger.info(f"Notification shown: {title} - {message}")
            
        except Exception as e:
            self.logger.error(f"Failed to show notification: {e}")
    
    def _show_message_box(self, title: str, message: str, duration: int):
        """Show a message box as fallback notification."""
        try:
            msg_box = QMessageBox()
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setStandardButtons(QMessageBox.Ok)
            
            # Auto-close after duration
            QTimer.singleShot(duration, msg_box.close)
            msg_box.exec()
            
        except Exception as e:
            self.logger.error(f"Failed to show message box: {e}")
    
    def show_success(self, message: str, duration: int = 2000):
        """Show a success notification."""
        self.show_notification("Smart Floater", message, True, duration)
    
    def show_error(self, message: str, duration: int = 4000):
        """Show an error notification."""
        self.show_notification("Smart Floater", message, False, duration)
    
    def show_info(self, message: str, duration: int = 3000):
        """Show an info notification."""
        self.show_notification("Smart Floater", message, True, duration)


class TextInjector(QObject):
    """Handles text insertion and clipboard operations with comprehensive error handling."""
    
    # Signals for injection events
    injection_completed = Signal(bool, str)  # success, message
    clipboard_copied = Signal(str)  # text
    
    def __init__(self):
        """Initialize the text injector."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Configure pyautogui for safer operation
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1  # Small pause between operations
        
        # Initialize notification system
        self.notification_system = NotificationSystem()
        
        # Initialize performance optimizer
        self._performance_optimizer = PerformanceOptimizer()
        self._performance_optimizer.start_optimization()
        
        # Connect performance signals
        self._performance_optimizer.warning_issued.connect(self._handle_performance_warning)
        
        # Error tracking
        self._last_error = None
        self._injection_attempts = 0
        self.MAX_INJECTION_ATTEMPTS = 3
    
    def paste_at_cursor(self, text: str) -> bool:
        """
        Insert text at the current cursor position using pyautogui.write().
        
        Args:
            text: The text to insert at cursor position
            
        Returns:
            bool: True if insertion was successful, False otherwise
        """
        if not text:
            error_msg = "No text provided for insertion"
            self.logger.warning(error_msg)
            self.notification_system.show_error(error_msg)
            self.injection_completed.emit(False, error_msg)
            return False
        
        self._injection_attempts += 1
        
        try:
            # Performance optimization: validate and sanitize text
            validation_result = self._performance_optimizer.validate_text_for_processing(text)
            if not validation_result.is_valid:
                error_msg = validation_result.errors[0] if validation_result.errors else "Invalid text for insertion"
                self.logger.warning(error_msg)
                self.notification_system.show_error(error_msg)
                self.injection_completed.emit(False, error_msg)
                return False
            
            # Use sanitized text for injection
            sanitized_text = validation_result.sanitized_text
            
            # Show warnings if any
            if validation_result.warnings:
                for warning in validation_result.warnings:
                    self.logger.warning(f"Text injection warning: {warning}")
            
            # Legacy validation for backward compatibility
            if len(sanitized_text) > 10000:
                error_msg = "Text is too long for insertion (maximum 10,000 characters)"
                self.logger.warning(error_msg)
                self.notification_system.show_error(error_msg)
                self.injection_completed.emit(False, error_msg)
                return False
            
            # Check if pyautogui is working
            if not self._test_pyautogui():
                error_msg = "Text insertion system is not available"
                self.logger.error(error_msg)
                self.notification_system.show_error(error_msg)
                self.injection_completed.emit(False, error_msg)
                return False
            
            # Small delay to ensure the target application is ready
            time.sleep(0.2)
            
            # Use pyautogui to type the sanitized text at cursor position
            pyautogui.write(sanitized_text, interval=0.01)  # Small interval between characters
            
            success_msg = f"Text inserted successfully ({len(sanitized_text)} characters)"
            self.logger.info(success_msg)
            self.notification_system.show_success("Text inserted successfully")
            self.injection_completed.emit(True, success_msg)
            self._injection_attempts = 0  # Reset on success
            return True
            
        except pyautogui.FailSafeException:
            error_msg = "Text insertion cancelled (mouse moved to corner)"
            self.logger.warning(error_msg)
            self.notification_system.show_error(error_msg)
            self.injection_completed.emit(False, error_msg)
            return False
            
        except Exception as e:
            error_msg = self._get_user_friendly_injection_error(str(e))
            self.logger.error(f"Failed to paste text at cursor: {e}")
            self.notification_system.show_error(error_msg)
            self.injection_completed.emit(False, error_msg)
            return False
    
    def _test_pyautogui(self) -> bool:
        """Test if pyautogui is working properly."""
        try:
            # Test basic pyautogui functionality
            pyautogui.position()  # This should work if pyautogui is functional
            return True
        except Exception as e:
            self.logger.error(f"pyautogui test failed: {e}")
            return False
    
    def _get_user_friendly_injection_error(self, error_message: str) -> str:
        """
        Convert technical injection errors to user-friendly messages.
        
        Args:
            error_message: Technical error message
            
        Returns:
            str: User-friendly error message
        """
        error_lower = error_message.lower()
        
        if "permission" in error_lower or "access" in error_lower:
            return ("Permission denied for text insertion. Please ensure the application "
                   "has the necessary permissions to simulate keyboard input.")
        
        if "display" in error_lower or "screen" in error_lower:
            return ("Cannot access the display for text insertion. Please check your "
                   "display settings and try again.")
        
        if "failsafe" in error_lower:
            return ("Text insertion was cancelled for safety. This happens when the mouse "
                   "is moved to a screen corner during insertion.")
        
        if "timeout" in error_lower:
            return ("Text insertion timed out. The target application might not be responding.")
        
        return ("Failed to insert text. Please ensure the cursor is in a text field and try again.")
    
    def copy_to_clipboard(self, text: str) -> bool:
        """
        Copy text to system clipboard with comprehensive error handling.
        
        Args:
            text: The text to copy to clipboard
            
        Returns:
            bool: True if copy was successful, False otherwise
        """
        if not text:
            error_msg = "No text provided for clipboard copy"
            self.logger.warning(error_msg)
            self.notification_system.show_error(error_msg)
            return False
            
        try:
            app = QApplication.instance()
            if not app:
                error_msg = "Application not available for clipboard access"
                self.logger.error(error_msg)
                self.notification_system.show_error("Failed to access clipboard")
                return False
            
            clipboard = app.clipboard()
            if not clipboard:
                error_msg = "Clipboard not available"
                self.logger.error(error_msg)
                self.notification_system.show_error("Clipboard is not available")
                return False
            
            # Attempt to copy to clipboard
            clipboard.setText(text, QClipboard.Clipboard)
            
            # Verify the copy was successful
            if clipboard.text() == text:
                success_msg = f"Text copied to clipboard ({len(text)} characters)"
                self.logger.info(success_msg)
                self.notification_system.show_success("Text copied to clipboard")
                self.clipboard_copied.emit(text)
                return True
            else:
                error_msg = "Clipboard copy verification failed"
                self.logger.error(error_msg)
                self.notification_system.show_error("Failed to copy text to clipboard")
                return False
                
        except Exception as e:
            error_msg = f"Failed to copy text to clipboard: {str(e)}"
            self.logger.error(error_msg)
            self.notification_system.show_error("Failed to copy text to clipboard")
            return False
    
    def paste_with_retry(self, text: str, max_attempts: int = 3) -> bool:
        """
        Attempt to paste text with retry functionality.
        
        Args:
            text: Text to paste
            max_attempts: Maximum number of attempts
            
        Returns:
            bool: True if successful, False otherwise
        """
        for attempt in range(max_attempts):
            if attempt > 0:
                self.logger.info(f"Retrying text insertion (attempt {attempt + 1}/{max_attempts})")
                time.sleep(1.0)  # Wait before retry
            
            if self.paste_at_cursor(text):
                return True
        
        # All attempts failed
        error_msg = f"Failed to insert text after {max_attempts} attempts"
        self.logger.error(error_msg)
        self.notification_system.show_error(error_msg)
        return False
    
    def paste_with_fallback(self, text: str) -> bool:
        """
        Attempt to paste text at cursor, fallback to clipboard if it fails.
        
        Args:
            text: The text to paste
            
        Returns:
            bool: True if either paste or clipboard copy succeeded
        """
        # First try to paste at cursor with retry
        if self.paste_with_retry(text, self.MAX_INJECTION_ATTEMPTS):
            return True
            
        # If paste fails, fallback to clipboard
        self.logger.info("Text insertion failed, falling back to clipboard")
        self.notification_system.show_info("Text insertion failed, copying to clipboard instead")
        
        if self.copy_to_clipboard(text):
            return True
        
        # Both methods failed
        error_msg = "Both text insertion and clipboard copy failed"
        self.logger.error(error_msg)
        self.notification_system.show_error(error_msg)
        return False
    
    def get_injection_status(self) -> dict:
        """
        Get current injection status and statistics.
        
        Returns:
            dict: Status information
        """
        return {
            'last_error': self._last_error,
            'injection_attempts': self._injection_attempts,
            'max_attempts': self.MAX_INJECTION_ATTEMPTS,
            'pyautogui_available': self._test_pyautogui()
        }
    
    def reset_injection_state(self):
        """Reset injection state and error tracking."""
        self._last_error = None
        self._injection_attempts = 0
        self.logger.info("Injection state reset")
    
    def _handle_performance_warning(self, warning_message: str):
        """Handle performance warnings from the optimizer."""
        self.logger.warning(f"Performance warning in text injector: {warning_message}")
    
    def cleanup(self):
        """Cleanup resources."""
        self.logger.info("Cleaning up TextInjector")
        self.reset_injection_state()
        
        # Cleanup performance optimizer
        if hasattr(self, '_performance_optimizer'):
            self._performance_optimizer.cleanup()
            self._performance_optimizer = None