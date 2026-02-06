# Agent File Writing Capabilities Guide

## Overview

The agentic chatbot in GGUF Loader now has **full file writing capabilities**. When Agent Mode is enabled, the AI assistant can create, modify, and manage files within the designated workspace directory.

## Features

### 1. **Write Files** (`write_file` tool)
- Create new files from scratch
- Overwrite existing files completely
- Automatically creates parent directories
- Supports any text content

**Example Usage:**
```
User: "Create a file called hello.py with a simple hello world program"
Agent: Uses write_file tool to create the file with Python code
```

### 2. **Edit Files** (`edit_file` tool)
- **Replace operation**: Find and replace text in files
- **Insert line**: Add new lines at specific positions
- **Delete line**: Remove lines by line number
- Preserves file structure and formatting

**Example Usage:**
```
User: "In hello.py, replace 'world' with 'universe'"
Agent: Uses edit_file with replace operation
```

### 3. **Read Files** (`read_file` tool)
- Read complete file contents
- UTF-8 encoding support
- Error handling for missing files

### 4. **List Directory** (`list_directory` tool)
- View files and folders in workspace
- Shows file types and sizes
- Recursive listing support

### 5. **Search Files** (`search_files` tool)
- Search for text patterns across files
- Case-insensitive search
- Returns matching file paths

## How to Use

### Step 1: Enable Agent Mode
1. Open GGUF Loader main chat window
2. Click the **"🤖 Agent Mode: OFF"** button to turn it ON
3. The button will change to **"🤖 Agent Mode: ON"**

### Step 2: Select Workspace
1. Choose or browse to a workspace directory
2. This is where the agent can create/modify files
3. The agent can only work within this directory (security sandbox)

### Step 3: Load a Model
1. Load a GGUF model as usual
2. The agent needs a model to understand your requests

### Step 4: Give Instructions
Simply chat with the agent and ask it to create or modify files:

**Examples:**
- "Create a README.md file with project documentation"
- "Write a Python script that calculates fibonacci numbers"
- "Create a config.json file with these settings: ..."
- "Modify the existing script.py to add error handling"
- "Create a folder structure for a web project"

## Tool Details

### write_file
**Purpose:** Create new files or completely overwrite existing files

**Parameters:**
- `path`: File path relative to workspace (e.g., "src/main.py")
- `content`: Complete file content as text

**Features:**
- Automatically creates parent directories
- Overwrites existing files without warning
- Returns bytes written and file path

**Example:**
```json
{
  "tool": "write_file",
  "parameters": {
    "path": "config/settings.json",
    "content": "{\"debug\": true, \"port\": 8080}"
  }
}
```

### edit_file
**Purpose:** Make targeted changes to existing files

**Parameters:**
- `path`: File path relative to workspace
- `operation`: One of "replace", "insert_line", "delete_line"
- `find`: Text to find (for replace operation)
- `replace`: Replacement text (for replace operation)
- `line_number`: Line number (for insert/delete operations, 1-based)
- `content`: Content to insert (for insert_line operation)

**Operations:**

1. **Replace**: Find and replace text
```json
{
  "tool": "edit_file",
  "parameters": {
    "path": "script.py",
    "operation": "replace",
    "find": "old_function_name",
    "replace": "new_function_name"
  }
}
```

2. **Insert Line**: Add a new line at specific position
```json
{
  "tool": "edit_file",
  "parameters": {
    "path": "script.py",
    "operation": "insert_line",
    "line_number": 5,
    "content": "    print('Debug line')"
  }
}
```

3. **Delete Line**: Remove a specific line
```json
{
  "tool": "edit_file",
  "parameters": {
    "path": "script.py",
    "operation": "delete_line",
    "line_number": 10
  }
}
```

## Security Features

### Workspace Sandbox
- Agent can **only** access files within the selected workspace
- Cannot access system files or parent directories
- Path traversal attacks are prevented

### Safe Operations
- All file operations are validated
- Parent directories are created automatically
- UTF-8 encoding is enforced
- Error handling prevents crashes

## Example Workflows

