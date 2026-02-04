Enhanced Prompt: Local Agentic Chatbot with GGUF Integration
You are a senior AI systems architect specializing in agentic AI systems and local LLM deployment. Your task is to design and implement a production-ready local agentic chatbot that transforms a GGUF model (via llama.cpp or similar inference engine) into an autonomous agent capable of performing file operations and executing commands within a sandboxed workspace—similar to Claude Cowork AI.
Core Requirements
1. Agent Capabilities
The agent must support the following tool operations:

File System Operations:

list_directory: Enumerate files and subdirectories with optional filtering
read_file: Read complete file contents with encoding detection
write_file: Create or overwrite files atomically
edit_file: Perform targeted edits (find-replace, line insertion)
append_file: Append content to existing files
delete_file: Remove files safely
create_directory: Create new directories


Search & Analysis:

search_files: Regex or text search across files with context
get_file_info: Retrieve metadata (size, modified time, permissions)


Execution:

execute_command: Run shell commands with timeout and output capture
Implement allowlist/denylist for command safety



2. Security & Sandboxing

Workspace Isolation:

All operations confined to a designated workspace root
Implement robust path traversal prevention (resolve symlinks, validate canonical paths)
Reject operations on hidden files/system directories by default


Command Execution Safety:

Whitelist approved commands (e.g., ls, grep, python, git)
Blacklist dangerous commands (rm -rf, sudo, chmod, etc.)
Run commands with timeout limits (configurable, default 30s)
Capture both stdout and stderr


Error Handling:

Graceful degradation on permission errors
Clear error messages returned to the LLM for self-correction



3. Agent Architecture
A. Tool Call Protocol
The agent must use a structured JSON tool calling system:
json{
  "tool": "read_file",
  "parameters": {
    "path": "src/main.py",
    "encoding": "utf-8"
  },
  "call_id": "call_001"
}
Response format:
json{
  "call_id": "call_001",
  "status": "success",
  "result": "file contents here...",
  "error": null
}
```

#### B. System Prompt Engineering
Create a comprehensive system prompt that:
- Defines the agent's role and capabilities
- Provides clear examples of tool usage
- Encourages step-by-step reasoning
- Includes error recovery strategies
- Emphasizes workspace boundaries

#### C. Conversation Loop
1. User provides a task
2. LLM generates reasoning + tool calls
3. Tool router validates and executes each call
4. Results injected back into conversation context
5. LLM decides: continue with more tools OR provide final answer
6. Maintain conversation history with token budget management

### 4. Implementation Structure

#### Module Organization
```
agentic_gguf/
├── core/
│   ├── llm_engine.py          # GGUF model loading & inference
│   ├── agent.py               # Main agent loop & orchestration
│   └── context_manager.py     # Conversation history management
├── tools/
│   ├── base.py                # Tool base class & registry
│   ├── filesystem.py          # File operation tools
│   ├── execution.py           # Command execution tools
│   └── search.py              # Search & analysis tools
├── security/
│   ├── sandbox.py             # Workspace validation & path safety
│   └── command_filter.py      # Command allowlist/denylist
├── utils/
│   ├── logging.py             # Structured logging
│   └── config.py              # Configuration management
├── main.py                    # CLI entry point
└── config.yaml                # Configuration file
Key Design Patterns

Tool Registry Pattern: Self-registering tools with metadata
Chain of Responsibility: Security validators before execution
Observer Pattern: Logging and monitoring hooks
Strategy Pattern: Pluggable LLM backends (llama-cpp-python, ctransformers, etc.)

5. LLM Integration
Model Requirements

Support for function calling or tool use via:

Structured output generation (JSON mode)
Or prompt-based tool calling (parse from text)


Recommended models:

Llama 3.1 8B Instruct (or larger)
Mistral 7B Instruct v0.3
OpenChat 3.5
Any model fine-tuned for tool use



Inference Options
Provide adapters for multiple backends:

