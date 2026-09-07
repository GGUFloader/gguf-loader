# Agent UI Deep Comparison — Source-Code Verified

> **📜 Historical document** — describes GGUF Loader at an earlier stage of the
> project and is kept for reference. The current build is a **single-model
> (Gemma 4 12B Q4_K_M)** agent app with a **React/TypeScript frontend and
> FastAPI backend**, running a strictly **plan-driven LangGraph agent** (no
> reactive loop, no multi-model family tuning). UI and architecture details
> below may be outdated.

> Based on reading actual source code from: aider/aider/io.py (1191 LOC),
> aider/commands.py (1712 LOC), sweagent/inspector_cli.py (493 LOC),
> sweagent/inspector/server.py (354 LOC), openhands/src/components (React),
> deepseek-harness/packages/client/ui-chat (React), and
> ggufloader/ui/chat_panel.py (570 LOC).

---

## 1. WHAT EACH HARNESS ACTUALLY DOES (Source-Verified)

### 1.1 Aider — The Gold Standard for Terminal UI

**Source: `aider/io.py` (1191 LOC)**

Aider's IO class is the most sophisticated terminal UI in the agent space:

```python
# Core IO class (aider/io.py)
class IO:
    def __init__(self, ...):
        self.console = Console()           # Rich console for colored output
        self.prompt_session = PromptSession(  # prompt_toolkit for input
            editing_mode=EditingMode.VI,   # Vi-mode editing
            history=FileHistory(...),       # Persistent history
        )
        self.confirmations = {}            # Confirmation state
        self.never_prompts = set()         # "Don't ask again" state
```

**Key UI Features (from source):**

| Feature | Source Location | Implementation |
|---------|----------------|----------------|
| **Autocomplete** | `AutoCompleter` class | Tab-completes filenames, commands, code symbols from tree-sitter |
| **Vi-mode editing** | `EditingMode.VI` | Full vi normal/insert/visual modes |
| **Rich markdown streaming** | `MarkdownStream` | Live markdown rendering as tokens arrive |
| **Side-by-side diffs** | `cmd_diff()` | `git diff` with Rich syntax highlighting |
| **ConfirmGroup** | `ConfirmGroup` dataclass | Batch approval: "Yes/No/All/Skip all/Don't ask again" |
| **30+ slash commands** | `Commands` class | Any method named `cmd_xxx` becomes `/xxx` |
| **Voice input** | `voice.py` | Whisper integration via `/voice` command |
| **File watcher** | `file_watcher` | Detects external file changes, offers to re-read |
| **Clipboard watcher** | `clipboard_watcher` | Detects image paste |
| **Multiline mode** | `{` to start, `}` to end | Bracket-delimited multiline input |
| **Bell notification** | `ring_bell()` | Terminal bell when waiting for input |
| **Platform info** | `cmd_settings()` | Shows OS, shell, Python version |

**Aider's Autocomplete (from source):**
```python
class AutoCompleter(Completer):
    def get_completions(self, document, complete_event):
        # 1. If starts with /, complete commands
        if text[0] == "/":
            yield from self.get_command_completions(...)
        # 2. Otherwise, complete filenames
        for rel_fname in self.addable_rel_fnames:
            yield Completion(rel_fname, ...)
        # 3. Tokenize code files for symbol completion
        for fname in self.all_fnames:
            lexer = guess_lexer_for_filename(fname, content)
            tokens = list(lexer.get_tokens(content))
            self.words.update(token[1] for token in tokens)
```

**Aider's ConfirmGroup (from source):**
```python
@dataclass
class ConfirmGroup:
    preference: str = None  # "all" or "skip" — persists across batch
    show_group: bool = True

# Usage: ConfirmGroup shows "(Y)es/(N)o/(A)ll/(S)kip all/(D)on't ask again"
# When user picks "All", group.preference = "all" and no more prompts
```

### 1.2 SWE-agent — Trajectory Inspector

**Source: `sweagent/inspector_cli.py` (493 LOC)**

SWE-agent uses Textual (TUI framework) for its CLI inspector:

