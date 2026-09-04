"""
ToolRegistry - Sandboxed filesystem tools for the agent engine.

Every tool resolves paths relative to a single workspace root and refuses
to escape it (path-traversal protection). The registry itself is pure
Python (no Qt) so it can be unit tested in isolation.
"""

from __future__ import annotations

import os
import re
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
    description = ("Search the text CONTENT of files under the workspace (scans the "
                   "first 256 KB of each file; binary/generated files are skipped). "
                   "To find a file BY NAME or path, use glob instead")
    schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string",
                         "description": "Plain text to search for (case-insensitive). "
                                        "Separate several alternatives with | to match any of them "
                                        "(e.g. 'purpose|overview' matches files containing either word). "
                                        "This is NOT a regular expression - no other regex syntax is supported."},
            "path": {"type": "string",
                      "description": "Directory to search, relative to the workspace (defaults to .)"},
        },
        "required": ["pattern"],
    }

    #: Directory names never worth searching: dependency caches, build
    #: artifacts, version-control internals. Pruned during the walk so a
    #: repo with node_modules/.git never stalls the agent for minutes.
    _SKIP_DIRS = frozenset({
        ".git", ".hg", ".svn", "__pycache__", "node_modules", "bower_components",
        ".venv", "venv", "env", ".tox", ".nox", "dist", "build", ".next",
        ".nuxt", ".svelte-kit", ".cache", ".pytest_cache", ".mypy_cache",
        ".ruff_cache", ".hypothesis", ".idea", ".vscode", ".turbo", ".parcel-cache",
        ".egg-info", ".yarn", ".pnpm-store", "site-packages", "coverage",
    })
    #: Safety valves: even after pruning, stop after this many files scanned
    #: (or matches found) and say so explicitly instead of hanging forever.
    _MAX_FILES_SCANNED = 20000
    _MAX_MATCHES = 300
    #: Suffixes never worth searching: binary formats, archives, media, and
    #: generated build artifacts (source maps, bytecode, compiled resources).
    #: Skipping them by extension avoids reading megabytes per file (a 1 MB
    #: PNG or a 5 MB source map costs nothing to skip this way).
    _SKIP_EXTS = frozenset({
        # images / media
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tif",
        ".tiff", ".avif", ".svgz", ".mp3", ".mp4", ".avi", ".mkv", ".mov",
        ".wav", ".flac", ".ogg", ".webm", ".m4a", ".ttf", ".otf", ".woff",
        ".woff2", ".eot",
        # documents / archives
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt",
        ".epub", ".zip", ".gz", ".tar", ".7z", ".rar", ".bz2", ".xz", ".zst",
        ".whl", ".egg", ".iso", ".dmg",
        # binaries / executables
        ".exe", ".dll", ".so", ".dylib", ".a", ".o", ".obj", ".lib",
        ".bin", ".dat", ".sys", ".pdb", ".exp", ".mod",
        # models / tensors
        ".gguf", ".safetensors", ".pt", ".pth", ".onnx", ".ckpt", ".npy",
        ".npz", ".h5", ".hdf5", ".parquet", ".arrow", ".pb", ".tflite",
        # bytecode / compiled / generated
        ".pyc", ".pyo", ".pyd", ".class", ".jar", ".wasm", ".pak", ".qm",
        ".qph", ".qmlc", ".map", ".tsbuildinfo",
        # databases / caches
        ".db", ".sqlite", ".sqlite3", ".mdb", ".idx", ".cache",
    })
    #: Filename markers for generated/minified artifacts whose extension is
    #: still a text one (.min.js, .bundle.js, .chunk.js...).
    _SKIP_NAME_SUFFIXES = (".min.js", ".min.css", ".bundle.js", ".chunk.js",
                           ".vendor.js", ".d.ts.map")
    #: Read only the first chunk of each file. Nearly all matches an agent
    #: cares about live in the head of a source/doc file; this caps the cost
    #: of minified bundles, generated JSON dumps and giant logs at one short
    #: read instead of reading the whole file into memory.
    _HEAD_BYTES = 256 * 1024

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            query = params.get("pattern") or params.get("query", "")
            if not query or not query.strip():
                return {"status": "error", "error": "pattern is required", "tool_name": self.name}
            path = self.resolve(params.get("path", "."))
            if not path.is_dir():
                return {"status": "error", "error": "Directory not found", "tool_name": self.name}
            # Literal (case-insensitive) match. Models routinely write
            # 'one|two' as a regex-style alternation; treat | as a union of
            # plain-text terms instead of searching for the literal pipe.
            needles = [q.strip().lower() for q in query.split("|") if q.strip()]
            if not needles:
                needles = [query.lower()]
            results = []
            files_scanned = 0
            truncated = False
            for root, dirs, files in os.walk(path):
                # Prune ignored and hidden directories in place (os.walk honors
                # the mutation); keep dotfiles but not dot-directories.
                dirs[:] = sorted(
                    d for d in dirs
                    if not d.startswith(".") and d not in self._SKIP_DIRS
                )
                for name in sorted(files):
                    if files_scanned >= self._MAX_FILES_SCANNED:
                        truncated = True
                        break
                    file_path = Path(root) / name
                    if (file_path.suffix.lower() in self._SKIP_EXTS
                            or name.endswith(self._SKIP_NAME_SUFFIXES)):
                        continue  # binary/generated - never worth reading
                    files_scanned += 1
                    try:
                        # Head-only read: one bounded read per file, then a
                        # NUL sniff (identical semantics to the old full-file
                        # sniff - the first 4 KB decide either way).
                        with file_path.open("rb") as fh:
                            head = fh.read(self._HEAD_BYTES)
                        if is_binary(head):
                            continue  # no clean keyword text
                        text = head.decode("utf-8", errors="ignore")
                        hay = text.lower()
                        if any(n in hay for n in needles):
                            results.append(str(file_path.relative_to(self.workspace)))
                            if len(results) >= self._MAX_MATCHES:
                                truncated = True
                                break
                    except Exception:
                        continue
                if truncated:
                    break
            result: Dict[str, Any] = {
                "status": "success", "result": results,
                "total_matches": len(results), "tool_name": self.name,
            }
            if truncated:
                result["truncated"] = True
                result["note"] = (f"Search stopped after {self._MAX_FILES_SCANNED} files / "
                                  f"{self._MAX_MATCHES} matches; results are partial.")
            return result
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


