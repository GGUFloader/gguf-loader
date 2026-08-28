"""
SlashCommands - Slash command parser for the chat input.

Inspired by Aider's Commands class where any method named cmd_xxx
becomes a /xxx command. This implementation provides the core commands
for GGUFLoader's agent mode.

Source: aider/commands.py Commands class (30+ cmd_xxx methods)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SlashCommands:
    """Slash command handler for the chat panel.

    Commands:
        /add <file>     - Add file to context
        /drop <file>    - Remove file from context
        /clear          - Clear conversation
        /undo           - Undo last exchange
        /help           - Show available commands
        /map            - Show workspace file map
        /diff           - Show recent changes
        /memory         - Show working memory
        /status         - Show session status
        /export         - Export conversation
    """

    def __init__(self, workspace: Optional[Path] = None) -> None:
        self.workspace = workspace
        self._context_files: List[str] = []
        self._commands: Dict[str, Callable] = {
            "add": self._cmd_add,
            "drop": self._cmd_drop,
            "clear": self._cmd_clear,
            "undo": self._cmd_undo,
            "help": self._cmd_help,
            "map": self._cmd_map,
            "diff": self._cmd_diff,
            "memory": self._cmd_memory,
            "status": self._cmd_status,
            "export": self._cmd_export,
            "preset": self._cmd_preset,
            "workspace": self._cmd_workspace,
            "settings": self._cmd_settings,
            "health": self._cmd_health,
        }
        # Callbacks set by the main window
        self.on_clear: Optional[Callable] = None
        self.on_undo: Optional[Callable] = None
        self.on_export: Optional[Callable] = None
        self.on_status: Optional[Callable[[], str]] = None
        self.on_memory: Optional[Callable[[], str]] = None
        self.on_preset: Optional[Callable[[str], None]] = None
        self.on_workspace: Optional[Callable[[str], None]] = None
        self.on_settings: Optional[Callable] = None
        self.on_health: Optional[Callable[[], str]] = None

    def get_commands(self) -> List[str]:
        """Return list of available slash commands."""
        return [f"/{cmd}" for cmd in sorted(self._commands.keys())]

    def matching_commands(self, text: str) -> List[str]:
        """Return commands matching the given prefix."""
        if not text.startswith("/"):
            return []
        prefix = text.lower()
        return [cmd for cmd in self.get_commands() if cmd.startswith(prefix)]

    def handle(self, text: str) -> Optional[str]:
        """Handle a slash command.

        Args:
            text: The full command text (e.g., "/add file.py")

        Returns:
            Response message, or None if not a command
        """
        if not text.startswith("/"):
            return None

        parts = text.strip().split(maxsplit=1)
        cmd_name = parts[0].lstrip("/").lower()
        args = parts[1] if len(parts) > 1 else ""

        handler = self._commands.get(cmd_name)
        if handler is None:
            return f"Unknown command: {parts[0]}. Type /help for available commands."

        try:
            return handler(args)
        except Exception as e:
            return f"Error executing {parts[0]}: {e}"

    def _cmd_add(self, args: str) -> str:
        """Add file to context."""
        if not args.strip():
            return "Usage: /add <filename>"
        fname = args.strip()
        if fname not in self._context_files:
            self._context_files.append(fname)
            return f"Added '{fname}' to context."
        return f"'{fname}' is already in context."

    def _cmd_drop(self, args: str) -> str:
        """Remove file from context."""
        if not args.strip():
            if self._context_files:
                dropped = self._context_files.copy()
                self._context_files.clear()
                return f"Dropped all files: {', '.join(dropped)}"
            return "No files in context."
        fname = args.strip()
        if fname in self._context_files:
            self._context_files.remove(fname)
            return f"Dropped '{fname}' from context."
        return f"'{fname}' not in context."

    def _cmd_clear(self, args: str) -> str:
        """Clear conversation."""
        if self.on_clear:
            self.on_clear()
        return "Chat cleared."

    def _cmd_undo(self, args: str) -> str:
        """Undo last exchange."""
        if self.on_undo:
            result = self.on_undo()
            return result or "Undid last exchange."
        return "Undo not available."

    def _cmd_help(self, args: str) -> str:
        """Show available commands."""
        lines = ["Available commands:"]
        for cmd in sorted(self._commands.keys()):
            doc = self._commands[cmd].__doc__ or ""
            lines.append(f"  /{cmd:12s} - {doc.strip()}")
        return "\n".join(lines)

    def _cmd_map(self, args: str) -> str:
        """Show workspace file map."""
        if self.workspace is None or not self.workspace.is_dir():
            return "No workspace set."
        try:
            files = []
            for root, dirs, names in self.workspace.walk():
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d not in ("__pycache__", "node_modules", ".venv")
                ]
                for name in names:
                    path = Path(root) / name
                    rel = str(path.relative_to(self.workspace))
                    files.append(rel)
                if len(files) > 100:
                    files.append("... (truncated)")
                    break
            if not files:
                return "Workspace is empty."
            return "Workspace files:\n" + "\n".join(f"  {f}" for f in sorted(files))
        except Exception as e:
            return f"Error reading workspace: {e}"

    def _cmd_diff(self, args: str) -> str:
        """Show recent changes."""
        return "Diff display not available in agent mode. Use /map to see files."

    def _cmd_memory(self, args: str) -> str:
        """Show working memory."""
        if self.on_memory:
            return self.on_memory()
        return "Working memory: (no data)"

    def _cmd_status(self, args: str) -> str:
        """Show session status."""
        if self.on_status:
            return self.on_status()
        parts = [f"Context files: {len(self._context_files)}"]
        if self.workspace:
            parts.append(f"Workspace: {self.workspace}")
        return "\n".join(parts)

    def _cmd_export(self, args: str) -> str:
        """Export conversation."""
        if self.on_export:
            self.on_export()
            return "Exporting..."
        return "Export not available."

    def get_context_files(self) -> List[str]:
        """Return the list of files added to context."""
        return self._context_files.copy()

    def _cmd_preset(self, args: str) -> str:
        """Switch agent preset (research, code_review, refactor, debug, full_stack, quick_fix)."""
        valid = ["research", "code_review", "refactor", "debug", "full_stack", "quick_fix"]
        if not args.strip():
            return f"Usage: /preset <name>\nAvailable: {', '.join(valid)}"
        preset = args.strip().lower()
        if preset not in valid:
            return f"Unknown preset: {preset}. Available: {', '.join(valid)}"
        if self.on_preset:
            self.on_preset(preset)
        return f"Switched to preset: {preset}"

    def _cmd_workspace(self, args: str) -> str:
        """Set or show the workspace directory."""
        if not args.strip():
            if self.workspace:
                return f"Current workspace: {self.workspace}"
            return "No workspace set. Use /workspace <path> to set one."
        path = args.strip()
        self.workspace = Path(path)
        if self.on_workspace:
            self.on_workspace(path)
        return f"Workspace set to: {path}"

    def _cmd_settings(self, args: str) -> str:
        """Open the agent settings dialog."""
        if self.on_settings:
            self.on_settings()
        return "Opening agent settings..."

    def _cmd_health(self, args: str) -> str:
        """Show agent health and performance metrics."""
        if self.on_health:
            return self.on_health()
        return "Health data not available."

