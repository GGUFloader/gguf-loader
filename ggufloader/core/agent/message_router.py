"""
MessageRouter - Lightweight classifier that decides chat vs agent mode.

Analyzes the user message and workspace context to determine whether
tools (file read, search, etc.) are needed, or if a direct LLM response
is sufficient.

Rules:
- Simple greetings, questions, explanations → chat
- File references, folder operations, search requests → agent
- Complex multi-step tasks → agent
- "what is", "explain", "how does" about code → agent (needs to read files)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


# Patterns that suggest tools are needed
_FILE_PATTERNS = [
    r"\b\w+\.\w{1,5}\b",                    # any file.ext
    r"(?:read|open|show|look at|check|view|cat)\b",  # file operations
    r"(?:search|find|grep|look for|scan)\b",  # search operations
    r"(?:list|ls|dir|folder|directory|tree)\b",  # directory operations
    r"(?:edit|modify|change|update|write|create|delete|remove|move|rename)\b",  # write operations
    r"(?:run|execute|build|compile|test|install)\b",  # command operations
    r"(?:git|commit|push|pull|diff|status|log)\b",  # git operations
]

# Patterns that suggest chat is sufficient
_CHAT_PATTERNS = [
    r"^(?:hi|hello|hey|yo|sup|howdy|greetings)\b",
    r"^(?:thanks|thank you|thx|ty)\b",
    r"^(?:ok|okay|sure|yes|no|yep|nope|bye|goodbye)\b",
    r"^(?:what(?:'s| is) (?:your name|the time|the date|up))\b",
    r"^(?:how (?:are you|do you work|does this work))\b",
    r"^(?:help|help me|what can you do)\b",
    r"^(?:good (?:morning|afternoon|evening|night))\b",
]

# Patterns that strongly suggest agent mode
_AGENT_STRONG = [
    r"(?:read|open|show|view|cat)\s+\S+\.\w{1,5}",  # read file.py
    r"(?:summarize|summarise|overview|analyze|analyse)\s+(?:this|the|all|every)",  # summarize this
    r"(?:search|find|grep|look for)\s+.{3,}",  # search for something
    r"(?:list|show)\s+(?:all|every|the)\s+(?:files?|folders?|contents?)",  # list all files
    r"(?:what(?:'s| is)\s+in\s+(?:this|the)\s+(?:folder|directory|file|project))",  # what's in this folder
    r"(?:explain|describe)\s+(?:this|the)\s+(?:file|code|project|folder|directory)",  # explain this file
    r"(?:fix|repair|debug|troubleshoot)\s+.{3,}",  # fix something
    r"(?:create|write|make|generate)\s+(?:a\s+)?(?:file|script|program|code)",  # create a file
]

# File extensions that indicate code/config files
_CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h",
    ".rs", ".go", ".rb", ".php", ".cs", ".swift", ".kt",
    ".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg",
    ".md", ".txt", ".rst",
    ".html", ".css", ".scss", ".less",
    ".sh", ".bat", ".ps1",
    ".sql", ".graphql",
    ".env", ".gitignore", ".dockerignore",
}

# Known folder names that suggest project context
_PROJECT_FOLDERS = {
    "src", "lib", "app", "components", "pages", "routes", "api",
    "tests", "test", "spec", "__tests__",
    "docs", "doc", "documentation",
    "config", "configs", "settings",
    "scripts", "tools", "utils", "helpers",
    "models", "data", "assets", "static", "public",
    ".git", ".github", ".vscode",
    "node_modules", "venv", ".venv", "__pycache__",
}


class MessageRouter:
    """Classifies user messages as chat or agent mode."""

    def __init__(self, workspace: Optional[Path] = None) -> None:
        self.workspace = workspace

    def route(self, message: str) -> str:
        """Return 'chat' or 'agent' based on message analysis."""
        msg = message.strip().lower()

        # Very short messages → chat
        if len(msg) < 5:
            return "chat"

        # Check chat patterns first (greetings, thanks, etc.)
        for pattern in _CHAT_PATTERNS:
            if re.match(pattern, msg):
                return "chat"

        # Check strong agent patterns
        for pattern in _AGENT_STRONG:
            if re.search(pattern, msg):
                return "agent"

        # Check for file references in the message
        if self._has_file_references(msg):
            return "agent"

        # Check for folder references
        if self._has_folder_references(msg):
            return "agent"

        # Check message complexity (longer messages often need tools)
        if len(msg.split()) > 30:
            return "agent"

        # Check for question words that might need file context
        question_words = {"what", "why", "how", "where", "which", "who"}
        first_word = msg.split()[0] if msg.split() else ""
        if first_word in question_words and self._mentions_code(msg):
            return "agent"

        # Default to chat
        return "chat"

    def _has_file_references(self, msg: str) -> bool:
        """Check if message references specific files."""
        # Look for file.ext patterns
        words = msg.split()
        for word in words:
            # Strip punctuation
            clean = word.strip(".,!?;:'\"()[]{}")
            if "." in clean:
                ext = "." + clean.rsplit(".", 1)[-1]
                if ext in _CODE_EXTS:
                    return True
        return False

    def _has_folder_references(self, msg: str) -> bool:
        """Check if message references folders or directories."""
        folder_words = {"folder", "directory", "dir", "path", "project", "workspace", "repo"}
        words = set(msg.split())
        return bool(words & folder_words)

    def _mentions_code(self, msg: str) -> bool:
        """Check if message mentions code-related concepts."""
        code_words = {
            "code", "function", "class", "method", "variable", "import",
            "module", "package", "library", "framework", "api", "endpoint",
            "file", "script", "program", "bug", "error", "issue", "fix",
            "refactor", "test", "debug", "compile", "build", "run",
        }
        words = set(msg.split())
        return bool(words & code_words)
