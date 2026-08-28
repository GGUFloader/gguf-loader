"""
RateLimiter - Rate limiting for LLM calls and tool execution.

Pattern from: API rate limiting best practices + OpenHands rate guard.
Prevents overwhelming the LLM or system by:
- Limiting requests per time window
- Token bucket algorithm for burst tolerance
- Separate limits for LLM calls vs tool calls
- Configurable per-model limits
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket rate limiter.

    Allows burst up to bucket capacity, then refills at a steady rate.
    """

    def __init__(self, capacity: int, refill_rate: float) -> None:
        """Initialize token bucket.

        Args:
            capacity: Maximum tokens in the bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def wait(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """Wait until tokens are available. Returns True if acquired."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.consume(tokens):
                return True
            # Calculate wait time
            with self._lock:
                deficit = tokens - self._tokens
                wait_time = deficit / self.refill_rate if self.refill_rate > 0 else 1.0
            time.sleep(min(wait_time, 0.5))
        return False

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self.capacity,
            self._tokens + elapsed * self.refill_rate,
        )
        self._last_refill = now

    @property
    def available(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens


class RateLimiter:
    """Rate limiter for LLM calls and tool execution.

    Usage:
        limiter = RateLimiter(
            llm_rpm=30,      # 30 LLM requests per minute
            tool_rpm=100,    # 100 tool calls per minute
            llm_tpm=100000,  # 100k tokens per minute
        )

        # Before LLM call
        if limiter.allow_llm():
            response = llm(prompt)
        else:
            wait_seconds = limiter.wait_time_llm()
    """

    def __init__(
        self,
        llm_rpm: int = 30,       # requests per minute
        tool_rpm: int = 100,      # tool calls per minute
        llm_tpm: int = 100000,    # tokens per minute
        burst: int = 5,           # burst allowance
    ) -> None:
        # LLM request limiter
        self._llm_bucket = TokenBucket(
            capacity=burst,
            refill_rate=llm_rpm / 60.0,
        )

        # Tool call limiter
        self._tool_bucket = TokenBucket(
            capacity=burst * 5,
            refill_rate=tool_rpm / 60.0,
        )

        # Token budget limiter
        self._token_bucket = TokenBucket(
            capacity=llm_tpm,
            refill_rate=llm_tpm / 60.0,
        )

        # Stats
        self._llm_requests = 0
        self._llm_rejected = 0
        self._tool_requests = 0
        self._tool_rejected = 0
        self._tokens_used = 0

    def allow_llm(self) -> bool:
        """Check if an LLM request is allowed."""
        self._llm_requests += 1
        if self._llm_bucket.consume():
            return True
        self._llm_rejected += 1
        return False

    def wait_llm(self, timeout: float = 30.0) -> bool:
        """Wait for LLM rate limit to allow a request."""
        self._llm_requests += 1
        if self._llm_bucket.wait(timeout=timeout):
            return True
        self._llm_rejected += 1
        return False

    def allow_tool(self) -> bool:
        """Check if a tool call is allowed."""
        self._tool_requests += 1
        if self._tool_bucket.consume():
            return True
        self._tool_rejected += 1
        return False

    def consume_tokens(self, count: int) -> bool:
        """Consume token budget."""
        self._tokens_used += count
        return self._token_bucket.consume(count)

    def wait_time_llm(self) -> float:
        """Estimate seconds until next LLM request is allowed."""
        available = self._llm_bucket.available
        if available >= 1:
            return 0
        deficit = 1 - available
        rate = self._llm_bucket.refill_rate
        return deficit / rate if rate > 0 else 0

    def wait_time_tool(self) -> float:
        """Estimate seconds until next tool call is allowed."""
        available = self._tool_bucket.available
        if available >= 1:
            return 0
        deficit = 1 - available
        rate = self._tool_bucket.refill_rate
        return deficit / rate if rate > 0 else 0

    def get_stats(self) -> Dict[str, int]:
        return {
            "llm_requests": self._llm_requests,
            "llm_rejected": self._llm_rejected,
            "tool_requests": self._tool_requests,
            "tool_rejected": self._tool_rejected,
            "tokens_used": self._tokens_used,
            "llm_available": int(self._llm_bucket.available),
            "tool_available": int(self._tool_bucket.available),
        }

    def reset(self) -> None:
        self._llm_requests = 0
        self._llm_rejected = 0
        self._tool_requests = 0
        self._tool_rejected = 0
        self._tokens_used = 0
