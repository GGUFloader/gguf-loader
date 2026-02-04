"""
Agent Loop - Manages conversation cycle and tool orchestration

This component handles:
- Conversation cycle with tool call generation and execution
- Context management and token budget handling
- Integration with existing Chat_Generator for response generation
"""

import json
import re
import logging
import time
import traceback
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QThread, Signal, QObject

from .tool_registry import ToolRegistry
from .context_manager import ContextManager
from .system_prompt import SystemPromptManager
from .streaming_handler import StreamingHandler
from .memory_manager import MemoryManager
from .progress_monitor import ProgressMonitor
from .event_system import EventSystem, EventType
from models.chat_generator import ChatGenerator


class AgentLoopError(Exception):
    """Base exception for agent loop errors."""
    pass


class ModelNotAvailableError(AgentLoopError):
    """Exception raised when model is not available."""
    pass


class ContextGenerationError(AgentLoopError):
    """Exception raised when context generation fails."""
    pass


class ToolCallParsingError(AgentLoopError):
    """Exception raised when tool call parsing fails."""
    pass


@dataclass
class ToolCall:
    """Represents a tool call request from the agent."""
    tool_name: str
    parameters: Dict[str, Any]
    call_id: str
    reasoning: Optional[str] = None


@dataclass
class AgentTurn:
    """Represents a complete agent turn with reasoning, tool calls, and response."""
    user_message: str
    reasoning: str
    tool_calls: List[ToolCall]
    tool_results: List[Dict[str, Any]]
    final_response: str
    timestamp: datetime
    token_count: int = 0