def tool_content_for_context(result: Dict[str, Any], max_chars: int = 1000) -> Optional[str]:
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
    if tool == "glob" and isinstance(payload, list):
        if not payload:
            # Zero matches: surface the tool's note so the answer step
            # knows the glob RAN and found nothing (instead of empty).
            return result.get("note") or "No files matched"
        paths = ", ".join(str(p) for p in payload[:50])
        return f"{paths} ({len(payload)} files)"
    if tool == "move_file" and isinstance(payload, str):
        return payload
    return None


class GlobTool(Tool):
    """Find files matching a glob pattern under the workspace.

    Walks the tree with the same pruning and caps as ``search_files`` —
    otherwise a ``**`` pattern crawls ``node_modules``/``.venv``/``.git`` and
    freezes the graph for seconds. An empty match is reported explicitly
    (with a hint) instead of as a silent success, so the answer step knows
    the tool actually ran and found nothing.
    """

    name = "glob"
    description = ("Find files BY NAME or path pattern (e.g. **/*.py, src/**/*.ts) — "
                   "use when the user wants to locate a file. Scans only source "
                   "files; dependency/build/vendor directories are skipped.")
    schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern (supports **, *, ?)",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (defaults to workspace root)",
            },
        },
        "required": ["pattern"],
    }

    #: Same safety valves as SearchFilesTool — shared semantics so a repo
    #: with node_modules/.git can never stall the agent on a glob.
    _SKIP_DIRS = SearchFilesTool._SKIP_DIRS
    _MAX_FILES_SCANNED = SearchFilesTool._MAX_FILES_SCANNED
    _MAX_MATCHES = 300

    @staticmethod
    def _glob_to_regex(pattern: str) -> "re.Pattern[str]":
        """Translate a glob pattern into an anchored regex.

        ``**`` matches zero or more path segments, ``*`` matches within a
        segment, ``?`` matches a single character. ``/`` is the only
        separator (paths are normalized to POSIX form before matching).
        """
        parts = [p for p in pattern.replace("\\", "/").split("/") if p != ""]
        out: List[str] = []
        for part in parts:
            if part == "**":
                out.append("(?:[^/]+/)*")
            else:
                chunk: List[str] = []
                i = 0
                while i < len(part):
                    c = part[i]
                    if c == "*":
                        chunk.append("[^/]*")
                    elif c == "?":
                        chunk.append("[^/]")
                    else:
                        chunk.append(re.escape(c))
                    i += 1
                out.append("".join(chunk))
                out.append("/")
        if out and out[-1] == "/":
            out.pop()
        return re.compile("^" + "".join(out) + "$")

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            pattern = params.get("pattern", "")
            if not pattern or not pattern.strip():
                return {"status": "error", "error": "pattern is required", "tool_name": self.name}
            base = self.resolve(params.get("path", "."))
            if not base.is_dir():
                return {"status": "error", "error": "Directory not found", "tool_name": self.name}
            regex = self._glob_to_regex(pattern)
            matches: List[str] = []
            files_scanned = 0
            truncated = False
            for root, dirs, files in os.walk(base):
                dirs[:] = sorted(
                    d for d in dirs
                    if not d.startswith(".") and d not in self._SKIP_DIRS
                )
                for name in sorted(files):
                    if files_scanned >= self._MAX_FILES_SCANNED:
                        truncated = True
                        break
                    files_scanned += 1
                    rel = (Path(root) / name).relative_to(base).as_posix()
                    if regex.match(rel):
                        matches.append((Path(root) / name).relative_to(self.workspace).as_posix())
                        if len(matches) >= self._MAX_MATCHES:
                            truncated = True
                            break
                if truncated:
                    break
            result: Dict[str, Any] = {
                "status": "success",
                "result": matches[:200],
                "total_matches": len(matches),
                "tool_name": self.name,
            }
            if not matches:
                base_rel = base.relative_to(self.workspace).as_posix() or "."
                result["note"] = (
                    f"No files matched pattern {pattern!r} under {base_rel}. "
                    f"Try a different pattern (e.g. '**/*.py' or '**/*.md')."
                )
            elif truncated:
                result["truncated"] = True
                result["note"] = (
                    f"Glob stopped after {self._MAX_FILES_SCANNED} files / "
                    f"{self._MAX_MATCHES} matches; results are partial."
                )
            return result
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": self.name}


