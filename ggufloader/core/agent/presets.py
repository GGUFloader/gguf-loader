"""
AgentPresets - Predefined agent configurations for different task types.

Pattern from: Aider's edit-format modes + OpenHands agent types.
Each preset configures the agent's behavior, system prompt additions,
tool permissions, max steps, temperature, and approval settings for
a specific type of work.

Presets:
- research: Read-only exploration, no file modifications
- code_review: Read-only with structured analysis output
- refactor: Safe refactoring with auto-verify
- debug: Error-focused with diagnostic tools
- full_stack: All tools enabled, maximum flexibility
- quick_fix: Minimal steps, fast turnaround
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentPreset:
    """Configuration for a specific agent mode."""
    id: str
    name: str
    description: str
    icon: str

    # System prompt additions (appended to base prompt)
    system_prompt_addition: str = ""

    # Tool permissions
    allowed_tools: List[str] = field(default_factory=lambda: [
        "list_directory", "read_file", "search_files",
        "write_file", "edit_file", "run_command", "run_python", "git",
    ])
    blocked_tools: List[str] = field(default_factory=list)

    # Execution settings
    max_steps: int = 8
    max_tokens: int = 2048
    temperature: float = 0.1

    # Approval settings
    auto_approve_read: bool = True
    auto_approve_write: bool = False
    auto_approve_command: bool = False

    # Behavior flags
    auto_commit: bool = False
    auto_test: bool = False
    auto_verify: bool = True
    reflection_enabled: bool = True

    # UI hints
    show_reasoning: bool = True
    show_tool_details: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "max_steps": self.max_steps,
            "temperature": self.temperature,
            "auto_commit": self.auto_commit,
            "auto_test": self.auto_test,
        }

    def get_system_prompt(self, base_prompt: str) -> str:
        """Build the full system prompt with preset additions."""
        if self.system_prompt_addition:
            return base_prompt + "\n\n" + self.system_prompt_addition
        return base_prompt


# =====================================================================
# Built-in presets
# =====================================================================

PRESETS: Dict[str, AgentPreset] = {
    "research": AgentPreset(
        id="research",
        name="Research",
        description="Read-only exploration. No file modifications.",
        icon="🔍",
        system_prompt_addition=(
            "MODE: Research (read-only)\n"
            "You are in research mode. You can ONLY read files and search the workspace.\n"
            "Do NOT create, edit, or delete any files. Do NOT run commands.\n"
            "Focus on: understanding code structure, finding bugs, explaining behavior.\n"
            "When done, provide a detailed analysis with file references."
        ),
        allowed_tools=["list_directory", "read_file", "search_files"],
        blocked_tools=[
            "write_file", "edit_file", "run_command", "run_python", "git",
            # one tool universe: the only remaining mutate alias to also block
            "move_file",
        ],
        max_steps=12,
        temperature=0.1,
        auto_approve_read=True,
        auto_verify=False,
        show_reasoning=True,
    ),

    "code_review": AgentPreset(
        id="code_review",
        name="Code Review",
        description="Structured code analysis with actionable feedback.",
        icon="📝",
        system_prompt_addition=(
            "MODE: Code Review\n"
            "You are reviewing code. Analyze for:\n"
            "1. Bugs and logic errors\n"
            "2. Performance issues\n"
            "3. Security vulnerabilities\n"
            "4. Code style and maintainability\n"
            "5. Missing error handling\n\n"
            "Format your response as:\n"
            "## Summary\n<one-line assessment>\n"
            "## Critical Issues\n<list>\n"
            "## Suggestions\n<list>\n"
            "## Positive Notes\n<list>"
        ),
        allowed_tools=["list_directory", "read_file", "search_files"],
        blocked_tools=[
            "write_file", "edit_file", "run_command", "run_python", "git",
            # one tool universe: the only remaining mutate alias to also block
            "move_file",
        ],
        max_steps=10,
        temperature=0.1,
        auto_verify=False,
        show_reasoning=True,
    ),

    "refactor": AgentPreset(
        id="refactor",
        name="Refactor",
        description="Safe code refactoring with automatic verification.",
        icon="♻️",
        system_prompt_addition=(
            "MODE: Refactoring\n"
            "Focus on improving code quality without changing behavior.\n"
            "After every edit, verify the code still works:\n"
            "- Read the modified file to confirm syntax\n"
            "- Run tests if available\n"
            "- Make small, incremental changes\n"
            "Never refactor more than one file at a time unless clearly related."
        ),
        max_steps=15,
        temperature=0.05,
        auto_approve_write=False,
        auto_commit=True,
        auto_test=True,
        auto_verify=True,
        reflection_enabled=True,
    ),

    "debug": AgentPreset(
        id="debug",
        name="Debug",
        description="Error-focused debugging with diagnostics.",
        icon="🐛",
        system_prompt_addition=(
            "MODE: Debugging\n"
            "You are debugging an issue. Follow this process:\n"
            "1. Understand the error message and stack trace\n"
            "2. Locate the relevant code\n"
            "3. Identify the root cause\n"
            "4. Fix the issue\n"
            "5. Verify the fix works\n\n"
            "Be methodical. Don't guess — read the code and trace the execution."
        ),
        max_steps=12,
        temperature=0.1,
        auto_approve_command=True,  # needs to run test commands
        auto_test=True,
        auto_verify=True,
        reflection_enabled=True,
    ),

    "full_stack": AgentPreset(
        id="full_stack",
        name="Full Stack",
        description="All tools enabled. Maximum flexibility.",
        icon="🚀",
        system_prompt_addition=(
            "MODE: Full Stack\n"
            "All tools are available. Use them proactively.\n"
            "After code changes, run tests to verify.\n"
            "Commit significant changes with descriptive messages."
        ),
        max_steps=20,
        temperature=0.1,
        auto_approve_read=True,
        auto_approve_write=False,
        auto_approve_command=False,
        auto_commit=True,
        auto_test=True,
        auto_verify=True,
        reflection_enabled=True,
    ),

    "quick_fix": AgentPreset(
        id="quick_fix",
        name="Quick Fix",
        description="Fast, minimal changes. Few steps, no fluff.",
        icon="⚡",
        system_prompt_addition=(
            "MODE: Quick Fix\n"
            "Make the minimal change to fix the issue. No refactoring, no improvements.\n"
            "One file, one change, verify it works. Done."
        ),
        max_steps=4,
        max_tokens=1024,
        temperature=0.05,
        auto_approve_write=False,
        auto_verify=True,
        reflection_enabled=False,
        show_reasoning=False,
    ),
}


class PresetManager:
    """Manage agent presets with user customization support.

    Usage:
        pm = PresetManager()
        preset = pm.get("debug")
        pm.list_all()  # returns all presets
    """

    def __init__(self) -> None:
        self._presets = dict(PRESETS)
        self._custom_file = None

    def get(self, preset_id: str) -> Optional[AgentPreset]:
        """Get a preset by ID."""
        return self._presets.get(preset_id)

    def list_all(self) -> List[AgentPreset]:
        """Return all available presets."""
        return list(self._presets.values())

    def list_ids(self) -> List[str]:
        """Return all preset IDs."""
        return list(self._presets.keys())

    def register(self, preset: AgentPreset) -> None:
        """Register a custom preset."""
        self._presets[preset.id] = preset

    def unregister(self, preset_id: str) -> bool:
        """Remove a custom preset. Built-in presets cannot be removed."""
        if preset_id in PRESETS:
            return False  # can't remove built-in
        return self._presets.pop(preset_id, None) is not None

    def get_summary(self) -> List[Dict[str, str]]:
        """Return a summary list for UI display."""
        return [
            {"id": p.id, "name": p.name, "description": p.description, "icon": p.icon}
            for p in self._presets.values()
        ]
