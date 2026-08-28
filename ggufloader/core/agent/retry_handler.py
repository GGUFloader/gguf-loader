"""
RetryHandler - Exponential backoff retry for LLM and tool failures.

Provides retry logic with:
- Exponential backoff with jitter
- Configurable max retries per operation type
- Separate retry budgets for LLM vs tool failures
- Circuit breaker pattern (stop retrying after N total failures)
- Callback hooks for retry events (UI can show retry status)

Pattern from: OpenHands RetryAgent + Aider's auto-retry.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default retry configurations
LLM_MAX_RETRIES = 3
LLM_BASE_DELAY = 1.0       # seconds
LLM_MAX_DELAY = 30.0       # seconds
LLM_BACKOFF_FACTOR = 2.0

TOOL_MAX_RETRIES = 2
TOOL_BASE_DELAY = 0.5
TOOL_MAX_DELAY = 5.0
TOOL_BACKOFF_FACTOR = 2.0

# Circuit breaker
CIRCUIT_BREAKER_THRESHOLD = 10  # total failures before opening
CIRCUIT_BREAKER_RESET = 60.0   # seconds before half-open


class RetryEvent:
    """Event emitted during retry operations."""

    def __init__(self, operation: str, attempt: int, max_attempts: int,
                 delay: float, error: str, will_retry: bool) -> None:
        self.operation = operation
        self.attempt = attempt
        self.max_attempts = max_attempts
        self.delay = delay
        self.error = error
        self.will_retry = will_retry

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "delay": round(self.delay, 2),
            "error": self.error,
            "will_retry": self.will_retry,
        }


class CircuitBreaker:
    """Circuit breaker to stop retrying after too many failures.

    States:
    - CLOSED: normal operation, failures counted
    - OPEN: too many failures, reject immediately
    - HALF_OPEN: after reset timeout, allow one attempt
    """

    def __init__(self, threshold: int = CIRCUIT_BREAKER_THRESHOLD,
                 reset_timeout: float = CIRCUIT_BREAKER_RESET) -> None:
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = "closed"  # closed | open | half_open

    @property
    def is_open(self) -> bool:
        if self._state == "open":
            if time.time() - self._last_failure_time >= self.reset_timeout:
                self._state = "half_open"
                return False
            return True
        return False

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.threshold:
            self._state = "open"
            logger.warning("Circuit breaker OPEN: %d consecutive failures", self._failure_count)

    @property
    def state(self) -> str:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count


class RetryHandler:
    """Configurable retry handler with exponential backoff.

    Usage:
        handler = RetryHandler()

        # Retry an LLM call
        result = handler.retry_llm(my_llm_call, args=(prompt,))

        # Retry a tool execution
        result = handler.retry_tool(my_tool.execute, kwargs={"params": params})
    """

    def __init__(
        self,
        on_retry: Optional[Callable[[RetryEvent], None]] = None,
        llm_max_retries: int = LLM_MAX_RETRIES,
        tool_max_retries: int = TOOL_MAX_RETRIES,
    ) -> None:
        self.on_retry = on_retry
        self.llm_max_retries = llm_max_retries
        self.tool_max_retries = tool_max_retries
        self._circuit = CircuitBreaker()
        # Stats
        self._total_retries = 0
        self._total_successes_after_retry = 0
        self._total_circuit_breaks = 0

    def retry_llm(self, fn: Callable, args: tuple = (), kwargs: dict = None) -> Any:
        """Retry an LLM call with exponential backoff.

        Retries on:
        - Empty response
        - Connection errors
        - Timeout errors
        - Any exception from the LLM callable
        """
        kwargs = kwargs or {}
        return self._retry_with_backoff(
            fn, args, kwargs,
            max_retries=self.llm_max_retries,
            base_delay=LLM_BASE_DELAY,
            max_delay=LLM_MAX_DELAY,
            backoff_factor=LLM_BACKOFF_FACTOR,
            operation="llm",
            is_retryable=self._is_llm_retryable,
        )

    def retry_tool(self, fn: Callable, args: tuple = (), kwargs: dict = None) -> Any:
        """Retry a tool execution with exponential backoff.

        Retries on:
        - Timeout errors
        - Transient filesystem errors
        - Connection errors (for network tools)
        """
        kwargs = kwargs or {}
        return self._retry_with_backoff(
            fn, args, kwargs,
            max_retries=self.tool_max_retries,
            base_delay=TOOL_BASE_DELAY,
            max_delay=TOOL_MAX_DELAY,
            backoff_factor=TOOL_BACKOFF_FACTOR,
            operation="tool",
            is_retryable=self._is_tool_retryable,
        )

    def _retry_with_backoff(
        self,
        fn: Callable,
        args: tuple,
        kwargs: dict,
        max_retries: int,
        base_delay: float,
        max_delay: float,
        backoff_factor: float,
        operation: str,
        is_retryable: Callable[[Exception], bool],
    ) -> Any:
        """Core retry loop with exponential backoff and jitter."""
        last_error = None

        for attempt in range(max_retries + 1):
            # Circuit breaker check
            if self._circuit.is_open:
                self._total_circuit_breaks += 1
                raise RuntimeError(
                    f"Circuit breaker is open after {self._circuit.failure_count} failures. "
                    f"Try again in {self._circuit.reset_timeout}s."
                )

            try:
                result = fn(*args, **kwargs)
                # Check for empty LLM response (retryable)
                if operation == "llm" and isinstance(result, str) and not result.strip():
                    raise EmptyResponseError("LLM returned empty response")
                self._circuit.record_success()
                return result

            except Exception as e:
                last_error = e
                self._circuit.record_failure()

                if attempt >= max_retries or not is_retryable(e):
                    break

                # Calculate delay with jitter
                delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                jitter = random.uniform(0, delay * 0.3)  # 30% jitter
                actual_delay = delay + jitter

                event = RetryEvent(
                    operation=operation,
                    attempt=attempt + 1,
                    max_attempts=max_retries,
                    delay=actual_delay,
                    error=str(e),
                    will_retry=True,
                )
                self._total_retries += 1

                if self.on_retry:
                    self.on_retry(event)

                logger.info(
                    "Retry %d/%d for %s after %.1fs: %s",
                    attempt + 1, max_retries, operation, actual_delay, e,
                )
                time.sleep(actual_delay)

        # All retries exhausted
        if last_error:
            raise last_error
        return None

    def _is_llm_retryable(self, error: Exception) -> bool:
        """Check if an LLM error is retryable."""
        error_str = str(error).lower()
        retryable_patterns = (
            "timeout", "connection", "rate limit", "503", "502",
            "529", "overloaded", "capacity", "empty response",
            "connectionreset", "broken pipe",
        )
        return any(p in error_str for p in retryable_patterns)

    def _is_tool_retryable(self, error: Exception) -> bool:
        """Check if a tool error is retryable."""
        error_str = str(error).lower()
        retryable_patterns = (
            "timeout", "connection", "temporary", "busy",
            "locked", "permission denied",
        )
        non_retryable = (
            "not found", "does not exist", "no such file",
            "syntax error", "invalid", "blocked",
        )
        if any(p in error_str for p in non_retryable):
            return False
        return any(p in error_str for p in retryable_patterns)

    def get_stats(self) -> Dict[str, Any]:
        """Return retry statistics."""
        return {
            "total_retries": self._total_retries,
            "successes_after_retry": self._total_successes_after_retry,
            "circuit_breaks": self._total_circuit_breaks,
            "circuit_state": self._circuit.state,
            "circuit_failures": self._circuit.failure_count,
        }

    def reset(self) -> None:
        """Reset all retry state."""
        self._circuit = CircuitBreaker()
        self._total_retries = 0
        self._total_successes_after_retry = 0
        self._total_circuit_breaks = 0


class EmptyResponseError(Exception):
    """Raised when the LLM returns an empty response."""
    pass
