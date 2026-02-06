# Agent Mode Quick Start Guide

## 🚀 Getting Started in 3 Steps

### 1. Enable Agent Mode
Click the **"🤖 Agent Mode: OFF"** button → It turns to **"🤖 Agent Mode: ON"**

### 2. Select Workspace
Choose a folder where the agent can work (or use the default `agent_workspace`)

### 3. Start Chatting!
The agent can now create and modify files for you.

---

## 💬 Example Commands

### Create Files
```
"Create a Python script called calculator.py"
"Write a README.md for my project"
"Create a config.json with these settings..."
```

### Modify Files
```
"In script.py, replace 'old_name' with 'new_name'"
"Add error handling to the main function"
"Insert a comment at line 10"
```

### Explore Files
```
"List all files in the workspace"
"Show me the contents of config.json"
"Search for the word 'TODO' in all files"
```

---

## 🛠️ Available Tools

| Tool | What It Does | Example |
|------|-------------|---------|
| **write_file** | Create or overwrite files | "Create hello.py" |
| **edit_file** | Modify existing files | "Replace X with Y in file.txt" |
| **read_file** | Read file contents | "Show me the code in main.py" |
| **list_directory** | List files and folders | "What files are in the workspace?" |
| **search_files** | Find text in files | "Find all files containing 'error'" |

---

## ✅ What the Agent CAN Do

- ✅ Create new files with any content
- ✅ Modify existing files
- ✅ Create nested directory structures
- ✅ Read and analyze files
- ✅ Search across multiple files
- ✅ Generate code, configs, documentation
- ✅ Refactor and improve code

## ❌ What the Agent CANNOT Do

- ❌ Access files outside the workspace
- ❌ Execute system commands (in SimpleAgent)
- ❌ Access the internet
- ❌ Modify GGUF Loader itself

---

## 🔒 Security

- **Sandboxed**: Agent only works in the selected workspace
- **Safe**: Cannot access system files or parent directories
- **Controlled**: You choose the workspace location

---

## 💡 Pro Tips

1. **Be Specific**: "Create a Python class for user authentication" works better than "make a file"
2. **Use Natural Language**: The agent understands conversational requests
3. **Check Results**: The agent will confirm what it did
4. **Iterate**: Ask the agent to refine or fix its work
5. **Backup**: Keep important files backed up before major changes

---

## 🐛 Troubleshooting

**Agent not responding?**
- Check that Agent Mode is ON
- Verify a model is loaded
- Ensure workspace is selected

**Files not created?**
- Check the workspace directory
- Verify you have write permissions
- Look for error messages in the chat

**Wrong output?**
- Be more specific in your request
- Ask the agent to read the file first
- Request corrections: "That's not quite right, try again with..."

---

## 📚 Learn More

- Full documentation: `AGENT_FILE_WRITING_GUIDE.md`
- Test the features: `python test_agent_file_writing.py`
- Advanced features: Check the agentic chatbot addon

---

## 🎯 Quick Examples

### Example 1: Create a Web Page
```
You: "Create an HTML file with a simple homepage"
Agent: Creates index.html with proper HTML structure
```

### Example 2: Generate Python Code
```
You: "Write a Python script that reads a CSV and calculates averages"
Agent: Creates script.py with pandas code
```

### Example 3: Modify Configuration
```
You: "In config.json, change the port from 8080 to 3000"
Agent: Uses edit_file to make the change
```

### Example 4: Project Setup
```
You: "Set up a basic Flask project structure"
Agent: Creates app.py, requirements.txt, templates/, static/
```

---

## 🎉 You're Ready!

Just enable Agent Mode, select a workspace, and start creating!

The agent is here to help you write code, create files, and manage your projects through natural conversation.
