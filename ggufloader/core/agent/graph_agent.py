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

import functools
import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, StreamWriter, interrupt
from typing import TypedDict

from .context_budget import ContextBudget, estimate_tokens
from .prompt_builder import PromptBuilder
from .token_cleaner import TokenCleaner, get_cleaner
from .tool_orchestrator import ToolOrchestrator
from .tool_registry import ToolRegistry, tool_content_for_context, validate_tool_call
from .workspace_context import WorkspaceContext, PromptPrefixCache, WorkingMemory

logger = logging.getLogger(__name__)


def strip_tool_envelope(text: str) -> str:
    """Remove a leading tool-call JSON envelope from a final answer.

    The model sometimes opens its prose answer with a (possibly fenced)
    ``{"tool_calls": []}`` object — the same envelope shape it uses for
    tool calls — before the real text. The plan/answer prompts forbid
    JSON, but a 12B quant frequently leaks the envelope anyway. This
    drops the leading object (and any fence around/after it) when it
    parses as a dict carrying a ``tool_calls`` key:

    - ``{"tool_calls": []}\nBased on the files...`` -> prose only
    - ```json block + envelope + prose`` -> prose only
    - ``{"tool_calls": [], "answer": "..."}`` -> the ``answer`` field

    Anything that does not start with such an envelope is returned
    unchanged, so ordinary prose (or prose that merely *mentions* JSON)
    is never touched.
    """
    if not text or not text.strip():
        return text
    s = text.strip()

    # Peel one optional ``` fence that may wrap the whole reply.
    if s.startswith("```"):
        first_nl = s.find("\n")
        s = s[first_nl + 1:] if first_nl != -1 else ""
        if s.endswith("```"):
            s = s[:-3].rstrip()
    if not s.startswith("{"):
        return text

    try:
        obj, end = json.JSONDecoder().raw_decode(s)
    except (ValueError, TypeError):
        return text  # not a leading JSON object - leave it alone
    if not isinstance(obj, dict) or "tool_calls" not in obj:
        return text  # not a tool-call envelope

    rest = s[end:].strip()
    # The envelope was fenced; its closing ``` may now lead the prose.
    if rest.startswith("```"):
        nl = rest.find("\n")
        rest = rest[nl + 1:].strip() if nl != -1 else ""
    if rest:
        return rest
    answer = obj.get("answer")
    return answer.strip() if isinstance(answer, str) else ""


# Phrases that mean the model dodged instead of answering. When tool
# evidence exists, a refusal must never reach the user — fall back to a
# deterministic rendering of that evidence instead.
_REFUSAL_PHRASES = (
    "do not have access", "don't have access", "cannot access", "can't access",
    "no access to", "unable to access", "without access to", "need access to",
    "as an ai", "as a language model", "cannot see your", "i am unable to see",
    "do not have the ability", "i do not have access", "i don't have access",
)


def _looks_like_refusal(text: str) -> bool:
    """True when *text* reads like an access/no-permission dodge, not an answer."""
    low = (text or "").lower()[:600]
    return any(p in low for p in _REFUSAL_PHRASES)


class _NoopWriter:
    """No-op StreamWriter for calls outside the graph runtime."""
    def __call__(self, data):
        pass


StatusCallback = Callable[[str], None]
ToolCallback = Callable[[Dict[str, Any]], None]
ApprovalCallback = Callable[[Dict[str, Any]], bool]
LLMCallable = Callable[..., Any]


class AgentCancelled(Exception):
    """Raised inside graph nodes when the user cancels the current run."""


class GraphState(TypedDict, total=False):
    messages: List[Dict[str, str]]       # persistent conversation
    tool_results: List[Dict[str, Any]]   # results accumulated in this run
    executed_calls: List[Dict[str, str]] # {"signature", "tool"} of calls that ran, in order
    step: int                            # steps used so far
    max_steps: int                       # step budget for the run
    pending_calls: List[Dict[str, Any]]  # tool calls waiting to execute
    final_answer: str                    # set when the run is done
    raw_response: str                    # last raw LLM output (fallback answer)
    plan: List[Dict[str, Any]]           # step plan from the planner node
    plan_index: int                      # current position in plan (0-based)


