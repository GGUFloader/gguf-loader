"""
SessionBranching - Branch, merge, and visualize session timelines.

Features:
- Branch from any conversation point
- Merge branches back together
- Visual timeline with branch divergences
- Diff between branches
- Undo/redo within a branch
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single message in a branch."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Branch:
    """A conversation branch."""
    id: str
    name: str
    parent_id: Optional[str]  # branch we diverged from
    fork_point: int  # message index where we forked
    messages: List[Message] = field(default_factory=list)
    created_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.messages)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "fork_point": self.fork_point,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Branch":
        return cls(
            id=data["id"],
            name=data["name"],
            parent_id=data.get("parent_id"),
            fork_point=data.get("fork_point", 0),
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            created_at=data.get("created_at", 0),
            metadata=data.get("metadata", {}),
        )


class SessionBranching:
    """Manage branching, merging, and timelines for sessions."""

    def __init__(self, workspace: Optional[Path] = None) -> None:
        self.workspace = workspace or Path.home() / ".ggufloader"
        self._sessions_dir = self.workspace / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._branches: Dict[str, Branch] = {}
        self._active_branch: Optional[str] = None

    @property
    def active_branch(self) -> Optional[Branch]:
        return self._branches.get(self._active_branch) if self._active_branch else None

    def create_session(self, session_id: str) -> Branch:
        """Create a new session with a main branch."""
        branch = Branch(
            id=f"{session_id}_main",
            name="main",
            parent_id=None,
            fork_point=0,
            created_at=time.time(),
        )
        self._branches[branch.id] = branch
        self._active_branch = branch.id
        return branch

    def add_message(self, role: str, content: str, **metadata: Any) -> Optional[Message]:
        """Add a message to the active branch."""
        if not self._active_branch:
            return None
        branch = self._branches[self._active_branch]
        msg = Message(role=role, content=content, timestamp=time.time(), metadata=metadata)
        branch.messages.append(msg)
        return msg

    def fork(self, branch_id: str, message_index: int, name: str = "") -> Optional[Branch]:
        """Fork a branch from a specific message index."""
        source = self._branches.get(branch_id)
        if not source:
            return None
        if message_index < 0 or message_index > len(source.messages):
            return None

        new_id = f"{source.id}_fork_{int(time.time() * 1000)}"
        fork_branch = Branch(
            id=new_id,
            name=name or f"fork@{message_index}",
            parent_id=source.id,
            fork_point=message_index,
            messages=[Message.from_dict(m.to_dict()) for m in source.messages[:message_index]],
            created_at=time.time(),
        )
        self._branches[new_id] = fork_branch
        return fork_branch

    def switch_branch(self, branch_id: str) -> bool:
        """Switch to a different branch."""
        if branch_id in self._branches:
            self._active_branch = branch_id
            return True
        return False

    def merge(self, source_id: str, target_id: str, strategy: str = "append") -> bool:
        """Merge a source branch into a target branch.

        Strategies:
        - 'append': add source-only messages to the end of target
        - 'interleave': merge messages by timestamp
        """
        source = self._branches.get(source_id)
        target = self._branches.get(target_id)
        if not source or not target:
            return False

        # Find messages that are only in the source (after fork point)
        source_msgs = source.messages[source.fork_point:]

        if strategy == "append":
            target.messages.extend(source_msgs)
        elif strategy == "interleave":
            all_msgs = target.messages + source_msgs
            all_msgs.sort(key=lambda m: m.timestamp)
            target.messages = all_msgs

        return True

    def get_timeline(self) -> List[Dict[str, Any]]:
        """Get a visual timeline of all branches."""
        timeline = []
        for branch in self._branches.values():
            timeline.append({
                "id": branch.id,
                "name": branch.name,
                "parent_id": branch.parent_id,
                "fork_point": branch.fork_point,
                "length": branch.length,
                "created_at": branch.created_at,
                "is_active": branch.id == self._active_branch,
            })
        return timeline

    def diff_branches(self, branch_a_id: str, branch_b_id: str) -> Dict[str, Any]:
        """Show differences between two branches."""
        a = self._branches.get(branch_a_id)
        b = self._branches.get(branch_b_id)
        if not a or not b:
            return {"error": "Branch not found"}

        a_roles = [m.role for m in a.messages]
        b_roles = [m.role for m in b.messages]
        a_contents = [m.content[:100] for m in a.messages]
        b_contents = [m.content[:100] for m in b.messages]

        # Find common prefix
        common = 0
        for i in range(min(len(a.messages), len(b.messages))):
            if a.messages[i].content == b.messages[i].content:
                common += 1
            else:
                break

        return {
            "branch_a": {"id": a.id, "name": a.name, "length": a.length},
            "branch_b": {"id": b.id, "name": b.name, "length": b.length},
            "common_prefix": common,
            "a_only_count": a.length - common,
            "b_only_count": b.length - common,
            "a_preview": a_contents[common:common + 3],
            "b_preview": b_contents[common:common + 3],
        }

    def get_branch_messages(self, branch_id: str) -> List[Dict[str, Any]]:
        """Get all messages in a branch."""
        branch = self._branches.get(branch_id)
        if not branch:
            return []
        return [m.to_dict() for m in branch.messages]

    def list_branches(self) -> List[Dict[str, Any]]:
        """List all branches with metadata."""
        return [
            {
                "id": b.id,
                "name": b.name,
                "parent_id": b.parent_id,
                "length": b.length,
                "created_at": b.created_at,
                "is_active": b.id == self._active_branch,
            }
            for b in self._branches.values()
        ]

    def save(self, session_id: str) -> None:
        """Save all branches to disk."""
        path = self._sessions_dir / f"{session_id}_branches.json"
        data = {
            "session_id": session_id,
            "branches": {bid: b.to_dict() for bid, b in self._branches.items()},
            "active_branch": self._active_branch,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load(self, session_id: str) -> bool:
        """Load branches from disk."""
        path = self._sessions_dir / f"{session_id}_branches.json"
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._branches = {
                bid: Branch.from_dict(bdata)
                for bid, bdata in data.get("branches", {}).items()
            }
            self._active_branch = data.get("active_branch")
            return True
        except Exception as e:
            logger.error("Failed to load branches for %s: %s", session_id, e)
            return False
