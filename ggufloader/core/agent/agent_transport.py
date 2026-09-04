"""
AgentTransport — adapter between the agent's callback interface and
a concrete transport (WebSocket, CLI, gRPC).

Extracted from the 150+ lines of callback definitions inside
handler.py's handle_agent_start.  The transport owns:
  - Phase classification from status strings
  - Progress event emission (announce, tool_call, tool_result, step_complete)
  - Approval flow management (send request, wait for response)
  - Token forwarding

This makes the agent testable without a running WebSocket — just inject
a mock transport.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable

from .tool_registry import tool_content_for_context

logger = logging.getLogger(__name__)


@runtime_checkable
class Transport(Protocol):
    """Minimal transport interface for the agent."""

    def send_event(self, event: dict) -> None:
        """Send a typed event to the frontend."""
        ...


class AgentTransport:
    """Bridges agent callbacks to a concrete transport.

    Parameters
    ----------
    transport : Transport
        The underlying transport (WebSocket wrapper, mock, etc.).
    loop : asyncio.AbstractEventLoop
        Event loop for scheduling async sends from sync callbacks.
    message_id : str
        Unique ID for the current agent run.
    preset_id : str
        Agent preset identifier.
    """

    def __init__(
        self,
        transport: Transport,
        loop: asyncio.AbstractEventLoop,
        message_id: str,
        preset_id: str = "full_stack",
    ) -> None:
        self._transport = transport
        self._loop = loop
        self.message_id = message_id
        self.preset_id = preset_id

    # ── Callback factories ──────────────────────────────────────────────

    def make_status_callback(self) -> Callable[[str], None]:
        """Return an on_status callback suitable for GraphAgent.process()."""
        def on_status(msg: str) -> None:
            self._handle_status(msg)
        return on_status

    def make_tool_callback(self) -> Callable[[Dict[str, Any]], None]:
        """Return an on_tool callback suitable for GraphAgent.process()."""
        def on_tool(result: dict) -> None:
            # Tool payloads live under 'result' (never 'content'); the canonical
            # formatter renders list/str payloads into model- and UI-visible text.
            payload = tool_content_for_context(result, max_chars=500)
            if payload is None:
                payload = result.get("content", result.get("error", ""))
            text = str(payload)
            self._send({
                "type": "tool_result",
                "message_id": self.message_id,
                "tool": result.get("tool_name", "unknown"),
                "success": result.get("status") == "success",
                # Bounded for the UI card, but always signal the cut so a
                # truncated directory listing cannot read as the full list.
                "result": (text[:497] + "…") if len(text) > 500 else text,
                "call_id": result.get("call_id", ""),
            })
        return on_tool

    def make_token_callback(self) -> Callable[[str], None]:
        """Return an on_token callback suitable for GraphAgent.process().

        The tuned 12B occasionally opens its prose answer with a tool-call
        envelope (``{"tool_calls": []}`` — bare or fenced) before the real
        text, even though the answer prompt forbids JSON. The final answer is
        scrubbed end-to-end too, but a live stream would still flash the
        envelope while the answer is typing. This stateful filter buffers the
        start of the stream, drops the envelope (and any fence around it) as
        soon as it is recognized, and passes the remaining prose straight
        through. Prose that never starts with ``{`` is never delayed.
        """
        state = {"buf": "", "passthrough": False, "just_dropped": False}

        def _find_envelope_end(s: str) -> Optional[int]:
            """Return the index just past the first balanced JSON object
            starting at the first ``{`` in *s*, else None. String-aware:
            braces inside quoted strings are ignored."""
            start = s.find("{")
            if start < 0:
                return None
            depth = 0
            in_str = False
            esc = False
            i = start
            while i < len(s):
                c = s[i]
                if in_str:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        in_str = False
                elif c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return i + 1
                i += 1
            return None

        def on_token(chunk: str) -> None:
            if state["passthrough"]:
                if state["just_dropped"]:
                    # Clean the blank line that often follows the dropped
                    # envelope before the prose begins.
                    chunk = chunk.lstrip("\n").lstrip()
                    state["just_dropped"] = False
                    if not chunk:
                        return
                self._send({"type": "token", "token": chunk,
                            "message_id": self.message_id})
                return
            state["buf"] += chunk
            s = state["buf"]
            if not s.lstrip().startswith("{") and "{" not in s:
                # No envelope shape at all: once we have enough text to be
                # sure, release everything and stream freely from here on.
                if len(s) >= 32:
                    state["passthrough"] = True
                    if s:
                        self._send({"type": "token", "token": s,
                                    "message_id": self.message_id})
                return
            end = _find_envelope_end(s)
            if end is None:
                # Still inside a possible envelope - hold a little longer, but
                # never stall the stream on malformed output.
                if len(s) > 2000:
                    state["passthrough"] = True
                    if s:
                        self._send({"type": "token", "token": s,
                                    "message_id": self.message_id})
                return
            obj_text = s[s.find("{"):end]
            rest = s[end:]
            try:
                import json as _json
                obj = _json.loads(obj_text)
                is_envelope = isinstance(obj, dict) and "tool_calls" in obj
            except (ValueError, TypeError):
                is_envelope = False
            if not is_envelope:
                state["passthrough"] = True
                if s:
                    self._send({"type": "token", "token": s,
                                "message_id": self.message_id})
                return
            # Envelope confirmed: drop it plus any trailing fence, then
            # stream the remaining prose live from here on.
            rest = rest.lstrip()
            if rest.startswith("```"):
                nl = rest.find("\n")
                rest = rest[nl + 1:].lstrip() if nl != -1 else ""
            state["passthrough"] = True
            if rest:
                self._send({"type": "token", "token": rest,
                            "message_id": self.message_id})
            else:
                state["just_dropped"] = True

        return on_token

    def make_reasoning_callback(self) -> Callable[[str], None]:
        """Return an on_plan_stream callback: live planner deltas shown as a
        'thinking' progress step while "Planning..." is on screen.

        The planner's raw output may start with a markdown fence
        (`````json```) — strip the fence so the card shows the plan itself.
        """
        state = {"prefix": True, "buf": ""}

        def on_reasoning(chunk: str) -> None:
            if not state["prefix"]:
                self._send({
                    "type": "reasoning",
                    "content": chunk,
                    "message_id": self.message_id,
                })
                return
            # Keep buffering until the JSON plan starts or it's clear the
            # model is producing prose (no '{' within 64 chars).
            state["buf"] += chunk
            idx = state["buf"].find("{")
            if idx >= 0:
                state["prefix"] = False
                rest = state["buf"][idx:]
                state["buf"] = ""
                if rest:
                    self._send({
                        "type": "reasoning",
                        "content": rest,
                        "message_id": self.message_id,
                    })
            elif len(state["buf"]) > 64:
                state["prefix"] = False
                text = state["buf"]
                state["buf"] = ""
                if text:
                    self._send({
                        "type": "reasoning",
                        "content": text,
                        "message_id": self.message_id,
                    })

        return on_reasoning

    def make_approval_callback(self, workspace: str = ".") -> Callable[[Dict[str, Any]], bool]:
        """Return an on_approval callback that blocks the agent thread."""
        def on_approval(payload: dict) -> bool:
            return self._handle_approval(payload, workspace)
        return on_approval

    # ── Status handling ─────────────────────────────────────────────────

    def _handle_status(self, msg: str) -> None:
        """Classify status message and emit appropriate progress events."""
        from ggufloader.api.routes.agent import update_plan_state

        # Phase classification
        phase = None
        if msg.startswith("...") or msg.startswith("[target]"):
            phase = "goal"
        elif msg.startswith("[checklist]"):
            phase = "plan"
        elif msg.startswith(">") or msg.startswith("->"):
            phase = "execute"
        elif msg.startswith("[search]"):
            phase = "verify"
        elif msg.startswith("[ok]") or msg.startswith("[reading]"):
            phase = "continue"
        elif msg.startswith("[note]"):
            phase = "finish"

        # Plan step parsing
        plan_step = None
        if msg.startswith("> Step "):
            m = re.match(r"> Step (\d+)/(\d+): (.+)", msg)
            if m:
                plan_step = {
                    "current": int(m.group(1)),
                    "total": int(m.group(2)),
                    "description": m.group(3),
                }

        # Legacy agent_phase event
        event: Dict[str, Any] = {
            "type": "agent_phase",
            "message_id": self.message_id,
            "status": msg,
            "preset": self.preset_id,
        }
        if phase:
            event["phase"] = phase
        if plan_step:
            event["plan_step"] = plan_step
        self._send(event)
        update_plan_state(phase=phase or "idle", plan_step=plan_step)

        # Progress events for StepProgressPanel
        stripped = msg.strip()
        if not stripped:
            return

        if stripped.startswith("...") or stripped.startswith("[!]"):
            clean = stripped.lstrip("...[!]...[checklist][search][ok][note][target]>>  \n")
            if clean:
                self._send({"type": "progress_announce", "content": clean})
        elif re.match(r"^\[\d+/\d+\]", stripped) or stripped.startswith("-> "):
            tool_desc = re.sub(r"^\[\d+/\d+\]\s*", "", stripped).lstrip("-> ")
            self._send({
                "type": "progress_tool_call",
                "name": tool_desc.split(" ")[0] if tool_desc else "tool",
                "content": tool_desc,
            })
        elif stripped.startswith("[ok]") or stripped.startswith("  [ok]"):
            self._send({
                "type": "progress_tool_result",
                "content": stripped.lstrip("[ok] "),
                "success": True,
            })
        elif stripped.startswith("[FAIL]") or stripped.startswith("  [FAIL]"):
            self._send({
                "type": "progress_tool_result",
                "content": stripped.lstrip("[FAIL] "),
                "success": False,
            })
        elif stripped.startswith("[lock]"):
            self._send({"type": "progress_announce", "content": stripped})
        elif stripped.startswith("> Step "):
            self._send({"type": "progress_step_complete", "content": stripped})
        elif stripped.startswith("Plan") or stripped.startswith("All plan") or stripped.startswith("Verif"):
            self._send({"type": "progress_step_complete", "content": stripped})
        # Bare "Step N/M" counters (no "> " prefix) are legacy reactive-loop
        # messages whose total is max_steps, not the plan length. The plan
        # length is the only valid total, so suppress these to avoid showing
        # e.g. "Step 1/12" when the plan has 3 steps. A bare "Step N"
        # (no denominator) is fine — it carries no misleading total.
        elif re.match(r"^Step \d+/\d+$", stripped):
            pass
        else:
            self._send({"type": "progress_announce", "content": stripped})

    # ── Approval flow ───────────────────────────────────────────────────

    def _handle_approval(self, payload: dict, workspace: str) -> bool:
        """Block agent thread, send approval request, wait for response.

        This bridges the sync agent thread with the async WebSocket.
        """
        from ggufloader.api.websocket.handler import get_approval_manager

        mgr = get_approval_manager()
        call_id = f"approval_{int(time.time() * 1000)}"
        event = asyncio.Event()
        mgr.register(call_id, event)

        call = payload.get("call", {})
        self._send({
            "type": "tool_approval",
            "id": call_id,
            "tool": call.get("tool", "unknown"),
            "args": call.get("parameters", {}),
            "description": payload.get("description", ""),
            "workspace": payload.get("workspace", workspace),
        })

        # Block agent thread until frontend responds (max 120s)
        try:
            event.wait(timeout=120)
        except Exception:
            pass

        approved = mgr.resolve(call_id, False)
        return approved

    # ── Helpers ─────────────────────────────────────────────────────────

    def _send(self, event: dict) -> None:
        """Send event via the transport, scheduling from sync context."""
        try:
            loop = self._loop
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._transport.send_event(event), loop
                )
            else:
                loop.run_until_complete(self._transport.send_event(event))
        except Exception as e:
            logger.debug("Transport send failed: %s", e)