```python
# CLI Inspector (sweagent/inspector_cli.py)
class TrajectoryViewer(Static):
    BINDINGS = [
        Binding("right,l", "next_item", "Step++"),
        Binding("left,h", "previous_item", "Step--"),
        Binding("0", "first_item", "Step=0"),
        Binding("$", "last_item", "Step=-1"),
        Binding("v", "toggle_view", "Toggle view"),
        Binding("j,down", "scroll_down", "Scroll down"),
        Binding("k,up", "scroll_up", "Scroll up"),
    ]

    def _show_step_simple(self, item):
        # Simplified view: THOUGHT / ACTION / OBSERVATION
        content_str = f"THOUGHT:\n{thought}\n\nACTION:\n{action}\n\nOBSERVATION:\n{observation}"

    def _show_step_yaml(self, item):
        # Full YAML view with syntax highlighting
        syntax = Syntax(content_str, "yaml", theme="monokai", word_wrap=True)
```

**Web Inspector (from `sweagent/inspector/server.py`):**
```python
# HTTP server that serves trajectory JSON as HTML
# Shows: problem statement, step-by-step, exit status, cost stats
# Stats: instance_cost, tokens_sent, tokens_received, api_calls
```

**Key UI Features:**
| Feature | Source | Implementation |
|---------|--------|----------------|
| **Vim keybindings** | `BINDINGS` list | h/l for steps, j/k for scroll, v for toggle |
| **Two views** | `show_full` flag | Simple (thought/action/obs) vs Full (YAML) |
| **Trajectory list** | `TrajectorySelectorScreen` | Modal screen with type-ahead search |
| **Cost display** | `overview_stats` | Shows cost, tokens, API calls per trajectory |
| **Benchmark overlay** | `results` dict | Pass/fail/cost per SWE-bench instance |
| **Syntax highlighting** | `rich.syntax.Syntax` | YAML syntax highlighting in terminal |

### 1.3 OpenHands — Browser SPA

**Source: `openhands/src/components/` (React TypeScript)**

OpenHands' Agent Canvas is a full React SPA:

```tsx
// Chat message component (chat-message.tsx)
export function ChatMessage({ type, message, actions, pendingStatus, onRetry, onDismiss, onStop }) {
    const [isHovering, setIsHovering] = React.useState(false);
    const [isCopy, setIsCopy] = React.useState(false);
    const [isExpanded, setIsExpanded] = React.useState(false);

    // Hover shows copy button + actions
    // Truncatable messages with expand/collapse
    // Markdown rendering via MarkdownRenderer
}
```

```tsx
// Collapsible thinking (collapsible-thinking.tsx)
export function CollapsibleThinking({ content }) {
    const [expanded, setExpanded] = React.useState(false);
    // Collapsed by default with lightbulb icon
    // Expands to show markdown-rendered thinking
}
```

```tsx
// Action content helpers (get-action-content.ts)
// Shows: command, pattern, path, risk level
// Security risk: LOW / MEDIUM / HIGH / UNKNOWN
// Internationalized (i18n)
```

**Key UI Features:**
| Feature | Source | Implementation |
|---------|--------|----------------|
| **Collapsible thinking** | `CollapsibleThinking` | Lightbulb icon, expand/collapse, markdown |
| **Copy button on hover** | `CopyToClipboardButton` | Clipboard API, 2s feedback |
| **Truncatable messages** | `isTruncatable` state | Expand/collapse for long messages |
| **Pending status** | `pendingStatus` prop | "sending" / "error" states with spinner |
| **Stop button on hover** | `onStop` callback | Shows stop icon when hovering pending message |
| **Error display** | `ErrorMessage` component | Error ID + retry button |
| **Security risk labels** | `getRiskText()` | LOW/MEDIUM/HIGH badges on actions |
| **Markdown rendering** | `MarkdownRenderer` | Full markdown in messages |
| **Action cards** | `get-action-content.ts` | Structured display per action type |
| **Task tracking** | `task-tracking/` | Task items with status |
| **Automations** | `automations/` | Schedule, cron, event triggers |

---

