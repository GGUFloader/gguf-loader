"""
Floating UI components for the Smart Floating Assistant addon.

This module handles the floating button and popup window interface.
"""

import sys
import time
import threading
from datetime import datetime
from dataclasses import dataclass
from typing import Tuple, Optional, Callable
from PySide6.QtWidgets import (QWidget, QDialog, QApplication, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QProgressBar, QFrame)
from PySide6.QtCore import QTimer, QThread, Signal, QObject, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QClipboard, QCursor, QPainter, QColor, QPen, QMovie
import pyautogui

from .privacy_security import PrivacySecurityManager
from .performance_optimizer import PerformanceOptimizer, TextValidationResult

# Platform-specific imports for global text selection detection
WIN32_AVAILABLE = False
MACOS_AVAILABLE = False
LINUX_X11_AVAILABLE = False

if sys.platform == "win32":
    try:
        import win32gui
        import win32con
        import win32clipboard
        import win32api
        WIN32_AVAILABLE = True
    except ImportError:
        print("Warning: pywin32 not available. Some Windows-specific features may not work.")
        print("Install with: pip install ggufloader[windows]")
elif sys.platform == "darwin":
    try:
        # macOS specific imports would go here
        # import Cocoa, Quartz frameworks when implemented
        MACOS_AVAILABLE = True
    except ImportError:
        print("Warning: macOS frameworks not available. Some macOS-specific features may not work.")
        print("Install with: pip install ggufloader[macos]")
else:
    try:
        # Linux specific imports would go here
        # import Xlib when implemented
        LINUX_X11_AVAILABLE = True
    except ImportError:
        print("Warning: X11 libraries not available. Some Linux-specific features may not work.")
        print("Install with: pip install ggufloader[linux]")


@dataclass
class TextSelection:
    """Data model for captured text selection."""
    content: str
    cursor_position: Tuple[int, int]
    timestamp: datetime
    source_app: str


class TextSelectionMonitor(QObject):
    """Monitors global text selection across all applications."""
    
    # Signals
    text_selected = Signal(TextSelection)
    text_deselected = Signal()
    
    def __init__(self):
        super().__init__()
        self.is_monitoring = False
        self.last_clipboard_content = ""
        self.last_selection = None
        self.clipboard_timer = QTimer()
        self.clipboard_timer.timeout.connect(self._check_clipboard)
        self.selection_check_timer = QTimer()
        self.selection_check_timer.timeout.connect(self._check_selection_status)
        
    def start_monitoring(self):
        """Start monitoring for text selection."""
        if self.is_monitoring:
            return
            
        self.is_monitoring = True
        
        # Start clipboard monitoring (fallback method)
        self.clipboard_timer.start(100)  # Check every 100ms
        
        # Start selection status checking
        self.selection_check_timer.start(200)  # Check every 200ms
        
        # Initialize clipboard content
        self._update_clipboard_baseline()
        
    def stop_monitoring(self):
        """Stop monitoring for text selection."""
        self.is_monitoring = False
        self.clipboard_timer.stop()
        self.selection_check_timer.stop()
        
    def _update_clipboard_baseline(self):
        """Update the baseline clipboard content."""
        try:
            clipboard = QApplication.clipboard()
            self.last_clipboard_content = clipboard.text()
        except Exception:
            self.last_clipboard_content = ""
            
    def _check_clipboard(self):
        """Check for clipboard changes that might indicate text selection."""
        if not self.is_monitoring:
            return
            
        try:
            clipboard = QApplication.clipboard()
            current_content = clipboard.text()
            
            # If clipboard content changed and it's not empty
            if (current_content != self.last_clipboard_content and 
                current_content.strip() and 
                len(current_content.strip()) > 0):
                
                cursor_pos = self._get_cursor_position()
                source_app = self._get_active_window_title()
                
                selection = TextSelection(
                    content=current_content.strip(),
                    cursor_position=cursor_pos,
                    timestamp=datetime.now(),
                    source_app=source_app
                )
                
                self.last_selection = selection
                self.text_selected.emit(selection)
                
            self.last_clipboard_content = current_content
            
        except Exception as e:
            # Silently handle clipboard access errors
            pass
            
    def _check_selection_status(self):
        """Check if text is still selected by monitoring selection state."""
        if not self.is_monitoring or not self.last_selection:
            return
            
        # Simple heuristic: if clipboard hasn't changed for a while,
        # assume selection might be gone
        # This is a fallback - more sophisticated detection would use system hooks
        
        # For now, we'll rely on clipboard monitoring
        # In a full implementation, this would use platform-specific APIs
        pass
        
    def _get_cursor_position(self) -> Tuple[int, int]:
        """Get current cursor position."""
        try:
            cursor = QCursor()
            pos = cursor.pos()
            return (pos.x(), pos.y())
        except Exception:
            return (0, 0)
            
    def _get_active_window_title(self) -> str:
        """Get the title of the currently active window."""
        try:
            if sys.platform == "win32" and WIN32_AVAILABLE:
                hwnd = win32gui.GetForegroundWindow()
                return win32gui.GetWindowText(hwnd)
            else:
                # Fallback for other platforms or when platform libraries aren't available
                return "Unknown Application"
        except Exception:
            return "Unknown Application"


