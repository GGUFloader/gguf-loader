"""
SessionExport - Export and replay agent sessions.

Pattern from: SWE-agent trajectory export + Aider conversation export.
Exports the full agent session as structured JSON that can be:
1. Shared with others for debugging
2. Imported into a new session
3. Analyzed for performance metrics
4. Used as few-shot examples

Features:
- Export full session with messages, tool calls, timing, costs
- Import/export as JSON
- Replay mode (re-execute tool calls)
- Markdown export for human readability
- Session comparison (diff two sessions)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionExport:
    """Export and replay agent sessions.

    Usage:
        exporter = SessionExport(workspace)

        # Export current session
        json_str = exporter.export_json(session_data)
        exporter.save(session_data, "session_2024-01-01.json")

        # Import a session
        data = exporter.load("session_2024-01-01.json")

        # Export as markdown
        md = exporter.export_markdown(session_data)
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._export_dir = workspace / ".gguf-sessions"
        self._export_dir.mkdir(parents=True, exist_ok=True)

    def export_json(self, session: Dict[str, Any]) -> str:
        """Export a session as formatted JSON string."""
        export_data = self._prepare_export(session)
        return json.dumps(export_data, indent=2, ensure_ascii=False)

    def save(self, session: Dict[str, Any], filename: str = None) -> Path:
        """Save a session to disk.

        Args:
            session: Session data dict
            filename: Override filename (auto-generated if None)

        Returns:
            Path to saved file.
        """
        if filename is None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            title = (session.get("title") or "session").replace(" ", "_")[:30]
            filename = f"{title}_{ts}.json"

        filepath = self._export_dir / filename
        export_data = self._prepare_export(session)
        filepath.write_text(
            json.dumps(export_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Session exported to %s", filepath)
        return filepath

    def load(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load a session from disk."""
        filepath = self._export_dir / filename
        if not filepath.exists():
            # Try without extension
            filepath = self._export_dir / (filename + ".json")
        if not filepath.exists():
            return None
        try:
            return json.loads(filepath.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to load session: %s", e)
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all exported sessions."""
        sessions = []
        for f in sorted(self._export_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append({
                    "filename": f.name,
                    "title": data.get("title", ""),
                    "timestamp": data.get("exported_at", ""),
                    "message_count": len(data.get("messages", [])),
                    "tool_calls": sum(
                        len(m.get("tool_calls", []))
                        for m in data.get("messages", [])
                    ),
                })
            except Exception:
                continue
        return sessions

    def export_markdown(self, session: Dict[str, Any]) -> str:
        """Export a session as human-readable markdown."""
        lines = [
            f"# Session: {session.get('title', 'Untitled')}",
            "",
            f"Exported: {time.strftime('%Y-%m-%d %H:%M')}",
            f"Mode: {session.get('mode', 'chat')}",
            f"Model: {session.get('model', 'unknown')}",
            "",
            "---",
            "",
        ]

        for msg in session.get("messages", []):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "user":
                lines.append(f"## User")
                lines.append("")
                lines.append(content)
                lines.append("")
            elif role == "assistant":
                lines.append(f"## Assistant")
                lines.append("")
                lines.append(content)
                lines.append("")
            elif role == "tool":
                tool_name = msg.get("tool_name", "tool")
                status = msg.get("status", "unknown")
                lines.append(f"### Tool: {tool_name} ({status})")
                lines.append("")
                result = msg.get("result", "")
                if result:
                    lines.append(f"```")
                    lines.append(str(result)[:1000])
                    lines.append(f"```")
                lines.append("")

        return "\n".join(lines)

    def get_session_stats(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Get statistics about a session."""
        messages = session.get("messages", [])
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        tool_msgs = [m for m in messages if m.get("role") == "tool"]

        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        total_tool_calls = sum(len(m.get("tool_calls", [])) for m in messages)

        return {
            "total_messages": len(messages),
            "user_messages": len(user_msgs),
            "assistant_messages": len(assistant_msgs),
            "tool_results": len(tool_msgs),
            "total_tool_calls": total_tool_calls,
            "total_characters": total_chars,
            "estimated_tokens": total_chars // 4,
        }

    def compare_sessions(self, session_a: Dict[str, Any],
                         session_b: Dict[str, Any]) -> Dict[str, Any]:
        """Compare two sessions and show differences."""
        stats_a = self.get_session_stats(session_a)
        stats_b = self.get_session_stats(session_b)

        return {
            "session_a": {
                "title": session_a.get("title", ""),
                "stats": stats_a,
            },
            "session_b": {
                "title": session_b.get("title", ""),
                "stats": stats_b,
            },
            "diff": {
                "message_diff": stats_b["total_messages"] - stats_a["total_messages"],
                "tool_call_diff": stats_b["total_tool_calls"] - stats_a["total_tool_calls"],
                "token_diff": stats_b["estimated_tokens"] - stats_a["estimated_tokens"],
            },
        }

    def _prepare_export(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare session data for export."""
        return {
            "version": 1,
            "title": session.get("title", ""),
            "mode": session.get("mode", "chat"),
            "model": session.get("model", ""),
            "workspace": str(self.workspace),
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "messages": session.get("messages", []),
            "stats": self.get_session_stats(session),
        }
