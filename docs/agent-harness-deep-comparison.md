# GGUFLoader Agent vs Modern AI Harnesses — Full Deep Comparison

> Code-level comparison of 5 harnesses studied from source: Mini-Coding-Agent (1019 LOC), SWE-agent (3890+ LOC), Aider (2485+ LOC), Codex CLI (170K+ LOC Rust), GGUFLoader (~2600 LOC).

---

## 1. USER INTERFACE & INTERACTION MODEL

### 1.1 Interface Type Comparison

| Harness | Interface | Input Method | Output Method |
|---------|-----------|-------------|---------------|
| Mini-Coding | CLI terminal | `input()` prompt | `print()` to stdout |
| SWE-agent | CLI + Inspector | YAML config + env injection | Trajectory files + web inspector |
| Aider | Rich CLI (prompt_toolkit) | Multi-line editor, vi mode, autocomplete | Rich markdown streaming + side-by-side diffs |
| Codex CLI | Terminal (Rust TUI) | Keyboard input | Colored terminal output |
| GGUFLoader | PySide6 Desktop GUI | TextEdit + Send button + Agent Mode toggle | Chat bubbles + Agent panel cards + approval dialogs |

### 1.2 GGUFLoader UI Architecture (Most Feature-Rich)

```
MainWindow (PySide6 QMainWindow)
├── Header Bar: Brand + Model Status Chip
├── Menu Bar: File | View | Tools | Addons | Help
├── QSplitter
│   ├── SettingsSidebar: Model params, sessions, GPU, RAG, context
│   └── ChatPanel: Message list + Composer + Agent controls
│       ├── Empty State Hero (welcome screen)
│       ├── ChatContainer (scrollable message list)
│       │   ├── ChatBubble (user/AI messages with hover actions)
│       │   ├── ReasoningBlock (collapsible thought process)
│       │   ├── Tool Cards (agent mode: success/error indicators)
│       │   └── Approval Cards (Allow/Deny buttons)
│       ├── AgentPanel (structured transcript for agent mode)
│       └── Input Area: TextEdit + Attach + Agent Toggle + Send/Stop
└── System Tray: Minimize-to-tray support
```

**Unique GGUFLoader UI Features:**
- **Agent Mode Toggle**: Switch between plain chat and agent mode with one button
- **Approval Cards**: Visual Allow/Deny buttons for dangerous tool calls
- **Reasoning Blocks**: Collapsible thought process cards (streams in real-time)
- **Follow-up Chips**: Suggested follow-up questions above the composer
- **File Attachments**: Paperclip button to attach text files
- **Session Management**: Sidebar with rename, delete, new chat
- **Auto-Generated Titles**: LLM names conversations (3 words or less)
- **Dark/Light Mode**: Toggle in View menu
- **Text Size Control**: 12-22px adjustable font
- **Find Dialog**: Search within documents
- **Token Rate Display**: Live tokens/sec in sidebar
- **Memory Estimate**: Shows RAM requirements before loading model
- **GPU Status Chip**: Shows GPU/CPU state in header

### 1.3 Aider UI (Most Polished CLI)

**Unique Aider UI Features:**
- **prompt_toolkit**: Vi-mode editing, autocomplete for filenames/commands
- **Rich markdown streaming**: Live-rendered markdown as tokens arrive
- **Side-by-side diffs**: Visual diff display for file edits
- **Auto-complete**: File paths, command names, code symbols
- **Multiline mode**: Alt+Enter for multi-line input
- **ConfirmGroup**: Batch approval for multiple file edits
- **URL detection**: Auto-detects URLs in messages, offers to fetch
- **Language detection**: Auto-detects user language, replies in same
- **Platform info**: Shows OS, shell, Python version in context
- **Chat history persistence**: Markdown files for session replay
- **Auto-copy context**: Copies context from clipboard on startup
- **Waiting spinner**: Visual indicator during long operations

### 1.4 Mini-Coding CLI (Simplest)

```
mini-coding-agent> [user types here]
┌─────────────────────────────────┐
│ /\     /\                       │
│ {  `---'  }                     │  Welcome art
│ {  O   O  }                     │
│ ~~>  V  <~~                     │
│ \  \|/  /                      │
│ `-----'__                       │
├─────────────────────────────────┤
│ WORKSPACE: /path/to/repo        │  Status display
│ MODEL: qwen3.5:4b               │
│ BRANCH: main                    │
│ APPROVAL: ask                   │
└─────────────────────────────────┘
```

