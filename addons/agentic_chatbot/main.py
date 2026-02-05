#!/usr/bin/env python3
"""
Agentic Chatbot Addon - Autonomous agent system with tool-calling capabilities

Features:
- File system operations within secure workspace
- Command execution with security filtering
- Search and analysis tools
- Agent orchestration and conversation management
- Integration with existing GGUF Loader architecture
"""

import os
import json
import logging
import traceback
from typing import Optional, Any, Dict, List
from pathlib import Path
from dataclasses import asdict

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QObject, Signal

from .agent_controller import AgentController
from .agent_loop import AgentLoop
from .tool_registry import ToolRegistry
from .security.sandbox import SandboxValidator
from .security.command_filter import CommandFilter
from .safety_monitor import SafetyMonitor
from .streaming_handler import StreamingHandler
from .memory_manager import MemoryManager
from .progress_monitor import ProgressMonitor
from .event_system import EventSystem
from .agent_config import get_config_manager, AgentConfig


class AgenticChatbotAddon(QObject):
    """
    Main addon class for the agentic chatbot system.
    
    Provides autonomous agent capabilities including:
    - Tool-calling for file operations and command execution
    - Secure workspace sandboxing
    - Agent conversation management
    - Integration with existing GGUF Loader components
    """
    
    # Signals
    addon_started = Signal()
    addon_stopped = Signal()
    agent_session_created = Signal(str)  # session_id
    tool_call_executed = Signal(dict)    # tool call result
    
    def __init__(self, gguf_app_instance: Any):
        """
        Initialize the agentic chatbot addon.
        
        Args:
            gguf_app_instance: Reference to the main GGUF Loader application
        """
        super().__init__()
        
        # Store reference to main app
        self.gguf_app = gguf_app_instance
        
        # Initialize configuration manager
        self._config_manager = get_config_manager()
        self._config = self._config_manager.get_config()
        
        # Setup logging
        self._logger = logging.getLogger(__name__)
        
        # Initialize core components
        self._agent_controller: Optional[AgentController] = None
        self._agent_loop: Optional[AgentLoop] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._sandbox_validator: Optional[SandboxValidator] = None
        self._command_filter: Optional[CommandFilter] = None
        self._safety_monitor: Optional[SafetyMonitor] = None
        self._streaming_handler: Optional[StreamingHandler] = None
        self._memory_manager: Optional[MemoryManager] = None
        self._progress_monitor: Optional[ProgressMonitor] = None
        self._event_system: Optional[EventSystem] = None
        self._is_running = False
        
        # Connect to main app signals if available
        self._connect_to_main_app()
    
    def get_config(self) -> AgentConfig:
        """
        Get current agent configuration.
        
        Returns:
            AgentConfig: Current configuration
        """
        return self._config
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """
        Update agent configuration.
        
        Args:
            updates: Configuration updates
            
        Returns:
            bool: True if updated successfully
        """
        try:
            success = self._config_manager.update_config(updates)
            if success:
                self._config = self._config_manager.get_config()
                self._logger.info("Agent configuration updated")
            return success
        except Exception as e:
            self._logger.error(f"Failed to update configuration: {e}")
            return False
    
    def _connect_to_main_app(self):
        """Connect to main application signals for model status updates."""
        try:
            if hasattr(self.gguf_app, 'model_loaded'):
                self.gguf_app.model_loaded.connect(self._on_model_loaded)
            if hasattr(self.gguf_app, 'generation_finished'):
                self.gguf_app.generation_finished.connect(self._on_generation_finished)
            if hasattr(self.gguf_app, 'generation_error'):
                self.gguf_app.generation_error.connect(self._on_generation_error)
            
            # Connect to additional main app signals if available
            if hasattr(self.gguf_app, 'model_unloaded'):
                self.gguf_app.model_unloaded.connect(self._on_model_unloaded)
            if hasattr(self.gguf_app, 'generation_started'):
                self.gguf_app.generation_started.connect(self._on_generation_started)
                
        except Exception as e:
            self._logger.debug(f"Could not connect to main app signals: {e}")
    
    def start(self) -> bool:
        """
        Start the agentic chatbot addon.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self._is_running:
            self._logger.warning("Addon is already running")
            return True
        
        try:
            self._logger.info("Starting Agentic Chatbot addon")
            
            # Initialize security components with comprehensive error handling
            try:
                workspace_path = Path(self._config.workspace.default_workspace)
                if self._config.workspace.auto_create_workspace:
                    workspace_path.mkdir(parents=True, exist_ok=True)
                
                self._sandbox_validator = SandboxValidator(workspace_path)
                self._command_filter = CommandFilter(asdict(self._config.security))
            except Exception as e:
                self._logger.error(f"Failed to initialize security components: {e}")
                return False
            
            # Initialize advanced features with error handling
            try:
                self._event_system = EventSystem(self._config.to_dict())
                self._streaming_handler = StreamingHandler(self._config.to_dict())
                self._memory_manager = MemoryManager(self._config.to_dict())
                self._progress_monitor = ProgressMonitor(self._config.to_dict())
                self._safety_monitor = SafetyMonitor(self._config.to_dict(), parent_widget=None)
            except Exception as e:
                self._logger.error(f"Failed to initialize advanced features: {e}")
                # Continue with basic functionality
                self._logger.warning("Continuing with basic functionality only")
            
            # Initialize tool registry with safety monitor
            try:
                self._tool_registry = ToolRegistry(
                    self._sandbox_validator, 
                    self._command_filter,
                    self._safety_monitor
                )
            except Exception as e:
                self._logger.error(f"Failed to initialize tool registry: {e}")
                return False
            
            # Initialize agent controller
            try:
                self._agent_controller = AgentController(
                    self.gguf_app,
                    self._tool_registry,
                    self._config.to_dict()
                )
            except Exception as e:
                self._logger.error(f"Failed to initialize agent controller: {e}")
                return False
            
            # Initialize agent loop
            try:
                self._agent_loop = AgentLoop(
                    self.gguf_app,
                    self._tool_registry,
                    self._config.to_dict()
                )
            except Exception as e:
                self._logger.error(f"Failed to initialize agent loop: {e}")
                return False
            
            # Connect signals with error handling
            try:
                self._connect_component_signals()
            except Exception as e:
                self._logger.error(f"Failed to connect component signals: {e}")
                # Continue without some signal connections
                self._logger.warning("Some signal connections failed, continuing with reduced functionality")
            
            self._is_running = True
            self.addon_started.emit()
            self._logger.info("Agentic Chatbot addon started successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to start Agentic Chatbot addon: {e}")
            self._logger.debug(f"Addon start traceback: {traceback.format_exc()}")
            
            # Cleanup on failure
            try:
                self._cleanup_on_failure()
            except Exception as cleanup_error:
                self._logger.error(f"Error during cleanup: {cleanup_error}")
            
            return False
    
    def _connect_component_signals(self):
        """Connect signals between components with error handling."""
        try:
            # Connect signals
            self._agent_controller.session_created.connect(
                lambda session_id: self.agent_session_created.emit(session_id)
            )
            self._tool_registry.tool_executed.connect(
                lambda result: self.tool_call_executed.emit(result)
            )
            
            # Connect agent loop to agent controller
            if self._agent_loop:
                self._agent_loop.tool_call_requested.connect(self._on_tool_call_requested)
                self._agent_loop.tool_result_received.connect(self._on_tool_result_received)
                self._agent_loop.response_generated.connect(self._on_response_generated)
                self._agent_loop.error_occurred.connect(self._on_agent_error)
            
            # Connect event system to components
            if self._event_system:
                self._event_system.register_callback(
                    "tool_call_started", 
                    self._on_tool_call_started_event,
                    "main_addon_tool_start"
                )
                self._event_system.register_callback(
                    "tool_call_completed", 
                    self._on_tool_call_completed_event,
                    "main_addon_tool_complete"
                )
                self._event_system.register_callback(
                    "error_occurred", 
                    self._on_error_event,
                    "main_addon_error"
                )
        except Exception as e:
            self._logger.error(f"Error connecting component signals: {e}")
            raise
    
    def _cleanup_on_failure(self):
        """Cleanup resources when startup fails."""
        try:
            if self._agent_controller:
                self._agent_controller.stop()
                self._agent_controller = None
            
            if self._agent_loop:
                if self._agent_loop.isRunning():
                    self._agent_loop.stop_processing()
                    self._agent_loop.wait(1000)
                self._agent_loop = None
            
            if self._event_system:
                self._event_system.shutdown()
                self._event_system = None
            
            # Reset other components
            self._tool_registry = None
            self._sandbox_validator = None
            self._command_filter = None
            self._safety_monitor = None
            self._streaming_handler = None
            self._memory_manager = None
            self._progress_monitor = None
            
        except Exception as e:
            self._logger.error(f"Error during cleanup: {e}")
    
    def stop(self) -> bool:
        """
        Stop the agentic chatbot addon and cleanup resources.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self._is_running:
            self._logger.warning("Addon is not running")
            return True
        
        try:
            self._logger.info("Stopping Agentic Chatbot addon")
            
            # Stop agent controller
            if self._agent_controller:
                self._agent_controller.stop()
                self._agent_controller = None
            
            # Stop agent loop
            if self._agent_loop:
                if self._agent_loop.isRunning():
                    self._agent_loop.stop_processing()
                    self._agent_loop.wait(1000)  # Wait up to 1 second
                self._agent_loop = None
            
            # Cleanup components
            if self._event_system:
                self._event_system.shutdown()
                self._event_system = None
            
            self._tool_registry = None
            self._sandbox_validator = None
            self._command_filter = None
            self._safety_monitor = None
            self._streaming_handler = None
            self._memory_manager = None
            self._progress_monitor = None
            
            self._is_running = False
            self.addon_stopped.emit()
            self._logger.info("Agentic Chatbot addon stopped successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to stop Agentic Chatbot addon: {e}")
            return False
    
    def create_agent_session(self, workspace_path: str) -> Optional[str]:
        """
        Create a new agent session with specified workspace.
        
        Args:
            workspace_path: Path to the workspace directory
            
        Returns:
            Optional[str]: Session ID if created successfully, None otherwise
        """
        if not self._is_running or not self._agent_controller:
            self._logger.error("Addon is not running")
            return None
        
        try:
            return self._agent_controller.create_session(workspace_path)
        except Exception as e:
            self._logger.error(f"Failed to create agent session: {e}")
            return None
    
    def _on_model_loaded(self, model):
        """Handle model loaded event from main app."""
        try:
            self._logger.info("Model loaded - agentic chatbot is ready")
            if self._agent_controller:
                self._agent_controller.on_model_loaded(model)
            if self._agent_loop:
                # Notify agent loop that model is ready
                self._agent_loop.on_model_loaded(model)
        except Exception as e:
            self._logger.error(f"Error handling model loaded: {e}")
    
    def _on_model_unloaded(self):
        """Handle model unloaded event from main app."""
        try:
            self._logger.info("Model unloaded - agentic chatbot paused")
            if self._agent_loop and self._agent_loop.is_processing():
                self._agent_loop.stop_processing()
        except Exception as e:
            self._logger.error(f"Error handling model unloaded: {e}")
    
    def _on_generation_started(self):
        """Handle generation started event from main app."""
        try:
            if self._progress_monitor:
                self._progress_monitor.start_operation(
                    "model_generation",
                    "Model generating response",
                    1
                )
        except Exception as e:
            self._logger.error(f"Error handling generation started: {e}")
    
    def _on_generation_finished(self):
        """Handle generation finished event from main app."""
        try:
            if self._agent_controller:
                self._agent_controller.on_generation_finished()
            if self._progress_monitor:
                self._progress_monitor.complete_operation(
                    "model_generation",
                    "Model generation completed"
                )
        except Exception as e:
            self._logger.error(f"Error handling generation finished: {e}")
    
    def _on_generation_error(self, error_message: str):
        """Handle generation error event from main app."""
        try:
            self._logger.error(f"Model generation error: {error_message}")
            if self._agent_controller:
                self._agent_controller.on_generation_error(error_message)
            if self._progress_monitor:
                self._progress_monitor.fail_operation(
                    "model_generation",
                    f"Model generation failed: {error_message}"
                )
            if self._event_system:
                self._event_system.emit_event(
                    "error_occurred",
                    "main_addon",
                    {
                        "error_type": "model_generation_error",
                        "error_message": error_message,
                        "component": "gguf_app"
                    }
                )
        except Exception as e:
            self._logger.error(f"Error handling generation error: {e}")
    
    def _on_tool_call_requested(self, tool_call: dict):
        """Handle tool call request from agent loop."""
        try:
            self._logger.debug(f"Tool call requested: {tool_call.get('tool', 'unknown')}")
            if self._progress_monitor:
                self._progress_monitor.start_operation(
                    f"tool_call_{tool_call.get('call_id', 'unknown')}",
                    f"Executing tool: {tool_call.get('tool', 'unknown')}",
                    1
                )
        except Exception as e:
            self._logger.error(f"Error handling tool call requested: {e}")
    
    def _on_tool_result_received(self, tool_result: dict):
        """Handle tool result from agent loop."""
        try:
            tool_name = tool_result.get('tool_name', 'unknown')
            status = tool_result.get('status', 'unknown')
            call_id = tool_result.get('call_id', 'unknown')
            
            self._logger.debug(f"Tool result received: {tool_name} - {status}")
            
            if self._progress_monitor:
                if status == "success":
                    self._progress_monitor.complete_operation(
                        f"tool_call_{call_id}",
                        f"Tool {tool_name} completed successfully"
                    )
                else:
                    error_msg = tool_result.get('error', 'Unknown error')
                    self._progress_monitor.fail_operation(
                        f"tool_call_{call_id}",
                        f"Tool {tool_name} failed: {error_msg}"
                    )
        except Exception as e:
            self._logger.error(f"Error handling tool result: {e}")
    
    def _on_response_generated(self, response: str):
        """Handle response generated from agent loop."""
        try:
            self._logger.debug("Agent response generated")
            # Response handling can be extended here if needed
        except Exception as e:
            self._logger.error(f"Error handling response generated: {e}")
    
    def _on_agent_error(self, error_message: str):
        """Handle error from agent loop."""
        try:
            self._logger.error(f"Agent loop error: {error_message}")
            if self._event_system:
                self._event_system.emit_event(
                    "error_occurred",
                    "agent_loop",
                    {
                        "error_type": "agent_processing_error",
                        "error_message": error_message,
                        "component": "agent_loop"
                    }
                )
        except Exception as e:
            self._logger.error(f"Error handling agent error: {e}")
    
    def _on_tool_call_started_event(self, event):
        """Handle tool call started event from event system."""
        try:
            tool_name = event.data.get('tool_name', 'unknown')
            self._logger.debug(f"Tool call started event: {tool_name}")
        except Exception as e:
            self._logger.error(f"Error handling tool call started event: {e}")
    
    def _on_tool_call_completed_event(self, event):
        """Handle tool call completed event from event system."""
        try:
            tool_name = event.data.get('tool_name', 'unknown')
            status = event.data.get('status', 'unknown')
            self._logger.debug(f"Tool call completed event: {tool_name} - {status}")
        except Exception as e:
            self._logger.error(f"Error handling tool call completed event: {e}")
    
    def _on_error_event(self, event):
        """Handle error event from event system."""
        try:
            error_message = event.data.get('error_message', 'Unknown error')
            component = event.data.get('component', 'unknown')
            self._logger.warning(f"Error event from {component}: {error_message}")
        except Exception as e:
            self._logger.error(f"Error handling error event: {e}")
    
    def is_running(self) -> bool:
        """
        Check if the addon is currently running.
        
        Returns:
            bool: True if addon is running, False otherwise
        """
        return self._is_running
    
    def get_active_sessions(self) -> List[str]:
        """
        Get list of active agent session IDs.
        
        Returns:
            List[str]: List of active session IDs
        """
        if self._agent_controller:
            return self._agent_controller.get_active_sessions()
        return []
    
    def get_agent_loop(self) -> Optional[AgentLoop]:
        """
        Get the agent loop instance.
        
        Returns:
            Optional[AgentLoop]: Agent loop if available
        """
        return self._agent_loop
    
    def get_tool_registry(self) -> Optional[ToolRegistry]:
        """
        Get the tool registry instance.
        
        Returns:
            Optional[ToolRegistry]: Tool registry if available
        """
        return self._tool_registry


