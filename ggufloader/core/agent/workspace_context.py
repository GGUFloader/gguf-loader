"""
WorkspaceContext - Live repo context, AGENTS.md support, and prompt prefix caching.

Collects "stable facts" about the workspace (git status, project type, conventions)
before the first prompt, so the agent doesn't start from zero on every turn.
Builds and caches the prompt prefix across turns to save tokens and KV cache.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Project marker files and their descriptions
PROJECT_MARKERS = {
    "pyproject.toml": "Python project (pyproject.toml)",
    "setup.py": "Python project (setup.py)",
    "requirements.txt": "Python project (requirements.txt)",
    "package.json": "Node.js project (package.json)",
    "Cargo.toml": "Rust project (Cargo.toml)",
    "go.mod": "Go project (go.mod)",
    "pom.xml": "Java project (pom.xml)",
    "build.gradle": "Java/Kotlin project (build.gradle)",
    "CMakeLists.txt": "C/C++ project (CMakeLists.txt)",
    "Makefile": "Project with Makefile",
    "Gemfile": "Ruby project (Gemfile)",
    "composer.json": "PHP project (composer.json)",
}

# Agent instruction files (checked in order)
AGENT_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
    "COPILOT.md",
    ".github/copilot-instructions.md",
    "CONVENTIONS.md",
]

# Files that hint at test frameworks
TEST_MARKERS = {
    "pytest.ini": "pytest",
    "setup.cfg": "pytest (setup.cfg)",
    "tox.ini": "tox/pytest",
    "jest.config.js": "Jest",
    "jest.config.ts": "Jest",
    "vitest.config.js": "Vitest",
    "vitest.config.ts": "Vitest",
    ".mocharc.yml": "Mocha",
    "phpunit.xml": "PHPUnit",
}


def _run_git(args: List[str], workspace: Path) -> Optional[str]:
    """Run a git command and return stripped stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


