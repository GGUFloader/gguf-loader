"""
File System Tools - Implements file operations for the agentic chatbot

This module provides secure file system operations within the workspace sandbox:
- ListDirectoryTool: Enumerate files and subdirectories with optional filtering
- ReadFileTool: Read complete file contents with automatic encoding detection  
- WriteFileTool: Write content atomically to prevent corruption
- EditFileTool: Perform find-replace operations and line insertions
"""

import os
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from ..tool_registry import BaseTool
from ..security.sandbox import SandboxValidator, SecurityError

try:
    import chardet  # type: ignore
except Exception:  # pragma: no cover
    chardet = None


class ListDirectoryTool(BaseTool):
    """Tool for listing directory contents with optional filtering."""
    
    def __init__(self, sandbox_validator: SandboxValidator):
        self.sandbox_validator = sandbox_validator
        self._logger = logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        return "list_directory"
    
    @property
    def description(self) -> str:
        return "List files and directories within the workspace with optional filtering"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list (relative to workspace root)",
                    "default": ""
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files and directories",
                    "default": False
                },
                "recursive": {
                    "type": "boolean",
                    "description": "List contents recursively",
                    "default": False
                }
            },
            "required": []
        }
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the list directory operation."""
        try:
            path = parameters.get("path", "")
            include_hidden = parameters.get("include_hidden", False)
            recursive = parameters.get("recursive", False)
            
            target_path = self.sandbox_validator.sanitize_path(path)
            
            if not target_path.exists():
                return {"status": "error", "error": f"Directory does not exist: {path}"}
            
            if not target_path.is_dir():
                return {"status": "error", "error": f"Path is not a directory: {path}"}
            
            contents = self._list_contents(target_path, include_hidden, recursive)
            
            return {
                "status": "success",
                "result": {
                    "path": str(self.sandbox_validator.get_relative_path(target_path)),
                    "contents": contents,
                    "total_items": len(contents)
                }
            }
            
        except SecurityError as e:
            return {"status": "error", "error": f"Security violation: {str(e)}"}
        except Exception as e:
            return {"status": "error", "error": f"Failed to list directory: {str(e)}"}
    
    def _list_contents(self, path: Path, include_hidden: bool, recursive: bool) -> List[Dict[str, Any]]:
        """List directory contents with filtering."""
        contents = []
        
        try:
            if recursive:
                items = path.rglob("*")
            else:
                items = path.iterdir()
            
            for item in items:
                if not include_hidden and item.name.startswith('.'):
                    continue
                
                item_info = {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "path": str(self.sandbox_validator.get_relative_path(item))
                }
                contents.append(item_info)
            
            contents.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
            
        except Exception as e:
            self._logger.error(f"Error processing directory contents: {e}")
            raise
        
        return contents

class ReadFileTool(BaseTool):
    """Tool for reading file contents with automatic encoding detection."""
    
    def __init__(self, sandbox_validator: SandboxValidator):
        self.sandbox_validator = sandbox_validator
        self._logger = logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read complete file contents with automatic encoding detection"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to read (relative to workspace root)"
                },
                "encoding": {
                    "type": "string",
                    "description": "Specific encoding to use (auto-detected if not provided)",
                    "default": "auto"
                },
                "max_size": {
                    "type": "integer",
                    "description": "Maximum file size to read in bytes (default: 10MB)",
                    "default": 10485760
                }
            },
            "required": ["path"]
        }
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the read file operation."""
        try:
            path = parameters["path"]
            encoding = parameters.get("encoding", "auto")
            max_size = parameters.get("max_size", 10485760)
            
            target_path = self.sandbox_validator.sanitize_path(path)
            
            if not target_path.exists():
                return {"status": "error", "error": f"File does not exist: {path}"}
            
            if not target_path.is_file():
                return {"status": "error", "error": f"Path is not a file: {path}"}
            
            file_size = target_path.stat().st_size
            if file_size > max_size:
                return {"status": "error", "error": f"File too large: {file_size} bytes (max: {max_size})"}
            
            content, detected_encoding = self._read_file_content(target_path, encoding)
            
            return {
                "status": "success",
                "result": {
                    "content": content,
                    "encoding": detected_encoding,
                    "size": file_size,
                    "lines": len(content.splitlines()),
                    "path": str(self.sandbox_validator.get_relative_path(target_path))
                }
            }
            
        except SecurityError as e:
            return {"status": "error", "error": f"Security violation: {str(e)}"}
        except Exception as e:
            return {"status": "error", "error": f"Failed to read file: {str(e)}"}
    
    def _read_file_content(self, path: Path, encoding: str) -> tuple[str, str]:
        """Read file content with encoding detection."""
        try:
            with open(path, 'rb') as f:
                raw_data = f.read()
            
            if encoding == "auto":
                # Prefer BOM-based detection, then chardet (if available), then utf-8 fallback
                if raw_data.startswith(b'\xef\xbb\xbf'):
                    encoding = 'utf-8-sig'
                elif raw_data.startswith(b'\xff\xfe') or raw_data.startswith(b'\xfe\xff'):
                    encoding = 'utf-16'
                elif raw_data.startswith(b'\xff\xfe\x00\x00') or raw_data.startswith(b'\x00\x00\xfe\xff'):
                    encoding = 'utf-32'
                elif chardet is not None:
                    detected = chardet.detect(raw_data)
                    encoding = detected.get('encoding', 'utf-8') or 'utf-8'
                else:
                    encoding = 'utf-8'
            
            try:
                content = raw_data.decode(encoding)
                return content, encoding
            except UnicodeDecodeError:
                content = raw_data.decode('utf-8', errors='replace')
                return content, 'utf-8'
                
        except Exception as e:
            self._logger.error(f"Error reading file content: {e}")
            raise
