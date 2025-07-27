"""
Comprehensive error handling and user feedback system for the Smart Floating Assistant addon.

This module provides centralized error handling, user feedback, and retry functionality
across all components of the addon.
"""

import logging
from typing import Optional, Callable, Dict, Any
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication

from .data_models import ProcessingResult


class ErrorHandler(QObject):
    """Centralized error handling and user feedback system."""
    
    # Signals for error events
    error_occurred = Signal(str, bool)  # error_message, can_retry
    retry_requested = Signal(str, str)  # operation_type, data
    notification_requested = Signal(str, bool, int)  # message, is_success, duration
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Error tracking
        self._error_history = []
        self._retry_counts = {}
        self._max_retries = 3
        self._retry_delay = 2000  # milliseconds
        
        # Retry timer
        self._retry_timer = QTimer()
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._execute_pending_retry)
        
        # Pending retry state
        self._pending_retry = None
    
    def handle_processing_error(self, result: ProcessingResult) -> bool:
        """
        Handle processing errors from the comment engine.
        
        Args:
            result: ProcessingResult with error information
            
        Returns:
            bool: True if error was handled and retry is possible, False otherwise
        """
        if result.success:
            # Reset retry count on success
            operation_key = f"{result.processing_type}:{hash(result.original_text)}"
            self._retry_counts.pop(operation_key, None)
            return True
        
        error_message = result.error_message or "Unknown processing error"
        self.logger.error(f"Processing error: {error_message}")
        
        # Add to error history
        self._add_to_error_history("processing", error_message, result.processing_type)
        
        # Check if error can be retried
        can_retry = self._can_retry_processing_error(result)
        
        # Emit error signal for UI display
        user_friendly_message = self._get_user_friendly_processing_error(error_message)
        self.error_occurred.emit(user_friendly_message, can_retry)
        
        return can_retry
    
    def handle_injection_error(self, error_message: str, operation_data: str) -> bool:
        """
        Handle text injection errors.
        
        Args:
            error_message: Error message from injection operation
            operation_data: The text that failed to inject
            
        Returns:
            bool: True if error was handled and retry is possible, False otherwise
        """
        self.logger.error(f"Injection error: {error_message}")
        
        # Add to error history
        self._add_to_error_history("injection", error_message, operation_data)
        
        # Check if error can be retried
        can_retry = self._can_retry_injection_error(error_message)
        
        # Emit error signal for UI display
        user_friendly_message = self._get_user_friendly_injection_error(error_message)
        self.error_occurred.emit(user_friendly_message, can_retry)
        
        return can_retry
    
    def handle_clipboard_error(self, error_message: str) -> bool:
        """
        Handle clipboard operation errors.
        
        Args:
            error_message: Error message from clipboard operation
            
        Returns:
            bool: True if error was handled, False otherwise
        """
        self.logger.error(f"Clipboard error: {error_message}")
        
        # Add to error history
        self._add_to_error_history("clipboard", error_message, None)
        
        # Clipboard errors are generally not retryable
        user_friendly_message = self._get_user_friendly_clipboard_error(error_message)
        self.error_occurred.emit(user_friendly_message, False)
        
        return False
    
    def request_retry(self, operation_type: str, operation_data: str, delay_ms: int = None):
        """
        Request a retry of a failed operation.
        
        Args:
            operation_type: Type of operation to retry ('processing' or 'injection')
            operation_data: Data needed for the retry
            delay_ms: Delay before retry in milliseconds (optional)
        """
        if delay_ms is None:
            delay_ms = self._retry_delay
        
        # Store pending retry
        self._pending_retry = {
            'operation_type': operation_type,
            'operation_data': operation_data
        }
        
        # Start retry timer
        self._retry_timer.start(delay_ms)
        
        self.logger.info(f"Retry scheduled for {operation_type} in {delay_ms}ms")
    
    def _execute_pending_retry(self):
        """Execute the pending retry operation."""
        if not self._pending_retry:
            return
        
        operation_type = self._pending_retry['operation_type']
        operation_data = self._pending_retry['operation_data']
        
        self.logger.info(f"Executing retry for {operation_type}")
        
        # Emit retry signal
        self.retry_requested.emit(operation_type, operation_data)
        
        # Clear pending retry
        self._pending_retry = None
    
    def _can_retry_processing_error(self, result: ProcessingResult) -> bool:
        """
        Determine if a processing error can be retried.
        
        Args:
            result: ProcessingResult with error information
            
        Returns:
            bool: True if error can be retried, False otherwise
        """
        if not result.error_message:
            return False
        
        error_lower = result.error_message.lower()
        
        # Non-retryable errors
        non_retryable = [
            "no gguf model",
            "model is not loaded",
            "too long",
            "maximum allowed",
            "no text provided",
            "out of memory"
        ]
        
        for non_retryable_error in non_retryable:
            if non_retryable_error in error_lower:
                return False
        
        # Check retry count
        operation_key = f"{result.processing_type}:{hash(result.original_text)}"
        current_retries = self._retry_counts.get(operation_key, 0)
        
        if current_retries >= self._max_retries:
            return False
        
        # Increment retry count
        self._retry_counts[operation_key] = current_retries + 1
        
        return True
    
    def _can_retry_injection_error(self, error_message: str) -> bool:
        """
        Determine if an injection error can be retried.
        
        Args:
            error_message: Error message from injection
            
        Returns:
            bool: True if error can be retried, False otherwise
        """
        error_lower = error_message.lower()
        
        # Non-retryable errors
        non_retryable = [
            "no text provided",
            "too long",
            "permission denied",
            "failsafe"
        ]
        
        for non_retryable_error in non_retryable:
            if non_retryable_error in error_lower:
                return False
        
        # Check retry count for injection operations
        operation_key = f"injection:{hash(error_message)}"
        current_retries = self._retry_counts.get(operation_key, 0)
        
        if current_retries >= self._max_retries:
            return False
        
        # Increment retry count
        self._retry_counts[operation_key] = current_retries + 1
        
        return True
    
    def _get_user_friendly_processing_error(self, error_message: str) -> str:
        """Convert technical processing errors to user-friendly messages."""
        error_lower = error_message.lower()
        
        if "no gguf model" in error_lower or "model is not loaded" in error_lower:
            return ("No AI model is currently loaded. Please load a model in the GGUF Loader "
                   "application before using text processing features.")
        
        if "failed to generate" in error_lower or "model failed" in error_lower:
            return ("The AI model encountered an issue while processing your text. "
                   "This might be due to the text content or model state.")
        
        if "timeout" in error_lower:
            return ("Text processing is taking longer than expected. The model might be "
                   "overloaded or the text might be too complex.")
        
        if "too long" in error_lower:
            return ("The selected text is too long for processing. Please select a shorter "
                   "text segment (maximum 10,000 characters).")
        
        if "memory" in error_lower:
            return ("The system is running low on memory. Please close some applications "
                   "and try again, or try processing shorter text.")
        
        return ("An error occurred while processing your text. Please try again or "
               "check that the GGUF Loader application is working properly.")
    
    def _get_user_friendly_injection_error(self, error_message: str) -> str:
        """Convert technical injection errors to user-friendly messages."""
        error_lower = error_message.lower()
        
        if "permission" in error_lower:
            return ("Permission denied for text insertion. Please ensure the application "
                   "has the necessary permissions to simulate keyboard input.")
        
        if "failsafe" in error_lower:
            return ("Text insertion was cancelled for safety. This happens when the mouse "
                   "is moved to a screen corner during insertion.")
        
        if "timeout" in error_lower or "timed out" in error_lower:
            return ("Text insertion timed out. The target application might not be responding.")
        
        if "display" in error_lower:
            return ("Cannot access the display for text insertion. Please check your "
                   "display settings and try again.")
        
        return ("Failed to insert text. Please ensure the cursor is in a text field and try again.")
    
    def _get_user_friendly_clipboard_error(self, error_message: str) -> str:
        """Convert technical clipboard errors to user-friendly messages."""
        error_lower = error_message.lower()
        
        if "not available" in error_lower:
            return ("Clipboard is not available. Please check your system settings.")
        
        if "access" in error_lower:
            return ("Cannot access clipboard. Please check application permissions.")
        
        return ("Failed to copy text to clipboard. Please try again.")
    
    def _add_to_error_history(self, error_type: str, error_message: str, context: Any):
        """Add an error to the error history."""
        from datetime import datetime
        
        error_entry = {
            'timestamp': datetime.now(),
            'type': error_type,
            'message': error_message,
            'context': context
        }
        
        self._error_history.append(error_entry)
        
        # Keep only last 50 errors
        if len(self._error_history) > 50:
            self._error_history = self._error_history[-50:]
    
    def get_error_history(self) -> list:
        """Get the error history."""
        return self._error_history.copy()
    
    def get_retry_statistics(self) -> Dict[str, int]:
        """Get retry statistics."""
        return self._retry_counts.copy()
    
    def reset_retry_counts(self):
        """Reset all retry counts."""
        self._retry_counts.clear()
        self.logger.info("Retry counts reset")
    
    def cleanup(self):
        """Cleanup resources."""
        self._retry_timer.stop()
        self._retry_counts.clear()
        self._error_history.clear()
        self._pending_retry = None
        self.logger.info("ErrorHandler cleaned up")