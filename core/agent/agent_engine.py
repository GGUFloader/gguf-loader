"""
AgentEngine - Pure, testable agent loop for GGUF Loader.

The engine has no Qt and no knowledge of llama_cpp; it receives a plain
callable ``llm(prompt, max_tokens, temperature) -> str`` and emits
status/tool events through optional callbacks. Services layer runs it on
a worker thread and forwards events to the UI via Qt signals.

Flow per user message:
1. (optional) quick analysis for complex requests
2. ask the model for a JSON tool-call plan
3. execute each tool, streaming status updates
4. ask the model for a natural-language final response
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str], None]
ToolCallback = Callable[[Dict[str, Any]], None]

SYSTEM_PROMPT = """You are Kiro, an AI assistant built to help developers. You're knowledgeable, decisive, and supportive.

Your workspace: {workspace}

You have access to these tools:
{tools}

When you need to use tools, respond with ONLY this JSON format (no other text):
```json
{{
    "reasoning": "Brief, natural explanation",
    "tool_calls": [
        {{"tool": "tool_name", "parameters": {{"param": "value"}}}}
    ]
}}
```

Key behaviors:
- Jump straight into action when the task is clear
- Use tools proactively - don't over-explain, just do it
- For simple tasks, be brief. For complex ones, provide context.
- If something fails, explain what happened and suggest alternatives
- Always work within the workspace directory
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
    """Runs the tool-use loop for a single user message."""

    def __init__(
        self,
        llm: Callable[..., str],
        workspace: str | Path,
        tools: Optional[ToolRegistry] = None,
        max_tokens: int = 2048,
    ) -> None:
        self.llm = llm
        self.workspace = Path(workspace)
        self.tools = tools or ToolRegistry(self.workspace)
        self.max_tokens = max_tokens
        self.conversation_history: List[Dict[str, str]] = []

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

            # 2. Ask for a tool plan
            context = self._build_context(user_message)
            raw = self._ask(context)
            tool_calls = self._parse_tool_calls(raw)

            # 3. Execute tools
            tool_results: List[Dict[str, Any]] = []
            if tool_calls:
                self._announce_plan(tool_calls, status)
                for index, tool_call in enumerate(tool_calls, 1):
                    if len(tool_calls) > 1:
                        status(f"[{index}/{len(tool_calls)}] {self._describe(tool_call)}")
                    result = self.tools.execute(
                        tool_call.get("tool", ""), tool_call.get("parameters", {})
                    )
                    tool_results.append(result)
                    if on_tool:
                        on_tool(result)
                    if result.get("status") == "success":
                        status(f"  ✓ {self._summarize_result(result)}")
                    else:
                        status(f"  ✗ {result.get('error', 'Unknown error')}")

            # 4. Final natural-language response
            if tool_results:
                status("")
                response = self._final_response(user_message, tool_results)
            else:
                response = raw

            self.conversation_history.append({"role": "assistant", "content": response})
            return {"response": response, "tool_results": tool_results}

        except Exception as e:
            logger.error("Agent error: %s", e)
            return {"response": f"Error: {e}", "tool_results": []}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _is_complex(self, message: str) -> bool:
        keywords = ["complex", "multiple", "several", "build", "create system"]
        return len(message.split()) > 20 or any(w in message.lower() for w in keywords)

    def _build_context(self, message: str) -> str:
        system = SYSTEM_PROMPT.format(workspace=self.workspace, tools=self.tools.describe())
        parts = [system, ""]
        for msg in self.conversation_history[-6:]:
            parts.append(f"{msg['role'].capitalize()}: {msg['content']}")
            parts.append("")
        parts.append(f"User: {message}")
        parts.append("Assistant: ")
        return "\n".join(parts)

    def _ask(self, prompt: str) -> str:
        try:
            return self.llm(prompt, max_tokens=self.max_tokens, temperature=0.1)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return ""

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        data = extract_json(response)
        if data is None:
            return []
        calls = data.get("tool_calls", [])
        return [c for c in calls if isinstance(c, dict) and c.get("tool")]

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
                context.append(f"✓ {tool}: {result.get('result', 'Success')}")
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
