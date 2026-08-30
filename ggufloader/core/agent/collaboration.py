"""
Collaboration - Real-time collaboration for agent sessions.

Features:
- WebSocket-based presence indicators
- Shared cursors showing where others are working
- Collaborative session editing
- User identity and avatar management
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class Collaborator:
    """A connected collaborator."""
    id: str
    name: str
    color: str
    cursor_position: Optional[Dict[str, Any]] = None
    last_active: float = 0.0
    is_typing: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "cursor_position": self.cursor_position,
            "last_active": self.last_active,
            "is_typing": self.is_typing,
        }


@dataclass
class CollaborativeSession:
    """A session with collaborative features."""
    id: str
    session_id: str
    collaborators: Dict[str, Collaborator] = field(default_factory=dict)
    created_at: float = 0.0
    last_event: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "collaborators": [c.to_dict() for c in self.collaborators.values()],
            "collaborator_count": len(self.collaborators),
            "created_at": self.created_at,
            "last_event": self.last_event,
        }


# Predefined collaborator colors
COLLABORATOR_COLORS = [
    "#e8a33d", "#38bdf8", "#34d399", "#f87171", "#a78bfa",
    "#fb923c", "#22d3ee", "#4ade80", "#f472b6", "#818cf8",
]


class CollaborationManager:
    """Manage collaborative sessions and presence."""

    def __init__(self) -> None:
        self._sessions: Dict[str, CollaborativeSession] = {}
        self._user_sessions: Dict[str, Set[str]] = {}  # user_id -> set of session_ids
        self._color_index = 0

    def join_session(self, session_id: str, user_id: str, user_name: str) -> Collaborator:
        """Join a collaborative session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = CollaborativeSession(
                id=str(uuid.uuid4()),
                session_id=session_id,
                created_at=time.time(),
            )

        session = self._sessions[session_id]

        # Assign color
        color = COLLABORATOR_COLORS[self._color_index % len(COLLABORATOR_COLORS)]
        self._color_index += 1

        collaborator = Collaborator(
            id=user_id,
            name=user_name,
            color=color,
            last_active=time.time(),
        )
        session.collaborators[user_id] = collaborator
        session.last_event = time.time()

        # Track user sessions
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = set()
        self._user_sessions[user_id].add(session_id)

        logger.info("User %s joined session %s", user_name, session_id)
        return collaborator

    def leave_session(self, session_id: str, user_id: str) -> None:
        """Leave a collaborative session."""
        session = self._sessions.get(session_id)
        if session and user_id in session.collaborators:
            del session.collaborators[user_id]
            session.last_event = time.time()

        if user_id in self._user_sessions:
            self._user_sessions[user_id].discard(session_id)

    def update_cursor(self, session_id: str, user_id: str, position: Dict[str, Any]) -> None:
        """Update a user's cursor position."""
        session = self._sessions.get(session_id)
        if session and user_id in session.collaborators:
            session.collaborators[user_id].cursor_position = position
            session.collaborators[user_id].last_active = time.time()

    def set_typing(self, session_id: str, user_id: str, is_typing: bool) -> None:
        """Set typing indicator."""
        session = self._sessions.get(session_id)
        if session and user_id in session.collaborators:
            session.collaborators[user_id].is_typing = is_typing
            session.collaborators[user_id].last_active = time.time()

    def broadcast_event(self, session_id: str, event: Dict[str, Any], exclude_user: str = "") -> List[str]:
        """Get list of user IDs to broadcast to (excluding sender)."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        return [uid for uid in session.collaborators if uid != exclude_user]

    def get_session(self, session_id: str) -> Optional[CollaborativeSession]:
        return self._sessions.get(session_id)

    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return {"session_id": session_id, "collaborators": []}
        return session.to_dict()

    def get_user_sessions(self, user_id: str) -> List[str]:
        return list(self._user_sessions.get(user_id, set()))

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all sessions with at least one collaborator."""
        return [
            s.to_dict() for s in self._sessions.values()
            if s.collaborators
        ]

    def cleanup_stale(self, timeout: float = 300.0) -> int:
        """Remove collaborators who haven't been active for timeout seconds."""
        now = time.time()
        removed = 0
        for session in list(self._sessions.values()):
            stale = [
                uid for uid, c in session.collaborators.items()
                if now - c.last_active > timeout
            ]
            for uid in stale:
                del session.collaborators[uid]
                removed += 1
        return removed

    def generate_user_id(self) -> str:
        return f"user_{uuid.uuid4().hex[:8]}"


# Singleton
_collab_manager: Optional[CollaborationManager] = None


def get_collab_manager() -> CollaborationManager:
    global _collab_manager
    if _collab_manager is None:
        _collab_manager = CollaborationManager()
    return _collab_manager