class WindowsTextSelectionMonitor(TextSelectionMonitor):
    """Windows-specific text selection monitor using system hooks."""
    
    def __init__(self):
        super().__init__()
        self.hook_thread = None
        self.selection_hook_active = False
        
    def start_monitoring(self):
        """Start Windows-specific monitoring."""
        super().start_monitoring()
        
        if sys.platform == "win32" and WIN32_AVAILABLE:
            self._start_windows_hooks()
            
    def stop_monitoring(self):
        """Stop Windows-specific monitoring."""
        super().stop_monitoring()
        
        if sys.platform == "win32" and WIN32_AVAILABLE:
            self._stop_windows_hooks()
            
    def _start_windows_hooks(self):
        """Start Windows system hooks for text selection detection."""
        try:
            # This would implement Windows-specific hooks
            # For now, we'll rely on clipboard monitoring as the primary method
            # A full implementation would use SetWindowsHookEx with WH_KEYBOARD_LL
            # and WH_MOUSE_LL to detect selection events
            pass
        except Exception:
            # Fall back to clipboard monitoring only
            pass
            
    def _stop_windows_hooks(self):
        """Stop Windows system hooks."""
        try:
            # Cleanup Windows hooks
            pass
        except Exception:
            pass


class CrossPlatformTextMonitor(QObject):
    """Cross-platform text selection monitor that chooses the best method per OS."""
    
    # Signals
    text_selected = Signal(TextSelection)
    text_deselected = Signal()
    
    def __init__(self):
        super().__init__()
        
        # Choose the appropriate monitor based on platform and availability
        if sys.platform == "win32" and WIN32_AVAILABLE:
            self.monitor = WindowsTextSelectionMonitor()
        else:
            # Use base monitor for other platforms or when platform libraries aren't available
            self.monitor = TextSelectionMonitor()
            
        # Connect signals
        self.monitor.text_selected.connect(self.text_selected.emit)
        self.monitor.text_deselected.connect(self.text_deselected.emit)
        
    def start_monitoring(self):
        """Start cross-platform text selection monitoring."""
        self.monitor.start_monitoring()
        
    def stop_monitoring(self):
        """Stop cross-platform text selection monitoring."""
        self.monitor.stop_monitoring()
        
    def get_current_selection(self) -> Optional[TextSelection]:
        """Get the current text selection if any."""
        return getattr(self.monitor, 'last_selection', None)


