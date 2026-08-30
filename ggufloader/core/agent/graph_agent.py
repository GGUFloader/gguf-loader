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
from .audit_log import AuditLog, EventType
from .context_budget import ContextBudget, estimate_tokens
from .cost_estimator import CostEstimator
from .error_patterns import ErrorPatternDetector
from .health_monitor import HealthMonitor
from .memory_persistence import MemoryPersistence
from .mcp_bridge import MCPBridge
from .plugin_manager import PluginManager
from .profiler import AgentProfiler
from .rate_limiter import RateLimiter
from .self_improve import SelfImprove
from .session_replay import SessionReplay
from .agents_md import AgentsMdGenerator
from .session_export import SessionExport
from .tool_registry import ToolRegistry, tool_content_for_context, validate_tool_call
from .workspace_context import WorkspaceContext, PromptPrefixCache, WorkingMemory

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str], None]
ToolCallback = Callable[[Dict[str, Any]], None]
ApprovalCallback = Callable[[Dict[str, Any]], bool]  # (payload) -> approved?
# (prompt, max_tokens=, temperature=) -> str, or an iterable of str chunks when streaming
LLMCallable = Callable[..., Any]


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
    ) -> None:
        self.llm = llm
        self.workspace = Path(workspace)
        self.tools = tools or ToolRegistry(self.workspace)
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.json_retries = json_retries
        self.max_directive_rounds = 2
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

        # Workspace context and prompt prefix caching
        self._workspace_ctx = WorkspaceContext(self.workspace)
        self._prefix_cache = PromptPrefixCache()
        self._memory = WorkingMemory()

        # Long-term memory persistence (survives restarts)
        self._memory_store = MemoryPersistence(self.workspace)

        # Context budget tracking and compaction
        self._context_budget = ContextBudget()

        # Plugin system: discover and load custom tools
        self._plugin_mgr = PluginManager(self.workspace)
        self._plugin_mgr.load_all(self.tools)

        # Error pattern detection
        self._error_patterns = ErrorPatternDetector(self.workspace)

        # Self-improvement from corrections
        self._self_improve = SelfImprove(self.workspace)

        # Audit log for full traceability
        self._audit = AuditLog(self.workspace)

        # Cost estimation (tokens, throughput, electricity)
        self._cost = CostEstimator()

        # Health monitoring
        self._health = HealthMonitor()

        # Rate limiting for LLM and tool calls
        self._rate_limiter = RateLimiter()

        # Session replay for debugging
        self._replay = SessionReplay(self.workspace)
        self._replay_session = None

        # AGENTS.md generator
        self._agents_md = AgentsMdGenerator(self.workspace)

        # Session export
        self._export = SessionExport(self.workspace)

        # MCP bridge: discover and use tools from external MCP servers
        self._mcp_bridge = MCPBridge(self.workspace)

        # Performance profiler: per-step latency, throughput, bottleneck detection
        self._profiler = AgentProfiler()

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

        # Start replay session
        import time as _time
        session_id = f"replay_{int(_time.time() * 1000)}"
        self._replay_session = self._replay.create_session(session_id, title=user_message[:80])
        self._replay.record_user_message(user_message)

        # Start profiling
        self._profiler.start_run(session_id)

        # Discover MCP tools if any servers are configured
        try:
            self._mcp_bridge.register_tools(self.tools)
        except Exception:
            pass

        base_messages = self._load_thread_messages() or list(self.messages)

        # Context compaction: trim old messages if approaching token limit
        if base_messages:
            strategy = self._context_budget.check_budget(base_messages)
            if strategy != "ok":
                on_status(f"📦 Compacting context ({strategy})...")
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

        # Replay: record final response and save
        self._replay.record_agent_response(final_answer or "Done.")
        self._replay.record_state({
            "total_tokens": self._cost._total_output_tokens if hasattr(self._cost, '_total_output_tokens') else 0,
            "steps": len(tool_results),
        })
        try:
            self._replay.save_session(self._replay_session)
        except Exception:
            pass

        # Finish profiling
        profile_summary = self._profiler.finish_run()

        return {
            "response": final_answer or "Done.",
            "tool_results": tool_results,
            "profile": profile_summary,
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

        # Quick analysis on the first step of a complex request.
        if step == 0:
            last_user = messages[-1]["content"] if messages else ""
            if self._is_complex(last_user):
                writer({"event": "status", "text": "🤔 Analyzing your request..."})
                analysis = self._call_llm(
                    f"Quickly analyze this request in 2-3 concise sentences:\n\n"
                    f"User Request: {last_user}",
                    writer,
                )
                if analysis.strip():
                    writer({"event": "status", "text": f"💡 {analysis.strip()}"})
                    writer({"event": "status", "text": ""})

        action, raw = self._request_action(
            messages, tool_results, writer, directive=state.get("directive", "")
        )
        if action is None:
            # Model could not produce valid JSON at all - fall back to plain chat.
            answer = raw or "I couldn't produce a valid response."
            return {
                "pending_calls": [],
                "final_answer": answer,
                "messages": messages + [{"role": "assistant", "content": answer}],
                "raw_response": raw,
                "step": step + 1,
            }

        reasoning = (action.get("reasoning") or "").strip()
        if reasoning:
            writer({"event": "status", "text": f"💭 {reasoning}"})

        calls = [
            c for c in (action.get("tool_calls") or [])
            if isinstance(c, dict) and c.get("tool")
        ]
        if not calls:
            answer = (action.get("answer") or "").strip()
            if not answer and tool_results:
                answer = self._final_response(messages, tool_results, writer)
            if not answer:
                answer = raw or "No further action needed."
            return self._finish_or_direct(state, messages, answer, raw, step, writer)

        # Drop repeats of calls that already ran with a still-valid result.
        # When the model proposes nothing but stale repeats (a hedge with
        # "tool_calls" + "answer", or pure repetition), finish now: use its
        # answer, or synthesize one - never burn the step budget on the same
        # call. Re-runs after a write/edit are kept (workspace may differ).
        stale = stale_repeat_signatures(calls, state.get("executed_calls", []))
        new_calls = [c for c in calls if self._signature(c) not in stale]
        if not new_calls:
            answer = (action.get("answer") or "").strip()
            if not answer:
                answer = self._final_response(messages, tool_results, writer)
            if not answer:
                answer = raw or "No further action needed."
            return self._finish_or_direct(state, messages, answer, raw, step, writer)

        return {"pending_calls": new_calls, "final_answer": "", "raw_response": raw, "step": step + 1}

    def _tools_node(self, state: GraphState, writer: StreamWriter) -> Dict[str, Any]:
        """Execute pending tool calls, with one corrective retry per failure.

        Sensitive calls (shell commands, git writes) are approved up front
        via LangGraph interrupts before anything executes, so a suspension
        never loses results from calls that already ran.
        """
        self._check_cancel()
        calls = state.get("pending_calls", [])
        tool_results = list(state.get("tool_results", []))
        executed_calls = list(state.get("executed_calls", []))
        self._announce_plan(calls, writer)

        approvals: Dict[int, bool] = {}
        for index, call in enumerate(calls):
            if self.tools.requires_approval(call.get("tool", ""), call.get("parameters", {})):
                payload = {
                    "type": "approval",
                    "call": call,
                    "description": self._describe(call),
                    "workspace": str(self.workspace),
                }
                writer({"event": "status", "text": f"🔐 Approval needed: {self._describe(call)}"})
                approvals[index] = bool(interrupt(payload))
        self._check_cancel()

        failures: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        for index, call in enumerate(calls, 1):
            self._check_cancel()
            if len(calls) > 1:
                writer({"event": "status", "text": f"[{index}/{len(calls)}] {self._describe(call)}"})
            signature = self._signature(call)
            if self._failed_signatures.get(signature, 0) >= 2:
                writer({"event": "status", "text": f"  ⏭ Skipping repeated failing call: {self._describe(call)}"})
                continue
            # Validate tool call before execution
            validation_error = validate_tool_call(call, self.tools)
            if validation_error:
                writer({"event": "status", "text": f"  ✗ Invalid call: {validation_error}"})
                self._failed_signatures[signature] = self._failed_signatures.get(signature, 0) + 1
                failures.append((call, {"status": "error", "error": validation_error, "tool_name": call.get("tool", "")}))
                continue
            # Audit: log tool call
            self._audit.log_tool_call(call.get("tool", "unknown"), call.get("parameters", {}))
            # Replay: record tool call
            self._replay.record_tool_call(call.get("tool", "unknown"), call.get("parameters", {}))
            # Rate limit check for tools
            self._rate_limiter.allow_tool()
            if index - 1 in approvals and not approvals[index - 1]:
                result = {"status": "error", "error": "Approval denied by the user",
                          "tool_name": call.get("tool", "")}
                self._audit.log_approval(call.get("tool", "unknown"), "denied")
            else:
                if index - 1 in approvals:
                    self._audit.log_approval(call.get("tool", "unknown"), "approved")
                self._profiler.begin_step("tool_execute", tool_name=call.get("tool", ""))
                result = self.tools.execute(call.get("tool", ""), call.get("parameters", {}))
                self._profiler.end_step(
                    success=result.get("status") == "success",
                    error=result.get("error", ""),
                )
                executed_calls.append(
                    {"signature": signature, "tool": call.get("tool", "")}
                )
            tool_results.append(result)
            writer({"event": "tool", "result": result})
            # Audit: log tool result
            self._audit.log_tool_result(
                call.get("tool", "unknown"),
                result.get("status", "unknown"),
                error=result.get("error"),
            )
            # Replay: record tool result
            self._replay.record_tool_result(
                call.get("tool", "unknown"),
                result.get("status", "unknown"),
                error=result.get("error"),
            )
            # Health: record tool metrics
            self._health.increment("tool_calls")
            if result.get("status") == "success":
                self._health.increment("tool_successes")
                writer({"event": "status", "text": f"  ✓ {self._summarize_result(result)}"})
            else:
                self._health.increment("errors")
                error_msg = result.get("error", "Unknown error")
                writer({"event": "status", "text": f"  ✗ {error_msg}"})
                self._failed_signatures[signature] = self._failed_signatures.get(signature, 0) + 1
                # Record error pattern for self-improvement
                try:
                    self._error_patterns.record_error(
                        "tool_failure", error_msg,
                        tool=call.get("tool", ""),
                        file_path=str(call.get("parameters", {}).get("path", "")),
                    )
                except Exception:
                    pass
                failures.append((call, result))

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
                writer({"event": "status", "text": f"  ✓ retry succeeded: {self._summarize_result(fixed)}"})
            else:
                writer({"event": "status", "text": f"  ✗ retry failed: {fixed.get('error', 'Unknown error')}"})

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
        """Build system prompt with workspace context, AGENTS.md, memory, and learned patterns."""
        base = _SYSTEM_PROMPT.replace("__WORKSPACE__", str(self.workspace))
        workspace_ctx = self._workspace_ctx.build_context()
        if workspace_ctx:
            base += "\n\n" + workspace_ctx
        # Inject long-term memory
        memory_ctx = self._memory_store.get_context(max_chars=2000)
        if memory_ctx:
            base += "\n\n" + memory_ctx
        # Inject error patterns (things to avoid)
        patterns = self._error_patterns.get_patterns(min_occurrences=2)
        if patterns:
            error_lines = ["## Known Error Patterns (avoid these)"]
            for p in patterns[:10]:
                fix = f" → {p.suggested_fix}" if p.suggested_fix else ""
                error_lines.append(f"- {p.description} ({p.occurrences}x){fix}")
            base += "\n\n" + "\n".join(error_lines)
        # Inject self-improvement advice
        improve_ctx = self._self_improve.get_advice("general")
        if improve_ctx:
            base += "\n\n" + improve_ctx
        return base

    def _get_prefix(self) -> str:
        """Get the cached prompt prefix (system prompt + tools + workspace context)."""
        return self._prefix_cache.get_prefix(
            system_prompt=self._system_prompt(),
            workspace_context="",  # already embedded in system_prompt
            tool_descriptions=self.tools.describe(),
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
        for result in tool_results[-12:]:
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
        """Synthesize a natural-language wrap-up; streams tokens when possible."""
        context = [
            f"User asked: {messages[-1]['content'] if messages else ''}",
            "",
            "I completed these operations:",
        ]
        for result in tool_results:
            tool = result.get("tool_name", "unknown")
            if result.get("status") == "success":
                content = tool_content_for_context(result, max_chars=2000)
                context.append(f"✓ {tool}: {content or 'Success'}")
            else:
                context.append(f"✗ {tool}: {result.get('error', 'Failed')}")
        context.append(
            "\nProvide a brief, natural response to the user. Don't repeat what they saw "
            "in the status updates - just give the key takeaway or next steps."
        )
        response = self._call_llm("\n".join(context), writer, stream_tokens=True)
        if response.strip():
            return response
        success = sum(1 for r in tool_results if r.get("status") == "success")
        if success == len(tool_results) and tool_results:
            return "Done! All operations completed successfully."
        if success > 0:
            return f"Completed {success} out of {len(tool_results)} operations. Some had issues."
        return "Ran into some issues completing those operations. Check the errors above."

    def _call_llm(self, prompt: str, writer: StreamWriter, stream_tokens: bool = False) -> str:
        """Call the LLM; streams token events when the callable yields chunks.

        Instruments: audit log, cost tracking, health metrics, rate limiting.
        """
        self._check_cancel()

        # Rate limit check
        self._rate_limiter.allow_llm()

        # Profiling: begin step
        self._profiler.begin_step("llm_call")

        # Audit: log LLM request
        self._audit.log(EventType.LLM_REQUEST, {
            "prompt_preview": prompt[:200],
            "max_tokens": self.max_tokens,
        })

        import time as _time
        llm_start = _time.monotonic()
        try:
            result = self.llm(prompt, max_tokens=self.max_tokens, temperature=0.1)
        except AgentCancelled:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("LLM call failed: %s", e)
            self._audit.log(EventType.LLM_ERROR, {"error": str(e)})
            self._health.increment("errors")
            return ""
        llm_ms = int((_time.monotonic() - llm_start) * 1000)

        if isinstance(result, str):
            self._check_cancel()
            # Estimate tokens (4 chars per token)
            out_tokens = max(1, len(result) // 4)
            in_tokens = max(1, len(prompt) // 4)
            self._cost.record_call(in_tokens, out_tokens, llm_ms)
            self._audit.log(EventType.LLM_RESPONSE, {
                "tokens_out": out_tokens, "latency_ms": llm_ms,
            })
            self._health.record("llm.latency_ms", llm_ms)
            self._health.increment("llm_calls")
            self._profiler.end_step(input_tokens=in_tokens, output_tokens=out_tokens)
            return result
        chunks: List[str] = []
        for chunk in result:
            self._check_cancel()
            if chunk:
                chunks.append(chunk)
                if stream_tokens:
                    writer({"event": "token", "chunk": chunk})
        full = "".join(chunks)
        out_tokens = max(1, len(full) // 4)
        in_tokens = max(1, len(prompt) // 4)
        self._cost.record_call(in_tokens, out_tokens, llm_ms)
        self._audit.log(EventType.LLM_RESPONSE, {
            "tokens_out": out_tokens, "latency_ms": llm_ms,
        })
        self._health.record("llm.latency_ms", llm_ms)
        self._health.increment("llm_calls")
        self._profiler.end_step(input_tokens=in_tokens, output_tokens=out_tokens)
        return full

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
            if step > 1:
                self._on_status(f"▶ Step {step}/{maximum}")

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
            writer({"event": "status", "text": f"→ {self._describe(calls[0])}"})
        else:
            writer({"event": "status", "text": f"→ {len(calls)} tasks to complete:"})
            for index, call in enumerate(calls, 1):
                writer({"event": "status", "text": f"  {index}. {self._describe(call)}"})
        writer({"event": "status", "text": ""})

    def _finish_or_direct(self, state, messages, answer, raw, step, writer) -> Dict[str, Any]:
        """Finish with *answer*, or loop once more to read unread files.

        For folder-wide summarize requests the run should not end while
        readable files remain unread - the model gets a directive to read
        them (capped) instead of the premature answer. The directive is
        surfaced to the UI as a status line.
        """
        directive = self._coverage_directive(state, messages)
        if directive:
            writer({"event": "status", "text": "📖 Reading remaining files…"})
            writer({"event": "status", "text": directive})
            return {
                "pending_calls": [],
                "final_answer": "",
                "directive": directive,
                "directive_rounds": state.get("directive_rounds", 0) + 1,
                "step": step + 1,
            }
        return {
            "pending_calls": [],
            "final_answer": answer,
            "messages": messages + [{"role": "assistant", "content": answer}],
            "raw_response": raw,
            "step": step + 1,
        }

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
