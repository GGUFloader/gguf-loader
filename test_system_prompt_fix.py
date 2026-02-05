#!/usr/bin/env python3
"""
Test System Prompt Fix - Verify the system prompt correctly instructs tool usage
"""

import sys
import os
import logging

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_system_prompt_format():
    """Test that the system prompt includes correct response format instructions."""
    print("=== Testing System Prompt Format Instructions ===")
    
    try:
        from addons.agentic_chatbot.system_prompt import SystemPromptManager
        
        # Create system prompt manager
        config = {
            "allowed_commands": ["ls", "cat", "grep"],
            "denied_commands": ["rm", "sudo"],
            "command_timeout": 30
        }
        
        prompt_manager = SystemPromptManager(config)
        
        # Generate system prompt
        workspace_path = "./test_workspace"
        available_tools = ["read_file", "write_file", "list_directory", "execute_command"]
        
        system_prompt = prompt_manager.get_system_prompt(workspace_path, available_tools)
        
        print("1. Checking for response format instructions...")
        
        # Check for key format instructions
        format_checks = [
            ("JSON code block", "```json" in system_prompt),
            ("Reasoning field", '"reasoning"' in system_prompt),
            ("Tool calls array", '"tool_calls"' in system_prompt),
            ("Tool structure", '"tool":' in system_prompt and '"parameters":' in system_prompt),
            ("Format explanation", "MUST format your response" in system_prompt),
            ("Example structure", "tool_name" in system_prompt)
        ]
        
        all_passed = True
        for check_name, passed in format_checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}: {'Found' if passed else 'Missing'}")
            if not passed:
                all_passed = False
        
        if not all_passed:
            print("\n❌ System prompt missing critical format instructions")
            return False
        
        print("\n2. Checking for tool usage examples...")
        
        # Check for proper examples
        example_checks = [
            ("Single tool example", "Single Tool Call Example" in system_prompt),
            ("Multiple tools example", "Multiple Tool Calls Example" in system_prompt),
            ("Error recovery example", "Error Recovery Example" in system_prompt),
            ("Reasoning examples", "reasoning" in system_prompt.lower()),
            ("Tool call structure", '{"tool":' in system_prompt)
        ]
        
        for check_name, passed in example_checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}: {'Found' if passed else 'Missing'}")
            if not passed:
                all_passed = False
        
        if not all_passed:
            print("\n❌ System prompt missing proper examples")
            return False
        
        print("\n3. Checking for tool availability...")
        
        # Check that available tools are mentioned
        for tool in available_tools:
            if tool in system_prompt:
                print(f"   ✅ Tool {tool}: Mentioned")
            else:
                print(f"   ⚠️  Tool {tool}: Not mentioned (may be okay)")
        
        print("\n✅ SUCCESS: System prompt includes proper format instructions")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_response_parsing():
    """Test that the agent loop can parse the expected response format."""
    print("\n=== Testing Response Parsing ===")
    
    try:
        from addons.agentic_chatbot.agent_loop import AgentLoop
        from addons.agentic_chatbot.tool_registry import ToolRegistry
        from unittest.mock import Mock
        
        # Create mock components
        mock_app = Mock()
        mock_sandbox = Mock()
        mock_command_filter = Mock()
        
        tool_registry = ToolRegistry(mock_sandbox, mock_command_filter)
        config = {"max_tokens": 2048, "temperature": 0.1}
        
        # Create agent loop
        agent_loop = AgentLoop(mock_app, tool_registry, config)
        
        print("1. Testing correct JSON format parsing...")
        
        # Test correct format
        correct_response = '''Here's what I'll do:

```json
{
  "reasoning": "I need to create a requirements.txt file with the necessary dependencies.",
  "tool_calls": [
    {"tool": "write_file", "parameters": {"path": "requirements.txt", "content": "PySide6>=6.5.0"}}
  ]
}
```

This will create the file you requested.'''
        
        parsed = agent_loop._parse_agent_response(correct_response)
        
        # Check parsing results
        checks = [
            ("Has reasoning", "reasoning" in parsed and parsed["reasoning"]),
            ("Has tool calls", "tool_calls" in parsed and len(parsed["tool_calls"]) > 0),
            ("Tool call structure", parsed["tool_calls"][0].get("tool") == "write_file" if parsed["tool_calls"] else False),
            ("Parameters present", "parameters" in parsed["tool_calls"][0] if parsed["tool_calls"] else False)
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}: {'Passed' if passed else 'Failed'}")
            if not passed:
                all_passed = False
        
        if not all_passed:
            print(f"\n❌ Parsing failed. Parsed result: {parsed}")
            return False
        
        print("\n2. Testing tool call extraction...")
        
        # Test tool call parsing
        tool_calls = agent_loop._parse_tool_calls(parsed)
        
        if len(tool_calls) != 1:
            print(f"   ❌ Expected 1 tool call, got {len(tool_calls)}")
            return False
        
        tool_call = tool_calls[0]
        
        tool_checks = [
            ("Tool name", tool_call.tool_name == "write_file"),
            ("Has parameters", bool(tool_call.parameters)),
            ("Path parameter", tool_call.parameters.get("path") == "requirements.txt"),
            ("Content parameter", "PySide6" in tool_call.parameters.get("content", "")),
            ("Has call ID", bool(tool_call.call_id))
        ]
        
        for check_name, passed in tool_checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}: {'Passed' if passed else 'Failed'}")
            if not passed:
                all_passed = False
        
        if not all_passed:
            print(f"\n❌ Tool call parsing failed. Tool call: {tool_call}")
            return False
        
        print("\n3. Testing invalid format handling...")
        
        # Test invalid format (old hallucinated format)
        invalid_response = '''I'll create the file for you.

**Tool Execution**:
```json
{"tool": "write_file", "parameters": {"path": "requirements.txt"}}
```

The file has been created successfully.'''
        
        parsed_invalid = agent_loop._parse_agent_response(invalid_response)
        
        # Should not find tool calls in this format
        if parsed_invalid["tool_calls"]:
            print(f"   ⚠️  Unexpectedly parsed tool calls from invalid format: {parsed_invalid['tool_calls']}")
        else:
            print("   ✅ Correctly ignored invalid format")
        
        print("\n✅ SUCCESS: Response parsing works correctly")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    # Enable info logging
    logging.basicConfig(level=logging.INFO)
    
    tests = [
        ("System Prompt Format Test", test_system_prompt_format),
        ("Response Parsing Test", test_response_parsing)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print('='*60)
        
        try:
            if test_func():
                passed += 1
                print(f"\n✅ PASSED: {test_name}")
            else:
                print(f"\n❌ FAILED: {test_name}")
        except Exception as e:
            print(f"\n💥 ERROR: {test_name} - {e}")
    
    print(f"\n{'='*60}")
    print(f"FINAL SUMMARY: {passed}/{total} tests passed")
    print('='*60)
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("\n✨ The system prompt fix should resolve the hallucination issue!")
        print("\nWhat was fixed:")
        print("- ✅ Added clear response format instructions")
        print("- ✅ Specified exact JSON structure required")
        print("- ✅ Provided proper examples with reasoning and tool_calls")
        print("- ✅ Explained when to use tool format vs normal responses")
        print("\nThe agent should now:")
        print("1. Use the correct JSON format for tool calls")
        print("2. Include reasoning for its actions")
        print("3. Structure tool calls properly")
        print("4. Not hallucinate about non-existent tools")
    else:
        print("⚠️  Some tests failed. The fix may need more work.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)