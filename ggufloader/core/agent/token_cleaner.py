"""
TokenCleaner — Protocol + model-specific implementations for stripping
thinking tokens from LLM output.

Each model family (Gemma, Qwen, DeepSeek, etc.) emits different channel
markers or thinking tags.  The cleaner is selected at model load time and
injected into the agent, so every response path gets cleaned by
construction — no more forgetting to call _clean_model_output on a new
code path.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenCleaner(Protocol):
    """Protocol for model-specific token cleaning."""

    def clean(self, text: str) -> str:
        """Strip thinking tokens and special markers from *text*."""
        ...


class GemmaCleaner:
    """Handles Gemma 4 / Gemma 3 channel markers.

    Gemma emits patterns like:
        <|channel|>thought <|channel|>thought <|channel|>The answer is...
    """

    _CHANNEL_THINK = re.compile(
        r"(<\|channel\|>\s*(?:thinking|thought|answer|reasoning)\s*)+",
        re.IGNORECASE,
    )
    _CHANNEL_BARE = re.compile(r"(<\|channel\|>\s*)+")
    _NAMED_TOKEN = re.compile(r"<\|[a-z_]+\|>")

    def clean(self, text: str) -> str:
        text = self._CHANNEL_THINK.sub("", text)
        text = self._CHANNEL_BARE.sub("", text)
        text = self._NAMED_TOKEN.sub("", text)
        return _collapse_whitespace(text)


class QwenCleaner:
    """Handles Qwen <think> ... </think> blocks."""

    _THINK_FULL = re.compile(r"<think>[\s\S]*?</think>")
    _THINK_PARTIAL = re.compile(r"<think>[\s\S]*$")

    def clean(self, text: str) -> str:
        text = self._THINK_FULL.sub("", text)
        text = self._THINK_PARTIAL.sub("", text)
        return _collapse_whitespace(text)


class DeepSeekCleaner:
    """Handles DeepSeek <\|begin_of_thought\|> blocks."""

    _BLOCK = re.compile(
        r"<\|begin_of_thought\|>[\s\S]*?<\|end_of_thought\|>"
    )
    _CHANNEL_THINK = re.compile(
        r"(<\|channel\|>\s*(?:thinking|thought|answer|reasoning)\s*)+",
        re.IGNORECASE,
    )
    _CHANNEL_BARE = re.compile(r"(<\|channel\|>\s*)+")
    _NAMED_TOKEN = re.compile(r"<\|[a-z_]+\|>")

    def clean(self, text: str) -> str:
        text = self._BLOCK.sub("", text)
        text = self._CHANNEL_THINK.sub("", text)
        text = self._CHANNEL_BARE.sub("", text)
        text = self._NAMED_TOKEN.sub("", text)
        return _collapse_whitespace(text)


class GenericCleaner:
    """Catch-all: strips <think> blocks and common special tokens.

    Safe for any model that doesn't have a dedicated cleaner.
    """

    _THINK_FULL = re.compile(r"<think>[\s\S]*?</think>")
    _THINK_PARTIAL = re.compile(r"<think>[\s\S]*$")
    _BLOCK = re.compile(
        r"<\|begin_of_thought\|>[\s\S]*?<\|end_of_thought\|>"
    )
    _CHANNEL_THINK = re.compile(
        r"(<\|channel\|>\s*(?:thinking|thought|answer|reasoning)\s*)+",
        re.IGNORECASE,
    )
    _CHANNEL_BARE = re.compile(r"(<\|channel\|>\s*)+")
    _NAMED_TOKEN = re.compile(r"<\|[a-z_]+\|>")

    def clean(self, text: str) -> str:
        text = self._THINK_FULL.sub("", text)
        text = self._THINK_PARTIAL.sub("", text)
        text = self._BLOCK.sub("", text)
        text = self._CHANNEL_THINK.sub("", text)
        text = self._CHANNEL_BARE.sub("", text)
        text = self._NAMED_TOKEN.sub("", text)
        return _collapse_whitespace(text)


# ── Registry ────────────────────────────────────────────────────────────

_CLEANERS: dict[str, TokenCleaner] = {
    "gemma": GemmaCleaner(),
    "gemma2": GemmaCleaner(),
    "gemma3": GemmaCleaner(),
    "gemma4": GemmaCleaner(),
    "qwen": QwenCleaner(),
    "qwen2": QwenCleaner(),
    "qwen3": QwenCleaner(),
    "deepseek": DeepSeekCleaner(),
    "deepseek2": DeepSeekCleaner(),
    "deepseek3": DeepSeekCleaner(),
}

_DEFAULT = GenericCleaner()


def get_cleaner(architecture: str | None = None) -> TokenCleaner:
    """Return the appropriate cleaner for *architecture*.

    Falls back to :class:`GenericCleaner` for unknown architectures.
    """
    if not architecture:
        return _DEFAULT
    key = architecture.lower().strip()
    return _CLEANERS.get(key, _DEFAULT)


# ── Helpers ─────────────────────────────────────────────────────────────

def _collapse_whitespace(text: str) -> str:
    """Normalise runs of blank lines and trim."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
