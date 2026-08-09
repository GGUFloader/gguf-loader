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

from .agent_engine import _SYSTEM_PROMPT, extract_json
from .tool_registry import ToolRegistry, tool_content_for_context

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
        max_tokens: int = 2048,
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
        inputs: GraphState = {
            "messages": base_messages + [{"role": "user", "content": user_message}],
            "tool_results": [],
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
        return {"response": final_answer or "Done.", "tool_results": tool_results}

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

        action, raw = self._request_action(messages, tool_results, writer)
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
            return {
                "pending_calls": [],
                "final_answer": answer,
                "messages": messages + [{"role": "assistant", "content": answer}],
                "raw_response": raw,
                "step": step + 1,
            }

        return {"pending_calls": calls, "final_answer": "", "raw_response": raw, "step": step + 1}

    def _tools_node(self, state: GraphState, writer: StreamWriter) -> Dict[str, Any]:
        """Execute pending tool calls, with one corrective retry per failure.

        Sensitive calls (shell commands, git writes) are approved up front
        via LangGraph interrupts before anything executes, so a suspension
        never loses results from calls that already ran.
        """
        self._check_cancel()
        calls = state.get("pending_calls", [])
        tool_results = list(state.get("tool_results", []))
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
            if index - 1 in approvals and not approvals[index - 1]:
                result = {"status": "error", "error": "Approval denied by the user",
                          "tool_name": call.get("tool", "")}
            else:
                result = self.tools.execute(call.get("tool", ""), call.get("parameters", {}))
            tool_results.append(result)
            writer({"event": "tool", "result": result})
            if result.get("status") == "success":
                writer({"event": "status", "text": f"  ✓ {self._summarize_result(result)}"})
            else:
                writer({"event": "status", "text": f"  ✗ {result.get('error', 'Unknown error')}"})
                self._failed_signatures[signature] = self._failed_signatures.get(signature, 0) + 1
                failures.append((call, result))

        for failed_call, failed_result in failures:
            self._check_cancel()
            fixed = self._request_fix(failed_call, failed_result, writer)
            if fixed is None:
                continue
            tool_results.append(fixed)
            writer({"event": "tool", "result": fixed})
            if fixed.get("status") == "success":
                writer({"event": "status", "text": f"  ✓ retry succeeded: {self._summarize_result(fixed)}"})
            else:
                writer({"event": "status", "text": f"  ✗ retry failed: {fixed.get('error', 'Unknown error')}"})

        return {"tool_results": tool_results, "pending_calls": []}

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
        return "end"

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------
    def _system_prompt(self) -> str:
        return (
            _SYSTEM_PROMPT
            .replace("__WORKSPACE__", str(self.workspace))
            .replace("__TOOLS__", self.tools.describe())
        )

    def _build_action_prompt(self, messages, tool_results, repair: str = "") -> str:
        parts = [self._system_prompt(), ""]
        for msg in messages[-4:]:
            parts.append(f"{msg['role'].capitalize()}: {msg['content']}")
            parts.append("")
        if tool_results:
            parts.append("Recent tool activity:")
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
        parts.append("Assistant:")
        return "\n".join(parts)

    def _format_tool_results(self, tool_results) -> List[str]:
        lines = []
        for result in tool_results[-12:]:
            tool = result.get("tool_name", "unknown")
            outcome = "success" if result.get("status") == "success" else "error"
            content = tool_content_for_context(result)
            if content is not None:
                lines.append(f"{tool}: {outcome} - {content}")
            else:
                lines.append(f"{tool}: {outcome} - {self._summarize_result(result)}")
        return lines

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------
    def _request_action(self, messages, tool_results, writer, repair: str = "") -> Tuple[Optional[Dict[str, Any]], str]:
        """Ask for the next action, repairing malformed JSON up to json_retries times."""
        prompt = self._build_action_prompt(messages, tool_results, repair)
        raw = self._call_llm(prompt, writer)
        data = extract_json(raw)
        if data is not None:
            return data, raw
        for _attempt in range(self.json_retries):
            prompt = self._build_action_prompt(messages, tool_results, repair=raw)
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

        The final-answer synthesis streams plain text to the UI. The JSON
        protocol calls do not (dumping raw JSON into the chat is noise).
        """
        self._check_cancel()
        try:
            result = self.llm(prompt, max_tokens=self.max_tokens, temperature=0.1)
        except AgentCancelled:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("LLM call failed: %s", e)
            return ""
        if isinstance(result, str):
            self._check_cancel()
            return result
        chunks: List[str] = []
        for chunk in result:
            self._check_cancel()
            if chunk:
                chunks.append(chunk)
                if stream_tokens:
                    writer({"event": "token", "chunk": chunk})
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
        if len(calls) == 1:
            writer({"event": "status", "text": f"→ {self._describe(calls[0])}"})
        else:
            writer({"event": "status", "text": f"→ {len(calls)} tasks to complete:"})
            for index, call in enumerate(calls, 1):
                writer({"event": "status", "text": f"  {index}. {self._describe(call)}"})
        writer({"event": "status", "text": ""})

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
            return f"Read {result.get('lines', 0)} lines"
        if tool == "list_directory":
            return f"Found {len(result.get('result', []))} items"
        if tool == "search_files":
            return f"Found {result.get('total_matches', 0)} matches" if result.get("total_matches") else "No matches"
        return "Done"
