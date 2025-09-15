"""
Integration module for the Smart Floating Assistant addon.

This module provides the main integration layer that wires together all components
and manages the complete user workflow from text selection to result insertion.
"""

import logging
from typing import Optional, Any
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication

from .data_models import TextSelection, ProcessingResult, UIState
from .floater_ui import CrossPlatformTextMonitor, FloatingButton, TextProcessorPopup
from .comment_engine import CommentEngine
from .injector import TextInjector
from .error_handler import ErrorHandler
from .privacy_security import PrivacySecurityManager


class SmartFloaterIntegration(QObject):
    """
    Main integration class that coordinates all addon components.
    
    This class manages the complete workflow:
    1. Text selection detection
    2. Floating button display
    3. Popup window interaction
    4. AI text processing
    5. Result display and insertion
    """
    
    # Signals for integration events
    workflow_started = Signal(TextSelection)
    workflow_completed = Signal(ProcessingResult)
    workflow_failed = Signal(str)
    
    def __init__(self, gguf_app_instance: Any):
        """
        Initialize the integration layer.
        
        Args:
            gguf_app_instance: Reference to the GGUF Loader application
        """
        super().__init__()
        self.gguf_app = gguf_app_instance
        self.logger = logging.getLogger(__name__)
        
        # Component references
        self.text_monitor = None
        self.floating_button = None
        self.popup_window = None
        self.comment_engine = None
        self.text_injector = None
        self.error_handler = None
        self.privacy_security = None
        
        # State management
        self.ui_state = UIState(
            is_button_visible=False,
            is_popup_open=False,
            current_selection=None,
            last_result=None
        )
        
        # Workflow state
        self.current_workflow_id = None
        self.is_processing = False
        
        # Cleanup timer for automatic resource management
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self._periodic_cleanup)
        self.cleanup_timer.start(30000)  # Cleanup every 30 seconds
        
    def initialize_components(self) -> bool:
        """
        Initialize all addon components and wire them together.
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            self.logger.info("Initializing Smart Floater components")
            
            # Initialize privacy and security first
            self.privacy_security = PrivacySecurityManager()
            self.privacy_security.start_protection()
            
            # Initialize error handling
            self.error_handler = ErrorHandler()
            
            # Initialize text monitoring
            self.text_monitor = CrossPlatformTextMonitor()
            
            # Initialize floating button
            self.floating_button = FloatingButton()
            
            # Initialize popup window
            self.popup_window = TextProcessorPopup()
            
            # Initialize comment engine with model backend
            model_backend = self._get_validated_model_backend()
            self.comment_engine = CommentEngine(model_backend)
            
            # Initialize text injector
            self.text_injector = TextInjector()
            
            # Wire components together
            self._wire_components()
            
            self.logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            return False
    
    def _get_validated_model_backend(self) -> Optional[Any]:
        """Get and validate the model backend from GGUF Loader."""
        try:
            if hasattr(self.gguf_app, 'model'):
                model = self.gguf_app.model
                if model and self.privacy_security.validate_model_backend(model):
                    return model
            return None
        except Exception as e:
            self.logger.error(f"Error validating model backend: {e}")
            return None
    
    def _wire_components(self):
        """Wire all components together with proper signal connections."""
        # Text selection workflow
        self.text_monitor.text_selected.connect(self._on_text_selected)
        self.text_monitor.text_deselected.connect(self._on_text_deselected)
        
        # Floating button workflow
        self.floating_button.clicked.connect(self._on_floating_button_clicked)
        
        # Popup window workflow
        self.popup_window.summarize_requested.connect(self._on_summarize_requested)
        self.popup_window.comment_requested.connect(self._on_comment_requested)
        self.popup_window.paste_comment_requested.connect(self._on_paste_comment_requested)
        
        # Comment engine workflow
        self.comment_engine.processing_completed.connect(self._on_processing_completed)
        self.comment_engine.processing_failed.connect(self._on_processing_failed)
        
        # Text injector workflow
        self.text_injector.injection_completed.connect(self._on_injection_completed)
        
        # Error handling workflow
        self.error_handler.error_occurred.connect(self._on_error_occurred)
        self.error_handler.retry_requested.connect(self._on_retry_requested)
        
        self.logger.info("Component signals wired successfully")
    
    def start_monitoring(self) -> bool:
        """
        Start the complete text selection monitoring workflow.
        
        Returns:
            bool: True if monitoring started successfully
        """
        try:
            if not self.text_monitor:
                self.logger.error("Text monitor not initialized")
                return False
            
            self.text_monitor.start_monitoring()
            self.logger.info("Text selection monitoring started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start monitoring: {e}")
            return False
    
    def stop_monitoring(self) -> bool:
        """
        Stop the text selection monitoring workflow.
        
        Returns:
            bool: True if monitoring stopped successfully
        """
        try:
            if self.text_monitor:
                self.text_monitor.stop_monitoring()
            
            # Hide any visible UI elements
            if self.floating_button and self.floating_button.isVisible():
                self.floating_button.hide()
            
            if self.popup_window and self.popup_window.isVisible():
                self.popup_window.close()
            
            self.logger.info("Text selection monitoring stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop monitoring: {e}")
            return False
    
    def _on_text_selected(self, selection: TextSelection):
        """Handle text selection event."""
        try:
            self.logger.info(f"Text selected: {len(selection.content)} characters from {selection.source_app}")
            
            # Update UI state
            self.ui_state.current_selection = selection
            self.ui_state.is_button_visible = True
            
            # Show floating button near cursor
            if self.floating_button:
                self.floating_button.show_at_cursor(selection.cursor_position)
                self.floating_button.hide_with_delay(5)  # Auto-hide after 5 seconds
            
            # Emit workflow started signal
            self.workflow_started.emit(selection)
            
        except Exception as e:
            self.logger.error(f"Error handling text selection: {e}")
            self._handle_workflow_error(f"Failed to handle text selection: {e}")
    
    def _on_text_deselected(self):
        """Handle text deselection event."""
        try:
            self.logger.debug("Text deselected")
            
            # Update UI state
            self.ui_state.current_selection = None
            self.ui_state.is_button_visible = False
            
            # Hide floating button with delay
            if self.floating_button:
                self.floating_button.hide_with_delay(2)  # Shorter delay for deselection
                
        except Exception as e:
            self.logger.error(f"Error handling text deselection: {e}")
    
    def _on_floating_button_clicked(self):
        """Handle floating button click event."""
        try:
            if not self.ui_state.current_selection:
                self.logger.warning("Floating button clicked but no text selection available")
                return
            
            self.logger.info("Floating button clicked, opening popup")
            
            # Update UI state
            self.ui_state.is_popup_open = True
            
            # Set selected text in popup and show it
            if self.popup_window:
                self.popup_window.set_selected_text(self.ui_state.current_selection.content)
                self.popup_window.show()
                self.popup_window.raise_()
                self.popup_window.activateWindow()
            
            # Hide floating button
            if self.floating_button:
                self.floating_button.hide()
                
        except Exception as e:
            self.logger.error(f"Error handling floating button click: {e}")
            self._handle_workflow_error(f"Failed to open popup: {e}")
    
    def _on_summarize_requested(self, text: str):
        """Handle summarization request from popup."""
        try:
            self.logger.info(f"Summarization requested for {len(text)} characters")
            
            if not self.comment_engine:
                self._handle_workflow_error("Comment engine not available")
                return
            
            # Check if model is available
            if not self.comment_engine.is_model_available():
                error_msg = "No AI model is currently loaded. Please load a model in the GGUF Loader application."
                self._handle_processing_error(error_msg)
                return
            
            # Start processing
            self.is_processing = True
            self.current_workflow_id = f"summary_{hash(text)}"
            
            # Process asynchronously
            self.comment_engine.process_text_async(text, "summary")
            
        except Exception as e:
            self.logger.error(f"Error handling summarize request: {e}")
            self._handle_workflow_error(f"Failed to start summarization: {e}")
    
    def _on_comment_requested(self, text: str):
        """Handle comment generation request from popup."""
        try:
            self.logger.info(f"Comment generation requested for {len(text)} characters")
            
            if not self.comment_engine:
                self._handle_workflow_error("Comment engine not available")
                return
            
            # Check if model is available
            if not self.comment_engine.is_model_available():
                error_msg = "No AI model is currently loaded. Please load a model in the GGUF Loader application."
                self._handle_processing_error(error_msg)
                return
            
            # Start processing
            self.is_processing = True
            self.current_workflow_id = f"comment_{hash(text)}"
            
            # Process asynchronously
            self.comment_engine.process_text_async(text, "comment")
            
        except Exception as e:
            self.logger.error(f"Error handling comment request: {e}")
            self._handle_workflow_error(f"Failed to start comment generation: {e}")
    
    def _on_processing_completed(self, result: ProcessingResult):
        """Handle successful text processing completion."""
        try:
            self.logger.info(f"Processing completed: {result.processing_type} in {result.processing_time:.2f}s")
            
            # Update UI state
            self.ui_state.last_result = result
            self.is_processing = False
            
            # Display result in popup
            if self.popup_window:
                self.popup_window.display_result(result.processed_text, result.processing_type)
            
            # Emit workflow completed signal
            self.workflow_completed.emit(result)
            
        except Exception as e:
            self.logger.error(f"Error handling processing completion: {e}")
            self._handle_workflow_error(f"Failed to display processing result: {e}")
    
    def _on_processing_failed(self, error_message: str):
        """Handle text processing failure."""
        try:
            self.logger.error(f"Processing failed: {error_message}")
            self.is_processing = False
            
            # Handle the error through error handler
            self._handle_processing_error(error_message)
            
        except Exception as e:
            self.logger.error(f"Error handling processing failure: {e}")
            self._handle_workflow_error(f"Failed to handle processing error: {e}")
    
    def _on_paste_comment_requested(self, text: str):
        """Handle paste comment request from popup."""
        try:
            self.logger.info(f"Paste comment requested for {len(text)} characters")
            
            if not self.text_injector:
                self._handle_workflow_error("Text injector not available")
                return
            
            # Close popup first
            if self.popup_window:
                self.popup_window.close()
                self.ui_state.is_popup_open = False
            
            # Inject text with fallback to clipboard
            self.text_injector.paste_with_fallback(text)
            
        except Exception as e:
            self.logger.error(f"Error handling paste comment request: {e}")
            self._handle_workflow_error(f"Failed to paste comment: {e}")
    
    def _on_injection_completed(self, success: bool, message: str):
        """Handle text injection completion."""
        try:
            if success:
                self.logger.info(f"Text injection completed: {message}")
            else:
                self.logger.warning(f"Text injection failed: {message}")
                # Let the injector handle its own error notifications
                
        except Exception as e:
            self.logger.error(f"Error handling injection completion: {e}")
    
    def _on_error_occurred(self, error_message: str):
        """Handle error events from error handler."""
        try:
            self.logger.error(f"Error occurred: {error_message}")
            
            # Display error in popup if it's open
            if self.popup_window and self.popup_window.isVisible():
                self.popup_window.display_error(error_message)
            
        except Exception as e:
            self.logger.error(f"Error handling error event: {e}")
    
    def _on_retry_requested(self, operation_type: str, operation_data: str):
        """Handle retry requests from error handler."""
        try:
            self.logger.info(f"Retry requested for {operation_type}")
            
            if operation_type == "processing" and self.comment_engine:
                # Parse operation data to determine processing type
                if "summary" in operation_data.lower():
                    self.comment_engine.process_text_async(operation_data, "summary")
                elif "comment" in operation_data.lower():
                    self.comment_engine.process_text_async(operation_data, "comment")
            elif operation_type == "injection" and self.text_injector:
                self.text_injector.paste_with_fallback(operation_data)
                
        except Exception as e:
            self.logger.error(f"Error handling retry request: {e}")
    
    def _handle_processing_error(self, error_message: str):
        """Handle processing errors through the error handler."""
        if self.error_handler:
            # Create a dummy ProcessingResult for error handling
            error_result = ProcessingResult(
                original_text="",
                processed_text="",
                processing_type="unknown",
                success=False,
                error_message=error_message,
                processing_time=0.0
            )
            self.error_handler.handle_processing_error(error_result)
        else:
            # Fallback error handling
            if self.popup_window and self.popup_window.isVisible():
                self.popup_window.display_error(error_message)
    
    def _handle_workflow_error(self, error_message: str):
        """Handle general workflow errors."""
        self.logger.error(f"Workflow error: {error_message}")
        self.is_processing = False
        self.workflow_failed.emit(error_message)
        
        # Display error in popup if available
        if self.popup_window and self.popup_window.isVisible():
            self.popup_window.display_error(error_message)
    
    def _periodic_cleanup(self):
        """Perform periodic cleanup of resources."""
        try:
            # Clean up privacy and security manager
            if self.privacy_security:
                self.privacy_security.cleanup_old_data()
            
            # Reset workflow state if stuck
            if self.is_processing and self.current_workflow_id:
                # Check if processing has been stuck for too long (5 minutes)
                # This is a safety mechanism
                pass
                
        except Exception as e:
            self.logger.error(f"Error during periodic cleanup: {e}")
    
    def update_model_backend(self, model_backend: Optional[Any]):
        """Update the model backend for the comment engine."""
        try:
            if self.comment_engine:
                validated_backend = None
                if model_backend and self.privacy_security.validate_model_backend(model_backend):
                    validated_backend = model_backend
                
                self.comment_engine.set_model_backend(validated_backend)
                self.logger.info(f"Model backend updated: {'Available' if validated_backend else 'None'}")
                
        except Exception as e:
            self.logger.error(f"Error updating model backend: {e}")
    
    def get_workflow_status(self) -> dict:
        """Get current workflow status information."""
        return {
            'is_monitoring': self.text_monitor.monitor.is_monitoring if self.text_monitor else False,
            'is_button_visible': self.ui_state.is_button_visible,
            'is_popup_open': self.ui_state.is_popup_open,
            'is_processing': self.is_processing,
            'current_workflow_id': self.current_workflow_id,
            'has_current_selection': self.ui_state.current_selection is not None,
            'has_last_result': self.ui_state.last_result is not None,
            'model_available': self.comment_engine.is_model_available() if self.comment_engine else False
        }
    
    def cleanup(self):
        """Cleanup all components and resources."""
        try:
            self.logger.info("Cleaning up SmartFloaterIntegration")
            
            # Stop monitoring
            self.stop_monitoring()
            
            # Stop cleanup timer
            self.cleanup_timer.stop()
            
            # Cleanup components
            components = [
                ('text_monitor', self.text_monitor),
                ('floating_button', self.floating_button),
                ('popup_window', self.popup_window),
                ('comment_engine', self.comment_engine),
                ('text_injector', self.text_injector),
                ('error_handler', self.error_handler),
                ('privacy_security', self.privacy_security)
            ]
            
            for name, component in components:
                if component and hasattr(component, 'cleanup'):
                    try:
                        component.cleanup()
                    except Exception as e:
                        self.logger.error(f"Error cleaning up {name}: {e}")
                setattr(self, name, None)
            
            # Reset state
            self.ui_state = UIState(False, False, None, None)
            self.is_processing = False
            self.current_workflow_id = None
            
            self.logger.info("SmartFloaterIntegration cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during integration cleanup: {e}")