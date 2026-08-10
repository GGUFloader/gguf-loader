"""
ModelEngine protocol - the one interface every LLM/embedding call goes
through.

The chat UI, the agent, and embeddings all talk to this abstraction;
tests inject fakes; an alternate backend (e.g. an OpenAI-compatible
server) can be added later without touching UI or agent code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Protocol, runtime_checkable


@dataclass
class ChatDelta:
    """One streamed unit of output from the engine."""

    token: str = ""
    finish_reason: Optional[str] = None


@dataclass
class EngineInfo:
    """What the engine knows about the loaded model and its device."""

    model_path: str = ""
    n_ctx: int = 0
    use_gpu: bool = False
    offloaded_layers: int = 0
    total_layers: int = 0
    device: str = ""
    vram_mb: int = 0


@runtime_checkable
class ModelEngine(Protocol):
    """Inference engine for chat, completion, and embeddings.

    Implementations must be thread-safe: calls are serialized by the
    engine executor, and a lock is held for the lifetime of any stream.
    """

    @property
    def is_loaded(self) -> bool: ...

    def load(self, path: str, *, gpu: bool = False, n_ctx: int = 32768) -> None:
        """Load *path* (a GGUF model). Raises on failure."""

    def chat(
        self,
        messages: List[dict],
        *,
        stream: bool = False,
        **params: object,
    ) -> str | Iterator[ChatDelta]:
        """Chat completion. Returns text, or yields ``ChatDelta`` when streaming."""

    def complete(
        self,
        prompt: str,
        *,
        stream: bool = False,
        **params: object,
    ) -> str | Iterator[ChatDelta]:
        """Raw completion. Returns text, or yields ``ChatDelta`` when streaming."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed *texts* into vectors. Requires an embedding-enabled engine."""

    def info(self) -> EngineInfo:
        """Metadata about the loaded model (offload, device, VRAM)."""

    def unload(self) -> None:
        """Release the model and free GPU/CPU memory."""
