"""LangChain adapter tests - fake engine, no real model."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ggufloader.core.engine import ChatDelta
from ggufloader.core.engine.langchain_adapter import LlamaCppChatModel, _message_to_dict


class FakeChatEngine:
    """Fake ModelEngine that just echoes a canned reply."""

    def chat(self, messages, *, stream=False, **params):
        assert isinstance(messages, list) and messages
        if stream:
            return iter(
                [
                    ChatDelta(token="Hel"),
                    ChatDelta(token="lo"),
                    ChatDelta(finish_reason="stop"),
                ]
            )
        return "Hello there"


def test_invoke_returns_text() -> None:
    model = LlamaCppChatModel(engine=FakeChatEngine())
    result = model.invoke([HumanMessage(content="hi")])
    assert result.content == "Hello there"


def test_stream_yields_accumulated_text() -> None:
    model = LlamaCppChatModel(engine=FakeChatEngine())
    parts = []
    for chunk in model.stream([HumanMessage(content="hi")]):
        # langchain-core yields ChatGenerationChunk (has .message) or a
        # bare AIMessageChunk depending on version - handle both.
        message = getattr(chunk, "message", chunk)
        parts.append(message.content)
    assert "".join(parts) == "Hello"


def test_message_to_dict_roles() -> None:
    assert _message_to_dict(HumanMessage(content="hi")) == {
        "role": "user",
        "content": "hi",
    }
    assert _message_to_dict(SystemMessage(content="sys")) == {
        "role": "system",
        "content": "sys",
    }
    assert _message_to_dict(AIMessage(content="a")) == {
        "role": "assistant",
        "content": "a",
    }


def test_model_is_a_langchain_chat_model() -> None:
    from langchain_core.language_models import BaseChatModel

    assert isinstance(LlamaCppChatModel(engine=FakeChatEngine()), BaseChatModel)
