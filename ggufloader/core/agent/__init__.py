"""
Agent core - Pure agent engine, LangGraph agent, and sandboxed tool registry.
"""

from .agent_engine import AgentEngine, ApprovalCallback, extract_json
from .graph_agent import AgentCancelled, GraphAgent
from .history_processors import (
    HistoryProcessorPipeline,
    AgeBasedClipper,
    DeduplicationProcessor,
    SummaryInserter,
    create_default_pipeline,
)
from .tool_registry import ToolRegistry, create_default_registry, validate_tool_call
from .workspace_context import WorkspaceContext, PromptPrefixCache, WorkingMemory
from .delegation import ChildAgent, DelegationToken, should_delegate
from .plugin_manager import PluginManager
from .memory_persistence import MemoryPersistence, MemoryEntry
from .context_budget import ContextBudget
from .semantic_search import SemanticSearch, SearchResult
from .retry_handler import RetryHandler
from .checkpoint_manager import CheckpointManager
from .stream_handler import StreamHandler, StreamAbort
from .auto_commit import AutoCommit
from .auto_test import AutoTest
from .agents_md import AgentsMdGenerator
from .cost_estimator import CostEstimator
from .presets import AgentPreset, PresetManager
from .file_watcher import FileWatcher, FileChange
from .session_export import SessionExport
from .workspace_analytics import WorkspaceAnalytics
from .parallel_executor import ParallelExecutor, Task, TaskStatus
from .approval_manager import ApprovalManager, ApprovalDecision, RiskLevel
from .structured_output import StructuredOutput, SCHEMAS
from .knowledge_base import KnowledgeBase, KnowledgeEntry
from .mcp_client import MCPClient, MCPServer, MCPTool
from .health_monitor import HealthMonitor, HealthStatus
from .audit_log import AuditLog, AuditEntry, EventType
from .self_improve import SelfImprove, Correction
from .config_manager import ConfigManager, AgentConfig
from .onboarding import OnboardingWizard, OnboardingResult
from .capabilities import CapabilitiesRegistry, Capability, CapStatus
from .workflow_engine import WorkflowEngine, Workflow, WorkflowStep
from .hooks import Hooks, HookPoint, HookContext
from .response_cache import ResponseCache
from .workflow_templates import WorkflowTemplates
from .benchmark import BenchmarkSuite, BenchmarkTask, BenchmarkResult
from .error_patterns import ErrorPatternDetector, ErrorPattern
from .tool_analytics import ToolAnalytics, ToolCall
from .session_replay import SessionReplay, ReplaySession
from .rate_limiter import RateLimiter, TokenBucket
from .feature_index import get_all_features, get_feature_count, Feature
from .agent_bridge import AgentBridge
from .docs_generator import DocsGenerator
from .auto_setup import AutoSetup
from .config_migration import ConfigMigration, Migration
from .project_templates import ProjectTemplate, ProjectTemplateManager, TEMPLATES

__all__ = [
    "AgentEngine",
    "ApprovalCallback",
    "extract_json",
    "AgentCancelled",
    "GraphAgent",
    "HistoryProcessorPipeline",
    "AgeBasedClipper",
    "DeduplicationProcessor",
    "SummaryInserter",
    "create_default_pipeline",
    "ToolRegistry",
    "create_default_registry",
    "validate_tool_call",
    "WorkspaceContext",
    "PromptPrefixCache",
    "WorkingMemory",
    "ChildAgent",
    "DelegationToken",
    "should_delegate",
    "PluginManager",
    "MemoryPersistence",
    "MemoryEntry",
    "ContextBudget",
    "SemanticSearch",
    "SearchResult",
    "RetryHandler",
    "CheckpointManager",
    "StreamHandler",
    "StreamAbort",
    "AutoCommit",
    "AutoTest",
    "AgentsMdGenerator",
    "CostEstimator",
    "AgentPreset",
    "PresetManager",
    "FileWatcher",
    "FileChange",
    "SessionExport",
    "WorkspaceAnalytics",
    "ParallelExecutor",
    "Task",
    "TaskStatus",
    "ApprovalManager",
    "ApprovalDecision",
    "RiskLevel",
    "StructuredOutput",
    "SCHEMAS",
    "KnowledgeBase",
    "KnowledgeEntry",
    "MCPClient",
    "MCPServer",
    "MCPTool",
    "HealthMonitor",
    "HealthStatus",
    "AuditLog",
    "AuditEntry",
    "EventType",
    "SelfImprove",
    "Correction",
    "ConfigManager",
    "AgentConfig",
    "OnboardingWizard",
    "OnboardingResult",
    "CapabilitiesRegistry",
    "Capability",
    "CapStatus",
    "WorkflowEngine",
    "Workflow",
    "WorkflowStep",
    "Hooks",
    "HookPoint",
    "HookContext",
    "ResponseCache",
    "WorkflowTemplates",
    "BenchmarkSuite",
    "BenchmarkTask",
    "BenchmarkResult",
    "ErrorPatternDetector",
    "ErrorPattern",
    "ToolAnalytics",
    "ToolCall",
    "SessionReplay",
    "ReplaySession",
    "RateLimiter",
    "TokenBucket",
    "get_all_features",
    "get_feature_count",
    "Feature",
    "AgentBridge",
    "DocsGenerator",
    "AutoSetup",
    "ConfigMigration",
    "Migration",
    "ProjectTemplate",
    "ProjectTemplateManager",
    "TEMPLATES",
]
