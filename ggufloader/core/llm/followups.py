"""Suggested follow-up questions (GPT4All parity).

Prompt is verbatim from GPT4All's ModelInfo defaults; extraction uses the
same English question-word regex they ship (acknowledged limitation).
"""

from __future__ import annotations

import re

FOLLOWUP_PROMPT = (
    "Suggest three very short factual follow-up questions that have not "
    "been answered yet or cannot be found inspired by the previous "
    "conversation and excerpts."
)

_QUESTION_RE = re.compile(
    r"\b(?:What|Where|How|Why|When|Who|Which|Whose|Whom)\b[^?]*\?"
)


def extract_questions(text: str, limit: int = 3) -> list:
    """Pull up to *limit* questions out of a model reply."""
    seen: list = []
    for q in _QUESTION_RE.findall(text or ""):
        q = " ".join(q.split())
        if q and q.lower() not in {s.lower() for s in seen}:
            seen.append(q)
        if len(seen) >= limit:
            break
    return seen
