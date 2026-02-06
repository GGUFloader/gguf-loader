#!/usr/bin/env python3
"""
Test script to verify agent file writing capabilities
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.agent.simple_agent import SimpleAgent


class MockModel:
    """Mock model for testing without actual GGUF model"""
    def __init__(self):
        self.loaded = True
    
    def generate(self, prompt, **kwargs):
        # Simulate tool call response
        return """```json
{
    "reasoning": "User wants to create a test file",
    "tool_calls": [
        {
            "tool": "write_file",
            "parameters": {
                "path": "test_output.txt",
                "content": "Hello from the agent!\\nThis file was created by the agentic system."
            }
        }
    ]
}
```"""


def test_file_writing():
    """Test file writing capabilities"""
    print("Testing Agent File Writing Capabilities")
    print("=" * 50)
    
    # Create workspace
    workspace = Path("agent_workspace")
    workspace.mkdir(exist_ok=True)
    
    # Create mock model
    model = MockModel()
    
    # Create agent
    agent = SimpleAgent(model, str(workspace))
    
    # Test 1: Write a new file
    print("\n1. Testing write_file tool...")
    result = agent._tool_write_file({
        "path": "test_file.txt",
        "content": "This is a test file created by the agent.\nIt has multiple lines.\nLine 3."
    })
    print(f"   Result: {result['status']}")
    if result['status'] == 'success':
        print(f"   {result['result']}")
        print(f"   Path: {result['path']}")
        print(f"   Bytes written: {result['bytes_written']}")
    
    # Test 2: Read the file back
    print("\n2. Testing read_file tool...")
    result = agent._tool_read_file({"path": "test_file.txt"})
    print(f"   Result: {result['status']}")
    if result['status'] == 'success':
        print(f"   Content preview: {result['result'][:50]}...")
    
    # Test 3: Edit the file (replace operation)
    print("\n3. Testing edit_file tool (replace)...")
    result = agent._tool_edit_file({
        "path": "test_file.txt",
        "operation": "replace",
        "find": "test file",
        "replace": "MODIFIED file"
    })
    print(f"   Result: {result['status']}")
    if result['status'] == 'success':
        print(f"   {result['result']}")
        print(f"   Changes made: {result['changes_made']}")
    
    # Test 4: Insert a line
    print("\n4. Testing edit_file tool (insert_line)...")
    result = agent._tool_edit_file({
        "path": "test_file.txt",
        "operation": "insert_line",
        "line_number": 2,
        "content": ">>> This line was inserted <<<"
    })
    print(f"   Result: {result['status']}")
    if result['status'] == 'success':
        print(f"   {result['result']}")
    
    # Test 5: List directory
    print("\n5. Testing list_directory tool...")
    result = agent._tool_list_directory({"path": "."})
    print(f"   Result: {result['status']}")
    if result['status'] == 'success':
        print(f"   Found {len(result['result'])} items")
        for item in result['result'][:5]:
            print(f"   - {item['name']} ({item['type']})")
    
    # Test 6: Search files
    print("\n6. Testing search_files tool...")
    result = agent._tool_search_files({
        "pattern": "MODIFIED",
        "path": "."
    })
    print(f"   Result: {result['status']}")
    if result['status'] == 'success':
        print(f"   Total matches: {result['total_matches']}")
        for match in result['result']:
            print(f"   - {match}")
    
    # Test 7: Create file in subdirectory
    print("\n7. Testing write_file with subdirectory...")
    result = agent._tool_write_file({
        "path": "subdir/nested/deep_file.txt",
        "content": "This file is in a nested directory structure."
    })
    print(f"   Result: {result['status']}")
    if result['status'] == 'success':
        print(f"   {result['result']}")
        print(f"   Path: {result['path']}")
    
    print("\n" + "=" * 50)
    print("All tests completed!")
    print(f"\nCheck the '{workspace}' directory to see the created files.")


if __name__ == "__main__":
    test_file_writing()
