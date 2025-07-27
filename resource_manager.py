"""
Resource Manager - Handles resource discovery and path resolution for packaged distribution

This module provides utilities to locate resources (icons, configs, etc.) that work
correctly whether the application is running from:
- Development environment
- Installed pip package
- PyInstaller executable
- Frozen executable
"""

import os
import sys
from pathlib import Path
from typing import Optional, Union
import importlib.resources
import importlib.util


class ResourceManager:
    """Manages resource discovery and path resolution for different deployment scenarios."""
    
    def __init__(self, package_name: str = "ggufloader"):
        self.package_name = package_name
        self._base_path = None
        self._deployment_type = None
        self._detect_deployment_type()
    
    def _detect_deployment_type(self):
        """Detect how the application is being run."""
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                self._deployment_type = 'pyinstaller'
                self._base_path = sys._MEIPASS
            else:
                self._deployment_type = 'frozen'
                self._base_path = os.path.dirname(sys.executable)
        else:
            # Check if we're running from an installed package
            try:
                spec = importlib.util.find_spec(self.package_name)
                if spec and spec.origin:
                    self._deployment_type = 'installed_package'
                    self._base_path = os.path.dirname(spec.origin)
                else:
                    self._deployment_type = 'development'
                    self._base_path = os.path.abspath(".")
            except ImportError:
                self._deployment_type = 'development'
                self._base_path = os.path.abspath(".")
    
    def get_resource_path(self, relative_path: str) -> str:
        """
        Get absolute path for a resource file.
        
        Args:
            relative_path: Path relative to the package root or application root
            
        Returns:
            Absolute path to the resource
        """
        if self._deployment_type == 'pyinstaller':
            return os.path.join(self._base_path, relative_path)
        
        elif self._deployment_type == 'installed_package':
            # For installed packages, try multiple locations
            candidates = [
                os.path.join(self._base_path, relative_path),  # Same directory as package
                os.path.join(os.path.dirname(self._base_path), relative_path),  # Parent directory
                os.path.join(self._base_path, "..", relative_path),  # Explicit parent
            ]
            
            for candidate in candidates:
                if os.path.exists(candidate):
                    return os.path.abspath(candidate)
            
            # If not found, return the first candidate (might be created later)
            return os.path.abspath(candidates[0])
        
        elif self._deployment_type == 'frozen':
            return os.path.join(self._base_path, relative_path)
        
        else:  # development
            return os.path.join(self._base_path, relative_path)
    
    def get_package_resource(self, resource_name: str, package: Optional[str] = None) -> Optional[str]:
        """
        Get a resource from within the package using importlib.resources.
        
        Args:
            resource_name: Name of the resource file
            package: Package name (defaults to self.package_name)
            
        Returns:
            Path to the resource or None if not found
        """
        if package is None:
            package = self.package_name
        
        try:
            # Try using importlib.resources (Python 3.9+)
            if hasattr(importlib.resources, 'files'):
                files = importlib.resources.files(package)
                resource_path = files / resource_name
                if resource_path.is_file():
                    return str(resource_path)
            
            # Fallback for older Python versions
            elif hasattr(importlib.resources, 'path'):
                with importlib.resources.path(package, resource_name) as path:
                    if path.exists():
                        return str(path)
        
        except (ImportError, FileNotFoundError, ModuleNotFoundError):
            pass
        
        return None
    
    def find_icon(self, icon_name: str = "icon.ico") -> str:
        """
        Find the application icon in various possible locations.
        
        Args:
            icon_name: Name of the icon file
            
        Returns:
            Path to the icon file
        """
        # Try package resource first
        package_icon = self.get_package_resource(icon_name)
        if package_icon and os.path.exists(package_icon):
            return package_icon
        
        # Try standard resource path
        standard_path = self.get_resource_path(icon_name)
        if os.path.exists(standard_path):
            return standard_path
        
        # Try common locations
        common_locations = [
            icon_name,  # Current directory
            f"assets/{icon_name}",
            f"resources/{icon_name}",
            f"icons/{icon_name}",
            f"ui/{icon_name}",
            f"ggufloader/{icon_name}",
        ]
        
        for location in common_locations:
            path = self.get_resource_path(location)
            if os.path.exists(path):
                return path
        
        # Return the standard path even if it doesn't exist (might be created later)
        return standard_path
    
    def find_config_dir(self) -> str:
        """
        Find or create the configuration directory.
        
        Returns:
            Path to the configuration directory
        """
        if self._deployment_type in ['pyinstaller', 'frozen']:
            # For executables, use a user data directory
            if os.name == 'nt':  # Windows
                config_dir = os.path.join(os.environ.get('APPDATA', ''), 'GGUFLoader')
            else:  # Unix-like
                config_dir = os.path.join(os.path.expanduser('~'), '.ggufloader')
        else:
            # For development/installed package, use local config directory
            config_dir = self.get_resource_path("config")
        
        # Create directory if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)
        return config_dir
    
    def find_cache_dir(self) -> str:
        """
        Find or create the cache directory.
        
        Returns:
            Path to the cache directory
        """
        if self._deployment_type in ['pyinstaller', 'frozen']:
            # For executables, use a user cache directory
            if os.name == 'nt':  # Windows
                cache_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'GGUFLoader', 'cache')
            else:  # Unix-like
                cache_dir = os.path.join(os.path.expanduser('~'), '.cache', 'ggufloader')
        else:
            # For development/installed package, use local cache directory
            cache_dir = self.get_resource_path("cache")
        
        # Create directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    
    def find_logs_dir(self) -> str:
        """
        Find or create the logs directory.
        
        Returns:
            Path to the logs directory
        """
        if self._deployment_type in ['pyinstaller', 'frozen']:
            # For executables, use a user data directory
            if os.name == 'nt':  # Windows
                logs_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'GGUFLoader', 'logs')
            else:  # Unix-like
                logs_dir = os.path.join(os.path.expanduser('~'), '.ggufloader', 'logs')
        else:
            # For development/installed package, use local logs directory
            logs_dir = self.get_resource_path("logs")
        
        # Create directory if it doesn't exist
        os.makedirs(logs_dir, exist_ok=True)
        return logs_dir
    
    def find_addons_dir(self) -> str:
        """
        Find the addons directory.
        
        Returns:
            Path to the addons directory
        """
        # For addons, we always want to use the package location
        if self._deployment_type == 'installed_package':
            return os.path.join(self._base_path, "addons")
        else:
            # For development, look in the current directory
            return self.get_resource_path("addons")
    
    def get_dll_path(self) -> Optional[str]:
        """
        Get the path to DLL files for llama.cpp.
        
        Returns:
            Path to DLL directory or None if not found
        """
        if self._deployment_type == 'pyinstaller':
            dll_path = os.path.join(self._base_path, "llama_cpp", "lib")
            if os.path.exists(dll_path):
                return dll_path
        
        # Try to find llama_cpp installation
        try:
            import llama_cpp
            llama_cpp_path = os.path.dirname(llama_cpp.__file__)
            dll_path = os.path.join(llama_cpp_path, 'lib')
            if os.path.exists(dll_path):
                return dll_path
        except ImportError:
            pass
        
        return None
    
    def get_deployment_info(self) -> dict:
        """
        Get information about the current deployment.
        
        Returns:
            Dictionary with deployment information
        """
        return {
            'deployment_type': self._deployment_type,
            'base_path': self._base_path,
            'package_name': self.package_name,
            'python_executable': sys.executable,
            'frozen': getattr(sys, 'frozen', False),
            'meipass': getattr(sys, '_MEIPASS', None),
        }


# Global instance for easy access
_resource_manager = ResourceManager()

# Convenience functions
def get_resource_path(relative_path: str) -> str:
    """Get absolute path for a resource file."""
    return _resource_manager.get_resource_path(relative_path)

def find_icon(icon_name: str = "icon.ico") -> str:
    """Find the application icon."""
    return _resource_manager.find_icon(icon_name)

def find_config_dir() -> str:
    """Find or create the configuration directory."""
    return _resource_manager.find_config_dir()

def find_cache_dir() -> str:
    """Find or create the cache directory."""
    return _resource_manager.find_cache_dir()

def find_logs_dir() -> str:
    """Find or create the logs directory."""
    return _resource_manager.find_logs_dir()

def find_addons_dir() -> str:
    """Find the addons directory."""
    return _resource_manager.find_addons_dir()

def get_dll_path() -> Optional[str]:
    """Get the path to DLL files for llama.cpp."""
    return _resource_manager.get_dll_path()

def get_deployment_info() -> dict:
    """Get information about the current deployment."""
    return _resource_manager.get_deployment_info()