## 2. GGUFLoader vs Others — Actual Code Comparison

### 2.1 Message Rendering

| Feature | GGUFLoader (PySide6) | Aider (Rich) | OpenHands (React) | SWE-agent (Textual) |
|---------|:--------------------:|:------------:|:-----------------:|:-------------------:|
| **Markdown rendering** | `setMarkdown()` | `MarkdownStream` live | `MarkdownRenderer` | Plain text |
| **Streaming** | `stream_token()` → `update_text()` | `MarkdownStream.feed()` | WebSocket events | N/A (batch) |
| **Code highlighting** | ❌ No | ✅ Pygments lexer | ✅ SyntaxHighlighter | ✅ `rich.syntax.Syntax` |
| **Collapsible thinking** | ✅ `ReasoningBlock` | ❌ Hidden | ✅ `CollapsibleThinking` | ❌ Hidden |
| **Copy per message** | ❌ No | ❌ No | ✅ `CopyToClipboardButton` | ❌ No |
| **Truncation** | ❌ No | ❌ No | ✅ `isTruncatable` | ❌ No |
| **Pending/error state** | ❌ No | Spinner only | ✅ `pendingStatus` | ❌ No |

### 2.2 Input Handling

| Feature | GGUFLoader | Aider | OpenHands | SWE-agent |
|---------|:----------:|:-----:|:---------:|:---------:|
| **Autocomplete** | ❌ No | ✅ `AutoCompleter` (filenames+symbols) | ❌ No | ❌ No |
| **Vi-mode** | ❌ No | ✅ `EditingMode.VI` | ❌ No | ❌ No |
| **Multiline** | Shift+Enter | `{` to start, `}` to end | Shift+Enter | N/A |
| **Voice input** | ❌ No | ✅ `/voice` command | ❌ No | ❌ No |
| **Image paste** | ❌ No | ✅ Clipboard watcher | ❌ No | ❌ No |
| **File picker** | ✅ Paperclip | ✅ `/add` + autocomplete | ❌ No | ❌ No |
| **Slash commands** | ❌ No | ✅ 30+ commands | ❌ No | ❌ No |
| **Search in history** | ✅ Find dialog | ✅ Ctrl+R (prompt_toolkit) | ❌ No | ❌ No |
| **History persistence** | ✅ SQLite | ✅ `FileHistory` | ✅ Backend | ❌ No |

### 2.3 Tool Call Display

| Feature | GGUFLoader | Aider | OpenHands | SWE-agent |
|---------|:----------:|:-----:|:---------:|:---------:|
| **Tool cards** | ✅ `ToolCard` widget | ❌ Inline | ✅ Action cards | ❌ stdout only |
| **Approval UI** | ✅ Allow/Deny buttons | ✅ `ConfirmGroup` (y/N/All/Skip) | ✅ Dialog | ❌ Blocklist only |
| **Error display** | ✅ Error card | ✅ Red text (`tool_error()`) | ✅ `ErrorMessage` + retry | ❌ stdout |
| **Risk badges** | ❌ No | ❌ No | ✅ `SecurityRisk.LOW/MEDIUM/HIGH` | ❌ No |
| **Diff display** | ❌ No | ✅ `cmd_diff()` | ✅ Diff view | ❌ No |
| **Step counter** | Status bar | Cost display | Session | Trajectory |

### 2.4 Session Management

| Feature | GGUFLoader | Aider | OpenHands | SWE-agent |
|---------|:----------:|:-----:|:---------:|:---------:|
| **Session list** | ✅ Sidebar | ❌ No (file-based) | ✅ Session list | ❌ Trajectory dir |
| **Auto-title** | ✅ LLM-generated | ❌ No | ❌ No | ❌ No |
| **Rename session** | ✅ Click to rename | ❌ No | ❌ No | ❌ No |
| **Delete session** | ✅ Delete button | ❌ No | ❌ No | ❌ No |
| **Export** | ❌ No | ✅ Markdown files | ✅ Backend | ✅ `.traj` JSON |
| **Resume** | ✅ Session selector | ✅ `--restore` flag | ✅ Session list | ✅ Replay trajectory |
| **Feedback** | ✅ Thumbs up/down | ❌ No | ❌ No | ❌ No |

