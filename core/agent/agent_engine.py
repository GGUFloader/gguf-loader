"""
AgentEngine - Pure, testable agent loop for GGUF Loader.

The engine has no Qt and no knowledge of llama_cpp; it receives a plain
callable ``llm(prompt, max_tokens, temperature) -> str`` and emits
status/tool events through optional callbacks. Services layer runs it on
a worker thread and forwards events to the UI via Qt signals.

Flow per user message (multi-step, budgeted):
1. (optional) quick analysis for complex requests
2. loop up to ``max_steps`` times:
   a. ask the model for the next JSON action (tool_calls or answer),
      repairing malformed JSON up to ``json_retries`` times
   b. execute each tool call; failed calls get one corrective retry
   c. feed results back so the model can continue or finish
3. produce a natural-language final response
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .tool_registry import ToolRegistry, tool_content_for_context

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str], None]
ToolCallback = Callable[[Dict[str, Any]], None]

_SYSTEM_PROMPT = """You are Kiro, an AI assistant built to help developers. You're knowledgeable, decisive, and supportive.

Your workspace: __WORKSPACE__

You have access to these tools:
__TOOLS__

You talk to the system through a strict JSON protocol. Whenever you need to use tools - and after every tool result arrives - reply with ONLY a JSON object (no markdown fences, no surrounding text):

{
  "reasoning": "Brief, natural explanation of what you're doing",
  "tool_calls": [
    {"tool": "tool_name", "parameters": {"param": "value"}}
  ],
  "answer": "Final answer text; only include this when no more tool calls are needed"
}

Rules:
- Jump straight into action when the task is clear; use tools proactively
- When no more tool calls are needed, return "tool_calls": [] and put your final answer in "answer"
- When a tool fails, read the error message and retry with corrected parameters
- Always work within the workspace directory

Example conversation:

User: Create notes.md containing "Hello", then list the workspace.
Assistant:
{"reasoning": "I'll create the file first.", "tool_calls": [{"tool": "write_file", "parameters": {"path": "notes.md", "content": "Hello"}}]}
Tool result for write_file: success - Successfully wrote 5 characters to notes.md
Assistant:
{"reasoning": "The file was created. Now I'll list the workspace.", "tool_calls": [{"tool": "list_directory", "parameters": {"path": "."}}]}
Tool result for list_directory: success - Found 1 items
Assistant:
{"reasoning": "Task complete.", "tool_calls": [], "answer": "Created notes.md with the text \"Hello\" and confirmed it's in the workspace."}
"""


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from a model response.

    Handles fenced ```json blocks, bare objects, and objects embedded in
    prose. Returns None when nothing parseable is found.
    """
    if not text:
        return None

    candidates: List[str] = []

    # 1. Explicit json code fences (may contain several objects - take first)
    for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
        candidates.append(match.group(1))

    # 2. Bare balanced-brace objects anywhere in the text
    for match in _balanced_objects(text):
        candidates.append(match)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return None


def _balanced_objects(text: str):
    """Yield substrings of *text* that span balanced brace pairs."""
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                yield text[start:i + 1]
                start = -1


