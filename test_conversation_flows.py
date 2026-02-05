#!/usr/bin/env python3
"""
Conversation Flow Validation Test for Agentic Chatbot

This test validates agent conversation flows and tool execution.
"""

import sys
import os
import tempfile
import logging
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_agent_loop_initialization():
    """Test agent loop initialization and basic functionality."""
    print("Testing agent loop initialization...")
    
    try:
        from addons.agentic_chatbot.agent_loop import AgentLoop
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
            
            # Mock GGUF app
            mock_app = Mock()
            config = {
                "max_iterations": 15,
                "max_tool_calls_per_turn": 5,
                "temperature": 0.1,
                "max_tokens": 2048
            }
            
            # Create agent loop
            agent_loop = AgentLoop(mock_app, tool_registry, config)
            print("- Agent loop created successfully")
            
            # Test basic properties
            if hasattr(agent_loop, 'process_user_message'):
                print("- Agent loop has message processing capability")
            else:
                print("- Agent loop missing message processing")
                return False
            
            if hasattr(agent_loop, 'set_session'):
                print("- Agent loop has session management capability")
            else:
                print("- Agent loop missing session management")
                return False
            
            # Test session setting
            agent_loop.set_session("test_session", str(workspace))
            print("- Agent loop session set successfully")
            
            return True
            
    except Exception as e:
        print(f"- Error: {e}")
        return False

def test_context_management():
    """Test conversation context management."""
    print("\nTesting context management...")
    
    try:
        from addons.agentic_chatbot.context_manager import ContextManager
        
        config = {
            "max_conversation_length": 50,
            "context_window_size": 4000,
            "memory_retention_turns": 10
        }
        
        context_manager = ContextManager(config)
        print("- Context manager created")
        
        # Create a test context
        session_id = "test_session"
        workspace_path = "/tmp/test_workspace"
        
        context = context_manager.create_context(session_id, workspace_path)
        if context:
            print("- Context created successfully")
        else:
            print("- Context creation failed")
            return False
        
        # Test message addition
        context_manager.add_message(session_id, "user", "Hello, agent!")
        context_manager.add_message(session_id, "assistant", "Hello! How can I help you?")
        print("- Messages added to context")
        
        # Test context retrieval
        retrieved_context = context_manager.get_context(session_id)
        if retrieved_context and len(retrieved_context.messages) == 2:
            print("- Context retrieval successful")
        else:
            print("- Context retrieval failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        return False

def test_system_prompt_generation():
    """Test system prompt generation."""
    print("\nTesting system prompt generation...")
    
    try:
        from addons.agentic_chatbot.system_prompt import SystemPromptManager
        
        config = {
            "allowed_commands": ["ls", "cat", "grep"],
            "denied_commands": ["rm", "sudo"],
            "command_timeout": 30
        }
        
        prompt_manager = SystemPromptManager(config)
        print("- System prompt manager created")
        
        # Test system prompt generation
        workspace_path = "/tmp/test_workspace"
        available_tools = ["list_directory", "read_file", "write_file", "execute_command"]
        
        prompt = prompt_manager.get_system_prompt(workspace_path, available_tools)
        
        # Basic validation of prompt content
        if len(prompt) > 100:
            print("- System prompt generated (substantial content)")
        else:
            print("- System prompt too short")
            return False
        
        if "Agentic Assistant" in prompt:
            print("- System prompt contains agent identity")
        else:
            print("- System prompt missing agent identity")
            return False
        
        if workspace_path in prompt:
            print("- System prompt contains workspace information")
        else:
            print("- System prompt missing workspace information")
            return False
        
        # Test tool-specific guidance
        guidance = prompt_manager.get_tool_usage_prompt("read_file")
        if len(guidance) > 0:
            print("- Tool-specific guidance generated")
        else:
            print("- Tool-specific guidance missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        return False

def test_tool_call_protocol():
    """Test tool call protocol and response format."""
    print("\nTesting tool call protocol...")
    
    try:
        from addons.agentic_chatbot.tool_registry import ToolRegistry
        from addons.agentic_chatbot.security.sandbox import SandboxValidator
        from addons.agentic_chatbot.security.command_filter import CommandFilter
        
        # Create temporary workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            # Create test file
            test_file = workspace / "test.txt"
            test_file.write_text("Test content for protocol validation")
            
            # Create components
            validator = SandboxValidator(workspace)
            filter_config = {'allowed_commands': ['ls'], 'denied_commands': ['rm']}
            cmd_filter = CommandFilter(filter_config)
            tool_registry = ToolRegistry(validator, cmd_filter)
            
            print("- Tool registry created")
            
            # Test tool call with proper protocol
            result = tool_registry.execute_tool('read_file', {'path': 'test.txt'})
            
            # Validate response format
            required_fields = ['status', 'execution_time', 'tool_name']
            missing_fields = [field for field in required_fields if field not in result]
            
            if not missing_fields:
                print("- Tool response contains required fields")
            else:
                print(f"- Tool response missing fields: {missing_fields}")
                return False
            
            # Validate successful execution
            if result['status'] == 'success':
                print("- Tool execution successful")
            else:
                print(f"- Tool execution failed: {result.get('error', 'Unknown error')}")
                return False
            
            # Validate result content
            if 'result' in result and 'Test content' in str(result['result']):
                print("- Tool result contains expected content")
            else:
                print("- Tool result missing expected content")
                return False
            
            return True
            
    except Exception as e:
        print(f"- Error: {e}")
        return False

def main():
    """Run all conversation flow validation tests."""
    print("=== Conversation Flow Validation Tests ===")
    
    # Suppress logging during tests
    logging.getLogger().setLevel(logging.CRITICAL)
    
    tests = [
        ("Agent Loop Initialization", test_agent_loop_initialization),
        ("Context Management", test_context_management),
        ("System Prompt Generation", test_system_prompt_generation),
        ("Tool Call Protocol", test_tool_call_protocol)
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
    
    print(f"\n=== CONVERSATION FLOW VALIDATION SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("ALL CONVERSATION FLOW TESTS PASSED!")
        return True
    else:
        print("SOME CONVERSATION FLOW TESTS FAILED")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)