"""
KnowledgeBase - Store and retrieve project-specific insights.

Pattern from: Aider's repo-map + ChatGPT's custom instructions.
A structured knowledge store that accumulates project-specific
knowledge over time:

1. File-level knowledge (what each file does)
2. Pattern knowledge (common patterns in this codebase)
3. Domain knowledge (business rules, API contracts)
4. Learned corrections (what the agent got wrong before)

The knowledge base is queried before each agent step to provide
context that improves decision-making.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Knowledge categories
CATEGORY_FILE = "file"         # What a specific file does
CATEGORY_PATTERN = "pattern"   # Code patterns in this project
CATEGORY_DOMAIN = "domain"     # Business rules, API contracts
CATEGORY_CORRECTION = "correction"  # Things the agent got wrong
CATEGORY_CONVENTION = "convention"  # Coding conventions


class KnowledgeEntry:
    """A single knowledge entry."""

    def __init__(self, category: str, key: str, value: str,
                 source: str = "agent", confidence: float = 1.0,
                 tags: List[str] = None) -> None:
        self.category = category
        self.key = key
        self.value = value
        self.source = source
        self.confidence = confidence
        self.tags = tags or []
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.access_count = 0

    def access(self) -> None:
        self.last_accessed = time.time()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "tags": self.tags,
            "created_at": self.created_at,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeEntry":
        entry = cls(
            category=data.get("category", ""),
            key=data.get("key", ""),
            value=data.get("value", ""),
            source=data.get("source", "agent"),
            confidence=data.get("confidence", 1.0),
            tags=data.get("tags", []),
        )
        entry.created_at = data.get("created_at", time.time())
        entry.access_count = data.get("access_count", 0)
        return entry


class KnowledgeBase:
    """Project-specific knowledge store.

    Usage:
        kb = KnowledgeBase(workspace_path)

        # Store knowledge
        kb.store("file", "src/auth.py", "Handles user authentication with JWT tokens")
        kb.store("pattern", "error_handling", "All API endpoints use try/except with logging")
        kb.store("correction", "no_orm", "This project uses raw SQL, not an ORM")

        # Query knowledge
        entries = kb.query("authentication")
        context = kb.get_context_for_prompt()

        # Auto-generate from workspace scan
        kb.auto_populate()
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._kb_file = workspace / ".ggufloader-knowledge.json"
        self._entries: List[KnowledgeEntry] = []
        self._load()

    def _load(self) -> None:
        if not self._kb_file.exists():
            return
        try:
            data = json.loads(self._kb_file.read_text(encoding="utf-8"))
            self._entries = [KnowledgeEntry.from_dict(e) for e in data.get("entries", [])]
        except Exception as e:
            logger.warning("Failed to load knowledge base: %s", e)
            self._entries = []

    def _save(self) -> None:
        try:
            data = {
                "version": 1,
                "entries": [e.to_dict() for e in self._entries],
            }
            self._kb_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to save knowledge base: %s", e)

    def store(self, category: str, key: str, value: str,
              source: str = "agent", confidence: float = 1.0,
              tags: List[str] = None) -> None:
        """Store a knowledge entry. Updates if key already exists."""
        # Check for existing entry
        for entry in self._entries:
            if entry.category == category and entry.key.lower() == key.lower():
                # Update if new value is more confident or different
                if confidence >= entry.confidence or value != entry.value:
                    entry.value = value
                    entry.confidence = confidence
                    entry.source = source
                    if tags:
                        entry.tags = tags
                entry.access()
                self._save()
                return

        entry = KnowledgeEntry(category, key, value, source, confidence, tags)
        self._entries.append(entry)
        self._save()

    def query(self, text: str, category: str = None,
              limit: int = 20) -> List[KnowledgeEntry]:
        """Search knowledge by text match."""
        text_lower = text.lower()
        results = []
        for entry in self._entries:
            if category and entry.category != category:
                continue
            if (text_lower in entry.key.lower() or
                    text_lower in entry.value.lower() or
                    any(text_lower in tag.lower() for tag in entry.tags)):
                entry.access()
                results.append(entry)
                if len(results) >= limit:
                    break
        if results:
            self._save()
        return results

    def get_by_category(self, category: str) -> List[KnowledgeEntry]:
        """Get all entries in a category."""
        return [e for e in self._entries if e.category == category]

    def get_file_knowledge(self, filepath: str) -> List[KnowledgeEntry]:
        """Get knowledge about a specific file."""
        return [e for e in self._entries
                if e.category == CATEGORY_FILE and e.key == filepath]

    def get_corrections(self) -> List[KnowledgeEntry]:
        """Get all learned corrections."""
        return self.get_by_category(CATEGORY_CORRECTION)

    def get_context_for_prompt(self, max_chars: int = 3000) -> str:
        """Format knowledge as context for the system prompt."""
        if not self._entries:
            return ""

        lines = ["# Project Knowledge Base\n"]

        # Group by category
        by_category: Dict[str, List[KnowledgeEntry]] = {}
        for entry in self._entries:
            by_category.setdefault(entry.category, []).append(entry)

        category_labels = {
            CATEGORY_FILE: "## File Descriptions",
            CATEGORY_PATTERN: "## Code Patterns",
            CATEGORY_DOMAIN: "## Domain Knowledge",
            CATEGORY_CORRECTION: "## Corrections (avoid repeating these)",
            CATEGORY_CONVENTION: "## Conventions",
        }

        total_chars = 0
        priority_order = [CATEGORY_CORRECTION, CATEGORY_FILE, CATEGORY_PATTERN,
                         CATEGORY_DOMAIN, CATEGORY_CONVENTION]

        for cat in priority_order:
            entries = by_category.get(cat, [])
            if not entries:
                continue
            label = category_labels.get(cat, f"## {cat.title()}")
            lines.append(label)
            for entry in entries[:15]:
                line = f"- {entry.key}: {entry.value}"
                total_chars += len(line)
                if total_chars > max_chars:
                    break
                lines.append(line)
            if total_chars > max_chars:
                break

        return "\n".join(lines)

    def auto_populate(self) -> int:
        """Auto-populate knowledge from workspace scan.

        Returns number of entries created.
        """
        count = 0

        # Scan Python files for docstrings and function descriptions
        for py_file in self.workspace.rglob("*.py"):
            if any(d in str(py_file) for d in (".git", "__pycache__", "node_modules", ".venv")):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")[:5000]
            except (OSError, UnicodeDecodeError):
                continue

            rel = str(py_file.relative_to(self.workspace))

            # Extract module docstring
            doc_match = __import__("re").search(r'"""(.*?)"""', content, __import__("re").DOTALL)
            if doc_match:
                doc = doc_match.group(1).strip().split("\n")[0][:200]
                self.store(CATEGORY_FILE, rel, doc, source="auto_scan", confidence=0.8)
                count += 1

            # Extract class definitions
            for match in __import__("re").finditer(r"class\s+(\w+).*?:", content):
                class_name = match.group(1)
                self.store(CATEGORY_FILE, f"{rel}::{class_name}",
                          f"Class {class_name}", source="auto_scan", confidence=0.5)
                count += 1

        # Detect common patterns
        py_files = list(self.workspace.rglob("*.py"))[:20]
        if py_files:
            all_content = ""
            for f in py_files[:10]:
                try:
                    all_content += f.read_text(encoding="utf-8", errors="ignore")[:3000]
                except (OSError, UnicodeDecodeError):
                    continue

            if "logging" in all_content:
                self.store(CATEGORY_PATTERN, "logging", "Uses Python logging module", source="auto_scan")
                count += 1
            if "async def" in all_content:
                self.store(CATEGORY_PATTERN, "async", "Uses async/await patterns", source="auto_scan")
                count += 1
            if "dataclass" in all_content:
                self.store(CATEGORY_PATTERN, "dataclasses", "Uses Python dataclasses", source="auto_scan")
                count += 1
            if "pydantic" in all_content.lower():
                self.store(CATEGORY_PATTERN, "pydantic", "Uses Pydantic for data validation", source="auto_scan")
                count += 1

        logger.info("Auto-populated %d knowledge entries", count)
        return count

    def record_correction(self, key: str, correction: str) -> None:
        """Record a correction from user feedback."""
        self.store(CATEGORY_CORRECTION, key, correction, source="user", confidence=1.0)

    def count(self) -> int:
        return len(self._entries)

    def get_stats(self) -> Dict[str, Any]:
        by_cat = {}
        for e in self._entries:
            by_cat[e.category] = by_cat.get(e.category, 0) + 1
        return {
            "total": len(self._entries),
            "by_category": by_cat,
        }