**Commands:** `/help`, `/memory` (show working memory), `/session` (show file path), `/reset`, `/exit`

### 1.5 SWE-agent UI (Config-Driven)

- **No interactive UI** — runs from YAML config files
- **Inspector server**: Web-based trajectory viewer at localhost
- **Batch mode**: Process multiple GitHub issues in parallel
- **Environment injection**: Problem statement injected as env variable

### 1.6 Interaction Flow Comparison

```
USER ACTION          Mini-Coding    SWE-agent         Aider              GGUFLoader
─────────────────────────────────────────────────────────────────────────────────
Type message         input()        YAML config       prompt_toolkit     QTextEdit
Send message         Enter          Auto (batch)      Enter              Send button / Enter
Cancel generation    Ctrl+C         Timeout (300s)    Ctrl+C             Stop button
Approve tool call    y/N input      Blocklist only    ConfirmGroup       Approval card
View thinking        (hidden)       Trajectory file   (hidden)           ReasoningBlock
Switch sessions      (N/A)          (N/A)             /clear, /restore   Session sidebar
Search history       (N/A)          (N/A)             Ctrl-R             Find dialog
Attach files         (N/A)          (N/A)             (images)           Paperclip button
View diffs           (N/A)          (N/A)             Side-by-side       (N/A)
Copy output          Ctrl+C         (N/A)             (auto)             Copy button
```

---

## 2. USER INTERACTION DEEP DIVE

### 2.1 Input Processing Pipeline

**Mini-Coding:**
```python
user_input = input("mini-coding-agent> ")  # raw text
# Slash commands: /help, /memory, /session, /reset, /exit
# Everything else -> agent.ask(user_input)
```

**SWE-agent:**
```python
# No user interaction — problem_statement injected from YAML
# Agent runs autonomously until done or budget exhausted
```

**Aider:**
```python
user_input = io.get_input(root, files, addable_files, commands)
# Preprocessing:
# 1. Slash commands (/add, /drop, /diff, /undo, /run, etc.)
# 2. File mention detection (adds files to context)
# 3. URL detection (fetches web content)
# 4. Multiline mode (Alt+Enter)
```

**GGUFLoader:**
```python
# ChatPanel._submit() -> message_submitted signal
# MainWindow._send_message(text)
#   1. Check model loaded
#   2. If agent mode -> _send_to_agent(text)
#   3. Else -> _ensure_current_session + _generate_reply(text)
#      a. RAG retrieval (if enabled)
#      b. PromptBuilder.build_messages()
#      c. _fit_messages_to_context() (trim old messages)
#      d. ChatService.generate() (streaming)
```

### 2.2 Output Presentation

**Mini-Coding:** Plain text to stdout, no formatting, no streaming

**SWE-agent:** JSON trajectory files, no live output (runs in background)

**Aider:**
- Rich markdown rendering as tokens stream in
- Side-by-side diffs for file edits
- Color-coded status (green=success, red=error)
- Cost display per message

**GGUFLoader:**
- **Chat Bubbles**: ChatBubble widgets with user/AI styling
- **Streaming**: Real-time token rendering via stream_token()
- **Reasoning Blocks**: Collapsible thought cards (shows thinking time)
- **Tool Cards**: Success/error indicators with details
- **Approval Cards**: Allow/Deny buttons for dangerous operations
- **System Messages**: Centered italic labels for status/errors
- **Follow-up Chips**: Clickable suggested questions
- **RAG Sources**: Document source chips after responses
- **Agent Status**: Color-coded status (yellow=busy, green=ready)
- **Token Rate**: Live tokens/sec in sidebar

### 2.3 Error Handling UX

| Error Type | Mini-Coding | Aider | GGUFLoader |
|-----------|-------------|-------|------------|
| Malformed JSON | Print retry_notice, try again | Reflection loop (re-query) | JSON repair + retry (2 attempts) |
| Failed tool | Print error, continue | Print error, continue | Error card in agent panel |
| Context overflow | Truncate silently | Warn + suggest /clear | System message + trim old messages |
| Model not loaded | (N/A) | (N/A) | QMessage

---

## 3. AGENT LOOP ARCHITECTURE (DEEP)

### 3.1 Loop State Machine Comparison

**Mini-Coding — Linear:**
```
START -> [model.complete] -> parse(raw)
  -> tool: execute -> record -> loop back
  -> retry: record notice -> loop back
  -> final: return -> END
  max_attempts = max_steps * 3
```

