"""
MemoryPersistence - Save and restore agent working memory across sessions.

Stores structured facts, user preferences, and learned patterns in a
JSON file that survives app restarts. The agent engine reads this on
startup and can append new memories during a session.

Pattern from: Aider's repo-map + ChatGPT's memory feature.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Memory file location
MEMORY_FILENAME = ".ggufloader-memory.json"
MAX_MEMORIES = 200  # cap to prevent unbounded growth
MEMORY_CATEGORIES = ("fact", "preference", "pattern", "correction", "context")


class MemoryEntry:
    """A single memory entry."""

    def __init__(self, category: str, key: str, value: str,
                 source: str = "session", confidence: float = 1.0) -> None:
        self.category = category  # fact, preference, pattern, correction, context
        self.key = key
        self.value = value
        self.source = source
        self.confidence = confidence
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.access_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        entry = cls(
            category=data.get("category", "fact"),
            key=data.get("key", ""),
            value=data.get("value", ""),
            source=data.get("source", "session"),
            confidence=data.get("confidence", 1.0),
        )
        entry.created_at = data.get("created_at", time.time())
        entry.last_accessed = data.get("last_accessed", time.time())
        entry.access_count = data.get("access_count", 0)
        return entry

    def access(self) -> None:
        """Record that this memory was accessed."""
        self.last_accessed = time.time()
        self.access_count += 1


class MemoryPersistence:
    """Persistent memory store for the agent.

    Memories are stored in a JSON file in the workspace root.
    The agent can:
    - remember(key, value, category) — store a new memory
    - recall(query) — search memories by key/value
    - forget(key) — remove a memory
    - get_context() — get all memories as context for the system prompt
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._memory_file = workspace / MEMORY_FILENAME
        self._entries: List[MemoryEntry] = []
        self._load()

    def _load(self) -> None:
        """Load memories from disk."""
        if not self._memory_file.exists():
            return
        try:
            data = json.loads(self._memory_file.read_text(encoding="utf-8"))
            self._entries = [MemoryEntry.from_dict(e) for e in data.get("entries", [])]
            logger.info("Loaded %d memories from %s", len(self._entries), self._memory_file)
        except Exception as e:
            logger.warning("Failed to load memories: %s", e)
            self._entries = []

    def _save(self) -> None:
        """Persist memories to disk."""
        try:
            data = {
                "version": 1,
                "entries": [e.to_dict() for e in self._entries],
            }
            self._memory_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to save memories: %s", e)

    def remember(self, key: str, value: str, category: str = "fact",
                 source: str = "session", confidence: float = 1.0) -> None:
        """Store a new memory. Updates if key already exists."""
        if category not in MEMORY_CATEGORIES:
            category = "fact"

        # Check if key already exists — update instead of duplicate
        for entry in self._entries:
            if entry.key.lower() == key.lower():
                entry.value = value
                entry.category = category
                entry.source = source
                entry.confidence = confidence
                entry.access()
                self._save()
                return

        # Enforce cap
        if len(self._entries) >= MAX_MEMORIES:
            # Remove least-accessed, oldest entries
            self._entries.sort(key=lambda e: (e.access_count, e.created_at))
            self._entries = self._entries[len(self._entries) // 4:]  # drop bottom 25%

        entry = MemoryEntry(category, key, value, source, confidence)
        self._entries.append(entry)
        self._save()

    def recall(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Search memories by key/value match."""
        query_lower = query.lower()
        results = []
        for entry in self._entries:
            if (query_lower in entry.key.lower() or
                    query_lower in entry.value.lower()):
                entry.access()
                results.append(entry)
                if len(results) >= limit:
                    break
        if results:
            self._save()  # persist access counts
        return results

    def forget(self, key: str) -> bool:
        """Remove a memory by key. Returns True if found and removed."""
        for i, entry in enumerate(self._entries):
            if entry.key.lower() == key.lower():
                self._entries.pop(i)
                self._save()
                return True
        return False

    def get_all(self, category: Optional[str] = None) -> List[MemoryEntry]:
        """Get all memories, optionally filtered by category."""
        if category:
            return [e for e in self._entries if e.category == category]
        return list(self._entries)

    def get_context(self, max_chars: int = 2000) -> str:
        """Format memories as context for the system prompt.

        Returns a structured string the model can use to recall
        past interactions and user preferences.
        """
        if not self._entries:
            return ""

        lines = ["# Agent Memory (persisted across sessions)\n"]

        # Group by category
        by_category: Dict[str, List[MemoryEntry]] = {}
        for entry in self._entries:
            by_category.setdefault(entry.category, []).append(entry)

        category_labels = {
            "fact": "## Known Facts",
            "preference": "## User Preferences",
            "pattern": "## Learned Patterns",
            "correction": "## Corrections (avoid repeating these)",
            "context": "## Project Context",
        }

        total_chars = 0
        for cat in MEMORY_CATEGORIES:
            entries = by_category.get(cat, [])
            if not entries:
                continue
            label = category_labels.get(cat, f"## {cat.title()}")
            lines.append(label)
            for entry in entries[:15]:  # cap per category
                line = f"- {entry.key}: {entry.value}"
                total_chars += len(line)
                if total_chars > max_chars:
                    break
                lines.append(line)
            if total_chars > max_chars:
                break

        return "\n".join(lines)

    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        """Clear all memories."""
        self._entries.clear()
        self._save()
