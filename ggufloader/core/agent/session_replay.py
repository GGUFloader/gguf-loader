"""
SessionReplay - Replay agent sessions step by step for debugging.

Pattern from: SWE-agent trajectory replay + Aider conversation replay.
Enables replaying a complete agent session:
1. Load a recorded session
2. Step through each action
3. Inspect state at each step
4. Compare with original execution
5. Branch and modify (what-if analysis)

Use cases:
- Debug why the agent made a wrong decision
- Test if a different tool/parameter would have been better
- Create training examples from successful sessions
- Reproduce bugs from user reports
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReplayStep:
    """A single step in a replayed session."""
    index: int
    action: str  # "user_message", "tool_call", "tool_result", "agent_response"
    data: Dict[str, Any]
    timestamp: float = 0
    state_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "action": self.action,
            "data": self.data,
            "timestamp": self.timestamp,
            "state": self.state_snapshot,
        }


class ReplaySession:
    """A loaded session ready for replay."""

    def __init__(self, session_id: str, title: str = "") -> None:
        self.session_id = session_id
        self.title = title
        self.steps: List[ReplayStep] = []
        self.metadata: Dict[str, Any] = {}

    def add_step(self, action: str, data: Dict[str, Any],
                 state: Dict[str, Any] = None) -> ReplayStep:
        step = ReplayStep(
            index=len(self.steps),
            action=action,
            data=data,
            timestamp=time.time(),
            state_snapshot=state or {},
        )
        self.steps.append(step)
        return step

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReplaySession":
        session = cls(
            session_id=data.get("session_id", ""),
            title=data.get("title", ""),
        )
        session.metadata = data.get("metadata", {})
        for step_data in data.get("steps", []):
            step = ReplayStep(
                index=step_data.get("index", 0),
                action=step_data.get("action", ""),
                data=step_data.get("data", {}),
                timestamp=step_data.get("timestamp", 0),
                state_snapshot=step_data.get("state", {}),
            )
            session.steps.append(step)
        return session


class SessionReplay:
    """Replay agent sessions for debugging.

    Usage:
        replay = SessionReplay(workspace)

        # Record a session
        session = replay.create_session("debug_session")
        session.add_step("user_message", {"text": "Read README.md"})
        session.add_step("tool_call", {"tool": "read_file", "params": {"path": "README.md"}})
        session.add_step("tool_result", {"status": "success", "result": "..."})

        # Save
        replay.save_session(session)

        # Load and replay
        loaded = replay.load_session("debug_session.json")
        for step in loaded.steps:
            print(f"Step {step.index}: {step.action}")
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._replay_dir = workspace / ".gguf-replays"
        self._replay_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: Optional[ReplaySession] = None

    def create_session(self, session_id: str, title: str = "") -> ReplaySession:
        """Create a new replay session."""
        self._current_session = ReplaySession(session_id, title)
        return self._current_session

    def record_user_message(self, text: str) -> None:
        """Record a user message."""
        if self._current_session:
            self._current_session.add_step("user_message", {"text": text})

    def record_tool_call(self, tool: str, params: Dict[str, Any]) -> None:
        """Record a tool call."""
        if self._current_session:
            self._current_session.add_step("tool_call", {
                "tool": tool, "params": params,
            })

    def record_tool_result(self, tool: str, status: str, result: Any = None,
                           error: str = None) -> None:
        """Record a tool result."""
        data = {"tool": tool, "status": status}
        if error:
            data["error"] = error
        if result:
            data["result"] = str(result)[:500]
        if self._current_session:
            self._current_session.add_step("tool_result", data)

    def record_agent_response(self, response: str) -> None:
        """Record an agent response."""
        if self._current_session:
            self._current_session.add_step("agent_response", {"text": response[:500]})

    def record_state(self, state: Dict[str, Any]) -> None:
        """Update the state snapshot on the current step."""
        if self._current_session and self._current_session.steps:
            self._current_session.steps[-1].state_snapshot = state

    def save_session(self, session: ReplaySession = None) -> Path:
        """Save a session to disk."""
        session = session or self._current_session
        if not session:
            return None

        filename = f"{session.session_id}.json"
        filepath = self._replay_dir / filename
        filepath.write_text(
            json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Replay session saved: %s", filepath)
        return filepath

    def load_session(self, filename: str) -> Optional[ReplaySession]:
        """Load a session from disk."""
        filepath = self._replay_dir / filename
        if not filepath.exists():
            filepath = self._replay_dir / (filename + ".json")
        if not filepath.exists():
            return None
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return ReplaySession.from_dict(data)
        except Exception as e:
            logger.error("Failed to load replay session: %s", e)
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all saved replay sessions."""
        sessions = []
        for f in sorted(self._replay_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append({
                    "filename": f.name,
                    "session_id": data.get("session_id", ""),
                    "title": data.get("title", ""),
                    "steps": len(data.get("steps", [])),
                })
            except Exception:
                continue
        return sessions

    def get_step_at(self, session: ReplaySession, index: int) -> Optional[ReplayStep]:
        """Get a specific step by index."""
        if 0 <= index < len(session.steps):
            return session.steps[index]
        return None

    def get_state_at(self, session: ReplaySession, index: int) -> Dict[str, Any]:
        """Get the state snapshot at a specific step."""
        step = self.get_step_at(session, index)
        if step:
            return step.state_snapshot
        return {}

    def compare_sessions(self, session_a: ReplaySession,
                         session_b: ReplaySession) -> Dict[str, Any]:
        """Compare two replay sessions."""
        steps_a = len(session_a.steps)
        steps_b = len(session_b.steps)

        actions_a = [s.action for s in session_a.steps]
        actions_b = [s.action for s in session_b.steps]

        # Find divergence point
        divergence = 0
        for i, (a, b) in enumerate(zip(actions_a, actions_b)):
            if a != b:
                divergence = i
                break

        return {
            "session_a": {"id": session_a.session_id, "steps": steps_a},
            "session_b": {"id": session_b.session_id, "steps": steps_b},
            "step_diff": steps_b - steps_a,
            "divergence_point": divergence,
            "identical_prefix": divergence,
        }

    def export_as_markdown(self, session: ReplaySession) -> str:
        """Export a session as readable markdown."""
        lines = [
            f"# Replay: {session.title or session.session_id}",
            f"Steps: {len(session.steps)}",
            "",
        ]

        for step in session.steps:
            action = step.action
            data = step.data

            if action == "user_message":
                lines.append(f"## 👤 User")
                lines.append(f"{data.get('text', '')}")
            elif action == "tool_call":
                lines.append(f"## 🔧 Tool Call: {data.get('tool', '')}")
                lines.append(f"Params: {json.dumps(data.get('params', {}), indent=2)}")
            elif action == "tool_result":
                status = data.get("status", "")
                icon = "✅" if status == "success" else "❌"
                lines.append(f"## {icon} Result: {data.get('tool', '')}")
                result = data.get("result") or data.get("error", "")
                lines.append(f"```{result[:300]}```")
            elif action == "agent_response":
                lines.append(f"## 🤖 Agent")
                lines.append(f"{data.get('text', '')}")

            lines.append("")

        return "\n".join(lines)