llama-cpp-python (primary, C++ bindings)
ctransformers (alternative)
vLLM (for GPU acceleration)
ExLlamaV2 (for high-performance GPTQ)

Configuration Parameters
yamlmodel:
  path: "models/llama-3.1-8b-instruct.Q5_K_M.gguf"
  context_length: 8192
  max_tokens: 2048
  temperature: 0.1
  top_p: 0.9
  stop_sequences: ["</tool_call>", "<|eot_id|>"]
  
agent:
  max_iterations: 15
  workspace: "./workspace"
  allowed_commands: ["ls", "grep", "python3", "git"]
  command_timeout: 30
6. Advanced Features
A. Multi-Step Planning

Agent can create execution plans before tool calls
Implement reflection: review results and adjust strategy

B. Memory & State Management

Track completed tasks to avoid redundant work
Maintain file modification history
Implement short-term memory (conversation) + long-term memory (summaries)

C. Streaming & Interactivity

Stream LLM responses token-by-token
Allow user interruption/confirmation before dangerous operations
Progress indicators for long-running commands

D. Extensibility Hooks

Plugin system for custom tools
Event callbacks (on_tool_call, on_error, on_completion)
Custom validators and post-processors

7. Comprehensive Example Usage
Provide a detailed walkthrough demonstrating:
Task: "Refactor all Python files in the src/ directory: add type hints to function signatures and add a docstring if missing."
Expected Agent Behavior:

list_directory on src/ to find all .py files
For each file:

read_file to load contents
Analyze code structure (using LLM reasoning)
Generate improved version with type hints and docstrings
write_file with updated content


execute_command to run black src/ for formatting
Provide summary of changes made

8. Testing & Validation
Include:

Unit tests for each tool (mocked filesystem)
Integration tests with actual LLM inference
Security tests verifying sandbox escapes are prevented
Performance benchmarks (tokens/sec, tool call latency)

9. Documentation Requirements
Provide:

README.md with:

Quick start guide
Installation instructions (dependencies, model download)
Configuration options
Example prompts and expected outputs


API Documentation:

Tool schemas (parameters, return types)
Agent API for programmatic use


Architecture Guide:

System diagrams (data flow, component interaction)
Extension points for custom tools
Troubleshooting common issues



10. Performance Considerations

Context Window Management:

Implement sliding window for long conversations
Compress or summarize old tool results


Caching:

Cache file contents read multiple times
Cache LLM KV cache for repeated prefixes


Parallel Execution:

Execute independent tool calls concurrently
Batch file reads when possible



11. Deliverables Checklist

 Complete Python codebase following the module structure
 Configuration file with sensible defaults
 System prompt optimized for tool use
 CLI interface with rich output formatting
 Logging system with multiple verbosity levels
 At least 3 end-to-end example scenarios
 Unit test suite with >80% coverage
 README with setup instructions
 Requirements.txt (or pyproject.toml)
 Docker support (optional but recommended)

Constraints
Technical

Python Version: 3.10+
Dependencies: Minimize; prefer standard library when possible
Required External Libraries:

llama-cpp-python or equivalent GGUF loader
pydantic for data validation
rich for CLI output (optional)
pytest for testing



Code Quality

Type hints throughout (use mypy for validation)
Docstrings for all public functions (Google or NumPy style)
Maximum function length: 50 lines
Follow PEP 8 with black formatting

Security Hardening

No eval() or exec() usage
Validate all file paths through centralized validator
Log all tool calls with timestamp and user context
Implement rate limiting for command execution (optional)

Bonus Enhancements
Consider implementing:

Web UI: Simple FastAPI or Gradio interface
Multi-agent collaboration: Spawn sub-agents for parallel tasks
Git integration: Track changes in version control
Recovery mode: Undo recent actions
Templates: Pre-built workflows (e.g., "create Flask app")
Observability: Export traces to OpenTelemetry