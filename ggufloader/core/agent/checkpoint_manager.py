"""
CheckpointManager - Auto-save file state before agent edits with undo.

Pattern from: Aider's .gguf-undo directory + Git stash.
Every file edit by the agent is automatically backed up so the user
can undo any or all changes. Checkpoints are stored in a hidden
directory alongside the workspace.

Features:
- Automatic backup before write/edit operations
- Undo individual files or full agent session
- Checkpoint history with timestamps
- Auto-cleanup of old checkpoints (keep last N sessions)
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Checkpoint directory name
CHECKPOINT_DIR = ".gguf-undo"
MAX_CHECKPOINTS = 20  # keep last N checkpoint sets


class Checkpoint:
    """A single file backup within a checkpoint set."""

    def __init__(self, relative_path: str, original_content: bytes,
                 checksum: str, timestamp: float) -> None:
        self.relative_path = relative_path
        self.original_content = original_content
        self.checksum = checksum
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.relative_path,
            "checksum": self.checksum,
            "timestamp": self.timestamp,
            "size": len(self.original_content),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], content_dir: Path) -> "Checkpoint":
        content_file = content_dir / data["checksum"]
        content = content_file.read_bytes() if content_file.exists() else b""
        return cls(
            relative_path=data["path"],
            original_content=content,
            checksum=data["checksum"],
            timestamp=data.get("timestamp", 0),
        )


class CheckpointSet:
    """A collection of file backups from a single agent operation."""

    def __init__(self, session_id: str, description: str = "") -> None:
        self.session_id = session_id
        self.description = description
        self.timestamp = time.time()
        self.checkpoints: List[Checkpoint] = []

    def add(self, checkpoint: Checkpoint) -> None:
        self.checkpoints.append(checkpoint)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "description": self.description,
            "timestamp": self.timestamp,
            "files": [c.to_dict() for c in self.checkpoints],
        }


class CheckpointManager:
    """Manages file checkpoints for undo support.

    Usage:
        mgr = CheckpointManager(workspace_path)

        # Before an agent edit
        mgr.backup("write_file", {"path": "foo.py", "content": "..."})

        # After the edit, if user wants to undo
        mgr.undo_last()

        # Or undo all changes from a session
        mgr.undo_session(session_id)
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._checkpoint_dir = workspace / CHECKPOINT_DIR
        self._content_dir = self._checkpoint_dir / "content"
        self._sessions_file = self._checkpoint_dir / "sessions.json"
        self._sessions: List[Dict[str, Any]] = []
        self._current_session_id: Optional[str] = None
        self._current_set: Optional[CheckpointSet] = None
        self._ensure_dirs()
        self._load_sessions()

    def _ensure_dirs(self) -> None:
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._content_dir.mkdir(parents=True, exist_ok=True)

    def _load_sessions(self) -> None:
        if self._sessions_file.exists():
            try:
                self._sessions = json.loads(
                    self._sessions_file.read_text(encoding="utf-8"))
            except Exception:
                self._sessions = []

    def _save_sessions(self) -> None:
        try:
            self._sessions_file.write_text(
                json.dumps(self._sessions, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to save checkpoint sessions: %s", e)

    def start_session(self, session_id: str, description: str = "") -> None:
        """Begin a new checkpoint session (typically at agent start)."""
        self._current_session_id = session_id
        self._current_set = CheckpointSet(session_id, description)

    def backup(self, tool_name: str, params: Dict[str, Any]) -> Optional[str]:
        """Backup a file before modification.

        Args:
            tool_name: The tool being executed (write_file, edit_file, etc.)
            params: Tool parameters

        Returns:
            Checkpoint ID if backup was created, None if not applicable.
        """
        if tool_name not in ("write_file", "edit_file", "run_command", "git"):
            return None

        path_str = params.get("path", "")
        if not path_str:
            return None

        filepath = self.workspace / path_str
        if not filepath.exists():
            return None  # new file, no backup needed

        try:
            content = filepath.read_bytes()
            checksum = hashlib.sha256(content).hexdigest()[:16]

            # Store content by checksum (dedup)
            content_file = self._content_dir / checksum
            if not content_file.exists():
                content_file.write_bytes(content)

            checkpoint = Checkpoint(
                relative_path=path_str,
                original_content=content,
                checksum=checksum,
                timestamp=time.time(),
            )

            if self._current_set is not None:
                self._current_set.add(checkpoint)

            return checksum

        except Exception as e:
            logger.warning("Backup failed for %s: %s", path_str, e)
            return None

    def end_session(self) -> Optional[str]:
        """Finalize the current checkpoint session.

        Returns:
            Session ID if checkpoints were saved, None otherwise.
        """
        if self._current_set is None or not self._current_set.checkpoints:
            self._current_set = None
            return None

        session_data = self._current_set.to_dict()
        self._sessions.append(session_data)

        # Cleanup old sessions
        if len(self._sessions) > MAX_CHECKPOINTS:
            old_sessions = self._sessions[:len(self._sessions) - MAX_CHECKPOINTS]
            for old in old_sessions:
                self._cleanup_session_files(old)
            self._sessions = self._sessions[-MAX_CHECKPOINTS:]

        self._save_sessions()
        session_id = self._current_session_id
        self._current_set = None
        self._current_session_id = None
        return session_id

    def undo_last(self) -> List[str]:
        """Undo the most recent checkpoint set.

        Returns:
            List of restored file paths.
        """
        if not self._sessions:
            return []

        last_session = self._sessions[-1]
        return self._restore_session(last_session)

    def undo_session(self, session_id: str) -> List[str]:
        """Undo all checkpoints from a specific session.

        Returns:
            List of restored file paths.
        """
        for session in self._sessions:
            if session.get("session_id") == session_id:
                return self._restore_session(session)
        return []

    def undo_file(self, filepath: str) -> bool:
        """Undo the most recent backup of a specific file.

        Returns:
            True if the file was restored, False otherwise.
        """
        for session in reversed(self._sessions):
            for file_data in session.get("files", []):
                if file_data.get("path") == filepath:
                    checkpoint = Checkpoint.from_dict(file_data, self._content_dir)
                    if checkpoint.original_content:
                        target = self.workspace / filepath
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(checkpoint.original_content)
                        logger.info("Restored %s from checkpoint", filepath)
                        return True
        return False

    def _restore_session(self, session: Dict[str, Any]) -> List[str]:
        """Restore all files from a checkpoint session."""
        restored = []
        for file_data in session.get("files", []):
            checkpoint = Checkpoint.from_dict(file_data, self._content_dir)
            if checkpoint.original_content:
                target = self.workspace / checkpoint.relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(checkpoint.original_content)
                restored.append(checkpoint.relative_path)
                logger.info("Restored %s from checkpoint", checkpoint.relative_path)
        return restored

    def _cleanup_session_files(self, session: Dict[str, Any]) -> None:
        """Remove content files that are no longer referenced."""
        # Collect all checksums still in use
        used_checksums = set()
        for s in self._sessions:
            if s is session:
                continue
            for f in s.get("files", []):
                used_checksums.add(f.get("checksum", ""))

        # Remove unreferenced content files
        for file_data in session.get("files", []):
            checksum = file_data.get("checksum", "")
            if checksum and checksum not in used_checksums:
                content_file = self._content_dir / checksum
                if content_file.exists():
                    try:
                        content_file.unlink()
                    except OSError:
                        pass

    def get_history(self) -> List[Dict[str, Any]]:
        """Return checkpoint history for display."""
        return [
            {
                "session_id": s.get("session_id", ""),
                "description": s.get("description", ""),
                "timestamp": s.get("timestamp", 0),
                "file_count": len(s.get("files", [])),
                "files": [f.get("path", "") for f in s.get("files", [])],
            }
            for s in reversed(self._sessions)
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Return checkpoint statistics."""
        total_files = sum(len(s.get("files", [])) for s in self._sessions)
        total_size = 0
        for s in self._sessions:
            for f in s.get("files", []):
                total_size += f.get("size", 0)
        return {
            "sessions": len(self._sessions),
            "total_files_backed_up": total_files,
            "total_size_bytes": total_size,
            "current_session": self._current_session_id,
        }
