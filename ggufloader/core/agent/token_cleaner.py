"""
TokenCleaner — strips Gemma 4 channel/thinking markers from LLM output.

The app is pinned to a single model (Gemma 4 12B Instruct Q4_K_M), so the
cleaner registry only needs the Gemma 4 family.  The cleaner is selected at
model load time and injected into the agent, so every response path gets
cleaned by construction — no more forgetting to call _clean_model_output
on a new code path.  Unknown architectures fall back to GenericCleaner.
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
    """Handles Gemma 4 channel markers.

    Gemma emits patterns like:
        <|channel|>thought <|channel|>thought <|channel|>The answer is...
        <|channel>thought <|channel|>AI (Artificial Intelligence)...
        <|channel|>analysis<|message|>...<|channel|>final<|message|>answer<|end|>
    """

    # Strip "<|channel|>NAME" or "<|channel>NAME" (channel-name marker).
    # The closing pipe may be missing in some quantized builds.
    # Match any word after channel marker (not just specific keywords)
    # to catch things like <|channel|>AI, <|channel>thought, etc.
    _CHANNEL_NAMED = re.compile(
        r"<\|?channel\|?>\s*(?:thinking|thought|answer|reasoning|analysis|final|user|assistant|model|plan|step)\b[^|<]*",
        re.IGNORECASE,
    )
    # Bare channel marker with non-keyword after it (e.g. <|channel|>AI)
    _CHANNEL_BARE = re.compile(r"<\|?channel\|?>\s*")
    _MESSAGE = re.compile(r"<\|?message\|?>\s*")
    _START_TURN = re.compile(r"<\|start\|>\s*(?:user|assistant|model|system)\s*", re.IGNORECASE)
    _END_TURN = re.compile(r"<\|end\|>\s*")
    # Gemma 3/4 chat-template markers
    # (<start_of_turn>user, <end_of_turn>) are stripped together with their
    # role name so no "user"/"model" residue survives into the JSON parser.
    _TURN_START_V3 = re.compile(
        r"<start_of_turn>\s*(?:user|assistant|model|system)?\s*", re.IGNORECASE)
    _TURN_END_V3 = re.compile(r"<end_of_turn>\s*")

    _CONSTRAIN = re.compile(r"<\|constrain\|>\s*[^|]*?\|>", re.IGNORECASE)
    _NAMED_TOKEN = re.compile(r"<\|[a-z_]+\|>")

    def clean(self, text: str) -> str:
        text = self._CHANNEL_NAMED.sub("", text)
        text = self._START_TURN.sub("", text)
        text = self._END_TURN.sub("", text)
        text = self._TURN_START_V3.sub("", text)
        text = self._TURN_END_V3.sub("", text)
        text = self._MESSAGE.sub("", text)
        text = self._CHANNEL_BARE.sub("", text)
        text = self._CONSTRAIN.sub("", text)
        text = self._NAMED_TOKEN.sub("", text)
        return _collapse_whitespace(text)


class GenericCleaner:
    """Catch-all fallback for unknown architectures.

    Safe for any model that doesn't have the Gemma 4 cleaner, and keeps
    old sessions/edge paths working if a non-Gemma file slips through.
    """

    _THINK_FULL = re.compile(r"<think>[\s\S]*?</think>")
    _THINK_PARTIAL = re.compile(r"<think>[\s\S]*$")
    _BLOCK = re.compile(
        r"<\|begin_of_thought\|>[\s\S]*?<\|end_of_thought\|>"
    )
    _CHANNEL_NAMED = re.compile(
        r"<\|?channel\|?>\s*(?:thinking|thought|answer|reasoning|analysis|final|user|assistant|model|plan|step)\b[^\n|]*",
        re.IGNORECASE,
    )
    _CHANNEL_BARE = re.compile(r"<\|?channel\|?>\s*")
    _START_TURN = re.compile(r"<\|start\|>\s*(?:user|assistant|model|system)\s*", re.IGNORECASE)
    _END_TURN = re.compile(r"<\|end\|>\s*")
    _NAMED_TOKEN = re.compile(r"<\|[a-z_]+\|>")

    def clean(self, text: str) -> str:
        text = self._THINK_FULL.sub("", text)
        text = self._THINK_PARTIAL.sub("", text)
        text = self._BLOCK.sub("", text)
        text = self._CHANNEL_NAMED.sub("", text)
        text = self._START_TURN.sub("", text)
        text = self._END_TURN.sub("", text)
        text = self._CHANNEL_BARE.sub("", text)
        text = self._NAMED_TOKEN.sub("", text)
        return _collapse_whitespace(text)


# ── Registry ────────────────────────────────────────────────────────────

# Single-model app: only the Gemma 4 family is loadable, so the registry
# needs exactly one entry. Unknown archs (generic fallback) get GenericCleaner.
_CLEANERS: dict[str, TokenCleaner] = {
    "gemma4": GemmaCleaner(),
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
