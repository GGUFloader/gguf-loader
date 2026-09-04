"""One LLM call path for the agent (both Qt and WebSocket UIs).

Every agent LLM call goes through :func:`build_llm`: the raw prompt is
delivered as a single ``user`` message so llama.cpp applies the model's
native chat template, sampling comes from the router role config with
per-purpose defaults, and generation stops on the canonical unified set
(``core.defaults.STOP_TOKENS_UNIFIED``) — never a completion-style call
with ad-hoc stops.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from ggufloader.core.defaults import (
    MAX_TOKENS_AGENT_ACTION,
    REPEAT_PENALTY_FLOOR,
    STOP_TOKENS_UNIFIED,
    TEMP_ACTION,
    TEMP_ANSWER,
)

#: temperature for tool-call / planning decisions (near-greedy JSON)
TEMP_BY_PURPOSE: Dict[str, float] = {
    "action": TEMP_ACTION,
    "answer": TEMP_ANSWER,
}


def build_llm(
    backend: Any,
    role: Optional[Dict[str, Any]] = None,
    purpose: str = "action",
    on_token: Optional[Callable[[str], None]] = None,
) -> Callable[..., str]:
    """Return ``llm(prompt, max_tokens=None, temperature=None, **kw) -> str``.

    ``purpose`` selects the default temperature (action ≈ greedy JSON,
    answer ≈ mild creativity for prose). An explicit ``temperature``
    argument always wins. ``role`` supplies top_k/top_p/repeat_penalty/
    max_tokens fallbacks from the router's RoleConfig.

    ``on_token`` receives each text delta as it is generated. Without it,
    ``chat_stream`` is drained into one joined string and callers see the
    reply only when generation finishes — the UI sits silent for the whole
    synthesis. A per-call ``on_chunk`` keyword (used by GraphAgent for its
    prose-answer calls) overrides it.
    """
    role = dict(role or {})
    default_temp = TEMP_BY_PURPOSE.get(purpose, TEMP_ACTION)

    def llm(prompt: str, max_tokens: Optional[int] = None,
            temperature: Optional[float] = None, **kw: Any) -> str:
        sink = kw.get("on_chunk") or on_token
        parts: List[str] = []
        for delta in backend.chat_stream(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens or role.get("max_tokens")
            or MAX_TOKENS_AGENT_ACTION,
            temperature=default_temp if temperature is None else temperature,
            top_k=kw.get("top_k", role.get("top_k", 40)),
            top_p=kw.get("top_p", role.get("top_p", 0.9)),
            repeat_penalty=kw.get(
                "repeat_penalty", role.get("repeat_penalty", REPEAT_PENALTY_FLOOR)),
            stop=kw.get("stop", STOP_TOKENS_UNIFIED),
        ):
            parts.append(delta)
            if sink:
                try:
                    sink(delta)
                except Exception:  # noqa: BLE001 - a dead sink must not kill generation
                    pass
        return "".join(parts)

    return llm
