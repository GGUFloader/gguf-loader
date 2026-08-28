"""
SemanticSearch - Advanced file search combining regex, glob, and content patterns.

Replaces the basic SearchFilesTool with a more powerful search that supports:
- Regex patterns for content search
- Glob patterns for filename matching
- Combined searches (e.g., "find .py files containing 'def main'")
- Contextual results with line numbers and surrounding lines

Pattern from: Aider's repo-map + SWE-agent's search commands.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Directories to skip during search
SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".idea", ".vscode", ".gguf-undo",
    "env", ".env", ".tox", ".mypy_cache", ".pytest_cache",
})

# Max file size to search (2MB)
MAX_FILE_SIZE = 2 * 1024 * 1024

# Binary file extensions to skip
BINARY_EXTS = frozenset({
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".obj",
    ".pyc", ".pyo", ".class", ".jar",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".gguf", ".bin", ".safetensors", ".pt", ".pth",
})


class SearchResult:
    """A single search result."""

    def __init__(self, path: str, line_number: int = 0, line_text: str = "",
                 context_lines: List[str] = None, match_type: str = "content") -> None:
        self.path = path
        self.line_number = line_number
        self.line_text = line_text
        self.context_lines = context_lines or []
        self.match_type = match_type  # "content", "filename", "glob"

    def to_dict(self) -> Dict[str, Any]:
        d = {"path": self.path, "match_type": self.match_type}
        if self.line_number:
            d["line"] = self.line_number
            d["text"] = self.line_text.strip()
        if self.context_lines:
            d["context"] = self.context_lines
        return d


class SemanticSearch:
    """Advanced file search engine for the agent workspace.

    Usage:
        search = SemanticSearch(workspace_path)
        results = search.search("pattern", glob="*.py", max_results=50)
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def search(self, query: str, glob: str = None,
               regex: bool = False, context_lines: int = 2,
               max_results: int = 50, case_sensitive: bool = False,
               max_file_size: int = MAX_FILE_SIZE) -> List[SearchResult]:
        """Search for files/content matching the query.

        Args:
            query: Search term (plain text or regex)
            glob: Glob pattern for filename filtering (e.g., "*.py")
            regex: Treat query as regex pattern
            context_lines: Number of surrounding lines to include
            max_results: Maximum results to return
            case_sensitive: Whether search is case-sensitive
            max_file_size: Skip files larger than this

        Returns:
            List of SearchResult objects
        """
        results: List[SearchResult] = []
        flags = 0 if case_sensitive else re.IGNORECASE

        compiled_pattern = None
        if regex:
            try:
                compiled_pattern = re.compile(query, flags)
            except re.error:
                # Invalid regex — fall back to plain text
                compiled_pattern = re.compile(re.escape(query), flags)

        for root, dirs, files in os.walk(self.workspace):
            # Skip excluded directories
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)

            for filename in files:
                if len(results) >= max_results:
                    return results

                filepath = Path(root) / filename

                # Skip binary files
                if filepath.suffix.lower() in BINARY_EXTS:
                    continue

                # Skip large files
                try:
                    if filepath.stat().st_size > max_file_size:
                        continue
                except OSError:
                    continue

                rel_path = str(filepath.relative_to(self.workspace))

                # Glob filter
                if glob and not fnmatch.fnmatch(filename, glob):
                    continue

                # Filename match
                if compiled_pattern and compiled_pattern.search(filename):
                    results.append(SearchResult(rel_path, match_type="filename"))
                    if len(results) >= max_results:
                        return results
                    continue

                # Content search
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except (OSError, UnicodeDecodeError):
                    continue

                for i, line in enumerate(content.splitlines(), 1):
                    if compiled_pattern and compiled_pattern.search(line):
                        # Gather context
                        all_lines = content.splitlines()
                        start = max(0, i - 1 - context_lines)
                        end = min(len(all_lines), i + context_lines)
                        ctx = [all_lines[j] for j in range(start, end)]

                        results.append(SearchResult(
                            path=rel_path,
                            line_number=i,
                            line_text=line,
                            context_lines=ctx,
                            match_type="content",
                        ))
                        if len(results) >= max_results:
                            return results

        return results

    def find_files(self, glob_pattern: str, max_results: int = 100) -> List[str]:
        """Find files matching a glob pattern.

        Args:
            glob_pattern: Glob pattern (e.g., "*.py", "**/*.json")
            max_results: Maximum results

        Returns:
            List of relative file paths
        """
        results = []

        # Handle recursive patterns
        if "**" in glob_pattern:
            for root, dirs, files in os.walk(self.workspace):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for filename in files:
                    filepath = Path(root) / filename
                    rel = str(filepath.relative_to(self.workspace))
                    if fnmatch.fnmatch(rel, glob_pattern):
                        results.append(rel)
                        if len(results) >= max_results:
                            return results
        else:
            for item in self.workspace.rglob(glob_pattern):
                if item.is_file() and not any(
                    d in SKIP_DIRS for d in item.relative_to(self.workspace).parts[:-1]
                ):
                    results.append(str(item.relative_to(self.workspace)))
                    if len(results) >= max_results:
                        return results

        return sorted(results)

    def find_definitions(self, name: str, file_glob: str = "*.py",
                         max_results: int = 20) -> List[SearchResult]:
        """Find function/class definitions matching a name.

        Useful for the agent to locate code definitions.
        """
        # Match def/class patterns
        patterns = [
            rf"\bdef\s+{re.escape(name)}\b",
            rf"\bclass\s+{re.escape(name)}\b",
        ]
        combined = "|".join(patterns)
        return self.search(combined, glob=file_glob, regex=True,
                          context_lines=3, max_results=max_results)

    def get_file_stats(self, path: str) -> Dict[str, Any]:
        """Get stats about a file (lines, size, language)."""
        filepath = self.workspace / path
        if not filepath.is_file():
            return {"error": "File not found"}

        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            return {
                "path": path,
                "lines": len(lines),
                "size_bytes": filepath.stat().st_size,
                "language": filepath.suffix.lstrip("."),
                "blank_lines": sum(1 for l in lines if not l.strip()),
                "comment_lines": sum(1 for l in lines if l.strip().startswith("#")),
            }
        except OSError as e:
            return {"error": str(e)}

    def get_workspace_summary(self, max_files: int = 100) -> Dict[str, Any]:
        """Get a high-level summary of the workspace."""
        file_count = 0
        dir_count = 0
        total_size = 0
        ext_counts: Dict[str, int] = {}

        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            dir_count += len(dirs)
            for f in files:
                filepath = Path(root) / f
                if filepath.suffix.lower() in BINARY_EXTS:
                    continue
                file_count += 1
                ext = filepath.suffix.lower() or "(no ext)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                try:
                    total_size += filepath.stat().st_size
                except OSError:
                    pass
                if file_count >= max_files:
                    break
            if file_count >= max_files:
                break

        # Top extensions
        top_exts = sorted(ext_counts.items(), key=lambda x: -x[1])[:10]

        return {
            "files": file_count,
            "directories": dir_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "top_file_types": top_exts,
        }
