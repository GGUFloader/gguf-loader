"""
Tool Registry - Manages available tools and their execution
"""

import logging
import time
from typing import Dict, List, Optional, Any, Type
from abc import ABC, abstractmethod

from PySide6.QtCore import QObject, Signal

from .security.sandbox import SandboxValidator
from .security.command_filter import CommandFilter
from .safety_monitor import SafetyMonitor


class BaseTool(ABC):
    """
    Abstract base class for all agent tools.
    
    All tools must inherit from this class and implement the required methods
    to provide a consistent interface for the agent system.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this tool."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of what this tool does."""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        Return JSON schema for tool parameters.
        
        Returns:
            Dict[str, Any]: JSON schema describing the tool's parameters
        """
        pass
    
    @abstractmethod
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool with given parameters.
        
        Args:
            parameters: Dictionary of parameters for the tool
            
        Returns:
            Dict[str, Any]: Result dictionary with status, result/error, and metadata
        """
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Validate parameters against the tool's schema.
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            bool: True if parameters are valid, False otherwise
        """
        try:
            # Basic validation - can be enhanced with jsonschema library
            schema = self.get_schema()
            required_params = schema.get("required", [])
            
            # Check required parameters
            for param in required_params:
                if param not in parameters:
                    return False
            
            return True
            
        except Exception:
            return False


class ToolRegistry(QObject):
    """
    Registry for managing and executing agent tools.
    
    This component:
    - Registers available tools
    - Validates tool calls and parameters
    - Executes tools with security validation
    - Provides tool schemas for agent planning
    """
    
    # Signals
    tool_registered = Signal(str)      # tool_name
    tool_executed = Signal(dict)       # execution result
    tool_error = Signal(str, str)      # tool_name, error_message
    
    def __init__(self, sandbox_validator: SandboxValidator, command_filter: CommandFilter, 
                 safety_monitor: Optional[SafetyMonitor] = None):
        """
        Initialize the tool registry.
        
        Args:
            sandbox_validator: Validator for workspace security
            command_filter: Filter for command execution security
            safety_monitor: Optional safety monitor for dangerous operations
        """
        super().__init__()
        
        self.sandbox_validator = sandbox_validator
        self.command_filter = command_filter
        self.safety_monitor = safety_monitor
        self._logger = logging.getLogger(__name__)
        
        # Registry of available tools
        self._tools: Dict[str, BaseTool] = {}
        
        # Execution statistics
        self._execution_stats: Dict[str, Dict[str, Any]] = {}
        
        # Register built-in tools (will be implemented in later tasks)
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """Register built-in tools that are always available."""
        from .tools import (
            ListDirectoryTool,
            ReadFileTool,
            WriteFileTool,
            EditFileTool,
            SearchFilesTool,
            FileMetadataTool,
            DirectoryAnalysisTool,
            ExecuteCommandTool
        )
        
        # Register file system tools by creating instances directly
        try:
            # File system tools with individual error handling
            tools_to_register = []
            
            try:
                list_tool = ListDirectoryTool(self.sandbox_validator)
                tools_to_register.append(list_tool)
            except Exception as e:
                self._logger.error(f"Failed to create ListDirectoryTool: {e}")
            
            try:
                read_tool = ReadFileTool(self.sandbox_validator)
                tools_to_register.append(read_tool)
            except Exception as e:
                self._logger.error(f"Failed to create ReadFileTool: {e}")
            
            try:
                write_tool = WriteFileTool(self.sandbox_validator)
                tools_to_register.append(write_tool)
            except Exception as e:
                self._logger.error(f"Failed to create WriteFileTool: {e}")
            
            try:
                edit_tool = EditFileTool(self.sandbox_validator)
                tools_to_register.append(edit_tool)
            except Exception as e:
                self._logger.error(f"Failed to create EditFileTool: {e}")
            
            # Search tools
            try:
                search_tool = SearchFilesTool(self.sandbox_validator)
                tools_to_register.append(search_tool)
            except Exception as e:
                self._logger.error(f"Failed to create SearchFilesTool: {e}")
            
            try:
                metadata_tool = FileMetadataTool(self.sandbox_validator)
                tools_to_register.append(metadata_tool)
            except Exception as e:
                self._logger.error(f"Failed to create FileMetadataTool: {e}")
            
            try:
                analysis_tool = DirectoryAnalysisTool(self.sandbox_validator)
                tools_to_register.append(analysis_tool)
            except Exception as e:
                self._logger.error(f"Failed to create DirectoryAnalysisTool: {e}")
            
            # Command execution tool
            try:
                execute_tool = ExecuteCommandTool(self.sandbox_validator, self.command_filter)
                tools_to_register.append(execute_tool)
            except Exception as e:
                self._logger.error(f"Failed to create ExecuteCommandTool: {e}")
            
            # Register all successfully created tools
            successful_registrations = 0
            for tool in tools_to_register:
                try:
                    self._tools[tool.name] = tool
                    
                    # Initialize execution stats
                    self._execution_stats[tool.name] = {
                        "total_calls": 0,
                        "successful_calls": 0,
                        "failed_calls": 0,
                        "total_execution_time": 0.0,
                        "last_used": None
                    }
                    self.tool_registered.emit(tool.name)
                    successful_registrations += 1
                    
                except Exception as e:
                    self._logger.error(f"Failed to register tool {tool.name}: {e}")
            
            if successful_registrations > 0:
                self._logger.info(f"Successfully registered {successful_registrations} built-in tools")
            else:
                self._logger.error("Failed to register any built-in tools")
            
        except Exception as e:
            self._logger.error(f"Critical error in built-in tool registration: {e}")
            # Continue with empty tool registry rather than failing completely
    
    def register_tool(self, tool_class: Type[BaseTool]) -> bool:
        """
        Register a new tool class.
        
        Args:
            tool_class: Class that inherits from BaseTool
            
        Returns:
            bool: True if registered successfully, False otherwise
        """
        try:
            # Instantiate the tool
            tool_instance = tool_class()
            
            # Validate tool interface
            if not isinstance(tool_instance, BaseTool):
                raise ValueError(f"Tool must inherit from BaseTool")
            
            tool_name = tool_instance.name
            
            # Check for name conflicts
            if tool_name in self._tools:
                self._logger.warning(f"Tool {tool_name} already registered, overwriting")
            
            # Register the tool
            self._tools[tool_name] = tool_instance
            
            # Initialize execution stats
            self._execution_stats[tool_name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_execution_time": 0.0,
                "last_used": None
            }
            
            self._logger.info(f"Registered tool: {tool_name}")
            self.tool_registered.emit(tool_name)
            
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to register tool: {e}")
            return False
    
    def unregister_tool(self, tool_name: str) -> bool:
        """
        Unregister a tool.
        
        Args:
            tool_name: Name of the tool to unregister
            
        Returns:
            bool: True if unregistered successfully, False otherwise
        """
        try:
            if tool_name not in self._tools:
                self._logger.warning(f"Tool {tool_name} not found")
                return False
            
            del self._tools[tool_name]
            if tool_name in self._execution_stats:
                del self._execution_stats[tool_name]
            
            self._logger.info(f"Unregistered tool: {tool_name}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to unregister tool {tool_name}: {e}")
            return False
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
            
        Returns:
            Dict[str, Any]: Execution result with status, result/error, and metadata
        """
        start_time = time.time()
        
        try:
            # Check if tool exists
            if tool_name not in self._tools:
                error_result = {
                    "status": "error",
                    "error": f"Tool '{tool_name}' not found",
                    "available_tools": list(self._tools.keys()),
                    "execution_time": 0.0
                }
                self.tool_error.emit(tool_name, error_result["error"])
                return error_result
            
            tool = self._tools[tool_name]
            
            # Validate parameters
            if not tool.validate_parameters(parameters):
                error_result = {
                    "status": "error",
                    "error": f"Invalid parameters for tool '{tool_name}'",
                    "schema": tool.get_schema(),
                    "execution_time": time.time() - start_time
                }
                self.tool_error.emit(tool_name, error_result["error"])
                self._update_execution_stats(tool_name, False, time.time() - start_time)
                return error_result
            
            # Safety validation if safety monitor is available
            if self.safety_monitor:
                operation_details = f"Tool: {tool_name}, Parameters: {parameters}"
                is_allowed, violation = self.safety_monitor.validate_operation(
                    "tool_execution", 
                    operation_details,
                    {"tool_name": tool_name, "parameters": parameters}
                )
                
                if not is_allowed:
                    error_result = {
                        "status": "error",
                        "error": f"Tool execution blocked by safety monitor: {violation.rule_id if violation else 'Unknown rule'}",
                        "safety_violation": violation.violation_id if violation else None,
                        "execution_time": time.time() - start_time
                    }
                    self.tool_error.emit(tool_name, error_result["error"])
                    self._update_execution_stats(tool_name, False, time.time() - start_time)
                    return error_result
            
            # Execute the tool
            self._logger.info(f"Executing tool: {tool_name}")
            result = tool.execute(parameters)
            
            # Ensure result has required fields
            if "status" not in result:
                result["status"] = "success" if "error" not in result else "error"
            
            result["execution_time"] = time.time() - start_time
            result["tool_name"] = tool_name
            
            # Update statistics
            success = result["status"] == "success"
            self._update_execution_stats(tool_name, success, result["execution_time"])
            
            self._logger.info(f"Tool {tool_name} executed successfully")
            self.tool_executed.emit(result)
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_result = {
                "status": "error",
                "error": f"Tool execution failed: {str(e)}",
                "tool_name": tool_name,
                "execution_time": execution_time
            }
            
            self._logger.error(f"Tool execution error: {e}")
            self.tool_error.emit(tool_name, str(e))
            self._update_execution_stats(tool_name, False, execution_time)
            
            return error_result
    
    def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names.
        
        Returns:
            List[str]: List of registered tool names
        """
        return list(self._tools.keys())
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get JSON schema for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Optional[Dict[str, Any]]: Tool schema if found, None otherwise
        """
        if tool_name in self._tools:
            return self._tools[tool_name].get_schema()
        return None
    
    def get_tool_schemas(self) -> Dict[str, Dict[str, Any]]:
        """
        Get JSON schemas for all registered tools.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping tool names to their schemas
        """
        schemas = {}
        for tool_name, tool in self._tools.items():
            try:
                schemas[tool_name] = {
                    "name": tool_name,
                    "description": tool.description,
                    "schema": tool.get_schema()
                }
            except Exception as e:
                self._logger.error(f"Error getting schema for tool {tool_name}: {e}")
        
        return schemas
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Optional[Dict[str, Any]]: Tool information if found, None otherwise
        """
        if tool_name not in self._tools:
            return None
        
        tool = self._tools[tool_name]
        stats = self._execution_stats.get(tool_name, {})
        
        return {
            "name": tool_name,
            "description": tool.description,
            "schema": tool.get_schema(),
            "statistics": stats
        }
    
    def get_execution_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get execution statistics for all tools.
        
        Returns:
            Dict[str, Dict[str, Any]]: Execution statistics by tool name
        """
        return self._execution_stats.copy()
    
    def _update_execution_stats(self, tool_name: str, success: bool, execution_time: float):
        """Update execution statistics for a tool."""
        try:
            if tool_name not in self._execution_stats:
                self._execution_stats[tool_name] = {
                    "total_calls": 0,
                    "successful_calls": 0,
                    "failed_calls": 0,
                    "total_execution_time": 0.0,
                    "last_used": None
                }
            
            stats = self._execution_stats[tool_name]
            stats["total_calls"] += 1
            stats["total_execution_time"] += execution_time
            stats["last_used"] = time.time()
            
            if success:
                stats["successful_calls"] += 1
            else:
                stats["failed_calls"] += 1
                
        except Exception as e:
            self._logger.error(f"Error updating execution stats: {e}")
    
    def clear_stats(self):
        """Clear all execution statistics."""
        for tool_name in self._execution_stats:
            self._execution_stats[tool_name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_execution_time": 0.0,
                "last_used": None
            }