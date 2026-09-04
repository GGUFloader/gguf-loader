"""
PromptBuilder — constructs LLM prompts from messages + tool results.

Extracted from GraphAgent to separate prompt construction from the agent
loop.  The builder owns:
  - System prompt generation (router-provided; never a generic fallback)
  - Cached prefix (system prompt + workspace context)
  - Action prompt assembly (prefix + transcript + tool results + directives)
  - Tool result formatting for context

Deleting this module concentrates all prompt logic in one place — the
deletion test passes because the alternative is scattering prompt
fragments across 15+ methods in GraphAgent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .tool_registry import ToolRegistry, tool_content_for_context
from .workspace_context import PromptPrefixCache


# System prompt comes exclusively from the model router via
# model_families.json.  The router injects the correct prompt per
# model family.  No hardcoded fallback — the router must always provide one.


class PromptBuilder:
    """Builds and caches prompts for the agent loop.

    Parameters
    ----------
    workspace : Path
        Workspace root directory.
    tools : ToolRegistry
        Registry of available tools (used for __TOOLS__ replacement).
    system_prompt_override : Optional[str]
        System prompt from the model router (model_families.json). Required:
        the agent refuses to run without it (see :meth:`system_prompt`).
    """

    def __init__(
        self,
        workspace: Path,
        tools: ToolRegistry,
        system_prompt_override: Optional[str] = None,
        preset_override: Optional[str] = None,
    ) -> None:
        self.workspace = workspace
        self.tools = tools
        self._system_prompt_override = system_prompt_override
        self._preset_override = preset_override or ""
        self._prefix_cache = PromptPrefixCache()

    # ── Public API ────────────────────────────────────────────────────────

    def system_prompt(self, with_tools: bool = True, with_mode: bool = True) -> str:
        """Build the system prompt with workspace and tool descriptions.

        The prompt MUST come from the model router (model_families.json).
        There is deliberately NO generic fallback: running the agent with
        a made-up prompt silently degrades it (the exact bug this module
        used to have). If the router failed to provide one, we fail loudly
        so the misconfiguration is visible instead of the agent quietly
        misbehaving.

        Composition: family identity/rules first, then the preset mode
        block (when ``with_mode``), then the tool catalog (when
        ``with_tools``).

        ``with_tools=False`` skips the appended tool catalog — used by the
        plan/answer paths, which either carry their own tool list (the plan
        prompt) or should not be flooded with tool schemas at all (pure
        answer synthesis).

        ``with_mode=False`` skips the preset block ("MODE: Full Stack —
        commit changes, run tests"). Mode text tells the model HOW to act
        with tools; it must never front a pure general-knowledge answer,
        where it reads as noise and biases the reply.
        """
        if not self._system_prompt_override:
            raise RuntimeError(
                "No system prompt provided by the model router. Add a "
                "`system_prompt` for this model family in "
                "ggufloader/config/model_families.json (or pass "
                "system_prompt=... when constructing GraphAgent). The agent "
                "refuses to run with a generic fallback prompt."
            )
        base = self._system_prompt_override
        base = base.replace("__WORKSPACE__", str(self.workspace))
        if with_mode and self._preset_override:
            base = base.rstrip() + "\n\n" + self._preset_override
        if "__TOOLS__" in base:
            base = base.replace("__TOOLS__", self.tools.describe())
        elif with_tools:
            # Task 10 (one tool universe): the prompt must always list the
            # LIVE registry tool set (preset-filtered), never a hardcoded
            # subset. Family prompts no longer enumerate tools themselves.
            described = self.tools.describe()
            if described:
                base = base.rstrip() + "\n\nAvailable tools:\n" + described
        return base

    def fix_prompt(
        self,
        failed_call: Dict[str, Any],
        failed_result: Dict[str, Any],
    ) -> str:
        """Build a prompt asking the model to correct a failed tool call."""
        import json
        tool_name = failed_call.get("tool", "")
        params = failed_call.get("parameters", {})
        error = failed_result.get("error", "Unknown error")
        return (
            self.system_prompt() + "\n\n"
            "A tool call just failed. Correct the parameters and retry, or decide it cannot be done.\n\n"
            f"Failed tool: {tool_name}\n"
            f"Parameters used: {json.dumps(params, ensure_ascii=False)[:800]}\n"
            f"Error: {error}\n\n"
            f'Respond with ONLY the JSON object. Include at most one corrected tool_calls entry for "{tool_name}" '
            '(or "tool_calls": [] if the task cannot be completed with corrected parameters).\n'
            "Assistant:"
        )

    def final_response_context(
        self,
        user_question: str,
        direct_answer: str,
    ) -> str:
        """Build context for LLM polish of the final answer."""
        return (
            f"User asked: {user_question}\n\n"
            f"Here is what I found:\n{direct_answer}\n\n"
            "IMPORTANT: Write a clear, natural-language answer for the user. "
            "Do NOT call any tools. Do NOT return JSON. Just write text. "
            "Answer truthfully from the findings above: if nothing matched or an "
            "error occurred, say so — never invent file names or paths."
        )

    # ── Internal ────────────────────────────────────────────────────────

    def _get_prefix(self) -> str:
        """Get cached prompt prefix (system prompt only — tools are embedded)."""
        return self._prefix_cache.get_prefix(
            system_prompt=self.system_prompt(),
            workspace_context="",   # already embedded in system_prompt
            tool_descriptions="",   # already embedded in system_prompt
        )

    def _format_tool_results(self, tool_results: List[Dict[str, Any]]) -> List[str]:
        """Format tool results for inclusion in the prompt (last 3 only)."""
        lines: List[str] = []
        for result in tool_results[-3:]:
            tool = result.get("tool_name", "unknown")
            outcome = "success" if result.get("status") == "success" else "error"
            content = tool_content_for_context(result)
            if content is not None:
                lines.append(f"Tool result for {tool}: {outcome} - {content}")
            else:
                lines.append(f"Tool result for {tool}: {outcome} - {self._summarize_result(result)}")
        return lines

    def _summarize_result(self, result: Dict[str, Any]) -> str:
        """Human-readable one-liner for a tool result."""
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
