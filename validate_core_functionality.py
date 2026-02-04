#!/usr/bin/env python3
"""
Core Functionality Validation Script for Agentic Chatbot Addon

This script validates the core security and tools functionality that has been implemented:
- Sandbox validator security
- Command filter security  
- Tool registry functionality
- File system tools
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_sandbox_validator():
    """Test the sandbox validator functionality."""
    print("Testing SandboxValidator...")
    
    from addons.agentic_chatbot.security.sandbox import SandboxValidator, SecurityError
    
    # Create a temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "test_workspace"
        workspace.mkdir()
        
        validator = SandboxValidator(workspace)
        
        # Test 1: Valid path within workspace
        try:
            valid_path = validator.validate_path("test_file.txt")
            assert valid_path.is_absolute()
            assert validator.is_safe_path("test_file.txt")
            print("✓ Valid path validation passed")
        except Exception as e:
            print(f"✗ Valid path validation failed: {e}")
            return False
        
        # Test 2: Path traversal attempt
        try:
            validator.validate_path("../../../etc/passwd")
            print("✗ Path traversal validation failed - should have been blocked")
            return False
        except SecurityError:
            print("✓ Path traversal blocked correctly")
        except Exception as e:
            print(f"✗ Path traversal test error: {e}")
            return False
        
        # Test 3: Sanitize path
        try:
            sanitized = validator.sanitize_path("subdir/file.txt")
            assert sanitized.is_absolute()
            print("✓ Path sanitization passed")
        except Exception as e:
            print(f"✗ Path sanitization failed: {e}")
            return False
        
        # Test 4: List workspace contents
        try:
            # Create a test file
            test_file = workspace / "test.txt"
            test_file.write_text("test content")
            
            contents = validator.list_workspace_contents()
            assert "test.txt" in contents
            print("✓ Workspace listing passed")
        except Exception as e:
            print(f"✗ Workspace listing failed: {e}")
            return False
    
    return True

def test_command_filter():
    """Test the command filter functionality."""
    print("\nTesting CommandFilter...")
    
    from addons.agentic_chatbot.security.command_filter import CommandFilter, SecurityError
    
    config = {
        'allowed_commands': ['ls', 'cat', 'grep', 'find'],
        'denied_commands': ['rm', 'sudo', 'chmod'],
        'command_timeout': 30
    }
    
    filter = CommandFilter(config)
    
    # Test 1: Allowed command
    try:
        assert filter.validate_command("ls -la")
        print("✓ Allowed command validation passed")
    except Exception as e:
        print(f"✗ Allowed command validation failed: {e}")
        return False
    
    # Test 2: Denied command
    try:
        assert not filter.validate_command("rm -rf /")
        print("✓ Denied command blocked correctly")
    except Exception as e:
        print(f"✗ Denied command test failed: {e}")
        return False
    
    # Test 3: Dangerous pattern
    try:
        assert not filter.validate_command("sudo rm -rf /")
        print("✓ Dangerous pattern blocked correctly")
    except Exception as e:
        print(f"✗ Dangerous pattern test failed: {e}")
        return False
    
    # Test 4: Command sanitization
    try:
        sanitized = filter.sanitize_command("ls -la")
        assert sanitized == "ls -la"
        print("✓ Command sanitization passed")
    except Exception as e:
        print(f"✗ Command sanitization failed: {e}")
        return False
    
    # Test 5: Get command info
    try:
        info = filter.get_command_info("ls -la")
        assert info["is_valid"] == True
        assert info["base_command"] == "ls"
        print("✓ Command info retrieval passed")
    except Exception as e:
        print(f"✗ Command info retrieval failed: {e}")
        return False
    
    return True

def test_tool_registry():
    """Test the tool registry functionality."""
    print("\nTesting ToolRegistry...")
    
    from addons.agentic_chatbot.security.sandbox import SandboxValidator
    from addons.agentic_chatbot.security.command_filter import CommandFilter
    from addons.agentic_chatbot.tool_registry import ToolRegistry
    
    # Create temporary workspace and components
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "test_workspace"
        workspace.mkdir()
        
        validator = SandboxValidator(workspace)
        filter_config = {'allowed_commands': ['ls'], 'denied_commands': ['rm']}
        cmd_filter = CommandFilter(filter_config)
        
        registry = ToolRegistry(validator, cmd_filter)
        
        # Test 1: Get available tools
        try:
            tools = registry.get_available_tools()
            expected_tools = ['list_directory', 'read_file', 'write_file', 'edit_file']
            for tool in expected_tools:
                assert tool in tools, f"Tool {tool} not found in registry"
            print("✓ Built-in tools registered correctly")
        except Exception as e:
            print(f"✗ Built-in tools registration failed: {e}")
            return False
        
        # Test 2: Get tool schemas
        try:
            schemas = registry.get_tool_schemas()
            assert len(schemas) >= 4
            assert 'list_directory' in schemas
            print("✓ Tool schemas retrieved correctly")
        except Exception as e:
            print(f"✗ Tool schemas retrieval failed: {e}")
            return False
        
        # Test 3: Execute a tool (list_directory)
        try:
            result = registry.execute_tool('list_directory', {'path': ''})
            assert result['status'] == 'success'
            print("✓ Tool execution passed")
        except Exception as e:
            print(f"✗ Tool execution failed: {e}")
            return False
        
        # Test 4: Execute invalid tool
        try:
            result = registry.execute_tool('nonexistent_tool', {})
            assert result['status'] == 'error'
            assert 'not found' in result['error']
            print("✓ Invalid tool handling passed")
        except Exception as e:
            print(f"✗ Invalid tool handling failed: {e}")
            return False
    
    return True

def test_filesystem_tools():
    """Test the file system tools functionality."""
    print("\nTesting FileSystem Tools...")
    
    from addons.agentic_chatbot.security.sandbox import SandboxValidator
    from addons.agentic_chatbot.tools.filesystem import ListDirectoryTool, ReadFileTool, WriteFileTool, EditFileTool
    
    # Create temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "test_workspace"
        workspace.mkdir()
        
        validator = SandboxValidator(workspace)
        
        # Test WriteFileTool
        try:
            write_tool = WriteFileTool(validator)
            result = write_tool.execute({
                'path': 'test_file.txt',
                'content': 'Hello, World!\nThis is a test file.'
            })
            assert result['status'] == 'success'
            print("✓ WriteFileTool passed")
        except Exception as e:
            print(f"✗ WriteFileTool failed: {e}")
            return False
        
        # Test ReadFileTool
        try:
            read_tool = ReadFileTool(validator)
            result = read_tool.execute({'path': 'test_file.txt'})
            assert result['status'] == 'success'
            assert 'Hello, World!' in result['result']['content']
            print("✓ ReadFileTool passed")
        except Exception as e:
            print(f"✗ ReadFileTool failed: {e}")
            return False
        
        # Test ListDirectoryTool
        try:
            list_tool = ListDirectoryTool(validator)
            result = list_tool.execute({'path': ''})
            assert result['status'] == 'success'
            assert any(item['name'] == 'test_file.txt' for item in result['result']['contents'])
            print("✓ ListDirectoryTool passed")
        except Exception as e:
            print(f"✗ ListDirectoryTool failed: {e}")
            return False
        
        # Test EditFileTool
        try:
            edit_tool = EditFileTool(validator)
            result = edit_tool.execute({
                'path': 'test_file.txt',
                'operation': 'replace',
                'find': 'Hello, World!',
                'replace': 'Hello, Universe!'
            })
            assert result['status'] == 'success'
            assert result['result']['changes_made'] == 1
            
            # Verify the edit worked
            read_result = read_tool.execute({'path': 'test_file.txt'})
            assert 'Hello, Universe!' in read_result['result']['content']
            print("✓ EditFileTool passed")
        except Exception as e:
            print(f"✗ EditFileTool failed: {e}")
            return False
    
    return True

def main():
    """Run all validation tests."""
    print("=== Agentic Chatbot Core Functionality Validation ===\n")
    
    tests = [
        ("Sandbox Validator", test_sandbox_validator),
        ("Command Filter", test_command_filter),
        ("Tool Registry", test_tool_registry),
        ("FileSystem Tools", test_filesystem_tools)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✓ {test_name} - ALL TESTS PASSED\n")
            else:
                print(f"✗ {test_name} - SOME TESTS FAILED\n")
        except Exception as e:
            print(f"✗ {test_name} - CRITICAL ERROR: {e}\n")
    
    print("=== VALIDATION SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL CORE FUNCTIONALITY TESTS PASSED!")
        return True
    else:
        print("❌ SOME TESTS FAILED - Review the output above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)