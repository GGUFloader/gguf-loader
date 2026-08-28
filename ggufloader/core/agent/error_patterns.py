"""
ErrorPatterns - Detect recurring error patterns and suggest fixes.

Pattern from: Aider's error recovery + OpenHands stuck detection.
Tracks error occurrences over time to identify:
- Recurring errors in the same file/function
- Common failure modes (permission, syntax, timeout)
- Error chains (one error causing another)
- Fix patterns (what resolved each error type)

The detector provides actionable suggestions based on what worked before.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ErrorEntry:
    """A single error occurrence."""

    def __init__(self, error_type: str, message: str, context: str = "",
                 tool: str = "", file_path: str = "", stack: str = "") -> None:
        self.error_type = error_type
        self.message = message
        self.context = context
        self.tool = tool
        self.file_path = file_path
        self.stack = stack
        self.timestamp = time.time()
        self.resolved = False
        self.fix_applied: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.error_type,
            "message": self.message[:200],
            "context": self.context[:200],
            "tool": self.tool,
            "file": self.file_path,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "fix": self.fix_applied,
        }


class ErrorPattern:
    """A detected pattern of recurring errors."""

    def __init__(self, pattern_id: str, error_type: str,
                 description: str, occurrences: int) -> None:
        self.pattern_id = pattern_id
        self.error_type = error_type
        self.description = description
        self.occurrences = occurrences
        self.suggested_fix: Optional[str] = None
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.files_affected: List[str] = []
        self.successful_fixes: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.pattern_id,
            "type": self.error_type,
            "description": self.description,
            "occurrences": self.occurrences,
            "suggested_fix": self.suggested_fix,
            "files": self.files_affected[:5],
            "successful_fixes": self.successful_fixes[:3],
        }


# Error type classification
ERROR_CLASSIFIERS = {
    "syntax": [r"syntaxerror", r"invalid syntax", r"unexpected token"],
    "import": [r"importerror", r"module.*not found", r"no module named"],
    "permission": [r"permission denied", r"access denied", r"eacces"],
    "not_found": [r"file not found", r"no such file", r"enoent"],
    "timeout": [r"timed? ?out", r"deadline exceeded", r"timeout"],
    "memory": [r"out of memory", r"memoryerror", r"oom"],
    "network": [r"connection.*refused", r"network.*unreachable", r"ename Resolution"],
    "type": [r"typeerror", r"unsupported operand", r"argument.*must be"],
    "value": [r"valueerror", r"invalid.*literal", r"could not convert"],
    "key": [r"keyerror", r"key.*not found", r"missing key"],
    "json": [r"jsondecodeerror", r"expecting.*delimiter", r"invalid json"],
    "unicode": [r"unicodeerror", r"utf.*codec", r"charmap"],
}

# Fix suggestions per error type
FIX_SUGGESTIONS = {
    "syntax": [
        "Check for missing colons, brackets, or quotes",
        "Run ast.parse() to identify the exact line",
        "Check indentation (tabs vs spaces)",
    ],
    "import": [
        "Check if the module is installed (pip install <module>)",
        "Verify the import path is correct",
        "Check for circular imports",
    ],
    "permission": [
        "Run with appropriate permissions",
        "Check file ownership (ls -la)",
        "Use sudo only if absolutely necessary",
    ],
    "not_found": [
        "Check the file path spelling",
        "Use list_directory to verify the file exists",
        "Check if the file was moved or deleted",
    ],
    "timeout": [
        "Increase the timeout value",
        "Break the operation into smaller parts",
        "Check if the system is under heavy load",
    ],
    "memory": [
        "Use a smaller model or reduce context size",
        "Process data in chunks",
        "Close other applications to free memory",
    ],
    "network": [
        "Check network connectivity",
        "Verify the URL is correct",
        "Try again in a few seconds (transient error)",
    ],
    "type": [
        "Check the data types being passed",
        "Add type conversion (int(), str(), etc.)",
        "Verify the function signature",
    ],
    "value": [
        "Validate input before processing",
        "Use try/except for user input",
        "Check for empty or malformed values",
    ],
    "key": [
        "Use .get() with default value instead of []",
        "Check if the key exists before accessing",
        "Verify the dictionary structure",
    ],
    "json": [
        "Validate JSON before parsing",
        "Use try/except json.JSONDecodeError",
        "Check for trailing commas or missing quotes",
    ],
    "unicode": [
        "Specify encoding explicitly (encoding='utf-8')",
        "Use errors='replace' or errors='ignore'",
        "Check the file's actual encoding",
    ],
}


class ErrorPatternDetector:
    """Detect and track recurring error patterns.

    Usage:
        detector = ErrorPatternDetector(workspace)

        # Record errors
        detector.record_error("syntax", "invalid syntax at line 5",
                            tool="edit_file", file_path="main.py")

        # Get patterns
        patterns = detector.get_patterns()
        for p in patterns:
            print(f"{p.description} ({p.occurrences}x): {p.suggested_fix}")

        # Record a fix
        detector.record_fix("syntax_main_py", "Added missing colon")
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._data_file = workspace / ".ggufloader-errors.json"
        self._errors: List[ErrorEntry] = []
        self._patterns: Dict[str, ErrorPattern] = {}
        self._fixes: Dict[str, List[str]] = {}  # pattern_id → list of fixes
        self._max_errors = 500
        self._load()

    def _load(self) -> None:
        if not self._data_file.exists():
            return
        try:
            data = json.loads(self._data_file.read_text(encoding="utf-8"))
            for e in data.get("errors", []):
                entry = ErrorEntry(
                    error_type=e.get("type", ""),
                    message=e.get("message", ""),
                    context=e.get("context", ""),
                    tool=e.get("tool", ""),
                    file_path=e.get("file", ""),
                )
                entry.resolved = e.get("resolved", False)
                entry.fix_applied = e.get("fix")
                self._errors.append(entry)
            for p in data.get("patterns", []):
                pattern = ErrorPattern(
                    p["id"], p["type"], p["description"], p["occurrences"],
                )
                pattern.suggested_fix = p.get("suggested_fix")
                pattern.files_affected = p.get("files", [])
                pattern.successful_fixes = p.get("successful_fixes", [])
                self._patterns[p["id"]] = pattern
        except Exception as e:
            logger.warning("Failed to load error data: %s", e)

    def _save(self) -> None:
        try:
            data = {
                "errors": [e.to_dict() for e in self._errors[-self._max_errors:]],
                "patterns": [p.to_dict() for p in self._patterns.values()],
            }
            self._data_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to save error data: %s", e)

    def record_error(self, error_type: str, message: str, context: str = "",
                     tool: str = "", file_path: str = "", stack: str = "") -> None:
        """Record an error occurrence."""
        # Classify if generic type
        if error_type == "unknown":
            error_type = self._classify_error(message)

        entry = ErrorEntry(error_type, message, context, tool, file_path, stack)
        self._errors.append(entry)

        # Update patterns
        self._update_patterns(entry)

        # Trim old errors
        if len(self._errors) > self._max_errors:
            self._errors = self._errors[-self._max_errors:]

        self._save()

    def record_fix(self, pattern_id: str, fix_description: str) -> None:
        """Record a successful fix for a pattern."""
        if pattern_id in self._patterns:
            self._patterns[pattern_id].successful_fixes.append(fix_description)
            self._patterns[pattern_id].resolved = True
        if pattern_id not in self._fixes:
            self._fixes[pattern_id] = []
        self._fixes[pattern_id].append(fix_description)
        self._save()

    def get_patterns(self, min_occurrences: int = 2) -> List[ErrorPattern]:
        """Get detected patterns with at least min_occurrences."""
        return sorted(
            [p for p in self._patterns.values() if p.occurrences >= min_occurrences],
            key=lambda p: -p.occurrences,
        )

    def get_suggestion(self, error_type: str, message: str = "") -> Optional[str]:
        """Get a fix suggestion for an error."""
        # Check for known patterns
        for pattern in self._patterns.values():
            if pattern.error_type == error_type and pattern.successful_fixes:
                return f"Previous fix that worked: {pattern.successful_fixes[-1]}"

        # Check built-in suggestions
        suggestions = FIX_SUGGESTIONS.get(error_type, [])
        if suggestions:
            return suggestions[0]

        return None

    def get_recent_errors(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._errors[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = defaultdict(int)
        for e in self._errors:
            by_type[e.error_type] += 1
        return {
            "total_errors": len(self._errors),
            "patterns": len(self._patterns),
            "by_type": dict(by_type),
            "resolved": sum(1 for p in self._patterns.values() if p.resolved),
        }

    def _classify_error(self, message: str) -> str:
        """Classify an error message into a type."""
        msg_lower = message.lower()
        for error_type, patterns in ERROR_CLASSIFIERS.items():
            for pattern in patterns:
                if re.search(pattern, msg_lower):
                    return error_type
        return "unknown"

    def _update_patterns(self, entry: ErrorEntry) -> None:
        """Update error patterns based on new error."""
        # Create pattern key from type + file
        key = f"{entry.error_type}:{entry.file_path}"
        if key not in self._patterns:
            desc = f"{entry.error_type} errors"
            if entry.file_path:
                desc += f" in {entry.file_path}"
            self._patterns[key] = ErrorPattern(
                pattern_id=key,
                error_type=entry.error_type,
                description=desc,
                occurrences=0,
            )

        pattern = self._patterns[key]
        pattern.occurrences += 1
        pattern.last_seen = entry.timestamp

        if entry.file_path and entry.file_path not in pattern.files_affected:
            pattern.files_affected.append(entry.file_path)
            if len(pattern.files_affected) > 10:
                pattern.files_affected = pattern.files_affected[-10:]

        # Set suggested fix if not already set
        if not pattern.suggested_fix:
            suggestions = FIX_SUGGESTIONS.get(entry.error_type, [])
            if suggestions:
                pattern.suggested_fix = suggestions[0]
