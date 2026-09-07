# Agent Routing Loops & Logic — Deep Comparison

> **📜 Historical document** — describes GGUF Loader at an earlier stage of the
> project and is kept for reference. The current build is a **single-model
> (Gemma 4 12B Q4_K_M)** agent app with a **React/TypeScript frontend and
> FastAPI backend**, running a strictly **plan-driven LangGraph agent** (no
> reactive loop, no multi-model family tuning). UI and architecture details
> below may be outdated.

> How each harness decides WHAT to do next: the router, the loop state machine,
> error recovery, budget gates, and delegation logic. Compared against GGUFLoader.

---

## 1. THE FIVE HARNESS ROUTERS

### 1.1 Router Architecture Overview

| Harness | Router Type | Input | Decision | Output |
|---------|-------------|-------|----------|--------|
| **GGUFLoader** | JSON Protocol Router | User message + history + tool results | Model emits `tool_calls` OR `answer` | JSON action or final text |
| **SWE-agent** | Bash Command Router | Problem statement + observation | Model emits `thought` + `action` (bash) | Shell command |
| **Aider** | Edit-Format Router | User message + repo-map + files | Model emits edit blocks (diff/whole/patch) | File mutations |
| **OpenHands** | Event-Stream Router | User message + event log | Model emits typed Actions | Action objects |
| **Mini-Coding** | XML+JSON Router | User message + memory | Model emits `<tool>` XML or text | Tool call or answer |

---

## 2. GGUFLoader ROUTER — Detailed State Machine

```
process(user_message)
│
├─ 1. COMPLEXITY CHECK
│   └─ if len(words) > 20 OR keywords: → quick analysis LLM call
│
├─ 2. MAIN LOOP (max_steps=8)
│   │
│   ├─ _request_action()
│   │   ├─ _build_action_prompt() [uses PromptPrefixCache]
│   │   ├─ llm(prompt, max_tokens=2048, temp=0.1)
│   │   ├─ extract_json(raw) [tries fenced, bare, balanced objects]
│   │   │   ├─ Success → return action dict
│   │   │   └─ Fail → _json_repair_attempts() [backslash escape]
│   │   │       ├─ Success → return action dict
│   │   │       └─ Fail → retry (up to json_retries=2)
│   │   └─ All retries fail → return None
│   │
│   ├─ if action is None:
│   │   ├─ final_answer = raw_response
│   │   ├─ _issue_directive() [coverage check for summaries]
│   │   │   ├─ directive exists → continue loop
│   │   │   └─ no directive → break
│   │
│   ├─ PARSE ACTION
│   │   ├─ Extract reasoning → status("💭 ...")
│   │   ├─ Extract tool_calls list
│   │   └─ if empty tool_calls:
│   │       ├─ _finish() → get answer text
│   │       ├─ _issue_directive() → maybe continue
│   │       ├─ _should_reflect() → reflection loop
│   │       │   └─ _execute_reflection() (max 3 steps, max 2 reflections)
│   │       └─ break
│   │
│   ├─ STALE DETECTION (unique to GGUFLoader)
│   │   ├─ stale_repeat_signatures(calls, executed)
│   │   ├─ Filters out calls that already ran with valid results
│   │   └─ If ALL calls are stale → wrap up with answer
│   │
│   ├─ EXECUTE CALLS (batch)
│   │   ├─ validate_tool_call() [schema check]
│   │   ├─ requires_approval()? → _on_approval() callback
│   │   ├─ tools.execute() → result
│   │   ├─ _log_tool_result() [age-based clipping]
│   │   └─ WorkingMemory.update()
│   │
│   └─ RETRY FAILURES
│       └─ _request_fix() for each failed call (1 corrective retry)
│
├─ 3. FINAL RESPONSE
│   ├─ _final_response() → LLM summarizes tool results
│   └─ return {response, tool_results}
│
└─ HistoryProcessorPipeline processes conversation for next turn
```