class AgentEngine:
    """Runs the multi-step tool-use loop for a single user message."""

    def __init__(
        self,
        llm: Callable[..., str],
        workspace: str | Path,
        tools: Optional[ToolRegistry] = None,
        max_tokens: int = 2048,
        max_steps: int = 8,
        json_retries: int = 2,
    ) -> None:
        self.llm = llm
        self.workspace = Path(workspace)
        self.tools = tools or ToolRegistry(self.workspace)
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.json_retries = json_retries
        self.conversation_history: List[Dict[str, str]] = []
        self._step_log: List[str] = []
        self._failed_signatures: Dict[str, int] = {}
        self._last_raw_response = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def process(
        self,
        user_message: str,
        on_status: Optional[StatusCallback] = None,
        on_tool: Optional[ToolCallback] = None,
    ) -> Dict[str, Any]:
        """Process *user_message* and return ``{"response": str, "tool_results": [...]}``."""
        self.conversation_history.append({"role": "user", "content": user_message})
        status = on_status or (lambda _msg: None)
        self._step_log = []
        self._failed_signatures = {}

        try:
            # 1. Optional quick analysis for complex requests
            if self._is_complex(user_message):
                status("🤔 Analyzing your request...")
                analysis = self._ask(
                    f"Quickly analyze this request in 2-3 concise sentences:\n\nUser Request: {user_message}"
                )
                if analysis.strip():
                    status(f"💡 {analysis.strip()}")
                    status("")

            tool_results: List[Dict[str, Any]] = []
            final_answer: Optional[str] = None

            # 2. Multi-step loop with a hard budget
            for step in range(1, self.max_steps + 1):
                if step > 1:
                    status(f"▶ Step {step}/{self.max_steps}")

                action = self._request_action()
                if action is None:
                    # Model could not produce valid JSON at all - fall back to chat
                    final_answer = self._last_raw_response or ""
                    break

                calls = [
                    c for c in (action.get("tool_calls") or [])
                    if isinstance(c, dict) and c.get("tool")
                ]
                if not calls:
                    final_answer = self._finish(user_message, action, tool_results)
                    break

                self._announce_plan(calls, status)
                failures: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
                for index, call in enumerate(calls, 1):
                    if len(calls) > 1:
                        status(f"[{index}/{len(calls)}] {self._describe(call)}")
                    signature = self._signature(call)
                    if self._failed_signatures.get(signature, 0) >= 2:
                        status(f"  ⏭ Skipping repeated failing call: {self._describe(call)}")
                        continue
                    result = self.tools.execute(call.get("tool", ""), call.get("parameters", {}))
                    tool_results.append(result)
                    if on_tool:
                        on_tool(result)
                    self._log_tool_result(call, result)
                    if result.get("status") == "success":
                        status(f"  ✓ {self._summarize_result(result)}")
                    else:
                        status(f"  ✗ {result.get('error', 'Unknown error')}")
                        self._failed_signatures[signature] = self._failed_signatures.get(signature, 0) + 1
                        failures.append((call, result))

                # 3. One corrective retry per failed call
                for failed_call, failed_result in failures:
                    fixed = self._request_fix(failed_call, failed_result)
                    if fixed is None:
                        continue
                    tool_results.append(fixed)
                    if on_tool:
                        on_tool(fixed)
                    self._log_tool_result(failed_call, fixed)
                    if fixed.get("status") == "success":
                        status(f"  ✓ retry succeeded: {self._summarize_result(fixed)}")
                    else:
                        status(f"  ✗ retry failed: {fixed.get('error', 'Unknown error')}")
                # Loop continues: results are in context, the model decides the next action.

            if final_answer is None:
                final_answer = self._final_response(user_message, tool_results)

            self.conversation_history.append({"role": "assistant", "content": final_answer})
            return {"response": final_answer, "tool_results": tool_results}

        except Exception as e:
            logger.error("Agent error: %s", e)
            return {"response": f"Error: {e}", "tool_results": []}

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------
    def _system_prompt(self) -> str:
        return (
            _SYSTEM_PROMPT
            .replace("__WORKSPACE__", str(self.workspace))
            .replace("__TOOLS__", self.tools.describe())
        )

    def _build_action_prompt(self, repair: str = "") -> str:
        """Prompt asking the model for the next JSON action.

        Includes the conversation tail, tool activity from this session,
        and - when *repair* is set - feedback that the last response was
        not valid JSON.
        """
        parts = [self._system_prompt(), ""]
        for msg in self.conversation_history[-4:]:
            parts.append(f"{msg['role'].capitalize()}: {msg['content']}")
            parts.append("")
        if self._step_log:
            parts.append("Recent tool activity:")
            parts.extend(self._step_log[-10:])
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

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------
    def _ask(self, prompt: str) -> str:
        try:
            return self.llm(prompt, max_tokens=self.max_tokens, temperature=0.1)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return ""

    def _request_action(self) -> Optional[Dict[str, Any]]:
        """Ask for the next action, repairing malformed JSON up to json_retries times."""
        prompt = self._build_action_prompt()
        for _attempt in range(self.json_retries + 1):
            raw = self._ask(prompt)
            self._last_raw_response = raw
            data = extract_json(raw)
            if data is not None:
                return data
            prompt = self._build_action_prompt(repair=raw)
        return None

    def _request_fix(self, failed_call: Dict[str, Any], failed_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Ask the model to correct a failed tool call; execute the corrected call.

        Returns the corrected tool result, or None when the model supplies
        no replacement call.
        """
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
        raw = self._ask(prompt)
        self._last_raw_response = raw
        data = extract_json(raw)
        if data is None:
            return None
        calls = [
            c for c in (data.get("tool_calls") or [])
            if isinstance(c, dict) and c.get("tool")
        ]
        if not calls:
            return None
        call = next((c for c in calls if c.get("tool") == tool_name), calls[0])
        return self.tools.execute(call.get("tool", ""), call.get("parameters", {}))

    # ------------------------------------------------------------------
    # Loop helpers
    # ------------------------------------------------------------------
    def _finish(self, user_message: str, action: Dict[str, Any], tool_results: List[Dict[str, Any]]) -> str:
        answer = (action.get("answer") or "").strip()
        if answer:
            return answer
        if tool_results:
            return self._final_response(user_message, tool_results)
        return self._last_raw_response or "No further action needed."

    def _signature(self, call: Dict[str, Any]) -> str:
        try:
            params = json.dumps(call.get("parameters", {}), sort_keys=True, ensure_ascii=False)
        except Exception:  # noqa: BLE001 - defensive
            params = str(call.get("parameters"))
        return f"{call.get('tool', '')}:{params}"

    def _log_tool_result(self, call: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Append a compact tool outcome to the session log fed back to the model."""
        tool = call.get("tool", "unknown")
        params = json.dumps(call.get("parameters", {}), ensure_ascii=False)[:300]
        outcome = "success" if result.get("status") == "success" else "error"
        content = tool_content_for_context(result)
        if content is not None:
            summary = content
        else:
            summary = self._summarize_result(result)
        self._step_log.append(f"{tool}({params}): {outcome} - {summary}")
        if len(self._step_log) > 30:
            self._step_log.pop(0)

    def _is_complex(self, message: str) -> bool:
        keywords = ["complex", "multiple", "several", "build", "create system"]
        return len(message.split()) > 20 or any(w in message.lower() for w in keywords)

    def _announce_plan(self, calls: List[Dict[str, Any]], status: StatusCallback) -> None:
        if len(calls) == 1:
            status(f"→ {self._describe(calls[0])}")
        else:
            status(f"→ {len(calls)} tasks to complete:")
            for index, call in enumerate(calls, 1):
                status(f"  {index}. {self._describe(call)}")
        status("")

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

    def _final_response(self, user_message: str, tool_results: List[Dict[str, Any]]) -> str:
        context = [f"User asked: {user_message}", "", "I completed these operations:"]
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
        response = self._ask("\n".join(context))
        if response.strip():
            return response
        # Fallback summary when the model returns nothing useful
        success = sum(1 for r in tool_results if r.get("status") == "success")
        if success == len(tool_results):
            return "Done! All operations completed successfully."
        if success > 0:
            return f"Completed {success} out of {len(tool_results)} operations. Some had issues."
        return "Ran into some issues completing those operations. Check the errors above."
