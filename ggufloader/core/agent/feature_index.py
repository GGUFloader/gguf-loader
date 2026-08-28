"""
FeatureIndex - Complete catalog of all agent features.

Pattern from: Claude Code feature list + Aider docs.
A structured index of every feature in the agent system with:
- Feature name and description
- Module location
- Status (stable/experimental/deprecated)
- Dependencies
- Phase of implementation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Feature:
    """A single feature entry."""
    id: str
    name: str
    description: str
    module: str
    phase: int
    status: str = "stable"  # stable, experimental, planned
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "module": self.module,
            "phase": self.phase,
            "status": self.status,
            "dependencies": self.dependencies,
            "tags": self.tags,
        }


# Complete feature catalog
FEATURES: List[Feature] = [
    # Phase 1: UI Polish
    Feature("copy_button", "Copy Button", "Copy individual messages with hover icon",
            "widgets/chat_bubble.py", 1, tags=["ui"]),
    Feature("cost_counter", "Cost/Token Counter", "Sidebar display of tokens used and cost",
            "ui/sidebar_panel.py", 1, tags=["ui", "observability"]),
    Feature("truncation", "Truncatable Messages", "Expand/collapse long messages",
            "widgets/chat_bubble.py", 1, tags=["ui"]),
    Feature("export_md", "Export Conversation", "Export chat as markdown file",
            "ui/main_window.py", 1, tags=["ui"]),
    Feature("pending_state", "Pending/Error State", "Visual indicator while generating",
            "widgets/chat_bubble.py", 1, tags=["ui"]),
    Feature("delegation", "Child Agent Delegation", "Spawn read-only child for exploration",
            "core/agent/delegation.py", 1, tags=["agent"]),

    # Phase 2: Power Features
    Feature("autocomplete", "Tab Autocomplete", "Filename and command completion",
            "ui/agent_completer.py", 2, tags=["ui"]),
    Feature("slash_commands", "Slash Commands", "10 slash commands (/add, /drop, /clear, etc.)",
            "ui/slash_commands.py", 2, tags=["ui"]),
    Feature("diff_view", "Side-by-Side Diffs", "Visual diff display in tool cards",
            "widgets/tool_card.py", 2, tags=["ui"]),
    Feature("risk_badges", "Risk Badges", "Color-coded risk indicators on tool calls",
            "ui/agent_panel.py", 2, tags=["ui", "safety"]),
    Feature("turn_navigator", "Turn Navigator", "Vertical rail to jump between turns",
            "widgets/turn_navigator.py", 2, tags=["ui"]),
    Feature("disclosure_row", "DisclosureRow", "Reusable expand/collapse component",
            "widgets/disclosure_row.py", 2, tags=["ui"]),
    Feature("file_tree", "File Tree View", "Workspace file browser in sidebar",
            "widgets/file_tree.py", 2, tags=["ui"]),

    # Phase 3: Advanced UI
    Feature("voice_input", "Voice Input", "Whisper-based voice input",
            "services/voice_service.py", 3, tags=["ui"]),
    Feature("image_paste", "Image Paste", "Clipboard image detection and paste",
            "services/image_service.py", 3, tags=["ui"]),
    Feature("cache_hits", "Cache Hit Display", "Show prompt cache hit rate",
            "ui/sidebar_panel.py", 3, tags=["ui", "observability"]),
    Feature("ttft", "TTFT Display", "Time-to-first-token per step",
            "ui/chat_panel.py", 3, tags=["ui", "observability"]),

    # Phase 4: Session Management
    Feature("confirm_group", "ConfirmGroup Approval", "Allow/Deny/All/Skip batch approval",
            "ui/agent_panel.py", 4, tags=["ui", "safety"]),
    Feature("session_tabs", "Multi-Session Tabs", "Browser-style session tabs",
            "widgets/session_tabs.py", 4, tags=["ui"]),
    Feature("trajectory", "Trajectory Inspector", "Full execution timeline viewer",
            "widgets/trajectory_inspector.py", 4, tags=["ui", "debugging"]),

    # Phase 5: Infrastructure
    Feature("plugins", "Plugin Architecture", "Load custom tools from JSON/Python",
            "core/agent/plugin_manager.py", 5, tags=["extensibility"]),
    Feature("memory", "Memory Persistence", "Cross-session memory store",
            "core/agent/memory_persistence.py", 5, tags=["agent"]),
    Feature("context_budget", "Context Budget Manager", "Token tracking and compaction",
            "core/agent/context_budget.py", 5, tags=["agent"]),
    Feature("semantic_search", "Semantic File Search", "Regex, glob, definition search",
            "core/agent/semantic_search.py", 5, tags=["agent"]),

    # Phase 6: Reliability
    Feature("retry", "Auto-Retry", "Exponential backoff with circuit breaker",
            "core/agent/retry_handler.py", 6, tags=["reliability"]),
    Feature("checkpoints", "File Checkpoints", "Auto-backup before edits, undo support",
            "core/agent/checkpoint_manager.py", 6, tags=["reliability"]),
    Feature("perf_dashboard", "Performance Dashboard", "Real-time metrics display",
            "widgets/performance_dashboard.py", 6, tags=["ui", "observability"]),
    Feature("stream_repair", "Stream Response Repair", "Partial JSON repair and abort",
            "core/agent/stream_handler.py", 6, tags=["reliability"]),

    # Phase 7: Developer Workflow
    Feature("auto_commit", "Auto-Commit", "Git commits after file edits",
            "core/agent/auto_commit.py", 7, tags=["workflow"]),
    Feature("auto_test", "Auto-Test", "Run tests after code changes",
            "core/agent/auto_test.py", 7, tags=["workflow"]),
    Feature("agents_md", "AGENTS.md Generation", "Auto-generate project context",
            "core/agent/agents_md.py", 7, tags=["workflow"]),
    Feature("cost_est", "Cost Estimation", "Token cost and API comparison",
            "core/agent/cost_estimator.py", 7, tags=["observability"]),

    # Phase 8: Intelligence
    Feature("presets", "Agent Mode Presets", "6 predefined agent configurations",
            "core/agent/presets.py", 8, tags=["agent"]),
    Feature("file_watcher", "File Watcher", "Monitor workspace for external changes",
            "core/agent/file_watcher.py", 8, tags=["agent"]),
    Feature("session_export", "Session Export", "Export/import sessions as JSON/Markdown",
            "core/agent/session_export.py", 8, tags=["workflow"]),
    Feature("workspace_analytics", "Workspace Analytics", "Code metrics and project health",
            "core/agent/workspace_analytics.py", 8, tags=["observability"]),

    # Phase 9: Multi-Agent
    Feature("parallel", "Parallel Execution", "Multi-task concurrent agent runs",
            "core/agent/parallel_executor.py", 9, tags=["agent"]),
    Feature("approval_mgr", "Approval Manager", "Risk-based approval with rules",
            "core/agent/approval_manager.py", 9, tags=["safety"]),
    Feature("structured_output", "Structured Output", "JSON schema validation",
            "core/agent/structured_output.py", 9, tags=["agent"]),
    Feature("knowledge", "Knowledge Base", "Project-specific insight store",
            "core/agent/knowledge_base.py", 9, tags=["agent"]),

    # Phase 10: Integration
    Feature("mcp", "MCP Protocol Client", "Connect to external tool servers",
            "core/agent/mcp_client.py", 10, tags=["extensibility"]),
    Feature("health_monitor", "Health Monitor", "System diagnostics and metrics",
            "core/agent/health_monitor.py", 10, tags=["observability"]),
    Feature("audit_log", "Audit Log", "Full agent action traceability",
            "core/agent/audit_log.py", 10, tags=["debugging"]),
    Feature("self_improve", "Self-Improvement", "Learn from user corrections",
            "core/agent/self_improve.py", 10, tags=["agent"]),

    # Phase 11: Unification
    Feature("config_mgr", "Unified Configuration", "Single source of truth for all settings",
            "core/agent/config_manager.py", 11, tags=["infra"]),
    Feature("onboarding", "Onboarding Wizard", "First-time setup guide",
            "core/agent/onboarding.py", 11, tags=["ui"]),
    Feature("integration_tests", "Integration Tests", "19 end-to-end pipeline tests",
            "core/agent/integration_tests.py", 11, tags=["testing"]),
    Feature("capabilities", "Capabilities Registry", "Dynamic feature discovery and toggling",
            "core/agent/capabilities.py", 11, tags=["infra"]),

    # Phase 12: Workflow Engine
    Feature("workflow_engine", "Workflow Engine", "DAG-based multi-step orchestration",
            "core/agent/workflow_engine.py", 12, tags=["agent"]),
    Feature("hooks", "Lifecycle Hooks", "Custom callbacks at agent lifecycle points",
            "core/agent/hooks.py", 12, tags=["extensibility"]),
    Feature("response_cache", "Response Cache", "LRU cache for LLM responses",
            "core/agent/response_cache.py", 12, tags=["performance"]),
    Feature("workflow_templates", "Workflow Templates", "4 pre-built workflows",
            "core/agent/workflow_templates.py", 12, tags=["agent"]),

    # Phase 13: Benchmarking & Analytics
    Feature("benchmark", "Benchmark Runner", "Task scoring and performance reports",
            "core/agent/benchmark.py", 13, tags=["testing"]),
    Feature("error_patterns", "Error Pattern Detector", "Recurring error tracking",
            "core/agent/error_patterns.py", 13, tags=["debugging"]),
    Feature("tool_analytics", "Tool Usage Analytics", "Tool optimization suggestions",
            "core/agent/tool_analytics.py", 13, tags=["observability"]),
    Feature("session_replay", "Session Replay", "Step-by-step session replay",
            "core/agent/session_replay.py", 13, tags=["debugging"]),

    # Phase 14: UI Integration
    Feature("agent_bridge", "Agent Bridge", "Connect engine to MainWindow UI",
            "core/agent/agent_bridge.py", 14, tags=["infra"]),
    Feature("feature_dashboard", "Feature Dashboard", "Capability status and toggles",
            "widgets/feature_dashboard.py", 14, tags=["ui"]),
    Feature("rate_limiter", "Rate Limiter", "Token bucket for LLM and tool calls",
            "core/agent/rate_limiter.py", 14, tags=["reliability"]),
    Feature("feature_index", "Feature Index", "Complete feature catalog",
            "core/agent/feature_index.py", 14, tags=["infra"]),
]


def get_all_features() -> List[Feature]:
    return list(FEATURES)


def get_features_by_phase(phase: int) -> List[Feature]:
    return [f for f in FEATURES if f.phase == phase]


def get_features_by_tag(tag: str) -> List[Feature]:
    return [f for f in FEATURES if tag in f.tags]


def get_feature(feature_id: str) -> Optional[Feature]:
    for f in FEATURES:
        if f.id == feature_id:
            return f
    return None


def get_feature_count() -> Dict[str, int]:
    """Get feature counts by phase and tag."""
    by_phase: Dict[int, int] = {}
    by_tag: Dict[str, int] = {}
    for f in FEATURES:
        by_phase[f.phase] = by_phase.get(f.phase, 0) + 1
        for tag in f.tags:
            by_tag[tag] = by_tag.get(tag, 0) + 1
    return {"total": len(FEATURES), "by_phase": by_phase, "by_tag": by_tag}


def get_catalog_markdown() -> str:
    """Generate a markdown catalog of all features."""
    lines = ["# GGUFLoader Agent — Feature Catalog\n"]
    lines.append(f"**Total features: {len(FEATURES)}**\n")

    # Group by phase
    for phase in range(1, 15):
        phase_features = get_features_by_phase(phase)
        if not phase_features:
            continue
        lines.append(f"\n## Phase {phase} ({len(phase_features)} features)\n")
        lines.append("| Feature | Module | Tags |")
        lines.append("|---------|--------|------|")
        for f in phase_features:
            tags = ", ".join(f.tags)
            lines.append(f"| **{f.name}** | `{f.module}` | {tags} |")

    return "\n".join(lines)
