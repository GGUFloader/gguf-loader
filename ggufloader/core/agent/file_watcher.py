"""
FileWatcher - Monitor workspace for external file changes.

Pattern from: OpenHands file explorer + live reload dev servers.
When files are modified outside the agent (by the user's editor,
by git, by build tools), the watcher detects the change and can
notify the agent to re-read affected files.

Features:
- Poll-based file monitoring (no OS-specific dependencies)
- Debounced change detection (avoid rapid-fire notifications)
- Change history tracking (what changed, when)
- Configurable ignore patterns
- Session-level change log for agent context
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Default ignore patterns
DEFAULT_IGNORE = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".idea", ".vscode", ".gguf-undo",
    ".ggufloader-memory.json", "AGENTS.md",
}

# File change types
CHANGE_CREATED = "created"
CHANGE_MODIFIED = "modified"
CHANGE_DELETED = "deleted"


class FileChange:
    """A single file change event."""

    def __init__(self, path: str, change_type: str, timestamp: float,
                 old_hash: str = "", new_hash: str = "") -> None:
        self.path = path
        self.change_type = change_type
        self.timestamp = timestamp
        self.old_hash = old_hash
        self.new_hash = new_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "type": self.change_type,
            "timestamp": self.timestamp,
        }


class FileWatcher:
    """Monitor workspace files for external changes.

    Usage:
        watcher = FileWatcher(workspace_path)
        watcher.set_callback(my_handler)
        watcher.start()

        # Later
        changes = watcher.get_pending_changes()
        watcher.clear_changes()
        watcher.stop()
    """

    def __init__(self, workspace: Path, poll_interval: float = 2.0) -> None:
        self.workspace = workspace
        self._poll_interval = poll_interval
        self._ignore: Set[str] = set(DEFAULT_IGNORE)
        self._file_hashes: Dict[str, str] = {}
        self._changes: List[FileChange] = []
        self._callback: Optional[Callable[[List[FileChange]], None]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._enabled = False

        # Build initial snapshot
        self._scan_files()

    def set_callback(self, callback: Callable[[List[FileChange]], None]) -> None:
        """Set the callback for change notifications."""
        self._callback = callback

    def add_ignore(self, pattern: str) -> None:
        """Add a pattern to ignore."""
        self._ignore.add(pattern)

    def remove_ignore(self, pattern: str) -> None:
        """Remove an ignore pattern."""
        self._ignore.discard(pattern)

    def enable(self) -> None:
        """Enable file watching and start the background thread."""
        if self._enabled:
            return
        self._enabled = True
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("FileWatcher started (interval=%.1fs)", self._poll_interval)

    def disable(self) -> None:
        """Disable file watching and stop the background thread."""
        self._enabled = False
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        logger.info("FileWatcher stopped")

    def scan_now(self) -> List[FileChange]:
        """Force an immediate scan and return detected changes."""
        changes = self._scan_for_changes()
        if changes:
            with self._lock:
                self._changes.extend(changes)
            if self._callback and changes:
                try:
                    self._callback(changes)
                except Exception as e:
                    logger.error("FileWatcher callback error: %s", e)
        return changes

    def get_pending_changes(self) -> List[FileChange]:
        """Get and clear pending changes."""
        with self._lock:
            changes = list(self._changes)
            self._changes.clear()
        return changes

    def clear_changes(self) -> None:
        """Clear all pending changes."""
        with self._lock:
            self._changes.clear()

    def get_change_summary(self) -> str:
        """Get a human-readable summary of pending changes."""
        changes = self.get_pending_changes()
        if not changes:
            return ""
        by_type: Dict[str, List[str]] = {}
        for c in changes:
            by_type.setdefault(c.change_type, []).append(c.path)
        parts = []
        for ctype, paths in by_type.items():
            if len(paths) <= 3:
                parts.append(f"{ctype}: {', '.join(paths)}")
            else:
                parts.append(f"{ctype}: {', '.join(paths[:3])} (+{len(paths) - 3} more)")
        return "; ".join(parts)

    def get_affected_files(self, changes: List[FileChange] = None) -> Set[str]:
        """Get the set of file paths that were affected."""
        if changes is None:
            changes = self.get_pending_changes()
        return {c.path for c in changes}

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent change history."""
        with self._lock:
            return [c.to_dict() for c in self._changes[-limit:]]

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._running:
            try:
                self.scan_now()
            except Exception as e:
                logger.error("FileWatcher scan error: %s", e)
            time.sleep(self._poll_interval)

    def _scan_files(self) -> None:
        """Build initial file hash snapshot."""
        self._file_hashes = {}
        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in self._ignore]
            for name in files:
                if name.startswith(".") or name in self._ignore:
                    continue
                filepath = Path(root) / name
                rel = str(filepath.relative_to(self.workspace))
                try:
                    self._file_hashes[rel] = self._file_hash(filepath)
                except (OSError, PermissionError):
                    continue

    def _scan_for_changes(self) -> List[FileChange]:
        """Compare current files against snapshot and detect changes."""
        changes: List[FileChange] = []
        current_files: Set[str] = set()
        now = time.time()

        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in self._ignore]
            for name in files:
                if name.startswith(".") or name in self._ignore:
                    continue
                filepath = Path(root) / name
                rel = str(filepath.relative_to(self.workspace))
                current_files.add(rel)

                try:
                    new_hash = self._file_hash(filepath)
                except (OSError, PermissionError):
                    continue

                old_hash = self._file_hashes.get(rel)
                if old_hash is None:
                    changes.append(FileChange(rel, CHANGE_CREATED, now, new_hash=new_hash))
                elif old_hash != new_hash:
                    changes.append(FileChange(rel, CHANGE_MODIFIED, now,
                                              old_hash=old_hash, new_hash=new_hash))

        # Detect deletions
        for rel in set(self._file_hashes.keys()) - current_files:
            changes.append(FileChange(rel, CHANGE_DELETED, now,
                                      old_hash=self._file_hashes[rel]))

        # Update snapshot
        for rel in current_files:
            try:
                filepath = self.workspace / rel
                self._file_hashes[rel] = self._file_hash(filepath)
            except (OSError, PermissionError):
                pass
        for rel in set(self._file_hashes.keys()) - current_files:
            self._file_hashes.pop(rel, None)

        return changes

    def _file_hash(self, path: Path) -> str:
        """Compute a fast hash of a file's content."""
        try:
            stat = path.stat()
            # Use size + mtime for fast change detection (no content read)
            return f"{stat.st_size}:{stat.st_mtime_ns}"
        except OSError:
            return ""

    def get_stats(self) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "files_tracked": len(self._file_hashes),
            "pending_changes": len(self._changes),
            "poll_interval": self._poll_interval,
        }
