"""
AgentBridge - Connect agent engine to MainWindow UI.

Pattern from: OpenHands event bus + Aider's IO layer.
Bridges the gap between the pure-Python agent engine (no Qt) and
the PySide6 UI by:
1. Running agent steps on a worker thread
2. Forwarding status/tool/approval events to UI signals
3. Handling user input (approvals, stop requests)
4. Managing agent lifecycle (start, stop, resume)
5. Recording sessions for replay
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .agent_engine import AgentEngine
from .presets import AgentPreset, PresetManager
from .session_replay import SessionReplay
from .tool_analytics import ToolAnalytics
from .error_patterns import ErrorPatternDetector
from .hooks import Hooks, HookPoint

logger = logging.getLogger(__name__)


class AgentBridge:
    """Bridge between AgentEngine and MainWindow UI.

    Usage:
        bridge = AgentBridge(engine, workspace)

        # Wire UI callbacks
        bridge.on_status = lambda msg: chat_panel.add_system_message(msg)
        bridge.on_tool = lambda result: agent_panel.add_tool_card(result)
        bridge.on_approval = lambda payload: show_approval_dialog(payload)
        bridge.on_response = lambda text: chat_panel.add_ai_message(text)

        # Process a user message
        bridge.process_message("Read README.md")
    """

    def __init__(self, engine: AgentEngine, workspace: Path) -> None:
        self._engine = engine
        self._workspace = workspace
        self._replay = SessionReplay(workspace)
        self._tool_analytics = ToolAnalytics()
        self._error_patterns = ErrorPatternDetector(workspace)
        self._hooks = Hooks()
        self._preset_mgr = PresetManager()

        # UI callbacks (set by MainWindow)
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_tool: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_approval: Optional[Callable[[Dict[str, Any]], Any]] = None
        self.on_response: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_token: Optional[Callable[[str], None]] = None
        self.on_finished: Optional[Callable[[Dict[str, Any]], None]] = None

        # State
        self._running = False
        self._worker: Optional[threading.Thread] = None
        self._current_preset: Optional[AgentPreset] = None
        self._abort_requested = False

    @property
    def is_running(self) -> bool:
        return self._running

    def set_preset(self, preset_id: str) -> bool:
        """Set the agent preset for the next message."""
        preset = self._preset_mgr.get(preset_id)
        if preset:
            self._current_preset = preset
            self._apply_preset(preset)
            return True
        return False

    def _apply_preset(self, preset: AgentPreset) -> None:
        """Apply preset settings to the engine."""
        self._engine.max_steps = preset.max_steps
        self._engine.max_tokens = preset.max_tokens
        self._engine._reflection_enabled = preset.reflection_enabled

    def process_message(self, message: str, workspace: str = None) -> None:
        """Process a user message on a worker thread.

        This is the main entry point from the UI.
        """
        if self._running:
            return

        self._running = True
        self._abort_requested = False

        # Record replay
        self._replay.record_user_message(message)

        # Fire hooks
        ctx = self._hooks.execute(HookPoint.BEFORE_MESSAGE, {"text": message})
        if ctx.result.value == "block":
            self._emit_status("⚠️ Message blocked by hook")
            self._running = False
            return

        # Start worker thread
        self._worker = threading.Thread(
            target=self._run_agent,
            args=(message,),
            daemon=True,
        )
        self._worker.start()

    def _run_agent(self, message: str) -> None:
        """Run the agent on a worker thread."""
        try:
            # Update engine workspace if changed
            if message.startswith("/workspace "):
                new_workspace = message.split(" ", 1)[1].strip()
                self._emit_status(f"📁 Workspace: {new_workspace}")
                self._running = False
                return

            # Process through engine
            result = self._engine.process(
                user_message=message,
                on_status=self._on_status,
                on_tool=self._on_tool,
                on_approval=self._on_approval,
            )

            # Record tool analytics
            for tool_result in result.get("tool_results", []):
                self._tool_analytics.record(
                    tool_result.get("tool_name", ""),
                    {},
                    "success" if tool_result.get("status") == "success" else "error",
                )

            # Record replay
            self._replay.record_agent_response(result.get("response", ""))
            self._replay.record_state({
                "total_tokens": self._engine._total_tokens,
                "steps": self._engine._total_llm_calls,
            })

            # Fire hooks
            self._hooks.execute(HookPoint.AFTER_RESPONSE, {"result": result})

            # Emit response
            response = result.get("response", "")
            if response and self.on_response:
                self.on_response(response)

            if self.on_finished:
                self.on_finished(result)

        except Exception as e:
            logger.error("Agent bridge error: %s", e)
            if self.on_error:
                self.on_error(str(e))

        finally:
            self._running = False
            self._tool_analytics.end_step()

    def _on_status(self, msg: str) -> None:
        """Forward status to UI."""
        if self.on_status:
            self.on_status(msg)
        # Record in replay
        if msg:
            self._replay.record_tool_call("status", {"message": msg})

    def _on_tool(self, result: Dict[str, Any]) -> None:
        """Forward tool results to UI."""
        tool = result.get("tool_name", "")
        status = "success" if result.get("status") == "success" else "error"

        # Record analytics
        self._tool_analytics.record(tool, {}, status)

        # Record error patterns
        if status == "error":
            error_msg = result.get("error", "")
            self._error_patterns.record_error(
                "unknown", error_msg, tool=tool,
            )

        # Record replay
        self._replay.record_tool_result(tool, status, result.get("result"))

        # Forward to UI
        if self.on_tool:
            self.on_tool(result)

        # Fire hooks
        self._hooks.execute(HookPoint.AFTER_TOOL_CALL, {
            "tool": tool, "result": result,
        })

    def _on_approval(self, payload: Dict[str, Any]) -> bool:
        """Handle approval request (blocking the agent thread)."""
        if self.on_approval:
            return self.on_approval(payload)
        return True  # default: approve

    def stop(self) -> None:
        """Request the agent to stop."""
        self._abort_requested = True
        self._engine.request_abort("User requested stop")
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=3)
        self._running = False

    def get_tool_stats(self) -> Dict[str, Any]:
        """Get tool usage analytics."""
        return self._tool_analytics.get_stats()

    def get_error_patterns(self) -> List[Dict[str, Any]]:
        """Get detected error patterns."""
        return [p.to_dict() for p in self._error_patterns.get_patterns()]

    def get_suggestions(self) -> List[str]:
        """Get tool optimization suggestions."""
        return self._tool_analytics.get_suggestions()

    def get_presets(self) -> List[Dict[str, str]]:
        """Get available presets for UI display."""
        return self._preset_mgr.get_summary()

    def register_hook(self, hook_id: str, point: HookPoint,
                      fn: Callable, priority: int = 0) -> None:
        """Register a lifecycle hook."""
        self._hooks.register(hook_id, point, fn, priority)

    def save_replay(self) -> None:
        """Save the current session replay."""
        self._replay.save_session()

    def get_replay_sessions(self) -> List[Dict[str, Any]]:
        """Get list of saved replay sessions."""
        return self._replay.list_sessions()

    def get_health(self) -> Dict[str, Any]:
        """Get health status of all subsystems."""
        return {
            "engine": "ok" if self._engine else "uninitialized",
            "running": self._running,
            "preset": self._current_preset.name if self._current_preset else "default",
            "tool_stats": self._tool_analytics.get_stats(),
            "errors": self._error_patterns.get_stats(),
            "hooks": self._hooks.get_stats(),
        }
