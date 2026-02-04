"""
Command Filter - Validates and filters command execution for security
"""

import re
import logging
from typing import List, Dict, Any, Optional


class CommandFilter:
    """
    Validates and filters shell commands for safe execution.
    
    This component provides security by:
    - Maintaining allowlist of safe commands
    - Blocking dangerous commands and patterns
    - Sanitizing command arguments
    - Logging security violations and blocked attempts
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the command filter.
        
        Args:
            config: Configuration dictionary containing security settings
        """
        self._logger = logging.getLogger(__name__)
        
        # Load configuration
        self.allowed_commands = set(config.get('allowed_commands', []))
        self.denied_commands = set(config.get('denied_commands', []))
        self.command_timeout = config.get('command_timeout', 30)
        
        # Dangerous patterns to always block
        self.dangerous_patterns = [
            r'rm\s+-rf\s+/',      # Recursive delete from root
            r'sudo\s+',           # Sudo commands
            r'chmod\s+777',       # Dangerous permissions
            r'>\s*/dev/',         # Writing to device files
            r'\|\s*sh',           # Piping to shell
            r'`.*`',              # Command substitution
            r'\$\(',              # Command substitution
            r'&&\s*rm',           # Chained dangerous commands
            r';\s*rm',            # Sequential dangerous commands
        ]
        
        # Compile regex patterns for efficiency
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.dangerous_patterns]
        
        self._logger.info(f"Initialized command filter with {len(self.allowed_commands)} allowed commands")
        self._logger.debug(f"Allowed commands: {sorted(self.allowed_commands)}")
        self._logger.debug(f"Denied commands: {sorted(self.denied_commands)}")
    
    def validate_command(self, command: str) -> bool:
        """
        Check if a command is allowed for execution.
        
        Args:
            command: Command string to validate
            
        Returns:
            bool: True if command is allowed, False otherwise
        """
        try:
            # Basic validation
            if not command or not command.strip():
                return False
            
            # Clean the command
            clean_command = command.strip()
            
            # Check for dangerous patterns first
            if self._contains_dangerous_patterns(clean_command):
                self._logger.warning(f"Command blocked due to dangerous pattern: {clean_command}")
                return False
            
            # Extract base command (first word)
            base_command = self._extract_base_command(clean_command)
            
            # Check denied commands
            if base_command in self.denied_commands:
                self._logger.warning(f"Command blocked (in deny list): {base_command}")
                return False
            
            # Check allowed commands (if allowlist is defined)
            if self.allowed_commands:
                if base_command not in self.allowed_commands:
                    self._logger.warning(f"Command blocked (not in allow list): {base_command}")
                    return False
            
            return True
            
        except Exception as e:
            self._logger.error(f"Error validating command: {e}")
            return False
    
    def sanitize_command(self, command: str) -> str:
        """
        Sanitize a command for safe execution.
        
        Args:
            command: Command string to sanitize
            
        Returns:
            str: Sanitized command string
            
        Raises:
            SecurityError: If command cannot be safely sanitized
        """
        try:
            # Basic cleaning
            clean_command = command.strip()
            
            # Remove potentially dangerous characters/sequences
            # Note: This is basic sanitization - more sophisticated filtering may be needed
            dangerous_chars = ['|', '&', ';', '`', '$']
            for char in dangerous_chars:
                if char in clean_command:
                    # For now, we'll be strict and reject commands with these characters
                    raise SecurityError(f"Command contains dangerous character '{char}': {clean_command}")
            
            # Validate the sanitized command
            if not self.validate_command(clean_command):
                raise SecurityError(f"Command failed validation after sanitization: {clean_command}")
            
            return clean_command
            
        except SecurityError:
            raise
        except Exception as e:
            raise SecurityError(f"Cannot sanitize command: {e}")
    
    def get_command_info(self, command: str) -> Dict[str, Any]:
        """
        Get detailed information about a command's validation status.
        
        Args:
            command: Command to analyze
            
        Returns:
            Dict[str, Any]: Information about command validation
        """
        try:
            clean_command = command.strip()
            base_command = self._extract_base_command(clean_command)
            
            info = {
                "command": clean_command,
                "base_command": base_command,
                "is_valid": False,
                "validation_errors": [],
                "security_warnings": []
            }
            
            # Check dangerous patterns
            dangerous_matches = []
            for pattern in self.compiled_patterns:
                if pattern.search(clean_command):
                    dangerous_matches.append(pattern.pattern)
            
            if dangerous_matches:
                info["validation_errors"].append(f"Contains dangerous patterns: {dangerous_matches}")
            
            # Check deny list
            if base_command in self.denied_commands:
                info["validation_errors"].append(f"Command '{base_command}' is in deny list")
            
            # Check allow list
            if self.allowed_commands and base_command not in self.allowed_commands:
                info["validation_errors"].append(f"Command '{base_command}' not in allow list")
            
            # Overall validation
            info["is_valid"] = len(info["validation_errors"]) == 0
            
            return info
            
        except Exception as e:
            return {
                "command": command,
                "is_valid": False,
                "validation_errors": [f"Analysis error: {e}"],
                "security_warnings": []
            }
    
    def _extract_base_command(self, command: str) -> str:
        """
        Extract the base command (first word) from a command string.
        
        Args:
            command: Full command string
            
        Returns:
            str: Base command name
        """
        try:
            # Split by whitespace and get first part
            parts = command.split()
            if not parts:
                return ""
            
            base = parts[0]
            
            # Handle common prefixes
            if base.startswith('./') or base.startswith('.\\'):
                base = base[2:]
            
            # Extract just the command name (remove path)
            if '/' in base:
                base = base.split('/')[-1]
            if '\\' in base:
                base = base.split('\\')[-1]
            
            return base.lower()
            
        except Exception:
            return ""
    
    def _contains_dangerous_patterns(self, command: str) -> bool:
        """
        Check if command contains any dangerous patterns.
        
        Args:
            command: Command to check
            
        Returns:
            bool: True if dangerous patterns found
        """
        try:
            for pattern in self.compiled_patterns:
                if pattern.search(command):
                    return True
            return False
        except Exception:
            return True  # Err on the side of caution
    
    def add_allowed_command(self, command: str):
        """
        Add a command to the allow list.
        
        Args:
            command: Command to allow
        """
        self.allowed_commands.add(command.lower())
        self._logger.info(f"Added command to allow list: {command}")
    
    def remove_allowed_command(self, command: str):
        """
        Remove a command from the allow list.
        
        Args:
            command: Command to remove
        """
        self.allowed_commands.discard(command.lower())
        self._logger.info(f"Removed command from allow list: {command}")
    
    def add_denied_command(self, command: str):
        """
        Add a command to the deny list.
        
        Args:
            command: Command to deny
        """
        self.denied_commands.add(command.lower())
        self._logger.info(f"Added command to deny list: {command}")
    
    def remove_denied_command(self, command: str):
        """
        Remove a command from the deny list.
        
        Args:
            command: Command to remove
        """
        self.denied_commands.discard(command.lower())
        self._logger.info(f"Removed command from deny list: {command}")
    
    def get_allowed_commands(self) -> List[str]:
        """
        Get list of allowed commands.
        
        Returns:
            List[str]: Sorted list of allowed commands
        """
        return sorted(self.allowed_commands)
    
    def get_denied_commands(self) -> List[str]:
        """
        Get list of denied commands.
        
        Returns:
            List[str]: Sorted list of denied commands
        """
        return sorted(self.denied_commands)


class SecurityError(Exception):
    """Exception raised for security violations in command filtering."""
    pass