---

## 3. WHAT GGUFLoader IS MISSING (Source-Verified)

### Priority 1: Quick Wins (1-2 weeks)

| Missing | Source Reference | Effort |
|---------|-----------------|--------|
| **Syntax highlighting** | Aider uses `PygmentsLexer` + `guess_lexer_for_filename()` | 100 lines |
| **Copy button per message** | OpenHands: `CopyToClipboardButton` with 2s feedback | 30 lines |
| **Cost/token counter** | SWE-agent: `model_stats` in trajectory. Aider: per-message $ | 50 lines |
| **Truncatable messages** | OpenHands: `isTruncatable` + expand/collapse | 50 lines |
| **Export conversation** | Aider: markdown files. SWE-agent: `.traj` JSON | 50 lines |
| **Pending/error state** | OpenHands: `pendingStatus` prop with spinner | 40 lines |

### Priority 2: Power Features (2-4 weeks)

| Missing | Source Reference | Effort |
|---------|-----------------|--------|
| **Autocomplete** | Aider: `AutoCompleter` with filenames + tree-sitter symbols | 200 lines |
| **Slash commands** | Aider: `Commands` class, any `cmd_xxx` method = `/xxx` command | 200 lines |
| **Side-by-side diffs** | Aider: `cmd_diff()` → `git diff` with Rich highlighting | 300 lines |
| **ConfirmGroup** | Aider: `ConfirmGroup` with All/Skip/Don't-ask-again | 100 lines |
| **Risk badges** | OpenHands: `SecurityRisk.LOW/MEDIUM/HIGH` labels | 50 lines |
| **File tree view** | OpenHands: workspace file browser in sidebar | 200 lines |

### Priority 3: Advanced (1-2 months)

| Missing | Source Reference | Effort |
|---------|-----------------|--------|
| **Voice input** | Aider: `voice.py` with Whisper | 200 lines |
| **Image paste** | Aider: `clipboard_watcher` for image detection | 150 lines |
| **Vi-mode** | Aider: `EditingMode.VI` in prompt_toolkit | 50 lines (config) |
| **Trajectory inspector** | SWE-agent: `TrajectoryViewer` with Textual | 400 lines |
| **Automation builder** | OpenHands: React automation components | 500 lines |

---

## 4. GGUFLoader'S UNIQUE STRENGTHS (None of the Others Have)

| Strength | Why It's Unique |
|----------|-----------------|
| **Chat bubble UI** | All others are terminal/browser. GGUFLoader is the only desktop GUI with chat bubbles |
| **Reasoning blocks with timing** | OpenHands has collapsible thinking but no timing. GGUFLoader shows thinking duration |
| **Follow-up chips** | No other harness suggests follow-up questions |
| **RAG source chips** | No other harness shows document citations inline |
| **Agent mode toggle** | One button switches between chat and agent. Others require separate modes |
| **Agent panel** | Structured tool-by-tool transcript view. Others show flat output |
| **Session sidebar** | Visual session management with rename/delete. Others use file lists |
| **Auto-generated titles** | LLM names conversations. No other harness does this |
| **GPU status chip** | Shows hardware state at a glance. Others don't expose this |
| **Token rate display** | Live tokens/sec. Others show total cost but not speed |
| **Feedback persistence** | Thumbs up/down saved across sessions. No other harness does this |
| **Dark/Light mode toggle** | Theme control. Others use terminal colors or browser themes |

---

## 5. DeepSeek Harness — Source-Code Verified

**Source: `packages/client/ui-chat/` (React TypeScript)**

DeepSeek Harness is the most UI-sophisticated agent harness. Everything is a plugin — UI components are Compose/Slot-based.

### 5.1 ChatView Architecture

```tsx
// ChatView.tsx (695 LOC) — Main conversation view
// Features:
// - Virtual scrolling with stable anchor keys
// - Turn-based navigation (vertical rail)
// - Paging anchors for scroll position recovery
// - Follow threshold (24px) for auto-scroll
// - Composer seat for input area
```