**SWE-agent — Stateful with Recovery:**
```
START -> setup(env, problem_statement)
  -> [forward_with_handling loop]
    -> forward(history) -> model.query -> parse_actions
    -> handle_action(step)
      -> blocked? -> _BlockedActionError -> requery
      -> syntax error? -> requery
      -> timeout? -> interrupt_session -> requery
      -> success? -> add_step_to_history
    -> step.done? -> handle_submission -> END
  -> if RetryAgent:
    -> review_solution -> score
    -> if score < threshold: _next_attempt() -> reset env -> loop
    -> else: pick best attempt -> END
```

**Aider — Reflection + Edit Strategy:**
```
START -> preproc_user_input (commands, URL, file mentions)
  -> [send_message loop]
    -> format_chat_chunks (system + examples + done + repo + files + cur)
    -> model.complete -> parse response
    -> apply edit (diff/whole/patch based on edit_format)
    -> auto_lint -> if errors: feed back to model
    -> auto_test -> if errors: feed back to model
    -> if reflected_message: loop (up to 3x)
    -> else: -> END
  -> summarize_start() (background thread if context too big)
```

**GGUFLoader — Coverage + Memory:**
```
START -> process(user_message)
  -> [multi-step loop, max_steps=8]
    -> _request_action() -> model(prompt) -> extract_json(raw)
      -> if malformed: repair attempts (2x)
    -> if no tool_calls: _finish()
      -> _issue_directive() (coverage check for summaries)
      -> if directive: continue loop
      -> else: break
    -> stale_repeat_signatures() -> filter new calls only
    -> for each call:
      -> validate_tool_call() (schema check)
      -> requires_approval()? -> _on_approval() callback
      -> tools.execute() -> _log_tool_result()
      -> WorkingMemory.update()
    -> _request_fix() for failed calls (1 corrective retry)
  -> _final_response() -> END
```

### 3.2 Error Recovery Comparison

| Mechanism | Mini-Coding | SWE-agent | Aider | GGUFLoader |
|-----------|:-----------:|:---------:|:-----:|:----------:|
| Malformed output | retry_notice | FormatError requery | Reflection | json_retries (2) |
| Blocked action | N/A | _BlockedActionError | N/A | requires_approval() |
| Syntax error | N/A | bash -n check + requery | Auto-lint re-feed | N/A |
| Timeout | N/A | interrupt_session | N/A | per-tool timeout |
| Failed tool | N/A | autosubmission | Reflection | _request_fix (1 retry) |
| Context overflow | N/A | HistoryProcessor | Summarize thread | _fit_messages_to_context |
| Crash | Session lost | autosubmission | Markdown history | SQLite checkpoint |

### 3.3 Budget Control

| Budget Type | Mini-Coding | SWE-agent | Aider | GGUFLoader |
|-------------|:-----------:|:---------:|:-----:|:----------:|
| Max steps | max_steps (default 3) | No explicit limit | max_reflections=3 | max_steps (default 8) |
| Token budget | max_new_tokens (512) | per_instance_cost_limit | max_input_tokens | max_tokens (2048) |
| Time budget | Ollama timeout | total_execution_timeout | None | per-tool timeout (60s) |
| Cost budget | None | cost_limit (total + per-instance) | total_cost tracking | None |
| Attempt budget | max_attempts = steps*3 | retry_loop.max_attempts | None | None |

---

## 4. TOOL CALLING PROTOCOL (DEEP)

### 4.1 Tool Call Format

**Mini-Coding — XML + JSON:**
```xml
<tool>{"name":"read_file","args":{"path":"README.md","start":1,"end":80}}</tool>
```

**SWE-agent — Bash thought/action:**
```python
thought = "I need to check the file"
action = "cat README.md"  # raw bash command
```

**Aider — Edit format dependent (diff/whole/patch):**
```python
<<<<<<< SEARCH
:1: def old_function():
    pass
=======
def new_function():
    return 42
>>>>>>> REPLACE
```

**GGUFLoader — JSON:**
```json
{"reasoning": "...", "tool_calls": [{"tool": "read_file", "parameters": {"path": "foo.py"}}], "answer": ""}
```

### 4.2 Tool Validation

