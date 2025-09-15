"""
AI text processing engine for the Smart Floating Assistant addon.

This module handles AI text processing using the GGUF backend, including
summarization and comment generation with comprehensive error handling.
"""

import logging
import time
from typing import Optional, Any, Callable
from PySide6.QtCore import QObject, Signal, QTimer

from .data_models import ProcessingResult
from .privacy_security import PrivacySecurityManager
from .performance_optimizer import PerformanceOptimizer


class CommentEngine(QObject):
    """AI text processing engine that interfaces with GGUF backend."""
    
    # Signals for async processing
    processing_completed = Signal(ProcessingResult)
    processing_failed = Signal(str)
    retry_requested = Signal(str, str)  # text, processing_type
    
    def __init__(self, model_backend: Optional[Any] = None):
        """
        Initialize the comment engine with GGUF backend.
        
        Args:
            model_backend: Reference to the loaded GGUF model instance
        """
        super().__init__()
        self.model_backend = model_backend
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.INFO)
        
        # Initialize privacy and security manager
        self.privacy_security = PrivacySecurityManager()
        self.privacy_security.start_protection()
        
        # Initialize performance optimizer
        self._performance_optimizer = PerformanceOptimizer()
        self._performance_optimizer.start_optimization()
        
        # Connect performance signals
        self._performance_optimizer.warning_issued.connect(self._handle_performance_warning)
        
        # Processing templates
        self.SUMMARIZE_PROMPT = "Summarize this clearly: {text}"
        self.COMMENT_PROMPT = "Write a friendly and insightful comment about: {text}"
        
        # Configuration
        self.MAX_TEXT_LENGTH = 10000
        self.PROCESSING_TIMEOUT = 30.0  # seconds
        self.MAX_RETRY_ATTEMPTS = 3
        self.RETRY_DELAY = 2.0  # seconds between retries
        
        # Error handling state
        self._retry_count = {}  # Track retry attempts per operation
        self._last_error = None
        self._retry_timer = QTimer()
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._execute_retry)
    
    def set_model_backend(self, model_backend: Optional[Any]):
        """
        Update the model backend reference.
        
        Args:
            model_backend: New model backend instance or None
        """
        # Validate model backend for security before setting
        if model_backend is not None:
            if not self.privacy_security.validate_model_backend(model_backend):
                self._logger.error("Model backend failed security validation")
                return
        
        self.model_backend = model_backend
        self._logger.info(f"Model backend updated: {'Available' if model_backend else 'None'}")
    
    def is_model_available(self) -> bool:
        """
        Check if a GGUF model is currently available for processing.
        
        Returns:
            bool: True if model is available and ready, False otherwise
        """
        if self.model_backend is None:
            return False
        
        try:
            # Check if the model has the necessary methods for text generation
            return callable(self.model_backend) or hasattr(self.model_backend, 'create_completion')
        except Exception as e:
            self._logger.error(f"Error checking model availability: {e}")
            return False
    
    def summarize_text(self, text: str) -> ProcessingResult:
        """
        Generate a summary of the provided text.
        
        Args:
            text: Text to summarize
            
        Returns:
            ProcessingResult: Result containing summary or error information
        """
        return self._process_text(text, "summary", self.SUMMARIZE_PROMPT)
    
    def generate_comment(self, text: str) -> ProcessingResult:
        """
        Generate a friendly and insightful comment about the provided text.
        
        Args:
            text: Text to comment on
            
        Returns:
            ProcessingResult: Result containing comment or error information
        """
        return self._process_text(text, "comment", self.COMMENT_PROMPT)
    
    def _process_text(self, text: str, processing_type: str, prompt_template: str) -> ProcessingResult:
        """
        Internal method to process text with the GGUF model.
        
        Args:
            text: Text to process
            processing_type: Type of processing ('summary' or 'comment')
            prompt_template: Template for the prompt
            
        Returns:
            ProcessingResult: Result of the processing operation
        """
        start_time = time.time()
        
        try:
            # Performance optimization: validate and sanitize text
            validation_result = self._performance_optimizer.validate_text_for_processing(text)
            if not validation_result.is_valid:
                return ProcessingResult(
                    original_text=text,
                    processed_text="",
                    processing_type=processing_type,
                    success=False,
                    error_message=validation_result.errors[0] if validation_result.errors else "Invalid text",
                    processing_time=time.time() - start_time
                )
            
            # Use sanitized text for processing
            sanitized_text = validation_result.sanitized_text
            
            # Security validation for text processing
            if not self.privacy_security.validate_text_processing(sanitized_text, processing_type):
                return ProcessingResult(
                    original_text="",  # Don't store potentially unsafe text
                    processed_text="",
                    processing_type=processing_type,
                    success=False,
                    error_message="Text processing blocked for security reasons.",
                    processing_time=time.time() - start_time
                )
            
            # Legacy validation for backward compatibility
            validation_error = self._validate_input(sanitized_text)
            if validation_error:
                return ProcessingResult(
                    original_text=text,
                    processed_text="",
                    processing_type=processing_type,
                    success=False,
                    error_message=validation_error,
                    processing_time=time.time() - start_time
                )
            
            # Check model availability
            if not self.is_model_available():
                return ProcessingResult(
                    original_text=text,
                    processed_text="",
                    processing_type=processing_type,
                    success=False,
                    error_message="No GGUF model is currently loaded. Please load a model in the GGUF Loader application.",
                    processing_time=time.time() - start_time
                )
            
            # Prepare prompt with sanitized text
            prompt = prompt_template.format(text=sanitized_text.strip())
            self._logger.info(f"Processing {processing_type} for text length: {len(sanitized_text)}")
            
            # Generate response using GGUF model
            response = self._generate_with_model(prompt)
            
            if response is None:
                return ProcessingResult(
                    original_text=text,
                    processed_text="",
                    processing_type=processing_type,
                    success=False,
                    error_message="Model failed to generate a response. Please try again.",
                    processing_time=time.time() - start_time
                )
            
            # Clean and validate response
            processed_text = self._clean_response(response)
            
            result = ProcessingResult(
                original_text=text,
                processed_text=processed_text,
                processing_type=processing_type,
                success=True,
                error_message=None,
                processing_time=time.time() - start_time
            )
            
            # Track result for automatic cleanup
            self.privacy_security.track_data(result)
            
            self._logger.info(f"Successfully processed {processing_type} in {result.processing_time:.2f}s")
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error during {processing_type} processing: {str(e)}"
            self._logger.error(error_msg)
            
            return ProcessingResult(
                original_text=text,
                processed_text="",
                processing_type=processing_type,
                success=False,
                error_message=error_msg,
                processing_time=time.time() - start_time
            )
    
    def _validate_input(self, text: str) -> Optional[str]:
        """
        Validate input text for processing.
        
        Args:
            text: Text to validate
            
        Returns:
            Optional[str]: Error message if validation fails, None if valid
        """
        if not text or not text.strip():
            return "No text provided for processing."
        
        if len(text) > self.MAX_TEXT_LENGTH:
            return f"Text is too long ({len(text)} characters). Maximum allowed: {self.MAX_TEXT_LENGTH} characters."
        
        return None
    
    def _generate_with_model(self, prompt: str) -> Optional[str]:
        """
        Generate text using the GGUF model backend.
        
        Args:
            prompt: Formatted prompt for the model
            
        Returns:
            Optional[str]: Generated text or None if generation failed
        """
        try:
            # Handle different GGUF model interfaces
            if hasattr(self.model_backend, 'create_completion'):
                # llama-cpp-python style interface
                response = self.model_backend.create_completion(
                    prompt=prompt,
                    max_tokens=512,
                    temperature=0.7,
                    top_p=0.9,
                    stop=["\n\n", "Human:", "Assistant:"],
                    echo=False
                )
                
                if response and 'choices' in response and len(response['choices']) > 0:
                    return response['choices'][0]['text'].strip()
                    
            elif callable(self.model_backend):
                # Direct callable interface
                try:
                    response = self.model_backend(
                        prompt,
                        max_tokens=512,
                        temperature=0.7,
                        top_p=0.9,
                        stop=["\n\n", "Human:", "Assistant:"]
                    )
                except TypeError:
                    # Fallback for simpler callable interface
                    response = self.model_backend(prompt)
                
                if isinstance(response, str):
                    return response.strip()
                elif isinstance(response, dict) and 'text' in response:
                    return response['text'].strip()
            
            else:
                self._logger.error("Model backend does not have a recognized interface")
                return None
                
        except Exception as e:
            self._logger.error(f"Error generating text with model: {e}")
            return None
        
        return None
    
    def _clean_response(self, response: str) -> str:
        """
        Clean and format the model response.
        
        Args:
            response: Raw response from the model
            
        Returns:
            str: Cleaned response text
        """
        if not response:
            return ""
        
        # Remove common artifacts
        cleaned = response.strip()
        
        # Remove potential prompt echoes
        if cleaned.startswith("Summarize this clearly:"):
            cleaned = cleaned.replace("Summarize this clearly:", "", 1).strip()
        elif cleaned.startswith("Write a friendly and insightful comment about:"):
            cleaned = cleaned.replace("Write a friendly and insightful comment about:", "", 1).strip()
        
        # Remove excessive whitespace
        lines = [line.strip() for line in cleaned.split('\n')]
        cleaned = '\n'.join(line for line in lines if line)
        
        return cleaned
    
    def process_text_async(self, text: str, processing_type: str):
        """
        Process text asynchronously and emit signals when complete.
        
        Args:
            text: Text to process
            processing_type: Type of processing ('summary' or 'comment')
        """
        try:
            if processing_type == "summary":
                result = self.summarize_text(text)
            elif processing_type == "comment":
                result = self.generate_comment(text)
            else:
                result = ProcessingResult(
                    original_text=text,
                    processed_text="",
                    processing_type=processing_type,
                    success=False,
                    error_message=f"Unknown processing type: {processing_type}",
                    processing_time=0.0
                )
            
            if result.success:
                self.processing_completed.emit(result)
            else:
                self.processing_failed.emit(result.error_message)
                
        except Exception as e:
            error_msg = f"Async processing failed: {str(e)}"
            self._logger.error(error_msg)
            self.processing_failed.emit(error_msg)
    
    def retry_processing(self, text: str, processing_type: str) -> bool:
        """
        Retry a failed processing operation.
        
        Args:
            text: Text to process
            processing_type: Type of processing ('summary' or 'comment')
            
        Returns:
            bool: True if retry was initiated, False if max retries exceeded
        """
        operation_key = f"{processing_type}:{hash(text)}"
        current_attempts = self._retry_count.get(operation_key, 0)
        
        if current_attempts >= self.MAX_RETRY_ATTEMPTS:
            self._logger.warning(f"Max retry attempts ({self.MAX_RETRY_ATTEMPTS}) exceeded for {processing_type}")
            return False
        
        self._retry_count[operation_key] = current_attempts + 1
        self._logger.info(f"Retrying {processing_type} (attempt {current_attempts + 1}/{self.MAX_RETRY_ATTEMPTS})")
        
        # Store retry parameters
        self._retry_text = text
        self._retry_type = processing_type
        
        # Start retry timer
        self._retry_timer.start(int(self.RETRY_DELAY * 1000))
        return True
    
    def _execute_retry(self):
        """Execute the retry operation."""
        if hasattr(self, '_retry_text') and hasattr(self, '_retry_type'):
            self.process_text_async(self._retry_text, self._retry_type)
    
    def get_user_friendly_error(self, error_message: str) -> str:
        """
        Convert technical error messages to user-friendly ones.
        
        Args:
            error_message: Technical error message
            
        Returns:
            str: User-friendly error message
        """
        error_lower = error_message.lower()
        
        # Model availability errors
        if "no gguf model" in error_lower or "model is not loaded" in error_lower:
            return ("No AI model is currently loaded. Please load a model in the GGUF Loader "
                   "application before using text processing features.")
        
        # Model processing errors
        if "failed to generate" in error_lower or "model failed" in error_lower:
            return ("The AI model encountered an issue while processing your text. "
                   "This might be due to the text content or model state. Please try again.")
        
        # Timeout errors
        if "timeout" in error_lower or "took too long" in error_lower:
            return ("Text processing is taking longer than expected. The model might be "
                   "overloaded or the text might be too complex. Please try with shorter text.")
        
        # Text length errors
        if "too long" in error_lower or "maximum allowed" in error_lower:
            return ("The selected text is too long for processing. Please select a shorter "
                   "text segment (maximum 10,000 characters).")
        
        # Network/connection errors
        if "connection" in error_lower or "network" in error_lower:
            return ("There was a connection issue with the AI model. Please check that the "
                   "GGUF Loader application is running properly.")
        
        # Memory errors
        if "memory" in error_lower or "out of memory" in error_lower:
            return ("The system is running low on memory. Please close some applications "
                   "and try again, or try processing shorter text.")
        
        # Generic processing errors
        if "processing" in error_lower or "unexpected error" in error_lower:
            return ("An unexpected error occurred during text processing. Please try again. "
                   "If the problem persists, try restarting the GGUF Loader application.")
        
        # Default fallback
        return ("An error occurred while processing your text. Please try again or "
               "check that the GGUF Loader application is working properly.")
    
    def can_retry_error(self, error_message: str) -> bool:
        """
        Determine if an error is retryable.
        
        Args:
            error_message: Error message to check
            
        Returns:
            bool: True if the error can be retried, False otherwise
        """
        error_lower = error_message.lower()
        
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
        
        # Retryable errors
        retryable = [
            "failed to generate",
            "model failed",
            "timeout",
            "connection",
            "network",
            "processing",
            "unexpected error"
        ]
        
        for retryable_error in retryable:
            if retryable_error in error_lower:
                return True
        
        # Default to retryable for unknown errors
        return True
    
    def reset_retry_count(self, text: str, processing_type: str):
        """
        Reset retry count for a specific operation.
        
        Args:
            text: Text being processed
            processing_type: Type of processing
        """
        operation_key = f"{processing_type}:{hash(text)}"
        self._retry_count.pop(operation_key, None)
    
    def get_retry_count(self, text: str, processing_type: str) -> int:
        """
        Get current retry count for an operation.
        
        Args:
            text: Text being processed
            processing_type: Type of processing
            
        Returns:
            int: Current retry count
        """
        operation_key = f"{processing_type}:{hash(text)}"
        return self._retry_count.get(operation_key, 0)
    
    def _handle_performance_warning(self, warning_message: str):
        """Handle performance warnings from the optimizer."""
        self._logger.warning(f"Performance warning: {warning_message}")
        # Could emit a signal here to notify UI components if needed
    
    def cleanup(self):
        """Cleanup resources and disconnect from model backend."""
        self._logger.info("Cleaning up CommentEngine")
        self._retry_timer.stop()
        self._retry_count.clear()
        
        # Cleanup performance optimizer
        if hasattr(self, '_performance_optimizer'):
            self._performance_optimizer.cleanup()
            self._performance_optimizer = None
        
        # Cleanup privacy and security manager
        if hasattr(self, 'privacy_security'):
            self.privacy_security.cleanup()
        
        self.model_backend = None