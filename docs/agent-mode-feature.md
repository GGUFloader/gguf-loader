# Agent Mode in Main Chat Window

## Overview

The main GGUF Loader chat window now includes an **Agent Mode** feature that allows you to enable agentic capabilities with tool execution directly from the main interface, without needing to open a separate agent window.

## Features

### 1. Agent Mode Toggle
- **Location**: Left sidebar, under "Agent Mode" section
- **Control**: Checkbox labeled "🔧 Enable Agent Mode"
- **Function**: Toggles between regular chat mode and agent mode

### 2. Workspace Selector
- **Visibility**: Appears when Agent Mode is enabled
- **Components**:
  - Dropdown combo box with common workspace paths
  - Browse button (📁) to select custom workspace folder
  - Agent status indicator showing current state

### 3. Automatic Message Routing
- When Agent Mode is enabled, all messages are automatically routed through the agentic chatbot
- The agent can execute tools, access files, and perform complex tasks
- Responses include tool execution status and results

## How to Use

### Step 1: Enable Agent Mode
1. Open GGUF Loader
2. Load a model (required for agent operation)
3. In the left sidebar, find the "🤖 Agent Mode" section
4. Check the "🔧 Enable Agent Mode" checkbox

### Step 2: Select Workspace
1. Once Agent Mode is enabled, the workspace selector appears
2. Choose from predefined workspace paths:
   - `./agent_workspace` (default)
   - `./workspace`
   - `./projects`
3. Or click the 📁 button to browse for a custom folder
4. The workspace will be created automatically if it doesn't exist

### Step 3: Start Chatting
1. Wait for the agent status to show "🟢 Agent: Ready"
2. Type your message in the chat input
3. Messages will be processed by the agent with tool execution capabilities
4. You'll see:
   - Your message (right side, blue bubble)
   - Agent processing indicators
   - Tool execution notifications
   - Agent responses (left side, gray bubble)

## Agent Status Indicators

- **⚪ Agent: Inactive** - Agent mode is disabled
- **🟡 Agent: Initializing...** - Agent session is being created
- **🟢 Agent: Ready** - Agent is ready to process messages
- **❌ Agent: Error** - There was an error initializing the agent

## System Messages

The chat will display system messages to keep you informed:

- **🤖 Agent mode activated** - Confirms agent mode is enabled with session details
- **🔧 Agent is using tool: [tool_name]** - Shows when the agent executes a tool
- **🤔 Agent is processing your request...** - Indicates the agent is working
- **❌ Agent error: [message]** - Reports any errors that occur

## Switching Between Modes

You can toggle Agent Mode on/off at any time:

- **Disable Agent Mode**: Uncheck the "Enable Agent Mode" checkbox
  - Messages will use regular chat mode
  - Workspace selector will hide
  - Agent session will be cleared

- **Re-enable Agent Mode**: Check the checkbox again
  - A new agent session will be created
  - Previous workspace selection is remembered

## Requirements

1. **Model Loaded**: A GGUF model must be loaded before using Agent Mode
2. **Agentic Chatbot Addon**: The agentic_chatbot addon must be installed and enabled
3. **Workspace**: A valid workspace directory (created automatically if needed)

## Troubleshooting

### "Agent addon not loaded"
- Make sure the agentic_chatbot addon is enabled in the addon sidebar
- Restart GGUF Loader if the addon was just installed

### "Model: Not loaded"
- Load a GGUF model using the "Select GGUF Model" button in the sidebar
- Wait for the model to finish loading before enabling Agent Mode

### "Workspace error"
- Check that you have write permissions in the selected directory
- Try selecting a different workspace folder
- Ensure the path doesn't contain special characters

### Agent not responding
- Check the agent status indicator
- Try disabling and re-enabling Agent Mode
- Check the console/logs for error messages

## Technical Details

### Architecture
- **Agent Mode Mixin**: `mixins/agent_mode_mixin.py` - Handles agent mode logic
- **UI Setup**: `mixins/ui_setup_mixin.py` - Creates agent mode UI components
- **Message Routing**: `mixins/chat_handler_mixin.py` - Routes messages to agent when enabled

### Signal Flow
1. User enables Agent Mode → `toggle_agent_mode()` called
2. Agent session created → Signals connected to agent loop
3. User sends message → `send_message_to_agent()` called
4. Agent processes → Tool calls and responses flow through signals
5. Responses displayed → Chat bubbles updated with agent output

### Integration Points
- Integrates with existing agentic_chatbot addon
- Uses addon manager to access agent functionality
- Connects to agent loop signals for real-time updates
- Maintains separate conversation history for agent mode

## Future Enhancements

Potential improvements for future versions:

- [ ] Persistent workspace history
- [ ] Agent configuration options in UI
- [ ] Tool execution visualization
- [ ] Agent conversation export
- [ ] Multiple agent profiles
- [ ] Agent performance metrics

## See Also

- [Agentic Chatbot Addon Documentation](../addons/agentic_chatbot/README.md)
- [GGUF Loader User Guide](user-guide.md)
- [Addon Development Guide](addon-development.md)
