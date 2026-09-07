# Comprehensive UI Upgrade Plan: GGUFLoader to Match Agent Harnesses

> **📜 Historical document** — describes GGUF Loader at an earlier stage of the
> project and is kept for reference. The current build is a **single-model
> (Gemma 4 12B Q4_K_M)** agent app with a **React/TypeScript frontend and
> FastAPI backend**, running a strictly **plan-driven LangGraph agent** (no
> reactive loop, no multi-model family tuning). UI and architecture details
> below may be outdated.

Based on deep comparison with DeepSeek Harness, OpenHands, Claude Code, Aider,
Codeium, and Mini-Coding-Agent.

---

## Current Layout

LEFT SIDEBAR (fixed, 280-400px):
  Model Settings | GPU Toggle | Sessions | File Tree | Agent Health | Model Info

CENTER:
  Header: Brand + Model Chip
  Session Tabs
  Chat Bubbles / Agent Panel (stacked)
  Input: Preset badge + Agent toggle + Message input

MENU: File | View | Addons | Tools | Help

---

## Target Layout (DSH-style)

HEADER: Brand | Model Chip | Mode Selector (Standard/Code/Minimal) | Context Chart
LEFT PANEL (collapsible): Sessions list with search + Quick actions
CENTER: Chat composer (bubbles, reasoning, tools, approvals, metrics)
RIGHT PANEL (tabbed, extensible): Files | Terminal | Git | Settings
BOTTOM BAR: Context lens [system][history][tools][free headroom]
INPUT AREA: @ file mentions | / commands | workspace selector | message input

---
## Phase 1: Header Redesign

### 1.1 Runtime Mode Selector
- Add mode buttons to header: [Standard] [Code] [Minimal] [Creator]
- Each mode changes available tools and system prompt
- Active mode highlighted with accent color
- Pattern from: DSH preset switcher, Claude Code mode selector
- File: ggufloader/ui/main_window.py (_build_header)
- New widget: ggufloader/widgets/mode_selector.py

### 1.2 Context Composition Chart
- Add live bar/donut chart to header showing token breakdown
- Segments: system prompt, conversation, tool results, available headroom
- Updates in real-time during streaming
- Pattern from: DSH context-vista plugin, dsh-context plugin
- New widget: ggufloader/widgets/context_chart.py
- Wire: Update on each model request/response

### 1.3 Sandbox + Approval Badge
- Small badge next to mode selector showing current sandbox mode
- read-only / workspace-write / danger-full-access
- Click to cycle or open settings
- Pattern from: DSH sandbox mode indicator

---
## Phase 2: Input Area Redesign

### 2.1 @ File Mention System
- When user types @, show a popup listing workspace files
- Type to filter files, arrow keys to navigate, Enter to insert
- Insert file path as a colored chip in the input box
- On send, read file content and add to context
- Pattern from: DSH dsh-at-file plugin, Claude Code @mentions, Aider /add
- New widget: ggufloader/widgets/file_mention_popup.py
- Modify: ggufloader/ui/chat_panel.py (MessageInput)

### 2.2 Workspace Selector in Input
- Small folder icon next to input box shows current workspace
- Click to browse and select project directory
- Updates file tree, file mentions, and agent context
- Pattern from: DSH workspace chooser, Aider --working-dir

### 2.3 Slash Command Autocomplete Dropdown
- Type / to show dropdown of available commands
- Fuzzy match as user types
- Arrow keys + Enter to select
- Already have SmartAutocomplete widget, needs UI polish

---

## Phase 3: Right Panel (Workbench)

### 3.1 Create Right Panel with QTabWidget
- Add a right-side QDockWidget or fixed panel
- Tabs: Files | Terminal | Git | Settings
- Resizable, collapsible with Ctrl+B toggle
- Pattern from: DSH dsh-better-sidebar plugin
- New file: ggufloader/ui/right_panel.py

### 3.2 Files Tab
- Move FileTree from left sidebar to right panel tab
- Add file editing: click file to open in editor pane
- Add file preview with syntax highlighting
- Pattern from: DSH file explorer + editor

### 3.3 Terminal Tab
- Integrate QPlainTextEdit as pseudo-terminal
- Show command output from tool calls
- Allow user to type and execute shell commands
- Pattern from: DSH terminal tab, OpenHands terminal
- New widget: ggufloader/widgets/terminal_widget.py

### 3.4 Git Tab
- Show git status (modified/new/deleted files)
- Show recent commits (git log --oneline -10)
- Show diff for selected file
- Auto-refresh after agent makes changes
- Pattern from: DSH Git tab, Aider git integration
- New widget: ggufloader/widgets/git_panel.py