### GGUFLoader Router Strengths:
- **Stale repeat detection** — won't re-run identical calls
- **Coverage directive** — forces reading all files for summaries
- **Reflection loop** — model can self-verify before answering
- **Batch execution** — multiple tool calls per step
- **Dual JSON repair** — handles Windows backslashes in paths

### GGUFLoader Router Weaknesses:
- **No syntax validation** — doesn't check Python/bash before running
- **No auto-lint** — no verification after file edits
- **No cost tracking** — no budget gates on tokens/cost
- **No delegation** — can't spawn child agents
- **No stuck detection** — no mechanism to detect infinite loops

---

## 3. SWE-agent ROUTER — Detailed State Machine

```
run(problem_statement)
│
├─ 1. SETUP
│   ├─ Clone repo into sandbox (SWE-ReX)
│   ├─ Install tool bundles (YAML + bash scripts)
│   └─ Build initial prompt with problem statement
│
├─ 2. MAIN LOOP (while not done)
│   │
│   ├─ forward_with_handling(messages)
│   │   │
│   │   ├─ [REQUERY LOOP: up to 3 attempts]
│   │   │   │
│   │   │   ├─ forward(messages)
│   │   │   │   ├─ model.query(messages) → raw response
│   │   │   │   ├─ parse_actions(response) → (thought, action)
│   │   │   │   │   ├─ LiteLLM native function calling (Anthropic/OpenAI)
│   │   │   │   │   └─ ThoughtActionParser (triple-backtick extraction)
│   │   │   │   ├─ should_block_action(action)?
│   │   │   │   │   └─ Yes → raise _BlockedActionError
│   │   │   │   ├─ bash -n check (syntax validation!)
│   │   │   │   │   └─ Fail → raise BashIncorrectSyntaxError
│   │   │   │   ├─ env.communicate(action, timeout) → observation
│   │   │   │   ├─ env.communicate(state_command) → JSON state
│   │   │   │   ├─ check_for_submission_cmd(observation)?
│   │   │   │   │   └─ Yes → handle_submission() → DONE
│   │   │   │   └─ return StepOutput(thought, action, observation, state)
│   │   │   │
│   │   │   ├─ on FormatError:
│   │   │   │   └─ inject format_error_template → retry
│   │   │   ├─ on _BlockedActionError:
│   │   │   │   └─ inject action_blocked_template → retry
│   │   │   ├─ on BashIncorrectSyntaxError:
│   │   │   │   └─ inject shell_check_error_template → retry
│   │   │   └─ on CommandTimeoutError:
│   │   │       ├─ increment consecutive_timeouts
│   │   │       ├─ if >= max → raise (HARD STOP)
│   │   │       └─ inject command_cancelled_timeout_template → retry
│   │   │
│   │   └─ All retries exhausted → raise FormatError
│   │
│   ├─ add_step_to_history(output)
│   ├─ add_step_to_trajectory(output)
│   ├─ save_trajectory() [write .traj JSON]
│   │
│   └─ step.done? → DONE
│
├─ 3. COST/RESOURCE GATES
│   ├─ per_instance_cost_limit → stop if exceeded
│   ├─ total_execution_timeout → stop if exceeded
│   ├─ context overflow → HistoryProcessor truncation
│   └─ consecutive_failure_count → autosubmit
│
├─ 4. AUTOSUBMIT ON FAILURE
│   └─ Every fatal error → git diff → ship partial patch
│
└─ 5. RETRY AGENT (optional)
    ├─ review_solution() → score
    ├─ if score < threshold → _next_attempt() → reset env → loop
    └─ else → pick best attempt → DONE
```

### SWE-agent Router Strengths:
- **4 error types with templated recovery** — each gets a specific message
- **bash -n syntax check** — catches broken commands before execution
- **Autosubmit on failure** — partial patches are still useful
- **Cost/timeout budgets** — hard stops prevent runaway spending
- **RetryAgent** — tries multiple strategies, picks the best
- **State persistence** — `_state` command refreshes cursor position

### SWE-agent Router Weaknesses:
- **No approval workflow** — fully autonomous, no human-in-the-loop
- **No stale detection** — can re-run same commands
- **No batch execution** — one command per step
- **No reflection** — no self-verification before submission
- **Shell-only** — can't do structured tool calls

