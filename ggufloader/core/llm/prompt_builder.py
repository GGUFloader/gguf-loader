"""
PromptBuilder - Pure prompt formatting for chat-style models.

Builds the ``User:/Assistant:`` style conversation prompt used by both
the chat pipeline and the agent engine, including an optional system
prompt and bounded conversation history.
"""

from __future__ import annotations

from typing import Dict, List

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. Answer questions clearly and concisely."
)

# Token-level stop sequences that terminate generation cleanly.
STOP_TOKENS = [
    "<|im_end|>", "</s>", "user:", "assistant:", "###",
    "\nHuman:", "\nUser:", "Human:", "User:",
]


class PromptBuilder:
    """Formats conversation history + user message into a single prompt."""

    def __init__(self, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> None:
        self.system_prompt = system_prompt

    def build(self, history: List[Dict[str, str]], user_message: str) -> str:
        """Return the full prompt text for *user_message*.

        ``history`` is a list of ``{"role": "user"|"assistant",
        "content": str}`` entries. Only the last ``max_history`` messages
        are included to bound prompt size.
        """
        parts = [self.system_prompt, "", "Answer clearly and concisely.", ""]
        for msg in history[-6:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"{role.capitalize()}: {content}")
            parts.append("")
        parts.append(f"User: {user_message}")
        parts.append("Assistant: ")
        return "\n".join(parts)

    @staticmethod
    def stop_tokens() -> List[str]:
        return list(STOP_TOKENS)