class FloatingButton(QWidget):
    """Transparent floating button that appears near selected text."""
    
    # Signal emitted when button is clicked
    clicked = Signal()
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._setup_timers()
        self._setup_animations()
        
    def _setup_ui(self):
        """Set up the floating button UI."""
        # Make window frameless and always on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        # Set transparent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set fixed size for the button
        self.setFixedSize(40, 40)
        
        # Create the button
        self.button = QPushButton("✨", self)
        self.button.setFixedSize(40, 40)
        self.button.setStyleSheet("""
            QPushButton {
                background-color: rgba(70, 130, 180, 200);
                border: 2px solid rgba(255, 255, 255, 150);
                border-radius: 20px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(70, 130, 180, 255);
                border: 2px solid rgba(255, 255, 255, 200);
            }
            QPushButton:pressed {
                background-color: rgba(50, 110, 160, 255);
            }
        """)
        
        # Connect button click to signal
        self.button.clicked.connect(self.clicked.emit)
        
        # Initially hide the widget
        self.hide()
        
    def _setup_timers(self):
        """Set up timers for auto-hide functionality."""
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._fade_out)
        
    def _setup_animations(self):
        """Set up fade-in and fade-out animations."""
        # Fade-in animation
        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in_animation.setDuration(300)  # 300ms fade-in
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Fade-out animation
        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out_animation.setDuration(300)  # 300ms fade-out
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_out_animation.finished.connect(self.hide)
        
    def show_at_cursor(self, position: Tuple[int, int]):
        """Show the floating button at the specified cursor position."""
        # Calculate position within 50 pixels of cursor
        x, y = position
        
        # Offset the button to be near but not directly on the cursor
        # Place it slightly to the right and below the cursor
        offset_x = 20
        offset_y = 20
        
        # Ensure the button stays within screen bounds
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        
        # Adjust position to keep button within 50 pixels but on screen
        button_x = min(x + offset_x, screen_geometry.width() - self.width())
        button_y = min(y + offset_y, screen_geometry.height() - self.height())
        
        # Ensure minimum distance from cursor (within 50 pixels requirement)
        distance_x = abs(button_x - x)
        distance_y = abs(button_y - y)
        
        if distance_x > 50:
            button_x = x + (50 if button_x > x else -50)
        if distance_y > 50:
            button_y = y + (50 if button_y > y else -50)
            
        # Final bounds check
        button_x = max(0, min(button_x, screen_geometry.width() - self.width()))
        button_y = max(0, min(button_y, screen_geometry.height() - self.height()))
        
        # Move to calculated position
        self.move(button_x, button_y)
        
        # Stop any running animations
        self.fade_in_animation.stop()
        self.fade_out_animation.stop()
        self.hide_timer.stop()
        
        # Show with fade-in animation
        self.setWindowOpacity(0.0)
        self.show()
        self.fade_in_animation.start()
        
    def hide_with_delay(self, delay_seconds: int = 5):
        """Hide the button after the specified delay."""
        # Stop any existing timer
        self.hide_timer.stop()
        
        # Start new timer with specified delay
        self.hide_timer.start(delay_seconds * 1000)  # Convert to milliseconds
        
    def _fade_out(self):
        """Start fade-out animation."""
        if self.isVisible():
            self.fade_out_animation.start()
            
    def cancel_hide_delay(self):
        """Cancel the scheduled hide delay."""
        self.hide_timer.stop()
        
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        # Cancel hide delay when user interacts with button
        self.cancel_hide_delay()
        super().mousePressEvent(event)
        
    def enterEvent(self, event):
        """Handle mouse enter events."""
        # Cancel hide delay when mouse enters button area
        self.cancel_hide_delay()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Handle mouse leave events."""
        # Restart hide delay when mouse leaves button area
        self.hide_with_delay(3)  # Shorter delay when mouse leaves
        super().leaveEvent(event)


class TextProcessorPopup(QDialog):
    """Popup window for displaying selected text and processing options."""
    
    # Signals
    summarize_requested = Signal(str)  # Emitted when Summarize button is clicked
    comment_requested = Signal(str)    # Emitted when Comment button is clicked
    paste_comment_requested = Signal(str)  # Emitted when Paste Comment button is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_text = ""
        self.current_result = None
        self.current_result_type = None
        self.is_processing = False
        
        # Initialize performance optimizer
        self._performance_optimizer = PerformanceOptimizer()
        self._performance_optimizer.start_optimization()
        
        # Connect performance signals
        self._performance_optimizer.warning_issued.connect(self.show_warning)
        self._performance_optimizer.optimization_applied.connect(self.show_optimization_info)
        
        self._setup_ui()
        self._setup_window_properties()
        
        # Track this widget for memory management
        self._performance_optimizer.memory_manager.track_object(self, self._cleanup_resources)
        
    def _setup_window_properties(self):
        """Set up window properties for always-on-top modal behavior."""
        # Set window flags for always-on-top modal dialog
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        
        # Set modal behavior
        self.setModal(True)
        
        # Set window size
        self.setFixedSize(400, 300)
        
        # Set window title (though it won't be visible due to frameless)
        self.setWindowTitle("Text Processor")
        
        # Enable click-outside-to-close by installing event filter
        self.installEventFilter(self)
        
    def _setup_ui(self):
        """Set up the popup window UI components."""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # Add title label
        title_label = QLabel("Selected Text")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #333;
                margin-bottom: 5px;
            }
        """)
        main_layout.addWidget(title_label)
        
        # Create scrollable text area for selected text
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlaceholderText("Selected text will appear here...")
        # Disable text editing completely
        self.text_area.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | 
                                               Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.text_area.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.text_area.setStyleSheet("""
            QTextEdit {
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
                background-color: #f9f9f9;
                selection-background-color: #4a90e2;
            }
            QTextEdit:focus {
                border-color: #4a90e2;
            }
        """)
        main_layout.addWidget(self.text_area)
        
        # Create loading indicator (initially hidden)
        self.loading_frame = QFrame()
        self.loading_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.loading_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f8ff;
                border: 2px solid #4a90e2;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        loading_layout = QHBoxLayout(self.loading_frame)
        loading_layout.setContentsMargins(10, 10, 10, 10)
        
        # Loading progress bar
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 0)  # Indeterminate progress
        self.loading_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ddd;
                border-radius: 5px;
                text-align: center;
                font-size: 11px;
                color: #333;
            }
            QProgressBar::chunk {
                background-color: #4a90e2;
                border-radius: 3px;
            }
        """)
        loading_layout.addWidget(self.loading_progress)
        
        # Loading label
        self.loading_label = QLabel("Processing...")
        self.loading_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #4a90e2;
                font-weight: bold;
                margin-left: 10px;
            }
        """)
        loading_layout.addWidget(self.loading_label)
        
        main_layout.addWidget(self.loading_frame)
        self.loading_frame.hide()  # Initially hidden
        
        # Create result display area (initially hidden)
        self.result_frame = QFrame()
        self.result_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.result_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px solid #28a745;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        result_layout = QVBoxLayout(self.result_frame)
        result_layout.setContentsMargins(10, 10, 10, 10)
        result_layout.setSpacing(8)
        
        # Result title
        self.result_title = QLabel("Result")
        self.result_title.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #28a745;
                margin-bottom: 5px;
            }
        """)
        result_layout.addWidget(self.result_title)
        
        # Result text area
        self.result_text_area = QTextEdit()
        self.result_text_area.setReadOnly(True)
        self.result_text_area.setMaximumHeight(100)
        self.result_text_area.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | 
                                                      Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.result_text_area.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.result_text_area.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                font-size: 11px;
                background-color: white;
                selection-background-color: #4a90e2;
            }
        """)
        result_layout.addWidget(self.result_text_area)
        
        main_layout.addWidget(self.result_frame)
        self.result_frame.hide()  # Initially hidden
        
        # Create button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Create Summarize button
        self.summarize_button = QPushButton("Summarize")
        self.summarize_button.setEnabled(False)  # Initially disabled
        self.summarize_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2968a3;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        self.summarize_button.clicked.connect(self._on_summarize_clicked)
        button_layout.addWidget(self.summarize_button)
        
        # Create Comment button
        self.comment_button = QPushButton("Comment")
        self.comment_button.setEnabled(False)  # Initially disabled
        self.comment_button.setStyleSheet("""
            QPushButton {
                background-color: #5cb85c;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #449d44;
            }
            QPushButton:pressed {
                background-color: #398439;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        self.comment_button.clicked.connect(self._on_comment_clicked)
        button_layout.addWidget(self.comment_button)
        
        # Create Paste Comment button (initially hidden)
        self.paste_button = QPushButton("Paste Comment")
        self.paste_button.setStyleSheet("""
            QPushButton {
                background-color: #ff8c00;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e67e00;
            }
            QPushButton:pressed {
                background-color: #cc7000;
            }
        """)
        self.paste_button.clicked.connect(self._on_paste_comment_clicked)
        button_layout.addWidget(self.paste_button)
        self.paste_button.hide()  # Initially hidden
        
        # Create Retry button (initially hidden)
        self.retry_button = QPushButton("Retry")
        self.retry_button.setStyleSheet("""
            QPushButton {
                background-color: #f0ad4e;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ec971f;
            }
            QPushButton:pressed {
                background-color: #d58512;
            }
        """)
        self.retry_button.clicked.connect(self._on_retry_clicked)
        button_layout.addWidget(self.retry_button)
        self.retry_button.hide()  # Initially hidden
        
        # Add close button
        close_button = QPushButton("Close")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #d9534f;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c9302c;
            }
            QPushButton:pressed {
                background-color: #ac2925;
            }
        """)
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
        
        # Set overall dialog styling
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border: 2px solid #ddd;
                border-radius: 10px;
            }
        """)
        
    def set_selected_text(self, text: str):
        """Set the selected text to display in the popup."""
        # Store the original text, but strip for display and button enabling
        original_text = text if text else ""
        stripped_text = original_text.strip()
        
        # Validate and sanitize text using performance optimizer
        if hasattr(self, '_performance_optimizer'):
            try:
                validation_result = self._performance_optimizer.validate_text_for_processing(stripped_text)
                
                if not validation_result.is_valid:
                    # Show validation errors
                    error_msg = validation_result.errors[0] if validation_result.errors else "Invalid text"
                    self.display_error(error_msg)
                    return
                
                # Use sanitized text
                self.selected_text = validation_result.sanitized_text
                
                # Show warnings if any
                if validation_result.warnings:
                    for warning in validation_result.warnings:
                        self.show_warning(warning)
                        
            except Exception as e:
                # Fallback to original text if validation fails
                self.selected_text = stripped_text
                self.show_warning(f"Text validation warning: {str(e)}")
        else:
            # Fallback when performance optimizer not available
            if len(stripped_text) > 10000:
                self.display_error("Text is too long (maximum 10,000 characters)")
                return
            self.selected_text = stripped_text
        
        self.text_area.setPlainText(self.selected_text)
        
        # Clear any previous results when new text is set
        self.clear_result()
        self.hide_loading()
        self.hide_error()
        
        # Enable/disable buttons based on whether we have text and not processing
        has_text = bool(self.selected_text)
        if not self.is_processing:
            self.summarize_button.setEnabled(has_text)
            self.comment_button.setEnabled(has_text)
        
        # Scroll to top of text area
        cursor = self.text_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.text_area.setTextCursor(cursor)
        
    def _on_summarize_clicked(self):
        """Handle Summarize button click."""
        if self.selected_text and not self.is_processing:
            self.show_loading("Generating summary...")
            self.summarize_requested.emit(self.selected_text)
            
    def _on_comment_clicked(self):
        """Handle Comment button click."""
        if self.selected_text and not self.is_processing:
            self.show_loading("Generating comment...")
            self.comment_requested.emit(self.selected_text)
            
    def _on_paste_comment_clicked(self):
        """Handle Paste Comment button click."""
        if self.current_result and self.current_result_type == "comment":
            self.paste_comment_requested.emit(self.current_result)
            
    def eventFilter(self, obj, event):
        """Event filter to handle click-outside-to-close functionality."""
        if obj == self and event.type() == event.Type.MouseButtonPress:
            # Check if click is outside the dialog area
            if not self.rect().contains(event.pos()):
                self.close()
                return True
        return super().eventFilter(obj, event)
        
    def mousePressEvent(self, event):
        """Handle mouse press events for click-outside-to-close."""
        # If click is outside the dialog content area, close the dialog
        if not self.childAt(event.pos()):
            self.close()
        else:
            super().mousePressEvent(event)
            
    def keyPressEvent(self, event):
        """Handle key press events."""
        # Close on Escape key
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
            
    def show_loading(self, message: str = "Processing..."):
        """Show loading indicator during text processing."""
        if self.is_processing:
            return  # Already showing loading
            
        self.is_processing = True
        
        # Hide result frame if visible
        self.result_frame.hide()
        self.paste_button.hide()
        
        # Update loading message
        self.loading_label.setText(message)
        
        # Show loading frame
        self.loading_frame.show()
        
        # Disable action buttons during processing
        self.summarize_button.setEnabled(False)
        self.comment_button.setEnabled(False)
        
        # Start progress bar animation
        self.loading_progress.setRange(0, 0)  # Indeterminate
    
    def hide_loading(self):
        """Hide loading indicator."""
        self.is_processing = False
        self.loading_frame.hide()
        
        # Re-enable action buttons if we have text
        has_text = bool(self.selected_text)
        self.summarize_button.setEnabled(has_text)
        self.comment_button.setEnabled(has_text)
    
    def display_result(self, result: str, result_type: str):
        """Display the processing result in the popup."""
        # Hide loading indicator
        self.hide_loading()
        
        # Store current result
        self.current_result = result
        self.current_result_type = result_type
        
        # Update result title based on type
        if result_type == "summary":
            self.result_title.setText("Summary")
            self.result_frame.setStyleSheet("""
                QFrame {
                    background-color: #f0f8ff;
                    border: 2px solid #4a90e2;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
            self.result_title.setStyleSheet("""
                QLabel {
                    font-size: 13px;
                    font-weight: bold;
                    color: #4a90e2;
                    margin-bottom: 5px;
                }
            """)
        elif result_type == "comment":
            self.result_title.setText("Generated Comment")
            self.result_frame.setStyleSheet("""
                QFrame {
                    background-color: #f8f9fa;
                    border: 2px solid #28a745;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
            self.result_title.setStyleSheet("""
                QLabel {
                    font-size: 13px;
                    font-weight: bold;
                    color: #28a745;
                    margin-bottom: 5px;
                }
            """)
        
        # Set result text
        self.result_text_area.setPlainText(result)
        
        # Show result frame
        self.result_frame.show()
        
        # Show paste button only for comments
        if result_type == "comment":
            self.add_paste_button()
        else:
            self.paste_button.hide()
            
        # Scroll result text to top
        cursor = self.result_text_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.result_text_area.setTextCursor(cursor)
    
    def display_error(self, error_message: str):
        """Display an error message in the popup."""
        # Hide loading indicator
        self.hide_loading()
        
        # Clear current result
        self.current_result = None
        self.current_result_type = None
        
        # Update result frame for error display
        self.result_title.setText("Error")
        self.result_frame.setStyleSheet("""
            QFrame {
                background-color: #fff5f5;
                border: 2px solid #dc3545;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        self.result_title.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #dc3545;
                margin-bottom: 5px;
            }
        """)
        
        # Set error message
        self.result_text_area.setPlainText(error_message)
        
        # Show result frame
        self.result_frame.show()
        
        # Hide paste button for errors
        self.paste_button.hide()
    
    def add_paste_button(self):
        """Add paste button for comment results."""
        # Only show paste button for comment results
        if self.current_result_type == "comment" and self.current_result:
            self.paste_button.show()
        else:
            self.paste_button.hide()
    
    def clear_result(self):
        """Clear the current result display."""
        self.result_frame.hide()
        self.paste_button.hide()
        self.current_result = None
        self.current_result_type = None
        self.result_text_area.clear()
    
    def display_error(self, error_message: str, can_retry: bool = False):
        """
        Display an error message in the popup.
        
        Args:
            error_message: The error message to display
            can_retry: Whether the error can be retried
        """
        # Hide loading indicator
        self.hide_loading()
        
        # Hide result frame
        self.result_frame.hide()
        self.paste_button.hide()
        
        # Store error state
        self.current_error = error_message
        self.can_retry_current = can_retry
        
        # Create error frame if it doesn't exist
        if not hasattr(self, 'error_frame'):
            self._create_error_frame()
        
        # Update error message
        self.error_text_area.setPlainText(error_message)
        
        # Show/hide retry button based on whether error can be retried
        if can_retry:
            self.retry_button.show()
        else:
            self.retry_button.hide()
        
        # Show error frame
        self.error_frame.show()
        
        # Re-enable action buttons
        has_text = bool(self.selected_text)
        self.summarize_button.setEnabled(has_text)
        self.comment_button.setEnabled(has_text)
    
    def _create_error_frame(self):
        """Create the error display frame."""
        # Create error display area
        self.error_frame = QFrame()
        self.error_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.error_frame.setStyleSheet("""
            QFrame {
                background-color: #fff5f5;
                border: 2px solid #e53e3e;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        error_layout = QVBoxLayout(self.error_frame)
        error_layout.setContentsMargins(10, 10, 10, 10)
        error_layout.setSpacing(8)
        
        # Error title
        self.error_title = QLabel("Error")
        self.error_title.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #e53e3e;
                margin-bottom: 5px;
            }
        """)
        error_layout.addWidget(self.error_title)
        
        # Error text area
        self.error_text_area = QTextEdit()
        self.error_text_area.setReadOnly(True)
        self.error_text_area.setMaximumHeight(80)
        self.error_text_area.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | 
                                                     Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.error_text_area.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.error_text_area.setStyleSheet("""
            QTextEdit {
                border: 1px solid #fed7d7;
                border-radius: 5px;
                padding: 8px;
                font-size: 11px;
                background-color: #fff5f5;
                color: #742a2a;
                selection-background-color: #e53e3e;
            }
        """)
        error_layout.addWidget(self.error_text_area)
        
        # Add error frame to main layout (insert before button layout)
        main_layout = self.layout()
        main_layout.insertWidget(main_layout.count() - 1, self.error_frame)
        self.error_frame.hide()  # Initially hidden
    
    def hide_error(self):
        """Hide the error display."""
        if hasattr(self, 'error_frame'):
            self.error_frame.hide()
        self.retry_button.hide()
        self.current_error = None
        self.can_retry_current = False
    
    def clear_result(self):
        """Clear any displayed result."""
        self.result_frame.hide()
        self.paste_button.hide()
        self.current_result = None
        self.current_result_type = None
    
    def _on_retry_clicked(self):
        """Handle retry button click."""
        if hasattr(self, 'current_error') and self.can_retry_current:
            # Hide error display
            self.hide_error()
            
            # Determine what to retry based on the last operation
            if hasattr(self, 'last_operation_type'):
                if self.last_operation_type == "summary":
                    self._on_summarize_clicked()
                elif self.last_operation_type == "comment":
                    self._on_comment_clicked()
    
    def _on_summarize_clicked(self):
        """Handle Summarize button click."""
        if self.selected_text and not self.is_processing:
            self.last_operation_type = "summary"
            self.hide_error()
            self.show_loading("Generating summary...")
            self.summarize_requested.emit(self.selected_text)
            
    def _on_comment_clicked(self):
        """Handle Comment button click."""
        if self.selected_text and not self.is_processing:
            self.last_operation_type = "comment"
            self.hide_error()
            self.show_loading("Generating comment...")
            self.comment_requested.emit(self.selected_text)
    
    def show_warning(self, message: str):
        """Show a warning message to the user."""
        # For now, we'll show warnings in the error area with a different style
        if hasattr(self, 'error_frame'):
            self.error_frame.setStyleSheet("""
                QFrame {
                    background-color: #fff3cd;
                    border: 2px solid #ffc107;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
            self.error_title.setText("Warning")
            self.error_title.setStyleSheet("""
                QLabel {
                    font-size: 13px;
                    font-weight: bold;
                    color: #856404;
                    margin-bottom: 5px;
                }
            """)
            self.error_text_area.setPlainText(message)
            self.error_frame.show()
            
            # Auto-hide warning after 5 seconds
            QTimer.singleShot(5000, self.hide_error)
    
    def show_optimization_info(self, message: str):
        """Show optimization information to the user."""
        # Show as a brief info message
        self.show_warning(f"Optimization: {message}")
    
    def _cleanup_resources(self):
        """Cleanup resources to prevent memory leaks."""
        try:
            # Stop any running timers
            if hasattr(self, '_hide_timer'):
                self._hide_timer.stop()
            
            # Clear large data structures
            self.selected_text = ""
            self.current_result = None
            
            # Cleanup performance optimizer
            if hasattr(self, '_performance_optimizer'):
                self._performance_optimizer.cleanup()
                self._performance_optimizer = None
                
        except Exception as e:
            # Log error but don't raise to avoid cleanup issues
            import logging
            logging.getLogger(__name__).error(f"Error during resource cleanup: {e}")
    
    def closeEvent(self, event):
        """Handle close event with proper cleanup."""
        self._cleanup_resources()
        super().closeEvent(event)