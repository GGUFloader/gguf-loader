"""
LlamaCppEngine - the one real ``ModelEngine`` implementation.

Wraps ``llama_cpp.Llama``:

- ``chat()`` / ``complete()`` use llama.cpp's chat/completion endpoints;
  the chat template is handled by llama.cpp itself.
- ``embed()`` requires an embedding-enabled engine (``embedding=True``) -
  the app uses a separate small embed engine for that.
- Loading captures llama.cpp's stderr to record how many layers were
  actually offloaded to the GPU (the "provable GPU" story), instead of
  trusting the requested ``n_gpu_layers``.

The llama_cpp import is lazy so unit tests and CI can import this module
without the heavy wheel present.
"""

from __future__ import annotations

import contextlib
import io
import logging
import re
import threading
from typing import Any, Iterator, List, Optional

from .protocol import ChatDelta, EngineInfo, ModelEngine

logger = logging.getLogger(__name__)

try:  # pragma: no cover - depends on environment
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    Llama = None  # type: ignore[assignment]
    LLAMA_AVAILABLE = False

_OFFLOAD_RE = re.compile(
    r"llm_load_tensors:\s+offloaded\s+(\d+)/(\d+)\s+layers\s+to\s+(\S+)"
)


def _parse_offloaded(log: str) -> tuple[int, int, str]:
    """Extract ``(offloaded, total, device)`` from llama.cpp's load log.

    Returns ``(0, 0, "")`` when the line is missing (e.g. very old
    builds or unusual logging), so callers can treat it as "unknown"
    rather than "no GPU".
    """
    match = _OFFLOAD_RE.search(log)
    if match is None:
        return 0, 0, ""
    return int(match.group(1)), int(match.group(2)), match.group(3)


class LlamaCppEngine:
    """``ModelEngine`` implementation over llama-cpp-python."""

    def __init__(self, *, embedding: bool = False) -> None:
        self._embedding = embedding
        self._llama: Any = None
        self._lock = threading.Lock()
        self._info = EngineInfo()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @property
    def is_loaded(self) -> bool:
        return self._llama is not None

    def load(self, path: str, *, gpu: bool = False, n_ctx: int = 32768) -> None:
        """Load *path* (a GGUF model). Raises on failure."""
        if not LLAMA_AVAILABLE:
            raise RuntimeError(
                "llama-cpp-python is required but not installed.\n"
                "Install it with: pip install llama-cpp-python"
            )
        n_gpu_layers = -1 if gpu else 0

        # Capture llama.cpp's load log so we can report the *actual*
        # offload, not just the requested one.
        log_buffer = io.StringIO()
        with contextlib.redirect_stderr(log_buffer):
            llama = Llama(
                model_path=path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                embedding=self._embedding,
                verbose=True,
            )
        load_log = log_buffer.getvalue()

        offloaded, total, device = _parse_offloaded(load_log)
        logger.info(
            "Loaded %s (gpu=%s, ctx=%d, offloaded %d/%d layers to %s)",
            path, gpu, n_ctx, offloaded, total, device or "?",
        )
        if gpu and total and offloaded == 0:
            logger.warning("GPU mode requested but no layers were offloaded")

        self._llama = llama
        self._info = EngineInfo(
            model_path=path,
            n_ctx=n_ctx,
            use_gpu=gpu,
            offloaded_layers=offloaded,
            total_layers=total,
            device=device,
        )

    def unload(self) -> None:
        with self._lock:
            self._llama = None
            self._info = EngineInfo()

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: List[dict],
        *,
        stream: bool = False,
        **params: object,
    ) -> str | Iterator[ChatDelta]:
        if stream:
            return self._chat_stream(messages, params)
        with self._lock:
            llama = self._require()
            response = llama.create_chat_completion(
                messages=messages, stream=False, **params
            )
        content = response["choices"][0]["message"].get("content") or ""
        return str(content)

    def complete(
        self,
        prompt: str,
        *,
        stream: bool = False,
        **params: object,
    ) -> str | Iterator[ChatDelta]:
        if stream:
            return self._complete_stream(prompt, params)
        with self._lock:
            llama = self._require()
            response = llama(prompt, stream=False, **params)
        return str(response["choices"][0]["text"])

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self._embedding:
            raise RuntimeError(
                "This engine was not loaded for embeddings. Create a "
                "LlamaCppEngine(embedding=True) with an embed model."
            )
        with self._lock:
            llama = self._require()
            response = llama.create_embedding(input=texts)
        return [item["embedding"] for item in response["data"]]

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def info(self) -> EngineInfo:
        return self._info

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _require(self) -> Any:
        if not LLAMA_AVAILABLE:
            raise RuntimeError("llama-cpp-python is not installed")
        if self._llama is None:
            raise RuntimeError("No model is loaded")
        return self._llama

    def _chat_stream(self, messages: List[dict], params: dict) -> Iterator[ChatDelta]:
        with self._lock:
            llama = self._require()
            stream = llama.create_chat_completion(
                messages=messages, stream=True, **params
            )
            for chunk in stream:
                choice = (chunk.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                token = delta.get("content")
                if token:
                    yield ChatDelta(token=str(token))
                if choice.get("finish_reason"):
                    yield ChatDelta(finish_reason=str(choice["finish_reason"]))

    def _complete_stream(self, prompt: str, params: dict) -> Iterator[ChatDelta]:
        with self._lock:
            llama = self._require()
            stream = llama(prompt, stream=True, **params)
            for chunk in stream:
                token = (chunk.get("choices") or [{}])[0].get("text", "")
                if token:
                    yield ChatDelta(token=str(token))
