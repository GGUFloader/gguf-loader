"""ContextCompactor - Trim conversation history to stay within token limits.

Adapted from pydantic-ai-harness compaction capabilities for LangGraph agents.
Summarizes old turns and keeps recent messages intact.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ContextCompactor:
    """Trims conversation history when it approaches the context limit.

    Strategy:
    - Keep the last N messages intact (recent context)
    - Summarize older messages into a single system message
    - Cap total history at max_history_chars
    """

    def __init__(
        self,
        max_history_chars: int = 12000,
        keep_recent: int = 4,
    ) -> None:
        self.max_history_chars = max_history_chars
        self.keep_recent = keep_recent

    def compact(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Return a compacted version of the message history.

        If total character count is under the limit, returns messages unchanged.
        Otherwise, summarizes old messages and keeps recent ones intact.
        """
        if not messages:
            return messages

        total = sum(len(m.get("content", "")) for m in messages)
        if total <= self.max_history_chars:
            return messages

        # Split into old and recent
        if len(messages) <= self.keep_recent:
            return messages  # Too few to compact

        old = messages[: -self.keep_recent]
        recent = messages[-self.keep_recent :]

        # Summarize old messages
        summary = self._summarize(old)

        # Build compacted history
        compacted = [
            {"role": "system", "content": f"[Context summary] {summary}"},
        ]
        compacted.extend(recent)

        return compacted

    def _summarize(self, messages: List[Dict[str, str]]) -> str:
        """Create a compact summary of old messages.

        Extracts key information: user requests, tool results, decisions.
        """
        parts: List[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:150]
            if role == "user":
                parts.append(f"User asked: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            elif role == "tool":
                parts.append(f"Tool result: {content[:80]}")
        return " | ".join(parts) if parts else "(no prior context)"

    def estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Rough token estimate (4 chars per token)."""
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return total_chars // 4