class WorkspaceContext:
    """Collects and caches workspace facts for the agent system prompt."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._cache: Optional[str] = None
        self._cache_hash: Optional[str] = None

    def build_context(self) -> str:
        """Build the workspace context block. Cached until workspace changes."""
        # Build a hash of key files to detect changes
        current_hash = self._compute_hash()
        if self._cache is not None and self._cache_hash == current_hash:
            return self._cache

        parts: List[str] = []

        # 1. Git context
        git_info = self._git_context()
        if git_info:
            parts.append(git_info)

        # 2. Project type
        project_info = self._detect_project_type()
        if project_info:
            parts.append(project_info)

        # 3. AGENTS.md / project memory
        agents_md = self._read_agents_md()
        if agents_md:
            parts.append(agents_md)

        # 4. Test framework
        test_info = self._detect_test_framework()
        if test_info:
            parts.append(test_info)

        result = "\n".join(parts) if parts else ""
        self._cache = result
        self._cache_hash = current_hash
        return result

    def invalidate_cache(self) -> None:
        """Force rebuild on next call (e.g. after file edits)."""
        self._cache = None
        self._cache_hash = None

    def _compute_hash(self) -> str:
        """Hash key workspace files to detect changes."""
        h = hashlib.md5()
        h.update(str(self.workspace).encode())
        for name in ["AGENTS.md", "CLAUDE.md", "pyproject.toml", "package.json"]:
            path = self.workspace / name
            if path.exists():
                try:
                    h.update(path.read_bytes()[:4096])
                except OSError:
                    pass
        return h.hexdigest()

    def _git_context(self) -> str:
        """Git branch, status, and recent commits."""
        lines: List[str] = ["## Git Repository"]

        branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], self.workspace)
        if branch:
            lines.append(f"- Branch: {branch}")

        status = _run_git(["status", "--short"], self.workspace)
        if status:
            changed = len(status.splitlines())
            lines.append(f"- Status: {changed} file(s) modified")
        else:
            lines.append("- Status: clean")

        log = _run_git(
            ["log", "--oneline", "-5", "--format=%h %s"], self.workspace
        )
        if log:
            lines.append("- Recent commits:")
            for commit_line in log.splitlines()[:5]:
                lines.append(f"  {commit_line}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def _detect_project_type(self) -> str:
        """Detect project type from marker files."""
        found: List[str] = []
        for marker, description in PROJECT_MARKERS.items():
            if (self.workspace / marker).exists():
                found.append(description)
        if not found:
            return ""
        return "## Project Type\n" + "\n".join(f"- {d}" for d in found)

    def _read_agents_md(self) -> str:
        """Read AGENTS.md or similar project memory files."""
        for filename in AGENT_FILES:
            path = self.workspace / filename
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    # Cap at 3000 chars to avoid prompt bloat
                    if len(content) > 500:
                        content = content[:500] + "\n... (truncated)"
                    return f"## Project Instructions ({filename})\n{content}"
                except OSError:
                    continue
        return ""

    def _detect_test_framework(self) -> str:
        """Detect which test framework the project uses."""
        for marker, framework in TEST_MARKERS.items():
            if (self.workspace / marker).exists():
                return f"## Test Framework\n- Uses {framework}"
        return ""


class WorkingMemory:
    """Tracks task context across agent steps (like Mini-Coding-Agent).

    Maintains a short-lived working memory of:
    - The current task description
    - Files touched (MRU list, max 8)
    - Notes accumulated during execution (last 5)

    This prevents the agent from forgetting its task context across steps,
    which is especially important for local models with limited context.
    """

    def __init__(self) -> None:
        self.task: str = ""
        self.files: list[str] = []   # MRU, max 8
        self.notes: list[str] = []   # last 5

    def remember_file(self, path: str) -> None:
        """Track a file that was read/written. MRU order."""
        if not path:
            return
        if path in self.files:
            self.files.remove(path)
        self.files.append(path)
        del self.files[:-8]

    def add_note(self, note: str) -> None:
        """Add a short execution note."""
        if not note:
            return
        clipped = note[:220]
        if clipped in self.notes:
            self.notes.remove(clipped)
        self.notes.append(clipped)
        del self.notes[:-5]

    def set_task(self, task: str) -> None:
        """Set the current task description (once per user message)."""
        if not self.task:
            self.task = task[:300]

    def text(self) -> str:
        """Model-visible memory block."""
        files = ", ".join(self.files) or "(none)"
        notes_lines = ["  - " + n for n in self.notes]
        notes = chr(10).join(notes_lines) if notes_lines else "  (none)"
        NL = chr(10)
        return (
            "Working memory:" + NL
            + "- Task: " + (self.task or "(none)") + NL
            + "- Files touched: " + files + NL
            + "- Notes:" + NL + notes
        )

    def clear(self) -> None:
        """Reset memory for a new task."""
        self.task = ""
        self.files.clear()
        self.notes.clear()

class PromptPrefixCache:
    """Caches the stable prompt prefix across turns."

    The prefix includes: system prompt + workspace context + tool descriptions.
    Only the variable suffix (transcript + user message) changes per turn.
    """

    def __init__(self) -> None:
        self._prefix: Optional[str] = None
        self._prefix_hash: Optional[str] = None

    def get_prefix(
        self,
        system_prompt: str,
        workspace_context: str,
        tool_descriptions: str,
    ) -> str:
        """Return the cached prefix, rebuilding only if inputs changed."""
        # Build hash of inputs
        h = hashlib.md5()
        h.update(system_prompt.encode())
        h.update(workspace_context.encode())
        h.update(tool_descriptions.encode())
        new_hash = h.hexdigest()

        if self._prefix is not None and self._prefix_hash == new_hash:
            return self._prefix

        # Rebuild prefix
        parts = [system_prompt, ""]
        if workspace_context:
            parts.append(workspace_context)
            parts.append("")
        if tool_descriptions:
            parts.append("You have access to these tools:")
            parts.append(tool_descriptions)
            parts.append("")

        self._prefix = "\n".join(parts)
        self._prefix_hash = new_hash
        return self._prefix

    def invalidate(self) -> None:
        """Force rebuild on next call."""
        self._prefix = None
        self._prefix_hash = None
