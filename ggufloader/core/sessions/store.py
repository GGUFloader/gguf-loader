"""Session persistence for GGUF Loader chats.

One JSON file per conversation under the ``chats`` directory (see
``ggufloader.config.get_paths``). Pure Python - no Qt, no llama - so the
store is fully testable headless.

Schema (version 1):

    {
      "version": 1,
      "id": "20260825-142233-a1b2c3",
      "title": "Help me refactor the loader" | null,
      "created": ISO timestamp,
      "updated": ISO timestamp,
      "mode": "chat" | "agent",
      "workspace": str | null,
      "messages": [
        {"role": "user" | "assistant", "content": str, "ts": ts},
        {"role": "tool", "tool_result": {...}, "ts": ts}
      ]
    }

Writes are atomic (temp file + os.replace) so a crash never truncates a
session file.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
TITLE_MAX_CHARS = 40


def _now() -> str:
    # Millisecond precision keeps list ordering deterministic when several
    # sessions are saved within the same second.
    return datetime.now().isoformat(timespec="milliseconds")


def derive_title(text: str, max_chars: int = TITLE_MAX_CHARS) -> str:
    """First line of *text*, truncated to ~max_chars at a word boundary."""
    first_line = text.strip().splitlines()[0].strip() if text.strip() else ""
    if len(first_line) <= max_chars:
        return first_line
    cut = first_line[: max_chars + 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-").rstrip()


class SessionStore:
    """Creates, loads, saves and lists chat session files."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def create(self, mode: str = "chat", workspace: Optional[str] = None) -> Dict[str, Any]:
        """Build an unsaved in-memory session; call :meth:`save` to persist."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        session_id = f"{stamp}-{secrets.token_hex(3)}"
        now = _now()
        return {
            "version": SCHEMA_VERSION,
            "id": session_id,
            "title": None,
            "created": now,
            "updated": now,
            "mode": mode,
            "workspace": workspace,
            "messages": [],
        }

    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return the session dict, or None when missing/corrupt."""
        path = self._path_for(session_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except Exception as e:  # noqa: BLE001 - any decode error => corrupt
            logger.warning("Corrupt session file %s: %s", path.name, e)
            return None
        if not isinstance(data, dict) or not data.get("id"):
            return None
        return data

    def save(self, session: Dict[str, Any]) -> None:
        """Atomically persist *session* and bump its ``updated`` stamp."""
        session["updated"] = _now()
        session.setdefault("version", SCHEMA_VERSION)
        path = self._path_for(session["id"])
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(
                json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(tmp, path)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def delete(self, session_id: str) -> bool:
        """Remove the session file; True when something was deleted."""
        path = self._path_for(session_id)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False

    def rename(self, session_id: str, title: str) -> bool:
        """Set a new title on the stored session."""
        session = self.load(session_id)
        if session is None:
            return False
        title = title.strip()
        session["title"] = title or None
        self.save(session)
        return True

    def append_message(self, session: Dict[str, Any], role: str, content: str) -> None:
        """Append a user/assistant message to an in-memory session."""
        session["messages"].append({"role": role, "content": content, "ts": _now()})
        if role == "user" and not session.get("title"):
            session["title"] = derive_title(content)

    def append_tool_result(self, session: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Append a tool event (persisted for transcript replay)."""
        session["messages"].append({"role": "tool", "tool_result": result, "ts": _now()})

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------
    def list_sessions(self) -> List[Dict[str, Any]]:
        """Metadata for every session file, newest activity first.

        Corrupt files yield ``{"corrupt": True, "id": ..., "error": ...}``
        entries instead of raising.
        """
        out: List[Dict[str, Any]] = []
        for path in self.root.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                out.append({
                    "id": data["id"],
                    "title": data.get("title"),
                    "updated": data.get("updated", ""),
                    "mode": data.get("mode", "chat"),
                })
            except Exception as e:  # noqa: BLE001 - corrupt file, keep listing
                out.append({
                    "corrupt": True,
                    "id": path.stem,
                    "error": str(e),
                    "updated": "",
                })
        out.sort(key=lambda meta: meta.get("updated", ""), reverse=True)
        return out

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _path_for(self, session_id: str) -> Path:
        # Guard against path traversal via crafted ids.
        safe = Path(session_id).name
        if safe != session_id or not session_id:
            raise ValueError(f"Invalid session id: {session_id!r}")
        return self.root / f"{safe}.json"
