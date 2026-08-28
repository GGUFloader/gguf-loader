"""
Delegation - Bounded read-only child agent for subtask decomposition.

Inspired by Mini-Coding-Agent's delegation and OpenHands' sub-agent pattern.
The parent agent can spawn a read-only child to explore files, summarize code,
or answer questions without risking file modifications.

The child agent:
- Has only read-only tools (read_file, list_directory, search_files)
- Is bounded: max 3 steps, 500 token output
- Returns a summary to the parent context
- Cannot modify the workspace
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class DelegationToken:
    """Sentinel returned when delegation completes."""

    def __init__(self, summary: str, tools_used: List[str]) -> None:
        self.summary = summary
        self.tools_used = tools_used


class ChildAgent:
    """Bounded read-only child agent for subtask exploration.

    Usage:
        child = ChildAgent(parent_engine.llm, parent_engine.workspace, parent_engine.tools)
        result = child.explore("Find all Python files that import os")
        # result.summary = "Found 3 files: a.py, b.py, c.py"
    """

    MAX_STEPS = 3
    MAX_OUTPUT_CHARS = 500

    def __init__(
        self,
        llm: Callable[..., str],
        workspace: Any,
        parent_tools: Any,
        max_tokens: int = 512,
    ) -> None:
        self.llm = llm
        self.workspace = workspace
        self.parent_tools = parent_tools
        self.max_tokens = max_tokens
        self._read_only_tools = self._extract_read_only_tools()

    def _extract_read_only_tools(self) -> Dict[str, Any]:
        """Extract read-only tools from the parent's tool registry."""
        read_only = {}
        for name in ("read_file", "list_directory", "search_files"):
            tool = self.parent_tools._tools.get(name)
            if tool is not None:
                read_only[name] = tool
        return read_only

    def _build_prompt(self, task: str, history: List[Dict[str, str]]) -> str:
        """Build the child agent's system prompt."""
        tools_desc = "\n".join(
            f"- {name}: {tool.description}"
            for name, tool in self._read_only_tools.items()
        )
        return (
            "You are a read-only exploration agent. Your job is to investigate "
            "the workspace and return a concise summary.\n\n"
            f"Workspace: {self.workspace}\n\n"
            f"Available tools (READ ONLY):\n{tools_desc}\n\n"
            "Respond with ONLY a JSON object:\n"
            '{"tool_calls": [{"tool": "tool_name", "parameters": {...}}], '
            '"answer": "Your summary here"}\n\n'
            "Rules:\n"
            "- Use tools to explore the workspace\n"
            "- When done, provide a concise answer\n"
            "- Maximum 3 tool calls\n"
            "- NEVER modify files\n"
        )

    def _execute_tool(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a read-only tool call."""
        tool = self._read_only_tools.get(name)
        if tool is None:
            return {"status": "error", "error": f"Unknown tool: {name}"}
        try:
            return tool.execute(params)
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def explore(self, task: str) -> DelegationToken:
        """Run the child agent to explore and summarize.

        Args:
            task: The exploration task (e.g., "Find all error handlers")

        Returns:
            DelegationToken with summary and tools used
        """
        from .agent_engine import extract_json

        history: List[Dict[str, str]] = [
            {"role": "user", "content": task}
        ]
        tools_used: List[str] = []
        all_results: List[str] = []

        for step in range(self.MAX_STEPS):
            prompt = self._build_prompt(task, history)
            # Add conversation to prompt
            for msg in history:
                prompt += f"\n{msg['role'].capitalize()}: {msg['content']}"
            prompt += "\n\nAssistant:"

            try:
                raw = self.llm(prompt, max_tokens=self.max_tokens, temperature=0.1)
            except Exception as e:
                logger.error("Child agent LLM call failed: %s", e)
                break

            data = extract_json(raw)
            if data is None:
                break

            calls = [
                c for c in (data.get("tool_calls") or [])
                if isinstance(c, dict) and c.get("tool")
            ]

            if not calls:
                # Agent provided an answer
                answer = (data.get("answer") or "").strip()
                if answer:
                    all_results.append(answer)
                break

            # Execute tools
            for call in calls:
                tool_name = call.get("tool", "")
                params = call.get("parameters", {})
                result = self._execute_tool(tool_name, params)
                tools_used.append(tool_name)

                # Extract content for context
                content = result.get("result", "")
                if isinstance(content, list):
                    content = str(content[:20])
                elif isinstance(content, str):
                    content = content[:200]

                all_results.append(f"{tool_name}: {content}")
                history.append({
                    "role": "assistant",
                    "content": f"Called {tool_name}. Result: {content}"
                })

        # Build summary
        summary = "\n".join(all_results)
        if len(summary) > self.MAX_OUTPUT_CHARS:
            summary = summary[:self.MAX_OUTPUT_CHARS] + "..."

        logger.info(
            "Delegation complete: %d steps, %d tools used",
            len(history) - 1, len(tools_used),
        )
        return DelegationToken(summary=summary, tools_used=tools_used)


def should_delegate(user_message: str) -> bool:
    """Check if a user message should be delegated to a child agent.

    Delegation is triggered only for complex exploration tasks that benefit
    from a bounded read-only child. Simple questions should stay with the
    main agent to avoid unnecessary overhead.
    """
    lower = user_message.lower()
    # Only delegate for complex exploration — not simple questions
    delegate_patterns = (
        "find all", "list all files in", "search the entire",
        "explore the codebase", "summarize all the code",
        "give me an overview of the entire",
        "analyze all", "report on all",
    )
    # Don't delegate if the message asks for modifications
    modify_keywords = (
        "create", "write", "edit", "delete", "modify", "change",
        "fix", "update", "add", "remove", "implement",
    )
    has_delegate = any(k in lower for k in delegate_patterns)
    has_modify = any(k in lower for k in modify_keywords)
    return has_delegate and not has_modify
