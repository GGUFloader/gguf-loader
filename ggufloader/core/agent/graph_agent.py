"""
GraphAgent - LangGraph StateGraph agent for GGUF Loader.

The agent is a small ``StateGraph``:

    START -> agent -> (continue: tools -> agent | end: END)

* ``agent`` node - asks the LLM for the next JSON action (schemas +
  few-shot in the system prompt), repairing malformed JSON up to
  ``json_retries`` times. The final-answer LLM calls stream tokens.
* ``tools`` node - executes the proposed tool calls, with one corrective
  retry per failure.
* router - continues while tool calls remain and the step budget allows,
  otherwise finishes with a synthesized final answer.

Conversation state (``messages``) is checkpointed to SQLite per workspace
thread, so sessions survive restarts and every run is resumable.
Cancellation is cooperative: :meth:`cancel` sets an event the nodes check
between LLM and tool calls.

``process()`` keeps the exact ``AgentEngine`` call signature, so the
service layer can swap engines without any UI changes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, StreamWriter, interrupt
from typing import TypedDict

from .agent_engine import _SYSTEM_PROMPT, extract_json, stale_repeat_signatures, summarize_directive
from .context_budget import ContextBudget, estimate_tokens
from .tool_registry import ToolRegistry, tool_content_for_context, validate_tool_call
from .workspace_context import WorkspaceContext, PromptPrefixCache, WorkingMemory

logger = logging.getLogger(__name__)

# Lightweight system prompt for the file-assistant mode.
# Only includes what the model needs to read files and answer questions.
_LIGHT_ASSISTANT_PROMPT = """You are a helpful file assistant. You read files and help the user understand their content.

Your workspace: __WORKSPACE__

You have access to these tools:
__TOOLS__

You communicate through JSON. When you need tools, reply with ONLY a JSON object:
{
  "reasoning": "Brief explanation of what you're doing",
  "estimated_steps": 3,
  "tool_calls": [{"tool": "tool_name", "parameters": {"param": "value"}}],
  "answer": "Your final answer to the user"
}

