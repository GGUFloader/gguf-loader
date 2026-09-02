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

from .agent_engine import extract_json, stale_repeat_signatures, summarize_directive
from .context_budget import ContextBudget, estimate_tokens
from .prompt_builder import PromptBuilder
from .token_cleaner import TokenCleaner, get_cleaner
from .tool_orchestrator import ToolOrchestrator
from .tool_registry import ToolRegistry, tool_content_for_context, validate_tool_call
from .workspace_context import WorkspaceContext, PromptPrefixCache, WorkingMemory

logger = logging.getLogger(__name__)


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
    directive: str                       # transient read-coverage directive
    directive_rounds: int                # directives issued this run (capped)
    step: int                            # steps used so far
    max_steps: int                       # step budget for the run
    pending_calls: List[Dict[str, Any]]  # tool calls waiting to execute
    final_answer: str                    # set when the run is done
    raw_response: str                    # last raw LLM output (fallback answer)
    plan: List[Dict[str, Any]]           # step plan from _create_plan


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
        max_directive_rounds: int = 3,
        system_prompt: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None,
        blocked_tools: Optional[List[str]] = None,
        plan: bool = True,
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
        self.max_directive_rounds = max_directive_rounds
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

        # --- Extracted modules (delegated responsibilities) ---
        self._prompt_builder = PromptBuilder(
            self.workspace,
            self.tools,
            system_prompt_override=system_prompt,
        )
        self._cleaner: TokenCleaner = cleaner or get_cleaner()
        self._tool_orch: Optional[ToolOrchestrator] = None  # created per turn

        # --- Lightweight core (always loaded) ---
        self._workspace_ctx = WorkspaceContext(self.workspace)
        self._prefix_cache = PromptPrefixCache()
        self._context_budget = ContextBudget(total_budget=n_ctx or max_tokens)
        self._plan_enabled = plan

        # --- Lazy subsystems (only loaded when needed) ---
        self._lazy: Dict[str, Any] = {}

        self._saver_conn, self._saver = self._open_checkpointer()
        self._app = self._build_graph()

    def _clean(self, text: str) -> str:
        """Delegate to the model-specific token cleaner."""
        return self._cleaner.clean(text)

    def _system_prompt(self) -> str:
        """Build system prompt (delegated to PromptBuilder)."""
        return self._prompt_builder.system_prompt()

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
        graph.add_node("agent", self._agent_node)
        graph.add_node("tools", self._tools_node)
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", self._router, {"continue": "tools", "end": END})
        graph.add_edge("tools", "agent")
        return graph.compile(checkpointer=self._saver)

    # ------------------------------------------------------------------
    # Planning phase
    # ------------------------------------------------------------------
    # StreamWriter can't be instantiated outside the graph runtime,
    # so we use a no-op writer for calls outside the graph.
    def _create_plan(self, user_message: str, on_status: StatusCallback) -> List[Dict[str, Any]]:
        """Ask the LLM to create a concrete, tool-call plan with dependencies.

        The plan is a list of steps, each with:
          - step: int (1-based)
          - description: what this step does
          - tool: tool name (null for answer-only steps)
          - parameters: dict of tool parameters (may reference STEP_N.result)
          - depends_on: list of step numbers whose results this step needs
          - status: pending/running/done/failed
          - result: filled after execution

        Skipped when plan=False (e.g. in tests).
        """
        if not self._plan_enabled:
            return []

        tools_list = self.tools.describe()
        prompt = (
            f"User request: {user_message}\n\n"
            f"Available tools:\n{tools_list}\n\n"
            "Create a concrete execution plan. Reply with ONLY a JSON object:\n"
            '{\n'
            '  "goal": "one-sentence goal",\n'
            '  "steps": [\n'
            '    {\n'
            '      "step": 1,\n'
            '      "description": "what this step does",\n'
            '      "tool": "tool_name or null if just answering",\n'
            '      "parameters": {"param": "value"},\n'
            '      "depends_on": []\n'
            '    }\n'
            '  ]\n'
            '}\n\n'
            "Rules:\n"
            "- Simple questions (general knowledge): 1 step with tool=null (answer directly)\n"
            "- File/workspace tasks: 2-5 steps, each with a specific tool call\n"
            "- Use depends_on to link steps that need results from earlier steps\n"
            "- Parameters can reference previous results: use \"STEP_N.result\" as a value\n"
            "- In the description, ALWAYS mention which step results you need. Examples:\n"
            "  - Step 2 description: 'Read the file found in step 1 (STEP_1.result)'\n"
            "  - Step 3 description: 'Search for text from step 2 result (STEP_2.result)'\n"
            "  - Step 4 description: 'Summarize findings from steps 1, 2, and 3'\n"
            "- The last step should always be the answer (tool=null)\n"
            "- Be specific: use exact file paths and search terms\n\n"
            "Plan:"
        )

        _status = on_status or (lambda _msg: None)
        _status("Planning...")
        try:
            raw = self._call_llm(prompt, _NoopWriter())
        except Exception as e:  # noqa: BLE001
            logger.debug("Plan creation failed: %s", e)
            return []

        # Parse the plan from JSON
        import json as _json
        plan = []
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed = _json.loads(text)
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
        except (ValueError, TypeError):
            pass

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

    def _execute_plan(self, plan: List[Dict[str, Any]], user_message: str,
                      on_status: StatusCallback, on_tool: ToolCallback,
                      on_plan: Optional[Callable]) -> List[Dict[str, Any]]:
        """Execute a plan step-by-step, passing results between steps.

        Each step either:
          1. Runs a tool call (tool != null) and stores the result
          2. Answers directly (tool == null) — this is the final step

        Results from earlier steps are available to later steps via
        the step_results dict. Parameters containing "STEP_N.result"
        are resolved by substituting the actual result.
        """
        import json as _json
        _status = on_status or (lambda _msg: None)
        step_results: Dict[int, Any] = {}  # step_num -> result dict
        all_tool_results: List[Dict[str, Any]] = []

        for item in plan:
            step_num = item["step"]
            tool = item.get("tool")
            params = dict(item.get("parameters", {}))
            depends_on = item.get("depends_on", [])

            # Check if dependencies are met
            for dep in depends_on:
                if dep not in step_results:
                    _status(f"  Step {step_num}: waiting for step {dep}...")
                elif step_results[dep] is None:
                    _status(f"  Step {step_num}: dependency {dep} had no result, skipping")
                    item["status"] = "skipped"
                    continue

            # Resolve STEP_N.result references in parameters
            params = self._resolve_step_refs(params, step_results)

            # Update status
            item["status"] = "running"
            if on_plan:
                on_plan("execute", plan)

            if tool is None:
                # Answer step — generate final answer
                _status(f"  Step {step_num}/{len(plan)}: {item['description']}")
                evidence = []
                for dep in depends_on:
                    if dep in step_results and step_results[dep]:
                        r = step_results[dep]
                        content = r.get("content", r.get("error", ""))[:500] if isinstance(r, dict) else str(r)[:500]
                        evidence.append(f"Step {dep}: {content}")
                evidence_str = "\n".join(evidence) if evidence else "(no prior results)"
                answer = self._reask_for_answer(
                    [{"role": "user", "content": user_message}],
                    [{"tool_name": "plan_evidence", "status": "success", "content": evidence_str}],
                    _NoopWriter(),
                )
                item["status"] = "done"
                item["result"] = answer
                step_results[step_num] = {"content": answer}
                if on_plan:
                    on_plan("execute", plan)
                continue

            # Tool step — execute the tool
            _status(f"  Step {step_num}/{len(plan)}: {item['description']} [{tool}]")
            try:
                result = self.tools.execute(tool, params)
                all_tool_results.append(result)
                step_results[step_num] = result
                item["status"] = "done" if result.get("status") == "success" else "failed"
                item["result"] = result.get("content", result.get("error", ""))[:200]
                if on_tool:
                    on_tool(result)
                if result.get("status") == "success":
                    _status(f"    OK: {result.get('content', '')[:100]}")
                else:
                    _status(f"    Failed: {result.get('error', 'Unknown error')}")
            except Exception as e:  # noqa: BLE001
                item["status"] = "failed"
                item["result"] = str(e)[:200]
                step_results[step_num] = {"error": str(e)}
                _status(f"    Error: {e}")

            if on_plan:
                on_plan("execute", plan)

        return all_tool_results

    def _resolve_step_refs(self, params: Dict[str, Any],
                           step_results: Dict[int, Any]) -> Dict[str, Any]:
        """Resolve STEP_N.result references in parameter values."""
        import re as _re
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and "STEP_" in value:
                # Replace STEP_N.result with actual result content
                def _replace_ref(m):
                    step_num = int(m.group(1))
                    if step_num in step_results:
                        r = step_results[step_num]
                        if isinstance(r, dict):
                            return r.get("content", r.get("error", ""))[:2000]
                        return str(r)[:2000]
                    return m.group(0)  # keep original if step not found
                value = _re.sub(r"STEP_(\d+)\.result", _replace_ref, value)
            resolved[key] = value
        return resolved

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

        # Create tool orchestrator for this turn
        self._tool_orch = ToolOrchestrator(
            self.tools, str(self.workspace), self._failed_signatures
        )

        base_messages = self._load_thread_messages() or list(self.messages)

        if base_messages:
            strategy = self._context_budget.check_budget(base_messages)
            if strategy != "ok":
                on_status(f"[compact] Compacting context ({strategy})...")
                base_messages = self._context_budget.compact(base_messages)        # --- Planning phase ---
        plan = self._create_plan(user_message, on_status)
        if plan and on_plan:
            on_plan("plan", plan)

        # --- Plan-based execution ---
        # If a plan was created, execute it step-by-step with result flow.
        if plan:
            tool_results = self._execute_plan(plan, user_message, on_status, on_tool, on_plan)

            # Find the final answer from the plan (last step with tool=null)
            final_answer = ""
            for item in reversed(plan):
                if item.get("tool") is None and item.get("result"):
                    final_answer = self._clean(item["result"])
                    break

            if not final_answer:
                # Plan didn't produce an answer — synthesize from tool results
                final_answer = self._final_response(
                    [{"role": "user", "content": user_message}], tool_results, _NoopWriter()
                )

            if final_answer and on_plan:
                on_plan("finish", plan)

            self.messages = base_messages + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": final_answer},
            ]

            return {
                "response": final_answer or self._diagnostic(
                    "plan execution completed", len(plan), len(plan), tool_results
                ),
                "tool_results": tool_results,
                "plan": plan,
            }

        # --- Fallback: no plan — use graph loop (for tests or plan failures) ---
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
        except Exception as e:  # noqa: BLE001
            logger.error("Agent graph error: %s", e)
            return {"response": f"Error: {e}", "tool_results": tool_results}

        self.messages = self._load_thread_messages() or inputs["messages"]

        if self.messages:
            self._context_budget.check_budget(self.messages)

        return {
            "response": final_answer or self._diagnostic(
                "loop ended with no answer", self.max_steps, self.max_steps, tool_results
            ),
            "tool_results": tool_results,
        }

    def cancel(self) -> None:
        self._cancel.set()

    @staticmethod
    def _diagnostic(reason: str, step: int, max_steps: int, tool_results) -> str:
        tools = len(tool_results) if tool_results else 0
        return (
            f"I couldn't complete the full task ({reason}). "
            f"Reached step {step}/{max_steps} after {tools} tool call(s). "
            "Try a more specific request or a smaller workspace scope."
        )

    def close(self) -> None:
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

        # Budget exhausted
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

        writer({"event": "step", "step": step + 1, "max": max_steps})

        action, raw = self._request_action(
            messages, tool_results, writer, directive=state.get("directive", "")
        )
        if action is None:
            logger.warning(
                "Agent step %d: LLM failed to produce valid JSON after %d retries. "
                "Raw response (first 500 chars): %r",
                step + 1, self.json_retries, (raw or "")[:500],
            )
            answer = self._clean(raw or "I couldn't produce a valid response.")
            return {
                "pending_calls": [],
                "final_answer": answer,
                "messages": messages + [{"role": "assistant", "content": answer}],
                "raw_response": raw,
                "step": step + 1,
            }

        # Log the parsed action structure so we can diagnose missing-answer bugs.
        logger.info(
            "Agent step %d action: reasoning=%r tool_calls=%d answer=%r estimated_steps=%r",
            step + 1,
            (action.get("reasoning") or "")[:200],
            len(action.get("tool_calls") or []),
            (action.get("answer") or "")[:200],
            action.get("estimated_steps"),
        )
        if not action.get("answer") and not action.get("tool_calls"):
            logger.warning(
                "Agent step %d: model produced NO answer and NO tool_calls. "
                "This usually means the LLM returned only reasoning and stopped. "
                "reasoning=%r",
                step + 1, (action.get("reasoning") or "")[:300],
            )

        reasoning = self._clean((action.get("reasoning") or "").strip())
        if reasoning:
            writer({"event": "status", "text": f"... {reasoning}"})

        # Dynamic step estimate — only expand the budget, never shrink it.
        # Add a generous +2 buffer because small models routinely under-estimate
        # how many steps a multi-tool task really takes.
        est = action.get("estimated_steps")
        if isinstance(est, (int, float)) and est > 0:
            est = min(int(est) + 2, 20)
            if est > max_steps:
                max_steps = est

        calls = [
            c for c in (action.get("tool_calls") or [])
            if isinstance(c, dict) and c.get("tool")
        ]

        # --- Stuck-in-search detection ---
        # If the agent has done 2+ steps of only search/list with no useful
        # results and no state-changing tool ran, force it to answer from
        # knowledge.  A write/edit between searches makes re-reading legitimate
        # so we only trigger when the searches are truly futile.
        if step >= 2 and calls:
            search_only = all(
                c.get("tool") in ("search_files", "list_directory", "glob")
                for c in calls
            )
            has_read_result = any(
                r.get("tool_name") == "read_file" and r.get("status") == "success"
                for r in tool_results
            )
            state_changing = any(
                e.get("tool") in ("write_file", "edit_file", "run_command", "git")
                for e in state.get("executed_calls", [])
            )
            if search_only and not has_read_result and not state_changing:
                logger.info(
                    "Agent step %d: stuck in search loop (no useful results after %d steps). "
                    "Forcing answer from knowledge.",
                    step + 1, step,
                )
                writer({"event": "status", "text": "[short-circuit] No relevant files found — answering from knowledge"})
                answer = self._reask_for_answer(messages, tool_results, writer)
                if not answer:
                    answer = self._clean(raw or "I couldn't find relevant files. Let me answer from my knowledge.")
                return self._finish_or_direct(state, messages, answer, raw, step, writer, max_steps=max_steps)

        if not calls:
            answer = self._clean((action.get("answer") or "").strip())
            # No answer key AND no tool calls AND we have evidence: the model
            # rambled in reasoning instead of using the answer field. Ask it
            # once to produce a clean natural-language answer based on the
            # evidence (or its own knowledge when no relevant file exists).
            reasked = False
            if not answer and tool_results and not self._answer_field_present(action):
                answer = self._reask_for_answer(messages, tool_results, writer)
                reasked = True
            # Last-resort fallback: if the reask also returned nothing useful,
            # surface the model's own reasoning as the answer so the user sees
            # something instead of a silent "Done." or empty bubble.
            if not answer and reasoning:
                answer = reasoning
                logger.info(
                    "Agent step %d: using reasoning as answer (no answer key, reask empty)",
                    step + 1,
                )
            logger.info(
                "Agent step %d: model proposed 0 tool calls; answer_len=%d tool_results=%d reasked=%s",
                step + 1, len(answer), len(tool_results), reasked,
            )
            if not answer and tool_results:
                answer = self._final_response(messages, tool_results, writer)
            if not answer:
                answer = self._clean(raw or "No further action needed.")
            if not answer.strip():
                answer = self._diagnostic("model returned no answer", step + 1, max_steps, tool_results)
            return self._finish_or_direct(state, messages, answer, raw, step, writer, max_steps=max_steps)

        # Drop stale repeats
        stale = stale_repeat_signatures(calls, state.get("executed_calls", []))
        new_calls = [c for c in calls if self._signature(c) not in stale]
        if not new_calls:
            logger.info(
                "Agent step %d: all %d proposed tool calls were stale repeats",
                step + 1, len(calls),
            )
            answer = self._clean((action.get("answer") or "").strip())
            if not answer:
                answer = self._final_response(messages, tool_results, writer)
            if not answer:
                answer = self._clean(raw or "No further action needed.")
            return self._finish_or_direct(state, messages, answer, raw, step, writer, max_steps=max_steps)

        return {"pending_calls": new_calls, "final_answer": "", "raw_response": raw, "step": step + 1, "max_steps": max_steps}

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
            announce_plan=self._announce_plan,
            writer=writer,
            approval_fn=self._on_approval,
            llm_call=self._call_llm_for_fix,
        )

        return {"tool_results": tool_results, "executed_calls": executed_calls, "pending_calls": []}

    def _router(self, state: GraphState) -> str:
        self._check_cancel()
        if state.get("final_answer"):
            return "end"
        if state.get("pending_calls"):
            return "continue"
        if state.get("directive"):
            return "continue"
        return "end"

    # ------------------------------------------------------------------
    # Prompt construction (delegated to PromptBuilder)
    # ------------------------------------------------------------------
    def _request_action(self, messages, tool_results, writer, repair: str = "", directive: str = "") -> Tuple[Optional[Dict[str, Any]], str]:
        prompt = self._prompt_builder.action_prompt(messages, tool_results, repair, directive)
        raw = self._call_llm(prompt, writer)
        data = extract_json(raw)
        if data is not None:
            return data, raw
        for _attempt in range(self.json_retries):
            prompt = self._prompt_builder.action_prompt(messages, tool_results, repair=raw, directive=directive)
            raw = self._call_llm(prompt, writer)
            data = extract_json(raw)
            if data is not None:
                return data, raw
        logger.warning(
            "extract_json failed after %d retries. Raw (first 800 chars): %r",
            self.json_retries, (raw or "")[:800],
        )
        return None, raw

    def _call_llm_for_fix(self, prompt: str) -> str:
        """LLM call wrapper for ToolOrchestrator fix retries."""
        return self._call_llm(prompt, _NoopWriter(), stream_tokens=False)

    def _answer_field_present(self, action: Dict[str, Any]) -> bool:
        """True when the action JSON contains a non-empty 'answer' key."""
        return isinstance(action, dict) and bool((action.get("answer") or "").strip())

    def _reask_for_answer(self, messages, tool_results, writer) -> str:
        """Re-prompt the LLM to produce a clean natural-language answer.

        Used when the action step returned only reasoning without an
        ``answer`` field. Asks the model to reply either from file
        evidence (when relevant) or from its own internal knowledge.
        """
        import json as _json
        user_q = messages[-1]['content'] if messages else ''
        evidence_lines = []
        for r in tool_results:
            if r.get("status") != "success":
                continue
            content = tool_content_for_context(r, max_chars=600)
            if content:
                evidence_lines.append(f"- {r.get('tool_name')}: {content}")
        evidence = "\n".join(evidence_lines) if evidence_lines else "(no usable file content)"

        prompt = (
            f"User asked: {user_q}\n\n"
            f"Workspace evidence so far:\n{evidence}\n\n"
            "Respond to the user in plain natural language. If relevant files were found, "
            "use them. Otherwise answer from your own knowledge. "
            "Do NOT call any tools. Do NOT return JSON. Just write the answer text.\n\n"
            "Answer:"
        )
        writer({"event": "status", "text": "[reask] Asking model for a plain-text answer..."})
        try:
            response = self._call_llm(prompt, writer, stream_tokens=True)
        except Exception as e:  # noqa: BLE001 - best-effort re-ask
            logger.warning("_reask_for_answer LLM call failed: %s", e)
            return ""

        cleaned = self._clean(response or "")

        # The reask sometimes returns more JSON-thinking instead of plain text.
        # Detect that (with or without markdown fences) and strip out reasoning/
        # tool_calls artifacts so the user sees the actual prose.
        import re as _re
        fence_stripped = _re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned.strip(), flags=_re.IGNORECASE).strip()
        if fence_stripped.startswith("{") and '"answer"' in fence_stripped:
            try:
                parsed = _json.loads(fence_stripped)
                if isinstance(parsed, dict):
                    inner = (parsed.get("answer") or "").strip()
                    if inner:
                        cleaned = inner
                    else:
                        cleaned = (parsed.get("reasoning") or "").strip()
            except (ValueError, TypeError):
                pass

        logger.info(
            "_reask_for_answer: LLM returned len=%d cleaned_len=%d raw_preview=%r",
            len(response or ""), len(cleaned), (response or "")[:300],
        )
        return cleaned

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
                writer, stream_tokens=True,
            )
            logger.info(
                "_final_response (no evidence): LLM returned len=%d raw_preview=%r",
                len(response or ""), (response or "")[:300],
            )
            cleaned = self._clean(response)
            if cleaned.strip():
                return cleaned
            return self._diagnostic(
                "model returned empty response and no tool evidence was available",
                self.max_steps, self.max_steps, tool_results,
            )

        direct_answer = "\n\n".join(direct_parts)

        # Step 2: If the only evidence is a directory listing (no read/search hit),
        # the user probably asked a general question — answer it directly without
        # trying to force a polish that reuses the file list as context.
        if not has_readable_evidence:
            response = self._call_llm(
                f"User asked: {user_q}\n\n"
                "Note: no relevant files were found in the workspace, so this is a "
                "general question. Answer it in plain text, do NOT call tools, do "
                "NOT return JSON.\n\nAssistant:",
                writer, stream_tokens=True,
            )
            logger.info(
                "_final_response (list-only evidence): LLM returned len=%d raw_preview=%r",
                len(response or ""), (response or "")[:300],
            )
            cleaned = self._clean(response)
            if cleaned.strip():
                return cleaned
            return (
                f"I couldn't find files in the workspace relevant to your question "
                f"({user_q}). Here's what I saw:\n\n{direct_answer}"
            )

        # Step 3: Tool evidence exists — let the LLM polish it into a real answer.
        try:
            context = self._prompt_builder.final_response_context(user_q, direct_answer)
            response = self._call_llm(context, writer, stream_tokens=True)
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

        # Step 4: Clean
        direct_answer = self._clean(direct_answer)

        if not direct_answer.strip():
            logger.warning(
                "_final_response: cleaned answer is empty; falling back to direct_parts"
            )
            direct_answer = "\n\n".join(direct_parts)

        return direct_answer

    def _call_llm(self, prompt: str, writer: StreamWriter, stream_tokens: bool = False) -> str:
        """Call the LLM; streams token events when the callable yields chunks."""
        self._check_cancel()

        try:
            result = self.llm(prompt, max_tokens=self.max_tokens, temperature=0.1)
        except AgentCancelled:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("LLM call failed: %s", e)
            return ""

        if not result or (isinstance(result, dict) and not result.get("choices", [{}])[0].get("text")):
            logger.warning("LLM returned empty response (prompt length: %d chars)", len(prompt))

        if isinstance(result, str):
            self._check_cancel()
            return result

        if isinstance(result, dict):
            text = result.get("choices", [{}])[0].get("text", "")
            self._check_cancel()
            if stream_tokens and text:
                writer({"event": "token", "chunk": text})
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
    def _announce_plan(self, calls, writer) -> None:
        if not calls:
            return
        if len(calls) == 1:
            writer({"event": "status", "text": f"-> {self._tool_orch._describe(calls[0])}"})
        else:
            writer({"event": "status", "text": f"-> {len(calls)} tasks to complete:"})
            for index, call in enumerate(calls, 1):
                writer({"event": "status", "text": f"  {index}. {self._tool_orch._describe(call)}"})
        writer({"event": "status", "text": ""})

    def _finish_or_direct(self, state, messages, answer, raw, step, writer, max_steps=None) -> Dict[str, Any]:
        tool_results = state.get("tool_results", [])
        has_evidence = any(r.get("status") == "success" for r in tool_results)
        accept_short_with_evidence = has_evidence and len(answer) >= 10
        if answer and (len(answer) >= 200 or accept_short_with_evidence):
            answer = self._clean(answer)
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
        except Exception:  # noqa: BLE001
            params = str(call.get("parameters"))
        return f"{call.get('tool', '')}:{params}"

    def _is_complex(self, message: str) -> bool:
        keywords = ["complex", "multiple", "several", "build", "create system"]
        return len(message.split()) > 20 or any(w in message.lower() for w in keywords)
