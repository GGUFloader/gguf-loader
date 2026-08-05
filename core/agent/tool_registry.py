"""
ToolRegistry - Sandboxed filesystem tools for the agent engine.

Every tool resolves paths relative to a single workspace root and refuses
to escape it (path-traversal protection). The registry itself is pure
Python (no Qt) so it can be unit tested in isolation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


class Tool:
    """Base class for agent tools."""

    name = "base"
    description = ""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def resolve(self, raw_path: str) -> Path:
        """Resolve *raw_path* to an absolute path inside the workspace."""
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.workspace / path
        resolved = path.resolve()
        if resolved != self.workspace and self.workspace not in resolved.parents:
            raise ValueError(f"Path escapes workspace: {raw_path}")
        return resolved

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


class ListDirectoryTool(Tool):
    name = "list_directory"
    description = "List files and folders in a directory"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            path = self.resolve(params.get("path", "."))
            if not path.exists() or not path.is_dir():
                return {"status": "error", "error": "Directory not found", "tool_name": self.name}
            items = []
            for item in sorted(path.iterdir()):
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                })
            return {"status": "success", "result": items, "tool_name": self.name}
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": self.name}


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a text file"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            raw_path = params.get("path", "")
            if not raw_path:
                return {"status": "error", "error": "Path is required", "tool_name": self.name}
            path = self.resolve(raw_path)
            if not path.is_file():
                return {"status": "error", "error": "File not found", "tool_name": self.name}

            max_size = int(params.get("max_size", 10 * 1024 * 1024))
            file_size = path.stat().st_size
            if file_size > max_size:
                return {"status": "error",
                        "error": f"File too large: {file_size} bytes (max: {max_size})",
                        "tool_name": self.name}

            raw_data = path.read_bytes()
            content, encoding = _decode_bytes(raw_data, params.get("encoding", "auto"))
            return {"status": "success", "result": content, "tool_name": self.name,
                    "encoding": encoding, "size": file_size, "lines": len(content.splitlines())}
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": self.name}


class WriteFileTool(Tool):
    name = "write_file"
    description = "Create a new file or overwrite an existing one"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            path = self.resolve(params.get("path", ""))
            content = params.get("content", "")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {
                "status": "success",
                "result": f"Successfully wrote {len(content)} characters to {path.name}",
                "path": str(path.relative_to(self.workspace)),
                "bytes_written": len(content.encode("utf-8")),
                "tool_name": self.name,
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": self.name}


class EditFileTool(Tool):
    name = "edit_file"
    description = "Modify a file using replace, insert_line or delete_line operations"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            path = self.resolve(params.get("path", ""))
            if not path.is_file():
                return {"status": "error", "error": "File not found", "tool_name": self.name}

            operation = params.get("operation", "replace")
            content = path.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)
            changes_made = 0

            if operation == "replace":
                find_text = params.get("find", "")
                if not find_text:
                    return {"status": "error", "error": "Find text required for replace",
                            "tool_name": self.name}
                new_content = content.replace(find_text, params.get("replace", ""))
                changes_made = content.count(find_text)
            elif operation == "insert_line":
                line_number = int(params.get("line_number", 1))
                insert_content = params.get("content", "")
                if line_number <= len(lines):
                    lines.insert(line_number - 1, insert_content + "\n")
                else:
                    lines.append(insert_content + "\n")
                new_content = "".join(lines)
                changes_made = 1
            elif operation == "delete_line":
                line_number = int(params.get("line_number", 1))
                if 1 <= line_number <= len(lines):
                    del lines[line_number - 1]
                    changes_made = 1
                new_content = "".join(lines)
            else:
                return {"status": "error", "error": f"Unknown operation: {operation}",
                        "tool_name": self.name}

            if changes_made > 0:
                path.write_text(new_content, encoding="utf-8")

            return {"status": "success",
                    "result": f"Performed {operation}, {changes_made} change(s)",
                    "path": str(path.relative_to(self.workspace)),
                    "operation": operation, "changes_made": changes_made,
                    "tool_name": self.name}
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": self.name}


class SearchFilesTool(Tool):
    name = "search_files"
    description = "Search for text inside files under the workspace"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            query = params.get("pattern") or params.get("query", "")
            path = self.resolve(params.get("path", "."))
            if not path.is_dir():
                return {"status": "error", "error": "Directory not found", "tool_name": self.name}
            results = []
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    try:
                        text = file_path.read_text(encoding="utf-8", errors="ignore")
                        if query.lower() in text.lower():
                            results.append(str(file_path.relative_to(self.workspace)))
                    except Exception:
                        continue
            return {"status": "success", "result": results,
                    "total_matches": len(results), "tool_name": self.name}
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": self.name}


def _decode_bytes(raw_data: bytes, encoding: str) -> tuple[str, str]:
    """Decode raw bytes with BOM detection and common fallbacks."""
    if encoding and encoding != "auto":
        try:
            return raw_data.decode(encoding, errors="replace"), encoding
        except Exception:
            return raw_data.decode("utf-8", errors="replace"), "utf-8"

    if raw_data.startswith(b"\xef\xbb\xbf"):
        return raw_data.decode("utf-8-sig", errors="replace"), "utf-8-sig"
    if raw_data.startswith(b"\xff\xfe\x00\x00") or raw_data.startswith(b"\x00\x00\xfe\xff"):
        return raw_data.decode("utf-32", errors="replace"), "utf-32"
    if raw_data.startswith(b"\xff\xfe") or raw_data.startswith(b"\xfe\xff"):
        return raw_data.decode("utf-16", errors="replace"), "utf-16"

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


class ToolRegistry:
    """Registry of named tools bound to a single workspace root."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._tools: Dict[str, Tool] = {}
        self.register(ListDirectoryTool)
        self.register(ReadFileTool)
        self.register(WriteFileTool)
        self.register(EditFileTool)
        self.register(SearchFilesTool)

    def register(self, tool_cls: type) -> None:
        tool = tool_cls(self.workspace)
        self._tools[tool.name] = tool

    def names(self) -> List[str]:
        return list(self._tools)

    def describe(self) -> str:
        """Human-readable tool listing for the model system prompt."""
        lines = []
        for tool in self._tools.values():
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

    def execute(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            return {"status": "error", "error": f"Unknown tool: {name}", "tool_name": name}
        return tool.execute(params or {})


# Convenience factory used by services/UI
def create_default_registry(workspace: str | Path) -> ToolRegistry:
    return ToolRegistry(workspace)
