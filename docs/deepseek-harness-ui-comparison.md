# DeepSeek Harness vs GGUFLoader -- Deep UI Comparison

## 1. What DSH Streams vs GGUFLoader Streams

### DSH Streams:
- Token-by-token Markdown in chat composer
- Reasoning/thinking blocks with expand/collapse
- Tool call cards (name, args, result, time, status)
- Subagent progress in sidebar
- Context window composition (donut chart)
- Per-request metadata (model, tokens, cost, cache hit)
- Streaming trajectory (append-only event log)

### GGUFLoader Streams:
- Token-by-token in chat bubbles
- Reasoning blocks (ReasoningBlock widget)
- Tool cards in agent panel
- Approval cards with Allow/Deny buttons
- Metrics bar (steps, tokens, time, retries, context)
- Activity log (chronological events)

### GGUFLoader Is Missing:
- No context composition chart
- No per-request cost tracking
- No cache hit rate display
- No trajectory event source labels
- No subagent live progress in sidebar
---

## 2. What DSH Shows Users That GGUFLoader Does Not

| Feature | DSH | GGUFLoader |
|---------|-----|------------|
| @ file references | Type @ to search workspace | Not available |
| /goal /plan commands | Structured goal-setting | Basic slash commands |
| Runtime mode selector | Standard/Code/Minimal/Creator | Simple toggle |
| Sandbox mode indicator | Shows read-only/write/danger | No indicator |
| Approval policy badge | Shows ask/never mode | No badge |
| Plugin marketplace | Browse/install/update plugins | Tools > Manage Addons |
| Session fork | Fork from any historical point | Can resume only |
| Context lens | Token composition breakdown | Not available |
| Session search | Full-text search across sessions | Only session list |
| Cross-device sync | Sync via Git | Not available |
| Workspace selector | Choose project dir before agent | File > Load Model |
| Language selector | EN, CN localization | Not available |
| Credential management | Write-only API key display | Not available |
| Provider catalog | Anthropic, OpenAI, custom endpoints | GGUF only |
| Trajectory view | Inspect events by source plugin | Activity log only |
---

## 3. Side Panel Comparison

### DSH: Right side panel (via dsh-better-sidebar plugin)
  Files | Terminal | Git | Browser | Subagents | Custom Tabs
  Plugin-based, file editing, integrated terminal, Git diff

### GGUFLoader: Left sidebar (fixed)
  Model Settings | GPU Toggle | Sessions | File Tree | Agent Health | Model Info
  Fixed sections, no terminal, no Git, read-only file tree

| Aspect | DSH | GGUFLoader |
|--------|-----|------------|
| Position | Right (workbench) | Left (settings) |
| Purpose | Development workspace | Model configuration |
| Tabs | File, Terminal, Git, Browser, Subagents | Sessions, File Tree, Model Info |
| Extensibility | Plugin-based (any tab) | Fixed (hardcoded) |
| Terminal | Integrated in sidebar | No terminal |
| Git | Diff, history, graph in sidebar | No Git in UI |
| Browser | Live web preview in sidebar | No browser preview |
| Subagents | Live progress in sidebar | No subagent monitoring |
| File editing | Edit files directly | Read-only file tree |

---

## 4. Menu Layout Comparison

### DSH:
Settings > Models (API keys, providers, model selection)
Settings > Plugins (marketplace, enable/disable)
Settings > Language (EN, CN, etc.)
Settings > Sandbox (read-only / workspace-write / danger)
Settings > Approval (ask / never)
Settings > Credentials (API key management)
Agent: Runtime mode selector, /goal, /plan, @file, MCP

### GGUFLoader:
File > Load Model, Load/Save Session, Export, Quit
View > Toggle Sidebar, Minimize to Tray, Toggle Agent
Addons > [installed addons], Manage Addons
Tools > Agent Settings, Advanced Settings, GPU Install
Help > About, Keyboard Shortcuts
---

## 5. Streaming Gap Analysis

| Feature | DSH | GGUFLoader | Priority |
|---------|-----|------------|----------|
| Token streaming | Yes | Yes | Done |
| Reasoning blocks | Yes | Yes | Done |
| Tool call cards | Yes | Yes | Done |
| Approval cards | Yes | Yes | Done |
| Metrics bar | Yes | Yes | Done |
| Activity log | Yes | Yes | Done |
| Context composition chart | Yes | No | HIGH |
| Per-request cost | Yes | No | HIGH |
| Cache hit rate | Yes | No | MEDIUM |
| Subagent progress sidebar | Yes | No | MEDIUM |
| Trajectory source labels | Yes | No | LOW |
| Cross-session search | Yes | No | MEDIUM |
| Session fork | Yes | No | LOW |

---

## 6. GGUFLoader Improvements Needed

### Priority 1 -- Critical UX Gaps
1. @ file mention system
2. Context composition chart
3. Per-request cost tracking
4. Runtime mode selector

### Priority 2 -- Side Panel Improvements
5. Move sidebar to right
6. Add terminal tab
7. Add Git tab
8. Make sidebar tabs extensible
9. Add file editing in sidebar

### Priority 3 -- Menu and Settings
10. Add Settings page (Model, Provider, Sandbox, Approval, Language, Plugins)
11. Add credential management
12. Add provider catalog (Anthropic, OpenAI, custom)

### Priority 4 -- Session and Memory
13. Add session fork
14. Add cross-session search
15. Add context lens panel
16. Add workspace selector

### Priority 5 -- Agent Loop Improvements
17. Add subagent monitoring in sidebar
18. Add trajectory event source labels
19. Add sandbox mode indicator
20. Add approval policy badge

---

## 7. What GGUFLoader Does Better Than DSH

| Feature | GGUFLoader | DSH |
|---------|------------|-----|
| Local model loading | Direct GGUF with quant detection | Requires API key |
| GPU management | Toggle GPU offloading from UI | No GPU management |
| Model info display | Architecture, quant, params in sidebar | Hidden in settings |
| Memory estimate | VRAM/RAM estimate before loading | No memory estimation |
| Toast notifications | Non-blocking status messages | No toast system |
| Theme customization | Accent color, font size, compact mode | Plugin-based only |
| Onboarding wizard | 6-step guided setup | No onboarding |
| Chat history timeline | Visual timeline of turns | No timeline view |
| Model comparison | Side-by-side comparison widget | No model comparison |
| File drag-and-drop | Drop files onto input box | @ mentions only |
| Slash autocomplete | Tab-completion for commands | No autocomplete |
| Welcome screen | Rich empty-state with quick start | Minimal empty state |
| Floating action button | Quick access to common actions | No FAB |
| Keyboard shortcuts | Ctrl+/ shows all shortcuts | No shortcuts dialog |
| Export with metadata | JSON export with tokens, cost, timing | Basic export |

---

## 8. Implementation Roadmap

### Phase A -- Core DSH Parity (1-2 days)
- Add @ file mention system
- Add context composition chart widget
- Add per-request cost tracking
- Add runtime mode selector

### Phase B -- Side Panel Redesign (2-3 days)
- Move sidebar to right side
- Add tab-based sidebar (Files, Terminal, Git, Settings)
- Integrate terminal widget
- Add Git status/diff panel
- Make sidebar tabs extensible for addons

### Phase C -- Settings Overhaul (1-2 days)
- Create dedicated Settings dialog
- Add provider catalog (Anthropic, OpenAI, custom)
- Add credential management UI
- Add sandbox mode selector
- Add approval policy selector
- Add language selector

### Phase D -- Session Enhancements (1 day)
- Add session fork capability
- Add cross-session search
- Add context lens panel
- Add workspace selector dialog