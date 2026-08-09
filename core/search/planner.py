"""
SearchPlanner - builds an ordered search plan with read-only tool access.

Before scanning, the planner acts like a tiny agent: given the user's
natural-language request, it may call the read-only tools from the
:class:`~core.agent.tool_registry.ToolRegistry` (bound to the folder being
searched) to inspect the workspace - list directories, read files, grep
for terms - and then emits a decision-tree plan:

- ``query``    - the precise description the chunk scans will ask about
- ``keywords`` - concrete terms that drive the light-mode prefilter
- ``files``    - relative paths to restrict the scan to ([] = everything)
- ``steps``    - the ordered plan of what will happen, in which order

The protocol mirrors the agent's proven loop: schema-rich prompt + few-shot,
JSON tool-call replies with repair retries, a step budget, and a safe
fallback to the raw prompt when the model cannot produce a plan. The
planner is strictly read-only (see :data:`READ_ONLY_TOOLS`): it can inspect
the workspace but can never run commands or modify files.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from core.agent.tool_registry import ToolRegistry, tool_content_for_context
from core.search.paragraph_search import extract_keywords

GenerateFn = Callable[..., str]

# The planner inspects the workspace but must never change it: only these
# read-only tools are exposed, so it cannot run commands or write files
# while planning (enforced even if a full registry is passed in).
READ_ONLY_TOOLS = ("list_directory", "read_file", "search_files")

_FEW_SHOT = """\
EXAMPLE:
User request: "find the paragraph about gpu offloading"
Assistant: {"reasoning": "List the workspace to see the candidate files.", \\
"tool_calls": [{"tool": "list_directory", "parameters": {"path": "."}}]}
Tool results:
list_directory → status=success
content: main.py, notes.txt, readme.md (3 items)
Assistant: {"reasoning": "notes.txt is the likely home of the passage.", \\
"tool_calls": [], "done": true, \\
"query": "GPU offloading and how layers move to VRAM", \\
"keywords": ["gpu", "offload", "vram"], "files": ["notes.txt"], \\
"steps": ["1. Scan notes.txt for the GPU offloading passage", \\
"2. Quote the passage verbatim", "3. Report the quote"]}"""


@dataclass
class SearchPlan:
    """An ordered search plan produced by :class:`SearchPlanner`."""

    query: str
    keywords: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    trace: List[dict] = field(default_factory=list)  # read-only calls made

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "keywords": self.keywords,
            "files": self.files,
            "steps": self.steps,
            "trace": self.trace,
        }


class SearchPlanner:
    """Tool-using planner that distills a prompt into a :class:`SearchPlan`."""

    def __init__(
        self,
        generate: GenerateFn,
        *,
        tools: Optional[ToolRegistry] = None,
        read_only: bool = True,
        max_steps: int = 6,
        max_calls_per_round: int = 4,
        plan_tokens: int = 700,
        json_repairs: int = 2,
    ) -> None:
        self._generate = generate
        self.read_only = read_only
        if tools is not None and read_only:
            # Restrict to the read-only subset: the prompt only advertises
            # these tools and anything else returns "unknown tool".
            tools = ToolRegistry(tools.workspace, only=READ_ONLY_TOOLS)
        self._tools = tools
        self.max_steps = max_steps
        self.max_calls_per_round = max_calls_per_round
        self.plan_tokens = plan_tokens
        self.json_repairs = json_repairs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def plan(
        self,
        prompt: str,
        *,
        should_cancel: Optional[Callable[[], bool]] = None,
        on_tool_call: Optional[Callable[[dict], None]] = None,
    ) -> SearchPlan:
        """Distill *prompt* into a plan, calling tools as needed.

        ``on_tool_call`` fires immediately after each read-only tool
        executes with ``{"tool", "target"}`` so the UI can stream the
        planner's activity live.
        """
        history: List[str] = []
        trace: List[dict] = []
        repairs_left = self.json_repairs

        for _ in range(self.max_steps):
            if should_cancel is not None and should_cancel():
                break
            answer = self._ask(prompt, history)
            parsed = self._parse_json(answer)
            if parsed is None:
                if repairs_left > 0:
                    repairs_left -= 1
                    history.append(
                        "Your previous reply was not valid JSON. "
                        "Reply with ONLY the JSON object.\n"
                        f"Previous reply: {answer[:300]}"
                    )
                    continue
                break  # model cannot produce JSON at all -> fallback

            calls = parsed.get("tool_calls") or []
            if calls:
                if self._tools is None:
                    history.append(
                        "No tools are available in this mode. Reply with the "
                        "final plan JSON (done: true, query, keywords, steps)."
                    )
                    continue
                for call in calls[: self.max_calls_per_round]:
                    name = str(call.get("tool", ""))
                    if self.read_only and name not in READ_ONLY_TOOLS:
                        history.append(
                            f"tool '{name}' is not available in read-only planning"
                        )
                        continue
                    params = call.get("parameters") or {}
                    result = self._tools.execute(name, params)
                    entry = {"tool": name, "target": self._call_target(name, params)}
                    trace.append(entry)
                    if on_tool_call is not None:
                        on_tool_call(dict(entry))
                    history.append(self._format_result(name, result))
                continue

            # No tool calls: expect the final plan.
            if parsed.get("done") or self._usable(parsed):
                return self._to_plan(parsed, prompt, trace)
            break  # malformed final reply -> fallback

        return self._fallback(prompt, trace)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _system_prompt(self) -> str:
        workspace = self._tools.workspace if self._tools is not None else "(none)"
        tools_block = (
            self._tools.describe()
            if self._tools is not None
            else "No tools are available; answer directly with the plan."
        )
        return (
            "You are a search planner. You plan a document search - you do "
            "NOT execute the task. The folder being searched is:\n"
            f"{workspace}\n\n"
            "You have tools to inspect the folder before planning:\n"
            f"{tools_block}\n\n"
            "Reply with ONLY a JSON object, no commentary. To inspect, use:\n"
            '{"reasoning": "...", "tool_calls": [{"tool": "NAME", '
            '"parameters": {...}}]}\n'
            "When you have enough information, reply with the final plan:\n"
            '{"reasoning": "...", "tool_calls": [], "done": true, '
            '"query": "a 4-12 word description of the passage to find", '
            '"keywords": ["term1", "term2"], "files": ["rel/path", ...], '
            '"steps": ["1. ...", "2. ..."]}\n\n'
            "Rules:\n"
            "- Always work inside the workspace; paths are relative to it.\n"
            "- Prefer cheap reads: list_directory, search_files, read_file.\n"
            "- keywords: 2-6 concrete lowercase terms likely verbatim in the "
            "text (keep the request's language, e.g. Persian).\n"
            "- files: relative paths to search, or [] to search everything.\n"
            "- steps: the ordered decision tree - what happens and in which "
            "order.\n\n"
            f"{_FEW_SHOT}"
        )

    def _ask(self, prompt: str, history: List[str]) -> str:
        transcript = "\n\n".join(history) if history else "(no tool calls yet)"
        user = (
            f"User request: {prompt}\n\n"
            f"TRANSCRIPT SO FAR:\n{transcript}\n\n"
            "Now produce the next JSON reply:"
        )
        return self._generate(
            self._system_prompt() + "\n\n" + user,
            max_tokens=self.plan_tokens,
            temperature=0.1,
        )

    @staticmethod
    def _parse_json(answer: str) -> Optional[dict]:
        candidates = [answer or ""]
        match = re.search(r"\{.*\}", answer or "", flags=re.DOTALL)
        if match:
            candidates.append(match.group(0))
        for text in candidates:
            try:
                data = json.loads(text)
            except (ValueError, TypeError):
                continue
            if isinstance(data, dict):
                return data
        return None

    @staticmethod
    def _usable(parsed: dict) -> bool:
        query = parsed.get("query")
        return isinstance(query, str) and bool(query.strip())

    def _to_plan(self, parsed: dict, prompt: str, trace: List[dict]) -> SearchPlan:
        raw_query = parsed.get("query")
        query = raw_query.strip() if isinstance(raw_query, str) and raw_query.strip() else prompt.strip()
        keywords = [k.lower().strip() for k in (parsed.get("keywords") or [])
                    if isinstance(k, str) and k.strip()]
        if not keywords:
            keywords = extract_keywords(prompt)
        files = [f.strip() for f in (parsed.get("files") or [])
                 if isinstance(f, str) and f.strip()][:30]
        steps = [s.strip() for s in (parsed.get("steps") or [])
                 if isinstance(s, str) and s.strip()]
        return SearchPlan(query=query, keywords=keywords[:8], files=files, steps=steps,
                          trace=trace)

    def _fallback(self, prompt: str, trace: List[dict]) -> SearchPlan:
        return SearchPlan(query=prompt.strip(), keywords=extract_keywords(prompt),
                          trace=trace)

    @staticmethod
    def _call_target(name: str, params: dict) -> str:
        """Human-readable target of a read-only call (file/dir/pattern)."""
        if name == "search_files":
            pattern = params.get("pattern") or params.get("query", "")
            return f"{pattern} in {params.get('path', '.')}"
        return str(params.get("path", "."))

    @staticmethod
    def _format_result(name: str, result: dict) -> str:
        line = f"{name} → status={result.get('status', '?')}"
        content = tool_content_for_context(result)
        if content:
            return line + "\n" + content
        if result.get("error"):
            return line + "\nerror: " + str(result["error"])[:400]
        payload = result.get("result")
        if payload is not None:
            return line + "\n" + str(payload)[:400]
        return line