class AgentLoop(QThread):
    """
    Main agent loop that manages conversation cycles and tool orchestration.
    
    This component:
    - Processes user messages and generates agent responses
    - Orchestrates tool calls and integrates results
    - Manages conversation context and token budgets
    - Integrates with existing GGUF Loader Chat_Generator
    """
    
    # Signals
    tool_call_requested = Signal(dict)      # tool_call
    tool_result_received = Signal(dict)     # tool_result
    response_generated = Signal(str)        # response_text
    reasoning_generated = Signal(str)       # reasoning_text
    turn_completed = Signal(dict)           # agent_turn
    error_occurred = Signal(str)            # error_message
    
    def __init__(self, gguf_app_instance: Any, tool_registry: ToolRegistry, config: Dict[str, Any]):
        """
        Initialize the agent loop.
        
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
        
        # Initialize system prompt manager
        self.system_prompt_manager = SystemPromptManager(config)
        
        # Initialize advanced features
        self.streaming_handler = StreamingHandler(config)
        self.memory_manager = MemoryManager(config)
        self.progress_monitor = ProgressMonitor(config)
        self.event_system = EventSystem(config)
        
        # Agent state
        self._current_session_id: Optional[str] = None
        self._conversation_history: List[AgentTurn] = []
        self._is_processing = False
        self._stop_requested = False
        
        # Configuration parameters
        self.max_iterations = config.get("max_iterations", 15)
        self.max_tool_calls_per_turn = config.get("max_tool_calls_per_turn", 5)
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", 2048)
        
        # System prompt for agent behavior (will be generated dynamically)
        self._system_prompt: Optional[str] = None
        
        # Connect event system callbacks
        self._setup_event_callbacks()
    
    def _build_system_prompt(self, workspace_path: str) -> str:
        """Build comprehensive system prompt for agent behavior using SystemPromptManager."""
        try:
            available_tools = self.tool_registry.get_available_tools() if self.tool_registry else []
            return self.system_prompt_manager.get_system_prompt(workspace_path, available_tools)
        except Exception as e:
            self._logger.error(f"Error building system prompt: {e}")
            # Fallback to basic prompt
            return "You are an AI assistant with tool-calling capabilities. Use tools to help users accomplish tasks within your workspace."
    
    def set_session(self, session_id: str, workspace_path: str):
        """Set the current session ID for the agent loop and generate system prompt."""
        self._current_session_id = session_id
        
        # Generate system prompt for this workspace
        self._system_prompt = self._build_system_prompt(workspace_path)
        
        # Create or load context for this session
        context = self.context_manager.get_context(session_id)
        if not context:
            context = self.context_manager.create_context(session_id, workspace_path)
        
        self._logger.info(f"Agent loop set to session {session_id} with workspace {workspace_path}")
    
    def process_user_message(self, message: str) -> None:
        """
        Process a user message and generate agent response.
        
        Args:
            message: User input message
        """
        if self._is_processing:
            self._logger.warning("Agent loop is already processing a message")
            return
        
        self._is_processing = True
        self._stop_requested = False
        
        # Store message for processing in run()
        self._current_message = message
        
        # Start processing in thread
        self.start()
    
    def run(self):
        """Main processing loop - runs in separate thread."""
        try:
            if not self._current_message:
                self.error_occurred.emit("No message to process")
                return
            
            message = self._current_message
            self._logger.info(f"Processing user message: {message[:100]}...")
            
            # Start progress monitoring
            operation_id = f"agent_turn_{int(time.time())}"
            self.progress_monitor.start_operation(operation_id, "Processing user message", 4)
            
            # Emit event for agent turn started
            self.event_system.emit_event(
                EventType.AGENT_TURN_STARTED,
                "agent_loop",
                {"message": message, "session_id": self._current_session_id}
            )
            
            # Add user message to context
            if self._current_session_id:
                self.context_manager.add_message(self._current_session_id, "user", message)
            
            # Create agent turn
            agent_turn = AgentTurn(
                user_message=message,
                reasoning="",
                tool_calls=[],
                tool_results=[],
                final_response="",
                timestamp=datetime.now()
            )
            
            # Step 1: Generate initial response with potential tool calls
            self.progress_monitor.update_progress(operation_id, 1, "Generating response and tool calls")
            response_data = self._generate_agent_response(message)
            
            if self._stop_requested:
                self.progress_monitor.cancel_operation(operation_id, "User requested stop")
                return
            
            # Step 2: Parse response for tool calls
            self.progress_monitor.update_progress(operation_id, 2, "Parsing tool calls")
            tool_calls = self._parse_tool_calls(response_data)
            agent_turn.reasoning = response_data.get("reasoning", "")
            agent_turn.tool_calls = tool_calls
            
            # Step 3: Execute tool calls if any
            if tool_calls:
                self.progress_monitor.update_progress(operation_id, 3, f"Executing {len(tool_calls)} tool calls")
                self._logger.info(f"Executing {len(tool_calls)} tool calls")
                tool_results = self._execute_tool_calls(tool_calls)
                agent_turn.tool_results = tool_results
                
                if self._stop_requested:
                    self.progress_monitor.cancel_operation(operation_id, "User requested stop")
                    return
                
                # Generate final response with tool results
                final_response = self._generate_final_response(message, tool_results)
                agent_turn.final_response = final_response
            else:
                # No tools needed, use direct response
                agent_turn.final_response = response_data.get("response", "I understand your request.")
            
            # Step 4: Finalize and emit results
            self.progress_monitor.update_progress(operation_id, 4, "Finalizing response")
            
            # Add to conversation history
            self._conversation_history.append(agent_turn)
            
            # Add assistant response to context
            if self._current_session_id:
                self.context_manager.add_message(self._current_session_id, "assistant", agent_turn.final_response)
            
            # Record completed turn in memory
            if hasattr(self, 'memory_manager'):
                tool_names = [tc.tool_name for tc in agent_turn.tool_calls]
                self.memory_manager.record_completed_task(
                    f"Agent turn: {message[:50]}...",
                    self.context_manager.get_context(self._current_session_id).workspace_path if self._current_session_id else "",
                    tool_names,
                    agent_turn.final_response[:100] + "..." if len(agent_turn.final_response) > 100 else agent_turn.final_response,
                    self._current_session_id or "unknown"
                )
            
            # Complete progress monitoring
            self.progress_monitor.complete_operation(operation_id, "Agent turn completed successfully")
            
            # Emit completion signals
            self.response_generated.emit(agent_turn.final_response)
            self.turn_completed.emit({
                "user_message": agent_turn.user_message,
                "reasoning": agent_turn.reasoning,
                "tool_calls": [{"tool": tc.tool_name, "parameters": tc.parameters} for tc in agent_turn.tool_calls],
                "tool_results": agent_turn.tool_results,
                "final_response": agent_turn.final_response,
                "timestamp": agent_turn.timestamp.isoformat()
            })
            
            # Emit event for agent turn completed
            self.event_system.emit_event(
                EventType.AGENT_TURN_COMPLETED,
                "agent_loop",
                {
                    "message": message,
                    "response": agent_turn.final_response,
                    "tool_calls_count": len(agent_turn.tool_calls),
                    "session_id": self._current_session_id
                }
            )
            
            self._logger.info("Agent turn completed successfully")
            
        except Exception as e:
            self._logger.error(f"Error in agent loop: {e}")
            
            # Fail progress monitoring
            if 'operation_id' in locals():
                self.progress_monitor.fail_operation(operation_id, str(e))
            
            # Emit error event
            self.event_system.emit_event(
                EventType.ERROR_OCCURRED,
                "agent_loop",
                {"error_message": str(e), "context": "agent_turn_processing"}
            )
            
            self.error_occurred.emit(f"Agent processing error: {str(e)}")
        
        finally:
            self._is_processing = False
            self._current_message = None
    
    def _generate_agent_response(self, message: str) -> Dict[str, Any]:
        """
        Generate initial agent response with potential tool calls.
        
        Args:
            message: User message
            
        Returns:
            Dict containing reasoning and potential tool calls
            
        Raises:
            ModelNotAvailableError: If model is not available
            ContextGenerationError: If context generation fails
        """
        try:
            # Build context with conversation history
            try:
                context = self._build_conversation_context(message)
            except Exception as e:
                self._logger.error(f"Context generation failed: {e}")
                raise ContextGenerationError(f"Failed to build conversation context: {e}")
            
            # Validate model availability
            if not self.gguf_app or not hasattr(self.gguf_app, 'model') or not self.gguf_app.model:
                raise ModelNotAvailableError("No model available for processing")
            
            # Create chat generator for this request with error handling
            try:
                chat_generator = ChatGenerator(
                    model=self.gguf_app.model,
                    prompt=context,
                    chat_history=[],  # Context already built into prompt
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system_prompt_name="assistant"
                )
            except Exception as e:
                self._logger.error(f"Failed to create chat generator: {e}")
                raise ContextGenerationError(f"Failed to create chat generator: {e}")
            
            # Generate response synchronously (we're already in a thread)
            response_text = ""
            generation_error = None
            
            # Connect to token signals with error handling
            def on_token(token):
                nonlocal response_text
                try:
                    response_text += token
                except Exception as e:
                    self._logger.error(f"Error processing token: {e}")
            
            def on_finished():
                pass
            
            def on_error(error):
                nonlocal generation_error
                generation_error = error
                self._logger.error(f"Generation error: {error}")
            
            try:
                chat_generator.token_received.connect(on_token)
                chat_generator.finished.connect(on_finished)
                chat_generator.error.connect(on_error)
                
                # Run generation with timeout protection
                chat_generator.run()
                
                # Check for generation errors
                if generation_error:
                    raise ContextGenerationError(f"Model generation failed: {generation_error}")
                
                # Validate response
                if not response_text or not response_text.strip():
                    self._logger.warning("Empty response from model, using fallback")
                    response_text = "I understand your request, but I'm having trouble generating a response right now."
                
            except Exception as e:
                self._logger.error(f"Error during model generation: {e}")
                raise ContextGenerationError(f"Model generation error: {e}")
            
            # Parse the response with error handling
            try:
                return self._parse_agent_response(response_text)
            except Exception as e:
                self._logger.error(f"Response parsing failed: {e}")
                # Return fallback response
                return {
                    "reasoning": f"Response parsing failed: {str(e)}",
                    "tool_calls": [],
                    "response": response_text
                }
                
        except (ModelNotAvailableError, ContextGenerationError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            # Handle unexpected errors
            self._logger.error(f"Unexpected error generating agent response: {e}")
            self._logger.debug(f"Agent response generation traceback: {traceback.format_exc()}")
            return {
                "reasoning": f"Unexpected error generating response: {str(e)}",
                "response": "I encountered an unexpected error while processing your request. Please try again."
            }
    
    def _build_conversation_context(self, current_message: str) -> str:
        """
        Build conversation context with history and current message.
        
        Args:
            current_message: Current user message
            
        Returns:
            str: Formatted conversation context
        """
        context = self.system_prompt + "\n\n"
        
        # Use context manager to get optimized conversation history
        if self._current_session_id:
            history_context = self.context_manager.get_context_for_generation(
                self._current_session_id, 
                max_tokens=self.max_tokens // 2  # Reserve half tokens for response
            )
            if history_context:
                context += history_context + "\n\n"
        else:
            # Fallback to local history if no session
            recent_history = self._conversation_history[-3:] if len(self._conversation_history) > 3 else self._conversation_history
            
            for turn in recent_history:
                context += f"User: {turn.user_message}\n"
                if turn.reasoning:
                    context += f"Assistant Reasoning: {turn.reasoning}\n"
                if turn.tool_calls:
                    context += f"Tool Calls: {len(turn.tool_calls)} tools used\n"
                context += f"Assistant: {turn.final_response}\n\n"
        
        # Add current message
        context += f"User: {current_message}\n"
        context += "Assistant: "
        
        return context
    
    def _parse_agent_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse agent response to extract reasoning and tool calls.
        
        Args:
            response_text: Raw response from the model
            
        Returns:
            Dict containing parsed reasoning and tool calls
        """
        try:
            # Look for JSON blocks in the response
            json_pattern = r'```json\s*(\{.*?\})\s*```'
            json_matches = re.findall(json_pattern, response_text, re.DOTALL)
            
            if json_matches:
                # Parse the first JSON block
                json_text = json_matches[0]
                parsed_json = json.loads(json_text)
                
                return {
                    "reasoning": parsed_json.get("reasoning", ""),
                    "tool_calls": parsed_json.get("tool_calls", []),
                    "response": response_text
                }
            else:
                # No JSON found, treat as direct response
                return {
                    "reasoning": "",
                    "tool_calls": [],
                    "response": response_text
                }
                
        except json.JSONDecodeError as e:
            self._logger.warning(f"Failed to parse JSON from response: {e}")
            return {
                "reasoning": "Failed to parse tool calls",
                "tool_calls": [],
                "response": response_text
            }
        except Exception as e:
            self._logger.error(f"Error parsing agent response: {e}")
            return {
                "reasoning": f"Error parsing response: {str(e)}",
                "tool_calls": [],
                "response": response_text
            }
    
    def _parse_tool_calls(self, response_data: Dict[str, Any]) -> List[ToolCall]:
        """
        Parse tool calls from response data.
        
        Args:
            response_data: Parsed response data
            
        Returns:
            List of ToolCall objects
        """
        tool_calls = []
        
        try:
            raw_tool_calls = response_data.get("tool_calls", [])
            
            for i, call_data in enumerate(raw_tool_calls):
                if i >= self.max_tool_calls_per_turn:
                    self._logger.warning(f"Limiting tool calls to {self.max_tool_calls_per_turn}")
                    break
                
                tool_call = ToolCall(
                    tool_name=call_data.get("tool", ""),
                    parameters=call_data.get("parameters", {}),
                    call_id=f"call_{int(time.time())}_{i}",
                    reasoning=response_data.get("reasoning", "")
                )
                
                tool_calls.append(tool_call)
                
        except Exception as e:
            self._logger.error(f"Error parsing tool calls: {e}")
        
        return tool_calls
    
    def _execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[Dict[str, Any]]:
        """
        Execute a list of tool calls.
        
        Args:
            tool_calls: List of tool calls to execute
            
        Returns:
            List of tool execution results
        """
        results = []
        
        for tool_call in tool_calls:
            if self._stop_requested:
                break
            
            try:
                self._logger.info(f"Executing tool: {tool_call.tool_name}")
                
                # Emit event for tool call started
                self.event_system.emit_event(
                    EventType.TOOL_CALL_STARTED,
                    "agent_loop",
                    {
                        "tool_name": tool_call.tool_name,
                        "parameters": tool_call.parameters,
                        "call_id": tool_call.call_id,
                        "workspace_path": self.context_manager.get_context(self._current_session_id).workspace_path if self._current_session_id else ""
                    }
                )
                
                # Emit tool call signal
                self.tool_call_requested.emit({
                    "tool": tool_call.tool_name,
                    "parameters": tool_call.parameters,
                    "call_id": tool_call.call_id
                })
                
                # Execute tool through registry
                if not self.tool_registry:
                    result = {
                        "status": "error",
                        "error": "Tool registry not available",
                        "call_id": tool_call.call_id
                    }
                else:
                    result = self.tool_registry.execute_tool(
                        tool_call.tool_name, 
                        tool_call.parameters
                    )
                    result["call_id"] = tool_call.call_id
                
                results.append(result)
                
                # Emit tool result signal
                self.tool_result_received.emit(result)
                
                # Emit event for tool call completed
                self.event_system.emit_event(
                    EventType.TOOL_CALL_COMPLETED if result.get("status") == "success" else EventType.TOOL_CALL_FAILED,
                    "agent_loop",
                    {
                        "tool_name": tool_call.tool_name,
                        "call_id": tool_call.call_id,
                        "status": result.get("status", "unknown"),
                        "result": result.get("result", ""),
                        "error": result.get("error", ""),
                        "workspace_path": self.context_manager.get_context(self._current_session_id).workspace_path if self._current_session_id else ""
                    }
                )
                
                self._logger.info(f"Tool {tool_call.tool_name} executed: {result.get('status', 'unknown')}")
                
            except Exception as e:
                error_result = {
                    "status": "error",
                    "error": f"Tool execution failed: {str(e)}",
                    "call_id": tool_call.call_id,
                    "tool_name": tool_call.tool_name
                }
                results.append(error_result)
                self.tool_result_received.emit(error_result)
                
                # Emit error event
                self.event_system.emit_event(
                    EventType.TOOL_CALL_FAILED,
                    "agent_loop",
                    {
                        "tool_name": tool_call.tool_name,
                        "call_id": tool_call.call_id,
                        "error": str(e)
                    }
                )
                
                self._logger.error(f"Tool execution error: {e}")
        
        return results
    
    def _generate_final_response(self, user_message: str, tool_results: List[Dict[str, Any]]) -> str:
        """
        Generate final response incorporating tool results.
        
        Args:
            user_message: Original user message
            tool_results: Results from tool executions
            
        Returns:
            str: Final response text
        """
        try:
            # Build context with tool results
            context = f"{self.system_prompt}\n\n"
            context += f"User Request: {user_message}\n\n"
            context += "Tool Execution Results:\n"
            
            for i, result in enumerate(tool_results):
                status = result.get("status", "unknown")
                tool_name = result.get("tool_name", "unknown")
                
                context += f"\nTool {i+1} ({tool_name}): {status}\n"
                
                if status == "success":
                    # Include successful results
                    if "result" in result:
                        result_text = str(result["result"])
                        # Truncate very long results
                        if len(result_text) > 1000:
                            result_text = result_text[:1000] + "... (truncated)"
                        context += f"Result: {result_text}\n"
                else:
                    # Include error information
                    error = result.get("error", "Unknown error")
                    context += f"Error: {error}\n"
            
            context += "\nBased on these tool results, provide a helpful summary and response to the user:\n"
            
            # Generate final response
            if not self.gguf_app or not hasattr(self.gguf_app, 'model') or not self.gguf_app.model:
                return "Tool execution completed, but no model available for response generation."
            
            chat_generator = ChatGenerator(
                model=self.gguf_app.model,
                prompt=context,
                chat_history=[],
                max_tokens=min(self.max_tokens, 1024),  # Shorter for final response
                temperature=self.temperature,
                system_prompt_name="assistant"
            )
            
            # Generate response synchronously
            response_text = ""
            
            def on_token(token):
                nonlocal response_text
                response_text += token
            
            chat_generator.token_received.connect(on_token)
            chat_generator.run()
            
            return response_text.strip() if response_text else "Task completed successfully."
            
        except Exception as e:
            self._logger.error(f"Error generating final response: {e}")
            return f"I completed the requested operations, but encountered an error generating the summary: {str(e)}"
    
    def stop_processing(self):
        """Stop the current processing operation."""
        self._stop_requested = True
        self._logger.info("Agent loop stop requested")
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get conversation history for the current session.
        
        Returns:
            List of conversation turns
        """
        return [
            {
                "user_message": turn.user_message,
                "reasoning": turn.reasoning,
                "tool_calls": [{"tool": tc.tool_name, "parameters": tc.parameters} for tc in turn.tool_calls],
                "tool_results": turn.tool_results,
                "final_response": turn.final_response,
                "timestamp": turn.timestamp.isoformat(),
                "token_count": turn.token_count
            }
            for turn in self._conversation_history
        ]
    
    def clear_conversation_history(self):
        """Clear the conversation history."""
        self._conversation_history.clear()
        self._logger.info("Conversation history cleared")
    
    def is_processing(self) -> bool:
        """Check if the agent loop is currently processing."""
        return self._is_processing
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the agent loop.
        
        Returns:
            Dict containing usage statistics
        """
        total_turns = len(self._conversation_history)
        total_tool_calls = sum(len(turn.tool_calls) for turn in self._conversation_history)
        
        return {
            "total_turns": total_turns,
            "total_tool_calls": total_tool_calls,
            "current_session": self._current_session_id,
            "is_processing": self._is_processing,
            "max_iterations": self.max_iterations,
            "max_tool_calls_per_turn": self.max_tool_calls_per_turn
        }
    
    def _setup_event_callbacks(self):
        """Setup event system callbacks for agent loop integration."""
        try:
            # Register callbacks for various events
            self.event_system.register_callback(
                EventType.TOOL_CALL_STARTED,
                self._on_tool_call_started,
                "agent_loop_tool_start"
            )
            
            self.event_system.register_callback(
                EventType.TOOL_CALL_COMPLETED,
                self._on_tool_call_completed,
                "agent_loop_tool_complete"
            )
            
            self.event_system.register_callback(
                EventType.ERROR_OCCURRED,
                self._on_error_occurred,
                "agent_loop_error"
            )
            
            self._logger.debug("Event system callbacks registered")
            
        except Exception as e:
            self._logger.error(f"Error setting up event callbacks: {e}")
    
    def _on_tool_call_started(self, event):
        """Handle tool call started event."""
        try:
            tool_name = event.data.get("tool_name", "unknown")
            self._logger.debug(f"Tool call started: {tool_name}")
            
            # Start progress monitoring for tool execution
            if hasattr(self, 'progress_monitor'):
                self.progress_monitor.start_operation(
                    f"tool_{event.data.get('call_id', 'unknown')}",
                    f"Executing {tool_name}",
                    1  # Simple tool execution is 1 step
                )
                
        except Exception as e:
            self._logger.error(f"Error handling tool call started event: {e}")
    
    def _on_tool_call_completed(self, event):
        """Handle tool call completed event."""
        try:
            tool_name = event.data.get("tool_name", "unknown")
            call_id = event.data.get("call_id", "unknown")
            
            # Complete progress monitoring
            if hasattr(self, 'progress_monitor'):
                self.progress_monitor.complete_operation(
                    f"tool_{call_id}",
                    f"Tool {tool_name} completed"
                )
            
            # Record in memory if successful
            if event.data.get("status") == "success" and hasattr(self, 'memory_manager'):
                self.memory_manager.record_completed_task(
                    f"Tool execution: {tool_name}",
                    event.data.get("workspace_path", ""),
                    [tool_name],
                    event.data.get("result", "Tool executed successfully"),
                    self._current_session_id or "unknown",
                    {"tool_call_id": call_id}
                )
                
        except Exception as e:
            self._logger.error(f"Error handling tool call completed event: {e}")
    
    def _on_error_occurred(self, event):
        """Handle error occurred event."""
        try:
            error_message = event.data.get("error_message", "Unknown error")
            self._logger.warning(f"Error event received: {error_message}")
            
            # Emit error signal for UI
            self.error_occurred.emit(error_message)
            
        except Exception as e:
            self._logger.error(f"Error handling error event: {e}")
    
    def on_model_loaded(self, model):
        """Handle model loaded event from main app."""
        try:
            self._logger.info("Model loaded - agent loop ready")
            # Model integration is already handled through gguf_app reference
        except Exception as e:
            self._logger.error(f"Error handling model loaded in agent loop: {e}")