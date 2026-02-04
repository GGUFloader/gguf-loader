"""
Search Tools - Implements search and analysis operations for the agentic chatbot

This module provides search capabilities within the workspace sandbox:
- SearchFilesTool: Perform regex and text searches with context and line numbers
- FileMetadataTool: Retrieve file metadata including size, modification time, and permissions
- DirectoryAnalysisTool: Provide hierarchical directory information and analysis
"""

import os
import re
import logging
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from ..tool_registry import BaseTool
from ..security.sandbox import SandboxValidator, SecurityError


class SearchFilesTool(BaseTool):
    """Tool for performing regex and text searches across files with context."""
    
    def __init__(self, sandbox_validator: SandboxValidator):
        self.sandbox_validator = sandbox_validator
        self._logger = logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        return "search_files"
    
    @property
    def description(self) -> str:
        return "Search for text patterns across files using regex or plain text with context and line numbers"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (regex or plain text)"
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file path to search (relative to workspace root)",
                    "default": ""
                },
                "use_regex": {
                    "type": "boolean",
                    "description": "Whether to treat pattern as regex",
                    "default": False
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Whether search should be case sensitive",
                    "default": False
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines to include around matches",
                    "default": 2,
                    "minimum": 0,
                    "maximum": 10
                },
                "max_matches": {
                    "type": "integer",
                    "description": "Maximum number of matches to return",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000
                },
                "file_extensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File extensions to include (e.g., ['.py', '.txt'])",
                    "default": []
                },
                "exclude_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File patterns to exclude (e.g., ['*.log', '__pycache__'])",
                    "default": []
                }
            },
            "required": ["pattern"]
        }
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the search operation."""
        try:
            pattern = parameters["pattern"]
            path = parameters.get("path", "")
            use_regex = parameters.get("use_regex", False)
            case_sensitive = parameters.get("case_sensitive", False)
            context_lines = parameters.get("context_lines", 2)
            max_matches = parameters.get("max_matches", 100)
            file_extensions = parameters.get("file_extensions", [])
            exclude_patterns = parameters.get("exclude_patterns", [])
            
            target_path = self.sandbox_validator.sanitize_path(path)
            
            if not target_path.exists():
                return {"status": "error", "error": f"Path does not exist: {path}"}
            
            # Compile regex pattern if needed
            regex_pattern = None
            if use_regex:
                try:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    regex_pattern = re.compile(pattern, flags)
                except re.error as e:
                    return {"status": "error", "error": f"Invalid regex pattern: {str(e)}"}
            
            # Perform search
            matches = self._search_files(
                target_path, pattern, regex_pattern, case_sensitive,
                context_lines, max_matches, file_extensions, exclude_patterns
            )
            
            return {
                "status": "success",
                "result": {
                    "pattern": pattern,
                    "search_path": str(self.sandbox_validator.get_relative_path(target_path)),
                    "use_regex": use_regex,
                    "case_sensitive": case_sensitive,
                    "total_matches": len(matches),
                    "matches": matches[:max_matches]
                }
            }
            
        except SecurityError as e:
            return {"status": "error", "error": f"Security violation: {str(e)}"}
        except Exception as e:
            return {"status": "error", "error": f"Search failed: {str(e)}"}
    
    def _search_files(self, path: Path, pattern: str, regex_pattern: Optional[re.Pattern],
                     case_sensitive: bool, context_lines: int, max_matches: int,
                     file_extensions: List[str], exclude_patterns: List[str]) -> List[Dict[str, Any]]:
        """Search for pattern in files."""
        matches = []
        files_searched = 0
        
        try:
            # Get list of files to search
            files_to_search = self._get_files_to_search(path, file_extensions, exclude_patterns)
            
            for file_path in files_to_search:
                if len(matches) >= max_matches:
                    break
                
                try:
                    file_matches = self._search_in_file(
                        file_path, pattern, regex_pattern, case_sensitive, context_lines
                    )
                    matches.extend(file_matches)
                    files_searched += 1
                    
                except Exception as e:
                    self._logger.warning(f"Error searching file {file_path}: {e}")
                    continue
            
            self._logger.info(f"Searched {files_searched} files, found {len(matches)} matches")
            
        except Exception as e:
            self._logger.error(f"Error during file search: {e}")
            raise
        
        return matches
    
    def _get_files_to_search(self, path: Path, file_extensions: List[str], 
                           exclude_patterns: List[str]) -> List[Path]:
        """Get list of files to search based on criteria."""
        files = []
        
        if path.is_file():
            if self._should_include_file(path, file_extensions, exclude_patterns):
                files.append(path)
        else:
            # Recursively find files
            for file_path in path.rglob("*"):
                if file_path.is_file() and self._should_include_file(file_path, file_extensions, exclude_patterns):
                    files.append(file_path)
        
        return files
    
    def _should_include_file(self, file_path: Path, file_extensions: List[str], 
                           exclude_patterns: List[str]) -> bool:
        """Check if file should be included in search."""
        # Check file extensions
        if file_extensions:
            if file_path.suffix.lower() not in [ext.lower() for ext in file_extensions]:
                return False
        
        # Check exclude patterns
        for pattern in exclude_patterns:
            if file_path.match(pattern):
                return False
        
        # Skip binary files by checking if file is likely text
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                if b'\0' in chunk:  # Likely binary file
                    return False
        except Exception:
            return False
        
        return True
    
    def _search_in_file(self, file_path: Path, pattern: str, regex_pattern: Optional[re.Pattern],
                       case_sensitive: bool, context_lines: int) -> List[Dict[str, Any]]:
        """Search for pattern in a single file."""
        matches = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line_matches = []
                
                if regex_pattern:
                    # Regex search
                    for match in regex_pattern.finditer(line):
                        line_matches.append({
                            "start": match.start(),
                            "end": match.end(),
                            "matched_text": match.group()
                        })
                else:
                    # Plain text search
                    search_line = line if case_sensitive else line.lower()
                    search_pattern = pattern if case_sensitive else pattern.lower()
                    
                    start = 0
                    while True:
                        pos = search_line.find(search_pattern, start)
                        if pos == -1:
                            break
                        line_matches.append({
                            "start": pos,
                            "end": pos + len(pattern),
                            "matched_text": line[pos:pos + len(pattern)]
                        })
                        start = pos + 1
                
                # If matches found in this line, add to results
                if line_matches:
                    # Get context lines
                    context_start = max(0, line_num - context_lines - 1)
                    context_end = min(len(lines), line_num + context_lines)
                    context = [
                        {
                            "line_number": i + 1,
                            "content": lines[i].rstrip('\n\r'),
                            "is_match": i + 1 == line_num
                        }
                        for i in range(context_start, context_end)
                    ]
                    
                    matches.append({
                        "file": str(self.sandbox_validator.get_relative_path(file_path)),
                        "line_number": line_num,
                        "line_content": line.rstrip('\n\r'),
                        "matches": line_matches,
                        "context": context
                    })
        
        except Exception as e:
            self._logger.error(f"Error searching in file {file_path}: {e}")
            raise
        
        return matches


class FileMetadataTool(BaseTool):
    """Tool for retrieving file metadata including size, modification time, and permissions."""
    
    def __init__(self, sandbox_validator: SandboxValidator):
        self.sandbox_validator = sandbox_validator
        self._logger = logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        return "get_file_metadata"
    
    @property
    def description(self) -> str:
        return "Retrieve detailed metadata for files including size, modification time, permissions, and type information"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory path (relative to workspace root)"
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files in directory listings",
                    "default": False
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Include subdirectories recursively",
                    "default": False
                }
            },
            "required": ["path"]
        }
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the metadata retrieval operation."""
        try:
            path = parameters["path"]
            include_hidden = parameters.get("include_hidden", False)
            recursive = parameters.get("recursive", False)
            
            target_path = self.sandbox_validator.sanitize_path(path)
            
            if not target_path.exists():
                return {"status": "error", "error": f"Path does not exist: {path}"}
            
            if target_path.is_file():
                metadata = self._get_file_metadata(target_path)
                return {
                    "status": "success",
                    "result": {
                        "path": str(self.sandbox_validator.get_relative_path(target_path)),
                        "type": "file",
                        "metadata": metadata
                    }
                }
            else:
                # Directory metadata
                dir_metadata = self._get_directory_metadata(target_path, include_hidden, recursive)
                return {
                    "status": "success",
                    "result": {
                        "path": str(self.sandbox_validator.get_relative_path(target_path)),
                        "type": "directory",
                        "metadata": dir_metadata
                    }
                }
            
        except SecurityError as e:
            return {"status": "error", "error": f"Security violation: {str(e)}"}
        except Exception as e:
            return {"status": "error", "error": f"Failed to get metadata: {str(e)}"}
    
    def _get_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Get detailed metadata for a single file."""
        try:
            stat = file_path.stat()
            
            # Get MIME type
            mime_type, encoding = mimetypes.guess_type(str(file_path))
            
            # Check if file is likely text
            is_text = self._is_text_file(file_path)
            
            metadata = {
                "name": file_path.name,
                "size": stat.st_size,
                "size_human": self._format_size(stat.st_size),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
                "permissions": oct(stat.st_mode)[-3:],
                "is_readable": os.access(file_path, os.R_OK),
                "is_writable": os.access(file_path, os.W_OK),
                "is_executable": os.access(file_path, os.X_OK),
                "mime_type": mime_type,
                "encoding": encoding,
                "is_text": is_text,
                "extension": file_path.suffix.lower()
            }
            
            # Add line count for text files
            if is_text:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        line_count = sum(1 for _ in f)
                    metadata["line_count"] = line_count
                except Exception:
                    metadata["line_count"] = None
            
            return metadata
            
        except Exception as e:
            self._logger.error(f"Error getting file metadata: {e}")
            raise
    
    def _get_directory_metadata(self, dir_path: Path, include_hidden: bool, recursive: bool) -> Dict[str, Any]:
        """Get metadata for a directory."""
        try:
            stat = dir_path.stat()
            
            # Count files and subdirectories
            file_count = 0
            dir_count = 0
            total_size = 0
            
            if recursive:
                items = dir_path.rglob("*")
            else:
                items = dir_path.iterdir()
            
            for item in items:
                if not include_hidden and item.name.startswith('.'):
                    continue
                
                if item.is_file():
                    file_count += 1
                    try:
                        total_size += item.stat().st_size
                    except Exception:
                        pass
                elif item.is_dir():
                    dir_count += 1
            
            metadata = {
                "name": dir_path.name,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
                "permissions": oct(stat.st_mode)[-3:],
                "is_readable": os.access(dir_path, os.R_OK),
                "is_writable": os.access(dir_path, os.W_OK),
                "is_executable": os.access(dir_path, os.X_OK),
                "file_count": file_count,
                "directory_count": dir_count,
                "total_size": total_size,
                "total_size_human": self._format_size(total_size),
                "recursive": recursive
            }
            
            return metadata
            
        except Exception as e:
            self._logger.error(f"Error getting directory metadata: {e}")
            raise
    
    def _is_text_file(self, file_path: Path) -> bool:
        """Check if file is likely a text file."""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                if b'\0' in chunk:
                    return False
                
                # Check for high ratio of printable characters
                printable_chars = sum(1 for byte in chunk if 32 <= byte <= 126 or byte in [9, 10, 13])
                return printable_chars / len(chunk) > 0.7 if chunk else True
                
        except Exception:
            return False
    
    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


class DirectoryAnalysisTool(BaseTool):
    """Tool for providing hierarchical directory information and analysis."""
    
    def __init__(self, sandbox_validator: SandboxValidator):
        self.sandbox_validator = sandbox_validator
        self._logger = logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        return "analyze_directory"
    
    @property
    def description(self) -> str:
        return "Provide hierarchical directory structure analysis with file type statistics and organization insights"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to analyze (relative to workspace root)",
                    "default": ""
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum depth to analyze",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 10
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files and directories",
                    "default": False
                },
                "show_file_types": {
                    "type": "boolean",
                    "description": "Include file type statistics",
                    "default": True
                },
                "show_size_analysis": {
                    "type": "boolean",
                    "description": "Include size analysis",
                    "default": True
                }
            },
            "required": []
        }
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the directory analysis operation."""
        try:
            path = parameters.get("path", "")
            max_depth = parameters.get("max_depth", 3)
            include_hidden = parameters.get("include_hidden", False)
            show_file_types = parameters.get("show_file_types", True)
            show_size_analysis = parameters.get("show_size_analysis", True)
            
            target_path = self.sandbox_validator.sanitize_path(path)
            
            if not target_path.exists():
                return {"status": "error", "error": f"Directory does not exist: {path}"}
            
            if not target_path.is_dir():
                return {"status": "error", "error": f"Path is not a directory: {path}"}
            
            # Perform analysis
            analysis = self._analyze_directory(
                target_path, max_depth, include_hidden, show_file_types, show_size_analysis
            )
            
            return {
                "status": "success",
                "result": {
                    "path": str(self.sandbox_validator.get_relative_path(target_path)),
                    "analysis": analysis
                }
            }
            
        except SecurityError as e:
            return {"status": "error", "error": f"Security violation: {str(e)}"}
        except Exception as e:
            return {"status": "error", "error": f"Directory analysis failed: {str(e)}"}
    
    def _analyze_directory(self, path: Path, max_depth: int, include_hidden: bool,
                          show_file_types: bool, show_size_analysis: bool) -> Dict[str, Any]:
        """Perform comprehensive directory analysis."""
        try:
            # Build directory tree
            tree = self._build_directory_tree(path, max_depth, include_hidden, current_depth=0)
            
            # Collect statistics
            stats = self._collect_statistics(path, include_hidden)
            
            analysis = {
                "tree": tree,
                "statistics": stats
            }
            
            if show_file_types:
                analysis["file_types"] = self._analyze_file_types(path, include_hidden)
            
            if show_size_analysis:
                analysis["size_analysis"] = self._analyze_sizes(path, include_hidden)
            
            return analysis
            
        except Exception as e:
            self._logger.error(f"Error analyzing directory: {e}")
            raise
    
    def _build_directory_tree(self, path: Path, max_depth: int, include_hidden: bool, 
                             current_depth: int) -> Dict[str, Any]:
        """Build hierarchical directory tree."""
        tree = {
            "name": path.name or str(path),
            "type": "directory",
            "path": str(self.sandbox_validator.get_relative_path(path)),
            "children": []
        }
        
        if current_depth >= max_depth:
            tree["truncated"] = True
            return tree
        
        try:
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            
            for item in items:
                if not include_hidden and item.name.startswith('.'):
                    continue
                
                if item.is_dir():
                    child_tree = self._build_directory_tree(
                        item, max_depth, include_hidden, current_depth + 1
                    )
                    tree["children"].append(child_tree)
                else:
                    tree["children"].append({
                        "name": item.name,
                        "type": "file",
                        "path": str(self.sandbox_validator.get_relative_path(item)),
                        "size": item.stat().st_size if item.exists() else 0
                    })
        
        except Exception as e:
            self._logger.warning(f"Error processing directory {path}: {e}")
            tree["error"] = str(e)
        
        return tree
    
    def _collect_statistics(self, path: Path, include_hidden: bool) -> Dict[str, Any]:
        """Collect directory statistics."""
        stats = {
            "total_files": 0,
            "total_directories": 0,
            "total_size": 0,
            "depth": 0
        }
        
        try:
            for item in path.rglob("*"):
                if not include_hidden and any(part.startswith('.') for part in item.parts):
                    continue
                
                if item.is_file():
                    stats["total_files"] += 1
                    try:
                        stats["total_size"] += item.stat().st_size
                    except Exception:
                        pass
                elif item.is_dir():
                    stats["total_directories"] += 1
                
                # Calculate depth
                relative_path = item.relative_to(path)
                depth = len(relative_path.parts)
                stats["depth"] = max(stats["depth"], depth)
        
        except Exception as e:
            self._logger.error(f"Error collecting statistics: {e}")
        
        stats["total_size_human"] = self._format_size(stats["total_size"])
        return stats
    
    def _analyze_file_types(self, path: Path, include_hidden: bool) -> Dict[str, Any]:
        """Analyze file types in directory."""
        file_types = {}
        extension_stats = {}
        
        try:
            for item in path.rglob("*"):
                if not include_hidden and any(part.startswith('.') for part in item.parts):
                    continue
                
                if item.is_file():
                    # Get extension
                    ext = item.suffix.lower() or "no_extension"
                    if ext not in extension_stats:
                        extension_stats[ext] = {"count": 0, "total_size": 0}
                    
                    extension_stats[ext]["count"] += 1
                    try:
                        extension_stats[ext]["total_size"] += item.stat().st_size
                    except Exception:
                        pass
                    
                    # Get MIME type
                    mime_type, _ = mimetypes.guess_type(str(item))
                    if mime_type:
                        category = mime_type.split('/')[0]
                        if category not in file_types:
                            file_types[category] = {"count": 0, "total_size": 0}
                        
                        file_types[category]["count"] += 1
                        try:
                            file_types[category]["total_size"] += item.stat().st_size
                        except Exception:
                            pass
        
        except Exception as e:
            self._logger.error(f"Error analyzing file types: {e}")
        
        # Format sizes
        for stats in extension_stats.values():
            stats["total_size_human"] = self._format_size(stats["total_size"])
        
        for stats in file_types.values():
            stats["total_size_human"] = self._format_size(stats["total_size"])
        
        return {
            "by_extension": extension_stats,
            "by_mime_type": file_types
        }
    
    def _analyze_sizes(self, path: Path, include_hidden: bool) -> Dict[str, Any]:
        """Analyze file sizes in directory."""
        sizes = []
        size_ranges = {
            "tiny": {"min": 0, "max": 1024, "count": 0, "total_size": 0},           # < 1KB
            "small": {"min": 1024, "max": 1024*1024, "count": 0, "total_size": 0}, # 1KB - 1MB
            "medium": {"min": 1024*1024, "max": 10*1024*1024, "count": 0, "total_size": 0}, # 1MB - 10MB
            "large": {"min": 10*1024*1024, "max": float('inf'), "count": 0, "total_size": 0}  # > 10MB
        }
        
        try:
            for item in path.rglob("*"):
                if not include_hidden and any(part.startswith('.') for part in item.parts):
                    continue
                
                if item.is_file():
                    try:
                        size = item.stat().st_size
                        sizes.append({
                            "path": str(self.sandbox_validator.get_relative_path(item)),
                            "size": size,
                            "size_human": self._format_size(size)
                        })
                        
                        # Categorize by size
                        for category, range_info in size_ranges.items():
                            if range_info["min"] <= size < range_info["max"]:
                                range_info["count"] += 1
                                range_info["total_size"] += size
                                break
                    
                    except Exception:
                        pass
        
        except Exception as e:
            self._logger.error(f"Error analyzing sizes: {e}")
        
        # Sort by size (largest first)
        sizes.sort(key=lambda x: x["size"], reverse=True)
        
        # Format range totals
        for range_info in size_ranges.values():
            range_info["total_size_human"] = self._format_size(range_info["total_size"])
        
        return {
            "largest_files": sizes[:20],  # Top 20 largest files
            "size_distribution": size_ranges
        }
    
    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"