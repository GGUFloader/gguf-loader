"""
Simple Agent - Lightweight agent implementation for main GGUF Loader chat
"""
import json
import re
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from PySide6.QtCore import QObject, Signal

from models.chat_generator import ChatGenerator


class SimpleAgent(QObject):
    """
    Simplified agent for main chat window with tool execution capabilities.
    
    This is a lightweight version that doesn't require the full addon infrastructure.
    """
    
    # Signals
    response_generated = Signal(str)
    tool_executed = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, model, workspace_path: str):
        super().__init__()
        self.model = model
        self.workspace_path = Path(workspace_path)
        self._logger = logging.getLogger(__name__)
        self.conversation_history = []
        
        # Ensure workspace exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)
    
    def process_message(self, user_message: str):
        """Process user message and generate response with tool execution"""
        try:
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            # Build system prompt
            system_prompt = self._build_system_prompt()
            
            # Build context
            context = self._build_context(system_prompt, user_message)
            
            # Generate response
            response_text = self._generate_response(context)
            
            # Parse for tool calls
            tool_calls = self._parse_tool_calls(response_text)
            
            if tool_calls:
                # Execute tools
                tool_results = []
                for tool_call in tool_calls:
                    result = self._execute_tool(tool_call)
                    tool_results.append(result)
                    self.tool_executed.emit(result)
                
                # Generate final response with tool results
                final_response = self._generate_final_response(user_message, tool_results)
            else:
                # No tools, use direct response
                final_response = response_text
            
            # Add to history
            self.conversation_history.append({
                "role": "assistant",
                "content": final_response
            })
            
            # Emit response
            self.response_generated.emit(final_response)
            
        except Exception as e:
            self._logger.error(f"Error processing message: {e}")
            self.error_occurred.emit(str(e))
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for agent"""
        return f"""You are an AI assistant with full file system access. You can help users by:
- Reading and writing files (create new files or overwrite existing ones)
- Editing files (find-replace, insert/delete lines)
- Listing directory contents
- Searching for text in files
- Analyzing code and documents

Your workspace is: {self.workspace_path}

When you need to use tools, respond in this format:
```json
{{
    "reasoning": "Why you need to use these tools",
    "tool_calls": [
        {{
            "tool": "tool_name",
            "parameters": {{"param": "value"}}
        }}
    ]
}}
```

Available tools:
- list_directory: List files in a directory
  Parameters: {{"path": "directory_path"}}
  
- read_file: Read contents of a file
  Parameters: {{"path": "file_path"}}
  
- write_file: Write content to a file (creates new or overwrites existing)
  Parameters: {{"path": "file_path", "content": "file_content"}}
  
- edit_file: Edit an existing file with find-replace or line operations
  Parameters: {{"path": "file_path", "operation": "replace|insert_line|delete_line", "find": "text_to_find", "replace": "replacement_text", "line_number": 1, "content": "line_content"}}
  
- search_files: Search for text in files
  Parameters: {{"pattern": "search_text", "path": "directory_path"}}

IMPORTANT: You can write to ANY file in the workspace. When asked to create or modify files:
1. Use write_file to create new files or completely rewrite existing files
2. Use edit_file for targeted changes to existing files
3. Always create parent directories automatically (handled by the tool)

Always work within the workspace directory. Be helpful and concise."""
    
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
    
    def _generate_response(self, context: str) -> str:
        """Generate response using the model"""
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
            
            def on_token(token):
                nonlocal response_text
                response_text += token
            
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
            path = Path(params.get("path", ""))
            if not path.is_absolute():
                path = self.workspace_path / path
            
            if not path.exists():
                return {"status": "error", "error": "File not found"}
            
            content = path.read_text(encoding='utf-8')
            
            return {
                "status": "success",
                "result": content,
                "tool_name": "read_file"
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": "read_file"}
    
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
    
    def _generate_final_response(self, user_message: str, tool_results: List[Dict]) -> str:
        """Generate final response with tool results"""
        try:
            # Build context with tool results
            context = f"User asked: {user_message}\n\n"
            context += "Tool execution results:\n"
            for result in tool_results:
                tool_name = result.get("tool_name", "unknown")
                if result.get("status") == "success":
                    context += f"- {tool_name}: {result.get('result', 'Success')}\n"
                else:
                    context += f"- {tool_name}: Error - {result.get('error', 'Unknown error')}\n"
            
            context += "\nProvide a helpful response to the user based on these results:"
            
            return self._generate_response(context)
            
        except Exception as e:
            self._logger.error(f"Error generating final response: {e}")
            return "I completed the requested operations."
