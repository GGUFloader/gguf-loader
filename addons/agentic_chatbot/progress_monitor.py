"""
Progress Monitor - Provides status indicators and interruption capability

This component handles:
- Progress tracking for long-running operations
- Status indicators and user feedback
- Interruption capability for running processes
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from PySide6.QtCore import QObject, Signal, QTimer


class ProgressStatus(Enum):
    """Progress status enumeration."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class ProgressInfo:
    """Information about a progress operation."""
    operation_id: str
    operation_name: str
    status: ProgressStatus
    current_step: int
    total_steps: int
    current_description: str
    started_at: datetime
    estimated_completion: Optional[datetime]
    metadata: Dict[str, Any]


class ProgressMonitor(QObject):
    """
    Monitors progress of long-running operations with interruption capability.
    
    This component:
    - Tracks progress of long-running operations
    - Provides status indicators and user feedback
    - Allows interruption of running processes
    - Estimates completion times and provides progress updates
    """
    
    # Signals
    progress_started = Signal(str, str)         # operation_id, operation_name
    progress_updated = Signal(str, int, int)    # operation_id, current, total
    progress_completed = Signal(str)            # operation_id
    progress_cancelled = Signal(str)            # operation_id
    progress_failed = Signal(str, str)          # operation_id, error_message
    step_completed = Signal(str, str)           # operation_id, step_description
    interruption_requested = Signal(str)       # operation_id
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the progress monitor.
        
        Args:
            config: Configuration dictionary for progress monitoring
        """
        super().__init__()
        
        self.config = config
        self._logger = logging.getLogger(__name__)
        
        # Progress settings
        self.update_interval = config.get("progress_update_interval", 1000)  # ms
        self.enable_estimation = config.get("enable_progress_estimation", True)
        self.max_operations = config.get("max_concurrent_operations", 10)
        
        # Active operations
        self._active_operations: Dict[str, ProgressInfo] = {}
        self._interruption_callbacks: Dict[str, Callable] = {}
        self._completion_callbacks: Dict[str, List[Callable]] = {}
        
        # Update timer
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_progress)
        self._update_timer.start(self.update_interval)
    
    def start_operation(self, operation_id: str, operation_name: str, 
                       total_steps: int, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Start tracking a new operation.
        
        Args:
            operation_id: Unique identifier for the operation
            operation_name: Human-readable name for the operation
            total_steps: Total number of steps in the operation
            metadata: Optional metadata for the operation
            
        Returns:
            bool: True if operation started successfully, False otherwise
        """
        try:
            if operation_id in self._active_operations:
                self._logger.warning(f"Operation {operation_id} is already active")
                return False
            
            if len(self._active_operations) >= self.max_operations:
                self._logger.warning("Maximum concurrent operations reached")
                return False
            
            # Create progress info
            progress_info = ProgressInfo(
                operation_id=operation_id,
                operation_name=operation_name,
                status=ProgressStatus.IN_PROGRESS,
                current_step=0,
                total_steps=total_steps,
                current_description="Starting...",
                started_at=datetime.now(),
                estimated_completion=None,
                metadata=metadata or {}
            )
            
            # Store operation
            self._active_operations[operation_id] = progress_info
            
            # Initialize callbacks
            self._completion_callbacks[operation_id] = []
            
            # Emit signal
            self.progress_started.emit(operation_id, operation_name)
            
            self._logger.info(f"Started tracking operation: {operation_id} ({operation_name})")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to start operation {operation_id}: {e}")
            return False
    
    def update_progress(self, operation_id: str, current_step: int, 
                       step_description: Optional[str] = None) -> bool:
        """
        Update progress for an operation.
        
        Args:
            operation_id: Operation identifier
            current_step: Current step number
            step_description: Optional description of current step
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            if operation_id not in self._active_operations:
                self._logger.warning(f"Operation {operation_id} not found")
                return False
            
            progress_info = self._active_operations[operation_id]
            
            # Update progress
            progress_info.current_step = current_step
            if step_description:
                progress_info.current_description = step_description
            
            # Update estimated completion if enabled
            if self.enable_estimation:
                self._update_estimated_completion(progress_info)
            
            # Emit signals
            self.progress_updated.emit(operation_id, current_step, progress_info.total_steps)
            if step_description:
                self.step_completed.emit(operation_id, step_description)
            
            self._logger.debug(f"Updated progress for {operation_id}: {current_step}/{progress_info.total_steps}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to update progress for {operation_id}: {e}")
            return False
    
    def complete_operation(self, operation_id: str, result_summary: Optional[str] = None) -> bool:
        """
        Mark an operation as completed.
        
        Args:
            operation_id: Operation identifier
            result_summary: Optional summary of operation results
            
        Returns:
            bool: True if completed successfully, False otherwise
        """
        try:
            if operation_id not in self._active_operations:
                self._logger.warning(f"Operation {operation_id} not found")
                return False
            
            progress_info = self._active_operations[operation_id]
            
            # Update status
            progress_info.status = ProgressStatus.COMPLETED
            progress_info.current_step = progress_info.total_steps
            progress_info.current_description = result_summary or "Completed"
            
            # Execute completion callbacks
            callbacks = self._completion_callbacks.get(operation_id, [])
            for callback in callbacks:
                try:
                    callback(operation_id, ProgressStatus.COMPLETED, result_summary)
                except Exception as e:
                    self._logger.warning(f"Completion callback error for {operation_id}: {e}")
            
            # Emit signal
            self.progress_completed.emit(operation_id)
            
            # Clean up
            self._cleanup_operation(operation_id)
            
            self._logger.info(f"Completed operation: {operation_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to complete operation {operation_id}: {e}")
            return False
    
    def cancel_operation(self, operation_id: str, reason: Optional[str] = None) -> bool:
        """
        Cancel an operation.
        
        Args:
            operation_id: Operation identifier
            reason: Optional cancellation reason
            
        Returns:
            bool: True if cancelled successfully, False otherwise
        """
        try:
            if operation_id not in self._active_operations:
                self._logger.warning(f"Operation {operation_id} not found")
                return False
            
            progress_info = self._active_operations[operation_id]
            
            # Update status
            progress_info.status = ProgressStatus.CANCELLED
            progress_info.current_description = reason or "Cancelled by user"
            
            # Execute interruption callback if available
            if operation_id in self._interruption_callbacks:
                try:
                    self._interruption_callbacks[operation_id]()
                except Exception as e:
                    self._logger.warning(f"Interruption callback error for {operation_id}: {e}")
            
            # Execute completion callbacks
            callbacks = self._completion_callbacks.get(operation_id, [])
            for callback in callbacks:
                try:
                    callback(operation_id, ProgressStatus.CANCELLED, reason)
                except Exception as e:
                    self._logger.warning(f"Completion callback error for {operation_id}: {e}")
            
            # Emit signals
            self.progress_cancelled.emit(operation_id)
            self.interruption_requested.emit(operation_id)
            
            # Clean up
            self._cleanup_operation(operation_id)
            
            self._logger.info(f"Cancelled operation: {operation_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to cancel operation {operation_id}: {e}")
            return False
    
    def fail_operation(self, operation_id: str, error_message: str) -> bool:
        """
        Mark an operation as failed.
        
        Args:
            operation_id: Operation identifier
            error_message: Error message describing the failure
            
        Returns:
            bool: True if marked as failed successfully, False otherwise
        """
        try:
            if operation_id not in self._active_operations:
                self._logger.warning(f"Operation {operation_id} not found")
                return False
            
            progress_info = self._active_operations[operation_id]
            
            # Update status
            progress_info.status = ProgressStatus.FAILED
            progress_info.current_description = f"Failed: {error_message}"
            
            # Execute completion callbacks
            callbacks = self._completion_callbacks.get(operation_id, [])
            for callback in callbacks:
                try:
                    callback(operation_id, ProgressStatus.FAILED, error_message)
                except Exception as e:
                    self._logger.warning(f"Completion callback error for {operation_id}: {e}")
            
            # Emit signal
            self.progress_failed.emit(operation_id, error_message)
            
            # Clean up
            self._cleanup_operation(operation_id)
            
            self._logger.info(f"Failed operation: {operation_id} - {error_message}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to mark operation {operation_id} as failed: {e}")
            return False
    
    def register_interruption_callback(self, operation_id: str, callback: Callable):
        """
        Register a callback for operation interruption.
        
        Args:
            operation_id: Operation identifier
            callback: Callback function to execute on interruption
        """
        self._interruption_callbacks[operation_id] = callback
        self._logger.debug(f"Registered interruption callback for {operation_id}")
    
    def register_completion_callback(self, operation_id: str, callback: Callable):
        """
        Register a callback for operation completion.
        
        Args:
            operation_id: Operation identifier
            callback: Callback function to execute on completion
        """
        if operation_id not in self._completion_callbacks:
            self._completion_callbacks[operation_id] = []
        
        self._completion_callbacks[operation_id].append(callback)
        self._logger.debug(f"Registered completion callback for {operation_id}")
    
    def get_operation_info(self, operation_id: str) -> Optional[ProgressInfo]:
        """
        Get information about an operation.
        
        Args:
            operation_id: Operation identifier
            
        Returns:
            Optional[ProgressInfo]: Operation information if found, None otherwise
        """
        return self._active_operations.get(operation_id)
    
    def get_active_operations(self) -> List[ProgressInfo]:
        """
        Get list of all active operations.
        
        Returns:
            List[ProgressInfo]: List of active operations
        """
        return list(self._active_operations.values())
    
    def is_operation_active(self, operation_id: str) -> bool:
        """
        Check if an operation is currently active.
        
        Args:
            operation_id: Operation identifier
            
        Returns:
            bool: True if operation is active, False otherwise
        """
        return operation_id in self._active_operations
    
    def _update_estimated_completion(self, progress_info: ProgressInfo):
        """
        Update estimated completion time for an operation.
        
        Args:
            progress_info: Progress information to update
        """
        try:
            if progress_info.current_step <= 0 or progress_info.total_steps <= 0:
                return
            
            # Calculate elapsed time
            elapsed = datetime.now() - progress_info.started_at
            elapsed_seconds = elapsed.total_seconds()
            
            if elapsed_seconds <= 0:
                return
            
            # Calculate average time per step
            avg_time_per_step = elapsed_seconds / progress_info.current_step
            
            # Estimate remaining time
            remaining_steps = progress_info.total_steps - progress_info.current_step
            estimated_remaining_seconds = remaining_steps * avg_time_per_step
            
            # Update estimated completion
            progress_info.estimated_completion = datetime.now() + timedelta(seconds=estimated_remaining_seconds)
            
        except Exception as e:
            self._logger.warning(f"Error updating estimated completion: {e}")
    
    def _update_progress(self):
        """Periodic progress update (called by timer)."""
        try:
            # Clean up completed operations that are too old
            current_time = datetime.now()
            operations_to_cleanup = []
            
            for operation_id, progress_info in self._active_operations.items():
                # Clean up operations that have been completed for more than 5 minutes
                if (progress_info.status in [ProgressStatus.COMPLETED, ProgressStatus.CANCELLED, ProgressStatus.FAILED] and
                    (current_time - progress_info.started_at).total_seconds() > 300):
                    operations_to_cleanup.append(operation_id)
            
            for operation_id in operations_to_cleanup:
                self._cleanup_operation(operation_id)
                
        except Exception as e:
            self._logger.error(f"Error in progress update: {e}")
    
    def _cleanup_operation(self, operation_id: str):
        """
        Clean up resources for an operation.
        
        Args:
            operation_id: Operation identifier to clean up
        """
        try:
            # Remove from active operations
            if operation_id in self._active_operations:
                del self._active_operations[operation_id]
            
            # Remove callbacks
            if operation_id in self._interruption_callbacks:
                del self._interruption_callbacks[operation_id]
            
            if operation_id in self._completion_callbacks:
                del self._completion_callbacks[operation_id]
            
            self._logger.debug(f"Cleaned up operation: {operation_id}")
            
        except Exception as e:
            self._logger.error(f"Error cleaning up operation {operation_id}: {e}")
    
    def get_progress_stats(self) -> Dict[str, Any]:
        """
        Get progress monitoring statistics.
        
        Returns:
            Dict containing progress statistics
        """
        active_count = len(self._active_operations)
        status_counts = {}
        
        for progress_info in self._active_operations.values():
            status = progress_info.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "active_operations": active_count,
            "max_operations": self.max_operations,
            "status_counts": status_counts,
            "update_interval": self.update_interval,
            "estimation_enabled": self.enable_estimation
        }