class GraphAgent:
    """Runs the LangGraph agent loop for a single conversation thread."""

    def __init__(
        self,
        llm: LLMCallable,
        workspace: str | Path,
        tools: Optional[ToolRegistry] = None,
        max_tokens: int = 4096,
        max_steps: int = 16,
        json_retries: int = 2,
        checkpoint_path: Optional[str | Path] = None,
        thread_id: Optional[str] = None,
        n_ctx: Optional[int] = None,
        cleaner: Optional[TokenCleaner] = None,
        system_prompt: Optional[str] = None,
        preset_prompt: Optional[str] = None,
        task_prompts: Optional[Dict[str, str]] = None,
        allowed_tools: Optional[List[str]] = None,
        blocked_tools: Optional[List[str]] = None,
    ) -> None:
        self.llm = llm
        self.workspace = Path(workspace)
        READONLY_TOOLS = ["list_directory", "read_file", "search_files", "glob"]
        if tools is not None:
            self.tools = tools
        elif allowed_tools is not None:
            # Preset restricts to specific tools
            self.tools = ToolRegistry(self.workspace, only=allowed_tools)
        else:
            self.tools = ToolRegistry(self.workspace, only=READONLY_TOOLS)
        # Block specific tools if preset says so
        if blocked_tools:
            for tool_name in blocked_tools:
                self.tools._tools.pop(tool_name, None)
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.json_retries = json_retries
        self.messages: List[Dict[str, str]] = []

        self.thread_id = thread_id or (
            "agent-" + hashlib.sha256(str(self.workspace.resolve()).encode()).hexdigest()[:16]
        )
        self._checkpoint_path = Path(checkpoint_path) if checkpoint_path else None

        self._cancel = threading.Event()
        self._failed_signatures: Dict[str, int] = {}
        self._on_status: StatusCallback = lambda _msg: None
        self._on_tool: ToolCallback = lambda _result: None
        self._on_token: Callable[[str], None] = lambda _tok: None
        self._on_plan: Callable[[str, List[Dict[str, Any]]], None] = lambda _phase, _plan: None
        # Live deltas from the planner node's LLM call (plan reasoning).
        # Streamed to the UI as 'reasoning' events so "Planning..." shows
        # live text instead of a silent wait.
        self._on_plan_stream: Callable[[str], None] = lambda _tok: None

        # --- Extracted modules (delegated responsibilities) ---
        self._prompt_builder = PromptBuilder(
            self.workspace,
            self.tools,
            system_prompt_override=system_prompt,
            preset_override=preset_prompt,
        )
        self._cleaner: TokenCleaner = cleaner or get_cleaner()
        self._tool_orch: Optional[ToolOrchestrator] = None  # created per turn

        # --- Lightweight core (always loaded) ---
        self._workspace_ctx = WorkspaceContext(self.workspace)
        self._prefix_cache = PromptPrefixCache()
        self._context_budget = ContextBudget(total_budget=n_ctx or max_tokens)
        self._task_prompts = task_prompts or {}

        # --- Lazy subsystems (only loaded when needed) ---
        self._lazy: Dict[str, Any] = {}

        self._saver_conn, self._saver = self._open_checkpointer()
        self._trace = os.environ.get("GGUF_GRAPH_TRACE", "1") != "0"
        self._node_visits: Dict[str, int] = {}
        self._app = self._build_graph()

    def _clean(self, text: str) -> str:
        """Delegate to the model-specific token cleaner."""
        return self._cleaner.clean(text)

    def _system_prompt(self, with_tools: bool = True, with_mode: bool = True) -> str:
        """Build system prompt (delegated to PromptBuilder)."""
        return self._prompt_builder.system_prompt(
            with_tools=with_tools, with_mode=with_mode)

    def _prefixed_prompt(
        self, prompt: str, with_tools: bool = False, with_mode: bool = False
    ) -> str:
        """Prepend the router system prompt when one is available.

        The plan/answer paths build standalone prompts; prefixing keeps the
        model's identity, tool rules, and anti-refusal guidance in front of
        every call. Falls back to the bare prompt if no router prompt exists.
        ``with_tools`` and ``with_mode`` both default to False here: the plan
        prompt carries its own tool list, and answer synthesis should never
        be flooded with tool schemas or preset mode text ("commit changes /
        run tests") — that framing belongs to tool execution, not to
        answering. There is no reactive action loop anymore: the planner
        node composes the full family + mode + tools prompt for the plan
        call.
        """
        try:
            return self._system_prompt(
                with_tools=with_tools, with_mode=with_mode) + "\n\n" + prompt
        except RuntimeError:
            return prompt

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _open_checkpointer(self) -> Tuple[sqlite3.Connection, SqliteSaver]:
        conn_string = ":memory:"
        if self._checkpoint_path is not None:
            self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            conn_string = str(self._checkpoint_path)
        conn = sqlite3.connect(conn_string, check_same_thread=False)
        return conn, SqliteSaver(conn)

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("planner", self._traced_node("planner", self._planner_node))
        graph.add_node("agent", self._traced_node("agent", self._agent_node))
        graph.add_node("tools", self._traced_node("tools", self._tools_node))
        graph.add_edge(START, "planner")
        graph.add_edge("planner", "agent")
        graph.add_conditional_edges("agent", self._router, {"continue": "tools", "end": END})
        graph.add_edge("tools", "agent")
        return graph.compile(checkpointer=self._saver)

    # ------------------------------------------------------------------
    # Node tracing (architecture visibility in the server log)
    # ------------------------------------------------------------------
    def _traced_node(self, name: str, node_fn):
        """Wrap a graph node with entry/exit/duration logging.

        Every planner/agent/tools visit in a turn is logged at INFO with
        timing and a compact state summary, so architecture issues (wrong
        node order, repeated tool entries, silent terminal paths, a plan
        that never advances) show up directly in the server log. Disable
        with ``GGUF_GRAPH_TRACE=0``.
        """
        @functools.wraps(node_fn)
        def _wrapped(state, writer):
            self._node_visits[name] = self._node_visits.get(name, 0) + 1
            t0 = time.perf_counter()
            if self._trace:
                logger.info("[graph] %s enter | %s", name,
                            self._node_entry_detail(name, state))
            try:
                result = node_fn(state, writer)
            except AgentCancelled:
                if self._trace:
                    logger.info("[graph] %s cancel | %.0fms", name,
                                (time.perf_counter() - t0) * 1000)
                raise
            if self._trace:
                logger.info(
                    "[graph] %s exit  | %.0fms | %s", name,
                    (time.perf_counter() - t0) * 1000,
                    self._node_exit_detail(name, result),
                )
            return result
        return _wrapped

    def _node_entry_detail(self, name: str, state: GraphState) -> str:
        """Compact per-node entry context for the trace line."""
        if name == "planner":
            user = ""
            for msg in reversed(state.get("messages") or []):
                if msg.get("role") == "user":
                    user = (msg.get("content") or "")[:100]
                    break
            return f"user={user!r}"
        plan = state.get("plan") or []
        plan_index = state.get("plan_index", 0)
        pending = [c.get("tool") for c in (state.get("pending_calls") or [])
                   if isinstance(c, dict)]
        if name == "agent":
            if plan and plan_index < len(plan):
                item = plan[plan_index]
                mode = f"plan-step {item.get('step')}/{len(plan)} tool={item.get('tool')!r}"
            else:
                mode = "terminal"
            return (f"step={state.get('step', 0)} plan_idx={plan_index}/{len(plan)} "
                    f"mode={mode}")
        if name == "tools":
            return f"pending_calls={pending}"
        return ""

    def _node_exit_detail(self, name: str, result: Dict[str, Any]) -> str:
        """Compact per-node exit summary for the trace line."""
        if name == "planner":
            plan = result.get("plan") or []
            tool_steps = sum(1 for s in plan if s.get("tool"))
            return f"plan={len(plan)} steps ({tool_steps} tool)"
        if name == "agent":
            answer = result.get("final_answer") or ""
            calls = [c.get("tool") for c in (result.get("pending_calls") or [])
                     if isinstance(c, dict)]
            bits = []
            if answer:
                bits.append(f"final_answer={len(answer)}ch")
            if calls:
                bits.append(f"->tools {calls}")
            if result.get("plan_index") is not None:
                bits.append(f"plan_idx={result.get('plan_index')}")
            return " | ".join(bits) if bits else "noop"
        if name == "tools":
            results = result.get("tool_results") or []
            if not results:
                return "no results"
            last = results[-1]
            err = (last.get("error") or "")[:60]
            summary = f"{len(results)} results, last: {last.get('tool_name', '?')}={last.get('status')}"
            return summary + (f" err={err!r}" if err else "")
        return ""

    def _log_turn_summary(self, t0: float, tool_results, final_answer: str,
                          cancelled: bool = False) -> None:
        """One per-turn rollup line: total time, node visit counts, tools."""
        if not self._trace:
            return
        logger.info(
            "[graph] turn done | %.0fms | cancelled=%s | visits=%s | "
            "tools=%d | answer=%dch",
            (time.perf_counter() - t0) * 1000, cancelled,
            dict(self._node_visits), len(tool_results or []),
            len(final_answer or ""),
        )

    # ------------------------------------------------------------------
    # Planning phase
    # ------------------------------------------------------------------
    # StreamWriter can't be instantiated outside the graph runtime,
    # so we use a no-op writer for calls outside the graph.
    def _create_plan(
        self, user_message: str, on_status: StatusCallback,
        writer: Optional[StreamWriter] = None,
    ) -> List[Dict[str, Any]]:
        """Ask the LLM to create a concrete, tool-call plan with dependencies.

        The plan is a list of steps, each with:
          - step: int (1-based)
          - description: what this step does
          - tool: tool name (null for answer-only steps)
          - parameters: dict of tool parameters (may reference STEP_N.result)
          - depends_on: list of step numbers whose results this step needs
          - status: pending/running/done/failed
          - result: filled after execution

        Runs on every turn — this is the ONLY gate to tool execution (no
        reactive loop), so malformed JSON is retried with a repair hint.
        """
        tools_list = self.tools.describe()
        # Use task-specific plan prompt from router if available
        if self._task_prompts.get("plan"):
            prompt = self._task_prompts["plan"].replace("{tools}", tools_list).replace("{request}", user_message)
        else:
            prompt = (
                f"User request: {user_message}\n\n"
                f"Available tools: {tools_list}\n\n"
                "Create a plan. Reply with ONLY a JSON object:\n"
                '{"goal": "one sentence", "steps": [{"step": 1, "description": "what to do", "tool": "name or null", "parameters": {}, "depends_on": []}]}'
                "Rules:\n"
                "1. General knowledge questions: 1 step, tool=null, answer directly.\n"
                "2. File tasks: 2-4 steps with tools.\n"
                "3. Max 6 steps. Each step = one action.\n"
                "4. Last step is always the answer (tool=null).\n"
                "5. To FIND a file by name or path use glob; search_files searches text INSIDE files.\n"
                "6. Report only what tool results show. Zero matches means nothing was found — never invent file names or paths.\n\n"
                "Plan:"
            )
        # The router system prompt leads every plan request too — never a
        # plan-mode blind spot. Mode text IS included here: the preset is
        # policy for which tools/actions the plan may propose (e.g. a
        # read-only research preset must not plan writes).
        prompt = self._prefixed_prompt(prompt, with_tools=False, with_mode=True)

        _status = on_status or (lambda _msg: None)
        _status("Planning...")
        import json as _json
        plan = []
        # Clean gemma channel tokens before EVERY parse (same rule as action
        # parsing), and retry malformed JSON with a repair hint — the planner
        # is the only gate to tool execution, so a parse failure must be rare.
        # The call streams its deltas as 'reasoning' events (purpose="plan"
        # routes them to _on_plan_stream, not the chat bubble) so the UI shows
        # the plan being formed live instead of a silent "Planning..." wait.
        for attempt in range(1 + max(self.json_retries, 1)):
            try:
                raw = self._call_llm(
                    prompt, writer or _NoopWriter(),
                    stream_tokens=True, purpose="plan",
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("Plan creation failed: %s", e)
                return []
            text = self._clean(raw).strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            try:
                parsed = _json.loads(text)
            except (ValueError, TypeError):
                parsed = None
            steps = parsed.get("steps", []) if isinstance(parsed, dict) else parsed
            if isinstance(steps, list):
                for item in steps:
                    if isinstance(item, dict):
                        plan.append({
                            "step": item.get("step", len(plan) + 1),
                            "description": str(item.get("description", "")),
                            "tool": item.get("tool"),
                            "parameters": item.get("parameters", {}),
                            "depends_on": item.get("depends_on", []),
                            "status": "pending",
                            "result": None,
                        })
                break
            logger.warning(
                "_create_plan: could not parse plan JSON (attempt %d). raw=%.200r",
                attempt + 1, text,
            )
            plan = []
            prompt = prompt + (
                "\n\nYour previous response was not valid plan JSON. "
                'Reply with ONLY a JSON object: {"goal": "...", '
                '"steps": [{"step": 1, "description": "...", "tool": "name or null", '
                '"parameters": {}, "depends_on": []}]} — no prose, no code fences.'
            )

        # Cap plan length — LLMs often create too many steps despite instructions
        MAX_PLAN_STEPS = 6
        if len(plan) > MAX_PLAN_STEPS:
            # Keep first N-1 tool steps + last answer step
            tool_steps = [s for s in plan if s.get("tool") is not None]
            answer_step = [s for s in plan if s.get("tool") is None]
            kept = tool_steps[:MAX_PLAN_STEPS - 1]
            if answer_step:
                kept.append(answer_step[-1])
            # Renumber steps
            for i, item in enumerate(kept, 1):
                item["step"] = i
            plan = kept
            _status(f"[plan] Trimmed to {len(plan)} steps (was {len(plan) + (MAX_PLAN_STEPS - len(plan))})")

        # Strict plan-driven guarantee: the final answer must come from the
        # plan's answer step. If the model produced only tool steps, append
        # an answer step that depends on the last tool step.
        if plan and plan[-1].get("tool") is not None:
            last_step = plan[-1]["step"]
            plan.append({
                "step": last_step + 1,
                "description": "Summarize the results and answer the user",
                "tool": None,
                "parameters": {},
                "depends_on": [last_step],
                "status": "pending",
                "result": None,
            })

        if plan:
            goal = parsed.get("goal", user_message[:100]) if isinstance(parsed, dict) else user_message[:100]
            _status(f"Goal: {goal}")
            _status(f"Plan ({len(plan)} steps):")
            for item in plan:
                tool_info = f" [{item['tool']}]" if item.get("tool") else ""
                deps = f" (needs: {item['depends_on']})" if item.get("depends_on") else ""
                _status(f"  {item['step']}. {item['description']}{tool_info}{deps}")
            logger.info("Agent plan: %d steps for %r", len(plan), user_message[:80])

        return plan

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
        on_plan: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,
        on_plan_stream: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Run one agent turn through the graph.

        Returns {"response": str, "tool_results": [...]}, or
        {"cancelled": True, ...} when cancelled mid-run.
        """
        self._cancel = threading.Event()
        self._failed_signatures = {}
        self._on_status = on_status or (lambda _msg: None)
        self._on_tool = on_tool or (lambda _result: None)
        self._on_token = on_token or (lambda _tok: None)
        self._on_approval = on_approval or (lambda _payload: True)
        self._on_plan = on_plan or (lambda _phase, _plan: None)
        self._on_plan_stream = on_plan_stream or (lambda _tok: None)

        # Per-turn node tracing: reset visit counts, start the turn clock.
        self._node_visits = {}
        turn_t0 = time.perf_counter()

        # Create tool orchestrator for this turn. Thread the router system
        # prompt through so the failed-tool repair path uses the same prompt
        # (PromptBuilder raises when no prompt is provided).
        try:
            orch_prompt = self._prompt_builder.system_prompt()
        except RuntimeError:
            orch_prompt = None
        self._tool_orch = ToolOrchestrator(
            self.tools, str(self.workspace), self._failed_signatures,
            system_prompt=orch_prompt,
        )

        base_messages = self._load_thread_messages() or list(self.messages)

        if base_messages:
            strategy = self._context_budget.check_budget(base_messages)
            if strategy != "ok":
                on_status(f"[compact] Compacting context ({strategy})...")
                base_messages = self._context_budget.compact(base_messages)        # --- Execute through the graph (planner node → agent ⇄ tools) ---
        # The planner is a LangGraph node now: it runs inside the graph as
        # its first node, produces the plan (or decides none is needed),
        # and fires on_plan. The agent/tools nodes then execute that plan
        # step by step; when the planner produced nothing, the agent node
        # falls back to the reactive loop and says so.
        inputs: GraphState = {
            "messages": base_messages + [{"role": "user", "content": user_message}],
            "tool_results": [],
            "executed_calls": [],
            "step": 0,
            "max_steps": self.max_steps,
            "pending_calls": [],
            "final_answer": "",
            "raw_response": "",
            "plan": [],
            "plan_index": 0,
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
                approved = self._on_approval(interrupted)
                stream = self._app.stream(
                    Command(resume=approved), config=config, stream_mode=["updates", "custom"]
                )
        except AgentCancelled:
            self._log_turn_summary(turn_t0, tool_results, final_answer or "", cancelled=True)
            return {
                "cancelled": True,
                "response": final_answer or "Cancelled.",
                "tool_results": tool_results,
            }
        except Exception as e:  # noqa: BLE001
            logger.error("Agent graph error: %s", e)
            self._log_turn_summary(turn_t0, tool_results, final_answer or "")
            return {"response": f"Error: {e}", "tool_results": tool_results}

        self.messages = self._load_thread_messages() or inputs["messages"]

        if self.messages:
            self._context_budget.check_budget(self.messages)

        answer = final_answer or self._diagnostic(
            "loop ended with no answer", self.max_steps, self.max_steps, tool_results
        )
        self._log_turn_summary(turn_t0, tool_results, answer)
        return {
            "response": answer,
            "tool_results": tool_results,
        }

    def cancel(self) -> None:
        self._cancel.set()

    @staticmethod
    def _diagnostic(reason: str, step: int, max_steps: int, tool_results) -> str:
        tools = len(tool_results) if tool_results else 0
        return (
            f"I couldn't complete the full task ({reason}). "
            f"Stopped after {step} steps and {tools} tool call(s) "
            f"(reached the {max_steps}-step safety budget). "
            "Try a more specific request or a smaller workspace scope."
        )

    def close(self) -> None:
        try:
            self._saver_conn.close()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Plan-following logic (executes plan steps through the graph)
    # ------------------------------------------------------------------
    def _follow_plan_step(self, plan, plan_index, step, max_steps,
                          messages, tool_results, writer) -> Dict[str, Any]:
        """Execute the next step from the plan through the graph.

        Tool steps → set pending_calls, let _tools_node execute via ToolOrchestrator.
        Answer steps → generate final answer and finish.
        """
        import json as _json
        item = plan[plan_index]
        step_num = item["step"]
        tool = item.get("tool")
        params = dict(item.get("parameters", {}))
        depends_on = item.get("depends_on", [])

        writer({"event": "step", "step": step_num, "max": len(plan)})
        writer({"event": "status", "text": f"> Step {step_num}/{len(plan)}: {item['description']}"})

        # Mark as running. Status goes out ONCE via the graph writer above
        # (custom event → transport → UI); calling _on_status again here
        # duplicated every "> Step n/m" line in the progress sidebar.
        item["status"] = "running"
        self._check_cancel()

        # --- Answer step (tool=null) ---
        if tool is None:
            # Collect evidence from ALL completed tool steps. The plan's
            # depends_on edges sequence tool calls; they must not decide what
            # the final synthesis may see - a plan whose answer step depends
            # only on the last (possibly empty) search would otherwise discard
            # the README a middle step already read. Evidence is bounded when
            # stored (2000 chars per step); cap the total so a long plan does
            # not blow the context. Each result is prefixed with the tool and
            # step number so the model can tell listings from file contents.
            evidence = []
            evidence_budget = 6000
            spent = 0
            for dep in sorted({p["step"] for p in plan if p.get("result")}):
                dep_item = next(p for p in plan if p["step"] == dep)
                tool_name = dep_item.get("tool") or "answer"
                chunk = dep_item["result"][:2000]
                if spent + len(chunk) > evidence_budget:
                    room = evidence_budget - spent
                    if room <= 0:
                        break
                    evidence.append(
                        f"Step {dep} ({tool_name}): {chunk[:room]}…")
                    spent += room
                    break
                evidence.append(f"Step {dep} ({tool_name}): {chunk}")
                spent += len(chunk)

            # General questions never produced tool evidence. Telling the
            # model to answer "using ONLY the evidence" while showing it
            # "(no prior results)" is a contradiction that makes it stall or
            # refuse — phrase the instruction per case instead.
            if evidence:
                evidence_block = "Evidence from previous steps:\n" + "\n".join(evidence)
                guidance = (
                    "The evidence above is real output from tools you ran on this "
                    "machine — answer from it directly; never claim you cannot see "
                    "it or lack file access. If the results show zero matches or an "
                    "error, say clearly that nothing was found — never invent file "
                    "names or paths."
                )
            else:
                evidence_block = "No tool calls were needed for this question."
                guidance = (
                    "No tool calls were needed — this is a general-knowledge "
                    "question. Answer it directly from your own knowledge."
                )

            # Ask LLM to synthesize the answer. The router system prompt is
            # prepended (without the tool catalog — this is an answer call)
            # so identity and anti-refusal rules reach the model in plan mode.
            answer_prompt = self._prefixed_prompt(
                f"User asked: {messages[-1]['content'] if messages else ''}\n\n"
                f"{evidence_block}\n\n"
                f"{guidance}\n"
                "Write a clear, natural-language answer in plain text. Do NOT call "
                "tools. Do NOT return JSON. Do NOT repeat yourself or echo the "
                "evidence verbatim — write the answer fresh and stop.\n\nAnswer:"
            )
            writer({"event": "status", "text": "[plan] Synthesizing answer..."})
            answer = self._call_llm(
                answer_prompt, writer, stream_tokens=True, purpose="answer")
            self._check_cancel()
            answer = self._clean(answer)
            # The tuned 12B sometimes still opens its prose with a tool-call
            # envelope ({"tool_calls": []}...) despite the "no JSON" rule -
            # strip any leading envelope so the bubble shows clean prose.
            answer = strip_tool_envelope(answer) or answer

            if not answer.strip():
                answer = self._diagnostic("plan answer step produced empty result", step_num, len(plan), tool_results)
            elif _looks_like_refusal(answer):
                # A refusal ("I do not have access to your file system") must
                # never be the final answer when tool evidence exists — render
                # the evidence deterministically instead.
                if evidence:
                    logger.warning(
                        "Plan answer step refused (%r); answering from evidence",
                        answer[:160])
                    answer = "Here's what I found:\n" + "\n".join(evidence)
                else:
                    answer = self._diagnostic(
                        "model refused to answer and no tool evidence was available",
                        step_num, len(plan), tool_results)

            item["status"] = "done"
            item["result"] = answer

            return {
                "pending_calls": [],
                "final_answer": answer,
                "messages": messages + [{"role": "assistant", "content": answer}],
                "step": step + 1,
                "plan_index": plan_index + 1,
            }

        # --- Tool step ---
        # Resolve STEP_N.result references in parameters
        params = self._resolve_plan_refs(params, plan)

        writer({"event": "status", "text": f"[plan] → {tool}({params})"})

        # Return as pending_calls → _tools_node will execute via ToolOrchestrator
        # (retries, approvals, stuck detection all apply)
        return {
            "pending_calls": [{"tool": tool, "parameters": params}],
            "final_answer": "",
            "step": step + 1,
            "plan_index": plan_index + 1,
            "raw_response": _json.dumps({"tool": tool, "parameters": params}),
        }

    def _resolve_plan_refs(self, params: Dict[str, Any],
                           plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve STEP_N.result references using plan step results."""
        import re as _re
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and "STEP_" in value:
                def _replace_ref(m):
                    step_num = int(m.group(1))
                    dep_item = next((p for p in plan if p["step"] == step_num), None)
                    if dep_item and dep_item.get("result"):
                        return dep_item["result"][:2000]
                    return m.group(0)
                value = _re.sub(r"STEP_(\d+)\.result", _replace_ref, value)
            resolved[key] = value
        return resolved

    def _store_plan_result(self, plan: List[Dict[str, Any]],
                           plan_index: int, tool_results: List[Dict[str, Any]]) -> None:
        """Store the latest tool result back into the plan step.

        Orchestrator results carry the payload under ``result`` (not
        ``content``), so prefer the canonical formatter first and fall
        back to a raw dump — otherwise the answer step sees empty
        evidence and the model refuses/hallucinates.
        """
        if plan_index < len(plan) and tool_results:
            last_result = tool_results[-1]
            content = last_result.get("content")
            if not content:
                content = tool_content_for_context(last_result, max_chars=2000)
            if not content:
                payload = last_result.get("result")
                if isinstance(payload, str):
                    content = payload
                elif payload is not None:
                    content = json.dumps(payload, default=str)[:2000]
                else:
                    content = last_result.get("error", "")
            plan[plan_index]["result"] = str(content)[:2000]
            plan[plan_index]["status"] = "done" if last_result.get("status") == "success" else "failed"

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------
    def _planner_node(self, state: GraphState, writer: StreamWriter) -> Dict[str, Any]:
        """First graph node: decide whether tools are needed and write the plan.

        This is the LangGraph planner node — it runs inside the graph (not as
        a standalone pre-call), so the whole turn is one StateGraph run:
        ``START → planner → (agent ⇄ tools) → END``. It asks the LLM for a
        concrete step plan (or decides the question needs no tools), stores
        the plan in graph state, and notifies the UI via ``on_plan``. The
        agent/tools nodes then execute that plan step by step.
        """
        messages = state.get("messages", [])
        user_message = messages[-1]["content"] if messages else ""
        plan = self._create_plan(user_message, self._on_status, writer=writer)
        if plan and self._on_plan:
            try:
                self._on_plan("plan", plan)
            except Exception:  # noqa: BLE001 - a UI callback must never break the graph
                logger.warning("on_plan callback failed", exc_info=True)
        return {"plan": plan, "plan_index": 0}

    def _agent_node(self, state: GraphState, writer: StreamWriter) -> Dict[str, Any]:
        """Ask the model for the next JSON action (or finish the run).

        When a plan exists, follows the plan step-by-step instead of
        asking the LLM each time. Each plan step goes through the normal
        tools node (ToolOrchestrator) for retries, approvals, etc.
        """
        self._check_cancel()
        step = state.get("step", 0)
        max_steps = state.get("max_steps", self.max_steps)
        messages = state.get("messages", [])
        tool_results = list(state.get("tool_results", []))
        plan = state.get("plan", [])
        plan_index = state.get("plan_index", 0)

        # --- Plan-following mode (strict) ---
        # The plan is the ONLY driver: the planner node already decided
        # whether tools are needed and wrote the step plan. The agent node
        # never asks the model to pick actions itself — there is no reactive
        # ReAct loop anymore. Each plan step goes through the tools node
        # (ToolOrchestrator) for retries and approvals, and the plan's
        # answer step synthesizes the final answer.
        if plan and plan_index < len(plan):
            return self._follow_plan_step(
                plan, plan_index, step, max_steps, messages, tool_results, writer
            )

        # Safety budget: a plan is capped at 6 steps, but presets may set a
        # smaller max_steps (e.g. quick_fix=4). Never exceed that budget.
        if step >= max_steps:
            answer = self._final_response(messages, tool_results, writer)
            if not answer.strip():
                answer = self._diagnostic("step budget exhausted", step, max_steps, tool_results)
            return {
                "pending_calls": [],
                "final_answer": answer,
                "messages": messages + [{"role": "assistant", "content": answer}],
                "step": step,
            }

        # No plan (planner failed): end the run deterministically. There is
        # no reactive fallback — the run stops here with an honest answer
        # instead of switching to an ad-hoc agent loop.
        writer({"event": "status", "text": "[plan] No plan available — wrapping up"})
        answer = self._final_response(messages, tool_results, writer)
        if not answer.strip():
            answer = self._diagnostic("planner produced no plan", step, max_steps, tool_results)
        return {
            "pending_calls": [],
            "final_answer": answer,
            "messages": messages + [{"role": "assistant", "content": answer}],
            "step": step,
        }

    def _router(self, state: GraphState) -> str:
        self._check_cancel()
        if state.get("final_answer"):
            return "end"
        if state.get("pending_calls"):
            return "continue"
        return "end"

    def _tools_node(self, state: GraphState, writer: StreamWriter) -> Dict[str, Any]:
        """Execute pending tool calls via ToolOrchestrator."""
        self._check_cancel()
        calls = state.get("pending_calls", [])
        tool_results = list(state.get("tool_results", []))
        executed_calls = list(state.get("executed_calls", []))

        tool_results, executed_calls = self._tool_orch.execute_batch(
            calls=calls,
            existing_results=tool_results,
            existing_executed=executed_calls,
            on_status=self._on_status,
            on_tool=self._on_tool,
            check_cancel=self._check_cancel,
            announce_plan=lambda _calls, _writer: None,
            writer=writer,
            approval_fn=self._on_approval,
            llm_call=self._call_llm_for_fix,
        )

        # Store results back into plan step if following a plan
        plan = state.get("plan", [])
        plan_index = state.get("plan_index", 0)
        if plan and plan_index > 0 and tool_results:
            self._store_plan_result(plan, plan_index - 1, tool_results)

        return {"tool_results": tool_results, "executed_calls": executed_calls, "pending_calls": []}

    def _call_llm_for_fix(self, prompt: str) -> str:
        """LLM call wrapper for ToolOrchestrator fix retries."""
        return self._call_llm(prompt, _NoopWriter(), stream_tokens=False)

    def _final_response(self, messages, tool_results, writer) -> str:
        """Synthesize a natural-language wrap-up from tool results."""
        import json as _json
        user_q = messages[-1]['content'] if messages else ''

        # Step 1: Build direct answer from tool results (no LLM)
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
                    if len(content) > 1200:
                        content = content[:1200] + "..."
                    direct_parts.append(content)
                elif tool == "search_files":
                    direct_parts.append(f"Search results:\n{content}")
                else:
                    direct_parts.append(content)

        has_readable_evidence = any(
            r.get("status") == "success" and r.get("tool_name") in ("read_file", "search_files")
            for r in tool_results
        )

        logger.info(
            "_final_response: tool_results=%d direct_parts=%d readable_evidence=%s user_q=%r",
            len(tool_results), len(direct_parts), has_readable_evidence, user_q[:120],
        )

        if not direct_parts:
            response = self._call_llm(
                f"Answer this question briefly: {user_q}\n\nAssistant:",
                writer, stream_tokens=True, purpose="answer",
            )
            logger.info(
                "_final_response (no evidence): LLM returned len=%d raw_preview=%r",
                len(response or ""), (response or "")[:300],
            )
            cleaned = strip_tool_envelope(self._clean(response))
            if cleaned.strip():
                return cleaned
            return self._diagnostic(
                "model returned empty response and no tool evidence was available",
                self.max_steps, self.max_steps, tool_results,
            )

        direct_answer = "\n\n".join(direct_parts)

        # Step 2: If the only evidence is a directory listing (no read/search hit),
        # the question may or may not be about the workspace. Give the model the
        # actual listing as evidence so file-task prompts ("what's in folder X?") get
        # answered from it, while general questions can still ignore it. Never tell
        # the model nothing was found when a listing exists — that makes it refuse.
        if not has_readable_evidence:
            response = self._call_llm(
                self._prefixed_prompt(
                    f"User asked: {user_q}\n\n"
                    f"Here is what was found in the workspace:\n{direct_answer}\n\n"
                    "If this evidence answers the user's question, answer directly from "
                    "it. Otherwise treat this as a general question and answer in plain "
                    "text. Do NOT call tools, do NOT return JSON.\n\nAssistant:"
                ),
                writer, stream_tokens=True, purpose="answer",
            )
            logger.info(
                "_final_response (list-only evidence): LLM returned len=%d raw_preview=%r",
                len(response or ""), (response or "")[:300],
            )
            cleaned = strip_tool_envelope(self._clean(response))
            if cleaned.strip() and not _looks_like_refusal(cleaned):
                return cleaned
            if cleaned.strip():
                logger.warning(
                    "_final_response (list-only): LLM refused (%r); using listing",
                    cleaned[:200])
            return direct_answer

        # Step 3: Tool evidence exists — let the LLM polish it into a real answer.
        try:
            context = self._prefixed_prompt(
                self._prompt_builder.final_response_context(user_q, direct_answer))
            response = self._call_llm(
                context, writer, stream_tokens=True, purpose="answer")
        except Exception as e:  # noqa: BLE001 - polish is best-effort
            logger.warning("Final-response polish failed: %s", e)
            response = ""

        logger.info(
            "_final_response (with evidence): polish len=%d raw_preview=%r",
            len(response or ""), (response or "")[:300],
        )

        if response.strip():
            try:
                parsed = _json.loads(response.strip())
                if isinstance(parsed, dict) and (parsed.get("tool_calls") or parsed.get("answer") is None):
                    logger.warning(
                        "_final_response polish returned JSON with tool_calls; "
                        "falling back to direct answer. raw=%r",
                        response[:300],
                    )
                    pass  # LLM returned tool calls -- use direct answer
                elif isinstance(parsed, dict) and parsed.get("answer"):
                    direct_answer = parsed["answer"]
                else:
                    direct_answer = response.strip()
            except (ValueError, TypeError):
                direct_answer = response.strip()

        # Step 4: Clean — and never ship an access-refusal when real evidence
        # exists; render the evidence deterministically instead.
        direct_answer = strip_tool_envelope(self._clean(direct_answer))

        if not direct_answer.strip() or _looks_like_refusal(direct_answer):
            logger.warning(
                "_final_response: unusable LLM answer (%r); falling back to direct_parts",
                direct_answer[:200])
            direct_answer = "\n\n".join(direct_parts)

        return direct_answer

    def _call_llm(
        self, prompt: str, writer: StreamWriter,
        stream_tokens: bool = False, purpose: str = "action",
    ) -> str:
        """Call the LLM; streams token events when the callable yields chunks.

        ``purpose`` picks the temperature AND the token budget: ``action``
        (tool/plan JSON, near-greedy, capped so a degenerate JSON loop
        burns at most MAX_TOKENS_AGENT_ACTION) vs ``answer`` (final prose,
        mildly creative, capped at MAX_TOKENS_AGENT_ANSWER). The router
        role config (top_k/top_p/repeat) lives in the callable built by
        llm_factory.
        """
        from ggufloader.core.defaults import (
            MAX_TOKENS_AGENT_ACTION,
            MAX_TOKENS_AGENT_ANSWER,
            TEMP_ACTION,
            TEMP_ANSWER,
        )
        temperature = TEMP_ANSWER if purpose == "answer" else TEMP_ACTION
        # Q4_K_M anti-degeneration: never let a single call run past its
        # purpose budget even if the family profile allows a huge max_tokens.
        purpose_cap = MAX_TOKENS_AGENT_ANSWER if purpose == "answer" else MAX_TOKENS_AGENT_ACTION
        max_tokens = min(self.max_tokens, purpose_cap)
        self._check_cancel()

        # Prose-answer calls stream: the llm callable (build_llm) pushes each
        # generated delta through on_chunk so the UI shows text flowing during
        # synthesis instead of freezing on "Synthesizing answer..." until the
        # whole reply is done.
        # Deltas from prose-answer calls go to the chat bubble; deltas from
        # the planner call (purpose="plan") go to the sidebar reasoning
        # stream — the plan is JSON protocol text, never the user's answer.
        is_plan_call = purpose == "plan"
        call_kwargs: Dict[str, Any] = {}
        if stream_tokens:
            call_kwargs["on_chunk"] = self._on_plan_stream if is_plan_call else self._on_token
        try:
            result = self.llm(
                prompt, max_tokens=max_tokens, temperature=temperature,
                **call_kwargs)
        except AgentCancelled:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("LLM call failed: %s", e)
            return ""

        if not result or (isinstance(result, dict) and not result.get("choices", [{}])[0].get("text")):
            logger.warning("LLM returned empty response (prompt length: %d chars)", len(prompt))

        def _token_event(chunk: str) -> None:
            writer({"event": "plan_token" if is_plan_call else "token", "chunk": chunk})

        if isinstance(result, str):
            self._check_cancel()
            return result

        if isinstance(result, dict):
            text = result.get("choices", [{}])[0].get("text", "")
            self._check_cancel()
            if stream_tokens and text:
                _token_event(text)
            return text

        # Streaming
        chunks: List[str] = []
        for chunk in result:
            self._check_cancel()
            if isinstance(chunk, dict):
                text = chunk.get("choices", [{}])[0].get("text", "")
                if text:
                    chunks.append(text)
                    if stream_tokens:
                        _token_event(text)
            elif chunk:
                chunks.append(str(chunk))
                if stream_tokens:
                    _token_event(str(chunk))
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
        elif event == "plan_token":
            self._on_plan_stream(payload.get("chunk", ""))
        elif event == "status":
            self._on_status(payload.get("text", ""))
        elif event == "tool":
            result = payload.get("result")
            if isinstance(result, dict):
                self._on_tool(result)
        elif event == "step":
            step = payload.get("step", 0)
            maximum = payload.get("max")
            if maximum is not None:
                self._on_status(f"Step {step}/{maximum}")
            else:
                self._on_status(f"Step {step}")

    def _load_thread_messages(self) -> List[Dict[str, str]]:
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
    # Loop helpers
    # ------------------------------------------------------------------
