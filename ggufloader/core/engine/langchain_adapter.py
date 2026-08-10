"""
LangChain adapter - exposes a ``ModelEngine`` as a LangChain
``BaseChatModel`` so LangGraph can drive llama.cpp.

This is the only place LangChain touches the engine. The model does not
implement native tool calling (``bind_tools``); the agent uses the JSON
protocol prompt instead, which is far more reliable on small local
models. Streaming maps engine ``ChatDelta`` objects to LangChain chunks.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    SystemMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field

from .protocol import ModelEngine


def _message_to_dict(message: BaseMessage) -> Dict[str, str]:
    """Convert a LangChain message to a llama.cpp chat payload entry."""
    if isinstance(message, SystemMessage):
        role = "system"
    elif isinstance(message, AIMessage):
        role = "assistant"
    elif isinstance(message, ToolMessage):
        role = "tool"
    else:
        role = "user"
    content = message.content
    if isinstance(content, str):
        text = content
    else:  # multimodal content blocks - flatten to text
        text = "".join(
            str(block.get("text", "")) for block in content if isinstance(block, dict)
        )
    return {"role": role, "content": text}


class LlamaCppChatModel(BaseChatModel):
    """LangChain chat model backed by a :class:`ModelEngine`."""

    model_name: str = "llama.cpp"
    temperature: float = 0.1
    max_tokens: int = 2048
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    engine: Any = Field(exclude=True, description="The underlying ModelEngine")

    @property
    def _llm_type(self) -> str:
        return "llama_cpp_engine"

    # ------------------------------------------------------------------
    # BaseChatModel implementation
    # ------------------------------------------------------------------
    def _build_params(self, stop: Optional[Sequence[str]], kwargs: dict) -> dict:
        params: dict = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repeat_penalty": self.repeat_penalty,
        }
        if stop:
            params["stop"] = list(stop)
        params.update(kwargs)
        return params

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = [_message_to_dict(m) for m in messages]
        params = self._build_params(stop, kwargs)
        text = self.engine.chat(payload, stream=False, **params)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        payload = [_message_to_dict(m) for m in messages]
        params = self._build_params(stop, kwargs)
        for delta in self.engine.chat(payload, stream=True, **params):
            if delta.token and run_manager is not None:
                run_manager.on_llm_new_token(delta.token)
            yield ChatGenerationChunk(
                message=AIMessageChunk(content=delta.token or "")
            )