---
## Phase 4: Left Panel Redesign

### 4.1 Slim Down Left Sidebar
- Remove Model Settings, GPU Toggle, File Tree, Model Info from left sidebar
- These move to: Header (mode selector), Right Panel (files), Settings dialog
- Left sidebar becomes a slim session navigator
- Pattern from: DSH minimal left panel, Claude Code session list

### 4.2 Session Navigator
- Search bar at top (already exists)
- Session list with timestamps and preview text
- Right-click: rename, delete, fork, export
- Double-click: rename (already exists)
- Fork option: branch from this session (NEW)
- Pattern from: DSH session management, Claude Code session list

### 4.3 Quick Actions Section
- New Chat button (already exists)
- Load Model button
- Settings button
- Agent toggle
- Pattern from: DSH quick actions, OpenHands action bar

---

## Phase 5: Settings Dialog Overhaul

### 5.1 Create Unified Settings Dialog
- Replace scattered settings (Advanced, Agent, GPU) with one dialog
- Tabs: Model | Agent | Appearance | Keyboard | Plugins
- Pattern from: DSH Settings page, VS Code Settings
- New file: ggufloader/ui/settings_dialog.py

### 5.2 Model Tab
- Model path selector with browse
- Context length slider
- GPU layers slider
- Model parameters (temp, top_p, etc.)
- Provider catalog: Add Anthropic, OpenAI, custom endpoints
- Credential management: API key storage with write-only display
- Pattern from: DSH Settings > Models

### 5.3 Agent Tab
- Preset picker (research, code_review, refactor, debug, full_stack, quick_fix)
- Feature toggles (memory, knowledge, auto-commit, reflection, etc.)
- Sandbox mode: read-only / workspace-write / danger-full-access
- Approval policy: ask / never / always
- Max steps, max tokens, budget
- Pattern from: DSH Settings > Sandbox, Settings > Approval

### 5.4 Appearance Tab
- Theme: Dark / Light / System
- Accent color picker
- Font size slider
- Compact mode toggle
- Language selector (EN, CN)

---
## Phase 6: Context Lens (Bottom Bar)

### 6.1 Context Lens Bar
- Add a thin bar below the input area showing token composition
- Segments: [System: 1.2k] [History: 3.4k] [Tools: 0.8k] [Free: 27.4k]
- Color-coded: blue=system, green=history, orange=tools, gray=free
- Updates in real-time during streaming
- Click to expand into full context breakdown panel
- Pattern from: DSH context-vista plugin, dsh-context plugin
- New widget: ggufloader/widgets/context_lens.py

### 6.2 Per-Request Cost Display
- Show cost estimate after each request: Cost: /usr/bin/bash.003 (1,247 tokens)
- Accumulate total session cost
- Show in context lens bar
- Pattern from: DSH token-viewer plugin, Aider cost display

---

## Phase 7: Streaming Enhancements

### 7.1 Tool Call Streaming
- Show tool call starting (spinner + tool name)
- Stream tool arguments as they are generated
- Show tool result when complete
- Show execution time
- Already have tool cards, need streaming states

### 7.2 Subagent Progress in Sidebar
- When agent delegates to subagent, show progress in right panel
- Show subagent name, status, current step
- Allow clicking to view subagent conversation
- Pattern from: DSH background agents plugin

### 7.3 Trajectory Event Source Labels
- Label each event in activity log by source: [Model] [Tool] [System] [User]
- Color-coded by source
- Pattern from: DSH trajectory view

---

## Phase 8: Session Enhancements

### 8.1 Session Fork
- Right-click session > Fork: create new session from this point
- Copy all messages up to the fork point
- Pattern from: DSH session fork, Claude Code fork

### 8.2 Cross-Session Search
- Search bar that searches across ALL saved sessions
- Show matching sessions with context snippets
- Click to jump to that session
- Pattern from: DSH session-search plugin

### 8.3 Session Export Enhancements
- Export as Markdown (existing)
- Export as JSON with metadata (existing)
- Export as HTML with styled output (NEW)
- Export as PDF (NEW)

---
## Phase 9: Menu Restructure

### 9.1 New Menu Layout
File > Load Model, New Chat, Load Session, Save Session, Export, Quit
Edit > Undo, Redo, Cut, Copy, Paste, Find (Ctrl+F)
View > Toggle Left Panel, Toggle Right Panel, Toggle Context Lens, Minimize to Tray
Agent > Mode: Standard/Code/Minimal/Creator, Run, Stop, Settings
Tools > GPU Install, Image Generation, MCP Servers
Help > Keyboard Shortcuts, About, Check for Updates

