"""
ToolRegistry - Sandboxed filesystem tools for the agent engine.

Every tool resolves paths relative to a single workspace root and refuses
to escape it (path-traversal protection). The registry itself is pure
Python (no Qt) so it can be unit tested in isolation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class Tool:
    """Base class for agent tools."""

    name = "base"
    description = ""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def requires_approval(self, params: Dict[str, Any]) -> bool:
        """Whether a call needs user approval before it executes.

        Override to gate powerful tools (shell commands, git writes).
        """
        return False

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
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string",
                      "description": "Directory to list, relative to the workspace (defaults to .)"},
        },
        "required": [],
    }

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
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string",
                      "description": "File path, relative to the workspace"},
            "max_size": {"type": "integer",
                          "description": "Optional size cap in bytes (default 10 MB)"},
        },
        "required": ["path"],
    }

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
    description = "Create a new file or overwrite an existing one (creates parent directories)"
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string",
                      "description": "File path, relative to the workspace"},
            "content": {"type": "string",
                         "description": "Full content to write to the file"},
        },
        "required": ["path", "content"],
    }

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
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string",
                      "description": "File path, relative to the workspace"},
            "operation": {"type": "string",
                           "description": "replace (swap text), insert_line (add a line), or delete_line (remove a line)"},
            "find": {"type": "string",
                      "description": "Exact text to replace (required when operation is replace)"},
            "replace": {"type": "string",
                         "description": "New text to substitute (required when operation is replace)"},
            "line_number": {"type": "integer",
                             "description": "1-based line number (required when operation is insert_line or delete_line)"},
            "content": {"type": "string",
                         "description": "Line text to insert (required when operation is insert_line)"},
        },
        "required": ["path", "operation"],
    }

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


class RunCommandTool(Tool):
    """Run a shell command inside the workspace (approval-gated)."""

    name = "run_command"
    description = "Run a shell command inside the workspace (approval required before it runs)"
    schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string",
                         "description": "Shell command to run; the working directory is the workspace"},
            "timeout": {"type": "integer",
                         "description": "Max seconds to wait for the command (default 60)"},
        },
        "required": ["command"],
    }

    def requires_approval(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        command = params.get("command", "")
        if not command or not command.strip():
            return {"status": "error", "error": "Command is required", "tool_name": self.name}
        try:
            timeout = int(params.get("timeout", 60))
        except (TypeError, ValueError):
            timeout = 60
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"status": "error",
                    "error": f"Command timed out after {timeout}s",
                    "tool_name": self.name}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "error": str(e), "tool_name": self.name}

        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return {
            "status": "success" if proc.returncode == 0 else "error",
            "result": output[:8000],
            "returncode": proc.returncode,
            "tool_name": self.name,
        }


class GitTool(Tool):
    """Run git inside the workspace; write operations require approval."""

    name = "git"
    description = "Run git commands inside the workspace (read-only ones run freely; writes require approval)"
    schema = {
        "type": "object",
        "properties": {
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": 'Git arguments, e.g. ["status"] or ["diff", "--stat"] or ["commit", "-m", "msg"]',
            },
        },
        "required": ["args"],
    }

    # Subcommands that mutate repository state -> approval-gated.
    WRITE_OPS = {
        "add", "commit", "push", "reset", "checkout", "switch", "merge", "rebase",
        "clean", "rm", "mv", "tag", "branch", "stash", "cherry-pick", "revert",
        "restore", "fetch", "pull", "submodule", "gc", "prune", "am", "apply", "init",
    }

    def requires_approval(self, params: Dict[str, Any]) -> bool:
        args = params.get("args") or []
        if not args:
            return False
        return args[0] in self.WRITE_OPS

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        args = params.get("args") or []
        if not args or not isinstance(args, list):
            return {"status": "error", "error": "args must be a non-empty list, e.g. [\"status\"]",
                    "tool_name": self.name}
        try:
            proc = subprocess.run(
                ["git", *[str(a) for a in args]],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except FileNotFoundError:
            return {"status": "error", "error": "git is not installed or not on PATH", "tool_name": self.name}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "error": str(e), "tool_name": self.name}

        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return {
            "status": "success" if proc.returncode == 0 else "error",
            "result": output[:8000],
            "returncode": proc.returncode,
            "tool_name": self.name,
        }


class SearchFilesTool(Tool):
    name = "search_files"
    description = "Search for text inside files under the workspace"
    schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string",
                         "description": "Text to search for (case-insensitive)"},
            "path": {"type": "string",
                      "description": "Directory to search, relative to the workspace (defaults to .)"},
        },
        "required": ["pattern"],
    }

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


def tool_content_for_context(result: Dict[str, Any], max_chars: int = 4000) -> Optional[str]:
    """Model-visible payload text for contentful tools, else None.

    ``read_file``/``list_directory``/``search_files`` carry the actual
    payload (file text, item names, matched paths) that the model needs
    to continue. The loop must feed that back - a bare "Read N lines"
    summary makes reads useless because the content never reaches the
    model's context.
    """
    tool = result.get("tool_name", "")
    payload = result.get("result")

    if tool == "read_file" and isinstance(payload, str):
        text = payload[:max_chars]
        if len(payload) > max_chars:
            text += "…"
        return f"content:\n{text}"
    if tool == "list_directory" and isinstance(payload, list):
        names = ", ".join(str(item.get("name", "?")) for item in payload[:100])
        return f"{names} ({len(payload)} items)"
    if tool == "search_files" and isinstance(payload, list):
        paths = ", ".join(str(p) for p in payload[:50])
        return f"{paths} ({len(payload)} matches)"
    return None


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
        self.register(RunCommandTool)
        self.register(GitTool)

    def register(self, tool_cls: type) -> None:
        tool = tool_cls(self.workspace)
        self._tools[tool.name] = tool

    def names(self) -> List[str]:
        return list(self._tools)

    def describe(self) -> str:
        """Human-readable tool listing with parameter schemas, for the model prompt."""
        lines = []
        for tool in self._tools.values():
            lines.append(f"- {tool.name}: {tool.description}")
            schema = getattr(tool, "schema", None)
            if schema:
                required = set(schema.get("required", []))
                for param, info in schema.get("properties", {}).items():
                    marker = "required" if param in required else "optional"
                    lines.append(
                        f"    - {param} ({info.get('type', 'any')}, {marker}): {info.get('description', '')}"
                    )
        return "\n".join(lines)

    def execute(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            return {"status": "error", "error": f"Unknown tool: {name}", "tool_name": name}
        return tool.execute(params or {})

    def requires_approval(self, name: str, params: Dict[str, Any]) -> bool:
        """Whether a call to *name* needs user approval (see Tool.requires_approval)."""
        tool = self._tools.get(name)
        if tool is None:
            return False
        return bool(tool.requires_approval(params or {}))


# Convenience factory used by services/UI
def create_default_registry(workspace: str | Path) -> ToolRegistry:
    return ToolRegistry(workspace)
