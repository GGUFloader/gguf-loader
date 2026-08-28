"""
AutoCommit - Automatic git commits after agent file edits.

Pattern from: Aider's auto-commit system.
Every file change made by the agent is automatically committed with
a descriptive message. Users can review, revert, or disable auto-commits.

Features:
- Auto-commit after write_file / edit_file operations
- Smart commit messages generated from file changes
- Stash/unstash support for clean undo
- Configurable: enable/disable per session
- Commit history tracking
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AutoCommit:
    """Manages automatic git commits after agent file edits.

    Usage:
        ac = AutoCommit(workspace_path)
        ac.enable()

        # After agent edits files
        ac.commit_after_edit(
            files_changed=["foo.py", "bar.py"],
            description="Added error handling",
        )

        # Undo all auto-commits from this session
        ac.undo_session_commits()
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._enabled = False
        self._commits: List[Dict[str, Any]] = []
        self._session_commits: List[str] = []  # commit hashes for current session
        self._auto_stage = True  # stage all changes before commit

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def is_git_repo(self) -> bool:
        """Check if the workspace is a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def get_changed_files(self) -> List[str]:
        """Return list of changed (unstaged + staged) files."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            files = []
            for line in result.stdout.strip().splitlines():
                if len(line) > 3:
                    files.append(line[3:].strip())
            return files
        except Exception:
            return []

    def commit_after_edit(
        self,
        files_changed: List[str] = None,
        description: str = "",
    ) -> Optional[str]:
        """Create an automatic commit after agent edits.

        Args:
            files_changed: List of file paths that were modified
            description: Human-readable description of the change

        Returns:
            Commit hash if successful, None otherwise.
        """
        if not self._enabled or not self.is_git_repo():
            return None

        if not self.has_changes():
            return None

        try:
            # Stage all changes
            if self._auto_stage:
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=str(self.workspace),
                    capture_output=True,
                    timeout=10,
                )

            # Generate commit message
            if not description:
                description = self._generate_message(files_changed)

            # Create commit
            result = subprocess.run(
                ["git", "commit", "-m", description],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Get commit hash
                hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                commit_hash = hash_result.stdout.strip()[:8]

                commit_data = {
                    "hash": commit_hash,
                    "message": description,
                    "files": files_changed or [],
                    "timestamp": time.time(),
                }
                self._commits.append(commit_data)
                self._session_commits.append(commit_hash)

                logger.info("Auto-commit: %s — %s", commit_hash, description)
                return commit_hash

            logger.warning("Auto-commit failed: %s", result.stderr)
            return None

        except Exception as e:
            logger.error("Auto-commit error: %s", e)
            return None

    def undo_session_commits(self) -> int:
        """Undo all auto-commits from the current session.

        Uses git reset --soft to uncommit but keep changes.

        Returns:
            Number of commits undone.
        """
        if not self._session_commits or not self.is_git_repo():
            return 0

        count = len(self._session_commits)

        try:
            # Reset to before the first auto-commit
            # Find the parent of the first auto-commit
            first_hash = self._session_commits[0]
            result = subprocess.run(
                ["git", "rev-parse", f"{first_hash}^"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                parent = result.stdout.strip()
                subprocess.run(
                    ["git", "reset", "--soft", parent],
                    cwd=str(self.workspace),
                    capture_output=True,
                    timeout=10,
                )
                logger.info("Undid %d auto-commits", count)
            else:
                # Fallback: reset one by one
                for _ in range(count):
                    subprocess.run(
                        ["git", "reset", "--soft", "HEAD~1"],
                        cwd=str(self.workspace),
                        capture_output=True,
                        timeout=10,
                    )

            self._session_commits.clear()
            return count

        except Exception as e:
            logger.error("Undo commits failed: %s", e)
            return 0

    def get_diff(self, commit_hash: str = "HEAD") -> str:
        """Get the diff for a specific commit or working tree."""
        try:
            result = subprocess.run(
                ["git", "diff", commit_hash, "--stat"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout
        except Exception:
            return ""

    def get_log(self, count: int = 10) -> List[Dict[str, str]]:
        """Get recent commit log."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{count}", "--format=%h|%s|%ai"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            entries = []
            for line in result.stdout.strip().splitlines():
                parts = line.split("|", 2)
                if len(parts) >= 2:
                    entries.append({
                        "hash": parts[0],
                        "message": parts[1],
                        "date": parts[2] if len(parts) > 2 else "",
                    })
            return entries
        except Exception:
            return []

    def _generate_message(self, files_changed: List[str] = None) -> str:
        """Generate a descriptive commit message from the changes."""
        if files_changed:
            # Group by extension
            by_ext: Dict[str, List[str]] = {}
            for f in files_changed:
                ext = Path(f).suffix or "(no ext)"
                by_ext.setdefault(ext, []).append(Path(f).name)

            parts = []
            for ext, names in by_ext.items():
                if len(names) == 1:
                    parts.append(f"Update {names[0]}")
                else:
                    parts.append(f"Update {len(names)} {ext} files")

            return "agent: " + "; ".join(parts[:3])
        return "agent: Update files"

    def get_stats(self) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "total_commits": len(self._commits),
            "session_commits": len(self._session_commits),
            "is_git_repo": self.is_git_repo(),
            "has_changes": self.has_changes() if self._enabled else False,
        }