class WriteFileTool(BaseTool):
    """Tool for writing file contents atomically to prevent corruption."""
    
    def __init__(self, sandbox_validator: SandboxValidator):
        self.sandbox_validator = sandbox_validator
        self._logger = logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file atomically to prevent corruption"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to write (relative to workspace root)"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                },
                "encoding": {
                    "type": "string",
                    "description": "Text encoding to use",
                    "default": "utf-8"
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist",
                    "default": True
                }
            },
            "required": ["path", "content"]
        }
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the write file operation."""
        try:
            path = parameters["path"]
            content = parameters["content"]
            encoding = parameters.get("encoding", "utf-8")
            create_dirs = parameters.get("create_dirs", True)
            
            target_path = self.sandbox_validator.sanitize_path(path)
            
            if create_dirs:
                target_path.parent.mkdir(parents=True, exist_ok=True)
            
            bytes_written = self._write_file_atomic(target_path, content, encoding)
            
            return {
                "status": "success",
                "result": {
                    "path": str(self.sandbox_validator.get_relative_path(target_path)),
                    "bytes_written": bytes_written,
                    "encoding": encoding
                }
            }
            
        except SecurityError as e:
            return {"status": "error", "error": f"Security violation: {str(e)}"}
        except Exception as e:
            return {"status": "error", "error": f"Failed to write file: {str(e)}"}
    
    def _write_file_atomic(self, path: Path, content: str, encoding: str) -> int:
        """Write file content atomically."""
        temp_dir = path.parent
        with tempfile.NamedTemporaryFile(
            mode='w', 
            encoding=encoding, 
            dir=temp_dir, 
            delete=False,
            prefix=f".{path.name}.tmp"
        ) as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)
            bytes_written = len(content.encode(encoding))
        
        shutil.move(str(temp_path), str(path))
        self._logger.info(f"Wrote {bytes_written} bytes to {path}")
        return bytes_written
class EditFileTool(BaseTool):
    """Tool for performing targeted file edits like find-replace and line insertions."""
    
    def __init__(self, sandbox_validator: SandboxValidator):
        self.sandbox_validator = sandbox_validator
        self._logger = logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def description(self) -> str:
        return "Perform targeted file edits including find-replace operations and line insertions"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to edit (relative to workspace root)"
                },
                "operation": {
                    "type": "string",
                    "enum": ["replace", "insert_line", "delete_line"],
                    "description": "Type of edit operation to perform"
                },
                "find": {
                    "type": "string",
                    "description": "Text to find (for replace operations)"
                },
                "replace": {
                    "type": "string",
                    "description": "Replacement text (for replace operations)"
                },
                "line_number": {
                    "type": "integer",
                    "description": "Line number for line-based operations (1-based)",
                    "minimum": 1
                },
                "content": {
                    "type": "string",
                    "description": "Content to insert (for insert_line operations)"
                },
                "encoding": {
                    "type": "string",
                    "description": "Text encoding to use",
                    "default": "utf-8"
                }
            },
            "required": ["path", "operation"]
        }
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the edit file operation."""
        try:
            path = parameters["path"]
            operation = parameters["operation"]
            encoding = parameters.get("encoding", "utf-8")
            
            target_path = self.sandbox_validator.sanitize_path(path)
            
            if not target_path.exists():
                return {"status": "error", "error": f"File does not exist: {path}"}
            
            if not target_path.is_file():
                return {"status": "error", "error": f"Path is not a file: {path}"}
            
            with open(target_path, 'r', encoding=encoding) as f:
                original_content = f.read()
            
            modified_content, changes_made = self._perform_edit(original_content, operation, parameters)
            
            if changes_made > 0:
                bytes_written = self._write_file_atomic(target_path, modified_content, encoding)
            else:
                bytes_written = 0
            
            return {
                "status": "success",
                "result": {
                    "path": str(self.sandbox_validator.get_relative_path(target_path)),
                    "operation": operation,
                    "changes_made": changes_made,
                    "bytes_written": bytes_written
                }
            }
            
        except SecurityError as e:
            return {"status": "error", "error": f"Security violation: {str(e)}"}
        except Exception as e:
            return {"status": "error", "error": f"Failed to edit file: {str(e)}"}
    
    def _perform_edit(self, content: str, operation: str, parameters: Dict[str, Any]) -> tuple[str, int]:
        """Perform the specified edit operation."""
        changes_made = 0
        
        if operation == "replace":
            find_text = parameters.get("find", "")
            replace_text = parameters.get("replace", "")
            
            if not find_text:
                raise ValueError("Find text is required for replace operation")
            
            modified_content = content.replace(find_text, replace_text)
            changes_made = content.count(find_text)
        
        elif operation == "insert_line":
            line_number = parameters.get("line_number")
            insert_content = parameters.get("content", "")
            
            if line_number is None:
                raise ValueError("Line number is required for insert_line operation")
            
            lines = content.splitlines(keepends=True)
            
            if line_number <= len(lines):
                lines.insert(line_number - 1, insert_content + '\n')
            else:
                lines.append(insert_content + '\n')
            
            modified_content = ''.join(lines)
            changes_made = 1
        
        elif operation == "delete_line":
            line_number = parameters.get("line_number")
            
            if line_number is None:
                raise ValueError("Line number is required for delete_line operation")
            
            lines = content.splitlines(keepends=True)
            
            if 1 <= line_number <= len(lines):
                del lines[line_number - 1]
                changes_made = 1
            else:
                changes_made = 0
            
            modified_content = ''.join(lines)
        
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        return modified_content, changes_made
    
    def _write_file_atomic(self, path: Path, content: str, encoding: str) -> int:
        """Write file content atomically."""
        temp_dir = path.parent
        with tempfile.NamedTemporaryFile(
            mode='w', 
            encoding=encoding, 
            dir=temp_dir, 
            delete=False,
            prefix=f".{path.name}.tmp"
        ) as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)
            bytes_written = len(content.encode(encoding))
        
        shutil.move(str(temp_path), str(path))
        self._logger.info(f"Wrote {bytes_written} bytes to {path}")
        return bytes_written
