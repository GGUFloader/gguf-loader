"""
Engine layer - model runtime abstraction.

`ModelEngine` is the single interface the whole app uses to talk to a
local model. The only implementation is `LlamaCppEngine` (llama.cpp via
llama-cpp-python); `LlamaCppChatModel` adapts an engine to LangChain's
`BaseChatModel` so LangGraph can drive it.
"""

from .protocol import ChatDelta, EngineInfo, ModelEngine
from .llama_cpp_engine import LlamaCppEngine, LLAMA_AVAILABLE

__all__ = [
    "ChatDelta",
    "EngineInfo",
    "ModelEngine",
    "LlamaCppEngine",
    "LLAMA_AVAILABLE",
]