### 9.2 Agent Menu
- Top-level menu for agent controls (currently in View > Toggle Agent)
- Mode submenu: Standard | Code | Minimal | Creator
- Run / Stop / Pause actions
- Settings shortcut

---

## Phase 10: Visual Polish

### 10.1 Consistent Card Design
- All panels use the same card style (elevated surface, border, rounded corners)
- Consistent padding (12px), spacing (8px), border-radius (8px)
- Pattern from: DSH consistent card design

### 10.2 Status Indicators
- Green dot: model loaded, ready
- Yellow dot: generating, busy
- Red dot: error, failed
- Blue dot: agent mode active
- Show in header next to model chip

### 10.3 Loading States
- Skeleton placeholders while loading
- Spinner for model loading
- Progress bar for file operations
- Toast notifications for status updates (already exists)

---

## Implementation Order

| Order | Phase | Effort | Impact | Files Changed |
|-------|-------|--------|--------|---------------|
| 1 | Phase 2: Input Redesign (@ mentions, workspace) | 2 days | HIGH | chat_panel.py, new widget |
| 2 | Phase 1: Header Redesign (mode selector, context chart) | 2 days | HIGH | main_window.py, new widgets |
| 3 | Phase 6: Context Lens (bottom bar, cost) | 1 day | HIGH | new widget, chat_panel.py |
| 4 | Phase 3: Right Panel (tabs, terminal, git) | 3 days | HIGH | new panel + 3 widgets |
| 5 | Phase 4: Left Panel Slim Down | 1 day | MEDIUM | sidebar_panel.py |
| 6 | Phase 5: Settings Dialog Overhaul | 2 days | MEDIUM | new dialog, remove old dialogs |
| 7 | Phase 7: Streaming Enhancements | 2 days | MEDIUM | agent_panel.py, tool_card.py |
| 8 | Phase 8: Session Enhancements | 1 day | MEDIUM | session_export.py, sidebar |
| 9 | Phase 9: Menu Restructure | 0.5 day | LOW | main_window.py |
| 10 | Phase 10: Visual Polish | 1 day | LOW | theme.py, all widgets |

Total: ~15 days, ~15 new/modified files

---

## New Files to Create

| File | Purpose | Lines |
|------|---------|-------|
| ggufloader/widgets/mode_selector.py | Runtime mode buttons | ~150 |
| ggufloader/widgets/context_chart.py | Token breakdown chart | ~200 |
| ggufloader/widgets/context_lens.py | Bottom bar context display | ~180 |
| ggufloader/widgets/file_mention_popup.py | @ file mention popup | ~200 |
| ggufloader/widgets/terminal_widget.py | Integrated terminal | ~250 |
| ggufloader/widgets/git_panel.py | Git status/diff panel | ~200 |
| ggufloader/widgets/subagent_monitor.py | Subagent progress display | ~150 |
| ggufloader/ui/right_panel.py | Tabbed right panel container | ~200 |
| ggufloader/ui/settings_dialog.py | Unified settings dialog | ~400 |
| ggufloader/services/credential_store.py | Secure API key storage | ~100 |
| ggufloader/services/provider_catalog.py | Provider catalog (Anthropic, OpenAI) | ~150 |

Total: 11 new files, ~2,180 LOC

---

## Files to Modify

| File | Changes |
|------|---------|
| main_window.py | Header redesign, menu restructure, right panel, settings |
| sidebar_panel.py | Slim down to session navigator only |
| chat_panel.py | @ mentions, workspace selector, context lens integration |
| agent_panel.py | Streaming tool states, subagent progress |
| theme.py | New tokens for right panel, context chart, terminal |
| slash_commands.py | Add /goal, /plan, /fork, /search commands |
| tool_card.py | Streaming states (loading, running, complete) |
| session_export.py | HTML and PDF export |

Total: 8 files modified

---

## What GGUFLoader Will Have After This Plan

- DSH-style 3-panel layout (left sessions, center chat, right workbench)
- @ file mention system like Claude Code and DSH
- Context composition chart like DSH context-vista
- Context lens bar showing token breakdown
- Runtime mode selector (Standard/Code/Minimal/Creator)
- Integrated terminal in right panel
- Git status/diff panel in right panel
- File editing in right panel
- Unified settings dialog with provider catalog
- Sandbox mode and approval policy controls
- Session fork capability
- Cross-session search
- Subagent monitoring
- Per-request cost tracking
- Improved streaming with tool call states

This brings GGUFLoader to full parity with DSH and ahead in 15 areas
(local model loading, GPU management, model info, onboarding, etc.)