| Validation | Mini-Coding | SWE-agent | Aider | GGUFLoader |
|-----------|:-----------:|:---------:|:-----:|:----------:|
| Schema validation | Manual checks | Pydantic models | JSON Schema | JSON Schema |
| Required params | validate_tool() | Pydantic required | Draft7Validator | validate_tool_call() |
| Type checking | Manual | Pydantic types | JSON Schema types | Basic type check |
| Path sandbox | path_is_within_root | env restriction | repo root | Tool.resolve() |
| Execution timeout | 120s max | configurable | None | 60s default |

### 4.3 Tool Output Handling

**Mini-Coding:** `clip(text, 4000)` — simple truncation

**SWE-agent:** `max_observation_length=100000` — truncate + "response clipped"

**Aider:** No explicit output capping — relies on context management

**GGUFLoader:** Age-based clipping: `CLIP_RECENT=2000` (last 3), `CLIP_OLD=400` (older)

### 4.4 Approval Workflow

**Mini-Coding:** `input("approve? [y/N]")` — three modes: ask, auto, never

**SWE-agent:** Blocklist-based — no user approval, just blocks dangerous commands

**Aider:** ConfirmGroup — batch approval, "Yes/No/Never for this session"

**GGUFLoader:** Visual Allow/Deny approval cards in agent panel

---

## 5. PLANNING & DELEGATION (DEEP)

### 5.1 Planning Mechanisms

| Mechanism | Mini-Coding | SWE-agent | Aider | GGUFLoader |
|-----------|:-----------:|:---------:|:-----:|:----------:|
| Pre-planning | None | None | Architect mode (2-pass) | Coverage directive |
| Task decomposition | None | RetryAgent with configs | Edit format selection | Working memory |
| Strategy selection | None | agent_configs list | Coder.create() factory | None (single strategy) |
| Post-evaluation | None | ScoreRetryLoop | auto-lint + reflection | None |

### 5.2 Aider Architect Mode (Two-Pass)
User message -> ArchitectCoder (weak_model) plans -> EditorCoder (strong_model) implements -> auto-lint

### 5.3 SWE-agent RetryAgent (Multi-Config)
Multiple agent configs tried sequentially. ScoreRetryLoop or ChooserRetryLoop picks the best.

### 5.4 GGUFLoader Coverage Directive
When user asks to "summarize workspace", agent must read unread files first. Prevents lazy summarization.

### 5.5 Delegation
Only Mini-Coding has bounded read-only child agents. GGUFLoader has no delegation (gap).

---

## 6. SESSION PERSISTENCE

| Feature | Mini-Coding | SWE-agent | Aider | GGUFLoader |
|---------|:-----------:|:---------:|:-----:|:----------:|
| Storage | JSON files | .traj JSON | Markdown | SQLite + JSON |
| Save freq | Every step | Every step | Every message | Every message |
| Resume | --resume flag | Replay trajectory | --restore | Session selector |
| Working memory | Included | Not included | Not included | Included |
| Feedback | NO | NO | NO | YES (thumbs) |
| Auto-title | NO | NO | NO | YES |

---

## 7. CONTEXT MANAGEMENT (DEEP)

### 7.1 Context Budget

**Mini-Coding:** MAX_HISTORY=12000 chars. Age-clipped (900/180). Memory section ~200 chars.

**SWE-agent:** max_observation_length=100000. 6 composable HistoryProcessors. polling prevents cache invalidation.

**Aider:** max_input_tokens. ChatSummary thread. choose_fence(). Token-aware reminder insertion.

**GGUFLoader:** n_ctx - max_tokens - 64. PromptPrefixCache. CLIP_RECENT=2000/CLIP_OLD=400. WorkingMemory.

### 7.2 Compaction Strategies

| Strategy | Mini-Coding | SWE-agent | Aider | GGUFLoader |
|----------|:-----------:|:---------:|:-----:|:----------:|
| Age-based clipping | YES | YES | YES (summarize) | YES |
| Duplicate suppression | YES | YES (ClosedWindow) | NO | NO |
| Background summarization | NO | NO | YES (thread) | YES (compactor) |
| Regex removal | NO | YES | NO | NO |
| Tag-based keep/drop | NO | YES | NO | NO |
| Cache control markers | NO | YES | YES | YES |
| Working memory | YES | NO | NO | YES |

---

## 8. COMPLETE FEATURE MATRIX