---

## 4. AIDER ROUTER — Detailed State Machine

```
run(message)
│
├─ 1. INPUT PREPROCESSING
│   ├─ Slash commands (/add, /drop, /diff, /undo, /run, /voice)
│   ├─ File mention detection (auto-add to context)
│   ├─ URL detection (fetch web content)
│   └─ Multiline mode (Alt+Enter)
│
├─ 2. REPO-MAP GENERATION (PageRank)
│   ├─ tree-sitter parse all source files
│   ├─ Extract symbols (functions, classes, exports)
│   ├─ Graph ranking by reference frequency
│   └─ Top-ranked symbols → compact map (~1024 tokens)
│
├─ 3. MAIN LOOP (max_reflections=3)
│   │
│   ├─ format_chat_chunks()
│   │   ├─ system message + instructions
│   │   ├─ repo-map (always present)
│   │   ├─ explicitly added files
│   │   ├─ current file being edited
│   │   └─ chat history
│   │
│   ├─ model.complete(messages) → raw response
│   │
│   ├─ PARSE EDIT FORMAT (edit_format)
│   │   ├─ "diff" → search/replace blocks
│   │   ├─ "whole" → complete file replacement
│   │   ├─ "udiff" → unified diff
│   │   ├─ "architect" → plan → editor model
│   │   └─ "editor-diff" / "editor-whole" → architect sub-format
│   │
│   ├─ APPLY EDITS
│   │   ├─ Parse edit blocks from response
│   │   ├─ Apply to files
│   

│   └─ auto_lint() → run linter on changed files
│       ├─ Lint errors → feed back to model
│       └─ Lint passes → continue
│
│   ├─ AUTO-TEST (if configured)
│   │   ├─ Run test suite
│   │   ├─ Test failures → feed back to model
│   │   └─ Tests pass → continue
│
│   ├─ REFLECTION CHECK
│   │   ├─ if reflected_message exists → loop (up to 3x)
│   │   └─ else → break
│
│   └─ AUTO-COMMIT
│       └─ git commit with generated message
│
├─ 4. ARCHITECT MODE (two-pass)
│   ├─ Pass 1: ArchitectCoder (weak_model) → plans changes
│   ├─ Pass 2: EditorCoder (strong_model) → implements plan
│   └─ Both models share the same context
│
├─ 5. BACKGROUND SUMMARIZATION
│   └─ if context too large → ChatSummary thread
│       └─ Summarize old messages → inject summary
│
└─ return (edited files, commit message)
```

### Aider Router Strengths:
- **Architect mode** — separates planning from implementation
- **Auto-lint** — catches errors before they compound
- **Auto-test** — verifies changes work
- **Edit format selection** — matches risk to task
- **Repo-map** — structural awareness without scanning everything
- **Auto-commit** — every change is a git commit

### Aider Router Weaknesses:
- **No batch execution** — one edit per step
- **No stale detection** — can re-edit same file
- **No coverage directive** — no forced completeness
- **No tool validation** — relies on edit format parsing
- **No stuck detection** — relies on reflection limit only

---

## 5. OpenHands ROUTER - Detailed State Machine

