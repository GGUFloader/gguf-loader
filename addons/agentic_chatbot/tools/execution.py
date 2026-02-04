"""
Command Execution Tool - Implements safe command execution for the agentic chatbot

This module provides secure command execution within the workspace sandbox:
- ExecuteCommandTool: Execute shell commands with timeout and output capture
- Integrates with command filter for security validation
- Provides process management and error handling
"""

import os
import subprocess
import threading
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from ..tool_registry import BaseTool
from ..security.sandbox import SandboxValidator, SecurityError
from ..security.command_filter import CommandFilter, SecurityError as CommandSecurityError


class ExecuteCommandTool(BaseTool):
    """Tool for executing shell commands safely with timeout and output capture."""
    
    def __init__(self, sandbox_validator: SandboxValidator, command_filter: CommandFilter):
        self.sandbox_validator = sandbox_validator
        self.command_filter = command_filter
        self._logger = logging.getLogger(__name__)
        
        # Default timeout from command filter config
        self.default_timeout = getattr(command_filter, 'command_timeout', 30)
    
    @property
    def name(self) -> str:
        return "execute_command"
    
    @property
    def description(self) -> str:
        return "Execute shell commands safely with timeout and output capture within the workspace"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
                },
                "working_directory": {
                    "type": "string",
                    "description": "Working directory for command execution (relative to workspace root)",
                    "default": ""
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds for command execution",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 300
                },
                "capture_output": {
                    "type": "boolean",
                    "description": "Whether to capture command output",
                    "default": True
                },
                "shell": {
                    "type": "boolean",
                    "description": "Whether to execute command through shell",
                    "default": True
                }
            },
            "required": ["command"]
        }
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the command with security validation and timeout."""
        try:
            command = parameters["command"]
            working_directory = parameters.get("working_directory", "")
            timeout = parameters.get("timeout", self.default_timeout)
            capture_output = parameters.get("capture_output", True)
            use_shell = parameters.get("shell", True)
            
            # Validate and sanitize command
            try:
                if not self.command_filter.validate_command(command):
                    command_info = self.command_filter.get_command_info(command)
                    return {
                        "status": "error",
                        "error": f"Command blocked by security filter: {command}",
                        "security_info": command_info,
                        "allowed_commands": self.command_filter.get_allowed_commands()
                    }
                
                sanitized_command = self.command_filter.sanitize_command(command)
                
            except CommandSecurityError as e:
                return {
                    "status": "error",
                    "error": f"Security violation: {str(e)}",
                    "command": command
                }
            
            # Validate working directory
            if working_directory:
                try:
                    work_dir = self.sandbox_validator.sanitize_path(working_directory)
                    if not work_dir.exists():
                        return {"status": "error", "error": f"Working directory does not exist: {working_directory}"}
                    if not work_dir.is_dir():
                        return {"status": "error", "error": f"Working directory is not a directory: {working_directory}"}
                except SecurityError as e:
                    return {"status": "error", "error": f"Invalid working directory: {str(e)}"}
            else:
                work_dir = self.sandbox_validator.workspace_root
            
            # Execute command
            start_time = time.time()
            result = self._execute_command_safe(
                sanitized_command, work_dir, timeout, capture_output, use_shell
            )
            execution_time = time.time() - start_time
            
            result["execution_time"] = execution_time
            result["command"] = sanitized_command
            result["working_directory"] = str(self.sandbox_validator.get_relative_path(work_dir))
            
            return result
            
        except Exception as e:
            return {"status": "error", "error": f"Command execution failed: {str(e)}"}
    
    def _execute_command_safe(self, command: str, work_dir: Path, timeout: int,
                             capture_output: bool, use_shell: bool) -> Dict[str, Any]:
        """Execute command with proper process management and timeout handling."""
        try:
            self._logger.info(f"Executing command: {command} in {work_dir}")
            
            # Prepare environment
            env = os.environ.copy()
            
            # Configure subprocess parameters
            subprocess_kwargs = {
                'cwd': str(work_dir),
                'env': env,
                'shell': use_shell,
                'timeout': timeout
            }
            
            if capture_output:
                subprocess_kwargs.update({
                    'stdout': subprocess.PIPE,
                    'stderr': subprocess.PIPE,
                    'text': True,
                    'encoding': 'utf-8',
                    'errors': 'replace'
                })
            
            # Execute command
            try:
                if use_shell:
                    result = subprocess.run(command, **subprocess_kwargs)
                else:
                    # Split command for non-shell execution
                    cmd_parts = command.split()
                    result = subprocess.run(cmd_parts, **subprocess_kwargs)
                
                # Prepare response
                response = {
                    "status": "success" if result.returncode == 0 else "error",
                    "return_code": result.returncode
                }
                
                if capture_output:
                    response.update({
                        "stdout": result.stdout or "",
                        "stderr": result.stderr or "",
                        "output_length": len(result.stdout or "") + len(result.stderr or "")
                    })
                
                if result.returncode != 0:
                    response["error"] = f"Command failed with return code {result.returncode}"
                
                self._logger.info(f"Command completed with return code: {result.returncode}")
                return response
                
            except subprocess.TimeoutExpired as e:
                self._logger.warning(f"Command timed out after {timeout} seconds: {command}")
                return {
                    "status": "error",
                    "error": f"Command timed out after {timeout} seconds",
                    "return_code": -1,
                    "stdout": e.stdout.decode('utf-8', errors='replace') if e.stdout else "",
                    "stderr": e.stderr.decode('utf-8', errors='replace') if e.stderr else "",
                    "timeout": timeout
                }
            
            except subprocess.CalledProcessError as e:
                self._logger.error(f"Command failed: {command}, return code: {e.returncode}")
                return {
                    "status": "error",
                    "error": f"Command failed with return code {e.returncode}",
                    "return_code": e.returncode,
                    "stdout": e.stdout or "",
                    "stderr": e.stderr or ""
                }
            
            except FileNotFoundError as e:
                return {
                    "status": "error",
                    "error": f"Command not found: {str(e)}",
                    "return_code": -1
                }
            
            except PermissionError as e:
                return {
                    "status": "error",
                    "error": f"Permission denied: {str(e)}",
                    "return_code": -1
                }
                
        except Exception as e:
            self._logger.error(f"Unexpected error executing command: {e}")
            return {
                "status": "error",
                "error": f"Unexpected execution error: {str(e)}",
                "return_code": -1
            }
    
    def get_allowed_commands(self) -> List[str]:
        """Get list of commands allowed by the security filter."""
        return self.command_filter.get_allowed_commands()
    
    def get_denied_commands(self) -> List[str]:
        """Get list of commands denied by the security filter."""
        return self.command_filter.get_denied_commands()
    
    def validate_command_syntax(self, command: str) -> Dict[str, Any]:
        """Validate command syntax and security without executing."""
        return self.command_filter.get_command_info(command)