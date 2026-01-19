"""
Performance optimization and edge case handling for the Smart Floating Assistant addon.

This module provides text length validation, memory management, UI responsiveness optimization,
and special character handling to ensure robust operation under various conditions.
"""

import gc
import sys
import time
import logging
import threading
import unicodedata
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal, QTimer, QThread, QMutex, QMutexLocker
from PySide6.QtWidgets import QApplication


@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring system health."""
    memory_usage_mb: float
    processing_time_ms: float
    ui_response_time_ms: float
    text_length: int
    widget_count: int
    thread_count: int
    timestamp: float


@dataclass
class TextValidationResult:
    """Result of text validation including sanitization."""
    is_valid: bool
    sanitized_text: str
    original_length: int
    sanitized_length: int
    warnings: List[str]
    errors: List[str]


class TextValidator:
    """Handles text validation, sanitization, and length limits."""
    
    # Constants
    MAX_TEXT_LENGTH = 10000
    MAX_LINE_LENGTH = 1000
    MAX_LINES = 500
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_and_sanitize(self, text: str) -> TextValidationResult:
        """
        Validate and sanitize input text for processing.
        
        Args:
            text: Raw input text to validate
            
        Returns:
            TextValidationResult: Validation result with sanitized text
        """
        if not text:
            return TextValidationResult(
                is_valid=False,
                sanitized_text="",
                original_length=0,
                sanitized_length=0,
                warnings=[],
                errors=["No text provided"]
            )
        
        original_length = len(text)
        warnings = []
        errors = []
        
        # Check text length limit
        if original_length > self.MAX_TEXT_LENGTH:
            errors.append(
                f"Text is too long ({original_length:,} characters). "
                f"Maximum allowed: {self.MAX_TEXT_LENGTH:,} characters."
            )
            return TextValidationResult(
                is_valid=False,
                sanitized_text="",
                original_length=original_length,
                sanitized_length=0,
                warnings=warnings,
                errors=errors
            )
        
        # Sanitize text
        sanitized_text = self._sanitize_text(text, warnings)
        sanitized_length = len(sanitized_text)
        
        # Check line limits
        lines = sanitized_text.split('\n')
        if len(lines) > self.MAX_LINES:
            warnings.append(f"Text has many lines ({len(lines)}). Processing may be slower.")
        
        # Check for very long lines
        long_lines = [i for i, line in enumerate(lines) if len(line) > self.MAX_LINE_LENGTH]
        if long_lines:
            warnings.append(f"Found {len(long_lines)} very long lines. This may affect processing.")
        
        # Final validation
        is_valid = len(errors) == 0 and sanitized_length > 0
        
        return TextValidationResult(
            is_valid=is_valid,
            sanitized_text=sanitized_text,
            original_length=original_length,
            sanitized_length=sanitized_length,
            warnings=warnings,
            errors=errors
        )
    
    def _sanitize_text(self, text: str, warnings: List[str]) -> str:
        """
        Sanitize text by handling special characters and encoding issues.
        
        Args:
            text: Raw text to sanitize
            warnings: List to append warnings to
            
        Returns:
            str: Sanitized text
        """
        try:
            # Normalize Unicode characters
            normalized = unicodedata.normalize('NFKC', text)
            
            # Remove or replace problematic characters
            sanitized = self._handle_special_characters(normalized, warnings)
            
            # Clean up whitespace
            sanitized = self._clean_whitespace(sanitized)
            
            return sanitized
            
        except Exception as e:
            self.logger.error(f"Error sanitizing text: {e}")
            warnings.append("Text sanitization encountered issues")
            return text  # Return original if sanitization fails
    
    def _handle_special_characters(self, text: str, warnings: List[str]) -> str:
        """Handle special characters that might cause issues."""
        # Characters to remove (control characters except common ones)
        control_chars = []
        replacement_count = 0
        
        result = []
        for char in text:
            # Keep common whitespace characters
            if char in '\n\r\t ':
                result.append(char)
                continue
            
            # Check for control characters
            if unicodedata.category(char).startswith('C'):
                if char not in '\n\r\t':  # Already handled above
                    control_chars.append(char)
                    replacement_count += 1
                    continue
            
            # Handle zero-width characters
            if unicodedata.category(char) in ['Mn', 'Me', 'Cf']:
                if ord(char) in [0x200B, 0x200C, 0x200D, 0xFEFF]:  # Zero-width chars
                    replacement_count += 1
                    continue
            
            result.append(char)
        
        if replacement_count > 0:
            warnings.append(f"Removed {replacement_count} problematic characters")
        
        return ''.join(result)
    
    def _clean_whitespace(self, text: str) -> str:
        """Clean up excessive whitespace while preserving structure."""
        # Replace multiple spaces with single space (except at line start for indentation)
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Preserve leading whitespace but clean up the rest
            stripped = line.lstrip()
            if stripped:
                leading_whitespace = line[:len(line) - len(stripped)]
                # Clean up multiple spaces in the content
                cleaned_content = ' '.join(stripped.split())
                cleaned_lines.append(leading_whitespace + cleaned_content)
            else:
                # Keep empty lines but normalize them
                cleaned_lines.append('')
        
        # Remove excessive empty lines (more than 1 consecutive)
        result_lines = []
        empty_count = 0
        
        for line in cleaned_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 1:  # Allow up to 1 consecutive empty line
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)
        
        return '\n'.join(result_lines).strip()
    
    def get_text_statistics(self, text: str) -> Dict[str, Any]:
        """Get detailed statistics about text for performance planning."""
        if not text:
            return {'length': 0, 'lines': 0, 'words': 0, 'complexity': 'empty'}
        
        lines = text.split('\n')
        words = text.split()
        
        # Calculate complexity score
        complexity_score = 0
        complexity_score += len(text) / 1000  # Length factor
        complexity_score += len(lines) / 100   # Line count factor
        complexity_score += len([c for c in text if not c.isascii()]) / 100  # Unicode factor
        
        if complexity_score < 1:
            complexity = 'low'
        elif complexity_score < 5:
            complexity = 'medium'
        else:
            complexity = 'high'
        
        return {
            'length': len(text),
            'lines': len(lines),
            'words': len(words),
            'avg_line_length': sum(len(line) for line in lines) / len(lines) if lines else 0,
            'max_line_length': max(len(line) for line in lines) if lines else 0,
            'unicode_chars': len([c for c in text if not c.isascii()]),
            'complexity': complexity,
            'complexity_score': complexity_score
        }


class MemoryManager:
    """Manages memory usage and prevents memory leaks."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._tracked_objects = set()
        self._cleanup_callbacks = []
        self._memory_threshold_mb = 100  # MB
        
    def track_object(self, obj: Any, cleanup_callback: Optional[callable] = None):
        """Track an object for memory management."""
        self._tracked_objects.add(id(obj))
        if cleanup_callback:
            self._cleanup_callbacks.append((id(obj), cleanup_callback))
    
    def untrack_object(self, obj: Any):
        """Stop tracking an object."""
        obj_id = id(obj)
        self._tracked_objects.discard(obj_id)
        self._cleanup_callbacks = [(oid, cb) for oid, cb in self._cleanup_callbacks if oid != obj_id]
    
    def cleanup_tracked_objects(self):
        """Cleanup all tracked objects."""
        for obj_id, cleanup_callback in self._cleanup_callbacks:
            try:
                cleanup_callback()
            except Exception as e:
                self.logger.error(f"Error in cleanup callback: {e}")
        
        self._tracked_objects.clear()
        self._cleanup_callbacks.clear()
        
        # Force garbage collection
        gc.collect()
    
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except ImportError:
            # Fallback method using sys
            return sys.getsizeof(gc.get_objects()) / 1024 / 1024
        except Exception as e:
            self.logger.error(f"Error getting memory usage: {e}")
            return 0.0
    
    def check_memory_threshold(self) -> bool:
        """Check if memory usage exceeds threshold."""
        current_usage = self.get_memory_usage()
        return current_usage > self._memory_threshold_mb
    
    def force_cleanup(self):
        """Force memory cleanup when threshold is exceeded."""
        self.logger.info("Forcing memory cleanup due to high usage")
        self.cleanup_tracked_objects()
        
        # Additional cleanup
        if hasattr(gc, 'set_debug'):
            gc.set_debug(0)  # Disable debug mode to reduce memory
        
        # Multiple garbage collection passes
        for _ in range(3):
            gc.collect()


