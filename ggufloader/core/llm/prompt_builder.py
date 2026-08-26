"""
PromptBuilder - Pure prompt formatting for chat-style models.

Builds the ``User:/Assistant:`` style conversation prompt used by both
the chat pipeline and the agent engine, including an optional system
prompt and bounded conversation history.
"""

from __future__ import annotations

from typing import Dict, List, Optional

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. Answer questions clearly and concisely."
)

# Chat-template markers that models sometimes echo into their output.
# Feeding them back as history teaches the model to keep emitting them.
_TEMPLATE_MARKERS = (
    "[INST]", "<<SYS>>", "<</SYS>>", "[/INST]",
    "<|im_start|>", "<|im_end|>", "<|start_header_id|>", "<|end_header_id|>",
)


def _has_template_artifacts(text: str) -> bool:
    return any(marker in text for marker in _TEMPLATE_MARKERS)

# Token-level stop sequences that terminate generation cleanly.
STOP_TOKENS = [
    "<|im_end|>", "</s>", "user:", "assistant:", "###",
    "\nHuman:", "\nUser:", "Human:", "User:",
]

# End-of-turn markers passed as *stop strings* alongside the chat
# template. When a model's special tokens degrade to plain text (weak
# quant, template fallback), the runtime never sees EOS and generation
# runs until the context window fills - these strings catch that case.
CHAT_STOP_TOKENS = [
    "<|im_end|>",      # ChatML / LFM2 / Qwen turn end
    "<|endoftext|>",   # GPT-style / LFM2
    "<|eot_id|>",      # Llama 3 turn end
    "</s>",            # Mistral / Llama 2
    "<|end_of_text|>", # Llama 3
    "<|return|>",      # gpt-oss final
]


class PromptBuilder:
    """Formats conversation history + user message into a single prompt."""

    def __init__(self, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> None:
        self.system_prompt = system_prompt

    def build_messages(
        self, history: List[Dict[str, str]], user_message: str,
        max_history: int = 8, system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Return a chat *messages* list for create_chat_completion.

        llama.cpp renders this through the model's embedded chat template
        (the model's native format), so roles stay structured instead of
        being flattened into ``User:/Assistant:`` text.
        """
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt or self.system_prompt}
        ]
        for msg in history[-max_history:]:
            role = msg.get("role", "user")
            if role not in ("user", "assistant"):
                continue
            content = msg.get("content", "")
            if not content or _has_template_artifacts(content):
                continue  # template junk poisons the next generation
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})
        return messages

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
