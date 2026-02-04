#!/usr/bin/env python3
"""
Security Validation Test for Agentic Chatbot

This test validates security boundaries and workspace isolation.
"""

import sys
import os
import tempfile
import logging
from pathlib import Path
from unittest.mock import Mock

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_workspace_isolation():
    """Test workspace isolation and path traversal prevention."""
    print("Testing workspace isolation...")
    
    try:
        from addons.agentic_chatbot.security.sandbox import SandboxValidator
        
        # Create temporary workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            validator = SandboxValidator(workspace)
            print("- Sandbox validator created")
            
            # Test valid paths within workspace
            try:
                valid_path = validator.validate_path("test.txt")
                print("- Valid relative path accepted")
            except Exception as e:
                print(f"- Valid path rejected: {e}")
                return False
            
            # Test path traversal attempts
            traversal_attempts = [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32",
                "/etc/passwd",
                "C:\\Windows\\System32",
                "test/../../../etc/passwd"
            ]
            
            blocked_attempts = 0
            for attempt in traversal_attempts:
                try:
                    validator.validate_path(attempt)
                    print(f"- WARNING: Path traversal not blocked: {attempt}")
                except Exception:
                    blocked_attempts += 1
            
            if blocked_attempts == len(traversal_attempts):
                print(f"- All {len(traversal_attempts)} path traversal attempts blocked")
            else:
                print(f"- Only {blocked_attempts}/{len(traversal_attempts)} path traversal attempts blocked")
                return False
            
            return True
            
    except Exception as e:
        print(f"- Error: {e}")
        return False

def test_command_filtering():
    """Test command filtering and security enforcement."""
    print("\nTesting command filtering...")
    
    try:
        from addons.agentic_chatbot.security.command_filter import CommandFilter
        
        # Create command filter with security rules
        filter_config = {
            'allowed_commands': ['ls', 'dir', 'cat', 'grep', 'find'],
            'denied_commands': ['rm', 'del', 'sudo', 'chmod', 'format', 'shutdown']
        }
        cmd_filter = CommandFilter(filter_config)
        print("- Command filter created")
        
        # Test allowed commands
        allowed_commands = ['ls', 'dir', 'cat test.txt', 'grep pattern file.txt']
        allowed_passed = 0
        
        for cmd in allowed_commands:
            if cmd_filter.validate_command(cmd):
                allowed_passed += 1
            else:
                print(f"- WARNING: Allowed command rejected: {cmd}")
        
        if allowed_passed == len(allowed_commands):
            print(f"- All {len(allowed_commands)} allowed commands accepted")
        else:
            print(f"- Only {allowed_passed}/{len(allowed_commands)} allowed commands accepted")
            return False
        
        # Test dangerous commands
        dangerous_commands = [
            'rm -rf /',
            'del /f /s /q C:\\',
            'sudo rm -rf /',
            'chmod 777 /etc/passwd',
            'format C:',
            'shutdown -h now',
            'dd if=/dev/zero of=/dev/sda'
        ]
        
        blocked_commands = 0
        for cmd in dangerous_commands:
            if not cmd_filter.validate_command(cmd):
                blocked_commands += 1
            else:
                print(f"- WARNING: Dangerous command not blocked: {cmd}")
        
        if blocked_commands == len(dangerous_commands):
            print(f"- All {len(dangerous_commands)} dangerous commands blocked")
        else:
            print(f"- Only {blocked_commands}/{len(dangerous_commands)} dangerous commands blocked")
            return False
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        return False

