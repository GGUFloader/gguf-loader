"""
Simple Smart Floating Assistant addon.

Shows a floating button when text is selected anywhere, processes text with GGUF model.
"""

import logging
from typing import Optional, Any
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication
import pyautogui


class SmartFloaterAddon(QObject):
    """Simple floating assistant that shows button on text selection."""
    
    def __init__(self, gguf_app_instance: Any):
        """Initialize the addon with GGUF Loader reference."""
        super().__init__()
        self.gguf_app = gguf_app_instance
        self._is_running = False
        self._floating_button = None
        self._popup_window = None
        self._selected_text = ""
        
        # Setup logging
        self._logger = logging.getLogger(__name__)
        
        # Timer to check for text selection
        self._selection_timer = QTimer()
        self._selection_timer.timeout.connect(self._check_text_selection)
        self._selection_timer.setInterval(500)  # Check every 500ms
    
    def _check_text_selection(self):
        """Check if text is currently selected and show/hide button accordingly."""
        try:
            # TEMPORARILY DISABLED - This was interfering with Ctrl key shortcuts
            # The pyautogui.hotkey('ctrl', 'c') was sending global Ctrl+C every 500ms
            # which was blocking normal Ctrl+V, Ctrl+C usage in text inputs
            return
            
            # Get currently selected text using clipboard
            app = QApplication.instance()
            clipboard = app.clipboard()
            
            # Store current clipboard content
            original_clipboard = clipboard.text()
            
            # Try to copy selection to clipboard
            pyautogui.hotkey('ctrl', 'c')
            
            # Small delay to let clipboard update
            QTimer.singleShot(50, lambda: self._process_selection(original_clipboard))
            
        except Exception as e:
            self._logger.debug(f"Error checking text selection: {e}")
    
    def _process_selection(self, original_clipboard):
        """Process the text selection and show button if text is selected."""
        try:
            app = QApplication.instance()
            clipboard = app.clipboard()
            current_text = clipboard.text()
            
            # Check if we have new selected text
            if current_text and current_text != original_clipboard and len(current_text.strip()) > 0:
                if current_text != self._selected_text:
                    self._selected_text = current_text
                    self._show_floating_button()
            else:
                # No text selected, hide button
                if self._floating_button:
                    self._hide_floating_button()
            
            # Restore original clipboard
            clipboard.setText(original_clipboard)
            
        except Exception as e:
            self._logger.debug(f"Error processing selection: {e}")
    
    def start(self) -> bool:
        """Start the addon and begin monitoring for text selection."""
        if self._is_running:
            return True
        
        try:
            self._logger.info("Starting Smart Floating Assistant addon")
            
            # Start monitoring for text selection
            self._selection_timer.start()
            
            self._is_running = True
            self._logger.info("Smart Floating Assistant addon started successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to start addon: {e}")
            return False
    
    def _show_floating_button(self):
        """Show floating button near cursor position."""
        try:
            from PySide6.QtWidgets import QPushButton, QWidget
            from PySide6.QtCore import Qt
            from PySide6.QtGui import QCursor
            
            # Hide existing button
            if self._floating_button:
                self._floating_button.close()
            
            # Create floating button
            self._floating_button = QPushButton("✨")
            self._floating_button.setFixedSize(30, 30)
            self._floating_button.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self._floating_button.setAttribute(Qt.WA_TranslucentBackground)
            self._floating_button.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 120, 215, 200);
                    border: none;
                    border-radius: 15px;
                    color: white;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 120, 215, 255);
                }
            """)
            
            # Position near cursor
            cursor_pos = QCursor.pos()
            self._floating_button.move(cursor_pos.x() + 20, cursor_pos.y() - 40)
            
            # Connect click to show popup
            self._floating_button.clicked.connect(self._show_popup)
            
            # Show button
            self._floating_button.show()
            
        except Exception as e:
            self._logger.error(f"Error showing floating button: {e}")
    
    def _hide_floating_button(self):
        """Hide the floating button."""
        if self._floating_button:
            self._floating_button.close()
            self._floating_button = None
    
    def _show_popup(self):
        """Show popup window with selected text and processing options."""
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel
            from PySide6.QtCore import Qt
            
            # Close existing popup
            if self._popup_window:
                self._popup_window.close()
            
            # Create popup dialog
            self._popup_window = QDialog()
            self._popup_window.setWindowTitle("Smart Floating Assistant")
            self._popup_window.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
            self._popup_window.setFixedSize(400, 300)
            
            # Layout
            layout = QVBoxLayout(self._popup_window)
            
            # Selected text display
            layout.addWidget(QLabel("Selected Text:"))
            text_display = QTextEdit()
            text_display.setPlainText(self._selected_text)
            text_display.setMaximumHeight(100)
            text_display.setReadOnly(True)
            text_display.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            text_display.setContextMenuPolicy(Qt.DefaultContextMenu)
            layout.addWidget(text_display)
            
            # Action buttons
            button_layout = QHBoxLayout()
            
            summarize_btn = QPushButton("Summarize")
            summarize_btn.clicked.connect(lambda: self._process_text("summarize"))
            button_layout.addWidget(summarize_btn)
            
            comment_btn = QPushButton("Comment")
            comment_btn.clicked.connect(lambda: self._process_text("comment"))
            button_layout.addWidget(comment_btn)
            
            layout.addLayout(button_layout)
            
            # Result display
            layout.addWidget(QLabel("Result:"))
            self._result_display = QTextEdit()
            self._result_display.setReadOnly(True)
            self._result_display.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            self._result_display.setContextMenuPolicy(Qt.DefaultContextMenu)
            layout.addWidget(self._result_display)
            
            # Show popup
            self._popup_window.show()
            
            # Hide floating button
            self._hide_floating_button()
            
        except Exception as e:
            self._logger.error(f"Error showing popup: {e}")
    
    def _connect_integration_signals(self):
        """Connect signals from the integration layer."""
        if hasattr(self, '_integration'):
            # Connect integration workflow signals
            self._integration.workflow_started.connect(self._on_workflow_started)
            self._integration.workflow_completed.connect(self._on_workflow_completed)
            self._integration.workflow_failed.connect(self._on_workflow_failed)
    
    def _on_workflow_started(self, selection):
        """Handle workflow started event."""
        self._logger.info(f"Workflow started for text selection: {len(selection.content)} chars")
        self.update_ui_state(current_selection=selection)
    
    def _on_workflow_completed(self, result):
        """Handle workflow completed event."""
        self._logger.info(f"Workflow completed: {result.processing_type}")
        self.update_ui_state(last_result=result)
    
    def _on_workflow_failed(self, error_message):
        """Handle workflow failed event."""
        self._logger.error(f"Workflow failed: {error_message}")
    
    def _connect_component_signals(self):
        """Connect signals between components for coordination (fallback)."""
        if self._floater_ui and self._comment_engine and self._error_handler:
            # Connect UI to processing engine
            if hasattr(self._floater_ui, 'text_processing_requested'):
                self._floater_ui.text_processing_requested.connect(
                    self._comment_engine.process_text
                )
            self._comment_engine.processing_completed.connect(
                lambda result: self._floater_ui.display_result(result.processed_text, result.processing_type) 
                if hasattr(self._floater_ui, 'display_result') else None
            )
            
            # Connect error handling for processing
            self._comment_engine.processing_failed.connect(
                lambda error: self._error_handler.handle_processing_error(
                    ProcessingResult("", "", "", False, error, 0.0)
                )
            )
            self._error_handler.error_occurred.connect(
                lambda error: self._floater_ui.display_error(error) 
                if hasattr(self._floater_ui, 'display_error') else None
            )
            self._error_handler.retry_requested.connect(
                self._handle_retry_request
            )
        
        if self._floater_ui and self._text_injector and self._error_handler:
            # Connect UI to text injection
            if hasattr(self._floater_ui, 'text_injection_requested'):
                self._floater_ui.text_injection_requested.connect(
                    self._text_injector.paste_with_fallback
                )
            
            # Connect error handling for injection
            self._text_injector.injection_completed.connect(
                self._handle_injection_result
            )
    
    def _handle_retry_request(self, operation_type: str, operation_data: str):
        """Handle retry requests from the error handler."""
        if operation_type == "processing":
            # Parse operation data to determine processing type and text
            # This is a simplified implementation - in practice you'd need more robust parsing
            if self._comment_engine:
                self._comment_engine.process_text_async(operation_data, "summary")
        elif operation_type == "injection":
            if self._text_injector:
                self._text_injector.paste_with_fallback(operation_data)
    
    def _handle_injection_result(self, success: bool, message: str):
        """Handle injection results and errors."""
        if not success and self._error_handler:
            self._error_handler.handle_injection_error(message, "")
    
    def stop(self) -> bool:
        """
        Stop the addon and cleanup resources.
        
        Returns:
            bool: True if shutdown was successful, False otherwise
        """
        if not self._is_running:
            self._logger.warning("Addon is not running")
            return True
        
        try:
            self._logger.info("Stopping Smart Floating Assistant addon")
            
            # Stop UI monitoring
            if hasattr(self, '_integration'):
                self._integration.stop_monitoring()
            elif self._floater_ui and hasattr(self._floater_ui, 'stop_monitoring'):
                self._floater_ui.stop_monitoring()
            
            # Cleanup components
            self._cleanup_components()
            
            self._is_running = False
            self.addon_stopped.emit()
            self._logger.info("Smart Floating Assistant addon stopped successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to stop addon: {e}")
            return False
    
    def _handle_performance_warning(self, warning_message: str):
        """Handle performance warnings."""
        self._logger.warning(f"Performance warning: {warning_message}")
    
    def _handle_optimization_applied(self, optimization_message: str):
        """Handle optimization applied notifications."""
        self._logger.info(f"Optimization applied: {optimization_message}")
    
    def _cleanup_components(self):
        """Cleanup all addon components."""
        # Cleanup integration layer first
        if hasattr(self, '_integration'):
            try:
                self._integration.cleanup()
            except Exception as e:
                self._logger.error(f"Error cleaning up integration: {e}")
            finally:
                self._integration = None
        
        # Cleanup individual components (fallback)
        components = [
            ('_floater_ui', self._floater_ui),
            ('_comment_engine', self._comment_engine),
            ('_text_injector', self._text_injector),
            ('_error_handler', self._error_handler),
            ('_performance_optimizer', self._performance_optimizer),
            ('_privacy_security', self._privacy_security)
        ]
        
        for name, component in components:
            if component:
                try:
                    if hasattr(component, 'cleanup'):
                        component.cleanup()
                except Exception as e:
                    self._logger.error(f"Error cleaning up {name}: {e}")
                finally:
                    setattr(self, name, None)
    
    def get_model_backend(self) -> Optional[Any]:
        """
        Get reference to the GGUF model backend.
        
        Returns:
            Optional[Any]: The loaded GGUF model instance, or None if no model is loaded
        """
        try:
            if hasattr(self.gguf_app, 'model'):
                model = self.gguf_app.model
                return model if model is not None else None
            else:
                self._logger.debug("No model currently loaded in GGUF Loader")
                return None
        except Exception as e:
            self._logger.error(f"Error accessing model backend: {e}")
            return None
    
    def is_model_available(self) -> bool:
        """
        Check if a GGUF model is currently available for processing.
        
        Returns:
            bool: True if model is available, False otherwise
        """
        return self.get_model_backend() is not None
    
    def get_ui_state(self) -> UIState:
        """
        Get current UI state.
        
        Returns:
            UIState: Current state of the floating UI components
        """
        return self._ui_state
    
    def update_ui_state(self, **kwargs):
        """
        Update UI state with provided parameters.
        
        Args:
            **kwargs: UI state parameters to update
        """
        for key, value in kwargs.items():
            if hasattr(self._ui_state, key):
                setattr(self._ui_state, key, value)
    
    def is_running(self) -> bool:
        """
        Check if the addon is currently running.
        
        Returns:
            bool: True if addon is running, False otherwise
        """
        return self._is_running
    
    def get_component(self, component_name: str) -> Optional[Any]:
        """
        Get reference to a specific component.
        
        Args:
            component_name: Name of the component ('floater_ui', 'comment_engine', 'text_injector')
            
        Returns:
            Optional[Any]: Component instance or None if not found
        """
        # Try integration layer first
        if hasattr(self, '_integration') and component_name == 'integration':
            return self._integration
        
        component_map = {
            'floater_ui': self._floater_ui,
            'comment_engine': self._comment_engine,
            'text_injector': self._text_injector,
            'error_handler': getattr(self, '_error_handler', None),
            'privacy_security': self._privacy_security
        }
        return component_map.get(component_name)
    
    def get_integration_status(self) -> dict:
        """
        Get current integration status and workflow information.
        
        Returns:
            dict: Integration status information
        """
        if hasattr(self, '_integration'):
            return self._integration.get_workflow_status()
        else:
            return {
                'is_monitoring': False,
                'is_button_visible': self._ui_state.is_button_visible,
                'is_popup_open': self._ui_state.is_popup_open,
                'is_processing': False,
                'current_workflow_id': None,
                'has_current_selection': self._ui_state.current_selection is not None,
                'has_last_result': self._ui_state.last_result is not None,
                'model_available': self.is_model_available()
            }


# Addon registration function for GGUF Loader addon system
def register(parent=None):
    """
    Register function called by the GGUF Loader addon system.
    
    This function is called when the addon is loaded by the addon manager.
    It should return a widget or None for background addons.
    
    Args:
        parent: Parent widget (GGUF Loader main window)
        
    Returns:
        None: This addon runs in background, no widget needed
    """
    try:
        # Get reference to the main GGUF Loader application
        gguf_app = parent
        
        # Stop existing addon if running
        if hasattr(parent, '_smart_floater_addon') and parent._smart_floater_addon:
            parent._smart_floater_addon.stop()
        
        # Create and start the addon
        addon = SmartFloaterAddon(gguf_app)
        addon.start()
        
        # Store addon reference in parent for lifecycle management
        parent._smart_floater_addon = addon
        
        # Return None since this is a background addon with no UI widget
        return None
        
    except Exception as e:
        logging.error(f"Failed to register Smart Floating Assistant addon: {e}")
        return None