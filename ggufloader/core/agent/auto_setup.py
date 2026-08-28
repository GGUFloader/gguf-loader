"""
AutoSetup - First-launch detection and automatic configuration.

Pattern from: Claude Code's first-run + Aider's auto-setup.
Runs automatically on first launch to:
1. Detect if agent has been configured before
2. Analyze the workspace
3. Generate AGENTS.md
4. Populate knowledge base
5. Set optimal defaults based on project type
6. Create initial configuration

The setup runs silently in the background and only shows results
if something interesting was found.
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

# Setup marker file
SETUP_MARKER = ".ggufloader-setup-complete"


class AutoSetup:
    """Automatic first-launch setup.

    Usage:
        setup = AutoSetup(workspace_path)
        if setup.needs_setup():
            result = setup.run()
            if result["new_setup"]:
                print("Agent configured automatically!")
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._marker = workspace / SETUP_MARKER

    def needs_setup(self) -> bool:
        """Check if auto-setup is needed."""
        return not self._marker.exists()

    def run(self) -> Dict[str, Any]:
        """Run the auto-setup process."""
        result = {
            "new_setup": True,
            "steps": [],
            "config_created": False,
            "agents_md_generated": False,
            "knowledge_populated": False,
            "analytics": None,
        }

        start = time.monotonic()

        try:
            # Step 1: Analyze workspace
            analytics = WorkspaceAnalytics(self.workspace)
            report = analytics.generate_report()
            result["analytics"] = report
            result["steps"].append({
                "name": "workspace_analysis",
                "status": "ok",
                "detail": f"{report['metrics']['total_files']} files, "
                         f"{report['health']['score']}/100 health",
            })

            # Step 2: Create config with smart defaults
            config_mgr = ConfigManager(self.workspace)
            config = config_mgr.load()

            # Apply smart defaults based on project type
            project_type = self._detect_project_type(report)
            self._apply_smart_defaults(config, project_type, report)
            config_mgr.save()
            result["config_created"] = True
            result["steps"].append({
                "name": "config_setup",
                "status": "ok",
                "detail": f"Preset: {config.preset}, project type: {project_type}",
            })

            # Step 3: Generate AGENTS.md
            gen = AgentsMdGenerator(self.workspace)
            gen.write(force=False)
            result["agents_md_generated"] = True
            result["steps"].append({
                "name": "agents_md",
                "status": "ok",
                "detail": "Generated project context file",
            })

            # Step 4: Populate knowledge base
            kb = KnowledgeBase(self.workspace)
            count = kb.auto_populate()
            result["knowledge_populated"] = count > 0
            result["steps"].append({
                "name": "knowledge_base",
                "status": "ok",
                "detail": f"{count} entries populated",
            })

            # Step 5: Write setup marker
            self._write_marker()

        except Exception as e:
            logger.error("Auto-setup error: %s", e)
            result["steps"].append({
                "name": "error",
                "status": "error",
                "detail": str(e),
            })

        elapsed = time.monotonic() - start
        result["elapsed_ms"] = int(elapsed * 1000)
        return result

    def _detect_project_type(self, report: Dict[str, Any]) -> str:
        """Detect project type from analytics."""
        metrics = report.get("metrics", {})
        languages = metrics.get("languages", {})

        if "Python" in languages:
            return "python"
        elif "JavaScript" in languages or "TypeScript" in languages:
            return "javascript"
        elif "Rust" in languages:
            return "rust"
        elif "Go" in languages:
            return "go"
        elif "Java" in languages:
            return "java"
        return "unknown"

    def _apply_smart_defaults(self, config: AgentConfig, project_type: str,
                              report: Dict[str, Any]) -> None:
        """Apply smart defaults based on project analysis."""
        # Set preset based on project characteristics
        health = report.get("health", {})
        health_score = health.get("score", 50)

        if health_score < 50:
            config.preset = "quick_fix"
        elif project_type == "python":
            config.preset = "full_stack"
        else:
            config.preset = "full_stack"

        # Enable auto-test if tests exist
        has_tests = any(
            "test" in issue.lower() for issue in health.get("issues", [])
        )
        if not has_tests:
            config.auto_test = False

        # Enable auto-commit for git repos
        config.auto_commit = (self.workspace / ".git").exists()

        # Set context budget based on project size
        total_files = report.get("metrics", {}).get("total_files", 0)
        if total_files > 100:
            config.budget_tokens = 16384
        elif total_files > 30:
            config.budget_tokens = 8192
        else:
            config.budget_tokens = 4096

    def _write_marker(self) -> None:
        """Write the setup-complete marker."""
        try:
            self._marker.write_text(
                json.dumps({
                    "setup_time": time.time(),
                    "version": 1,
                }),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Failed to write setup marker: %s", e)

    def get_setup_info(self) -> Optional[Dict[str, Any]]:
        """Get info about when setup was last run."""
        if not self._marker.exists():
            return None
        try:
            return json.loads(self._marker.read_text(encoding="utf-8"))
        except Exception:
            return None

    def reset(self) -> None:
        """Reset setup marker to trigger re-setup."""
        if self._marker.exists():
            self._marker.unlink()
