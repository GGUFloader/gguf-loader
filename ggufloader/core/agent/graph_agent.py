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
from .prompt_builder import PromptBuilder
from .token_cleaner import TokenCleaner, get_cleaner
from .tool_orchestrator import ToolOrchestrator
from .tool_registry import ToolRegistry, tool_content_for_context, validate_tool_call
from .workspace_context import WorkspaceContext, PromptPrefixCache, WorkingMemory

logger = logging.getLogger(__name__)

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
    ) -> None:
        self.llm = llm
        self.workspace = Path(workspace)
        READONLY_TOOLS = ["list_directory", "read_file", "search_files", "glob"]
        self.tools = tools or ToolRegistry(self.workspace, only=READONLY_TOOLS)
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
        self._prompt_builder = PromptBuilder(self.workspace, self.tools)
        self._cleaner: TokenCleaner = cleaner or get_cleaner()
        self._tool_orch: Optional[ToolOrchestrator] = None  # created per turn

        # --- Lightweight core (always loaded) ---
        self._workspace_ctx = WorkspaceContext(self.workspace)
        self._prefix_cache = PromptPrefixCache()
        self._context_budget = ContextBudget(total_budget=n_ctx or max_tokens)

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
            answer = self._clean(raw or "I couldn't produce a valid response.")
            return {
                "pending_calls": [],
                "final_answer": answer,
                "messages": messages + [{"role": "assistant", "content": answer}],
                "raw_response": raw,
                "step": step + 1,
            }

        reasoning = self._clean((action.get("reasoning") or "").strip())
        if reasoning:
            writer({"event": "status", "text": f"... {reasoning}"})

        # Dynamic step estimate
        est = action.get("estimated_steps")
        if isinstance(est, (int, float)) and est > 0:
            est = min(int(est) + 1, 20)
            if step == 0 or est > max_steps:
                max_steps = est

        calls = [
            c for c in (action.get("tool_calls") or [])
            if isinstance(c, dict) and c.get("tool")
        ]
        if not calls:
            answer = self._clean((action.get("answer") or "").strip())
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
        return None, raw

    def _call_llm_for_fix(self, prompt: str) -> str:
        """LLM call wrapper for ToolOrchestrator fix retries."""
        # StreamWriter can't be instantiated outside the graph runtime,
        # so we pass a no-op writer that discards events.
        class _NoopWriter:
            def __call__(self, data):
                pass
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

        if not direct_parts:
            response = self._call_llm(
                f"Answer this question briefly: {user_q}\n\nAssistant:",
                writer, stream_tokens=True,
            )
            cleaned = self._clean(response)
            if cleaned.strip():
                return cleaned
            return f"I was unable to find information about: {user_q}"

        direct_answer = "\n\n".join(direct_parts)

        # Step 2: Try LLM polish (stream tokens so user sees answer in real time)
        context = self._prompt_builder.final_response_context(user_q, direct_answer)
        response = self._call_llm(context, writer, stream_tokens=True)

        if response.strip():
            try:
                parsed = _json.loads(response.strip())
                if isinstance(parsed, dict) and (parsed.get("tool_calls") or parsed.get("answer") is None):
                    pass  # LLM returned tool calls -- use direct answer
                elif isinstance(parsed, dict) and parsed.get("answer"):
                    direct_answer = parsed["answer"]
                else:
                    direct_answer = response.strip()
            except (ValueError, TypeError):
                direct_answer = response.strip()

        # Step 3: Clean
        direct_answer = self._clean(direct_answer)

        if not direct_answer.strip():
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