### 5.2 ReasoningRow (Thinking Display)

```tsx
// ReasoningRow.tsx — Collapsible thinking with live streaming
export function ReasoningRow({ text, running, t }) {
    const [expanded, setExpanded] = useState(false)
    // Shows first line when collapsed, latest line when streaming
    // Auto-scrolls summary to the right during streaming
    // Uses DisclosureRow with IconThinkOutline14
}
```

**vs GGUFLoader**: GGUFLoader's `ReasoningBlock` is similar but lacks auto-scroll summary and uses simple expand/collapse.

### 5.3 ApprovalPanel (Tool Approval)

```tsx
// ApprovalPanel.tsx — Composer takeover for pending approvals
export function ApprovalPanel(props) {
    return (
        <div className={css.card}>
            <div className={css.strip}><span className={css.dot} />{t('waiting')}</div>
            <div className={css.headline}>{pending.reason ?? t('escalation', { toolName })}</div>
            {detail !== null && <div className={css.command}>{detail}</div>}
            <div className={css.actionRow}>
                <Button variant="outline" onClick={() => answer('rejected')}>{t('reject')}</Button>
                <Button variant="primary" onClick={() => answer('allowed-once')}>{t('allowOnce')}</Button>
            </div>
        </div>
    )
}
```

**vs GGUFLoader**: DeepSeek has `allowOnce` (approve once) vs GGUFLoader's Allow (approve once). But DeepSeek also has `rejected` with visual feedback. GGUFLoader has thumbs feedback but no reject confirmation.

### 5.4 GenericCommandCard (Tool Call Display)

```tsx
// GenericCommandCard.tsx — Collapsible tool call card
// State: running | ok | error
// Features:
// - DisclosureRow with icon (running: ApiIcon, error: StateDot)
// - Collapsed: title + summary ("Running..." / "Done" / "Failed")
// - Expanded: full body with pre-formatted text
// - StateDot for error indication
```

**vs GGUFLoader**: GGUFLoader's tool cards are similar but lack the `running` state indicator and the collapsible body view.

### 5.5 StatsLine (Token/Cost Display)

```tsx
// StatsLine.tsx — Live stats in composer dock
// Shows:
// - Token usage (input/output/cache hits)
// - Tokens per second (TTFT + decode)
// - Cache hit percentage
// - Windowed stats: turns, steps, LLM ms, tool ms
// - Tooltip with detailed breakdown
// Uses: TokenUsageProjection, formatTokensPerSecond, formatCacheHitPercent
```

**vs GGUFLoader**: GGUFLoader only shows token rate (tokens/sec). DeepSeek shows cache hits, TTFT, decode speed, and windowed stats.

### 5.6 TurnNavigator (Session Navigation)

```tsx
// TurnNavigator.tsx — Vertical rail for turn-by-turn navigation
// Features:
// - Vertical rail with marks for each turn
// - Hover preview of turn content
// - Click to jump to any turn
// - Compresses when too many turns (auto-spacing)
// - Pointer-based interaction (no keyboard)
```

**vs GGUFLoader**: GGUFLoader has session sidebar but no turn-by-turn navigation within a session.

### 5.7 DeepSeek UI Strengths

| Strength | Description |
|----------|-------------|
| **Plugin architecture** | Every UI component is a Compose slot — mix and match |
| **Turn navigator** | Visual rail to jump between turns |
| **Cache hit display** | Shows prompt cache hit rate |
| **TTFT display** | Time-to-first-token per step |
| **DisclosureRow** | Reusable expand/collapse component with icon |
| **StateDot** | Visual state indicator (running/ok/error) |
| **Pending submission** | Shows "Submitting..." during generation |
| **Compaction item** | Visual indicator when context is compressed |
| **Context injection row** | Shows what context was injected |
| **Message icon actions** | Copy, retry, edit on each message |

---

## 6. RECOMMENDED UPGRADES (Prioritized by Impact)