| Feature | Mini-Coding | SWE-agent | Aider | Codex | GGUFLoader | Gap? |
|---------|:-----------:|:---------:|:-----:|:-----:|:----------:|:----:|
| Desktop GUI | NO | NO | NO | NO | YES | - |
| Rich markdown | NO | NO | YES | YES | YES | - |
| Streaming | NO | NO | YES | YES | YES | - |
| File attachment | NO | NO | YES(img) | NO | YES(text) | - |
| Auto-complete | NO | NO | YES | YES | NO | YES |
| Side-by-side diffs | NO | NO | YES | NO | NO | YES |
| Slash commands | YES | NO | YES(30+) | NO | NO | YES |
| Approval UI | input() | Blocklist | ConfirmGroup | Allow/Deny | Card | - |
| Cancel | Ctrl+C | Timeout | Ctrl+C | Ctrl+C | Stop btn | - |
| Session sidebar | NO | NO | NO | NO | YES | - |
| Follow-up chips | NO | NO | NO | NO | YES | - |
| Multi-step loop | YES | YES | YES | YES | YES | - |
| Error recovery | retry | 3 types | reflection | retry | repair+fix | - |
| Stale detection | NO | NO | NO | NO | YES | - |
| Coverage directive | NO | NO | NO | NO | YES | - |
| Reflection loop | NO | NO | YES(3x) | NO | NO | YES |
| Batch execute | NO | NO | NO | NO | YES | - |
| Sandboxed Python | NO | NO | NO | NO | YES | - |
| Delegation | YES | NO | NO | YES | NO | YES |
| Pre-planning | NO | NO | YES(architect) | YES | NO | YES |
| Post-evaluation | NO | YES(scoring) | YES(lint) | NO | NO | YES |
| Background summarize | NO | NO | YES | NO | NO | YES |
| History pipeline | NO | YES(6) | NO | NO | NO | YES |
| Repo map (AST) | NO | NO | YES | NO | NO | YES |
| Platform info | NO | NO | YES | YES | NO | YES |
| Auto-title | NO | NO | NO | NO | YES | - |
| Feedback | NO | NO | NO | NO | YES | - |
| Crash recovery | YES | YES | YES | YES | YES | - |
| Session fork | NO | YES | YES | NO | NO | YES |

---

## 9. GAP ANALYSIS

### Priority 1: High Impact, Low Effort

| Gap | Source | What | Effort |
|-----|--------|------|--------|
| Delegation | Mini-Coding | Read-only bounded child agent | 100 lines |
| Tool blocklist | SWE-agent | BLOCKED_COMMANDS set | 20 lines |
| Platform info | Aider | OS/shell/date in prompt | 15 lines |
| Reflection loop | Aider | reflected_message, max 3x | 50 lines |

### Priority 2: High Impact, Medium Effort

| Gap | Source | What | Effort |
|-----|--------|------|--------|
| History pipeline | SWE-agent | Composable processors | 200 lines |
| Background summarization | Aider | ChatSummary thread | 150 lines |
| Multi-format edits | Aider | Diff/whole/patch strategies | 500 lines |
| Repo map | Aider | tree-sitter AST overview | 400 lines |
| Auto-lint/test | Aider | Verify after file edits | 100 lines |
| Auto-complete | Aider | Filename/command completion | 100 lines |

---

## 10. WHAT GGUFLoader DOES BETTER

| Strength | Unique? |
|----------|:-------:|
| Stale repeat detection | YES |
| Coverage directives | YES |
| Batch execution | YES |
| Sandboxed Python | YES |
| Dual JSON repair | YES |
| Desktop GUI with approval cards | YES |
| Auto-titling | YES |
| Follow-up chips | YES |
| File attachments | YES |
| Feedback persistence | YES |
| Reasoning blocks | YES |
| Session sidebar | YES |
| Token rate display | YES |

---

## 11. RECOMMENDATIONS

### Immediate (This Sprint)
1. Add delegation (~100 lines, steal from Mini-Coding)
2. Add tool blocklist (~20 lines)
3. Add platform info (~15 lines)
4. Add reflection loop (~50 lines)

### Short-term (Next 2 Weeks)
5. History processor pipeline
6. Background summarization
7. Auto-lint/test
8. Auto-complete in input box

### Medium-term (Next Month)
9. Repo map (tree-sitter)
10. Multi-format edits
11. Side-by-side diffs
12. Session fork

---

## APPENDIX: Study Repos

| Repo | Language | LOC |
|------|----------|-----|
| mini-coding-agent | Python | 1,019 |
| SWE-agent | Python | 3,890+ |
| aider | Python | 2,485+ |
| codex | Rust | 170,000+ |
| OpenHands | Python | 30,000+ |
