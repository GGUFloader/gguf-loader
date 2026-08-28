"""
ResponseCache - Cache LLM responses based on prompt similarity.

Pattern from: Aider's modelxo + LLM response deduplication.
Caches responses to avoid redundant LLM calls for similar prompts.
Uses:
- Exact match (fast)
- Normalized prefix match (handles minor prompt variations)
- Configurable TTL and size limits

Features:
- LRU eviction when cache is full
- TTL-based expiration
- Cache hit/miss statistics
- Persistent cache (optional JSON file)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _normalize_prompt(prompt: str) -> str:
    """Normalize a prompt for cache matching.

    Strips whitespace variations, normalizes newlines, and
    truncates to the common prefix (first 500 chars).
    """
    normalized = " ".join(prompt.split())  # collapse whitespace
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    # Take first 500 chars as the cache key prefix
    return normalized[:500]


def _prompt_hash(prompt: str) -> str:
    """Compute a fast hash for a prompt."""
    normalized = _normalize_prompt(prompt)
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


class CacheEntry:
    """A single cached response."""

    def __init__(self, prompt_hash: str, response: str, ttl: float = 3600) -> None:
        self.prompt_hash = prompt_hash
        self.response = response
        self.created_at = time.time()
        self.ttl = ttl
        self.hits = 0

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash": self.prompt_hash,
            "response": self.response[:500],  # truncate for storage
            "created_at": self.created_at,
            "hits": self.hits,
        }


class ResponseCache:
    """LRU cache for LLM responses.

    Usage:
        cache = ResponseCache(max_size=100, ttl=3600)

        # Check cache before LLM call
        cached = cache.get(prompt)
        if cached:
            return cached

        # After LLM call, cache the response
        response = llm(prompt)
        cache.set(prompt, response)
    """

    def __init__(self, max_size: int = 100, ttl: float = 3600,
                 persistent: bool = False, workspace: Path = None) -> None:
        self._max_size = max_size
        self._ttl = ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._persistent = persistent
        self._cache_file = (workspace / ".ggufloader-cache.json") if workspace else None

        if persistent and self._cache_file and self._cache_file.exists():
            self._load()

    def get(self, prompt: str) -> Optional[str]:
        """Get a cached response for the prompt."""
        key = _prompt_hash(prompt)

        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            del self._cache[key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        entry.hits += 1
        self._hits += 1
        return entry.response

    def set(self, prompt: str, response: str, ttl: float = None) -> None:
        """Cache a response for the given prompt."""
        key = _prompt_hash(prompt)

        # Remove if exists (to update position)
        if key in self._cache:
            del self._cache[key]

        # Evict oldest if full
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        entry = CacheEntry(key, response, ttl or self._ttl)
        self._cache[key] = entry

        if self._persistent:
            self._save()

    def invalidate(self, prompt: str) -> bool:
        """Remove a cached entry."""
        key = _prompt_hash(prompt)
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0

    @property
    def size(self) -> int:
        return len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate * 100, 1),
            "ttl": self._ttl,
        }

    def _save(self) -> None:
        if not self._cache_file:
            return
        try:
            data = {
                "entries": [e.to_dict() for e in self._cache.values()],
                "stats": {"hits": self._hits, "misses": self._misses},
            }
            self._cache_file.write_text(
                json.dumps(data, indent=2), encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Failed to save cache: %s", e)

    def _load(self) -> None:
        if not self._cache_file or not self._cache_file.exists():
            return
        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            for entry_data in data.get("entries", []):
                entry = CacheEntry(
                    entry_data["hash"],
                    entry_data.get("response", ""),
                )
                entry.hits = entry_data.get("hits", 0)
                if not entry.is_expired:
                    self._cache[entry.prompt_hash] = entry
            stats = data.get("stats", {})
            self._hits = stats.get("hits", 0)
            self._misses = stats.get("misses", 0)
        except Exception as e:
            logger.warning("Failed to load cache: %s", e)