### Phase 1: Polish (1-2 weeks)
1. **Syntax highlighting in code blocks** — Use Pygments in QTextEdit (Aider pattern)
2. **Copy button per message** — Hover icon with clipboard feedback (OpenHands pattern)
3. **Cost/token counter** — Show per-message tokens + total in sidebar
4. **Truncatable messages** — Expand/collapse for long AI responses
5. **Export conversation** — Save as markdown file
6. **Pending/error state** — Spinner + retry for in-progress messages (DeepSeek `PendingSubmissionBubble`)

### Phase 2: Power Features (2-4 weeks)
7. **Autocomplete** — Tab-complete filenames and tool names (Aider `AutoCompleter`)
8. **Slash commands** — /add, /drop, /clear, /undo, /help, /map (Aider `Commands` pattern)
9. **Side-by-side diffs** — Show file changes as inline diffs in tool cards
10. **ConfirmGroup** — Batch approval with All/Skip/Don't-ask-again (Aider pattern)
11. **Risk badges** — LOW/MEDIUM/HIGH labels on tool calls (OpenHands pattern)
12. **Turn navigator** — Visual rail to jump between turns (DeepSeek `TurnNavigator`)
13. **DisclosureRow** — Reusable expand/collapse with icon (DeepSeek pattern)

### Phase 3: Advanced (1-2 months)
14. **Voice input** — Whisper integration (Aider `voice.py`)
15. **Image paste** — Screenshot attachment (Aider `clipboard_watcher`)
16. **File tree view** — Workspace browser in sidebar (OpenHands pattern)
17. **Cache hit display** — Show prompt cache hit rate (DeepSeek `StatsLine`)
18. **TTFT display** — Time-to-first-token per step (DeepSeek `StatsLine`)
19. **Trajectory inspector** — Step-by-step replay view (SWE-agent `TrajectoryViewer`)
20. **Plugin architecture** — Slot-based UI components (DeepSeek pattern)

---

## APPENDIX: Source Files Studied

| Harness | File | LOC | Key Classes |
|---------|------|-----|-------------|
| Aider | `aider/io.py` | 1191 | `IO`, `AutoCompleter`, `ConfirmGroup` |
| Aider | `aider/commands.py` | 1712 | `Commands` (30+ `cmd_xxx` methods) |
| SWE-agent | `sweagent/inspector_cli.py` | 493 | `TrajectoryViewer`, `TrajectorySelectorScreen` |
| SWE-agent | `sweagent/inspector/server.py` | 354 | HTTP server for web inspector |
| OpenHands | `src/components/features/chat/chat-message.tsx` | ~100 | `ChatMessage` |
| OpenHands | `src/components/conversation-events/chat/event-message-components/collapsible-thinking.tsx` | ~80 | `CollapsibleThinking` |
| OpenHands | `src/components/conversation-events/chat/event-content-helpers/get-action-content.ts` | ~200 | `getRiskText()`, action content helpers |
| DeepSeek | `packages/client/ui-chat/src/client/chat/ChatView.tsx` | 695 | `ChatView` (virtual scroll, turn nav) |
| DeepSeek | `packages/client/ui-chat/src/client/chat/MessageItem.tsx` | 343 | `MessageItem`, `ModelRetryItem` |
| DeepSeek | `packages/client/ui-chat/src/client/chat/ReasoningRow.tsx` | ~80 | `ReasoningRow` (streaming thinking) |
| DeepSeek | `packages/client/ui-chat/src/client/chat/StatsLine.tsx` | ~120 | `StatsLine` (tokens, cache, TTFT) |
| DeepSeek | `packages/client/ui-chat/src/client/chat/TurnNavigator.tsx` | ~80 | `TurnNavigator` (turn rail) |
| DeepSeek | `packages/client/ui-chat/src/client/chat/GenericCommandCard.tsx` | ~80 | `GenericCommandCard` (tool call card) |
| DeepSeek | `packages/client/ui-approval/src/client/ApprovalPanel.tsx` | ~50 | `ApprovalPanel` (approval flow) |
| GGUFLoader | `ggufloader/ui/chat_panel.py` | 570 | `ChatPanel`, `MessageInput` |
