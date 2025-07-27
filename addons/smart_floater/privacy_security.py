"""
Privacy and security measures for the Smart Floating Assistant addon.

This module implements privacy protection and security validation to ensure
all text processing remains local and no data is transmitted externally.
"""

import logging
import socket
import threading
import time
import weakref
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from PySide6.QtCore import QObject, Signal, QTimer

from .data_models import TextSelection, ProcessingResult


@dataclass
class SecurityViolation:
    """Represents a detected security violation."""
    violation_type: str
    description: str
    timestamp: datetime
    component: str
    severity: str  # 'low', 'medium', 'high', 'critical'


class NetworkMonitor(QObject):
    """Monitors for any network activity that could indicate data transmission."""
    
    # Signal emitted when network activity is detected
    network_activity_detected = Signal(str, str)  # destination, description
    
    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self._monitoring = False
        self._allowed_connections: Set[str] = set()
        self._blocked_connections: Set[str] = set()
        self._monitor_thread = None
        
    def start_monitoring(self):
        """Start monitoring network connections."""
        if self._monitoring:
            return
            
        self._monitoring = True
        self._logger.info("Starting network activity monitoring")
        
        # Start monitoring in a separate thread to avoid blocking UI
        self._monitor_thread = threading.Thread(target=self._monitor_connections, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring network connections."""
        self._monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
        self._logger.info("Stopped network activity monitoring")
    
    def _monitor_connections(self):
        """Monitor network connections in background thread."""
        while self._monitoring:
            try:
                # Check for any suspicious network activity
                # This is a simplified implementation - in production you'd use more sophisticated monitoring
                self._check_active_connections()
                time.sleep(1.0)  # Check every second
            except Exception as e:
                self._logger.error(f"Error monitoring network connections: {e}")
                time.sleep(5.0)  # Wait longer on error
    
    def _check_active_connections(self):
        """Check for active network connections that might indicate data transmission."""
        try:
            import psutil
            
            # Get current process connections
            current_process = psutil.Process()
            connections = current_process.connections(kind='inet')
            
            for conn in connections:
                if conn.status == psutil.CONN_ESTABLISHED:
                    remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "unknown"
                    
                    # Check if this is a suspicious connection
                    if self._is_suspicious_connection(conn):
                        self._logger.warning(f"Suspicious network connection detected: {remote_addr}")
                        self.network_activity_detected.emit(remote_addr, "Established connection")
                        
        except ImportError:
            # psutil not available, use basic socket monitoring
            self._basic_connection_check()
        except Exception as e:
            self._logger.debug(f"Connection check failed: {e}")
    
    def _basic_connection_check(self):
        """Basic connection checking without psutil."""
        # This is a fallback method - limited functionality
        # In practice, you'd implement platform-specific monitoring
        pass
    
    def _is_suspicious_connection(self, connection) -> bool:
        """Determine if a network connection is suspicious."""
        if not connection.raddr:
            return False
            
        remote_ip = connection.raddr.ip
        remote_port = connection.raddr.port
        
        # Allow local connections
        if remote_ip.startswith('127.') or remote_ip.startswith('::1'):
            return False
            
        # Allow private network ranges
        if (remote_ip.startswith('192.168.') or 
            remote_ip.startswith('10.') or 
            remote_ip.startswith('172.')):
            return False
            
        # Block common AI service ports and IPs
        suspicious_ports = {80, 443, 8080, 8443}  # HTTP/HTTPS ports
        if remote_port in suspicious_ports:
            return True
            
        return False


class DataCleanupManager(QObject):
    """Manages automatic cleanup of processed text data from memory."""
    
    # Signal emitted when cleanup is performed
    cleanup_performed = Signal(int)  # number of items cleaned
    
    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        
        # Storage for tracked data objects
        self._tracked_selections: List[weakref.ref] = []
        self._tracked_results: List[weakref.ref] = []
        self._tracked_strings: List[str] = []
        
        # Cleanup configuration
        self.cleanup_interval = 300  # 5 minutes
        self.max_data_age = 1800  # 30 minutes
        self.max_tracked_items = 100
        
        # Setup cleanup timer
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._perform_cleanup)
        self._cleanup_timer.start(self.cleanup_interval * 1000)  # Convert to milliseconds
        
    def track_text_selection(self, selection: TextSelection):
        """Track a text selection for automatic cleanup."""
        self._tracked_selections.append(weakref.ref(selection))
        self._logger.debug(f"Tracking text selection: {len(selection.content)} characters")
        
        # Immediate cleanup if too many items
        if len(self._tracked_selections) > self.max_tracked_items:
            self._perform_cleanup()
    
    def track_processing_result(self, result: ProcessingResult):
        """Track a processing result for automatic cleanup."""
        self._tracked_results.append(weakref.ref(result))
        self._logger.debug(f"Tracking processing result: {result.processing_type}")
        
        # Immediate cleanup if too many items
        if len(self._tracked_results) > self.max_tracked_items:
            self._perform_cleanup()
    
    def track_string_data(self, data: str):
        """Track string data for cleanup (for temporary strings)."""
        if data and len(data) > 10:  # Only track substantial strings
            self._tracked_strings.append(data)
            
            # Limit tracked strings to prevent memory issues
            if len(self._tracked_strings) > 50:
                self._tracked_strings = self._tracked_strings[-25:]  # Keep only recent half
    
    def _perform_cleanup(self):
        """Perform automatic cleanup of tracked data."""
        cleaned_count = 0
        current_time = datetime.now()
        
        # Clean up dead weak references
        self._tracked_selections = [ref for ref in self._tracked_selections if ref() is not None]
        self._tracked_results = [ref for ref in self._tracked_results if ref() is not None]
        
        # Clean up old selections
        valid_selections = []
        for ref in self._tracked_selections:
            selection = ref()
            if selection is not None:
                age = current_time - selection.timestamp
                if age.total_seconds() < self.max_data_age:
                    valid_selections.append(ref)
                else:
                    # Clear the selection content
                    try:
                        selection.content = ""
                        cleaned_count += 1
                    except Exception:
                        pass  # Object might be read-only or deleted
        self._tracked_selections = valid_selections
        
        # Clean up old results
        valid_results = []
        for ref in self._tracked_results:
            result = ref()
            if result is not None:
                # Results don't have timestamps, so we clean based on count
                valid_results.append(ref)
        
        # Keep only recent results
        if len(valid_results) > 20:
            for ref in valid_results[:-20]:  # Clean all but last 20
                result = ref()
                if result is not None:
                    try:
                        result.original_text = ""
                        result.processed_text = ""
                        cleaned_count += 1
                    except Exception:
                        pass
            self._tracked_results = valid_results[-20:]
        else:
            self._tracked_results = valid_results
        
        # Clean up tracked strings
        if len(self._tracked_strings) > 25:
            cleaned_count += len(self._tracked_strings) - 25
            self._tracked_strings = self._tracked_strings[-25:]
        
        if cleaned_count > 0:
            self._logger.info(f"Cleaned up {cleaned_count} data items from memory")
            self.cleanup_performed.emit(cleaned_count)
    
    def force_cleanup(self):
        """Force immediate cleanup of all tracked data."""
        self._logger.info("Performing forced cleanup of all tracked data")
        
        # Clear all selections
        for ref in self._tracked_selections:
            selection = ref()
            if selection is not None:
                try:
                    selection.content = ""
                except Exception:
                    pass
        
        # Clear all results
        for ref in self._tracked_results:
            result = ref()
            if result is not None:
                try:
                    result.original_text = ""
                    result.processed_text = ""
                except Exception:
                    pass
        
        # Clear tracked strings
        self._tracked_strings.clear()
        
        # Clear reference lists
        self._tracked_selections.clear()
        self._tracked_results.clear()
        
        self.cleanup_performed.emit(-1)  # -1 indicates forced cleanup
    
    def get_cleanup_stats(self) -> Dict[str, int]:
        """Get statistics about tracked data."""
        return {
            'tracked_selections': len(self._tracked_selections),
            'tracked_results': len(self._tracked_results),
            'tracked_strings': len(self._tracked_strings),
            'cleanup_interval': self.cleanup_interval,
            'max_data_age': self.max_data_age
        }
    
    def cleanup(self):
        """Cleanup the cleanup manager itself."""
        self._cleanup_timer.stop()
        self.force_cleanup()


class SecurityValidator(QObject):
    """Validates operations to ensure no data transmission to external services."""
    
    # Signal emitted when security violation is detected
    security_violation = Signal(SecurityViolation)
    
    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self._violations: List[SecurityViolation] = []
        
        # Security configuration
        self.strict_mode = True
        self.allowed_local_ips = {'127.0.0.1', '::1', 'localhost'}
        self.blocked_domains = {
            'openai.com', 'api.openai.com',
            'anthropic.com', 'api.anthropic.com',
            'cohere.ai', 'api.cohere.ai',
            'huggingface.co', 'api-inference.huggingface.co',
            'googleapis.com', 'api.googleapis.com'
        }
        
    def validate_model_backend(self, model_backend: Any) -> bool:
        """Validate that the model backend is local and safe."""
        if model_backend is None:
            return True  # No model is safe
            
        try:
            # Check if model has network-related attributes
            suspicious_attrs = ['api_key', 'endpoint', 'url', 'host', 'server']
            for attr in suspicious_attrs:
                if hasattr(model_backend, attr):
                    value = getattr(model_backend, attr)
                    if value and str(value).strip():
                        self._report_violation(
                            'model_validation',
                            f'Model backend has suspicious attribute: {attr}={value}',
                            'main',
                            'high'
                        )
                        return False
            
            # Check model type/class name for known remote model types
            model_type = type(model_backend).__name__.lower()
            remote_indicators = ['api', 'client', 'remote', 'http', 'rest', 'web']
            for indicator in remote_indicators:
                if indicator in model_type:
                    self._report_violation(
                        'model_validation',
                        f'Model backend type suggests remote access: {model_type}',
                        'main',
                        'medium'
                    )
                    return False
            
            self._logger.info(f"Model backend validation passed: {model_type}")
            return True
            
        except Exception as e:
            self._logger.error(f"Error validating model backend: {e}")
            return False
    
    def validate_text_processing(self, text: str, processing_type: str) -> bool:
        """Validate text processing request for security."""
        if not text or not text.strip():
            return True  # Empty text is safe
            
        # Check for suspicious content that might indicate data exfiltration attempts
        suspicious_patterns = [
            'http://', 'https://', 'ftp://',
            'api_key', 'token', 'password',
            'send_to', 'transmit', 'upload'
        ]
        
        text_lower = text.lower()
        for pattern in suspicious_patterns:
            if pattern in text_lower:
                self._report_violation(
                    'text_validation',
                    f'Text contains suspicious pattern: {pattern}',
                    'comment_engine',
                    'medium'
                )
                # Don't block processing, just log the violation
        
        # Check text length for potential abuse
        if len(text) > 50000:  # Very large text might be suspicious
            self._report_violation(
                'text_validation',
                f'Unusually large text for processing: {len(text)} characters',
                'comment_engine',
                'low'
            )
        
        return True
    
    def validate_network_operation(self, operation: str, destination: str) -> bool:
        """Validate network operations to prevent external data transmission."""
        if not destination:
            return True
            
        # Parse destination
        dest_lower = destination.lower()
        
        # Check against blocked domains
        for domain in self.blocked_domains:
            if domain in dest_lower:
                self._report_violation(
                    'network_validation',
                    f'Blocked network operation to: {destination}',
                    'network',
                    'critical'
                )
                return False
        
        # Check if destination is local
        is_local = any(local_ip in dest_lower for local_ip in self.allowed_local_ips)
        if not is_local and self.strict_mode:
            # In strict mode, only local connections are allowed
            self._report_violation(
                'network_validation',
                f'Non-local network operation blocked: {destination}',
                'network',
                'high'
            )
            return False
        
        return True
    
    def _report_violation(self, violation_type: str, description: str, 
                         component: str, severity: str):
        """Report a security violation."""
        violation = SecurityViolation(
            violation_type=violation_type,
            description=description,
            timestamp=datetime.now(),
            component=component,
            severity=severity
        )
        
        self._violations.append(violation)
        self._logger.warning(f"Security violation [{severity}]: {description}")
        self.security_violation.emit(violation)
        
        # Keep only recent violations to prevent memory issues
        if len(self._violations) > 100:
            self._violations = self._violations[-50:]
    
    def get_violations(self, severity_filter: Optional[str] = None) -> List[SecurityViolation]:
        """Get recorded security violations."""
        if severity_filter:
            return [v for v in self._violations if v.severity == severity_filter]
        return self._violations.copy()
    
    def clear_violations(self):
        """Clear recorded violations."""
        self._violations.clear()
        self._logger.info("Security violations cleared")


class PrivacySecurityManager(QObject):
    """Main manager for privacy and security measures."""
    
    # Signals
    security_status_changed = Signal(bool)  # True if secure, False if violations detected
    cleanup_completed = Signal(int)
    
    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        
        # Initialize components
        self.network_monitor = NetworkMonitor()
        self.data_cleanup = DataCleanupManager()
        self.security_validator = SecurityValidator()
        
        # Connect signals
        self.network_monitor.network_activity_detected.connect(self._handle_network_activity)
        self.data_cleanup.cleanup_performed.connect(self.cleanup_completed.emit)
        self.security_validator.security_violation.connect(self._handle_security_violation)
        
        # Security state
        self._is_secure = True
        self._last_violation_time = None
        
    def start_protection(self):
        """Start all privacy and security protection measures."""
        self._logger.info("Starting privacy and security protection")
        
        # Start network monitoring
        self.network_monitor.start_monitoring()
        
        # Data cleanup is started automatically in its constructor
        
        self._is_secure = True
        self.security_status_changed.emit(True)
    
    def stop_protection(self):
        """Stop all privacy and security protection measures."""
        self._logger.info("Stopping privacy and security protection")
        
        # Stop network monitoring
        self.network_monitor.stop_monitoring()
        
        # Perform final cleanup
        self.data_cleanup.force_cleanup()
    
    def validate_model_backend(self, model_backend: Any) -> bool:
        """Validate model backend for security."""
        return self.security_validator.validate_model_backend(model_backend)
    
    def validate_text_processing(self, text: str, processing_type: str) -> bool:
        """Validate text processing for security."""
        return self.security_validator.validate_text_processing(text, processing_type)
    
    def track_data(self, data: Any):
        """Track data for automatic cleanup."""
        if isinstance(data, TextSelection):
            self.data_cleanup.track_text_selection(data)
        elif isinstance(data, ProcessingResult):
            self.data_cleanup.track_processing_result(data)
        elif isinstance(data, str):
            self.data_cleanup.track_string_data(data)
    
    def _handle_network_activity(self, destination: str, description: str):
        """Handle detected network activity."""
        self._logger.warning(f"Network activity detected: {destination} - {description}")
        
        # Validate the network operation
        if not self.security_validator.validate_network_operation("connection", destination):
            self._is_secure = False
            self._last_violation_time = datetime.now()
            self.security_status_changed.emit(False)
    
    def _handle_security_violation(self, violation: SecurityViolation):
        """Handle security violations."""
        if violation.severity in ['high', 'critical']:
            self._is_secure = False
            self._last_violation_time = datetime.now()
            self.security_status_changed.emit(False)
    
    def is_secure(self) -> bool:
        """Check if the system is currently secure."""
        return self._is_secure
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get comprehensive security status."""
        violations = self.security_validator.get_violations()
        cleanup_stats = self.data_cleanup.get_cleanup_stats()
        
        return {
            'is_secure': self._is_secure,
            'last_violation_time': self._last_violation_time,
            'total_violations': len(violations),
            'critical_violations': len([v for v in violations if v.severity == 'critical']),
            'high_violations': len([v for v in violations if v.severity == 'high']),
            'cleanup_stats': cleanup_stats,
            'network_monitoring_active': self.network_monitor._monitoring
        }
    
    def cleanup(self):
        """Cleanup all privacy and security components."""
        self.stop_protection()
        self.data_cleanup.cleanup()