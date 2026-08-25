# Chat Sessions Design (ChatGPT-style persistence)

Date: 2026-08-25
Status: Approved

## Goal

Persist chat conversations as switchable sessions, like ChatGPT:

- Every conversation auto-saves; no manual save step.
- A sidebar "Chats" section lists sessions with a New Chat button.
- Users can rename and delete sessions.
- Restarting the app reopens the most recently active session.
- Covers both normal chat and Agent Mode conversations.

Non-goals: cross-session full-text search, cloud sync, session folders,
multi-model-per-session tracking.

## Storage

One JSON file per session under the existing `chats` path from
`ggufloader.config.get_paths()` (per-user data dir in frozen deployments).

File name: `<id>.json` where `id = YYYYmmdd-HHMMSS-<6 hex random>`.

Schema:

```json
{
  "version": 1,
  "id": "20260825-142233-a1b2c3",
  "title": "Help me refactor the loader",
  "created": "2026-08-25T14:22:33",
  "updated": "2026-08-25T14:25:01",
  "mode": "chat",
  "workspace": null,
  "messages": [
    {"role": "user", "content": "...", "ts": "..."},
    {"role": "assistant", "content": "...", "ts": "..."}
  ]
}
```

Rules:

- `mode` is `"chat"` or `"agent"`. `workspace` is set only for agent
  sessions.
- Tool activity in agent sessions is persisted as messages with
  `"role": "tool"` and the full result dict in `"tool_result"`, so
  transcripts can be replayed as tool cards. Status lines are not
  persisted.
- Title: `null` until the first user message, then the first ~40
  characters of that message. An explicit rename overwrites permanently
  (stored as-is afterwards).
- Writes are atomic: write `<id>.json.tmp`, then `os.replace`.

## SessionStore (`ggufloader/core/sessions/store.py`)

Pure Python; no Qt or llama imports (headless-testable). All methods
synchronous; MainWindow calls it on the main thread (file I/O per
exchange is tiny).

```python
class SessionStore:
    def __init__(self, root: Path): ...          # root = chats dir
    def create(self, mode: str, workspace: str | None = None) -> dict
    def load(self, session_id: str) -> dict | None    # None if missing/corrupt
    def save(self, session: dict) -> None             # atomic, bumps updated
    def delete(self, session_id: str) -> bool
    def list_sessions(self) -> list[dict]             # metadata, newest first
    def rename(self, session_id: str, title: str) -> bool
```

- `list_sessions()` returns `{id, title, updated, mode}` sorted by
  `updated` descending. Corrupt files yield a `{"corrupt": True, "id":
  ..., "error": ...}` entry instead of raising.
- `derive_title(text)` helper: first user message -> up to 40 chars at a
  word boundary.

## Sidebar UI (`ggufloader/ui/sidebar_panel.py`)

New collapsible-style section "💬 Chats" in `SettingsSidebar`:

- "＋ New Chat" button.
- `QListWidget`: one row per session — title (or "New Chat"), relative
  time (e.g. "5m", "2h", "3d"), mode badge (🤖 for agent). Active
  session highlighted/selected.
- Right-click context menu on a row: Rename…, Delete (with confirm).
- The panel stays dumb. New signals:

```python
new_chat_requested = Signal()
session_selected = Signal(str)        # session id
session_rename_requested = Signal(str)
session_delete_requested = Signal(str)
```

MainWindow performs store operations and calls back
`sidebar.set_sessions(list, active_id)` to refresh the list.

## MainWindow wiring

State: `self._sessions = SessionStore(...)`, `self._current_session_id`,
`self._renamed_ids: set[str]` (titles manually set are never re-derived).

Normal chat flow (`_send_message`):

1. If no current session: `store.create("chat")`.
2. Append and save the user message immediately (a crash mid-generation
   keeps what was asked); save again when generation finishes with the
   assistant reply; update title if still `None`.
3. `clear_chat` menu item clears the current session's messages and
   saves it.

Agent flow:

- Activating Agent Mode attaches agent turns to the current session: if
  none is open, create one with `mode="agent"`,
  `workspace=<combo value>`; otherwise set that session's
  `mode="agent"` and `workspace` fields (the same conversation simply
  gains tool abilities, matching how the transcript already shares one
  panel).
- Per turn: append user message, then assistant answer and each tool
  result as messages; save after the turn completes.
- Reopening an agent session switches Agent Mode ON, sets the workspace
  combo, and re-initializes the engine for that workspace. GraphAgent's
  thread id derives from the workspace, so its LangGraph SQLite
  checkpoint resumes the agent's memory automatically.

Switching sessions:

1. Stop running work: `chat_service` cancel + `_agent_service.stop()`.
2. Persist current state if dirty; load target session.
3. Re-render: chat sessions replay `messages` as bubbles; agent
   sessions additionally render `"role": "tool"` entries via
   `AgentPanel.add_tool_card`. Restore `conversation_history` from
   user/assistant messages so model context continues.

New Chat button: persist nothing new (already auto-saved), clear both
panels, reset `conversation_history`, show welcome empty state;
`_current_session_id = None`. The next sent message lazily creates the
session.

Startup (`MainWindow.__init__` tail):

- Sessions = store list. If any exist: open the newest (`updated`
  max). Else: fresh welcome state. Model loading is unaffected. A
  restored agent session shows its transcript and agent controls
  immediately; the engine itself initializes through the existing lazy
  path once a model is loaded.

Clear Chat menu item: empties the *current* session (messages cleared,
saved). The session stays in the list with its title.

## Error handling

- Corrupt/unreadable session file: listed with ⚠ prefix, not selectable;
  Delete works on it. Loading never raises into the UI.
- Write failure (disk full, permissions): log error, surface one system
  message in the chat panel ("⚠ Failed to save chat session"), keep the
  in-memory conversation usable.
- Deleting the active session behaves like New Chat (empty state).
- Switching while generating is safe because generation is stopped first.

## Testing (`tests/unit/test_session_store.py` + wiring tests)

Headless pytest (no Qt required):

- create/save/load round-trip preserves schema and timestamps.
- `list_sessions` ordering by `updated`; corrupt file → corrupt entry,
  no exception.
- delete removes file; rename persists and sets renamed flag semantics.
- atomic write leaves no `.tmp` residue; save over existing keeps same id.
- `derive_title`: truncation at word boundary, short input passthrough.

UI wiring smoke tests use offscreen Qt where practical (following
existing test conventions); core logic tests remain Qt-free.