class UIResponsivenessOptimizer:
    """Optimizes UI responsiveness during processing operations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._processing_thread = None
        self._processing_mutex = QMutex()
        self._is_processing = False
        
    def process_async(self, processing_func: callable, *args, **kwargs) -> QThread:
        """
        Execute processing function asynchronously to maintain UI responsiveness.
        
        Args:
            processing_func: Function to execute
            *args, **kwargs: Arguments for the function
            
        Returns:
            QThread: Thread handling the processing
        """
        with QMutexLocker(self._processing_mutex):
            if self._is_processing:
                self.logger.warning("Processing already in progress")
                return None
            
            self._is_processing = True
        
        # Create worker thread
        worker_thread = ProcessingWorkerThread(processing_func, *args, **kwargs)
        worker_thread.finished.connect(self._on_processing_finished)
        worker_thread.start()
        
        self._processing_thread = worker_thread
        return worker_thread
    
    def _on_processing_finished(self):
        """Handle processing completion."""
        with QMutexLocker(self._processing_mutex):
            self._is_processing = False
            if self._processing_thread:
                self._processing_thread.deleteLater()
                self._processing_thread = None
    
    def is_processing(self) -> bool:
        """Check if processing is currently active."""
        with QMutexLocker(self._processing_mutex):
            return self._is_processing
    
    def cancel_processing(self):
        """Cancel current processing if active."""
        with QMutexLocker(self._processing_mutex):
            if self._processing_thread and self._processing_thread.isRunning():
                self._processing_thread.requestInterruption()
                self._processing_thread.wait(5000)  # Wait up to 5 seconds
                self._is_processing = False


class ProcessingWorkerThread(QThread):
    """Worker thread for async processing operations."""
    
    result_ready = Signal(object)
    error_occurred = Signal(str)
    
    def __init__(self, processing_func: callable, *args, **kwargs):
        super().__init__()
        self.processing_func = processing_func
        self.args = args
        self.kwargs = kwargs
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """Execute the processing function."""
        try:
            result = self.processing_func(*self.args, **self.kwargs)
            if not self.isInterruptionRequested():
                self.result_ready.emit(result)
        except Exception as e:
            self.logger.error(f"Processing error in worker thread: {e}")
            if not self.isInterruptionRequested():
                self.error_occurred.emit(str(e))


class PerformanceMonitor(QObject):
    """Monitors system performance and provides metrics."""
    
    # Signals
    performance_warning = Signal(str)
    memory_threshold_exceeded = Signal(float)
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._metrics_history = []
        self._monitoring_timer = QTimer()
        self._monitoring_timer.timeout.connect(self._collect_metrics)
        self._memory_manager = MemoryManager()
        
    def start_monitoring(self, interval_ms: int = 5000):
        """Start performance monitoring."""
        self._monitoring_timer.start(interval_ms)
        self.logger.info(f"Performance monitoring started (interval: {interval_ms}ms)")
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        self._monitoring_timer.stop()
        self.logger.info("Performance monitoring stopped")
    
    def _collect_metrics(self):
        """Collect current performance metrics."""
        try:
            app = QApplication.instance()
            if not app:
                return
            
            # Collect metrics
            memory_usage = self._memory_manager.get_memory_usage()
            widget_count = len(app.allWidgets())
            thread_count = threading.active_count()
            
            metrics = PerformanceMetrics(
                memory_usage_mb=memory_usage,
                processing_time_ms=0,  # Will be updated during processing
                ui_response_time_ms=0,  # Will be updated during UI operations
                text_length=0,  # Will be updated during text processing
                widget_count=widget_count,
                thread_count=thread_count,
                timestamp=time.time()
            )
            
            # Add to history
            self._metrics_history.append(metrics)
            
            # Keep only last 100 metrics
            if len(self._metrics_history) > 100:
                self._metrics_history = self._metrics_history[-100:]
            
            # Check for performance issues
            self._check_performance_warnings(metrics)
            
        except Exception as e:
            self.logger.error(f"Error collecting performance metrics: {e}")
    
    def _check_performance_warnings(self, metrics: PerformanceMetrics):
        """Check for performance issues and emit warnings."""
        # Memory usage warning
        if metrics.memory_usage_mb > 100:
            self.memory_threshold_exceeded.emit(metrics.memory_usage_mb)
        
        # Widget count warning
        if metrics.widget_count > 50:
            self.performance_warning.emit(
                f"High widget count detected: {metrics.widget_count}. "
                "This may indicate memory leaks."
            )
        
        # Thread count warning
        if metrics.thread_count > 10:
            self.performance_warning.emit(
                f"High thread count detected: {metrics.thread_count}. "
                "This may affect performance."
            )
    
    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """Get the most recent performance metrics."""
        return self._metrics_history[-1] if self._metrics_history else None
    
    def get_metrics_history(self) -> List[PerformanceMetrics]:
        """Get performance metrics history."""
        return self._metrics_history.copy()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of performance metrics."""
        if not self._metrics_history:
            return {'status': 'no_data'}
        
        recent_metrics = self._metrics_history[-10:]  # Last 10 measurements
        
        avg_memory = sum(m.memory_usage_mb for m in recent_metrics) / len(recent_metrics)
        max_memory = max(m.memory_usage_mb for m in recent_metrics)
        avg_widgets = sum(m.widget_count for m in recent_metrics) / len(recent_metrics)
        avg_threads = sum(m.thread_count for m in recent_metrics) / len(recent_metrics)
        
        return {
            'status': 'active',
            'avg_memory_mb': avg_memory,
            'max_memory_mb': max_memory,
            'avg_widget_count': avg_widgets,
            'avg_thread_count': avg_threads,
            'total_measurements': len(self._metrics_history),
            'monitoring_duration_minutes': (
                (self._metrics_history[-1].timestamp - self._metrics_history[0].timestamp) / 60
                if len(self._metrics_history) > 1 else 0
            )
        }
    
    def cleanup(self):
        """Cleanup monitoring resources."""
        self.stop_monitoring()
        self._memory_manager.cleanup_tracked_objects()
        self._metrics_history.clear()


