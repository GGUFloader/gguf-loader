"""
ContextBudget - Token budget tracking and conversation compaction.

Monitors the total token count of the conversation history and
triggers compaction (summarization) when the budget is exceeded.
Prevents context overflow without losing important information.

Pattern from: Pydantic AI Harness SlidingWindowCompaction +
Aider's auto-compaction.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Rough token estimation: ~4 chars per token for English text
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Rough token count estimation."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_message_tokens(message: Dict[str, Any]) -> int:
    """Estimate tokens for a single message dict."""
    content = message.get("content", "")
    if isinstance(content, list):
        # Multimodal messages
        total = 0
        for part in content:
            if isinstance(part, dict):
                total += estimate_tokens(part.get("text", ""))
            else:
                total += estimate_tokens(str(part))
        return total
    return estimate_tokens(str(content))


class ContextBudget:
    """Track token usage and trigger compaction when needed.

    The budget has three thresholds:
    - soft_limit (80%): start warning / preparing for compaction
    - hard_limit (95%): trigger compaction immediately
    - max_limit (100%): drop oldest messages if still over

    Compaction strategies:
    1. Summarize: Replace old messages with a summary
    2. Drop: Remove oldest non-critical messages
    3. Trim: Shorten long tool results
    """

    def __init__(self, total_budget: int = 8192, system_prompt_tokens: int = 500) -> None:
        self.total_budget = total_budget
        self.system_prompt_tokens = system_prompt_tokens
        self.available = total_budget - system_prompt_tokens
        self._used = 0
        self._step_history: List[Dict[str, Any]] = []
        self._compaction_count = 0
        self._on_compact: Optional[Callable[[str], None]] = None

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        return max(0, self.available - self._used)

    @property
    def usage_ratio(self) -> float:
        return self._used / self.available if self.available > 0 else 1.0

    def set_compaction_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for when compaction happens."""
        self._on_compact = callback

    def set_budget(self, total: int, system_tokens: int = 500) -> None:
        """Update the total budget (e.g., after model load reveals n_ctx)."""
        self.total_budget = total
        self.system_prompt_tokens = system_tokens
        self.available = total - system_tokens
        logger.info("Context budget set: %d tokens (system: %d, available: %d)",
                     total, system_tokens, self.available)

    def check_budget(self, history: List[Dict[str, Any]]) -> str:
        """Check if compaction is needed. Returns compaction strategy or 'ok'.

        Strategies:
        - 'ok': within budget
        - 'summarize': old messages can be summarized
        - 'trim': tool results are too long
        - 'drop': must drop oldest messages
        """
        self._used = sum(estimate_message_tokens(m) for m in history)
        ratio = self.usage_ratio

        if ratio < 0.80:
            return "ok"
        elif ratio < 0.95:
            return "summarize"
        elif ratio < 1.0:
            return "trim"
        else:
            return "drop"

    def compact(self, history: List[Dict[str, Any]],
                summarize_fn: Optional[Callable[[str], str]] = None) -> List[Dict[str, Any]]:
        """Compact the conversation history to fit within budget.

        Returns the compacted history (modifies in place too).
        """
        strategy = self.check_budget(history)
        if strategy == "ok":
            return history

        self._compaction_count += 1
        logger.info("Context compaction #%d: strategy=%s, used=%d/%d",
                     self._compaction_count, strategy, self._used, self.available)

        if strategy == "summarize":
            history = self._summarize_compact(history, summarize_fn)
        elif strategy == "trim":
            history = self._trim_compact(history)
        elif strategy == "drop":
            history = self._drop_compact(history)

        # Re-check after compaction
        self._used = sum(estimate_message_tokens(m) for m in history)
        if self._used > self.available and history:
            # Last resort: drop oldest messages until we fit
            while history and self._used > self.available:
                # Never drop the system message (index 0) or the last 2 messages
                if len(history) <= 3:
                    break
                dropped = history.pop(1)  # drop second message (first user msg)
                self._used -= estimate_message_tokens(dropped)

        if self._on_compact:
            self._on_compact(
                f"Context compacted ({strategy}): {self._used} tokens used "
                f"of {self.available} available"
            )

        return history

    def _summarize_compact(self, history: List[Dict[str, Any]],
                           summarize_fn: Optional[Callable[[str], str]] = None,
                           ) -> List[Dict[str, Any]]:
        """Summarize old messages to reduce token count.

        Keeps: system prompt, last 4 messages, and any summary.
        Summarizes everything in between.
        """
        if len(history) <= 5:
            return history

        # Extract messages to summarize (everything except system + last 4)
        old_messages = history[1:-4]  # skip system, keep last 4
        kept = [history[0]] + history[-4:]  # system + last 4

        # Build summary text
        summary_parts = []
        for msg in old_messages:
            role = msg.get("role", "unknown")
            content = str(msg.get("content", ""))[:300]
            if content:
                summary_parts.append(f"{role}: {content}")

        summary_text = "\n".join(summary_parts)

        if summarize_fn:
            summary_text = summarize_fn(summary_text)

        # Insert summary as a system message
        summary_msg = {
            "role": "system",
            "content": f"[Conversation summary — {len(old_messages)} messages condensed]\n{summary_text}"
        }
        return [summary_msg] + kept

    def _trim_compact(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Trim long tool results in messages."""
        for msg in history:
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > 2000:
                msg["content"] = content[:2000] + "\n...(trimmed to fit context)"
        return history

    def _drop_compact(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Drop oldest non-system messages."""
        if len(history) <= 3:
            return history

        # Keep system message + last 3 messages
        dropped_count = len(history) - 4
        if dropped_count > 0 and self._on_compact:
            self._on_compact(f"Dropped {dropped_count} oldest messages to fit context")
        return [history[0]] + history[-3:]

    def get_stats(self) -> Dict[str, Any]:
        """Return budget statistics."""
        return {
            "total_budget": self.total_budget,
            "system_tokens": self.system_prompt_tokens,
            "available": self.available,
            "used": self._used,
            "remaining": self.remaining,
            "usage_pct": round(self.usage_ratio * 100, 1),
            "compactions": self._compaction_count,
        }