### 1. Create a Python Project
```
User: "Create a basic Python project structure with main.py, 
       requirements.txt, and README.md"

Agent will:
1. Use write_file to create main.py with starter code
2. Use write_file to create requirements.txt
3. Use write_file to create README.md with documentation
```

### 2. Modify Existing Code
```
User: "In main.py, add error handling to the read_file function"

Agent will:
1. Use read_file to see current content
2. Use edit_file to add try-except blocks
3. Confirm changes were made
```

### 3. Create Configuration Files
```
User: "Create a config.json with database settings"

Agent will:
1. Use write_file to create config.json
2. Include proper JSON formatting
3. Add comments explaining each setting
```

## Testing

Run the test script to verify all capabilities:

```bash
python test_agent_file_writing.py
```

This will test:
- Writing new files
- Reading files
- Editing files (replace, insert, delete)
- Listing directories
- Searching files
- Creating nested directory structures

## Troubleshooting

### Agent doesn't write files
- **Check**: Is Agent Mode enabled? (button should show "ON")
- **Check**: Is a workspace selected?
- **Check**: Is a model loaded?
- **Check**: Does the agent have permission to write to the workspace?

### Files not appearing
- **Check**: Look in the correct workspace directory
- **Check**: Refresh your file explorer
- **Check**: Check agent status messages for errors

### Permission errors
- **Check**: Workspace directory is writable
- **Check**: Not trying to write to system directories
- **Check**: Workspace path is valid

## Advanced Usage

### Batch Operations
The agent can perform multiple file operations in sequence:
```
User: "Create a web project with index.html, style.css, and script.js"

Agent will execute multiple write_file operations automatically
```

### Complex Edits
The agent can make sophisticated changes:
```
User: "Refactor the code in utils.py to use async/await"

Agent will:
1. Read the file
2. Analyze the code structure
3. Make multiple edit operations
4. Verify the changes
```

## Integration with Full Agentic Chatbot

The SimpleAgent in the main window uses the same tool infrastructure as the full agentic chatbot addon. For more advanced features:

1. Use the full agentic chatbot addon for:
   - Command execution
   - Advanced file analysis
   - Directory structure analysis
   - Metadata operations

2. The tools are defined in:
   - `addons/agentic_chatbot/tools/filesystem.py` - File operations
   - `addons/agentic_chatbot/tools/search.py` - Search operations
   - `addons/agentic_chatbot/tools/execution.py` - Command execution

## API Reference

### SimpleAgent Class

Located in: `core/agent/simple_agent.py`

**Key Methods:**
- `process_message(user_message: str)` - Main entry point
- `_tool_write_file(params: Dict)` - Write file implementation
- `_tool_edit_file(params: Dict)` - Edit file implementation
- `_tool_read_file(params: Dict)` - Read file implementation
- `_tool_list_directory(params: Dict)` - List directory implementation
- `_tool_search_files(params: Dict)` - Search files implementation

**Signals:**
- `response_generated` - Emitted when agent generates a response
- `tool_executed` - Emitted when a tool is executed
- `error_occurred` - Emitted when an error occurs

## Best Practices

1. **Be Specific**: Give clear instructions about what files to create/modify
2. **Use Relative Paths**: Always use paths relative to workspace root
3. **Check Results**: Review agent's confirmation messages
4. **Backup Important Files**: Keep backups before major modifications
5. **Use Version Control**: Git works great with agent-modified files

## Future Enhancements

Planned features:
- File backup before modifications
- Undo/redo operations
- Diff preview before applying changes
- Multi-file refactoring
- Code formatting integration
- Syntax validation

## Support

For issues or questions:
1. Check the logs in the `logs/` directory
2. Review agent status messages in the UI
3. Test with the provided test script
4. Check file permissions in workspace

## Conclusion

The agent file writing capabilities make GGUF Loader a powerful tool for:
- Code generation
- Project scaffolding
- File management
- Documentation creation
- Configuration management

The agent understands natural language instructions and translates them into precise file operations, making it easy to work with files without leaving the chat interface.
