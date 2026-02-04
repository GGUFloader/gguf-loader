"""
Agent Controller - Core orchestration component for the agentic chatbot system
"""

import uuid
import logging
import traceback
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .tool_registry import ToolRegistry
from .context_manager import ContextManager
from .safety_monitor import SafetyMonitor


class AgentControllerError(Exception):
    """Base exception for agent controller errors."""
    pass


class SessionCreationError(AgentControllerError):
    """Exception raised when session creation fails."""
    pass


class SessionNotFoundError(AgentControllerError):
    """Exception raised when session is not found."""
    pass


class ToolExecutionError(AgentControllerError):
    """Exception raised when tool execution fails."""
    pass


@dataclass
class AgentSession:
    """Data class representing an agent session state."""
    session_id: str
    workspace_path: Path
    conversation_history: List[Dict[str, Any]]
    active_tools: List[str]
    security_context: Dict[str, Any]
    created_at: datetime
    last_activity: datetime


class AgentController(QObject):
    """
    Core agent controller that orchestrates agent sessions and tool execution.
    
    This component manages:
    - Agent session lifecycle
    - Integration with GGUF Loader model and chat generation
    - Tool execution coordination
    - Conversation state management
    """
    
    # Signals
    session_created = Signal(str)  # session_id
    session_ended = Signal(str)    # session_id
    tool_execution_started = Signal(str, dict)  # session_id, tool_call
    tool_execution_finished = Signal(str, dict) # session_id, result
    
    def __init__(self, gguf_app_instance: Any, tool_registry: ToolRegistry, config: Dict[str, Any]):
        """
        Initialize the agent controller.
        
        Args:
            gguf_app_instance: Reference to main GGUF Loader application
            tool_registry: Tool registry for executing agent tools
            config: Configuration dictionary for agent behavior
        """
        super().__init__()
        
        self.gguf_app = gguf_app_instance
        self.tool_registry = tool_registry
        self.config = config
        self._logger = logging.getLogger(__name__)
        
        # Initialize context manager
        self.context_manager = ContextManager(config)
        
        # Session management
        self._active_sessions: Dict[str, AgentSession] = {}
        self._is_running = False
        
        # Connect tool registry signals
        if self.tool_registry:
            self.tool_registry.tool_executed.connect(self._on_tool_executed)
    
    def create_session(self, workspace_path: str) -> str:
        """
        Create a new agent session with specified workspace.
        
        Args:
            workspace_path: Path to the workspace directory
            
        Returns:
            str: Unique session ID
            
        Raises:
            SessionCreationError: If session creation fails
            ValueError: If workspace path is invalid
        """
        try:
            # Generate unique session ID
            session_id = str(uuid.uuid4())
            
            # Validate and resolve workspace path
            workspace = Path(workspace_path).resolve()
            
            # Security validation - ensure workspace is not in sensitive areas
            sensitive_paths = [
                Path.home() / ".ssh",
                Path("/etc"),
                Path("/sys"),
                Path("/proc"),
                Path("/dev")
            ]
            
            for sensitive_path in sensitive_paths:
                try:
                    if workspace.is_relative_to(sensitive_path):
                        raise ValueError(f"Workspace cannot be in sensitive directory: {sensitive_path}")
                except (OSError, ValueError):
                    # is_relative_to may fail on some systems, continue with other checks
                    pass
            
            if not workspace.exists():
                if self.config.get("auto_create_workspace", True):
                    try:
                        workspace.mkdir(parents=True, exist_ok=True)
                        self._logger.info(f"Created workspace directory: {workspace}")
                    except (OSError, PermissionError) as e:
                        raise SessionCreationError(f"Failed to create workspace directory: {e}")
                else:
                    raise ValueError(f"Workspace path does not exist: {workspace}")
            
            # Verify workspace is writable
            try:
                test_file = workspace / ".agent_test"
                test_file.touch()
                test_file.unlink()
            except (OSError, PermissionError) as e:
                raise SessionCreationError(f"Workspace is not writable: {e}")
            
            # Create session
            session = AgentSession(
                session_id=session_id,
                workspace_path=workspace,
                conversation_history=[],
                active_tools=self.tool_registry.get_available_tools() if self.tool_registry else [],
                security_context={
                    "workspace_root": str(workspace),
                    "allowed_commands": self.config.get("allowed_commands", []),
                    "command_timeout": self.config.get("command_timeout", 30)
                },
                created_at=datetime.now(),
                last_activity=datetime.now()
            )
            
            # Store session
            self._active_sessions[session_id] = session
            
            # Create context for this session with error handling
            try:
                self.context_manager.create_context(session_id, str(workspace))
            except Exception as e:
                # Clean up session if context creation fails
                del self._active_sessions[session_id]
                raise SessionCreationError(f"Failed to create session context: {e}")
            
            self._logger.info(f"Created agent session {session_id} with workspace {workspace}")
            self.session_created.emit(session_id)
            
            return session_id
            
        except (ValueError, SessionCreationError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            self._logger.error(f"Unexpected error creating session: {e}")
            self._logger.debug(f"Session creation traceback: {traceback.format_exc()}")
            raise SessionCreationError(f"Unexpected session creation error: {e}")
    
    def end_session(self, session_id: str) -> bool:
        """
        End an agent session and cleanup resources.
        
        Args:
            session_id: ID of the session to end
            
        Returns:
            bool: True if session ended successfully, False otherwise
        """
        try:
            if session_id not in self._active_sessions:
                self._logger.warning(f"Session {session_id} not found")
                return False
            
            # Remove session
            del self._active_sessions[session_id]
            
            # Delete context
            self.context_manager.delete_context(session_id)
            
            self._logger.info(f"Ended agent session {session_id}")
            self.session_ended.emit(session_id)
            
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to end session {session_id}: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """
        Get agent session by ID.
        
        Args:
            session_id: ID of the session to retrieve
            
        Returns:
            Optional[AgentSession]: Session if found, None otherwise
        """
        return self._active_sessions.get(session_id)
    
    def get_active_sessions(self) -> List[str]:
        """
        Get list of active session IDs.
        
        Returns:
            List[str]: List of active session IDs
        """
        return list(self._active_sessions.keys())
    
    def execute_tool_call(self, session_id: str, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool call within a specific session context.
        
        Args:
            session_id: ID of the session
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
            
        Returns:
            Dict[str, Any]: Tool execution result
            
        Raises:
            SessionNotFoundError: If session not found
            ToolExecutionError: If tool execution fails
        """
        try:
            # Validate session
            session = self.get_session(session_id)
            if not session:
                raise SessionNotFoundError(f"Session {session_id} not found")
            
            # Update last activity
            session.last_activity = datetime.now()
            
            # Validate tool name
            if not tool_name or not isinstance(tool_name, str):
                raise ToolExecutionError("Invalid tool name provided")
            
            # Validate parameters
            if not isinstance(parameters, dict):
                raise ToolExecutionError("Tool parameters must be a dictionary")
            
            # Create tool call context
            tool_call = {
                "tool": tool_name,
                "parameters": parameters,
                "call_id": str(uuid.uuid4()),
                "session_id": session_id
            }
            
            self._logger.info(f"Executing tool call {tool_call['call_id']} in session {session_id}")
            self.tool_execution_started.emit(session_id, tool_call)
            
            # Execute tool through registry with comprehensive error handling
            if not self.tool_registry:
                raise ToolExecutionError("Tool registry not available")
            
            try:
                result = self.tool_registry.execute_tool(tool_name, parameters)
            except Exception as e:
                # Log the full traceback for debugging
                self._logger.error(f"Tool registry execution failed: {e}")
                self._logger.debug(f"Tool execution traceback: {traceback.format_exc()}")
                raise ToolExecutionError(f"Tool registry execution failed: {e}")
            
            # Validate result format
            if not isinstance(result, dict):
                self._logger.warning(f"Tool {tool_name} returned non-dict result, wrapping")
                result = {
                    "status": "success",
                    "result": result,
                    "tool_name": tool_name
                }
            
            # Ensure required fields
            if "status" not in result:
                result["status"] = "success" if "error" not in result else "error"
            
            # Add session context to result
            result["session_id"] = session_id
            result["call_id"] = tool_call["call_id"]
            result["tool_name"] = tool_name
            
            # Log result status
            status = result.get("status", "unknown")
            if status == "success":
                self._logger.info(f"Tool call {tool_call['call_id']} completed successfully")
            else:
                error_msg = result.get("error", "Unknown error")
                self._logger.warning(f"Tool call {tool_call['call_id']} failed: {error_msg}")
            
            self.tool_execution_finished.emit(session_id, result)
            return result
            
        except (SessionNotFoundError, ToolExecutionError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            # Handle unexpected errors
            error_result = {
                "status": "error",
                "error": f"Unexpected tool execution error: {str(e)}",
                "session_id": session_id,
                "call_id": tool_call.get("call_id", "unknown") if 'tool_call' in locals() else "unknown",
                "tool_name": tool_name
            }
            
            self._logger.error(f"Unexpected tool execution error: {e}")
            self._logger.debug(f"Tool execution traceback: {traceback.format_exc()}")
            self.tool_execution_finished.emit(session_id, error_result)
            
            return error_result
    
    def add_conversation_message(self, session_id: str, role: str, content: str, tool_calls: Optional[List[Dict]] = None):
        """
        Add a message to the conversation history.
        
        Args:
            session_id: ID of the session
            role: Message role (user, assistant, tool)
            content: Message content
            tool_calls: Optional tool calls associated with the message
        """
        try:
            session = self.get_session(session_id)
            if not session:
                self._logger.warning(f"Session {session_id} not found")
                return
            
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "tool_calls": tool_calls or []
            }
            
            session.conversation_history.append(message)
            session.last_activity = datetime.now()
            
        except Exception as e:
            self._logger.error(f"Failed to add conversation message: {e}")
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            List[Dict[str, Any]]: Conversation history
        """
        session = self.get_session(session_id)
        if session:
            return session.conversation_history.copy()
        return []
    
    def stop(self):
        """Stop the agent controller and cleanup all sessions."""
        try:
            self._logger.info("Stopping agent controller")
            
            # End all active sessions
            session_ids = list(self._active_sessions.keys())
            for session_id in session_ids:
                self.end_session(session_id)
            
            self._is_running = False
            
        except Exception as e:
            self._logger.error(f"Error stopping agent controller: {e}")
    
    def _on_tool_executed(self, result: Dict[str, Any]):
        """Handle tool execution completion from tool registry."""
        try:
            session_id = result.get("session_id")
            if session_id and session_id in self._active_sessions:
                # Tool execution is already handled in execute_tool_call
                pass
        except Exception as e:
            self._logger.error(f"Error handling tool execution result: {e}")
    
    def on_model_loaded(self, model):
        """Handle model loaded event from main app."""
        try:
            self._logger.info("Model loaded - agent controller ready")
            # Model integration will be implemented in later tasks
        except Exception as e:
            self._logger.error(f"Error handling model loaded: {e}")
    
    def on_generation_finished(self):
        """Handle generation finished event from main app."""
        try:
            # Generation handling will be implemented in later tasks
            pass
        except Exception as e:
            self._logger.error(f"Error handling generation finished: {e}")
    
    def on_generation_error(self, error_message: str):
        """Handle generation error event from main app."""
        try:
            self._logger.error(f"Generation error: {error_message}")
            # Error handling will be implemented in later tasks
        except Exception as e:
            self._logger.error(f"Error handling generation error: {e}")