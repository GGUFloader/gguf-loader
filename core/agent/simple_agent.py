"""
Simple Agent - Lightweight agent implementation for main GGUF Loader chat
"""
import json
import re
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread

from models.chat_generator import ChatGenerator


class AgentWorker(QThread):
    """Worker thread for agent processing to prevent UI blocking"""
    
    # Signals
    response_generated = Signal(str)
    tool_executed = Signal(dict)
    error_occurred = Signal(str)
    processing_started = Signal()
    processing_finished = Signal()
    status_update = Signal(str)  # For streaming status messages
    
    def __init__(self, agent, user_message: str):
        super().__init__()
        self.agent = agent
        self.user_message = user_message
        self._is_running = True
    
    def run(self):
        """Run agent processing in separate thread"""
        try:
            self.processing_started.emit()
            self.agent._process_message_internal(
                self.user_message,
                self.response_generated,
                self.tool_executed,
                self.error_occurred,
                self.status_update  # Pass status signal
            )
        except Exception as e:
            self.agent._logger.error(f"Worker thread error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.processing_finished.emit()
    
    def stop(self):
        """Stop the worker thread"""
        self._is_running = False


class SimpleAgent(QObject):
    """
    Simplified agent for main chat window with tool execution capabilities.
    
    This is a lightweight version that doesn't require the full addon infrastructure.
    Now runs in a separate thread to prevent UI blocking.
    """
    
    # Signals
    response_generated = Signal(str)
    tool_executed = Signal(dict)
    error_occurred = Signal(str)
    processing_started = Signal()
    processing_finished = Signal()
    status_update = Signal(str)  # For streaming status messages
    
    def __init__(self, model, workspace_path: str):
        super().__init__()
        self.model = model
        self.workspace_path = Path(workspace_path)
        self._logger = logging.getLogger(__name__)
        self.conversation_history = []
        self._current_worker = None
        
        # Ensure workspace exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)
    
    def process_message(self, user_message: str):
        """Process user message asynchronously to prevent UI blocking"""
        try:
            # Stop any existing worker
            if self._current_worker and self._current_worker.isRunning():
                self._current_worker.stop()
                self._current_worker.wait(1000)  # Wait up to 1 second
            
            # Create and start new worker thread
            self._current_worker = AgentWorker(self, user_message)
            
            # Connect worker signals to agent signals
            self._current_worker.response_generated.connect(self.response_generated.emit)
            self._current_worker.tool_executed.connect(self.tool_executed.emit)
            self._current_worker.error_occurred.connect(self.error_occurred.emit)
            self._current_worker.processing_started.connect(self.processing_started.emit)
            self._current_worker.processing_finished.connect(self.processing_finished.emit)
            self._current_worker.status_update.connect(self.status_update.emit)
            
            # Start processing in background thread
            self._current_worker.start()
            
        except Exception as e:
            self._logger.error(f"Error starting agent worker: {e}")
            self.error_occurred.emit(str(e))
    
    def _process_message_internal(self, user_message: str, response_signal, tool_signal, error_signal, status_signal):
        """Internal message processing (runs in worker thread)"""
        try:
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            # Quick analysis for complex requests only
            # For simple requests, skip straight to planning
            is_complex = len(user_message.split()) > 20 or any(word in user_message.lower() for word in ['complex', 'multiple', 'several', 'build', 'create system'])
            
            if is_complex:
                status_signal.emit("🤔 Analyzing your request...")
                
                analysis_prompt = f"""Quickly analyze this request:

User Request: {user_message}

In 2-3 sentences, tell me:
1. What they want
2. What operations are needed
3. Any potential issues

Be concise and direct."""
                
                analysis_response = self._generate_response(analysis_prompt, stream_to_ui=False, status_signal=status_signal)
                status_signal.emit(f"💡 {analysis_response.strip()}")
                status_signal.emit("")
            
            # Build system prompt and context
            system_prompt = self._build_system_prompt()
            context = self._build_context(system_prompt, user_message)
            
            # Generate response to get tool calls (don't show raw JSON to user)
            response_text = self._generate_response(context, stream_to_ui=False, status_signal=None)
            
            # Parse for tool calls
            tool_calls = self._parse_tool_calls(response_text)
            
            # Extract and show reasoning naturally
            reasoning = self._extract_reasoning(response_text)
            if reasoning and tool_calls:
                status_signal.emit(f"💭 {reasoning}")
                status_signal.emit("")
            
            if tool_calls:
                # Show plan concisely
                if len(tool_calls) == 1:
                    tool_name = tool_calls[0].get("tool", "unknown")
                    parameters = tool_calls[0].get("parameters", {})
                    task_desc = self._describe_single_task(tool_name, parameters)
                    status_signal.emit(f"→ {task_desc}")
                else:
                    status_signal.emit(f"→ {len(tool_calls)} tasks to complete:")
                    for idx, tool_call in enumerate(tool_calls, 1):
                        tool_name = tool_call.get("tool", "unknown")
                        parameters = tool_call.get("parameters", {})
                        task_desc = self._describe_single_task(tool_name, parameters)
                        status_signal.emit(f"  {idx}. {task_desc}")
                status_signal.emit("")
                
                tool_results = []
                
                # Execute tasks with minimal status updates
                for idx, tool_call in enumerate(tool_calls, 1):
                    tool_name = tool_call.get("tool", "unknown")
                    parameters = tool_call.get("parameters", {})
                    
                    # Brief status update
                    if len(tool_calls) > 1:
                        status_signal.emit(f"[{idx}/{len(tool_calls)}] {self._describe_single_task(tool_name, parameters)}")
                    
                    # Execute the tool
                    result = self._execute_tool(tool_call)
                    tool_results.append(result)
                    tool_signal.emit(result)
                    
                    # Show result concisely
                    if result.get("status") == "success":
                        update_message = self._generate_task_update(tool_name, result, parameters)
                        status_signal.emit(f"  ✓ {update_message}")
                    else:
                        error_msg = result.get("error", "Unknown error")
                        status_signal.emit(f"  ✗ {error_msg}")
                        # For errors, suggest what to do
                        status_signal.emit(f"  → Trying to continue anyway...")
                
                # Generate final response
                status_signal.emit("")
                final_response = self._generate_final_response(user_message, tool_results, status_signal)
            else:
                # No tools needed - direct answer
                final_response = response_text
            
            # Add to history
            self.conversation_history.append({
                "role": "assistant",
                "content": final_response
            })
            
            # Emit response
            response_signal.emit(final_response)
            
        except Exception as e:
            self._logger.error(f"Error processing message: {e}")
            error_signal.emit(str(e))
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for agent - Kiro-style personality"""
        return f"""You are Kiro, an AI assistant built to help developers. You're knowledgeable, decisive, and supportive.

Your personality:
- Talk like a human, not a bot. Be conversational and natural.
- Be decisive and clear. Skip the fluff.
- Show expertise without being condescending.
- Stay warm and friendly. You're a partner, not a cold tech tool.
- Be concise - say what matters, nothing more.
- Adapt your verbosity: detailed for complex tasks, brief for simple ones.

Your workspace: {self.workspace_path}

You have access to these tools:
- list_directory: List files in a directory
  Parameters: {{"path": "directory_path"}}
  
- read_file: Read file contents
  Parameters: {{"path": "file_path"}}
  
- write_file: Create or overwrite files
  Parameters: {{"path": "file_path", "content": "file_content"}}
  
- edit_file: Modify existing files (find-replace, insert/delete lines)
  Parameters: {{"path": "file_path", "operation": "replace|insert_line|delete_line", "find": "text_to_find", "replace": "replacement_text", "line_number": 1, "content": "line_content"}}
  
- search_files: Search for text in files
  Parameters: {{"pattern": "search_text", "path": "directory_path"}}

When you need tools, respond ONLY with this JSON format (no other text):
```json
{{
    "reasoning": "Brief, natural explanation like: 'I'll create the file first, then list the directory to see what's there'",
    "tool_calls": [
        {{
            "tool": "tool_name",
            "parameters": {{"param": "value"}}
        }}
    ]
}}
```

IMPORTANT for reasoning:
- Write it like you're talking to a friend, not writing documentation
- Use "I'll" instead of "Need to" or "Will"
- Be specific about what you're doing: "I'll create summary.md, then read all the files to gather content"
- Keep it under 15 words
- NO technical jargon or formal language

Examples of GOOD reasoning:
- "I'll create the file first, then list what's in the directory"
- "Let me read the config to see what we're working with"
- "I'll search for that pattern across all Python files"

Examples of BAD reasoning:
- "Create a markdown file to store the summary, then read all files in the folder to gather content for summarization"
- "Need to execute write_file operation followed by list_directory"
- "Will perform file creation and subsequent directory listing operations"

Key behaviors:
- Jump straight into action when the task is clear
- Use tools proactively - don't over-explain, just do it
- For simple tasks, be brief. For complex ones, provide context.
- If something fails, explain what happened and suggest alternatives
- Always work within the workspace directory
- Parent directories are created automatically

Remember: You're here to enhance their ability to code well, not to write code for them. Be their capable, easygoing partner."""
    
    def _build_context(self, system_prompt: str, current_message: str) -> str:
        """Build conversation context"""
        context = system_prompt + "\n\n"
        
        # Add recent history (last 3 exchanges)
        recent = self.conversation_history[-6:] if len(self.conversation_history) > 6 else self.conversation_history
        for msg in recent:
            role = msg["role"].capitalize()
            context += f"{role}: {msg['content']}\n\n"
        
        context += f"User: {current_message}\nAssistant: "
        return context
    
    def _generate_response(self, context: str, stream_to_ui: bool = False, status_signal=None) -> str:
        """Generate response using the model
        
        Args:
            context: The prompt context
            stream_to_ui: If True, stream tokens to UI as they're generated
            status_signal: Signal to emit streaming updates to
        """
        try:
            chat_gen = ChatGenerator(
                model=self.model,
                prompt=context,
                chat_history=[],
                max_tokens=2048,
                temperature=0.1,
                system_prompt_name="assistant"
            )
            
            response_text = ""
            token_count = 0
            last_update_length = 0
            
            def on_token(token):
                nonlocal response_text, token_count, last_update_length
                response_text += token
                token_count += 1
                
                # Stream to UI if requested
                if stream_to_ui and status_signal and token_count % 5 == 0:  # Update every 5 tokens
                    # Show partial response
                    if len(response_text) - last_update_length > 50:  # Update when we have 50+ new chars
                        preview = response_text[-100:] if len(response_text) > 100 else response_text
                        status_signal.emit(f"💭 Model thinking: ...{preview}")
                        last_update_length = len(response_text)
            
            chat_gen.token_received.connect(on_token)
            chat_gen.run()
            
            return response_text
            
        except Exception as e:
            self._logger.error(f"Error generating response: {e}")
            return "I encountered an error generating a response."
    
    def _parse_tool_calls(self, response: str) -> List[Dict]:
        """Parse tool calls from response"""
        try:
            # Look for JSON blocks
            json_pattern = r'```json\s*(\{.*?\})\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            if matches:
                data = json.loads(matches[0])
                return data.get("tool_calls", [])
            
            return []
        except Exception as e:
            self._logger.debug(f"No tool calls found: {e}")
            return []
    
    def _extract_reasoning(self, response: str) -> str:
        """Extract reasoning from response"""
        try:
            # Look for JSON blocks
            json_pattern = r'```json\s*(\{.*?\})\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            if matches:
                data = json.loads(matches[0])
                return data.get("reasoning", "")
            
            return ""
        except Exception as e:
            self._logger.debug(f"No reasoning found: {e}")
            return ""
    
    def _execute_tool(self, tool_call: Dict) -> Dict:
        """Execute a tool call"""
        tool_name = tool_call.get("tool", "")
        parameters = tool_call.get("parameters", {})
        
        try:
            if tool_name == "list_directory":
                return self._tool_list_directory(parameters)
            elif tool_name == "read_file":
                return self._tool_read_file(parameters)
            elif tool_name == "write_file":
                return self._tool_write_file(parameters)
            elif tool_name == "edit_file":
                return self._tool_edit_file(parameters)
            elif tool_name == "search_files":
                return self._tool_search_files(parameters)
            else:
                return {
                    "status": "error",
                    "error": f"Unknown tool: {tool_name}",
                    "tool_name": tool_name
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "tool_name": tool_name
            }
    
    def _tool_list_directory(self, params: Dict) -> Dict:
        """List directory contents"""
        try:
            path = Path(params.get("path", "."))
            if not path.is_absolute():
                path = self.workspace_path / path
            
            if not path.exists():
                return {"status": "error", "error": "Directory not found"}
            
            items = []
            for item in path.iterdir():
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0
                })
            
            return {
                "status": "success",
                "result": items,
                "tool_name": "list_directory"
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": "list_directory"}
    
    def _tool_read_file(self, params: Dict) -> Dict:
        """Read file contents"""
        try:
            raw_path = params.get("path", "")
            if not raw_path:
                return {"status": "error", "error": "Path is required", "tool_name": "read_file"}

            path = Path(raw_path)
            if not path.is_absolute():
                path = self.workspace_path / path
            
            if not path.exists():
                return {"status": "error", "error": "File not found", "tool_name": "read_file"}

            if not path.is_file():
                return {"status": "error", "error": "Path is not a file", "tool_name": "read_file"}

            max_size = int(params.get("max_size", 10 * 1024 * 1024))  # 10MB default
            file_size = path.stat().st_size
            if file_size > max_size:
                return {
                    "status": "error",
                    "error": f"File too large: {file_size} bytes (max: {max_size})",
                    "tool_name": "read_file"
                }

            requested_encoding = params.get("encoding", "auto")
            raw_data = path.read_bytes()
            content, used_encoding = self._decode_file_content(raw_data, requested_encoding)
            
            return {
                "status": "success",
                "result": content,
                "tool_name": "read_file",
                "encoding": used_encoding,
                "size": file_size,
                "lines": len(content.splitlines())
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": "read_file"}

    def _decode_file_content(self, raw_data: bytes, encoding: str) -> tuple[str, str]:
        """Decode raw file bytes into text with best-effort encoding detection."""
        if encoding and encoding != "auto":
            try:
                return raw_data.decode(encoding, errors="replace"), encoding
            except Exception:
                return raw_data.decode("utf-8", errors="replace"), "utf-8"

        # BOM-based detection first
        if raw_data.startswith(b'\xef\xbb\xbf'):
            return raw_data.decode("utf-8-sig", errors="replace"), "utf-8-sig"
        if raw_data.startswith(b'\xff\xfe') or raw_data.startswith(b'\xfe\xff'):
            return raw_data.decode("utf-16", errors="replace"), "utf-16"
        if raw_data.startswith(b'\xff\xfe\x00\x00') or raw_data.startswith(b'\x00\x00\xfe\xff'):
            return raw_data.decode("utf-32", errors="replace"), "utf-32"

        # Try utf-8 strictly first, then common fallbacks
        try:
            return raw_data.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            pass

        for fallback in ("cp1252", "latin-1"):
            try:
                return raw_data.decode(fallback, errors="replace"), fallback
            except Exception:
                continue

        return raw_data.decode("utf-8", errors="replace"), "utf-8"
    
    def _tool_write_file(self, params: Dict) -> Dict:
        """Write file contents - creates new file or overwrites existing"""
        try:
            path = Path(params.get("path", ""))
            if not path.is_absolute():
                path = self.workspace_path / path
            
            content = params.get("content", "")
            
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            path.write_text(content, encoding='utf-8')
            
            return {
                "status": "success",
                "result": f"Successfully wrote {len(content)} characters to {path.name}",
                "path": str(path.relative_to(self.workspace_path)),
                "bytes_written": len(content.encode('utf-8')),
                "tool_name": "write_file"
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": "write_file"}
    
    def _tool_edit_file(self, params: Dict) -> Dict:
        """Edit file with find-replace or line operations"""
        try:
            path = Path(params.get("path", ""))
            if not path.is_absolute():
                path = self.workspace_path / path
            
            if not path.exists():
                return {"status": "error", "error": "File not found", "tool_name": "edit_file"}
            
            operation = params.get("operation", "replace")
            
            # Read current content
            content = path.read_text(encoding='utf-8')
            lines = content.splitlines(keepends=True)
            
            changes_made = 0
            
            if operation == "replace":
                find_text = params.get("find", "")
                replace_text = params.get("replace", "")
                
                if not find_text:
                    return {"status": "error", "error": "Find text required for replace operation", "tool_name": "edit_file"}
                
                new_content = content.replace(find_text, replace_text)
                changes_made = content.count(find_text)
                
            elif operation == "insert_line":
                line_number = params.get("line_number", 1)
                insert_content = params.get("content", "")
                
                if line_number <= len(lines):
                    lines.insert(line_number - 1, insert_content + '\n')
                else:
                    lines.append(insert_content + '\n')
                
                new_content = ''.join(lines)
                changes_made = 1
                
            elif operation == "delete_line":
                line_number = params.get("line_number", 1)
                
                if 1 <= line_number <= len(lines):
                    del lines[line_number - 1]
                    changes_made = 1
                else:
                    changes_made = 0
                
                new_content = ''.join(lines)
                
            else:
                return {"status": "error", "error": f"Unknown operation: {operation}", "tool_name": "edit_file"}
            
            # Write modified content
            if changes_made > 0:
                path.write_text(new_content, encoding='utf-8')
            
            return {
                "status": "success",
                "result": f"Successfully performed {operation} operation, {changes_made} changes made",
                "path": str(path.relative_to(self.workspace_path)),
                "operation": operation,
                "changes_made": changes_made,
                "tool_name": "edit_file"
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": "edit_file"}
    
    def _tool_search_files(self, params: Dict) -> Dict:
        """Search for text in files"""
        try:
            # Support both 'query' and 'pattern' parameter names
            query = params.get("pattern") or params.get("query", "")
            path = Path(params.get("path", "."))
            if not path.is_absolute():
                path = self.workspace_path / path
            
            results = []
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        if query.lower() in content.lower():
                            results.append(str(file_path.relative_to(self.workspace_path)))
                    except:
                        pass
            
            return {
                "status": "success",
                "result": results,
                "total_matches": len(results),
                "tool_name": "search_files"
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": "search_files"}
    
    def _generate_final_response(self, user_message: str, tool_results: List[Dict], status_signal=None) -> str:
        """Generate final response with tool results - Kiro style"""
        try:
            # Build context with tool results
            context = f"User asked: {user_message}\n\n"
            context += "I completed these operations:\n"
            
            success_count = 0
            for result in tool_results:
                tool_name = result.get("tool_name", "unknown")
                if result.get("status") == "success":
                    success_count += 1
                    context += f"✓ {tool_name}: {result.get('result', 'Success')}\n"
                else:
                    context += f"✗ {tool_name}: {result.get('error', 'Failed')}\n"
            
            context += f"\nProvide a brief, natural response to the user. Be conversational and concise. Don't repeat what you already did - they saw the status updates. Just give them the key takeaway or next steps if relevant."
            
            return self._generate_response(context, stream_to_ui=False, status_signal=status_signal)
            
        except Exception as e:
            self._logger.error(f"Error generating final response: {e}")
            # Fallback to simple summary
            success_count = sum(1 for r in tool_results if r.get("status") == "success")
            if success_count == len(tool_results):
                return "Done! All operations completed successfully."
            elif success_count > 0:
                return f"Completed {success_count} out of {len(tool_results)} operations. Some had issues but I did what I could."
            else:
                return "Ran into some issues completing those operations. Check the errors above."
    
    def _generate_complete_plan(self, tool_calls: List[Dict]) -> str:
        """Generate a complete plan showing all tasks"""
        try:
            if len(tool_calls) == 1:
                tool = tool_calls[0]
                tool_name = tool.get("tool", "unknown")
                params = tool.get("parameters", {})
                return self._describe_single_task(tool_name, params)
            else:
                # Multiple tasks - show numbered list
                plan_lines = [f"I'll complete {len(tool_calls)} tasks:"]
                for idx, tool in enumerate(tool_calls, 1):
                    tool_name = tool.get("tool", "unknown")
                    params = tool.get("parameters", {})
                    task_desc = self._describe_single_task(tool_name, params)
                    plan_lines.append(f"  {idx}. {task_desc}")
                return "\n".join(plan_lines)
        except Exception as e:
            self._logger.error(f"Error generating plan: {e}")
            return f"I'll execute {len(tool_calls)} operation(s)"
    
    def _describe_single_task(self, tool_name: str, params: Dict) -> str:
        """Describe a single task naturally"""
        try:
            if tool_name == "write_file":
                path = params.get("path", "file")
                return f"Write {path}"
            
            elif tool_name == "edit_file":
                path = params.get("path", "file")
                operation = params.get("operation", "edit")
                if operation == "replace":
                    find = params.get("find", "")[:20]
                    return f"Edit {path}"
                else:
                    return f"Modify {path}"
            
            elif tool_name == "read_file":
                path = params.get("path", "file")
                return f"Read {path}"
            
            elif tool_name == "list_directory":
                path = params.get("path", ".")
                return f"List files in {path}"
            
            elif tool_name == "search_files":
                pattern = params.get("pattern", "text")
                return f"Search for '{pattern}'"
            
            else:
                return f"{tool_name}"
        except Exception as e:
            self._logger.error(f"Error describing task: {e}")
            return f"{tool_name}"
    
    def _generate_task_description(self, tool_name: str, parameters: Dict, step: int, total: int) -> str:
        """Generate description of current task being worked on"""
        try:
            task_desc = self._describe_single_task(tool_name, parameters)
            return f"Task {step}/{total} - {task_desc}"
        except Exception as e:
            self._logger.error(f"Error generating task description: {e}")
            return f"Task {step}/{total}: {tool_name}"
    
    def _generate_task_update(self, tool_name: str, result: Dict, parameters: Dict) -> str:
        """Generate concise update after task completion"""
        try:
            status = result.get("status", "unknown")
            
            if status == "success":
                if tool_name == "write_file":
                    path = parameters.get("path", "file")
                    return f"Created {path}"
                
                elif tool_name == "edit_file":
                    path = parameters.get("path", "file")
                    changes = result.get("changes_made", 0)
                    return f"Modified {path}" if changes > 0 else f"No changes needed"
                
                elif tool_name == "read_file":
                    lines = result.get("lines", 0)
                    return f"Read {lines} lines"
                
                elif tool_name == "list_directory":
                    items = result.get("result", [])
                    count = len(items)
                    return f"Found {count} items"
                
                elif tool_name == "search_files":
                    matches = result.get("total_matches", 0)
                    return f"Found {matches} matches" if matches > 0 else "No matches"
                
                else:
                    return "Done"
            else:
                error = result.get("error", "Unknown error")
                return f"Error: {error}"
        except Exception as e:
            self._logger.error(f"Error generating update: {e}")
            return "Completed"
    
    def _generate_next_task_preview(self, tool_name: str, parameters: Dict, step: int, total: int) -> str:
        """Generate preview of next task"""
        try:
            task_desc = self._describe_single_task(tool_name, parameters)
            return f"Task {step}/{total} - {task_desc}"
        except Exception as e:
            self._logger.error(f"Error generating next task preview: {e}")
            return f"Task {step}/{total}: {tool_name}"
    
    def _generate_task_reasoning(self, tool_name: str, parameters: Dict, user_message: str) -> str:
        """Generate reasoning for why this task is needed"""
        try:
            if tool_name == "write_file":
                path = parameters.get("path", "file")
                return f"Creating '{path}' as requested to fulfill your needs"
            
            elif tool_name == "edit_file":
                path = parameters.get("path", "file")
                operation = parameters.get("operation", "edit")
                return f"Modifying '{path}' to make the changes you asked for"
            
            elif tool_name == "read_file":
                path = parameters.get("path", "file")
                return f"Reading '{path}' first so I can understand its current content"
            
            elif tool_name == "list_directory":
                path = parameters.get("path", ".")
                return f"Checking what files exist in '{path}' to give you accurate information"
            
            elif tool_name == "search_files":
                pattern = parameters.get("pattern", "text")
                return f"Searching for '{pattern}' to find all relevant files"
            
            else:
                return f"This step is necessary to complete your request"
        except Exception as e:
            self._logger.error(f"Error generating reasoning: {e}")
            return "Executing this task as part of the plan"
        """Generate natural language plan message"""
        try:
            if len(tool_calls) == 1:
                tool = tool_calls[0]
                tool_name = tool.get("tool", "unknown")
                params = tool.get("parameters", {})
                
                if tool_name == "write_file":
                    path = params.get("path", "file")
                    return f"I'll create the file '{path}' for you"
                elif tool_name == "edit_file":
                    path = params.get("path", "file")
                    operation = params.get("operation", "edit")
                    return f"I'll {operation} the file '{path}'"
                elif tool_name == "read_file":
                    path = params.get("path", "file")
                    return f"Let me read '{path}' first"
                elif tool_name == "list_directory":
                    path = params.get("path", ".")
                    return f"I'll list the contents of '{path}'"
                elif tool_name == "search_files":
                    pattern = params.get("pattern", "text")
                    return f"I'll search for '{pattern}' in your files"
                else:
                    return f"I'll use the {tool_name} tool"
            else:
                # Multiple tools
                tool_names = [t.get("tool", "unknown") for t in tool_calls]
                return f"I'll perform {len(tool_calls)} operations: {', '.join(tool_names)}"
                
        except Exception as e:
            self._logger.error(f"Error generating plan: {e}")
            return f"I'll execute {len(tool_calls)} operation(s)"
    
    def _generate_tool_status(self, tool_name: str, parameters: Dict, step: int, total: int) -> str:
        """Generate natural language status for tool execution"""
        try:
            if tool_name == "write_file":
                path = parameters.get("path", "file")
                content_len = len(parameters.get("content", ""))
                return f"Step {step}/{total}: Writing {content_len} characters to '{path}'..."
            
            elif tool_name == "edit_file":
                path = parameters.get("path", "file")
                operation = parameters.get("operation", "edit")
                if operation == "replace":
                    find = parameters.get("find", "text")
                    return f"Step {step}/{total}: Replacing '{find}' in '{path}'..."
                elif operation == "insert_line":
                    line_num = parameters.get("line_number", 1)
                    return f"Step {step}/{total}: Inserting line at position {line_num} in '{path}'..."
                elif operation == "delete_line":
                    line_num = parameters.get("line_number", 1)
                    return f"Step {step}/{total}: Deleting line {line_num} from '{path}'..."
                else:
                    return f"Step {step}/{total}: Editing '{path}'..."
            
            elif tool_name == "read_file":
                path = parameters.get("path", "file")
                return f"Step {step}/{total}: Reading contents of '{path}'..."
            
            elif tool_name == "list_directory":
                path = parameters.get("path", ".")
                return f"Step {step}/{total}: Listing files in '{path}'..."
            
            elif tool_name == "search_files":
                pattern = parameters.get("pattern", "text")
                path = parameters.get("path", ".")
                return f"Step {step}/{total}: Searching for '{pattern}' in '{path}'..."
            
            else:
                return f"Step {step}/{total}: Executing {tool_name}..."
                
        except Exception as e:
            self._logger.error(f"Error generating tool status: {e}")
            return f"Step {step}/{total}: Executing {tool_name}..."
    
    def _generate_result_message(self, tool_name: str, result: Dict, parameters: Dict) -> str:
        """Generate natural language result message"""
        try:
            status = result.get("status", "unknown")
            
            if status == "success":
                if tool_name == "write_file":
                    path = parameters.get("path", "file")
                    bytes_written = result.get("bytes_written", 0)
                    return f"Successfully wrote {bytes_written} bytes to '{path}'"
                
                elif tool_name == "edit_file":
                    path = parameters.get("path", "file")
                    changes = result.get("changes_made", 0)
                    operation = parameters.get("operation", "edit")
                    if changes > 0:
                        return f"Made {changes} change(s) to '{path}' using {operation}"
                    else:
                        return f"No changes needed in '{path}'"
                
                elif tool_name == "read_file":
                    content = result.get("result", "")
                    lines = len(content.splitlines())
                    return f"Read {lines} lines from the file"
                
                elif tool_name == "list_directory":
                    items = result.get("result", [])
                    files = sum(1 for i in items if i.get("type") == "file")
                    dirs = sum(1 for i in items if i.get("type") == "directory")
                    return f"Found {files} file(s) and {dirs} folder(s)"
                
                elif tool_name == "search_files":
                    matches = result.get("total_matches", 0)
                    if matches > 0:
                        return f"Found '{parameters.get('pattern', 'text')}' in {matches} file(s)"
                    else:
                        return f"No matches found for '{parameters.get('pattern', 'text')}'"
                
                else:
                    return f"{tool_name} completed successfully"
            else:
                error = result.get("error", "Unknown error")
                return f"Failed: {error}"
                
        except Exception as e:
            self._logger.error(f"Error generating result message: {e}")
            if status == "success":
                return "Operation completed"
            else:
                return f"Operation failed: {result.get('error', 'Unknown error')}"