class MoveFileTool(Tool):
    """Move or rename a file within the workspace."""

    name = "move_file"
    description = "Move or rename a file within the workspace"
    requires_approval = True
    schema = {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Current file path (relative to workspace)"},
            "destination": {"type": "string", "description": "New file path (relative to workspace)"},
        },
        "required": ["source", "destination"],
    }

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            src = self.resolve(params.get("source", ""))
            dst = self.resolve(params.get("destination", ""))
            if not src.exists():
                return {"status": "error", "error": f"Source not found: {src.name}", "tool_name": self.name}
            if dst.exists():
                return {"status": "error", "error": f"Destination already exists: {dst.name}", "tool_name": self.name}
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            return {
                "status": "success",
                "result": f"Moved {src.name} -> {dst.relative_to(self.workspace)}",
                "tool_name": self.name,
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": self.name}


# Default tool universe for the pinned single-model build: file/dev tools
# only. The memory/meta tools (remember, recall, forget, record_correction,
# generate_agents_md, export_session, batch_execute and the python_interpreter
# alias of run_python) were removed — a 12B model should never be offered a
# catalog it can't use well.
ALL_TOOL_CLASSES = (
    ListDirectoryTool, ReadFileTool, WriteFileTool, EditFileTool,
    SearchFilesTool, RunCommandTool, RunPythonTool, GitTool,
    GlobTool, MoveFileTool,
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
