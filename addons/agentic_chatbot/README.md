# Agentic Chatbot Addon

An autonomous agent system addon for GGUF Loader that provides tool-calling capabilities, secure workspace sandboxing, and agent orchestration features.

## Features

- **File System Operations**: Read, write, edit, and manage files within secure workspace
- **Command Execution**: Execute shell commands with security filtering and validation
- **Search and Analysis**: Search file contents and analyze directory structures
- **Secure Sandboxing**: All operations confined to designated workspace with path validation
- **Tool Registry**: Extensible system for registering and managing agent tools
- **Agent Sessions**: Multiple concurrent agent sessions with independent workspaces

## Architecture

### Core Components

- **AgenticChatbotAddon** (`main.py`): Main addon class that integrates with GGUF Loader
- **AgentController** (`agent_controller.py`): Orchestrates agent sessions and tool execution
- **ToolRegistry** (`tool_registry.py`): Manages available tools and their execution
- **SandboxValidator** (`security/sandbox.py`): Enforces workspace boundaries and path security
- **CommandFilter** (`security/command_filter.py`): Validates and filters command execution

### Security Features

- **Workspace Confinement**: All file operations restricted to designated workspace
- **Path Traversal Prevention**: Blocks attempts to access files outside workspace
- **Command Filtering**: Allowlist/denylist validation for command execution
- **Security Logging**: Audit trail for security violations and blocked attempts

## Installation

The addon is automatically loaded by the GGUF Loader addon system when placed in the `addons/` directory.

## Configuration

Default configuration includes:

```python
{
    # Workspace settings
    "default_workspace": "./agent_workspace",
    "auto_create_workspace": True,
    
    # Security settings
    "allowed_commands": ["ls", "grep", "find", "cat", "head", "tail", "wc", "sort", "uniq"],
    "denied_commands": ["rm", "sudo", "chmod", "chown", "dd", "mkfs"],
    "command_timeout": 30,
    
    # Agent behavior
    "max_iterations": 15,
    "max_tool_calls_per_turn": 5,
    "enable_multi_step_planning": True
}
```

## Usage

1. The addon appears in the GGUF Loader sidebar as "🤖 Agentic Chatbot"
2. Click "Create Session" to start a new agent session
3. Agent sessions operate within secure workspace boundaries
4. Tools are executed through the registry with security validation

## Development Status

This is the initial structure implementation (Task 1). Additional features will be implemented in subsequent tasks:

- File system tools (Task 3)
- Search and command execution tools (Task 5)
- Agent loop and conversation management (Task 6)
- UI components (Task 9)
- Configuration system (Task 10)

## Security

The addon implements multiple layers of security:

1. **Sandbox Validation**: All file paths validated against workspace boundaries
2. **Command Filtering**: Commands validated against allowlist/denylist
3. **Path Traversal Protection**: Prevents access to files outside workspace
4. **Security Logging**: Audit trail for security events

## Integration

The addon integrates with existing GGUF Loader components:

- Uses existing model loading and chat generation systems
- Follows established addon patterns and lifecycle management
- Integrates with PySide6/Qt6 UI framework
- Uses existing configuration system patterns