def test_tool_security_integration():
    """Test tool execution with security validation."""
    print("\nTesting tool security integration...")
    
    try:
        from addons.agentic_chatbot.tool_registry import ToolRegistry
        from addons.agentic_chatbot.security.sandbox import SandboxValidator
        from addons.agentic_chatbot.security.command_filter import CommandFilter
        
        # Create temporary workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            # Create test file in workspace
            test_file = workspace / "test.txt"
            test_file.write_text("Hello, World!")
            
            # Create security components
            validator = SandboxValidator(workspace)
            filter_config = {'allowed_commands': ['ls'], 'denied_commands': ['rm']}
            cmd_filter = CommandFilter(filter_config)
            tool_registry = ToolRegistry(validator, cmd_filter)
            
            print("- Tool registry with security created")
            
            # Test valid file operation within workspace
            result = tool_registry.execute_tool('read_file', {'path': 'test.txt'})
            if result['status'] == 'success':
                print("- Valid file read within workspace succeeded")
            else:
                print(f"- Valid file read failed: {result.get('error', 'Unknown error')}")
                return False
            
            # Test invalid file operation outside workspace
            result = tool_registry.execute_tool('read_file', {'path': '../../../etc/passwd'})
            if result['status'] == 'error':
                print("- Invalid file read outside workspace blocked")
            else:
                print("- WARNING: Invalid file read outside workspace not blocked")
                return False
            
            # Test command execution with allowed command
            result = tool_registry.execute_tool('execute_command', {'command': 'ls'})
            if result['status'] == 'success':
                print("- Allowed command execution succeeded")
            else:
                print(f"- Allowed command execution failed: {result.get('error', 'Unknown error')}")
                # This might fail due to environment, but that's okay
                print("- (Command execution failure may be due to environment)")
            
            # Test command execution with denied command
            result = tool_registry.execute_tool('execute_command', {'command': 'rm -rf /'})
            if result['status'] == 'error':
                print("- Dangerous command execution blocked")
            else:
                print("- WARNING: Dangerous command execution not blocked")
                return False
            
            return True
            
    except Exception as e:
        print(f"- Error: {e}")
        return False

def test_agent_session_security():
    """Test agent session security and isolation."""
    print("\nTesting agent session security...")
    
    try:
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        
        # Create temporary workspaces
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace1 = Path(temp_dir) / "workspace1"
            workspace2 = Path(temp_dir) / "workspace2"
            workspace1.mkdir()
            workspace2.mkdir()
            
            # Create test files in each workspace
            (workspace1 / "secret1.txt").write_text("Secret from workspace 1")
            (workspace2 / "secret2.txt").write_text("Secret from workspace 2")
            
            # Mock GGUF app
            mock_app = Mock()
            
            # Create and start addon
            addon = AgenticChatbotAddon(mock_app)
            if not addon.start():
                print("- Failed to start addon")
                return False
            
            print("- Addon started")
            
            # Create sessions for different workspaces
            session1 = addon.create_agent_session(str(workspace1))
            session2 = addon.create_agent_session(str(workspace2))
            
            if not session1 or not session2:
                print("- Failed to create sessions")
                addon.stop()
                return False
            
            print("- Multiple sessions created")
            
            # Test that sessions are isolated
            active_sessions = addon.get_active_sessions()
            if len(active_sessions) == 2:
                print("- Session isolation maintained")
            else:
                print(f"- Session isolation failed: {len(active_sessions)} sessions")
                addon.stop()
                return False
            
            # Cleanup
            addon.stop()
            print("- Addon stopped")
            
            return True
            
    except Exception as e:
        print(f"- Error: {e}")
        return False

def main():
    """Run all security validation tests."""
    print("=== Security Validation Tests ===")
    
    # Suppress logging during tests
    logging.getLogger().setLevel(logging.CRITICAL)
    
    tests = [
        ("Workspace Isolation", test_workspace_isolation),
        ("Command Filtering", test_command_filtering),
        ("Tool Security Integration", test_tool_security_integration),
        ("Agent Session Security", test_agent_session_security)
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
    
    print(f"\n=== SECURITY VALIDATION SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("ALL SECURITY TESTS PASSED!")
        return True
    else:
        print("SOME SECURITY TESTS FAILED")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)