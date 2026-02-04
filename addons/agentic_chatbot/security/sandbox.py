"""
Sandbox Validator - Enforces workspace boundaries and path security
"""

import os
import logging
from pathlib import Path
from typing import Union, Optional


class SandboxValidator:
    """
    Validates file system operations to ensure they remain within workspace boundaries.
    
    This component provides security by:
    - Preventing path traversal attacks (../, symlinks, absolute paths)
    - Enforcing workspace confinement for all file operations
    - Resolving canonical paths and validating against workspace root
    - Logging security violations for audit trails
    """
    
    def __init__(self, workspace_root: Union[str, Path]):
        """
        Initialize the sandbox validator.
        
        Args:
            workspace_root: Root directory for the workspace
            
        Raises:
            ValueError: If workspace_root is invalid
        """
        self._logger = logging.getLogger(__name__)
        
        # Resolve and validate workspace root
        try:
            self.workspace_root = Path(workspace_root).resolve()
            
            # Ensure workspace exists
            if not self.workspace_root.exists():
                self.workspace_root.mkdir(parents=True, exist_ok=True)
                self._logger.info(f"Created workspace directory: {self.workspace_root}")
            
            if not self.workspace_root.is_dir():
                raise ValueError(f"Workspace root is not a directory: {self.workspace_root}")
            
            self._logger.info(f"Initialized sandbox validator with workspace: {self.workspace_root}")
            
        except Exception as e:
            raise ValueError(f"Invalid workspace root: {e}")
    
    def validate_path(self, path: Union[str, Path]) -> Path:
        """
        Validate that a path is within the workspace boundaries.
        
        Args:
            path: Path to validate (can be relative or absolute)
            
        Returns:
            Path: Resolved absolute path within workspace
            
        Raises:
            SecurityError: If path is outside workspace or contains traversal attempts
            ValueError: If path is invalid
        """
        try:
            # Convert to Path object
            if isinstance(path, str):
                path_obj = Path(path)
            else:
                path_obj = path
            
            # Handle relative paths by making them relative to workspace
            if not path_obj.is_absolute():
                resolved_path = (self.workspace_root / path_obj).resolve()
            else:
                resolved_path = path_obj.resolve()
            
            # Check if resolved path is within workspace
            if not self._is_within_workspace(resolved_path):
                error_msg = f"Path outside workspace: {path} -> {resolved_path}"
                self._logger.warning(f"Security violation: {error_msg}")
                raise SecurityError(error_msg)
            
            # Additional security checks
            self._check_path_security(resolved_path)
            
            return resolved_path
            
        except SecurityError:
            raise
        except Exception as e:
            raise ValueError(f"Invalid path: {e}")
    
    def is_safe_path(self, path: Union[str, Path]) -> bool:
        """
        Check if a path is safe for operations without raising exceptions.
        
        Args:
            path: Path to check
            
        Returns:
            bool: True if path is safe, False otherwise
        """
        try:
            self.validate_path(path)
            return True
        except (SecurityError, ValueError):
            return False
    
    def sanitize_path(self, path: str) -> Path:
        """
        Convert a relative path to a safe absolute path within workspace.
        
        Args:
            path: Relative path string
            
        Returns:
            Path: Safe absolute path within workspace
            
        Raises:
            SecurityError: If path cannot be safely resolved
        """
        try:
            # Remove any leading/trailing whitespace
            clean_path = path.strip()
            
            # Remove any leading slashes to force relative interpretation
            while clean_path.startswith('/') or clean_path.startswith('\\'):
                clean_path = clean_path[1:]
            
            # Convert to Path and resolve relative to workspace
            path_obj = Path(clean_path)
            
            # Check for obvious traversal attempts
            if '..' in path_obj.parts:
                raise SecurityError(f"Path traversal attempt detected: {path}")
            
            # Resolve relative to workspace
            resolved_path = (self.workspace_root / path_obj).resolve()
            
            # Final validation
            return self.validate_path(resolved_path)
            
        except Exception as e:
            raise SecurityError(f"Cannot sanitize path: {e}")
    
    def get_relative_path(self, path: Union[str, Path]) -> Path:
        """
        Get path relative to workspace root.
        
        Args:
            path: Absolute path within workspace
            
        Returns:
            Path: Path relative to workspace root
            
        Raises:
            SecurityError: If path is not within workspace
        """
        try:
            validated_path = self.validate_path(path)
            return validated_path.relative_to(self.workspace_root)
        except Exception as e:
            raise SecurityError(f"Cannot get relative path: {e}")
    
    def _is_within_workspace(self, path: Path) -> bool:
        """
        Check if a resolved path is within the workspace.
        
        Args:
            path: Resolved absolute path
            
        Returns:
            bool: True if path is within workspace
        """
        try:
            # Check if path is under workspace root
            path.relative_to(self.workspace_root)
            return True
        except ValueError:
            return False
    
    def _check_path_security(self, path: Path):
        """
        Perform additional security checks on a path.
        
        Args:
            path: Path to check
            
        Raises:
            SecurityError: If path fails security checks
        """
        try:
            # Check for hidden files/directories (optional security measure)
            for part in path.parts:
                if part.startswith('.') and part not in ['.', '..']:
                    self._logger.debug(f"Hidden file/directory access: {path}")
                    # Note: Not blocking hidden files by default, just logging
            
            # Check for system directories (if path exists)
            if path.exists():
                # Additional checks can be added here for system directories
                pass
            
        except Exception as e:
            self._logger.debug(f"Security check warning: {e}")
    
    def list_workspace_contents(self, relative_path: str = "") -> list:
        """
        Safely list contents of a directory within the workspace.
        
        Args:
            relative_path: Path relative to workspace root
            
        Returns:
            list: List of file/directory names
            
        Raises:
            SecurityError: If path is invalid or outside workspace
        """
        try:
            target_path = self.sanitize_path(relative_path)
            
            if not target_path.exists():
                return []
            
            if not target_path.is_dir():
                raise ValueError(f"Path is not a directory: {relative_path}")
            
            contents = []
            for item in target_path.iterdir():
                contents.append(item.name)
            
            return sorted(contents)
            
        except Exception as e:
            raise SecurityError(f"Cannot list directory contents: {e}")
    
    def get_workspace_root(self) -> Path:
        """
        Get the workspace root path.
        
        Returns:
            Path: Workspace root directory
        """
        return self.workspace_root


class SecurityError(Exception):
    """Exception raised for security violations in sandbox operations."""
    pass