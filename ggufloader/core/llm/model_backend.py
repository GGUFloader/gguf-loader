"""
ModelBackend - Thread-safe wrapper around the llama-cpp-python runtime.

This is the *only* module in the application that talks directly to
llama_cpp. It exposes a callable interface compatible with the raw
``Llama`` object (``model(prompt, stream=True, ...)``), so UI code and
addons that historically called the raw object keep working, while all
access is serialized through a lock to prevent concurrent-call crashes.

This module is intentionally Qt-free so it can be unit tested in
isolation and reused from any worker thread.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    Llama = None
    LLAMA_AVAILABLE = False


class ModelBackend:
    """Owns a loaded GGUF model and serializes access to it."""

    def __init__(
        self,
        model_path: str,
        use_gpu: bool = False,
        n_ctx: int = 32768,
        n_gpu_layers: int = -1,
    ) -> None:
        self.model_path = model_path
        self.use_gpu = use_gpu
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers if use_gpu else 0
        self._llama: Any = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def load(self) -> "ModelBackend":
        """Create the underlying llama_cpp runtime. Raises on failure."""
        if not LLAMA_AVAILABLE:
            raise RuntimeError(
                "llama-cpp-python is required but not installed.\n"
                "Install it with: pip install llama-cpp-python"
            )
        logger.info(
            "Loading model %s (gpu_layers=%d, ctx=%d)",
            self.model_path, self.n_gpu_layers, self.n_ctx,
        )
        self._llama = Llama(
            model_path=self.model_path,
            n_ctx=self.n_ctx,
            n_gpu_layers=self.n_gpu_layers,
            verbose=True,
        )
        return self

    def unload(self) -> None:
        """Release the model and free GPU/CPU memory."""
        with self._lock:
            self._llama = None

    @property
    def is_loaded(self) -> bool:
        return self._llama is not None

    @property
    def n_ctx_train(self) -> Optional[int]:
        """Tokens the model was trained for (None when unavailable).

        Running far beyond this degrades quality even though llama.cpp
        happily accepts a larger ``n_ctx``.
        """
        if self._llama is None:
            return None
        try:
            return int(self._llama.n_ctx_train())
        except Exception:  # noqa: BLE001 - depends on llama-cpp version
            return None

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterator[str]:
        """Stream assistant content for a chat *messages* list.

        Uses ``llama.create_chat_completion``, which renders the messages
        through the GGUF's own embedded chat template (Llama-3, Qwen,
        Mistral, gpt-oss harmony, ...) - the same mechanism Ollama uses.
        This matches the format the model was instruction-tuned on and is
        strongly preferred over hand-built ``User:/Assistant:`` strings.

        Yields content deltas (plain text chunks).
        """
        kwargs = dict(kwargs)
        kwargs["stream"] = True
        kwargs["messages"] = messages
        with self._lock:
            llama = self._require_llama()
            stream = llama.create_chat_completion(**kwargs)
            for chunk in stream:
                choices = chunk.get("choices") or [{}]
                delta = choices[0].get("delta") or {}
                text = delta.get("content")
                if text:
                    yield text

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Non-streaming :meth:`chat_stream`; returns the full reply."""
        parts: List[str] = []
        for piece in self.chat_stream(messages, **kwargs):
            parts.append(piece)
        return "".join(parts)

    def generate_stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """Stream raw text tokens for *prompt*.

        ``kwargs`` are passed straight through to llama_cpp (max_tokens,
        temperature, top_p, repeat_penalty, top_k, stop, ...).
        """
        kwargs = dict(kwargs)
        kwargs["stream"] = True
        for token_data in self._stream(prompt, kwargs):
            yield token_data.get("choices", [{}])[0].get("text", "")

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a complete (non-streamed) text response."""
        with self._lock:
            llama = self._require_llama()
            response = llama(prompt, **kwargs)
        return response["choices"][0]["text"]

    def __call__(self, prompt: str, **kwargs: Any) -> Any:
        """Llama-compatible callable used by the UI and addons.

        ``stream=True`` returns a generator of token dicts (same shape as
        llama_cpp); otherwise a full response dict is returned. The lock
        is held for the lifetime of a stream so two threads never call
        the runtime concurrently.
        """
        if kwargs.get("stream"):
            return self._stream(prompt, kwargs)
        with self._lock:
            llama = self._require_llama()
            return llama(prompt, **kwargs)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _require_llama(self) -> Any:
        if not LLAMA_AVAILABLE:
            raise RuntimeError("llama-cpp-python is not installed")
        if self._llama is None:
            raise RuntimeError("No model is loaded")
        return self._llama

    def _stream(self, prompt: str, kwargs: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """Yield raw token dicts while holding the lock for the stream lifetime."""
        with self._lock:
            llama = self._require_llama()
            stream = llama(prompt, **kwargs)
            for token_data in stream:
                yield token_data
