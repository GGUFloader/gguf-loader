"""
Onboarding - First-time agent setup wizard.

Pattern from: Claude Code's initial setup + Aider's first-run experience.
Guides the user through:
1. Workspace selection
2. Model configuration
3. Agent preset selection
4. Tool permissions
5. AGENTS.md generation
6. Initial knowledge base population

The wizard generates a setup report and writes initial config.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config_manager import ConfigManager, AgentConfig
from .agents_md import AgentsMdGenerator
from .knowledge_base import KnowledgeBase
from .workspace_analytics import WorkspaceAnalytics

logger = logging.getLogger(__name__)


class OnboardingStep:
    """A single step in the onboarding wizard."""

    def __init__(self, step_id: str, title: str, description: str,
                 options: List[Dict[str, Any]] = None) -> None:
        self.step_id = step_id
        self.title = title
        self.description = description
        self.options = options or []
        self.selected: Optional[str] = None
        self.completed = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.step_id,
            "title": self.title,
            "description": self.description,
            "options": self.options,
            "selected": self.selected,
            "completed": self.completed,
        }


class OnboardingResult:
    """Result of the onboarding wizard."""

    def __init__(self) -> None:
        self.success = False
        self.config: Optional[AgentConfig] = None
        self.agents_md_generated = False
        self.knowledge_populated = False
        self.workspace_analyzed = False
        self.messages: List[str] = []
        self.errors: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "agents_md_generated": self.agents_md_generated,
            "knowledge_populated": self.knowledge_populated,
            "workspace_analyzed": self.workspace_analyzed,
            "messages": self.messages,
            "errors": self.errors,
        }


class OnboardingWizard:
    """Guide first-time users through agent setup.

    Usage:
        wizard = OnboardingWizard(workspace_path)

        # Get steps
        steps = wizard.get_steps()

        # Process user selections
        wizard.set_selection("workspace", "/path/to/project")
        wizard.set_selection("preset", "full_stack")

        # Complete setup
        result = wizard.complete()
    """

    def __init__(self, workspace: Path = None) -> None:
        self.workspace = workspace
        self._steps = self._build_steps()
        self._selections: Dict[str, str] = {}

    def _build_steps(self) -> List[OnboardingStep]:
        """Build the onboarding steps."""
        return [
            OnboardingStep(
                "workspace",
                "Select Workspace",
                "Choose the project directory for the agent to work in.",
                [
                    {"id": "current", "label": "Current directory", "description": str(self.workspace or ".")},
                    {"id": "browse", "label": "Browse for directory", "description": "Open file picker"},
                ],
            ),
            OnboardingStep(
                "preset",
                "Choose Agent Mode",
                "Select a preset that matches your primary use case.",
                [
                    {"id": "full_stack", "label": "🚀 Full Stack", "description": "All tools enabled, maximum flexibility"},
                    {"id": "research", "label": "🔍 Research", "description": "Read-only exploration, no modifications"},
                    {"id": "refactor", "label": "♻️ Refactor", "description": "Safe refactoring with auto-verify"},
                    {"id": "debug", "label": "🐛 Debug", "description": "Error-focused with diagnostics"},
                    {"id": "quick_fix", "label": "⚡ Quick Fix", "description": "Fast, minimal changes"},
                ],
            ),
            OnboardingStep(
                "permissions",
                "Tool Permissions",
                "Configure which tools require user approval.",
                [
                    {"id": "strict", "label": "Strict", "description": "All tools require approval"},
                    {"id": "balanced", "label": "Balanced (Recommended)", "description": "Read auto-approve, writes require approval"},
                    {"id": "permissive", "label": "Permissive", "description": "Auto-approve all except shell commands"},
                ],
            ),
            OnboardingStep(
                "features",
                "Enable Features",
                "Choose which agent features to enable.",
                [
                    {"id": "all", "label": "All features (Recommended)", "description": "Memory, knowledge, auto-commit, file watching"},
                    {"id": "essential", "label": "Essential only", "description": "Memory and knowledge base"},
                    {"id": "minimal", "label": "Minimal", "description": "No background features"},
                ],
            ),
        ]

    def get_steps(self) -> List[Dict[str, Any]]:
        """Get all steps for display."""
        return [s.to_dict() for s in self._steps]

    def set_selection(self, step_id: str, value: str) -> None:
        """Record a user selection for a step."""
        self._selections[step_id] = value
        for step in self._steps:
            if step.step_id == step_id:
                step.selected = value
                step.completed = True
                break

    def is_complete(self) -> bool:
        """Check if all steps have selections."""
        return all(s.completed for s in self._steps)

    def complete(self) -> OnboardingResult:
        """Execute the onboarding based on selections."""
        result = OnboardingResult()

        try:
            # Step 1: Workspace
            workspace = self.workspace or Path(self._selections.get("workspace", "."))
            if not workspace.exists():
                workspace.mkdir(parents=True, exist_ok=True)
            result.messages.append(f"✅ Workspace: {workspace}")

            # Step 2: Config
            config_mgr = ConfigManager(workspace)
            preset_id = self._selections.get("preset", "full_stack")
            permissions = self._selections.get("permissions", "balanced")
            features = self._selections.get("features", "all")

            # Apply selections to config
            config = config_mgr.config
            config.preset = preset_id

            if permissions == "strict":
                config.auto_approve_read = False
                config.auto_approve_write = False
                config.auto_approve_command = False
            elif permissions == "permissive":
                config.auto_approve_read = True
                config.auto_approve_write = True
                config.auto_approve_command = False
            # balanced = defaults

            if features == "all":
                config.memory_enabled = True
                config.knowledge_enabled = True
                config.audit_enabled = True
                config.self_improve_enabled = True
                config.auto_commit = True
                config.auto_test = True
            elif features == "essential":
                config.memory_enabled = True
                config.knowledge_enabled = True
                config.audit_enabled = False
                config.self_improve_enabled = False
                config.auto_commit = False
                config.auto_test = False
            else:  # minimal
                config.memory_enabled = False
                config.knowledge_enabled = False
                config.audit_enabled = False
                config.self_improve_enabled = False

            config_mgr.save()
            result.config = config
            result.messages.append(f"✅ Configuration saved")

            # Step 3: AGENTS.md
            try:
                gen = AgentsMdGenerator(workspace)
                gen.write(force=False)  # don't overwrite existing
                result.agents_md_generated = True
                result.messages.append("✅ AGENTS.md generated")
            except Exception as e:
                result.messages.append(f"⚠️ AGENTS.md generation skipped: {e}")

            # Step 4: Knowledge base
            try:
                kb = KnowledgeBase(workspace)
                count = kb.auto_populate()
                result.knowledge_populated = True
                result.messages.append(f"✅ Knowledge base: {count} entries")
            except Exception as e:
                result.messages.append(f"⚠️ Knowledge base skipped: {e}")

            # Step 5: Workspace analytics
            try:
                analytics = WorkspaceAnalytics(workspace)
                report = analytics.generate_report()
                health = report.get("health", {})
                score = health.get("score", 0)
                result.workspace_analyzed = True
                result.messages.append(f"✅ Workspace health: {score}/100")
                for issue in health.get("issues", [])[:3]:
                    result.messages.append(f"  ⚠️ {issue}")
            except Exception as e:
                result.messages.append(f"⚠️ Workspace analysis skipped: {e}")

            result.success = True
            result.messages.append("")
            result.messages.append("🎉 Setup complete! The agent is ready to use.")

        except Exception as e:
            result.errors.append(str(e))
            result.messages.append(f"❌ Setup failed: {e}")

        return result

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of current selections."""
        return {
            "steps": len(self._steps),
            "completed": sum(1 for s in self._steps if s.completed),
            "selections": dict(self._selections),
        }