```
step(conversation)
│
├─ 1. DRAIN PENDING ACTIONS (confirmation flow)
│   ├─ get_unmatched_actions(events)
│   └─ execute_actions(pending) → return
│
├─ 2. HOOK BLOCK CHECK
│   ├─ if UserPromptSubmit hook rejected message
│   │   └─ FINISHED → return
│
├─ 3. PREPARE LLM PROMPT
│   ├─ prepare_llm_messages(events, condenser, llm)
│   │   ├─ Normal → messages list
│   │   └─ Condensation needed → Condensation event → return
│   │
│   └─ Context window check
│       └─ LLMContextWindowExceedError → CondensationRequest → return
│
├─ 4. CALL LLM (with retry)
│   └─ make_llm_completion(llm, messages, tools, on_token)
│
├─ 5. CLASSIFY & DISPATCH
│   ├─ classify_response(response.message)
│   │   ├─ TOOL_CALLS → _handle_tool_calls()
│   │   │   ├─ For each tool call:
│   │   │   │   ├─ Security analysis (risk analyzer)
│   │   │   │   ├─ Confirmation policy check
│   │   │   │   ├─ Execute in workspace
│   │   │   │   └─ Append observation to event log
│   │   │   └─ Return to step 1 (drain next actions)
│   │   │
│   │   ├─ CONTENT → _handle_content_response()
│   │   │   ├─ Emit MessageEvent
│   │   │   └─ Return (user turn)
│   │   │
│   │   └─ REASONING_ONLY | EMPTY → _handle_no_content_response()
│   │       └─ Ask LLM to try again
│
├─ 6. STUCK DETECTION (auxiliary service)
│   ├─ Monitors event patterns
│   ├─ Detects repeated actions, no progress
│   └─ Triggers conversation reset or user prompt
│
└─ 7. SUB-AGENT DELEGATION
    ├─ AgentDelegateAction(agent, inputs)
    ├─ Spawn child agent on shared workspace
    └─ AgentDelegateObservation(result) → back to parent
```

### OpenHands Router Strengths:
- **Event-stream architecture** — fully auditable, replayable
- **Security analyzer** — risk assessment before execution
- **Stuck detection** — detects infinite loops automatically
- **Sub-agent delegation** — parallel agents on shared workspace
- **Condensation** — automatic context compression
- **Confirmation policy** — configurable approval for risky actions
- **Multi-workspace** — Local/Docker/Remote with same code

### OpenHands Router Weaknesses:
- **No batch execution** — one action per step
- **No stale detection** — relies on stuck detection
- **No repo-map** — no structural awareness
- **Heavy architecture** — 30K+ LOC, complex configuration
- **No edit format selection** — CodeAct is the only mode

---

## 6. Mini-Coding ROUTER - Detailed State Machine

```
ask(user_message)
│
├─ 1. COMMAND CHECK
│   ├─ /help → show commands
│   ├─ /memory → show working memory
│   ├─ /session → show file path
│   ├─ /reset → clear history
│   └─ /exit → terminate
│
├─ 2. MAIN LOOP (max_attempts = max_steps x 3)
│   │
│   ├─ model.complete(messages)
│   │   └─ Returns raw text (XML or JSON)
│   │
│   ├─ parse(raw) → Action object
│   │   ├─ Parse <tool> XML tags
│   │   ├─ Extract tool name + JSON args
│   │   └─ Return Action(tool, args) or Final(text)
│   │
│   ├─ if Action:
│   │   ├─ validate_tool(tool, args) [manual checks]
│   │   │   ├─ Path within workspace? → continue
│   │   │   └─ Path outside → error message
│   │   ├─ execute(tool, args) [subprocess, 120s timeout]
│   │   ├─ Record result in messages
│   │   └─ Loop back to model.complete
│   │
│   ├─ if Final:
│   │   ├─ print(text)
│   │   └─ break
│   │
│   └─ if ParseError:
│       ├─ print("Parsing failed. Retrying...")
│       ├─ Add retry_notice to messages
│       └─ Loop back (max 3 retries per step)
│
├─ 3. DELEGATION (unique feature)
│   ├─ spawn_read_only_child(user_message)
│   │   ├─ Create child agent with read-only tools
│   │   ├─ child.ask(user_message)
│   │   ├─ Capture result
│   │   └─ Inject into parent context
│   └─ Bounded: max 1 child, read-only, 500 token output
│
├─ 4. MEMORY MANAGEMENT
│   ├─ MAX_HISTORY = 12,000 chars
│   ├─ Age-based clipping (900 chars recent, 180 chars old)
│   ├─ Working memory section (~200 chars)
│   └─ File access tracking
│
└─ return final_answer
```

### Mini-Coding Router Strengths:
- **Delegation** — bounded read-only child agents
- **Simple** — 1019 LOC, easy to understand and modify
- **Memory management** — working memory + age clipping
- **Path sandboxing** — validates all paths within workspace
- **Timeout enforcement** — 120s max per tool execution

