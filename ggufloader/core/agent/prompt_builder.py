"""
PromptBuilder — constructs LLM prompts from messages + tool results.

Extracted from GraphAgent to separate prompt construction from the agent
loop.  The builder owns:
  - System prompt generation (lightweight file-assistant mode)
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
        If provided, replaces the lightweight default system prompt. Used by
        the router to inject a per-family system prompt.
    """

    def __init__(
        self,
        workspace: Path,
        tools: ToolRegistry,
        system_prompt_override: Optional[str] = None,
    ) -> None:
        self.workspace = workspace
        self.tools = tools
        self._system_prompt_override = system_prompt_override
        self._prefix_cache = PromptPrefixCache()

    # ── Public API ────────────────────────────────────────────────────────

    def system_prompt(self) -> str:
        """Build the system prompt with workspace and tool descriptions.

        Uses the router-provided prompt (from model_families.json). Logs a
        warning when no router prompt was supplied — the router should
        always provide one in production.
        """
        if not self._system_prompt_override:
            import logging as _log
            _log.getLogger(__name__).warning(
                "No system prompt provided by the router. "
                "Falling back to minimal prompt — add system_prompt to model_families.json."
            )
        base = self._system_prompt_override or (
            "You are a helpful file assistant. Read files and help users."
        )
        base = base.replace("__WORKSPACE__", str(self.workspace))
        base = base.replace("__TOOLS__", self.tools.describe())
        return base

    def action_prompt(
        self,
        messages: List[Dict[str, str]],
        tool_results: List[Dict[str, Any]],
        repair: str = "",
        directive: str = "",
    ) -> str:
        """Build the full action prompt using cached prefix.

        The prefix (system prompt) is cached across turns; only the
        variable suffix (transcript + tool results) is rebuilt.
        """
        prefix = self._get_prefix()
        parts = [prefix, ""]

        # Last 4 messages of transcript
        for msg in messages[-4:]:
            parts.append(f"{msg['role'].capitalize()}: {msg['content']}")
            parts.append("")

        # Tool results (last 3)
        if tool_results:
            parts.append("Tool results:")
            parts.extend(self._format_tool_results(tool_results))
            parts.append("")

        # Repair prompt (for malformed JSON retries)
        if repair:
            parts.append(
                "Your previous response was not valid JSON. Reply with ONLY the JSON "
                "object described above - no markdown fences, no extra text."
            )
            parts.append("")
            parts.append("Your previous (invalid) response was:")
            parts.append(repair[:1500])
            parts.append("")

        # Directive (e.g. read-coverage for summarize requests)
        if directive:
            parts.append("IMPORTANT - follow this instruction before replying:")
            parts.append(directive)
            parts.append("")

        parts.append("Assistant:")
        return "\n".join(parts)

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
            "Do NOT call any tools. Do NOT return JSON. Just write text."
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
