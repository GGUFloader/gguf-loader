"""ModelEngine protocol + LlamaCppEngine guards (no real model needed)."""

import pytest

from core.engine import ChatDelta, EngineInfo, LlamaCppEngine, ModelEngine
from core.engine.llama_cpp_engine import _parse_offloaded


class FakeEngine:
    """Minimal implementation used to prove Protocol conformance."""

    def __init__(self) -> None:
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self, path: str, *, gpu: bool = False, n_ctx: int = 32768) -> None:
        self._loaded = True

    def chat(self, messages, *, stream=False, **params):
        return "hi"

    def complete(self, prompt, *, stream=False, **params):
        return "hi"

    def embed(self, texts):
        return [[0.0]]

    def info(self) -> EngineInfo:
        return EngineInfo()

    def unload(self) -> None:
        self._loaded = False


def test_fake_engine_conforms_to_protocol() -> None:
    assert isinstance(FakeEngine(), ModelEngine)


def test_engine_info_defaults() -> None:
    info = EngineInfo()
    assert info.model_path == ""
    assert info.n_ctx == 0
    assert info.use_gpu is False
    assert info.offloaded_layers == 0
    assert info.total_layers == 0
    assert info.device == ""
    assert info.vram_mb == 0


def test_chat_delta_defaults() -> None:
    assert ChatDelta().token == ""
    assert ChatDelta().finish_reason is None
    assert ChatDelta(token="x", finish_reason="stop").finish_reason == "stop"


def test_parse_offloaded_matches_llama_log() -> None:
    log = (
        "llama_model_loader: loaded meta data\n"
        "llm_load_tensors: offloaded 32/33 layers to GPU\n"
        "llama_perf_context_print: ..."
    )
    assert _parse_offloaded(log) == (32, 33, "GPU")


def test_parse_offloaded_metal() -> None:
    log = "llm_load_tensors: offloaded 33/33 layers to Metal\n"
    assert _parse_offloaded(log) == (33, 33, "Metal")


def test_parse_offloaded_missing_line() -> None:
    assert _parse_offloaded("no offload information here") == (0, 0, "")


def test_unloaded_engine_raises_on_chat() -> None:
    engine = LlamaCppEngine()
    assert engine.is_loaded is False
    with pytest.raises(RuntimeError, match="No model is loaded"):
        engine.chat([{"role": "user", "content": "hi"}])


def test_embed_requires_embedding_engine() -> None:
    engine = LlamaCppEngine()
    with pytest.raises(RuntimeError, match="embeddings"):
        engine.embed(["hi"])


def test_unload_is_safe_when_not_loaded() -> None:
    engine = LlamaCppEngine()
    engine.unload()  # must not raise
    assert engine.is_loaded is False


def test_info_before_load_is_empty() -> None:
    assert LlamaCppEngine().info() == EngineInfo()
