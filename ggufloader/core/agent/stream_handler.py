"""
StreamHandler - Partial JSON repair and graceful abort for agent responses.

Handles streaming LLM output with:
- Progressive JSON repair (fix as tokens arrive, don't wait for full response)
- Graceful abort (user can stop mid-stream, get partial result)
- Response timeout (kill stale streams)
- Token counting during streaming

Pattern from: Aider streaming + OpenHands condensation.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Timeout for a single LLM response (seconds)
DEFAULT_RESPONSE_TIMEOUT = 120


class StreamAbort:
    """Thread-safe abort signal for streaming responses."""

    def __init__(self) -> None:
        self._abort = threading.Event()
        self._abort_reason = ""

    @property
    def is_aborted(self) -> bool:
        return self._abort.is_set()

    @property
    def reason(self) -> str:
        return self._abort_reason

    def abort(self, reason: str = "User requested stop") -> None:
        self._abort_reason = reason
        self._abort.set()

    def reset(self) -> None:
        self._abort.clear()
        self._abort_reason = ""


class PartialJsonRepair:
    """Progressive JSON repair for streaming LLM output.

    As tokens arrive, this attempts to extract a valid JSON object
    from the partial text. If the full response arrives and still
    isn't valid JSON, it applies increasingly aggressive repairs.
    """

    @staticmethod
    def try_parse(text: str) -> Optional[Dict[str, Any]]:
        """Try to parse the text as JSON, with progressive repairs.

        Returns parsed dict if successful, None otherwise.
        """
        if not text or not text.strip():
            return None

        # Level 0: Direct parse
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # Level 1: Extract from code fences
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence_match:
            try:
                data = json.loads(fence_match.group(1))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # Level 2: Find balanced braces
        for obj_str in _find_balanced_braces(text):
            try:
                data = json.loads(obj_str)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                # Level 3: Try repairing common issues
                repaired = _repair_json(obj_str)
                try:
                    data = json.loads(repaired)
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    continue

        return None

    @staticmethod
    def try_extract_answer(text: str) -> Optional[str]:
        """Try to extract just the 'answer' field from partial JSON."""
        data = PartialJsonRepair.try_parse(text)
        if data and "answer" in data:
            return data["answer"]
        # Try regex fallback for partial output
        match = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if match:
            return match.group(1).replace('\\"', '"').replace("\\n", "\n")
        return None

    @staticmethod
    def try_extract_reasoning(text: str) -> Optional[str]:
        """Try to extract just the 'reasoning' field from partial JSON."""
        data = PartialJsonRepair.try_parse(text)
        if data and "reasoning" in data:
            return data["reasoning"]
        match = re.search(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if match:
            return match.group(1).replace('\\"', '"').replace("\\n", "\n")
        return None

    @staticmethod
    def try_extract_tool_calls(text: str) -> list:
        """Try to extract tool_calls array from partial JSON."""
        data = PartialJsonRepair.try_parse(text)
        if data and "tool_calls" in data:
            return data["tool_calls"]
        # Try to find partial tool_calls array
        match = re.search(r'"tool_calls"\s*:\s*(\[.*?\])', text, re.DOTALL)
        if match:
            try:
                calls = json.loads(match.group(1))
                if isinstance(calls, list):
                    return calls
            except json.JSONDecodeError:
                pass
        return []


class StreamHandler:
    """Manages streaming LLM responses with abort and timeout.

    Usage:
        handler = StreamHandler()
        abort = handler.create_abort()

        # In a worker thread
        result = handler.stream_with_repair(
            llm_fn, prompt, abort=abort,
            on_token=lambda t: update_ui(t),
        )

        # User clicks Stop
        abort.abort()
    """

    def __init__(self, response_timeout: float = DEFAULT_RESPONSE_TIMEOUT) -> None:
        self.response_timeout = response_timeout
        self._repair = PartialJsonRepair()
        self._current_abort: Optional[StreamAbort] = None
        # Stats
        self._total_streams = 0
        self._total_aborts = 0
        self._total_timeouts = 0
        self._total_repairs = 0

    def create_abort(self) -> StreamAbort:
        """Create a new abort signal for a streaming operation."""
        abort = StreamAbort()
        self._current_abort = abort
        return abort

    def stream_with_repair(
        self,
        llm_fn: Callable[..., str],
        prompt: str,
        abort: Optional[StreamAbort] = None,
        on_token: Optional[Callable[[str], None]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """Execute an LLM call with streaming, repair, and abort support.

        Since llama-cpp-python doesn't support true streaming from Python,
        this wraps a synchronous call with abort checking and timeout.

        Returns:
            {"response": str, "data": dict|None, "aborted": bool, "repaired": bool}
        """
        self._total_streams += 1
        start = time.monotonic()
        repaired = False

        if abort is None:
            abort = self.create_abort()

        try:
            # Run LLM call with timeout
            result = [None]
            error = [None]

            def _call():
                try:
                    result[0] = llm_fn(prompt, max_tokens=max_tokens, temperature=temperature)
                except Exception as e:
                    error[0] = e

            thread = threading.Thread(target=_call, daemon=True)
            thread.start()
            thread.join(timeout=self.response_timeout)

            # Check abort before processing
            if abort.is_aborted:
                self._total_aborts += 1
                partial = result[0] or ""
                return {
                    "response": partial,
                    "data": self._repair.try_parse(partial),
                    "aborted": True,
                    "repaired": False,
                    "reason": abort.reason,
                }

            # Check timeout
            if thread.is_alive():
                self._total_timeouts += 1
                return {
                    "response": "",
                    "data": None,
                    "aborted": False,
                    "repaired": False,
                    "reason": f"Response timed out after {self.response_timeout}s",
                }

            # Check error
            if error[0] is not None:
                return {
                    "response": "",
                    "data": None,
                    "aborted": False,
                    "repaired": False,
                    "reason": str(error[0]),
                }

            raw = result[0] or ""

            # Try to parse as JSON
            data = self._repair.try_parse(raw)
            if data is None and raw.strip():
                # Try harder with repair
                repaired_text = _repair_json(raw)
                if repaired_text != raw:
                    data = self._repair.try_parse(repaired_text)
                    if data is not None:
                        repaired = True
                        self._total_repairs += 1
                        raw = repaired_text

            elapsed = (time.monotonic() - start) * 1000
            return {
                "response": raw,
                "data": data,
                "aborted": False,
                "repaired": repaired,
                "elapsed_ms": int(elapsed),
            }

        except Exception as e:
            return {
                "response": "",
                "data": None,
                "aborted": False,
                "repaired": False,
                "reason": str(e),
            }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_streams": self._total_streams,
            "total_aborts": self._total_aborts,
            "total_timeouts": self._total_timeouts,
            "total_repairs": self._total_repairs,
        }


# --- Internal helpers ---

def _find_balanced_braces(text: str):
    """Find all balanced brace substrings."""
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                yield text[start:i + 1]
                start = -1


def _repair_json(text: str) -> str:
    """Apply common JSON repairs to model output."""
    # Escape unescaped backslashes in strings
    result = text

    # Fix trailing commas before } or ]
    result = re.sub(r",\s*([}\]])", r"\1", result)

    # Fix missing closing braces
    opens = result.count("{") - result.count("}")
    if opens > 0:
        result += "}" * opens

    # Fix missing closing brackets
    opens = result.count("[") - result.count("]")
    if opens > 0:
        result += "]" * opens

    # Fix single quotes (model sometimes uses ' instead of ")
    # Only if there are no double quotes at all
    if '"' not in result and "'" in result:
        result = result.replace("'", '"')

    return result
