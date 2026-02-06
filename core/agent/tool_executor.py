"""
Tool Executor - Executes tools and returns structured results
"""
import logging
from typing import Dict, Any
from pathlib import Path


class ToolExecutor:
    """
    Executes tools and returns structured, observable results
    """
    
    def __init__(self, workspace_path: str):
        """
        Initialize tool executor
        
        Args:
            workspace_path: Path to the workspace
        """
        self.workspace_path = Path(workspace_path)
        self._logger = logging.getLogger(__name__)
        
        # Ensure workspace exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)
    
    def execute(self, tool_name: str, parameters: Dict) -> Dict[str, Any]:
        """
        Execute a tool and return structured result
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            
        Returns:
            Dict with status, result, and summary
        """
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
                    "result": None,
                    "summary": f"Unknown tool: {tool_name}"
                }
        except Exception as e:
            self._logger.error(f"Error executing {tool_name}: {e}")
            return {
                "status": "error",
                "result": None,
                "summary": f"Error: {str(e)}"
            }
    
    def _tool_list_directory(self, params: Dict) -> Dict:
        """List directory contents"""
        try:
            path = Path(params.get("path", "."))
            if not path.is_absolute():
                path = self.workspace_path / path
            
            if not path.exists():
                return {
                    "status": "error",
                    "result": None,
                    "summary": f"Directory not found: {path.name}"
                }
            
            items = []
            file_names = []
            for item in path.iterdir():
                item_info = {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0
                }
                items.append(item_info)
                if item.is_file():
                    file_names.append(item.name)
            
            # Create detailed summary with file names
            files = [i for i in items if i["type"] == "file"]
            dirs = [i for i in items if i["type"] == "directory"]
            
            summary = f"Found {len(files)} files and {len(dirs)} directories"
            if file_names:
                # Show first few file names
                preview = ", ".join(file_names[:5])
                if len(file_names) > 5:
                    preview += f", and {len(file_names) - 5} more"
                summary += f". Files: {preview}"
            
            return {
                "status": "success",
                "result": items,
                "summary": summary
            }
        except Exception as e:
            return {
                "status": "error",
                "result": None,
                "summary": f"Error listing directory: {str(e)}"
            }
    
    def _tool_read_file(self, params: Dict) -> Dict:
        """Read file contents (supports text and PDF files)"""
        try:
            raw_path = params.get("path", "")
            if not raw_path:
                return {
                    "status": "error",
                    "result": None,
                    "summary": "No file path provided"
                }
            
            path = Path(raw_path)
            if not path.is_absolute():
                path = self.workspace_path / path
            
            if not path.exists():
                return {
                    "status": "error",
                    "result": None,
                    "summary": f"File not found: {path.name}"
                }
            
            if not path.is_file():
                return {
                    "status": "error",
                    "result": None,
                    "summary": f"Not a file: {path.name}"
                }
            
            # Check if it's a PDF file
            if path.suffix.lower() == '.pdf':
                return self._read_pdf_file(path)
            
            # Read text file
            content = path.read_text(encoding='utf-8', errors='replace')
            lines = len(content.splitlines())
            chars = len(content)
            
            return {
                "status": "success",
                "result": content,
                "summary": f"Read {path.name} ({lines} lines, {chars} chars)"
            }
        except Exception as e:
            return {
                "status": "error",
                "result": None,
                "summary": f"Error reading file: {str(e)}"
            }
    
    def _read_pdf_file(self, path: Path) -> Dict:
        """Read PDF file contents"""
        try:
            # Try to import PyPDF2
            try:
                import PyPDF2
            except ImportError:
                return {
                    "status": "error",
                    "result": None,
                    "summary": "PyPDF2 not installed. Install with: pip install PyPDF2"
                }
            
            # Read PDF
            with open(path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)
                
                # Extract text from all pages
                text_content = []
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    text_content.append(page.extract_text())
                
                full_text = "\n\n".join(text_content)
                chars = len(full_text)
                
                return {
                    "status": "success",
                    "result": full_text,
                    "summary": f"Read {path.name} ({num_pages} pages, {chars} chars)"
                }
        except Exception as e:
            return {
                "status": "error",
                "result": None,
                "summary": f"Error reading PDF: {str(e)}"
            }
    
    def _tool_write_file(self, params: Dict) -> Dict:
        """Write file contents"""
        try:
            path = Path(params.get("path", ""))
            if not path.is_absolute():
                path = self.workspace_path / path
            
            content = params.get("content", "")
            
            # Create parent directories
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            path.write_text(content, encoding='utf-8')
            
            bytes_written = len(content.encode('utf-8'))
            
            return {
                "status": "success",
                "result": str(path.relative_to(self.workspace_path)),
                "summary": f"Wrote {path.name} ({bytes_written} bytes)"
            }
        except Exception as e:
            return {
                "status": "error",
                "result": None,
                "summary": f"Error writing file: {str(e)}"
            }
    
    def _tool_edit_file(self, params: Dict) -> Dict:
        """Edit file with find-replace or line operations"""
        try:
            path = Path(params.get("path", ""))
            if not path.is_absolute():
                path = self.workspace_path / path
            
            if not path.exists():
                return {
                    "status": "error",
                    "result": None,
                    "summary": f"File not found: {path.name}"
                }
            
            operation = params.get("operation", "replace")
            
            # Read current content
            content = path.read_text(encoding='utf-8')
            lines = content.splitlines(keepends=True)
            
            changes_made = 0
            
            if operation == "replace":
                find_text = params.get("find", "")
                replace_text = params.get("replace", "")
                
                if not find_text:
                    return {
                        "status": "error",
                        "result": None,
                        "summary": "Find text required for replace operation"
                    }
                
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
                
                new_content = ''.join(lines)
                
            else:
                return {
                    "status": "error",
                    "result": None,
                    "summary": f"Unknown operation: {operation}"
                }
            
            # Write modified content
            if changes_made > 0:
                path.write_text(new_content, encoding='utf-8')
            
            return {
                "status": "success",
                "result": changes_made,
                "summary": f"Modified {path.name} ({changes_made} changes)"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "result": None,
                "summary": f"Error editing file: {str(e)}"
            }
    
    def _tool_search_files(self, params: Dict) -> Dict:
        """Search for text in files"""
        try:
            query = params.get("pattern") or params.get("query", "")
            path = Path(params.get("path", "."))
            if not path.is_absolute():
                path = self.workspace_path / path
            
            results = []
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='replace')
                        if query.lower() in content.lower():
                            results.append(str(file_path.relative_to(self.workspace_path)))
                    except:
                        pass
            
            return {
                "status": "success",
                "result": results,
                "summary": f"Found '{query}' in {len(results)} files"
            }
        except Exception as e:
            return {
                "status": "error",
                "result": None,
                "summary": f"Error searching: {str(e)}"
            }