class PerformanceOptimizer(QObject):
    """Main performance optimization coordinator."""
    
    # Signals
    optimization_applied = Signal(str)
    warning_issued = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.text_validator = TextValidator()
        self.memory_manager = MemoryManager()
        self.ui_optimizer = UIResponsivenessOptimizer()
        self.performance_monitor = PerformanceMonitor()
        
        # Connect signals
        self.performance_monitor.performance_warning.connect(self.warning_issued.emit)
        self.performance_monitor.memory_threshold_exceeded.connect(self._handle_memory_threshold)
    
    def start_optimization(self):
        """Start performance optimization systems."""
        self.performance_monitor.start_monitoring()
        self.logger.info("Performance optimization started")
    
    def stop_optimization(self):
        """Stop performance optimization systems."""
        self.performance_monitor.stop_monitoring()
        self.logger.info("Performance optimization stopped")
    
    def validate_text_for_processing(self, text: str) -> TextValidationResult:
        """Validate text before processing with performance considerations."""
        result = self.text_validator.validate_and_sanitize(text)
        
        if result.warnings:
            for warning in result.warnings:
                self.warning_issued.emit(warning)
        
        return result
    
    def optimize_processing(self, processing_func: callable, text: str, *args, **kwargs):
        """Optimize text processing for performance and responsiveness."""
        # Validate text first
        validation_result = self.validate_text_for_processing(text)
        if not validation_result.is_valid:
            raise ValueError(validation_result.errors[0] if validation_result.errors else "Invalid text")
        
        # Use sanitized text
        sanitized_text = validation_result.sanitized_text
        
        # Process asynchronously for UI responsiveness
        try:
            worker_thread = self.ui_optimizer.process_async(
                processing_func, sanitized_text, *args, **kwargs
            )
            return worker_thread
        except Exception as e:
            self.logger.error(f"Error in optimize_processing: {e}")
            # Fallback to synchronous processing
            return processing_func(sanitized_text, *args, **kwargs)
    
    def _handle_memory_threshold(self, memory_usage_mb: float):
        """Handle memory threshold exceeded."""
        self.warning_issued.emit(
            f"High memory usage detected: {memory_usage_mb:.1f}MB. "
            "Performing cleanup..."
        )
        
        # Force memory cleanup
        self.memory_manager.force_cleanup()
        self.optimization_applied.emit("Memory cleanup performed")
    
    def cleanup_widgets(self, widget_list: List[Any]):
        """Cleanup widgets to prevent memory leaks."""
        cleanup_count = 0
        
        for widget in widget_list:
            try:
                if hasattr(widget, 'close'):
                    widget.close()
                if hasattr(widget, 'deleteLater'):
                    widget.deleteLater()
                cleanup_count += 1
            except Exception as e:
                self.logger.error(f"Error cleaning up widget: {e}")
        
        if cleanup_count > 0:
            self.optimization_applied.emit(f"Cleaned up {cleanup_count} widgets")
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status."""
        return {
            'text_validator': {
                'max_length': self.text_validator.MAX_TEXT_LENGTH,
                'max_lines': self.text_validator.MAX_LINES
            },
            'memory_manager': {
                'current_usage_mb': self.memory_manager.get_memory_usage(),
                'threshold_mb': self.memory_manager._memory_threshold_mb,
                'tracked_objects': len(self.memory_manager._tracked_objects)
            },
            'ui_optimizer': {
                'is_processing': self.ui_optimizer.is_processing()
            },
            'performance_monitor': self.performance_monitor.get_performance_summary()
        }
    
    def cleanup(self):
        """Cleanup all optimization resources."""
        self.stop_optimization()
        self.memory_manager.cleanup_tracked_objects()
        self.performance_monitor.cleanup()
        self.logger.info("Performance optimizer cleaned up")