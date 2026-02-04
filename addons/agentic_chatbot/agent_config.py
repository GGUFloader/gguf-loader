#!/usr/bin/env python3
"""
Agent Configuration System

Provides comprehensive configuration management for the agentic chatbot addon,
integrating with existing GGUF Loader configuration patterns while adding
agent-specific settings for workspace management, security, and behavior tuning.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Import existing config patterns
try:
    from config import get_paths, ensure_directories, PATHS
except ImportError:
    # Fallback if config module not available
    PATHS = {}


@dataclass
class WorkspaceConfig:
    """Configuration for agent workspace settings."""
    default_workspace: str = "./agent_workspace"
    auto_create_workspace: bool = True
    workspace_isolation: bool = True
    max_workspace_size_mb: int = 1000
    cleanup_on_exit: bool = False
    backup_workspace: bool = True
    workspace_templates: List[str] = field(default_factory=list)


@dataclass
class SecurityConfig:
    """Configuration for security and sandboxing."""
    # Command filtering
    allowed_commands: List[str] = field(default_factory=lambda: [
        "ls", "dir", "grep", "find", "cat", "head", "tail", 
        "wc", "sort", "uniq", "echo", "pwd", "whoami", "tree",
        "file", "stat", "du", "df", "ps", "top", "which"
    ])
    denied_commands: List[str] = field(default_factory=lambda: [
        "rm", "del", "sudo", "chmod", "chown", "dd", "mkfs",
        "format", "fdisk", "shutdown", "reboot", "halt", "kill",
        "killall", "pkill", "systemctl", "service", "mount", "umount"
    ])
    command_timeout: int = 30
    max_command_output_size: int = 1024 * 1024  # 1MB
    
    # Path validation
    allow_hidden_files: bool = False
    allow_system_paths: bool = False
    max_path_depth: int = 10
    blocked_extensions: List[str] = field(default_factory=lambda: [
        ".exe", ".bat", ".cmd", ".sh", ".ps1", ".scr", ".com", ".pif"
    ])
    
    # Security logging
    log_security_events: bool = True
    security_log_file: str = "agent_security.log"
    audit_trail: bool = True


@dataclass  
class AgentBehaviorConfig:
    """Configuration for agent behavior and capabilities."""
    max_iterations: int = 15
    max_tool_calls_per_turn: int = 5
    enable_multi_step_planning: bool = True
    enable_memory_management: bool = True
    enable_streaming_responses: bool = True
    enable_progress_monitoring: bool = True
    
    # Conversation management
    max_conversation_length: int = 50
    context_window_size: int = 4000
    memory_retention_turns: int = 10
    auto_summarize_context: bool = True
    
    # Error handling
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    graceful_degradation: bool = True
    fallback_to_basic_mode: bool = True


@dataclass
class ModelConfig:
    """Configuration for model parameters and generation."""
    # Generation parameters
    temperature: float = 0.1
    top_p: float = 0.9
    top_k: int = 50
    max_tokens: int = 2048
    repeat_penalty: float = 1.1
    
    # Agent-specific parameters
    reasoning_temperature: float = 0.3
    tool_call_temperature: float = 0.1
    planning_temperature: float = 0.2
    
    # Token management
    reserve_tokens_for_tools: int = 512
    max_tool_response_tokens: int = 1024
    context_compression_threshold: float = 0.8


@dataclass
class UIConfig:
    """Configuration for user interface components."""
    show_tool_calls: bool = True
    show_reasoning_steps: bool = True
    show_progress_indicators: bool = True
    enable_real_time_updates: bool = True
    
    # Window settings
    default_window_size: tuple = (1000, 700)
    min_window_size: tuple = (600, 400)
    remember_window_position: bool = True
    
    # Chat interface
    show_timestamps: bool = True
    show_token_counts: bool = False
    enable_syntax_highlighting: bool = True
    auto_scroll: bool = True


@dataclass
class ExtensibilityConfig:
    """Configuration for extensibility and plugin support."""
    enable_custom_tools: bool = True
    custom_tools_directory: str = "./custom_tools"
    enable_tool_marketplace: bool = False
    auto_load_tools: bool = True
    
    # Event system
    enable_event_system: bool = True
    event_log_file: str = "agent_events.log"
    max_event_history: int = 1000
    
    # Plugin system
    plugin_directories: List[str] = field(default_factory=lambda: ["./plugins"])
    enable_plugin_sandboxing: bool = True
    plugin_timeout: int = 10


@dataclass
class AgentConfig:
    """Main configuration class combining all agent settings."""
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    behavior: AgentBehaviorConfig = field(default_factory=AgentBehaviorConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    extensibility: ExtensibilityConfig = field(default_factory=ExtensibilityConfig)
    
    # Metadata
    config_version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dict[str, Any]: Configuration as dictionary
        """
        return asdict(self)