# Addon registration function for GGUF Loader addon system
def register(parent=None):
    """
    Register function called by the GGUF Loader addon system.
    
    Args:
        parent: Parent widget (might be dialog or main window)
        
    Returns:
        QWidget: Status widget for the addon sidebar, or None for background addons
    """
    try:
        # Find the main GGUF Loader application
        gguf_app = None
        
        # First, try to use parent directly if it's the main app
        if parent and hasattr(parent, 'model') and hasattr(parent, 'model_loaded'):
            gguf_app = parent
        else:
            # If parent is a dialog or other widget, try to find the main window
            current_widget = parent
            while current_widget is not None:
                # Check if this widget is the main AIChat window
                if hasattr(current_widget, 'model') and hasattr(current_widget, 'model_loaded'):
                    gguf_app = current_widget
                    break
                
                # Try parent widget
                current_widget = current_widget.parent() if hasattr(current_widget, 'parent') else None
            
            # If still not found, try to get it from QApplication
            if gguf_app is None:
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    # Look through all top-level widgets
                    for widget in app.topLevelWidgets():
                        if hasattr(widget, 'model') and hasattr(widget, 'model_loaded'):
                            gguf_app = widget
                            break
        
        if gguf_app is None:
            logging.error("Could not find main GGUF Loader application instance")
            return None
        
        logging.info(f"Found GGUF app: {type(gguf_app).__name__}")
        
        # Stop existing addon if running
        if hasattr(gguf_app, '_agentic_chatbot_addon') and gguf_app._agentic_chatbot_addon:
            gguf_app._agentic_chatbot_addon.stop()
        
        # Create and start the addon
        addon = AgenticChatbotAddon(gguf_app)
        success = addon.start()
        
        if success:
            # Store addon reference in gguf_app for lifecycle management
            gguf_app._agentic_chatbot_addon = addon
            
            # Create status widget for addon sidebar
            from .status_widget import AgenticChatbotStatusWidget
            status_widget = AgenticChatbotStatusWidget(addon)
            
            return status_widget
        else:
            logging.error("Failed to start Agentic Chatbot addon")
            return None
        
    except Exception as e:
        logging.error(f"Failed to register Agentic Chatbot addon: {e}")
        return None
    
    def get_streaming_handler(self) -> Optional[StreamingHandler]:
        """
        Get the streaming handler instance.
        
        Returns:
            Optional[StreamingHandler]: Streaming handler if available
        """
        return self._streaming_handler
    
    def get_memory_manager(self) -> Optional[MemoryManager]:
        """
        Get the memory manager instance.
        
        Returns:
            Optional[MemoryManager]: Memory manager if available
        """
        return self._memory_manager
    
    def get_progress_monitor(self) -> Optional[ProgressMonitor]:
        """
        Get the progress monitor instance.
        
        Returns:
            Optional[ProgressMonitor]: Progress monitor if available
        """
        return self._progress_monitor
    
    def get_safety_monitor(self) -> Optional[SafetyMonitor]:
        """
        Get the safety monitor instance.
        
        Returns:
            Optional[SafetyMonitor]: Safety monitor if available
        """
        return self._safety_monitor
    
    def get_event_system(self) -> Optional[EventSystem]:
        """
        Get the event system instance.
        
        Returns:
            Optional[EventSystem]: Event system if available
        """
        return self._event_system
    
    def get_addon_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the addon and its components.
        
        Returns:
            Dict[str, Any]: Addon statistics
        """
        stats = {
            "is_running": self._is_running,
            "active_sessions": len(self.get_active_sessions()),
            "components": {
                "agent_controller": self._agent_controller is not None,
                "agent_loop": self._agent_loop is not None,
                "tool_registry": self._tool_registry is not None,
                "sandbox_validator": self._sandbox_validator is not None,
                "command_filter": self._command_filter is not None,
                "safety_monitor": self._safety_monitor is not None,
                "streaming_handler": self._streaming_handler is not None,
                "memory_manager": self._memory_manager is not None,
                "progress_monitor": self._progress_monitor is not None,
                "event_system": self._event_system is not None
            }
        }
        
        # Add component-specific stats if available
        if self._memory_manager:
            stats["memory_stats"] = self._memory_manager.get_memory_stats()
        
        if self._progress_monitor:
            stats["progress_stats"] = self._progress_monitor.get_progress_stats()
        
        if self._safety_monitor:
            stats["safety_stats"] = self._safety_monitor.get_safety_stats()
        
        if self._event_system:
            stats["event_stats"] = self._event_system.get_event_stats()
        
        if self._streaming_handler:
            stats["streaming_stats"] = self._streaming_handler.get_stats()
        
        return stats