"""
Streaming Handler - Provides token-by-token output for real-time feedback

This component handles:
- Token-by-token streaming of agent responses
- Real-time progress updates during generation
- Buffering and formatting of streaming content
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, Signal, QTimer


@dataclass
class StreamingChunk:
    """Represents a chunk of streaming content."""
    content: str
    timestamp: datetime
    chunk_type: str  # 'token', 'tool_call', 'tool_result', 'reasoning'
    metadata: Dict[str, Any]


class StreamingHandler(QObject):
    """
    Handles streaming responses for real-time feedback.
    
    This component:
    - Provides token-by-token streaming of agent responses
    - Buffers and formats streaming content appropriately
    - Manages streaming state and progress indicators
    """
    
    # Signals
    token_received = Signal(str)                    # token
    chunk_received = Signal(dict)                   # streaming_chunk
    streaming_started = Signal(str)                 # stream_type
    streaming_finished = Signal(str)                # stream_type
    streaming_error = Signal(str)                   # error_message
    progress_updated = Signal(int, int)             # current, total
    
    # Enhanced signals for process visibility
    process_step_started = Signal(str, str)         # step_name, description
    process_step_completed = Signal(str)            # step_name
    reasoning_chunk_received = Signal(str)          # reasoning_text
    tool_call_detected = Signal(dict)               # tool_call_info
    tool_execution_started = Signal(str, dict)      # tool_name, parameters
    tool_execution_completed = Signal(str, dict)    # tool_name, result
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the streaming handler.
        
        Args:
            config: Configuration dictionary for streaming behavior
        """
        super().__init__()
        
        self.config = config
        self._logger = logging.getLogger(__name__)
        
        # Streaming settings
        self.buffer_size = config.get("streaming_buffer_size", 10)
        self.flush_interval = config.get("streaming_flush_interval", 50)  # ms
        self.enable_streaming = config.get("enable_streaming", True)
        
        # Streaming state
        self._is_streaming = False
        self._current_stream_type = None
        self._content_buffer = []
        self._total_tokens = 0
        self._current_tokens = 0
        
        # Flush timer for buffered content
        self._flush_timer = QTimer()
        self._flush_timer.timeout.connect(self._flush_buffer)
        self._flush_timer.setSingleShot(False)
        
        # Callbacks for different stream types
        self._stream_callbacks: Dict[str, List[Callable]] = {}
    
    def start_streaming(self, stream_type: str, total_tokens: Optional[int] = None):
        """
        Start a streaming session.
        
        Args:
            stream_type: Type of streaming ('response', 'reasoning', 'tool_execution')
            total_tokens: Optional total token count for progress tracking
        """
        try:
            if not self.enable_streaming:
                return
            
            self._is_streaming = True
            self._current_stream_type = stream_type
            self._content_buffer.clear()
            self._current_tokens = 0
            self._total_tokens = total_tokens or 0
            
            # Start flush timer
            if self.flush_interval > 0:
                self._flush_timer.start(self.flush_interval)
            
            self._logger.debug(f"Started streaming for {stream_type}")
            self.streaming_started.emit(stream_type)
            
        except Exception as e:
            self._logger.error(f"Error starting streaming: {e}")
            self.streaming_error.emit(f"Failed to start streaming: {str(e)}")
    
    def add_token(self, token: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add a token to the streaming buffer.
        
        Args:
            token: Token content
            metadata: Optional metadata for the token
        """
        try:
            if not self._is_streaming or not self.enable_streaming:
                return
            
            # Create streaming chunk
            chunk = StreamingChunk(
                content=token,
                timestamp=datetime.now(),
                chunk_type='token',
                metadata=metadata or {}
            )
            
            # Add to buffer
            self._content_buffer.append(chunk)
            self._current_tokens += 1
            
            # Emit token signal immediately
            self.token_received.emit(token)
            
            # Update progress if total is known
            if self._total_tokens > 0:
                self.progress_updated.emit(self._current_tokens, self._total_tokens)
            
            # Flush buffer if it's full
            if len(self._content_buffer) >= self.buffer_size:
                self._flush_buffer()
                
        except Exception as e:
            self._logger.error(f"Error adding token: {e}")
            self.streaming_error.emit(f"Error processing token: {str(e)}")
    
    def add_chunk(self, content: str, chunk_type: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add a content chunk to the streaming buffer.
        
        Args:
            content: Chunk content
            chunk_type: Type of chunk ('tool_call', 'tool_result', 'reasoning', 'status')
            metadata: Optional metadata for the chunk
        """
        try:
            if not self._is_streaming or not self.enable_streaming:
                return
            
            # Create streaming chunk
            chunk = StreamingChunk(
                content=content,
                timestamp=datetime.now(),
                chunk_type=chunk_type,
                metadata=metadata or {}
            )
            
            # Add to buffer
            self._content_buffer.append(chunk)
            
            # Emit chunk signal
            self.chunk_received.emit({
                "content": content,
                "chunk_type": chunk_type,
                "timestamp": chunk.timestamp.isoformat(),
                "metadata": metadata or {}
            })
            
            # Immediate flush for non-token chunks
            if chunk_type != 'token':
                self._flush_buffer()
                
        except Exception as e:
            self._logger.error(f"Error adding chunk: {e}")
            self.streaming_error.emit(f"Error processing chunk: {str(e)}")
    
    def _flush_buffer(self):
        """Flush the content buffer and process accumulated chunks."""
        try:
            if not self._content_buffer:
                return
            
            # Process buffered chunks
            for chunk in self._content_buffer:
                # Execute callbacks for this chunk type
                callbacks = self._stream_callbacks.get(chunk.chunk_type, [])
                for callback in callbacks:
                    try:
                        callback(chunk)
                    except Exception as e:
                        self._logger.warning(f"Callback error for {chunk.chunk_type}: {e}")
            
            # Clear buffer
            self._content_buffer.clear()
            
        except Exception as e:
            self._logger.error(f"Error flushing buffer: {e}")
    
    def finish_streaming(self):
        """Finish the current streaming session."""
        try:
            if not self._is_streaming:
                return
            
            # Flush any remaining content
            self._flush_buffer()
            
            # Stop flush timer
            self._flush_timer.stop()
            
            # Update state
            stream_type = self._current_stream_type
            self._is_streaming = False
            self._current_stream_type = None
            
            self._logger.debug(f"Finished streaming for {stream_type}")
            self.streaming_finished.emit(stream_type or "unknown")
            
        except Exception as e:
            self._logger.error(f"Error finishing streaming: {e}")
            self.streaming_error.emit(f"Error finishing streaming: {str(e)}")
    
    def register_callback(self, chunk_type: str, callback: Callable[[StreamingChunk], None]):
        """
        Register a callback for specific chunk types.
        
        Args:
            chunk_type: Type of chunk to listen for
            callback: Callback function to execute
        """
        if chunk_type not in self._stream_callbacks:
            self._stream_callbacks[chunk_type] = []
        
        self._stream_callbacks[chunk_type].append(callback)
        self._logger.debug(f"Registered callback for chunk type: {chunk_type}")
    
    def unregister_callback(self, chunk_type: str, callback: Callable[[StreamingChunk], None]):
        """
        Unregister a callback for specific chunk types.
        
        Args:
            chunk_type: Type of chunk to stop listening for
            callback: Callback function to remove
        """
        if chunk_type in self._stream_callbacks:
            try:
                self._stream_callbacks[chunk_type].remove(callback)
                self._logger.debug(f"Unregistered callback for chunk type: {chunk_type}")
            except ValueError:
                self._logger.warning(f"Callback not found for chunk type: {chunk_type}")
    
    def is_streaming(self) -> bool:
        """Check if currently streaming."""
        return self._is_streaming
    
    def get_current_stream_type(self) -> Optional[str]:
        """Get the current stream type."""
        return self._current_stream_type
    
    def get_progress(self) -> tuple[int, int]:
        """
        Get current streaming progress.
        
        Returns:
            Tuple of (current_tokens, total_tokens)
        """
        return (self._current_tokens, self._total_tokens)
    
    def set_streaming_enabled(self, enabled: bool):
        """
        Enable or disable streaming.
        
        Args:
            enabled: Whether to enable streaming
        """
        self.enable_streaming = enabled
        
        if not enabled and self._is_streaming:
            self.finish_streaming()
        
        self._logger.info(f"Streaming {'enabled' if enabled else 'disabled'}")
    
    def add_process_step(self, step_name: str, description: str):
        """
        Add a process step for visibility.
        
        Args:
            step_name: Name of the process step
            description: Description of what's happening
        """
        try:
            if not self.enable_streaming:
                return
            
            self._logger.debug(f"Process step started: {step_name} - {description}")
            self.process_step_started.emit(step_name, description)
            
            # Add as a chunk for tracking
            self.add_chunk(description, 'process_step', {'step_name': step_name})
            
        except Exception as e:
            self._logger.error(f"Error adding process step: {e}")
    
    def complete_process_step(self, step_name: str):
        """
        Mark a process step as completed.
        
        Args:
            step_name: Name of the completed step
        """
        try:
            if not self.enable_streaming:
                return
            
            self._logger.debug(f"Process step completed: {step_name}")
            self.process_step_completed.emit(step_name)
            
        except Exception as e:
            self._logger.error(f"Error completing process step: {e}")
    
    def add_reasoning_chunk(self, reasoning_text: str):
        """
        Add reasoning text chunk for streaming display.
        
        Args:
            reasoning_text: Chunk of reasoning text
        """
        try:
            if not self.enable_streaming:
                return
            
            self.reasoning_chunk_received.emit(reasoning_text)
            self.add_chunk(reasoning_text, 'reasoning')
            
        except Exception as e:
            self._logger.error(f"Error adding reasoning chunk: {e}")
    
    def notify_tool_call_detected(self, tool_name: str, parameters: dict):
        """
        Notify that a tool call was detected in the response.
        
        Args:
            tool_name: Name of the tool to be called
            parameters: Parameters for the tool call
        """
        try:
            if not self.enable_streaming:
                return
            
            tool_info = {
                'tool_name': tool_name,
                'parameters': parameters,
                'timestamp': datetime.now().isoformat()
            }
            
            self.tool_call_detected.emit(tool_info)
            self.add_chunk(f"Tool call detected: {tool_name}", 'tool_detection', tool_info)
            
        except Exception as e:
            self._logger.error(f"Error notifying tool call detected: {e}")
    
    def notify_tool_execution_started(self, tool_name: str, parameters: dict):
        """
        Notify that tool execution has started.
        
        Args:
            tool_name: Name of the tool being executed
            parameters: Parameters for the tool execution
        """
        try:
            if not self.enable_streaming:
                return
            
            self.tool_execution_started.emit(tool_name, parameters)
            self.add_chunk(f"Executing tool: {tool_name}", 'tool_execution_start', {
                'tool_name': tool_name,
                'parameters': parameters
            })
            
        except Exception as e:
            self._logger.error(f"Error notifying tool execution started: {e}")
    
    def notify_tool_execution_completed(self, tool_name: str, result: dict):
        """
        Notify that tool execution has completed.
        
        Args:
            tool_name: Name of the completed tool
            result: Result of the tool execution
        """
        try:
            if not self.enable_streaming:
                return
            
            self.tool_execution_completed.emit(tool_name, result)
            
            status = result.get('status', 'unknown')
            self.add_chunk(f"Tool {tool_name} completed: {status}", 'tool_execution_complete', {
                'tool_name': tool_name,
                'result': result
            })
            
        except Exception as e:
            self._logger.error(f"Error notifying tool execution completed: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get streaming statistics.
        
        Returns:
            Dict containing streaming stats
        """
        return {
            "is_streaming": self._is_streaming,
            "current_stream_type": self._current_stream_type,
            "current_tokens": self._current_tokens,
            "total_tokens": self._total_tokens,
            "buffer_size": len(self._content_buffer),
            "enabled": self.enable_streaming,
            "registered_callbacks": {
                chunk_type: len(callbacks) 
                for chunk_type, callbacks in self._stream_callbacks.items()
            }
        }