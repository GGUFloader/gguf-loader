"""
Event System - Provides callbacks for tool calls, errors, and completions

This component handles:
- Event registration and callback management
- Event emission and propagation
- Asynchronous event handling and queuing
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal, QTimer


class EventType(Enum):
    """Event type enumeration."""
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_CALL_FAILED = "tool_call_failed"
    AGENT_TURN_STARTED = "agent_turn_started"
    AGENT_TURN_COMPLETED = "agent_turn_completed"
    AGENT_TURN_FAILED = "agent_turn_failed"
    ERROR_OCCURRED = "error_occurred"
    WARNING_ISSUED = "warning_issued"
    PROGRESS_UPDATED = "progress_updated"
    SAFETY_VIOLATION = "safety_violation"
    MEMORY_UPDATED = "memory_updated"
    CONTEXT_UPDATED = "context_updated"
    STREAMING_STARTED = "streaming_started"
    STREAMING_FINISHED = "streaming_finished"
    CUSTOM_EVENT = "custom_event"


@dataclass
class Event:
    """Represents an event in the system."""
    event_id: str
    event_type: EventType
    timestamp: datetime
    source: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    priority: int = 0  # Higher numbers = higher priority


class EventSystem(QObject):
    """
    Manages event registration, emission, and callback execution.
    
    This component:
    - Provides event registration and callback management
    - Handles event emission and propagation
    - Supports both synchronous and asynchronous event handling
    - Manages event queuing and priority processing
    """
    
    # Qt Signals for integration with UI
    event_emitted = Signal(dict)        # event_data
    callback_executed = Signal(str)     # callback_id
    callback_failed = Signal(str, str)  # callback_id, error_message
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the event system.
        
        Args:
            config: Configuration dictionary for event system
        """
        super().__init__()
        
        self.config = config
        self._logger = logging.getLogger(__name__)
        
        # Event system settings
        self.enable_async_callbacks = config.get("enable_async_callbacks", True)
        self.max_callback_timeout = config.get("max_callback_timeout", 30)  # seconds
        self.max_event_queue_size = config.get("max_event_queue_size", 1000)
        self.enable_event_logging = config.get("enable_event_logging", True)
        
        # Event storage and management
        self._event_callbacks: Dict[EventType, List[Dict[str, Any]]] = {}
        self._event_queue: List[Event] = []
        self._event_history: List[Event] = []
        self._callback_registry: Dict[str, Dict[str, Any]] = {}
        
        # Async processing
        self._thread_pool = ThreadPoolExecutor(max_workers=4)
        self._processing_queue = False
        
        # Queue processing timer
        self._queue_timer = QTimer()
        self._queue_timer.timeout.connect(self._process_event_queue)
        self._queue_timer.start(100)  # Process queue every 100ms
        
        # Initialize default event types
        for event_type in EventType:
            self._event_callbacks[event_type] = []
    
    def register_callback(self, event_type: Union[EventType, str], callback: Callable,
                         callback_id: Optional[str] = None, priority: int = 0,
                         async_execution: bool = False) -> str:
        """
        Register a callback for an event type.
        
        Args:
            event_type: Type of event to listen for
            callback: Callback function to execute
            callback_id: Optional unique identifier for the callback
            priority: Callback priority (higher numbers execute first)
            async_execution: Whether to execute callback asynchronously
            
        Returns:
            str: Callback ID for management
        """
        try:
            # Convert string to EventType if needed
            if isinstance(event_type, str):
                event_type = EventType(event_type)
            
            # Generate callback ID if not provided
            if not callback_id:
                callback_id = f"callback_{int(datetime.now().timestamp())}_{id(callback)}"
            
            # Create callback info
            callback_info = {
                "callback_id": callback_id,
                "callback": callback,
                "priority": priority,
                "async_execution": async_execution,
                "registered_at": datetime.now(),
                "execution_count": 0,
                "last_executed": None,
                "last_error": None
            }
            
            # Register callback
            self._event_callbacks[event_type].append(callback_info)
            self._callback_registry[callback_id] = callback_info
            
            # Sort callbacks by priority
            self._event_callbacks[event_type].sort(key=lambda x: x["priority"], reverse=True)
            
            self._logger.debug(f"Registered callback {callback_id} for event {event_type.value}")
            return callback_id
            
        except Exception as e:
            self._logger.error(f"Error registering callback: {e}")
            return ""
    
    def unregister_callback(self, callback_id: str) -> bool:
        """
        Unregister a callback.
        
        Args:
            callback_id: ID of the callback to unregister
            
        Returns:
            bool: True if unregistered successfully, False otherwise
        """
        try:
            if callback_id not in self._callback_registry:
                self._logger.warning(f"Callback {callback_id} not found")
                return False
            
            # Remove from callback registry
            callback_info = self._callback_registry[callback_id]
            del self._callback_registry[callback_id]
            
            # Remove from event callbacks
            for event_type, callbacks in self._event_callbacks.items():
                self._event_callbacks[event_type] = [
                    cb for cb in callbacks if cb["callback_id"] != callback_id
                ]
            
            self._logger.debug(f"Unregistered callback {callback_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"Error unregistering callback {callback_id}: {e}")
            return False
    
    def emit_event(self, event_type: Union[EventType, str], source: str,
                  data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None,
                  priority: int = 0, immediate: bool = False) -> str:
        """
        Emit an event.
        
        Args:
            event_type: Type of event to emit
            source: Source component that emitted the event
            data: Event data
            metadata: Optional event metadata
            priority: Event priority for queue processing
            immediate: Whether to process immediately (bypass queue)
            
        Returns:
            str: Event ID
        """
        try:
            # Convert string to EventType if needed
            if isinstance(event_type, str):
                if event_type in [et.value for et in EventType]:
                    event_type = EventType(event_type)
                else:
                    event_type = EventType.CUSTOM_EVENT
                    if not metadata:
                        metadata = {}
                    metadata["original_event_type"] = event_type
            
            # Create event
            event_id = f"event_{int(datetime.now().timestamp())}_{id(data)}"
            event = Event(
                event_id=event_id,
                event_type=event_type,
                timestamp=datetime.now(),
                source=source,
                data=data,
                metadata=metadata or {},
                priority=priority
            )
            
            # Log event if enabled
            if self.enable_event_logging:
                self._log_event(event)
            
            # Add to history
            self._event_history.append(event)
            
            # Keep history size manageable
            if len(self._event_history) > 1000:
                self._event_history = self._event_history[-1000:]
            
            # Emit Qt signal
            self.event_emitted.emit({
                "event_id": event_id,
                "event_type": event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "source": source,
                "data": data,
                "metadata": metadata or {}
            })
            
            if immediate:
                # Process immediately
                self._process_event(event)
            else:
                # Add to queue
                self._add_to_queue(event)
            
            return event_id
            
        except Exception as e:
            self._logger.error(f"Error emitting event: {e}")
            return ""
    
    def _add_to_queue(self, event: Event):
        """
        Add event to processing queue.
        
        Args:
            event: Event to add to queue
        """
        try:
            # Check queue size limit
            if len(self._event_queue) >= self.max_event_queue_size:
                # Remove oldest low-priority event
                self._event_queue.sort(key=lambda x: (x.priority, x.timestamp))
                self._event_queue.pop(0)
                self._logger.warning("Event queue full, removed oldest low-priority event")
            
            # Add event to queue
            self._event_queue.append(event)
            
            # Sort queue by priority and timestamp
            self._event_queue.sort(key=lambda x: (x.priority, x.timestamp), reverse=True)
            
        except Exception as e:
            self._logger.error(f"Error adding event to queue: {e}")
    
    def _process_event_queue(self):
        """Process events from the queue (called by timer)."""
        try:
            if self._processing_queue or not self._event_queue:
                return
            
            self._processing_queue = True
            
            # Process up to 5 events per timer tick
            events_to_process = self._event_queue[:5]
            self._event_queue = self._event_queue[5:]
            
            for event in events_to_process:
                self._process_event(event)
            
        except Exception as e:
            self._logger.error(f"Error processing event queue: {e}")
        finally:
            self._processing_queue = False
    
    def _process_event(self, event: Event):
        """
        Process a single event by executing callbacks.
        
        Args:
            event: Event to process
        """
        try:
            callbacks = self._event_callbacks.get(event.event_type, [])
            
            if not callbacks:
                return
            
            self._logger.debug(f"Processing event {event.event_id} with {len(callbacks)} callbacks")
            
            for callback_info in callbacks:
                try:
                    if callback_info["async_execution"] and self.enable_async_callbacks:
                        # Execute asynchronously
                        self._thread_pool.submit(self._execute_callback, callback_info, event)
                    else:
                        # Execute synchronously
                        self._execute_callback(callback_info, event)
                        
                except Exception as e:
                    self._logger.error(f"Error scheduling callback {callback_info['callback_id']}: {e}")
                    self.callback_failed.emit(callback_info["callback_id"], str(e))
            
        except Exception as e:
            self._logger.error(f"Error processing event {event.event_id}: {e}")
    
    def _execute_callback(self, callback_info: Dict[str, Any], event: Event):
        """
        Execute a callback function.
        
        Args:
            callback_info: Callback information
            event: Event to pass to callback
        """
        try:
            callback_id = callback_info["callback_id"]
            callback = callback_info["callback"]
            
            # Update execution info
            callback_info["execution_count"] += 1
            callback_info["last_executed"] = datetime.now()
            
            # Execute callback
            callback(event)
            
            # Emit success signal
            self.callback_executed.emit(callback_id)
            
            self._logger.debug(f"Executed callback {callback_id} for event {event.event_id}")
            
        except Exception as e:
            callback_id = callback_info.get("callback_id", "unknown")
            error_msg = str(e)
            
            # Update error info
            callback_info["last_error"] = error_msg
            
            self._logger.error(f"Callback {callback_id} failed: {error_msg}")
            self.callback_failed.emit(callback_id, error_msg)
    
    def _log_event(self, event: Event):
        """
        Log an event.
        
        Args:
            event: Event to log
        """
        self._logger.info(f"Event: {event.event_type.value} from {event.source} at {event.timestamp}")
    
    def get_event_history(self, event_type: Optional[Union[EventType, str]] = None,
                         source: Optional[str] = None, hours: Optional[int] = None) -> List[Event]:
        """
        Get event history with optional filtering.
        
        Args:
            event_type: Optional event type filter
            source: Optional source filter
            hours: Optional hours to look back
            
        Returns:
            List[Event]: Filtered event history
        """
        try:
            events = self._event_history.copy()
            
            # Filter by event type
            if event_type:
                if isinstance(event_type, str):
                    event_type = EventType(event_type)
                events = [e for e in events if e.event_type == event_type]
            
            # Filter by source
            if source:
                events = [e for e in events if e.source == source]
            
            # Filter by time
            if hours:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                events = [e for e in events if e.timestamp >= cutoff_time]
            
            # Sort by timestamp (most recent first)
            events.sort(key=lambda x: x.timestamp, reverse=True)
            
            return events
            
        except Exception as e:
            self._logger.error(f"Error getting event history: {e}")
            return []
    
    def get_callback_info(self, callback_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a registered callback.
        
        Args:
            callback_id: Callback ID
            
        Returns:
            Optional[Dict[str, Any]]: Callback information if found
        """
        callback_info = self._callback_registry.get(callback_id)
        if callback_info:
            # Return copy without the actual callback function
            return {
                "callback_id": callback_info["callback_id"],
                "priority": callback_info["priority"],
                "async_execution": callback_info["async_execution"],
                "registered_at": callback_info["registered_at"].isoformat(),
                "execution_count": callback_info["execution_count"],
                "last_executed": callback_info["last_executed"].isoformat() if callback_info["last_executed"] else None,
                "last_error": callback_info["last_error"]
            }
        return None
    
    def get_registered_callbacks(self, event_type: Optional[Union[EventType, str]] = None) -> List[Dict[str, Any]]:
        """
        Get list of registered callbacks.
        
        Args:
            event_type: Optional event type filter
            
        Returns:
            List[Dict[str, Any]]: List of callback information
        """
        try:
            if event_type:
                if isinstance(event_type, str):
                    event_type = EventType(event_type)
                callbacks = self._event_callbacks.get(event_type, [])
            else:
                callbacks = []
                for event_callbacks in self._event_callbacks.values():
                    callbacks.extend(event_callbacks)
            
            # Return callback info without actual functions
            return [
                {
                    "callback_id": cb["callback_id"],
                    "priority": cb["priority"],
                    "async_execution": cb["async_execution"],
                    "execution_count": cb["execution_count"],
                    "last_executed": cb["last_executed"].isoformat() if cb["last_executed"] else None,
                    "last_error": cb["last_error"]
                }
                for cb in callbacks
            ]
            
        except Exception as e:
            self._logger.error(f"Error getting registered callbacks: {e}")
            return []
    
    def clear_event_history(self):
        """Clear the event history."""
        self._event_history.clear()
        self._logger.info("Cleared event history")
    
    def clear_event_queue(self):
        """Clear the event queue."""
        self._event_queue.clear()
        self._logger.info("Cleared event queue")
    
    def set_event_logging_enabled(self, enabled: bool):
        """
        Enable or disable event logging.
        
        Args:
            enabled: Whether to enable event logging
        """
        self.enable_event_logging = enabled
        self._logger.info(f"Event logging {'enabled' if enabled else 'disabled'}")
    
    def get_event_stats(self) -> Dict[str, Any]:
        """
        Get event system statistics.
        
        Returns:
            Dict containing event system statistics
        """
        total_callbacks = len(self._callback_registry)
        callbacks_by_type = {}
        
        for event_type, callbacks in self._event_callbacks.items():
            if callbacks:
                callbacks_by_type[event_type.value] = len(callbacks)
        
        total_events = len(self._event_history)
        events_by_type = {}
        
        for event in self._event_history:
            event_type = event.event_type.value
            events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
        
        return {
            "total_callbacks": total_callbacks,
            "callbacks_by_type": callbacks_by_type,
            "total_events": total_events,
            "events_by_type": events_by_type,
            "queue_size": len(self._event_queue),
            "max_queue_size": self.max_event_queue_size,
            "async_callbacks_enabled": self.enable_async_callbacks,
            "event_logging_enabled": self.enable_event_logging
        }
    
    def shutdown(self):
        """Shutdown the event system and cleanup resources."""
        try:
            # Stop timer
            self._queue_timer.stop()
            
            # Process remaining events in queue
            while self._event_queue:
                event = self._event_queue.pop(0)
                self._process_event(event)
            
            # Shutdown thread pool
            self._thread_pool.shutdown(wait=True)
            
            self._logger.info("Event system shutdown complete")
            
        except Exception as e:
            self._logger.error(f"Error during event system shutdown: {e}")


# Convenience functions for common event types
def create_tool_call_event(tool_name: str, parameters: Dict[str, Any], call_id: str) -> Dict[str, Any]:
    """Create data for a tool call event."""
    return {
        "tool_name": tool_name,
        "parameters": parameters,
        "call_id": call_id,
        "timestamp": datetime.now().isoformat()
    }


def create_error_event(error_message: str, error_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Create data for an error event."""
    return {
        "error_message": error_message,
        "error_type": error_type,
        "context": context,
        "timestamp": datetime.now().isoformat()
    }


def create_progress_event(operation_id: str, current: int, total: int, description: str) -> Dict[str, Any]:
    """Create data for a progress event."""
    return {
        "operation_id": operation_id,
        "current": current,
        "total": total,
        "description": description,
        "percentage": (current / total * 100) if total > 0 else 0,
        "timestamp": datetime.now().isoformat()
    }