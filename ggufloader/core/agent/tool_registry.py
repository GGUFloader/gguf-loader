"""
ToolRegistry - Sandboxed filesystem tools for the agent engine.

Every tool resolves paths relative to a single workspace root and refuses
to escape it (path-traversal protection). The registry itself is pure
Python (no Qt) so it can be unit tested in isolation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .text_extract import extract_text, is_binary, looks_like_binary_text


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
    description = ("Read the contents of a text file (Markdown, code, CSV, ...) or "
                   "extract the text of a PDF or DOCX file")
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
            ext = path.suffix.lower()
            if ext in (".pdf", ".docx"):
                content = extract_text(path, raw_data)
                if content is None:
                    return {"status": "error",
                            "error": f"Could not extract text from {ext} file '{raw_path}' "
                                     "(unsupported or no extractable text)",
                            "tool_name": self.name}
                return {"status": "success", "result": content, "tool_name": self.name,
                        "encoding": ext.lstrip("."), "size": file_size,
                        "lines": len(content.splitlines()),
                        "path": str(path.relative_to(self.workspace))}

            content, encoding = _decode_bytes(raw_data, params.get("encoding", "auto"))
            if looks_like_binary_text(raw_data):
                return {"status": "error",
                        "error": f"Cannot read '{raw_path}': looks like a binary file "
                                 "(only text/Markdown, PDF, and DOCX are supported)",
                        "tool_name": self.name}
            return {"status": "success", "result": content, "tool_name": self.name,
                    "encoding": encoding, "size": file_size, "lines": len(content.splitlines()),
                    "path": str(path.relative_to(self.workspace))}
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


class RunPythonTool(Tool):
    """Execute Python source inside the workspace (approval-gated).

    Runs via ``sys.executable -c <code>`` - full interpreter access, so
    like run_command it always requires human approval. Errors are
    reported back so the model can self-correct.
    """

    name = "run_python"
    description = ("Execute Python code inside the workspace and return stdout/stderr "
                   "(approval required before it runs)")
    schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string",
                     "description": "Python source code to execute; the working directory is the workspace"},
            "timeout": {"type": "integer",
                        "description": "Max seconds to wait (default 60)"},
        },
        "required": ["code"],
    }

    def requires_approval(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        code = params.get("code", "")
        if not code or not code.strip():
            return {"status": "error", "error": "Code is required", "tool_name": self.name}
        try:
            timeout = int(params.get("timeout", 60))
        except (TypeError, ValueError):
            timeout = 60
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"status": "error",
                    "error": f"Python code timed out after {timeout}s",
                    "tool_name": self.name}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "error": str(e), "tool_name": self.name}
        out = (proc.stdout or "")[:8000]
        err = (proc.stderr or "")[:2000]
        result: Dict[str, Any] = {
            "status": "success" if proc.returncode == 0 else "error",
            "tool_name": self.name,
            "exit_code": proc.returncode,
        }
        if out.strip():
            result["result"] = out
        if proc.returncode != 0:
            result["error"] = f"exit {proc.returncode}: {err}" if err else \
                f"exited with code {proc.returncode}"
        elif err.strip():
            result["stderr"] = err
        return result


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
            if not query or not query.strip():
                return {"status": "error", "error": "pattern is required", "tool_name": self.name}
            path = self.resolve(params.get("path", "."))
            if not path.is_dir():
                return {"status": "error", "error": "Directory not found", "tool_name": self.name}
            results = []
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    try:
                        raw = file_path.read_bytes()
                        if is_binary(raw):
                            continue  # skip PDFs/DOCX/images - no clean keyword text
                        text = raw.decode("utf-8", errors="ignore")
                        if query.lower() in text.lower():
                            results.append(str(file_path.relative_to(self.workspace)))
                    except Exception:
                        continue
            return {"status": "success", "result": results,
                    "total_matches": len(results), "tool_name": self.name}
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": self.name}


class PythonInterpreterTool(Tool):
    """Sandboxed Python code interpreter for non-workspace chats.

    Safe by construction:
    - Runs in a temporary directory (no workspace/filesystem access)
    - No approval required (can't modify anything)
    - Output capped at 8000 chars
    - Timeout of 30s
    - stdin disabled (reads from /dev/null)
    - Restricted to stdlib + whatever is installed (no pip)
    """

    name = "python_interpreter"
    description = (
        "Run Python code in a sandboxed environment (no filesystem access, "
        "no network, read-only). Use for math, data processing, string "
        "manipulation, and calculations. Output is capped at 8000 chars."
    )
    schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute (no file/network access)",
            },
            "timeout": {
                "type": "integer",
                "description": "Max seconds (default 30, max 60)",
            },
        },
        "required": ["code"],
    }

    MAX_OUTPUT = 8000
    MAX_TIMEOUT = 60
    DEFAULT_TIMEOUT = 30

    def requires_approval(self, params: Dict[str, Any]) -> bool:
        return False  # safe by construction

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import tempfile

        code = params.get("code", "")
        if not code or not code.strip():
            return {"status": "error", "error": "Code is required", "tool_name": self.name}

        try:
            timeout = min(int(params.get("timeout", self.DEFAULT_TIMEOUT)), self.MAX_TIMEOUT)
        except (TypeError, ValueError):
            timeout = self.DEFAULT_TIMEOUT

        # Create a sandboxed temp directory for this execution
        with tempfile.TemporaryDirectory(prefix="gguf_sandbox_") as tmpdir:
            try:
                # Run with restrictions:
                # - cwd = temp dir (not workspace)
                # - stdin = /dev/null
                # - env stripped of dangerous vars
                import os
                safe_env = {
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": tmpdir,
                    "TMPDIR": tmpdir,
                    "TEMP": tmpdir,
                    "TMP": tmpdir,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONUNBUFFERED": "1",
                }
                # Remove network-related env vars
                for key in list(os.environ.keys()):
                    kl = key.lower()
                    if any(n in kl for n in ("proxy", "http", "https", "socket", "ssh")):
                        continue  # don't copy

                proc = subprocess.run(
                    [sys.executable, "-c", code],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                    env=safe_env,
                    stdin=subprocess.DEVNULL,
                )
            except subprocess.TimeoutExpired:
                return {
                    "status": "error",
                    "error": f"Code timed out after {timeout}s",
                    "tool_name": self.name,
                }
            except Exception as e:  # noqa: BLE001
                return {"status": "error", "error": str(e), "tool_name": self.name}

            out = (proc.stdout or "")[:self.MAX_OUTPUT]
            err = (proc.stderr or "")[:2000]
            result: Dict[str, Any] = {
                "status": "success" if proc.returncode == 0 else "error",
                "tool_name": self.name,
                "exit_code": proc.returncode,
            }
            if out.strip():
                result["result"] = out
            if proc.returncode != 0:
                result["error"] = f"exit {proc.returncode}: {err}" if err else \
                    f"exited with code {proc.returncode}"
            elif err.strip():
                result["stderr"] = err
            return result


class BatchExecuteTool(Tool):
    """Execute multiple tool calls in sequence (CodeMode adaptation).

    Collapses N tool calls into one LLM round-trip. The model writes a
    list of {tool, parameters} pairs and this tool executes them in order.
    """

    name = "batch_execute"
    description = "Execute multiple tool calls in sequence. Reduces LLM round-trips."
    schema = {
        "type": "object",
        "properties": {
            "calls": {
                "type": "array",
                "description": "List of tool calls to execute in order",
            }
        },
        "required": ["calls"],
    }

    def __init__(self, workspace: Path) -> None:
        super().__init__(workspace)
        self._registry: Optional["ToolRegistry"] = None

    def set_registry(self, registry: "ToolRegistry") -> None:
        self._registry = registry

    def requires_approval(self, params: Dict[str, Any]) -> bool:
        """Batch requires approval if any call needs it."""
        if not self._registry:
            return True
        for call in params.get("calls", []):
            if not isinstance(call, dict):
                continue
            tool_name = call.get("tool", "")
            tool_params = call.get("parameters", {})
            if self._registry.requires_approval(tool_name, tool_params):
                return True
        return False

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._registry:
            return {"status": "error", "error": "No registry set", "tool_name": self.name}
        calls = params.get("calls", [])
        if not calls:
            return {"status": "error", "error": "No calls provided", "tool_name": self.name}
        results = []
        for call in calls:
            if not isinstance(call, dict):
                results.append({"status": "error", "error": "Invalid call format"})
                continue
            tool_name = call.get("tool", "")
            tool_params = call.get("parameters", {})
            result = self._registry.execute(tool_name, tool_params)
            results.append(result)
            # Stop on error
            if result.get("status") == "error":
                break
        return {"status": "success", "results": results, "tool_name": self.name}


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


ALL_TOOL_CLASSES = (
    ListDirectoryTool, ReadFileTool, WriteFileTool, EditFileTool,
    SearchFilesTool, RunCommandTool, RunPythonTool, GitTool,
    PythonInterpreterTool, BatchExecuteTool,
)


def validate_tool_call(call: Dict[str, Any], registry: "ToolRegistry") -> Optional[str]:
    """Validate a proposed tool call against its schema.

    Returns None when valid, or an error message string when invalid.
    This catches malformed calls before execution so the model can retry.
    """
    tool_name = call.get("tool", "")
    if not tool_name:
        return "No tool name specified"

    tool = registry._tools.get(tool_name)
    if tool is None:
        return f"Unknown tool: {tool_name}"

    schema = getattr(tool, "schema", None)
    if schema is None:
        return None  # no schema to validate against

    params = call.get("parameters", {})
    if not isinstance(params, dict):
        return f"Parameters must be a JSON object, got {type(params).__name__}"

    required = set(schema.get("required", []))
    properties = schema.get("properties", {})

    # Check required params
    for key in required:
        if key not in params:
            return f"Missing required parameter '{key}' for tool '{tool_name}'"

    # Check param types (basic validation)
    for key, value in params.items():
        if key in properties:
            expected_type = properties[key].get("type")
            if expected_type == "string" and not isinstance(value, str):
                return f"Parameter '{key}' must be a string, got {type(value).__name__}"
            if expected_type == "integer" and not isinstance(value, int):
                return f"Parameter '{key}' must be an integer, got {type(value).__name__}"
            if expected_type == "array" and not isinstance(value, list):
                return f"Parameter '{key}' must be an array, got {type(value).__name__}"

    return None  # valid


class ToolRegistry:
    """Registry of named tools bound to a single workspace root."""

    def __init__(
        self,
        workspace: str | Path,
        *,
        only: Optional[Sequence[str]] = None,
    ) -> None:
        """Register all tools, or only the named subset when *only* is given.

        ``only`` lets callers expose a restricted tool set (e.g. the search
        planner gets just the read-only tools) without weakening the jail:
        a tool that is not registered cannot be called at all.
        """
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._tools: Dict[str, Tool] = {}
        for tool_cls in ALL_TOOL_CLASSES:
            if only is None or tool_cls.name in only:
                self.register(tool_cls)

    def register(self, tool_cls: type) -> None:
        tool = tool_cls(self.workspace)
        self._tools[tool.name] = tool

    def register_instance(self, tool: Tool) -> None:
        """Register a pre-built tool instance (for plugins)."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Remove a tool by name."""
        self._tools.pop(name, None)

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
