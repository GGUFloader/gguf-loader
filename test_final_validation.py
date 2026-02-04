#!/usr/bin/env python3
"""
Final Validation Test for Agentic Chatbot

This test validates the core functionality without Unicode characters
that cause issues on Windows.
"""

import sys
import os
import tempfile
import shutil
import logging
from pathlib import Path
from unittest.mock import Mock

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_addon_startup_and_shutdown():
    """Test basic addon startup and shutdown."""
    print("Testing addon startup and shutdown...")
    
    try:
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        
        # Mock GGUF app
        mock_app = Mock()
        
        # Create addon
        addon = AgenticChatbotAddon(mock_app)
        print("- Addon created successfully")
        
        # Test startup
        success = addon.start()
        if success:
            print("- Addon started successfully")
        else:
            print("- Addon startup failed")
            return False
        
        # Test running state
        if addon.is_running():
            print("- Addon is running")
        else:
            print("- Addon is not running")
            return False
        
        # Test shutdown
        success = addon.stop()
        if success:
            print("- Addon stopped successfully")
        else:
            print("- Addon shutdown failed")
            return False
        
        # Test stopped state
        if not addon.is_running():
            print("- Addon is stopped")
        else:
            print("- Addon is still running")
            return False
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        return False

def test_session_management():
    """Test agent session creation and management."""
    print("\nTesting session management...")
    
    try:
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        
        # Create temporary workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            # Mock GGUF app
            mock_app = Mock()
            
            # Create and start addon
            addon = AgenticChatbotAddon(mock_app)
            if not addon.start():
                print("- Failed to start addon")
                return False
            
            print("- Addon started")
            
            # Test session creation
            session_id = addon.create_agent_session(str(workspace))
            if session_id:
                print("- Session created successfully")
            else:
                print("- Session creation failed")
                addon.stop()
                return False
            
            # Test active sessions
            active_sessions = addon.get_active_sessions()
            if session_id in active_sessions:
                print("- Session is active")
            else:
                print("- Session is not active")
                addon.stop()
                return False
            
            # Cleanup
            addon.stop()
            print("- Addon stopped")
            
            return True
            
    except Exception as e:
        print(f"- Error: {e}")
        return False

def test_tool_registry():
    """Test tool registry functionality."""
    print("\nTesting tool registry...")
    
    try:
        from addons.agentic_chatbot.tool_registry import ToolRegistry
        from addons.agentic_chatbot.security.sandbox import SandboxValidator
        from addons.agentic_chatbot.security.command_filter import CommandFilter
        
        # Create temporary workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            # Create components
            validator = SandboxValidator(workspace)
            filter_config = {'allowed_commands': ['ls'], 'denied_commands': ['rm']}
            cmd_filter = CommandFilter(filter_config)
            tool_registry = ToolRegistry(validator, cmd_filter)
            
            print("- Tool registry created")
            
            # Test available tools
            available_tools = tool_registry.get_available_tools()
            if len(available_tools) > 0:
                print(f"- Found {len(available_tools)} available tools")
            else:
                print("- No tools available")
                return False
            
            # Test tool execution
            result = tool_registry.execute_tool('list_directory', {'path': ''})
            if result['status'] == 'success':
                print("- Tool execution successful")
            else:
                print(f"- Tool execution failed: {result.get('error', 'Unknown error')}")
                return False
            
            return True
            
    except Exception as e:
        print(f"- Error: {e}")
        return False

def test_security_components():
    """Test security components."""
    print("\nTesting security components...")
    
    try:
        from addons.agentic_chatbot.security.sandbox import SandboxValidator
        from addons.agentic_chatbot.security.command_filter import CommandFilter
        
        # Create temporary workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            # Test sandbox validator
            validator = SandboxValidator(workspace)
            print("- Sandbox validator created")
            
            # Test valid path
            try:
                valid_path = validator.validate_path("test.txt")
                print("- Valid path validation passed")
            except Exception as e:
                print(f"- Valid path validation failed: {e}")
                return False
            
            # Test command filter
            filter_config = {'allowed_commands': ['ls'], 'denied_commands': ['rm']}
            cmd_filter = CommandFilter(filter_config)
            print("- Command filter created")
            
            # Test allowed command
            if cmd_filter.validate_command("ls"):
                print("- Allowed command validation passed")
            else:
                print("- Allowed command validation failed")
                return False
            
            # Test denied command
            if not cmd_filter.validate_command("rm"):
                print("- Denied command validation passed")
            else:
                print("- Denied command validation failed")
                return False
            
            return True
            
    except Exception as e:
        print(f"- Error: {e}")
        return False

def test_configuration_system():
    """Test configuration system."""
    print("\nTesting configuration system...")
    
    try:
        from addons.agentic_chatbot.agent_config import get_config_manager, AgentConfig
        
        # Test config manager
        config_manager = get_config_manager()
        print("- Config manager created")
        
        # Test config loading
        config = config_manager.get_config()
        if isinstance(config, AgentConfig):
            print("- Configuration loaded successfully")
        else:
            print("- Configuration loading failed")
            return False
        
        # Test config validation
        if config_manager.validate_config(config):
            print("- Configuration validation passed")
        else:
            print("- Configuration validation failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        return False

def main():
    """Run all validation tests."""
    print("=== Final Validation Tests ===")
    
    # Suppress logging during tests
    logging.getLogger().setLevel(logging.CRITICAL)
    
    tests = [
        ("Addon Startup/Shutdown", test_addon_startup_and_shutdown),
        ("Session Management", test_session_management),
        ("Tool Registry", test_tool_registry),
        ("Security Components", test_security_components),
        ("Configuration System", test_configuration_system)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"PASS: {test_name}")
            else:
                print(f"FAIL: {test_name}")
        except Exception as e:
            print(f"ERROR: {test_name} - {e}")
    
    print(f"\n=== VALIDATION SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("ALL TESTS PASSED!")
        return True
    else:
        print("SOME TESTS FAILED")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)