class AgentConfigManager:
    """
    Configuration manager for the agentic chatbot addon.
    
    Provides loading, saving, validation, and management of agent configuration
    following existing GGUF Loader patterns while adding agent-specific features.
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Directory for configuration files (uses GGUF paths if None)
        """
        self._logger = logging.getLogger(__name__)
        
        # Use existing GGUF Loader paths or fallback
        if config_dir:
            self.config_dir = Path(config_dir)
        elif PATHS and 'config' in PATHS:
            self.config_dir = PATHS['config'] / 'agentic_chatbot'
        else:
            self.config_dir = Path('./config/agentic_chatbot')
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration file paths
        self.config_file = self.config_dir / 'agent_config.json'
        self.user_config_file = self.config_dir / 'user_config.json'
        self.workspace_config_file = self.config_dir / 'workspace_config.json'
        
        # Current configuration
        self._config: Optional[AgentConfig] = None
        self._user_overrides: Dict[str, Any] = {}
        
        # Load configuration on initialization
        self.load_config()
    
    def load_config(self) -> AgentConfig:
        """
        Load configuration from files with proper fallbacks.
        
        Returns:
            AgentConfig: Loaded configuration
        """
        try:
            # Start with default configuration
            config = AgentConfig()
            
            # Load base configuration if exists
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    base_config = json.load(f)
                    config = self._merge_config(config, base_config)
            
            # Load user overrides if exists
            if self.user_config_file.exists():
                with open(self.user_config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    self._user_overrides = user_config
                    config = self._merge_config(config, user_config)
            
            # Update last modified timestamp
            config.last_modified = datetime.now().isoformat()
            
            self._config = config
            self._logger.info("Agent configuration loaded successfully")
            return config
            
        except Exception as e:
            self._logger.error(f"Failed to load configuration: {e}")
            # Return default configuration on error
            self._config = AgentConfig()
            return self._config
    
    def save_config(self, config: Optional[AgentConfig] = None) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save (uses current if None)
            
        Returns:
            bool: True if saved successfully
        """
        try:
            if config is None:
                config = self._config
            
            if config is None:
                self._logger.error("No configuration to save")
                return False
            
            # Update timestamp
            config.last_modified = datetime.now().isoformat()
            
            # Convert to dictionary
            config_dict = asdict(config)
            
            # Save to file with pretty formatting
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            self._config = config
            self._logger.info("Agent configuration saved successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to save configuration: {e}")
            return False
    
    def save_user_overrides(self, overrides: Dict[str, Any]) -> bool:
        """
        Save user-specific configuration overrides.
        
        Args:
            overrides: Dictionary of configuration overrides
            
        Returns:
            bool: True if saved successfully
        """
        try:
            with open(self.user_config_file, 'w', encoding='utf-8') as f:
                json.dump(overrides, f, indent=2, ensure_ascii=False)
            
            self._user_overrides = overrides
            self._logger.info("User configuration overrides saved")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to save user overrides: {e}")
            return False
    
    def get_config(self) -> AgentConfig:
        """
        Get current configuration.
        
        Returns:
            AgentConfig: Current configuration
        """
        if self._config is None:
            self._config = self.load_config()
        return self._config
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
            
        Returns:
            bool: True if updated successfully
        """
        try:
            if self._config is None:
                self._config = self.load_config()
            
            # Merge updates into current config
            updated_config = self._merge_config(self._config, updates)
            
            # Validate the updated configuration
            if self.validate_config(updated_config):
                return self.save_config(updated_config)
            else:
                self._logger.error("Configuration validation failed")
                return False
                
        except Exception as e:
            self._logger.error(f"Failed to update configuration: {e}")
            return False
    
    def validate_config(self, config: AgentConfig) -> bool:
        """
        Validate configuration values.
        
        Args:
            config: Configuration to validate
            
        Returns:
            bool: True if configuration is valid
        """
        try:
            # Validate workspace settings
            if config.workspace.max_workspace_size_mb <= 0:
                self._logger.error("Invalid workspace size limit")
                return False
            
            # Validate security settings
            if config.security.command_timeout <= 0:
                self._logger.error("Invalid command timeout")
                return False
            
            if config.security.max_path_depth <= 0:
                self._logger.error("Invalid path depth limit")
                return False
            
            # Validate behavior settings
            if config.behavior.max_iterations <= 0:
                self._logger.error("Invalid max iterations")
                return False
            
            if config.behavior.max_tool_calls_per_turn <= 0:
                self._logger.error("Invalid max tool calls per turn")
                return False
            
            # Validate model settings
            if not (0.0 <= config.model.temperature <= 2.0):
                self._logger.error("Invalid temperature value")
                return False
            
            if config.model.max_tokens <= 0:
                self._logger.error("Invalid max tokens")
                return False
            
            return True
            
        except Exception as e:
            self._logger.error(f"Configuration validation error: {e}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """
        Reset configuration to default values.
        
        Returns:
            bool: True if reset successfully
        """
        try:
            self._config = AgentConfig()
            return self.save_config()
        except Exception as e:
            self._logger.error(f"Failed to reset configuration: {e}")
            return False
    
    def export_config(self, export_path: Path) -> bool:
        """
        Export configuration to specified path.
        
        Args:
            export_path: Path to export configuration
            
        Returns:
            bool: True if exported successfully
        """
        try:
            if self._config is None:
                self._config = self.load_config()
            
            config_dict = asdict(self._config)
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            self._logger.info(f"Configuration exported to {export_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to export configuration: {e}")
            return False
    
    def import_config(self, import_path: Path) -> bool:
        """
        Import configuration from specified path.
        
        Args:
            import_path: Path to import configuration from
            
        Returns:
            bool: True if imported successfully
        """
        try:
            if not import_path.exists():
                self._logger.error(f"Import file does not exist: {import_path}")
                return False
            
            with open(import_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            # Create config from imported data
            config = AgentConfig()
            config = self._merge_config(config, config_dict)
            
            # Validate imported configuration
            if self.validate_config(config):
                return self.save_config(config)
            else:
                self._logger.error("Imported configuration is invalid")
                return False
                
        except Exception as e:
            self._logger.error(f"Failed to import configuration: {e}")
            return False
    
    def get_workspace_config(self, workspace_path: str) -> Dict[str, Any]:
        """
        Get workspace-specific configuration.
        
        Args:
            workspace_path: Path to workspace
            
        Returns:
            Dict[str, Any]: Workspace configuration
        """
        try:
            workspace_config_file = Path(workspace_path) / '.agent_config.json'
            
            if workspace_config_file.exists():
                with open(workspace_config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            return {}
            
        except Exception as e:
            self._logger.error(f"Failed to load workspace config: {e}")
            return {}
    
    def save_workspace_config(self, workspace_path: str, config: Dict[str, Any]) -> bool:
        """
        Save workspace-specific configuration.
        
        Args:
            workspace_path: Path to workspace
            config: Configuration to save
            
        Returns:
            bool: True if saved successfully
        """
        try:
            workspace_config_file = Path(workspace_path) / '.agent_config.json'
            
            with open(workspace_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to save workspace config: {e}")
            return False
    
    def _merge_config(self, base_config: AgentConfig, updates: Dict[str, Any]) -> AgentConfig:
        """
        Merge configuration updates into base configuration.
        
        Args:
            base_config: Base configuration
            updates: Updates to merge
            
        Returns:
            AgentConfig: Merged configuration
        """
        try:
            # Convert base config to dict
            config_dict = asdict(base_config)
            
            # Recursively merge updates
            self._deep_merge(config_dict, updates)
            
            # Create new config from merged dict
            return self._dict_to_config(config_dict)
            
        except Exception as e:
            self._logger.error(f"Failed to merge configuration: {e}")
            return base_config
    
    def _deep_merge(self, base: Dict[str, Any], updates: Dict[str, Any]):
        """
        Recursively merge dictionaries.
        
        Args:
            base: Base dictionary to merge into
            updates: Updates to merge
        """
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _dict_to_config(self, config_dict: Dict[str, Any]) -> AgentConfig:
        """
        Convert dictionary to AgentConfig object.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            AgentConfig: Configuration object
        """
        try:
            # Create sub-configs
            workspace = WorkspaceConfig(**config_dict.get('workspace', {}))
            security = SecurityConfig(**config_dict.get('security', {}))
            behavior = AgentBehaviorConfig(**config_dict.get('behavior', {}))
            model = ModelConfig(**config_dict.get('model', {}))
            ui = UIConfig(**config_dict.get('ui', {}))
            extensibility = ExtensibilityConfig(**config_dict.get('extensibility', {}))
            
            # Create main config
            return AgentConfig(
                workspace=workspace,
                security=security,
                behavior=behavior,
                model=model,
                ui=ui,
                extensibility=extensibility,
                config_version=config_dict.get('config_version', '1.0.0'),
                created_at=config_dict.get('created_at', datetime.now().isoformat()),
                last_modified=config_dict.get('last_modified', datetime.now().isoformat())
            )
            
        except Exception as e:
            self._logger.error(f"Failed to convert dict to config: {e}")
            return AgentConfig()


# Global configuration manager instance
_config_manager: Optional[AgentConfigManager] = None


def get_config_manager() -> AgentConfigManager:
    """
    Get the global configuration manager instance.
    
    Returns:
        AgentConfigManager: Configuration manager
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = AgentConfigManager()
    return _config_manager


def get_agent_config() -> AgentConfig:
    """
    Get the current agent configuration.
    
    Returns:
        AgentConfig: Current configuration
    """
    return get_config_manager().get_config()


def update_agent_config(updates: Dict[str, Any]) -> bool:
    """
    Update agent configuration.
    
    Args:
        updates: Configuration updates
        
    Returns:
        bool: True if updated successfully
    """
    return get_config_manager().update_config(updates)


def reset_agent_config() -> bool:
    """
    Reset agent configuration to defaults.
    
    Returns:
        bool: True if reset successfully
    """
    return get_config_manager().reset_to_defaults()