"""Split reasoning-model output into thought and answer streams.

Local "thinking" models emit their chain-of-thought inline with special
markers before the real answer. Two families are common:

1. Tag style (DeepSeek-R1, Qwen3, ...)::

       <think>private reasoning</think>Visible answer

2. Harmony / gpt-oss channel style::

       <|start|>assistant<|channel|>analysis<|message|>reasoning<|end|>
       <|start|>assistant<|channel|>final<|message|>Visible answer

Some quantized builds drop individual pipes, so ``<channel|>`` style
variants are tolerated too.

:class:`ReasoningStreamParser` is incremental (token-stream safe - tags
may arrive split across chunks) and yields ``("thought" | "answer",
text)`` events. :func:`split_reasoning` handles complete strings.

States::

    prologue -> thought -> prologue* -> ... -> final
        prologue --(channel)--> await_message --> thought | final

Text seen in ``prologue`` is provisional: short prefixes (e.g. a stray
"thought" word ahead of a channel tag) join the thought stream once a
marker appears; otherwise they are flushed as the answer at ``finish()``
(or past a large-size safety threshold).
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

# Tolerate missing pipes: <|channel|>, <channel|>, <|channel>, <channel>
_RE_CHANNEL = re.compile(r"<\|?channel\|?>", re.IGNORECASE)
_RE_MESSAGE = re.compile(r"<\|?message\|?>", re.IGNORECASE)
_RE_STOP = re.compile(r"<\|(?:end|return)\|?>", re.IGNORECASE)
_RE_THINK_OPEN = re.compile(r"<think(?:ing)?>", re.IGNORECASE)
_RE_THINK_CLOSE = re.compile(r"</think(?:ing)?>", re.IGNORECASE)
# Harmony role preamble before a channel tag - never shown to the user.
_RE_ROLE_PREAMBLE = re.compile(r"(?:<\|?start\|?>)?\s*assistant\s*$", re.IGNORECASE)

_HOLD = 20                # chars kept back in case a tag straddles chunks

Event = Tuple[str, str]


class ReasoningStreamParser:
    """Incremental splitter; feed chunks, receive routed text events."""

    def __init__(self) -> None:
        self._buf = ""
        self._state = "prologue"
        self._after_message = "thought"   # where await_message goes next
        self.saw_thoughts = False
        self._answer_started = False
        self.final_state = "prologue"     # state at finish() - see panels

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def feed(self, chunk: str) -> List[Event]:
        """Consume *chunk*; return decisively-routed ``(kind, text)`` parts."""
        self._buf += chunk
        events: List[Event] = []
        while self._step(events):
            pass
        return events

    def finish(self) -> List[Event]:
        """Flush whatever is left according to the current state.

        ``final_state`` records where the stream ended: ``prologue``
        means no marker ever appeared, so everything previously emitted
        as "thought" was actually a plain answer (panels use this to
        relocate the text into the reply bubble).
        """
        self.final_state = self._state
        events: List[Event] = []
        text = self._buf
        self._buf = ""
        if not text:
            return events
        if self._state == "thought" or (
            self._state == "await_message" and self._after_message == "thought"
        ):
            self._emit_thought(events, text)
        elif self._state == "await_message" and self._after_message == "final":
            self._emit_answer(events, text)
        else:
            self._emit_answer(events, text)
        return events

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def _step(self, events: List[Event]) -> bool:
        state = self._state
        if state == "final":
            return self._step_final(events)
        if state == "thought":
            return self._step_thought(events)
        if state == "await_message":
            return self._step_await_message(events)
        return self._step_prologue(events)

    def _step_prologue(self, events: List[Event]) -> bool:
        buf = self._buf
        think = _RE_THINK_OPEN.search(buf)
        chan = _RE_CHANNEL.search(buf)
        # A close tag with no opening marker happens when the model's
        # opening <think> is a special token that decodes to empty text
        # while </think> arrives as literal text. Everything before it is
        # reasoning, everything after is the answer.
        close = _RE_THINK_CLOSE.search(buf)
        starts = [m for m in (think, chan, close) if m]

        if not starts:
            # No marker yet. Stream the text live into the thinking block
            # (provisionally): models with an invisible <think> opener
            # would otherwise show nothing until the close tag arrived.
            # If no marker EVER appears, finish() flags final_state ==
            # 'prologue' and panels relocate the text to the answer bubble.
            take = len(buf) - _HOLD
            if take > 0:
                self._emit_thought(events, buf[:take])
                self._buf = buf[take:]
                return True
            return False

        marker = min(starts, key=lambda m: m.start())
        boundary = marker.start()
        if boundary > 0:
            self._emit_thought(events, buf[:boundary])
        self._buf = buf[marker.end():]
        if marker is think:
            self._state = "thought"
        elif marker is chan:
            self._enter_channel()
        else:
            # Bare closing tag: held buffer was all reasoning.
            self._state = "final"
        return True

    def _step_thought(self, events: List[Event]) -> bool:
        buf = self._buf
        closers = [m for m in (_RE_THINK_CLOSE.search(buf), _RE_STOP.search(buf)) if m]
        chan = _RE_CHANNEL.search(buf)
        markers = closers + ([chan] if chan else [])

        if not markers:
            take = len(buf) - _HOLD
            if take > 0:
                self._emit_thought(events, buf[:take])
                self._buf = buf[take:]
                return True
            return False

        marker = min(markers, key=lambda m: m.start())
        if marker.start() > 0:
            self._emit_thought(events, buf[: marker.start()])
        self._buf = buf[marker.end():]
        if marker is chan:
            self._enter_channel()
        elif marker.re is _RE_THINK_CLOSE:
            # </think> hands over to the visible answer.
            self._state = "final"
        else:
            # <|end|>/<|return|>: harmony continues with a final channel,
            # so return to prologue until the next marker shows up.
            self._state = "prologue"
        return True

    def _step_await_message(self, events: List[Event]) -> bool:
        m = _RE_MESSAGE.search(self._buf)
        if m:
            self._buf = self._buf[m.end():]
            self._state = self._after_message
            return True
        # Keep only the tail that could still grow into a message tag.
        if len(self._buf) > _HOLD:
            self._buf = self._buf[-_HOLD:]
        return False

    def _step_final(self, events: List[Event]) -> bool:
        buf = self._buf
        stop = _RE_STOP.search(buf)
        if stop:
            if stop.start() > 0:
                self._emit_answer(events, buf[: stop.start()])
            self._buf = buf[stop.end():]
            return True
        take = len(buf) - _HOLD
        if take > 0:
            self._emit_answer(events, buf[:take])
            self._buf = buf[take:]
            return True
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _enter_channel(self) -> None:
        """Classify the keyword right after a channel tag."""
        stripped = self._buf.lstrip()
        low = stripped.lower()
        if low.startswith("final"):
            self._buf = stripped[len("final"):]
            self._after_message = "final"
        elif low.startswith("analysis"):
            self._buf = stripped[len("analysis"):]
            self._after_message = "thought"
        else:
            # Unknown channel: assume reasoning until proven otherwise.
            self._after_message = "thought"
        self._state = "await_message"

    def _emit_thought(self, events: List[Event], text: str) -> None:
        # Drop a trailing harmony role preamble ("<|start|>assistant").
        cleaned = _RE_ROLE_PREAMBLE.sub("", text)
        cleaned = cleaned.replace("<|start|>", "").replace("<|end|>", "")
        if not cleaned.strip():
            if cleaned:
                # keep whitespace-only runs attached to following thought
                events.append(("thought", ""))
            return
        self.saw_thoughts = True
        events.append(("thought", cleaned))

    def _emit_answer(self, events: List[Event], text: str) -> None:
        if not self._answer_started:
            self._answer_started = True
            text = text.lstrip()
        if text:
            events.append(("answer", text))


def split_reasoning(text: str) -> Tuple[str, str]:
    """Split a complete model reply into ``(thought, answer)``.

    Markers are stripped from both parts. Plain replies come back as
    ``("", text)`` - including replies whose live deltas were streamed
    provisionally as thoughts but never confirmed by any marker.
    """
    parser = ReasoningStreamParser()
    events = [*parser.feed(text), *parser.finish()]
    thoughts: List[str] = []
    answers: List[str] = []
    for kind, part in events:
        if parser.final_state == "prologue":
            # No marker ever appeared: the entire reply is the answer.
            answers.append(part)
        elif kind == "thought":
            thoughts.append(part)
        else:
            answers.append(part)
    return "".join(thoughts).strip(), "".join(answers).strip()


def strip_markers(text: str) -> str:
    """Answer-only view of *text* (drops any thought block entirely)."""
    return split_reasoning(text)[1]


_RE_BOXED = re.compile(r"\\boxed\{([^{}]*)\}")

# Chat-template control tokens that degenerate generations scatter into
# otherwise-normal answers. None of these appear in legitimate prose.
_ARTIFACT_PATTERNS = [
    re.compile(r"</?s>", re.IGNORECASE),                     # <s> </s>
    re.compile(r"</?INST>", re.IGNORECASE),                  # <INST> </INST>
    re.compile(r"\[/?INST\]", re.IGNORECASE),                # [INST] [/INST]
    re.compile(r"\[/?SYS\]", re.IGNORECASE),                 # [SYS] [/SYS]
    re.compile(r"[<\\/{]{1,4}SYS[>]{1,3}", re.IGNORECASE),  # <<SYS>> <</SYS>> variants
    re.compile(r"<\|[^>|\n]{0,30}\|>"),                      # <|...|> specials
]


def _strip_artifacts(text: str) -> str:
    """Remove template tokens; drop lines that were nothing but junk."""
    out_lines: List[str] = []
    for raw_line in text.splitlines():
        cleaned = raw_line
        for pattern in _ARTIFACT_PATTERNS:
            cleaned = pattern.sub("", cleaned)
        if not cleaned.strip():
            if raw_line.strip():
                continue  # the whole line was template junk - remove it
            out_lines.append("")  # genuinely blank line - keep it
            continue
        out_lines.append(cleaned)
    return "\n".join(out_lines)


def format_answer(text: str) -> str:
    """Clean a complete answer string for display.

    Unwraps LaTeX ``\\boxed{...}`` (models love it, humans don't), strips
    stray chat-template tokens, trims outer whitespace and collapses 3+
    blank lines. Safe to apply to the full accumulated text on every
    stream update.
    """
    while True:
        replaced = _RE_BOXED.sub(r"\1", text)
        if replaced == text:
            break
        text = replaced
    text = _strip_artifacts(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