### Mini-Coding Router Weaknesses:
- **No batch execution** — one tool per step
- **No stale detection** — can re-run same calls
- **No reflection** — no self-verification
- **No syntax validation** — no bash -n or lint
- **No cost tracking** — no budget gates
- **No error recovery** — just prints error and continues
- **No edit format** — can't do structured file edits

---

## 7. ROUTING COMPARISON TABLE

### 7.1 Core Router Features

| Feature | GGUFLoader | SWE-agent | Aider | OpenHands | Mini-Coding |
|---------|:----------:|:---------:|:-----:|:---------:|:-----------:|
| **Router type** | JSON protocol | Bash commands | Edit-format | Event-stream | XML+JSON |
| **Max steps** | 8 | unlimited | 3 reflections | unlimited | steps x 3 |
| **Batch execution** | YES | NO | NO | NO | NO |
| **Parallel tools** | YES | NO | NO | NO | NO |
| **Action format** | JSON object | Shell command | Diff blocks | Typed actions | XML tags |
| **Response parsing** | extract_json | ThoughtActionParser | Edit parser | classify_response | XML parser |

### 7.2 Error Recovery

| Recovery Type | GGUFLoader | SWE-agent | Aider | OpenHands | Mini-Coding |
|--------------|:----------:|:---------:|:-----:|:---------:|:-----------:|
| **Malformed output** | JSON repair (2x) | FormatError requery (3x) | Reflection (3x) | no_content retry | retry_notice (3x) |
| **Blocked action** | requires_approval() | _BlockedActionError | N/A | confirmation policy | path validation |
| **Syntax error** | NO | bash -n check | auto-lint | NO | NO |
| **Timeout** | per-tool (60s) | interrupt_session | NO | NO | 120s max |
| **Failed tool** | _request_fix (1x) | autosubmit | reflection | stuck detection | print error |
| **Context overflow** | HistoryProcessor | HistoryProcessor | ChatSummary | Condensation | age clipping |
| **Crash recovery** | SQLite checkpoint | autosubmit (git diff) | markdown history | event log replay | session lost |
| **Stale detection** | YES signature-based | NO | NO | NO | NO |
| **Coverage enforcement** | YES directives | NO | NO | NO | NO |

### 7.3 Budget Gates

| Budget | GGUFLoader | SWE-agent | Aider | OpenHands | Mini-Coding |
|--------|:----------:|:---------:|:-----:|:---------:|:-----------:|
| **Step limit** | max_steps=8 | NO | max_reflections=3 | NO | steps x 3 |
| **Token limit** | max_tokens=2048 | NO | max_input_tokens | context window | max_new_tokens=512 |
| **Cost limit** | NO | per_instance + total | cost tracking | NO | NO |
| **Time limit** | per-tool 60s | total_execution_timeout | NO | NO | per-tool 120s |
| **Attempt limit** | json_retries=2 | max_requeries=3 | NO | NO | max_attempts |
| **Consecutive failure** | NO (2 failures → skip) | consecutive timeouts | NO | stuck detection | NO |

### 7.4 Self-Correction Mechanisms

| Mechanism | GGUFLoader | SWE-agent | Aider | OpenHands | Mini-Coding |
|-----------|:----------:|:---------:|:-----:|:---------:|:-----------:|
| **Pre-execution validation** | validate_tool_call() | bash -n | edit parser | security analyzer | validate_tool() |
| **Post-execution verification** | NO | NO | auto-lint + auto-test | NO | NO |
| **Reflection loop** | YES (max 2) | NO | YES (max 3) | NO | NO |
| **Retry with fix** | YES _request_fix | YES requery loop | YES reflection | YES stuck detection | NO |
| **Delegation** | NO | NO | architect mode | YES sub-agents | YES read-only child |
| **Stuck detection** | NO | NO | NO | YES | NO |

---

## 8. ROUTING DECISION FLOWCHART

### 8.1 What does the router do when it gets a response?