Rules:
- Be helpful, clear, and concise
- Read files before answering questions about them
- Summarize file contents clearly for the user
- "tool_calls" and "answer" are mutually exclusive
- Never repeat a tool call whose result is already in the conversation
- Use read_file to open files (handles PDF, DOCX, Markdown)
- Use list_directory to see what files exist
- Use search_files to find text inside files
- Use glob to find files by pattern
- On your FIRST response, set "estimated_steps" to how many tool calls you expect (e.g. 2 for list+read, 5 for list+read+search+analyze)
- Update your estimate if the task turns out more complex than expected
"""

StatusCallback = Callable[[str], None]
ToolCallback = Callable[[Dict[str, Any]], None]
ApprovalCallback = Callable[[Dict[str, Any]], bool]  # (payload) -> approved?
# (prompt, max_tokens=, temperature=) -> str, or an iterable of str chunks when streaming
LLMCallable = Callable[..., Any]


def _clean_model_output(text: str) -> str:
    """Strip special tokens and thinking markers from model output.

    Some models (Gemma, Qwen, DeepSeek, etc.) emit channel markers,
    <think> tags, or other thinking tokens that should not appear in the
    final response.
    """
    import re
    # Remove <think> ... </think> blocks (streaming token)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text)
    # Remove partial <think> blocks (e.g. <think>some text without closing)
    text = re.sub(r"<think>[\s\S]*$", "", text)
    # Remove <|begin_of_thought|> ... <|end_of_thought|>
    text = re.sub(r"<\|begin_of_thought\|>[\s\S]*?<\|end_of_thought\|>", "", text)
    # Remove <|channel|> thinking markers and their content
    text = re.sub(r"<\|channel\|>\s*(?:thinking|thought)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<\|channel\|>\s*", "", text)
    # Remove other common special tokens like <|name|>, <|assistant|>, etc.
    text = re.sub(r"<\|[a-z_]+\|>", "", text)
    # Clean up extra whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class AgentCancelled(Exception):
    """Raised inside graph nodes when the user cancels the current run."""


class GraphState(TypedDict, total=False):
    messages: List[Dict[str, str]]       # persistent conversation
    tool_results: List[Dict[str, Any]]   # results accumulated in this run
    executed_calls: List[Dict[str, str]] # {"signature", "tool"} of calls that ran, in order
    directive: str                       # transient read-coverage directive
    directive_rounds: int                # directives issued this run (capped)
    step: int                            # steps used so far
    max_steps: int                       # step budget for the run
    pending_calls: List[Dict[str, Any]]  # tool calls waiting to execute
    final_answer: str                    # set when the run is done
    raw_response: str                    # last raw LLM output (fallback answer)


class GraphAgent:
    """Runs the LangGraph agent loop for a single conversation thread."""

    def __init__(
        self,
        llm: LLMCallable,
        workspace: str | Path,
        tools: Optional[ToolRegistry] = None,
        max_tokens: int = 16384,
        max_steps: int = 8,
        json_retries: int = 2,
        checkpoint_path: Optional[str | Path] = None,
        thread_id: Optional[str] = None,
        n_ctx: Optional[int] = None,
    ) -> None:
        self.llm = llm
        self.workspace = Path(workspace)
        # Only expose read-only tools by default -- keeps prompt small
        # and prevents the model from trying write/edit operations.
        READONLY_TOOLS = ["list_directory", "read_file", "search_files", "glob"]
        self.tools = tools or ToolRegistry(self.workspace, only=READONLY_TOOLS)
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.json_retries = json_retries
        self.max_directive_rounds = 1  # Only 1 extra round to read key files
        self.messages: List[Dict[str, str]] = []

        # Stable per-workspace thread id: the same folder resumes the same
        # conversation thread, even across app restarts.
        self.thread_id = thread_id or (
            "agent-" + hashlib.sha256(str(self.workspace.resolve()).encode()).hexdigest()[:16]
        )
        self._checkpoint_path = Path(checkpoint_path) if checkpoint_path else None

        self._cancel = threading.Event()
        self._failed_signatures: Dict[str, int] = {}
        self._on_status: StatusCallback = lambda _msg: None
        self._on_tool: ToolCallback = lambda _result: None
        self._on_token: Callable[[str], None] = lambda _tok: None

        # --- Lightweight core (always loaded) ---
        self._workspace_ctx = WorkspaceContext(self.workspace)
        self._prefix_cache = PromptPrefixCache()
        self._context_budget = ContextBudget(total_budget=n_ctx or max_tokens)

        # --- Lazy subsystems (only loaded when needed) ---
        self._lazy: Dict[str, Any] = {}

        self._saver_conn, self._saver = self._open_checkpointer()
        self._app = self._build_graph()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _open_checkpointer(self) -> Tuple[sqlite3.Connection, SqliteSaver]:
        """Open a SQLite checkpointer; a file path persists across restarts."""
        conn_string = ":memory:"
        if self._checkpoint_path is not None:
            self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            conn_string = str(self._checkpoint_path)
        conn = sqlite3.connect(conn_string, check_same_thread=False)
        return conn, SqliteSaver(conn)

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("agent", self._agent_node)
        graph.add_node("tools", self._tools_node)
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", self._router, {"continue": "tools", "end": END})
        graph.add_edge("tools", "agent")
        return graph.compile(checkpointer=self._saver)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def process(
        self,
        user_message: str,
        on_status: Optional[StatusCallback] = None,
        on_tool: Optional[ToolCallback] = None,
        on_token: Optional[Callable[[str], None]] = None,
        on_approval: Optional[ApprovalCallback] = None,
    ) -> Dict[str, Any]:
        """Run one agent turn through the graph.

        Returns ``{"response": str, "tool_results": [...]}``, or
        ``{"cancelled": True, ...}`` when cancelled mid-run. When a tool
        needs approval, the graph suspends and ``on_approval(payload)`` is
        called; returning True/False resumes the run accordingly.
        """
        self._cancel = threading.Event()
        self._failed_signatures = {}
        self._on_status = on_status or (lambda _msg: None)
        self._on_tool = on_tool or (lambda _result: None)
        self._on_token = on_token or (lambda _tok: None)
        self._on_approval = on_approval or (lambda _payload: True)

        base_messages = self._load_thread_messages() or list(self.messages)

        # Context compaction: trim old messages if approaching token limit
        if base_messages:
            strategy = self._context_budget.check_budget(base_messages)
            if strategy != "ok":
                on_status(f"[compact] Compacting context ({strategy})...")
                base_messages = self._context_budget.compact(base_messages)

        inputs: GraphState = {
            "messages": base_messages + [{"role": "user", "content": user_message}],
            "tool_results": [],
            "executed_calls": [],
            "directive": "",
            "directive_rounds": 0,
            "step": 0,
            "max_steps": self.max_steps,
            "pending_calls": [],
            "final_answer": "",
            "raw_response": "",
        }
        config = {"configurable": {"thread_id": self.thread_id}}

        tool_results: List[Dict[str, Any]] = []
        final_answer = ""
        try:
            stream = self._app.stream(inputs, config=config, stream_mode=["updates", "custom"])
            while True:
                interrupted = None
                for mode, payload in stream:
                    self._check_cancel()
                    if mode == "custom":
                        self._dispatch_event(payload)
                    elif mode == "updates":
                        if "__interrupt__" in payload:
                            interrupts = payload["__interrupt__"]
                            if interrupts:
                                interrupted = interrupts[0].value
                            break
                        for _node, update in payload.items():
                            if not isinstance(update, dict):
                                continue
                            if update.get("tool_results") is not None:
                                tool_results = update["tool_results"]
                            if update.get("final_answer"):
                                final_answer = update["final_answer"]
                if interrupted is None:
                    break
                # Suspend for user approval, then resume the graph from the
                # interrupt point with the decision.
                approved = self._on_approval(interrupted)
                stream = self._app.stream(
                    Command(resume=approved), config=config, stream_mode=["updates", "custom"]
                )
        except AgentCancelled:
            return {
                "cancelled": True,
                "response": final_answer or "Cancelled.",
                "tool_results": tool_results,
            }
        except Exception as e:  # noqa: BLE001 - surface graph failures to the UI
            logger.error("Agent graph error: %s", e)
            return {"response": f"Error: {e}", "tool_results": tool_results}

        # The checkpoint holds the authoritative conversation (includes the
        # assistant reply); fall back to the inputs when nothing was saved.
        self.messages = self._load_thread_messages() or inputs["messages"]

        # Update context budget for next turn
        if self.messages:
            self._context_budget.check_budget(self.messages)

        return {
            "response": final_answer or "Done.",
            "tool_results": tool_results,
        }

    def cancel(self) -> None:
        """Cooperatively stop the running turn at the next safe boundary."""
        self._cancel.set()

    def close(self) -> None:
        """Close the checkpoint connection (releases the SQLite file)."""
        try:
            self._saver_conn.close()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------
    def _agent_node(self, state: GraphState, writer: StreamWriter) -> Dict[str, Any]:
        """Ask the model for the next JSON action (or finish the run)."""
        self._check_cancel()
        step = state.get("step", 0)
        max_steps = state.get("max_steps", self.max_steps)
        messages = state.get("messages", [])
        tool_results = state.get("tool_results", [])

        # Budget exhausted - synthesize a final answer from what already ran.
        if step >= max_steps:
            answer = self._final_response(messages, tool_results, writer)
            return {
                "pending_calls": [],
                "final_answer": answer,
                "messages": messages + [{"role": "assistant", "content": answer}],
                "step": step,
            }

        writer({"event": "step", "step": step + 1, "max": max_steps})

        action, raw = self._request_action(
            messages, tool_results, writer, directive=state.get("directive", "")
        )
        if action is None:
            # Model could not produce valid JSON at all - fall back to plain chat.
            answer = _clean_model_output(raw or "I couldn't produce a valid response.")
            return {
                "pending_calls": [],
                "final_answer": answer,
                "messages": messages + [{"role": "assistant", "content": answer}],
                "raw_response": raw,
                "step": step + 1,
            }

        reasoning = _clean_model_output((action.get("reasoning") or "").strip())
        if reasoning:
            writer({"event": "status", "text": f"... {reasoning}"})

        # Dynamic step estimate: the LLM estimates how many steps it needs.
        # On first step, use the estimate; on later steps, allow the model
        # to increase (but not decrease) the budget.
        est = action.get("estimated_steps")
        if isinstance(est, (int, float)) and est > 0:
            est = min(int(est) + 1, 20)  # +1 buffer, capped at 20
            if step == 0 or est > max_steps:
                max_steps = est

        calls = [
            c for c in (action.get("tool_calls") or [])
            if isinstance(c, dict) and c.get("tool")
        ]
        if not calls:
            answer = _clean_model_output((action.get("answer") or "").strip())
            if not answer and tool_results:
                answer = self._final_response(messages, tool_results, writer)
            if not answer:
                answer = _clean_model_output(raw or "No further action needed.")
            return self._finish_or_direct(state, messages, answer, raw, step, writer, max_steps=max_steps)

        # Drop repeats of calls that already ran with a still-valid result.
        # When the model proposes nothing but stale repeats (a hedge with
        # "tool_calls" + "answer", or pure repetition), finish now: use its
        # answer, or synthesize one - never burn the step budget on the same
        # call. Re-runs after a write/edit are kept (workspace may differ).
        stale = stale_repeat_signatures(calls, state.get("executed_calls", []))
        new_calls = [c for c in calls if self._signature(c) not in stale]
        if not new_calls:
            answer = _clean_model_output((action.get("answer") or "").strip())
            if not answer:
                answer = self._final_response(messages, tool_results, writer)
            if not answer:
                answer = _clean_model_output(raw or "No further action needed.")
            return self._finish_or_direct(state, messages, answer, raw, step, writer, max_steps=max_steps)

        return {"pending_calls": new_calls, "final_answer": "", "raw_response": raw, "step": step + 1, "max_steps": max_steps}

    def _tools_node(self, state: GraphState, writer: StreamWriter) -> Dict[str, Any]:
        """Execute pending tool calls concurrently, with corrective retry per failure.

        Independent tools (read_file, list_directory, search_files, glob)
        execute in parallel via ThreadPoolExecutor for 3x speedup.
        Approval-gated tools still block sequentially.
        """
        self._check_cancel()
        calls = state.get("pending_calls", [])
        tool_results = list(state.get("tool_results", []))
        executed_calls = list(state.get("executed_calls", []))
        self._announce_plan(calls, writer)

        # Collect approvals for approval-gated tools
        approvals: Dict[int, bool] = {}
        for index, call in enumerate(calls):
            if self.tools.requires_approval(call.get("tool", ""), call.get("parameters", {})):
                payload = {
                    "type": "approval",
                    "call": call,
                    "description": self._describe(call),
                    "workspace": str(self.workspace),
                }
                writer({"event": "status", "text": f"[approve] Approval needed: {self._describe(call)}"})
                approvals[index] = bool(interrupt(payload))
        self._check_cancel()

        # Separate into approval-gated (sequential) and independent (parallel)
        independent: List[Tuple[int, Dict[str, Any]]] = []
        gated: List[Tuple[int, Dict[str, Any]]] = []
        for index, call in enumerate(calls):
            if self.tools.requires_approval(call.get("tool", ""), call.get("parameters", {})):
                gated.append((index, call))
            else:
                independent.append((index, call))

        failures: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

        # Execute independent tools concurrently
        if independent:
            def _exec_one(idx_call: Tuple[int, Dict[str, Any]]) -> Tuple[int, str, Dict[str, Any], str]:
                idx, call = idx_call
                sig = self._signature(call)
                tool_name = call.get("tool", "")
                # Skip repeated failing calls
                if self._failed_signatures.get(sig, 0) >= 2:
                    return idx, sig, {"status": "skipped", "tool_name": tool_name}, "skip"
                # Validate
                verr = validate_tool_call(call, self.tools)
                if verr:
                    return idx, sig, {"status": "error", "error": verr, "tool_name": tool_name}, "error"
                # Execute
                result = self.tools.execute(tool_name, call.get("parameters", {}))
                return idx, sig, result, "ok"

            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=min(len(independent), 4)) as pool:
                futures = {pool.submit(_exec_one, ic): ic for ic in independent}
                for future in as_completed(futures):
                    self._check_cancel()
                    idx, sig, result, status = future.result()
                    if status == "skip":
                        writer({"event": "status", "text": f"  [skip] Skipping repeated failing call: {self._describe(calls[idx])}"})
                        continue
                    if status == "error":
                        writer({"event": "status", "text": f"  [FAIL] Invalid call: {result.get('error', '')}"})
                        self._failed_signatures[sig] = self._failed_signatures.get(sig, 0) + 1
                        failures.append((calls[idx], result))
                        continue
                    tool_results.append(result)
                    executed_calls.append({"signature": sig, "tool": calls[idx].get("tool", "")})
                    writer({"event": "tool", "result": result})
                    if result.get("status") == "success":
                        writer({"event": "status", "text": f"  [OK] {self._summarize_result(result)}"})
                    else:
                        error_msg = result.get("error", "Unknown error")
                        writer({"event": "status", "text": f"  [FAIL] {error_msg}"})
                        self._failed_signatures[sig] = self._failed_signatures.get(sig, 0) + 1
                        failures.append((calls[idx], result))

        # Execute approval-gated tools sequentially
        for idx, call in gated:
            self._check_cancel()
            sig = self._signature(call)
            writer({"event": "status", "text": f"-> {self._describe(call)}"})
            if approvals.get(idx) is not None and not approvals[idx]:
                result = {"status": "error", "error": "Approval denied",
                          "tool_name": call.get("tool", "")}
            else:
                result = self.tools.execute(call.get("tool", ""), call.get("parameters", {}))
                executed_calls.append({"signature": sig, "tool": call.get("tool", "")})
            tool_results.append(result)
            writer({"event": "tool", "result": result})
            if result.get("status") == "success":
                writer({"event": "status", "text": f"  [OK] {self._summarize_result(result)}"})
            else:
                error_msg = result.get("error", "Unknown error")
                writer({"event": "status", "text": f"  [FAIL] {error_msg}"})
                self._failed_signatures[sig] = self._failed_signatures.get(sig, 0) + 1
                failures.append((call, result))

        # Retry failures
        for failed_call, failed_result in failures:
            self._check_cancel()
            fixed = self._request_fix(failed_call, failed_result, writer)
            if fixed is None:
                continue
            executed_calls.append(
                {"signature": self._signature(failed_call), "tool": failed_call.get("tool", "")}
            )
            tool_results.append(fixed)
            writer({"event": "tool", "result": fixed})
            if fixed.get("status") == "success":
                writer({"event": "status", "text": f"  [OK] retry succeeded: {self._summarize_result(fixed)}"})
            else:
                writer({"event": "status", "text": f"  [FAIL] retry failed: {fixed.get('error', 'Unknown error')}"})

        return {"tool_results": tool_results, "executed_calls": executed_calls, "pending_calls": []}

    def _router(self, state: GraphState) -> str:
        """Decide whether the loop continues or the run ends.

        Pending calls always execute (the step budget is enforced when the
        agent node is next entered), so a proposal on the final step still
        runs before the run wraps up.
        """
        self._check_cancel()
        if state.get("final_answer"):
            return "end"
        if state.get("pending_calls"):
            return "continue"
        if state.get("directive"):
            return "continue"  # loop again so the directive reaches the model
        return "end"

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------
    def _system_prompt(self) -> str:
        """Build system prompt. Uses lightweight prompt for file-assistant mode."""
        base = _LIGHT_ASSISTANT_PROMPT.replace("__WORKSPACE__", str(self.workspace))
        # Replace __TOOLS__ with actual tool descriptions
        base = base.replace("__TOOLS__", self.tools.describe())
        return base

    def _get_prefix(self) -> str:
        """Get the cached prompt prefix (system prompt + workspace context).

        Tool descriptions are already embedded in the system prompt
        via __TOOLS__ replacement, so we don't pass them separately.
        """
        return self._prefix_cache.get_prefix(
            system_prompt=self._system_prompt(),
            workspace_context="",  # already embedded in system_prompt
            tool_descriptions="",  # already embedded in system_prompt
        )

    def _build_action_prompt(self, messages, tool_results, repair: str = "", directive: str = "") -> str:
        """Build prompt using cached prefix for the stable portion."""
        prefix = self._get_prefix()
        parts = [prefix, ""]
        for msg in messages[-4:]:
            parts.append(f"{msg['role'].capitalize()}: {msg['content']}")
            parts.append("")
        if tool_results:
            parts.append("Tool results:")
            parts.extend(self._format_tool_results(tool_results))
            parts.append("")
        if repair:
            parts.append(
                "Your previous response was not valid JSON. Reply with ONLY the JSON "
                "object described above - no markdown fences, no extra text."
            )
            parts.append("")
            parts.append("Your previous (invalid) response was:")
            parts.append(repair[:1500])
            parts.append("")
        if directive:
            parts.append("IMPORTANT - follow this instruction before replying:")
            parts.append(directive)
            parts.append("")
        parts.append("Assistant:")
        return "\n".join(parts)

    def _format_tool_results(self, tool_results) -> List[str]:
        lines = []
        for result in tool_results[-3:]:
            tool = result.get("tool_name", "unknown")
            outcome = "success" if result.get("status") == "success" else "error"
            content = tool_content_for_context(result)
            if content is not None:
                lines.append(f"Tool result for {tool}: {outcome} - {content}")
            else:
                lines.append(f"Tool result for {tool}: {outcome} - {self._summarize_result(result)}")
        return lines

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------
    def _request_action(self, messages, tool_results, writer, repair: str = "", directive: str = "") -> Tuple[Optional[Dict[str, Any]], str]:
        """Ask for the next action, repairing malformed JSON up to json_retries times."""
        prompt = self._build_action_prompt(messages, tool_results, repair, directive)
        raw = self._call_llm(prompt, writer)
        data = extract_json(raw)
        if data is not None:
            return data, raw
        for _attempt in range(self.json_retries):
            prompt = self._build_action_prompt(messages, tool_results, repair=raw, directive=directive)
            raw = self._call_llm(prompt, writer)
            data = extract_json(raw)
            if data is not None:
                return data, raw
        return None, raw

    def _request_fix(self, failed_call, failed_result, writer) -> Optional[Dict[str, Any]]:
        """Ask the model to correct a failed tool call; execute the corrected call."""
        tool_name = failed_call.get("tool", "")
        params = failed_call.get("parameters", {})
        error = failed_result.get("error", "Unknown error")
        prompt = (
            self._system_prompt() + "\n\n"
            "A tool call just failed. Correct the parameters and retry, or decide it cannot be done.\n\n"
            f"Failed tool: {tool_name}\n"
            f"Parameters used: {json.dumps(params, ensure_ascii=False)[:800]}\n"
            f"Error: {error}\n\n"
            f'Respond with ONLY the JSON object. Include at most one corrected tool_calls entry for "{tool_name}" '
            '(or "tool_calls": [] if the task cannot be completed with corrected parameters).\n'
            "Assistant:"
        )
        raw = self._call_llm(prompt, writer)
        data = extract_json(raw)
        if data is None:
            return None
        calls = [c for c in (data.get("tool_calls") or []) if isinstance(c, dict) and c.get("tool")]
        if not calls:
            return None
        call = next((c for c in calls if c.get("tool") == tool_name), calls[0])
        return self.tools.execute(call.get("tool", ""), call.get("parameters", {}))

    def _final_response(self, messages, tool_results, writer) -> str:
        """Synthesize a natural-language wrap-up from tool results.

        Always returns a non-empty string. Builds a direct answer from
        tool results first (fast, no LLM call). Then optionally tries
        LLM polish -- but only streams the result if it's a valid answer.
        """
        import json as _json
        user_q = messages[-1]['content'] if messages else ''

        # --- Step 1: Build direct answer from tool results (no LLM) ---
        direct_parts = []
        for result in tool_results:
            tool = result.get("tool_name", "unknown")
            if result.get("status") != "success":
                continue
            content = tool_content_for_context(result, max_chars=1500)
            if content:
                if tool == "list_directory":
                    direct_parts.append(f"The workspace contains these files and folders:\n{content}")
                elif tool == "read_file":
                    # Trim very long file content for the answer
                    if len(content) > 1200:
                        content = content[:1200] + "..."
                    direct_parts.append(content)
                elif tool == "search_files":
                    direct_parts.append(f"Search results:\n{content}")
                else:
                    direct_parts.append(content)

        if not direct_parts:
            # No useful content from tools -- try LLM with the raw question
            response = self._call_llm(
                f"Answer this question briefly: {user_q}\n\nAssistant:",
                writer, stream_tokens=True,
            )
            if response.strip():
                return response
            return f"I was unable to find information about: {user_q}"

        direct_answer = "\n\n".join(direct_parts)

        # --- Step 2: Try LLM polish (no streaming first, to validate) ---
        context = (
            f"User asked: {user_q}\n\n"
            f"Here is what I found:\n{direct_answer}\n\n"
            f"IMPORTANT: Write a clear, natural-language answer for the user. "
            f"Do NOT call any tools. Do NOT return JSON. Just write text."
        )
        # Call WITHOUT streaming first to check the response
        response = self._call_llm(context, writer, stream_tokens=False)

        if response.strip():
            try:
                parsed = _json.loads(response.strip())
                if isinstance(parsed, dict) and (parsed.get("tool_calls") or parsed.get("answer") is None):
                    # LLM returned tool calls or invalid JSON -- use direct answer
                    pass
                elif isinstance(parsed, dict) and parsed.get("answer"):
                    # LLM returned structured answer -- use it
                    direct_answer = parsed["answer"]
                else:
                    # Raw text -- use it
                    direct_answer = response.strip()
            except (ValueError, TypeError):
                # Not JSON -- natural language, use it
                direct_answer = response.strip()

        # --- Step 3: Clean and stream the final answer ---
        direct_answer = _clean_model_output(direct_answer)

        # Send as token events so the UI shows streaming
        for i in range(0, len(direct_answer), 20):
            chunk = direct_answer[i:i+20]
            writer({"event": "token", "chunk": chunk})

        return direct_answer


    def _call_llm(self, prompt: str, writer: StreamWriter, stream_tokens: bool = False) -> str:
        """Call the LLM; streams token events when the callable yields chunks.

        Instruments: audit log, cost tracking, health metrics, rate limiting.
        """
        self._check_cancel()

        import time as _time
        llm_start = _time.monotonic()
        try:
            result = self.llm(prompt, max_tokens=self.max_tokens, temperature=0.1)
        except AgentCancelled:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("LLM call failed: %s", e)
            return ""

        # Log when response is empty to help debug
        if not result or (isinstance(result, dict) and not result.get("choices", [{}])[0].get("text")):
            logger.warning("LLM returned empty response (prompt length: %d chars)", len(prompt))

        if isinstance(result, str):
            self._check_cancel()
            return result

        # ModelBackend.__call__ without stream returns a dict
        # {"choices": [{"text": "..."}]}. Extract the text directly.
        if isinstance(result, dict):
            text = result.get("choices", [{}])[0].get("text", "")
            self._check_cancel()
            if stream_tokens and text:
                writer({"event": "token", "chunk": text})
            return text

        # Streaming: result is an iterator of token dicts or strings
        chunks: List[str] = []
        for chunk in result:
            self._check_cancel()
            if isinstance(chunk, dict):
                text = chunk.get("choices", [{}])[0].get("text", "")
                if text:
                    chunks.append(text)
                    if stream_tokens:
                        writer({"event": "token", "chunk": text})
            elif chunk:
                chunks.append(str(chunk))
                if stream_tokens:
                    writer({"event": "token", "chunk": str(chunk)})
        return "".join(chunks)

    # ------------------------------------------------------------------
    # Event plumbing
    # ------------------------------------------------------------------
    def _dispatch_event(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        event = payload.get("event")
        if event == "token":
            self._on_token(payload.get("chunk", ""))
        elif event == "status":
            self._on_status(payload.get("text", ""))
        elif event == "tool":
            result = payload.get("result")
            if isinstance(result, dict):
                self._on_tool(result)
        elif event == "step":
            step = payload.get("step", 0)
            maximum = payload.get("max", self.max_steps)
            self._on_status(f"Step {step}/{maximum}")

    def _load_thread_messages(self) -> List[Dict[str, str]]:
        """Load the conversation from the latest checkpoint of this thread."""
        try:
            tup = self._saver.get_tuple({"configurable": {"thread_id": self.thread_id}})
            if tup is not None:
                return list(tup.checkpoint["channel_values"].get("messages", []) or [])
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not load agent checkpoint: %s", e)
        return []

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise AgentCancelled()

    # ------------------------------------------------------------------
    # Loop helpers (mirror AgentEngine's wording for consistent statuses)
    # ------------------------------------------------------------------
    def _announce_plan(self, calls, writer) -> None:
        if not calls:
            return
        if len(calls) == 1:
            writer({"event": "status", "text": f"-> {self._describe(calls[0])}"})
        else:
            writer({"event": "status", "text": f"-> {len(calls)} tasks to complete:"})
            for index, call in enumerate(calls, 1):
                writer({"event": "status", "text": f"  {index}. {self._describe(call)}"})
        writer({"event": "status", "text": ""})

    def _finish_or_direct(self, state, messages, answer, raw, step, writer, max_steps=None) -> Dict[str, Any]:
        """Finish with *answer*, or loop once more to read unread files.

        For folder-wide summarize requests the run should not end while
        readable files remain unread - the model gets a directive to read
        them (capped) instead of the premature answer. The directive is
        surfaced to the UI as a status line.

        If the model already provided a substantial answer (>30 chars),
        skip the directive and return it directly.
        """
        # If the model gave a substantial answer, don't override it
        if answer and len(answer) > 30:
            answer = _clean_model_output(answer)
            return {
                "pending_calls": [],
                "final_answer": answer,
                "messages": messages + [{"role": "assistant", "content": answer}],
                "raw_response": raw,
                "step": step + 1,
                **({"max_steps": max_steps} if max_steps else {}),
            }
        directive = self._coverage_directive(state, messages)
        if directive:
            writer({"event": "status", "text": "[reading] Reading remaining files..."})
            writer({"event": "status", "text": directive})
            ret = {
                "pending_calls": [],
                "final_answer": "",
                "directive": directive,
                "directive_rounds": state.get("directive_rounds", 0) + 1,
                "step": step + 1,
            }
            if max_steps is not None:
                ret["max_steps"] = max_steps
            return ret
        ret = {
            "pending_calls": [],
            "final_answer": answer,
            "messages": messages + [{"role": "assistant", "content": answer}],
            "raw_response": raw,
            "step": step + 1,
        }
        if max_steps is not None:
            ret["max_steps"] = max_steps
        return ret

    def _coverage_directive(self, state, messages) -> str:
        """A read-coverage directive for summarize asks, or "" when satisfied."""
        if state.get("directive_rounds", 0) >= self.max_directive_rounds:
            return ""
        user_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_text = msg.get("content", "")
                break
        return summarize_directive(
            user_text, self.workspace, state.get("executed_calls", [])
        ) or ""

    def _signature(self, call: Dict[str, Any]) -> str:
        try:
            params = json.dumps(call.get("parameters", {}), sort_keys=True, ensure_ascii=False)
        except Exception:  # noqa: BLE001 - defensive
            params = str(call.get("parameters"))
        return f"{call.get('tool', '')}:{params}"

    def _is_complex(self, message: str) -> bool:
        keywords = ["complex", "multiple", "several", "build", "create system"]
        return len(message.split()) > 20 or any(w in message.lower() for w in keywords)

    def _describe(self, call: Dict[str, Any]) -> str:
        tool = call.get("tool", "unknown")
        params = call.get("parameters", {})
        if tool == "write_file":
            return f"Write {params.get('path', 'file')}"
        if tool == "edit_file":
            return f"Edit {params.get('path', 'file')}"
        if tool == "read_file":
            return f"Read {params.get('path', 'file')}"
        if tool == "list_directory":
            return f"List files in {params.get('path', '.')}"
        if tool == "search_files":
            return f"Search for '{params.get('pattern', 'text')}'"
        if tool == "run_command":
            return f"Run command: {params.get('command', '')}"
        if tool == "git":
            args = params.get("args") or []
            return "git " + " ".join(str(a) for a in args)
        return tool

    def _summarize_result(self, result: Dict[str, Any]) -> str:
        tool = result.get("tool_name", "")
        if tool == "write_file":
            return f"Created {result.get('path', 'file')}"
        if tool == "edit_file":
            return f"Modified {result.get('path', 'file')}" if result.get("changes_made") else "No changes needed"
        if tool == "read_file":
            path = result.get("path", "")
            lines = result.get("lines", 0)
            return f"Read {path} ({lines} lines)" if path else f"Read {lines} lines"
        if tool == "list_directory":
            return f"Found {len(result.get('result', []))} items"
        if tool == "search_files":
            return f"Found {result.get('total_matches', 0)} matches" if result.get("total_matches") else "No matches"
        return "Done"
