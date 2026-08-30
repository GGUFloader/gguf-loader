"""
AdvancedSearch - Regex, cross-session, and semantic search.

Features:
- Regex search across all sessions
- Cross-session code search (search tool results)
- Saved search queries
- Search history
- Result ranking by relevance
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SearchQuery:
    """A saved search query."""

    def __init__(
        self,
        id: str,
        name: str,
        pattern: str,
        search_type: str = "text",  # text, regex, code
        case_sensitive: bool = False,
        scope: str = "all",  # all, sessions, code
        created_at: float = 0.0,
    ) -> None:
        self.id = id
        self.name = name
        self.pattern = pattern
        self.search_type = search_type
        self.case_sensitive = case_sensitive
        self.scope = scope
        self.created_at = created_at or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "pattern": self.pattern,
            "search_type": self.search_type,
            "case_sensitive": self.case_sensitive,
            "scope": self.scope,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchQuery":
        return cls(**{k: v for k, v in data.items() if k in cls.__init__.__code__.co_varnames})


class SearchResult:
    """A single search result."""

    def __init__(
        self,
        session_id: str,
        message_index: int,
        role: str,
        content: str,
        match_text: str,
        match_start: int,
        match_end: int,
        score: float = 1.0,
    ) -> None:
        self.session_id = session_id
        self.message_index = message_index
        self.role = role
        self.content = content
        self.match_text = match_text
        self.match_start = match_start
        self.match_end = match_end
        self.score = score

    def to_dict(self) -> Dict[str, Any]:
        # Show context around match
        start = max(0, self.match_start - 50)
        end = min(len(self.content), self.match_end + 50)
        context_before = self.content[start:self.match_start]
        context_after = self.content[self.match_end:end]

        return {
            "session_id": self.session_id,
            "message_index": self.message_index,
            "role": self.role,
            "match": self.match_text,
            "context": f"...{context_before}[{self.match_text}]{context_after}...",
            "score": self.score,
        }


class AdvancedSearch:
    """Advanced search across sessions and code."""

    def __init__(self, workspace: Optional[Path] = None) -> None:
        self.workspace = workspace or Path.home() / ".ggufloader"
        self._queries_dir = self.workspace / "search_queries"
        self._queries_dir.mkdir(parents=True, exist_ok=True)
        self._history: List[Dict[str, Any]] = []
        self._queries: Dict[str, SearchQuery] = {}
        self._load_queries()

    def search(
        self,
        pattern: str,
        *,
        search_type: str = "text",
        case_sensitive: bool = False,
        scope: str = "all",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search across all sessions.

        Args:
            pattern: search pattern (text, regex, or code pattern)
            search_type: 'text', 'regex', or 'code'
            case_sensitive: whether to match case
            scope: 'all', 'sessions', or 'code'
            limit: max results

        Returns:
            List of search result dicts
        """
        # Record in history
        self._add_history(pattern, search_type, scope)

        results: List[SearchResult] = []

        try:
            from ggufloader.config import get_paths
            from ggufloader.core.sessions.store import SessionStore
            store = SessionStore(get_paths()["chats"])
            sessions = store.list_sessions()

            for session in sessions:
                full = store.load(session["id"])
                if not full:
                    continue
                messages = full.get("messages", [])
                for i, msg in enumerate(messages):
                    content = msg.get("content", "")
                    role = msg.get("role", "")

                    # Filter by scope
                    if scope == "code" and role != "tool":
                        # For code search, also check if content looks like code
                        if not any(kw in content for kw in ("def ", "class ", "function ", "import ", "const ", "let ", "var ", "```")):
                            continue

                    matches = self._find_matches(content, pattern, search_type, case_sensitive)
                    for match_start, match_end, match_text in matches:
                        score = self._score_result(match_text, content, role)
                        results.append(SearchResult(
                            session_id=session["id"],
                            message_index=i,
                            role=role,
                            content=content,
                            match_text=match_text,
                            match_start=match_start,
                            match_end=match_end,
                            score=score,
                        ))

        except Exception as e:
            logger.error("Search failed: %s", e)

        # Sort by score and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return [r.to_dict() for r in results[:limit]]

    def save_query(self, name: str, pattern: str, search_type: str = "text",
                   case_sensitive: bool = False, scope: str = "all") -> SearchQuery:
        """Save a search query for reuse."""
        import hashlib
        qid = hashlib.sha256(f"{name}_{time.time()}".encode()).hexdigest()[:8]
        query = SearchQuery(
            id=qid, name=name, pattern=pattern,
            search_type=search_type, case_sensitive=case_sensitive,
            scope=scope,
        )
        self._queries[qid] = query
        self._save_queries()
        return query

    def list_queries(self) -> List[Dict[str, Any]]:
        """List all saved queries."""
        return [q.to_dict() for q in sorted(self._queries.values(), key=lambda q: q.created_at, reverse=True)]

    def delete_query(self, query_id: str) -> bool:
        """Delete a saved query."""
        if query_id in self._queries:
            del self._queries[query_id]
            self._save_queries()
            return True
        return False

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent search history."""
        return self._history[-limit:]

    def clear_history(self) -> None:
        self._history.clear()

    def _find_matches(self, text: str, pattern: str, search_type: str, case_sensitive: bool) -> List[tuple]:
        """Find all matches in text. Returns [(start, end, match_text), ...]"""
        flags = 0 if case_sensitive else re.IGNORECASE
        matches = []

        if search_type == "regex":
            try:
                for m in re.finditer(pattern, text, flags):
                    matches.append((m.start(), m.end(), m.group()))
            except re.error:
                # Invalid regex, fall back to literal search
                search_type = "text"

        if search_type == "text":
            flags_text = 0 if case_sensitive else re.IGNORECASE
            try:
                for m in re.finditer(re.escape(pattern), text, flags_text):
                    matches.append((m.start(), m.end(), m.group()))
            except re.error:
                pass

        if search_type == "code":
            # Code search: match the pattern as a substring
            flags_text = 0 if case_sensitive else re.IGNORECASE
            try:
                for m in re.finditer(re.escape(pattern), text, flags_text):
                    matches.append((m.start(), m.end(), m.group()))
            except re.error:
                pass

        return matches

    def _score_result(self, match_text: str, full_text: str, role: str) -> float:
        """Score a search result by relevance."""
        score = 1.0
        # Exact match gets higher score
        if match_text.lower() == full_text.lower():
            score += 2.0
        # Match at start of content
        if full_text.lower().startswith(match_text.lower()):
            score += 0.5
        # Prefer assistant messages (more likely to have useful content)
        if role == "assistant":
            score += 0.3
        # Prefer shorter match text (more specific)
        if len(match_text) < 20:
            score += 0.2
        return score

    def _add_history(self, pattern: str, search_type: str, scope: str) -> None:
        entry = {
            "pattern": pattern,
            "search_type": search_type,
            "scope": scope,
            "timestamp": time.time(),
        }
        self._history.append(entry)
        if len(self._history) > 100:
            self._history = self._history[-100:]

    def _load_queries(self) -> None:
        for f in self._queries_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                q = SearchQuery.from_dict(data)
                self._queries[q.id] = q
            except Exception:
                continue

    def _save_queries(self) -> None:
        for qid, q in self._queries.items():
            path = self._queries_dir / f"{qid}.json"
            path.write_text(json.dumps(q.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