```
GGUFLoader:
  response -> extract_json()
    + valid JSON with tool_calls -> validate -> approve? -> execute -> log -> loop
    + valid JSON with answer -> check directive -> check reflection -> done
    + invalid JSON -> repair -> retry (2x) -> fallback to raw text
    + stale repeat -> skip -> wrap up

SWE-agent:
  response -> parse_actions()
    + valid (thought, action) -> block check -> bash -n -> execute -> state -> loop
    + FormatError -> inject error template -> requery (3x)
    + BlockedAction -> inject blocked template -> requery
    + SyntaxError -> inject syntax template -> requery
    + Timeout -> interrupt -> increment counter -> requery or hard stop
    + submission detected -> handle_submission -> done

Aider:
  response -> edit parser
    + valid edit blocks -> apply -> auto-lint -> auto-test -> auto-commit -> done
    + lint errors -> feed back to model -> retry
    + test failures -> feed back to model -> retry
    + reflected_message -> loop (max 3x)
    + done -> commit -> done

OpenHands:
  response -> classify_response()
    + TOOL_CALLS -> security check -> confirm? -> execute -> append event -> loop
    + CONTENT -> emit message event -> user turn
    + REASONING_ONLY -> ask LLM to try again
    + Context overflow -> CondensationRequest -> compress -> retry
    + stuck detected -> prompt user or reset

Mini-Coding:
  response -> parse(raw)
    + Action -> validate path -> execute (120s) -> record -> loop
    + Final -> print -> done
    + ParseError -> retry_notice -> retry (3x)
    + max_attempts -> forced stop
```

---

## 9. WHAT GGUFLoader SHOULD STEAL

### From SWE-agent:
1. **bash -n syntax check** — validate commands before execution (20 lines)
2. **Autosubmit on failure** — ship partial progress instead of nothing
3. **Consecutive failure counter** — stop after N same-type failures
4. **Templated error messages** — specific recovery instructions per error type

### From Aider:
1. **Architect mode** — two-pass: plan then implement (100 lines)
2. **Auto-lint after file edits** — catch errors before they compound (50 lines)
3. **Auto-test after file edits** — verify changes work (50 lines)
4. **Repo-map** — structural awareness without scanning everything (400 lines)
5. **Cost tracking** — per-message and total cost display

### From OpenHands:
1. **Stuck detection** — detect infinite loops automatically (100 lines)
2. **Sub-agent delegation** — spawn child agents for subtasks (150 lines)
3. **Security analyzer** — risk assessment before execution (50 lines)
4. **Event-stream logging** — append-only audit trail

### From Mini-Coding:
1. **Bounded delegation** — read-only child agent (already noted)
2. **Simple memory management** — working memory section (already implemented)

---

## 10. GGUFLoader'S UNIQUE ROUTING ADVANTAGES

| Advantage | Why It Matters |
|-----------|----------------|
| **Batch execution** | Multiple tool calls per step = faster task completion |
| **Stale repeat detection** | Won't waste steps re-running identical calls |
| **Coverage directives** | Forces completeness for summarize/overview requests |
| **Reflection loop** | Model can self-verify before answering |
| **Dual JSON repair** | Handles Windows backslashes that break other parsers |
| **Desktop GUI routing** | Approval cards, reasoning blocks, follow-up chips |
| **History processor pipeline** | Composable context management (5 processors) |
| **Prompt prefix caching** | Reuses stable prompt prefix across steps |
| **Working memory** | Tracks files accessed and notes across steps |

---

## APPENDIX: ROUTING LOOP COMPLEXITY

| Harness | Loop LOC | Router LOC | Total Routing Logic |
|---------|----------|------------|---------------------|
| GGUFLoader | ~250 (process + helpers) | ~150 (extract_json + repair) | ~400 |
| SWE-agent | ~80 (run + step) | ~200 (parsers + error handling) | ~280 |
| Aider | ~300 (send_message + edit) | ~400 (repo-map + edit formats) | ~700 |
| OpenHands | ~60 (step) | ~150 (classify + dispatch) | ~210 |
| Mini-Coding | ~100 (ask + parse) | ~50 (validate + execute) | ~150 |
