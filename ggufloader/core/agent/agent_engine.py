"""
AgentEngine - Pure, testable agent loop for GGUF Loader.

The engine has no Qt and no knowledge of llama_cpp; it receives a plain
callable ``llm(prompt, max_tokens, temperature) -> str`` and emits
status/tool events through optional callbacks. Services layer runs it on
a worker thread and forwards events to the UI via Qt signals.

Flow per user message (multi-step, budgeted):
1. (optional) quick analysis for complex requests
2. loop up to ``max_steps`` times:
   a. ask the model for the next JSON action (tool_calls or answer),
      repairing malformed JSON up to ``json_retries`` times
   b. execute each tool call; failed calls get one corrective retry
   c. feed results back so the model can continue or finish
3. produce a natural-language final response
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .text_extract import TEXT_EXTENSIONS
from .tool_registry import ToolRegistry, GitTool, tool_content_for_context, validate_tool_call
from .workspace_context import WorkspaceContext, PromptPrefixCache, WorkingMemory
from .history_processors import (
    HistoryProcessorPipeline,
    SummaryInserter,
    create_default_pipeline,
)
from .delegation import ChildAgent, should_delegate
from .context_budget import ContextBudget, estimate_tokens
from .memory_persistence import MemoryPersistence
from .plugin_manager import PluginManager
from .retry_handler import RetryHandler
from .checkpoint_manager import CheckpointManager
from .stream_handler import StreamHandler, StreamAbort
from .auto_commit import AutoCommit
from .auto_test import AutoTest
from .agents_md import AgentsMdGenerator
from .cost_estimator import CostEstimator
from .parallel_executor import ParallelExecutor
from .approval_manager import ApprovalManager
from .structured_output import StructuredOutput, SCHEMAS
from .knowledge_base import KnowledgeBase
from .mcp_client import MCPClient
from .health_monitor import HealthMonitor
from .audit_log import AuditLog, EventType
from .self_improve import SelfImprove
from .config_manager import ConfigManager, AgentConfig
from .onboarding import OnboardingWizard
from .capabilities import CapabilitiesRegistry
from .workflow_engine import WorkflowEngine, Workflow
from .hooks import Hooks, HookPoint
from .response_cache import ResponseCache
from .workflow_templates import WorkflowTemplates
from .benchmark import BenchmarkSuite, BenchmarkTask
from .error_patterns import ErrorPatternDetector
from .tool_analytics import ToolAnalytics
from .session_replay import SessionReplay
from .rate_limiter import RateLimiter
from .feature_index import get_all_features, get_feature_count
from .docs_generator import DocsGenerator
from .auto_setup import AutoSetup
from .config_migration import ConfigMigration
from .project_templates import ProjectTemplateManager

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str], None]
ToolCallback = Callable[[Dict[str, Any]], None]
ApprovalCallback = Callable[[Dict[str, Any]], bool]  # (payload) -> approved?

# --- Risk levels for security assessment (from OpenHands) ---
RISK_LOW = "low"       # read-only tools: list, read, search
RISK_MEDIUM = "medium" # non-destructive writes: write_file, edit_file
RISK_HIGH = "high"     # destructive/external: run_command, run_python, git write ops




# Tools whose execution can change what a read-only tool would return.
# A repeat of an earlier call is only legitimate when one of these ran after it.
STATE_CHANGING_TOOLS = frozenset({"write_file", "edit_file", "run_command", "git"})

# Requests that ask for a folder-wide read/summary - the coverage guard applies.
SUMMARIZE_KEYWORDS = (
    "summarize", "summarise", "summary", "overview", "read all", "all files",
    "all the files", "tell me about the files", "tell me about this",
    "what's in", "what is in", "contents of", "the workspace", "the folder",
)

# Output clipping limits (chars) -- like Mini-Coding-Agent
CLIP_RECENT = 2000   # last 3 tool results
CLIP_OLD = 400       # older tool results
CLIP_STEP_LOG = 200  # compact summaries in step log

# --- Stuck detection constants (from OpenHands) ---
MAX_CONSECUTIVE_SAME_TOOL = 3    # stop if same tool called 3x in a row
MAX_CONSECUTIVE_FAILURES = 4     # stop if 4 failures in a row
MAX_DUPLICATE_SIGNATURES = 3     # stop if same signature called 3x

# --- Templated error messages (from SWE-agent) ---
ERROR_TEMPLATES = {
    "malformed_json": (
        "Your response was not valid JSON. Reply with ONLY a JSON object:\n"
        '{"reasoning": "...", "tool_calls": [...], "answer": "..."}'
    ),
    "missing_tool": (
        "You referenced a tool that doesn't exist. Available tools: {tools}.\n"
        "Check the tool name and try again."
    ),
    "missing_params": (
        "The tool call is missing required parameters. Check the schema and retry."
    ),
    "blocked_command": (
        "This command is blocked for safety. Try a different approach."
    ),
    "timeout": (
        "The command timed out. Try a simpler command or reduce scope."
    ),
    "syntax_error": (
        "The code has a syntax error. Fix it and retry."
    ),
    "stuck_loop": (
        "The agent appears stuck (repeating the same actions).\n"
        "Please describe what you want differently or try a new approach."
    ),
}

# File types the agent can actually read (text/Markdown + extracted PDF/DOCX).
READABLE_EXTS = TEXT_EXTENSIONS | frozenset({".pdf", ".docx"})

# Directories never walked when enumerating workspace files.
SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build",
    ".idea", ".vscode", ".gguf-undo",
})


def _normalize_rel_path(path: str) -> str:
    """Normalize a workspace-relative path for set comparison."""
    p = re.sub(r"^\./", "", str(path))
    return p.replace("\\", "/").lstrip("/").lower()


def workspace_readable_files(workspace: Path, limit: int = 60, max_bytes: int = 2_000_000) -> List[Path]:
    """Recursively list readable files under *workspace*, bounded for prompt cost."""
    files: List[Path] = []
    for root, dirs, names in os.walk(workspace):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in names:
            path = Path(root) / name
            if path.suffix.lower() not in READABLE_EXTS:
                continue
            try:
                if path.stat().st_size > max_bytes:
                    continue
            except OSError:
                continue
            files.append(path)
            if len(files) >= limit:
                return files
    return files


def summarize_directive(
    user_message: str,
    workspace: Path,
    executed_calls: List[Dict[str, Any]],
) -> Optional[str]:
    """Directive to read remaining files, or None when coverage is complete.

    Fires only for folder-wide summarize/overview requests (not when the
    message names a specific file) and only when readable files that the
    agent has not yet called ``read_file`` on still exist. Returns a short
    instruction listing those files so the loop can push the model to read
    them before answering.
    """
    text = user_message.lower()
    if not any(k in text for k in SUMMARIZE_KEYWORDS):
        return None
    # A specific filename in the request means the user targeted that file.
    if re.search(r"\b[\w.\-]+\.(?:md|txt|pdf|docx)\b", text):
        return None

    read_paths = set()
    for entry in executed_calls:
        if entry.get("tool") != "read_file":
            continue
        try:
            params = json.loads(entry.get("signature", "").split(":", 1)[1])
            raw_path = params.get("path", "")
        except Exception:  # noqa: BLE001 - defensive
            continue
        if raw_path:
            read_paths.add(_normalize_rel_path(raw_path))

    unread = []
    for path in workspace_readable_files(Path(workspace)):
        try:
            rel = path.relative_to(Path(workspace))
        except ValueError:
            rel = path
        rel_text = _normalize_rel_path(rel)
        if rel_text not in read_paths:
            unread.append(rel_text)
    if not unread:
        return None

    # Only suggest reading the most important files (max 5).
    # Priority: README/docs, entry points, config, then by path depth.
    PRIORITY_NAMES = {
        "readme.md", "readme.txt", "readme",
        "setup.py", "setup.cfg", "pyproject.toml",
        "package.json", "cargo.toml", "go.mod",
        "main.py", "app.py", "index.py", "index.ts", "index.js",
        "__init__.py", "__main__.py",
        "dockerfile", "docker-compose.yml", "makefile",
        "requirements.txt", "requirements-dev.txt",
        "tox.ini", "pytest.ini", "conftest.py",
    }

    def _priority(path_str: str) -> int:
        name = Path(path_str).name.lower()
        depth = len(Path(path_str).parts)
        if name in PRIORITY_NAMES:
            return 0
        if any(name.endswith(ext) for ext in ('.md', '.rst', '.txt')):
            return 1
        return depth  # shallower = higher priority

    unread.sort(key=_priority)
    shown = [Path(p).name for p in unread[:5]]
    tail = f" (and {len(unread) - 5} more)" if len(unread) > 5 else ""
    return (
        "The user asked to summarize the workspace. Read these key files to "
        f"understand the project: {', '.join(shown)}{tail}. "
        "Use read_file for each one. Do NOT try to read every file — just "
        "these key ones, then give your summary answer."
    )


def stale_repeat_signatures(calls: List[Dict[str, Any]], executed: List[Dict[str, Any]]) -> set:
    """Return signatures of proposed *calls* that already ran and are still valid.

    ``executed`` is a list of ``{"signature": str, "tool": str}`` in execution
    order. A proposed call is a stale repeat when the same signature already
    executed AND no state-changing tool ran after that execution (so the result
    the model already saw is still accurate). This is what stops a weak model
    from re-running the identical call every step while still allowing a
    legitimate re-list/re-read after a write or edit.
    """
    stale = set()
    for call in calls:
        try:
            signature = _signature_of(call)
        except Exception:  # noqa: BLE001 - defensive
            continue
        tool = call.get("tool", "")
        last_index = -1
        for i, entry in enumerate(executed):
            if entry.get("signature") == signature:
                last_index = i
        if last_index < 0:
            continue  # never ran - not a repeat
        if any(e.get("tool") in STATE_CHANGING_TOOLS for e in executed[last_index + 1:]):
            continue  # workspace may have changed since - re-run is legitimate
        stale.add(signature)
    return stale


def _signature_of(call: Dict[str, Any]) -> str:
    try:
        params = json.dumps(call.get("parameters", {}), sort_keys=True, ensure_ascii=False)
    except Exception:  # noqa: BLE001 - defensive
        params = str(call.get("parameters"))
    return f"{call.get('tool', '')}:{params}"


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
        for attempt in _json_repair_attempts(candidate):
            try:
                data = json.loads(attempt)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue
    return None


def _json_repair_attempts(text: str):
    """Yield *text*, then a version with bare backslashes escaped.

    Models frequently emit Windows paths like ``day4\\practice.md`` inside
    JSON strings; ``\\p`` is not a valid JSON escape, so the whole object
    fails to parse. Escaping those bare backslashes (``\\p`` -> ``\\\\p``)
    recovers the object without touching legitimate escapes.
    """
    yield text
    fixed = _escape_bare_backslashes(text)
    if fixed != text:
        yield fixed


def _escape_bare_backslashes(text: str) -> str:
    """Escape backslashes inside JSON strings that aren't structural escapes.

    Only ``\\"`` (quote), ``\\\\`` (backslash), and ``\\u`` (unicode) are kept
    as escapes. Everything else - including ``\\n``/``\\t``/``\\r`` - is a
    Windows path separator in model output and becomes a literal backslash.
    The pass only runs after the raw text failed to parse, so genuine JSON
    with valid escapes is never touched.
    """
    out: list[str] = []
    in_string = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            if in_string:
                nxt = text[i + 1] if i + 1 < n else ""
                if nxt in '"\\u':
                    out.append(ch)
                    out.append(nxt)
                    i += 1
                else:
                    out.append("\\\\")  # bare backslash -> escaped
            else:
                out.append(ch)
        elif ch == "\"":
            if in_string and _preceded_by_odd_backslashes(text, i):
                out.append(ch)  # escaped quote, still inside the string
            else:
                in_string = not in_string
                out.append(ch)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _preceded_by_odd_backslashes(text: str, index: int) -> bool:
    count = 0
    i = index - 1
    while i >= 0 and text[i] == "\\":
        count += 1
        i -= 1
    return count % 2 == 1


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
    """Runs the multi-step tool-use loop for a single user message."""

    def __init__(
        self,
        llm: Callable[..., str],
        workspace: str | Path,
        tools: Optional[ToolRegistry] = None,
        max_tokens: int = 2048,
        max_steps: int = 8,
        json_retries: int = 2,
        model_path: Optional[str] = None,
    ) -> None:
        self.llm = llm
        self.workspace = Path(workspace)
        self.tools = tools or ToolRegistry(self.workspace)
        # --- Model-specific router ---
        self._model_path = model_path
        self._model_profile: Dict[str, Any] = {}
        self._model_params: Dict[str, Any] = {}
        if model_path:
            try:
                self._model_profile = resolve_chat_config(model_path)
                self._model_params = self._model_profile.get("params", {})
                logger.info(
                    "Model router: family=%s params=%s",
                    self._model_profile.get("family", "unknown"),
                    self._model_params,
                )
            except Exception as e:
                logger.warning("Failed to load model profile: %s", e)
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.json_retries = json_retries
        self.conversation_history: List[Dict[str, str]] = []
        self._step_log: List[str] = []
        self._failed_signatures: Dict[str, int] = {}
        self._last_raw_response = ""
        self.max_directive_rounds = 2
        self._pending_directive = ""
        self._directive_rounds = 0
        # Workspace context and prompt prefix caching
        self._workspace_ctx = WorkspaceContext(self.workspace)
        self._prefix_cache = PromptPrefixCache()
        self._memory = WorkingMemory()
        self._on_approval: ApprovalCallback = lambda _payload: True
        # History processor pipeline (composable context management)
        self._history_pipeline = create_default_pipeline()
        self._summary_inserter: SummaryInserter = next(
            (p for p in self._history_pipeline.processors if isinstance(p, SummaryInserter)),
            SummaryInserter(),
        )
        # Reflection loop control
        self._reflection_enabled = True
        self._max_reflections = 2
        self._reflection_count = 0
        # --- Structured workflow phases ---
        self._current_phase = "idle"
        self._plan = []
        self._plan_index = 0
        self._verify_failures = []
        self._phase_log = []
        self._on_plan_update = lambda _data: None
        # --- Stuck detection state (from OpenHands) ---
        self._consecutive_failures = 0
        self._last_tool_name = ""
        self._same_tool_count = 0
        self._signature_counts: Dict[str, int] = {}
        # --- Cost tracking (from Aider) ---
        self._total_tokens = 0
        self._step_tokens = 0
        self._total_llm_calls = 0
        # --- Security risk cache ---
        self._risk_cache: Dict[str, str] = {}
        # Context budget manager (Pydantic AI Harness compaction pattern)
        self._context_budget = ContextBudget()
        # Persistent memory across sessions (Aider memory pattern)
        self._memory_store = MemoryPersistence(self.workspace)
        # Plugin manager for custom tools
        self._plugin_manager = PluginManager(self.workspace)
        # Retry handler with exponential backoff (OpenHands RetryAgent pattern)
        self._retry_handler = RetryHandler()
        # Checkpoint manager for undo support (Aider .gguf-undo pattern)
        self._checkpoint_mgr = CheckpointManager(self.workspace)
        # Stream handler for graceful abort and JSON repair
        self._stream_handler = StreamHandler()
        self._abort: Optional[StreamAbort] = None
        # Auto-commit after file edits (Aider pattern)
        self._auto_commit = AutoCommit(self.workspace)
        # Auto-test after code changes
        self._auto_test = AutoTest(self.workspace)
        # AGENTS.md generator
        self._agents_md = AgentsMdGenerator(self.workspace)
        # Cost estimator
        self._cost_estimator = CostEstimator()
        # Parallel executor for multi-task agent runs
        self._parallel_executor = ParallelExecutor(max_workers=3)
        # Approval manager with risk-based rules
        self._approval_mgr = ApprovalManager()
        # Structured output enforcer
        self._structured_output = StructuredOutput()
        # Project knowledge base
        self._knowledge = KnowledgeBase(self.workspace)
        # MCP client for external tool servers
        self._mcp_client = MCPClient(self.workspace)
        # Health monitor for system diagnostics
        self._health = HealthMonitor()
        # Audit log for full traceability
        self._audit = AuditLog(self.workspace)
        # Self-improvement from corrections
        self._self_improve = SelfImprove(self.workspace)
        # Unified configuration
        self._config_mgr = ConfigManager(self.workspace)
        # Capabilities registry
        self._capabilities = CapabilitiesRegistry()
        # Workflow engine for complex tasks
        self._workflow_engine = WorkflowEngine()
        self._workflow_templates = WorkflowTemplates(self._workflow_engine)
        # Lifecycle hooks
        self._hooks = Hooks()
        # Response cache
        self._response_cache = ResponseCache(workspace=self.workspace)
        # Benchmark suite
        self._benchmark = BenchmarkSuite(self.process)
        # Error pattern detector
        self._error_patterns = ErrorPatternDetector(self.workspace)
        # Tool usage analytics
        self._tool_analytics = ToolAnalytics()
        # Session replay
        self._replay = SessionReplay(self.workspace)
        # Rate limiter
        self._rate_limiter = RateLimiter()
        # Auto-setup for first launch
        self._auto_setup = AutoSetup(self.workspace)
        # Config migration for version upgrades
        self._config_migration = ConfigMigration(self.workspace)
        # Project templates
        self._project_templates = ProjectTemplateManager(self.workspace)

    # ------------------------------------------------------------------
    # Security risk assessment (from OpenHands)
    # ------------------------------------------------------------------
    def _assess_risk(self, tool_name: str, params: Dict[str, Any]) -> str:
        """Classify the risk level of a tool call.

        Returns RISK_LOW, RISK_MEDIUM, or RISK_HIGH.
        High-risk tools get extra scrutiny before execution.
        """
        cache_key = f"{tool_name}:{json.dumps(params, sort_keys=True)[:200]}"
        if cache_key in self._risk_cache:
            return self._risk_cache[cache_key]

        if tool_name in ("list_directory", "read_file", "search_files"):
            risk = RISK_LOW
        elif tool_name in ("write_file", "edit_file", "python_interpreter"):
            risk = RISK_MEDIUM
        elif tool_name == "run_command":
            cmd = (params.get("command") or "").lower()
            # Destructive commands are high risk
            destructive = ("rm ", "rmdir", "del ", "format ", "shutdown",
                           "reboot", "mkfs", "dd ", " > /dev/",
                           "git push", "git reset --hard", "git clean")
            risk = RISK_HIGH if any(d in cmd for d in destructive) else RISK_MEDIUM
        elif tool_name == "run_python":
            code = (params.get("code") or "").lower()
            risky = ("os.remove", "shutil.rmtree", "subprocess",
                     "__import__", "eval(", "exec(", "open(", "import os")
            risk = RISK_HIGH if any(r in code for r in risky) else RISK_MEDIUM
        elif tool_name == "git":
            args = params.get("args", [])
            if args and args[0] in GitTool.WRITE_OPS:
                risk = RISK_HIGH
            else:
                risk = RISK_LOW
        else:
            risk = RISK_MEDIUM

        self._risk_cache[cache_key] = risk
        return risk

    # ------------------------------------------------------------------
    # Syntax validation (from SWE-agent: bash -n)
    # ------------------------------------------------------------------
    def _validate_syntax(self, tool_name: str, params: Dict[str, Any]) -> Optional[str]:
        """Pre-execution syntax check. Returns error message or None.

        - Python code: ast.parse() check
        - Shell commands: basic pattern validation
        This catches errors before they waste execution time.
        """
        if tool_name == "run_python":
            code = params.get("code", "")
            if not code.strip():
                return "Empty Python code"
            try:
                ast.parse(code)
            except SyntaxError as e:
                return f"Python syntax error at line {e.lineno}: {e.msg}"
        elif tool_name == "run_command":
            cmd = params.get("command", "")
            if not cmd.strip():
                return "Empty command"
            # Check for obviously broken commands
            if cmd.count("\'") % 2 != 0:
                return "Unmatched single quotes in command"
            if cmd.count('\"') % 2 != 0:
                return "Unmatched double quotes in command"
        return None

    # ------------------------------------------------------------------
    # Stuck detection (from OpenHands)
    # ------------------------------------------------------------------
    def _check_stuck(self, call: Dict[str, Any]) -> Optional[str]:
        """Detect if the agent is stuck in a loop. Returns error or None."""
        tool_name = call.get("tool", "")
        sig = self._signature(call)

        # Track consecutive same-tool calls
        if tool_name == self._last_tool_name:
            self._same_tool_count += 1
        else:
            self._same_tool_count = 1
            self._last_tool_name = tool_name

        if self._same_tool_count >= MAX_CONSECUTIVE_SAME_TOOL:
            return (
                f"Stuck detection: '{tool_name}' called {self._same_tool_count} times in a row. "
                "Try a different tool or approach."
            )

        # Track signature duplicates
        self._signature_counts[sig] = self._signature_counts.get(sig, 0) + 1
        if self._signature_counts[sig] >= MAX_DUPLICATE_SIGNATURES:
            return (
                f"Stuck detection: identical call attempted {self._signature_counts[sig]} times. "
                "This approach is not working. Try something different."
            )

        # Track consecutive failures
        if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            return (
                f"Stuck detection: {self._consecutive_failures} consecutive failures. "
                "The agent is going in circles. Please provide guidance or try a new approach."
            )

        return None

    def _record_success(self) -> None:
        """Reset failure counters on success."""
        self._consecutive_failures = 0

    def _record_failure(self) -> None:
        """Increment failure counter."""
        self._consecutive_failures += 1

    # ------------------------------------------------------------------
    # Post-edit verification (from Aider auto-lint)
    # ------------------------------------------------------------------
    def _verify_post_edit(self, call: Dict[str, Any], result: Dict[str, Any]) -> Optional[str]:
        """After a file edit, verify the result is syntactically valid.

        Returns a warning message if verification fails, or None if OK.
        This prevents compounding errors from bad edits.
        """
        if result.get("status") != "success":
            return None
        tool_name = call.get("tool", "")
        params = call.get("parameters", {})

        if tool_name == "write_file":
            path = params.get("path", "")
            content = params.get("content", "")
            if path.endswith(".py") and content.strip():
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    return f"Warning: {path} has syntax error at line {e.lineno}: {e.msg}. The model should fix this."
        elif tool_name == "edit_file":
            path = params.get("path", "")
            if path.endswith(".py"):
                # Re-read the file after edit to verify
                try:
                    resolved = self.tools.resolve(path)
                    if resolved.is_file():
                        source = resolved.read_text(encoding="utf-8")
                        ast.parse(source)
                except (SyntaxError, OSError) as e:
                    return f"Warning: {path} has syntax error after edit: {e}. The model should fix this."
        return None

    # ------------------------------------------------------------------
    # Reflection loop
    # ------------------------------------------------------------------
    def _should_reflect(self, action: Dict[str, Any]) -> bool:
        """Check if the model requested a reflection before answering.

        A reflection is triggered when the action contains "reflect": true
        with a non-empty "reflect_reason". The model is saying: "I'm not
        confident in my answer; let me check something first."
        """
        if not self._reflection_enabled:
            return False
        if self._reflection_count >= self._max_reflections:
            return False
        if not action.get("reflect"):
            return False
        reason = (action.get("reflect_reason") or "").strip()
        return bool(reason)

    def _execute_reflection(
        self,
        user_message: str,
        reason: str,
        on_status: StatusCallback,
        on_tool: Optional[ToolCallback],
    ) -> Optional[str]:
        """Execute a reflection step: model checks its work before answering.

        Returns the final answer after reflection, or None if the model
        could not produce a valid response.
        """
        self._reflection_count += 1
        on_status(f"🔍 Reflecting: {reason}")

        # Ask the model to verify the claim using tools
        reflect_prompt = (
            f"User asked: {user_message}\n\n"
            f"You wanted to verify: {reason}\n\n"
            f"Use tools to verify this. When done, produce your final JSON\n"
            f"response with the verified answer in 'answer'.\n\n"
            f"Assistant:"
        )

        for _step in range(3):  # max 3 reflection tool steps
            raw = self._ask(reflect_prompt)
            data = extract_json(raw)
            if data is None:
                return None

            calls = [
                c for c in (data.get("tool_calls") or [])
                if isinstance(c, dict) and c.get("tool")
            ]
            if not calls:
                return (data.get("answer") or "").strip() or None

            for call in calls:
                result = self.tools.execute(call.get("tool", ""), call.get("parameters", {}))
                self._log_tool_result(call, result)
                on_status(f"  ✓ {self._describe(call)}")
                if on_tool:
                    on_tool(result)

        return None

    def _emit_plan_update(self, step_num: int) -> None:
        try:
            self._on_plan_update({
                "phase": self._current_phase,
                "plan": [dict(s) for s in self._plan],
                "step": step_num,
                "status": self._plan[step_num - 1]["status"] if step_num <= len(self._plan) else "unknown",
            })
        except Exception:
            pass

    def _phase_goal(self, user_message: str, status: StatusCallback) -> str:
        self._current_phase = "goal"
        status("Understanding your request...")
        is_simple = len(user_message.split()) <= 30 and not any(
            w in user_message.lower()
            for w in ("complex", "multiple", "several", "build", "create system", "refactor")
        )
        if is_simple:
            goal = user_message.strip()
        else:
            goal = self._ask(f"User request: {user_message}\n\nState the goal as a single sentence.").strip()
            if not goal:
                goal = user_message[:200]
        status(f"Goal: {goal}")
        self._phase_log.append(f"GOAL: {goal}")
        return goal

    def _phase_plan(self, goal: str, user_message: str, status: StatusCallback) -> list:
        self._current_phase = "plan"
        status("Creating plan...")
        is_simple = len(user_message.split()) <= 30
        if is_simple:
            plan = [{"step": 1, "description": goal[:200], "tool": None, "verify": "Check", "status": "pending", "result": None}]
        else:
            plan_prompt = f"Goal: {goal}\nOriginal request: {user_message}\nAvailable tools: {self.tools.names()}\n\nCreate a step-by-step plan. Reply with ONLY a JSON array:\n"
            raw = self._ask(plan_prompt)
            plan = self._parse_plan(raw, goal)
        self._plan = plan
        self._plan_index = 0
        if plan:
            status(f"Plan ({len(plan)} steps):")
            for item in plan:
                status(f"  {item['step']}. {item['description']}")
            self._phase_log.append(f"PLAN: {len(plan)} steps")
        return plan

    def _phase_execute(self, user_message: str, goal: str, status: StatusCallback, on_tool) -> list:
        self._current_phase = "execute"
        tool_results = []
        if self._plan:
            for plan_step in self._plan:
                if self._abort and self._abort.is_aborted:
                    status("Aborted")
                    break
                step_num = plan_step["step"]
                desc = plan_step["description"]
                status(f">>> Step {step_num}/{len(self._plan)}: {desc}")
                plan_step["status"] = "running"
                self._emit_plan_update(step_num)
                step_prompt = f"Goal: {goal}\nCurrent step: {step_num}. {desc}\nTool results so far:\n"
                for tr in tool_results[-5:]:
                    outcome = "success" if tr.get("status") == "success" else "error"
                    step_prompt += f"  - {tr.get('tool_name', '?')}: {outcome}\n"
                step_prompt += "\nExecute this step. Reply with ONLY JSON with tool_calls.\n"
                action = self._get_action_for_step(step_prompt, status)
                if action is None:
                    plan_step["status"] = "failed"
                    plan_step["result"] = "Could not generate action"
                    self._emit_plan_update(step_num)
                    continue
                calls = [x for x in (action.get("tool_calls") or []) if isinstance(x, dict) and x.get("tool")]
                if not calls:
                    plan_step["status"] = "done"
                    plan_step["result"] = action.get("answer", "Completed")
                    self._emit_plan_update(step_num)
                    continue
                step_ok = True
                for call in calls:
                    if self._abort and self._abort.is_aborted:
                        break
                    risk = self._assess_risk(call.get("tool", ""), call.get("parameters", {}))
                    if risk == RISK_HIGH:
                        status(f"  High-risk: {self._describe(call)}")
                    if self.tools.requires_approval(call.get("tool", ""), call.get("parameters", {})):
                        if not self._on_approval({"type": "approval", "call": call, "risk": risk}):
                            status("  Approval denied")
                            step_ok = False
                            continue
                    self._checkpoint_mgr.backup(call.get("tool", ""), call.get("parameters", {}))
                    result = self.tools.execute(call.get("tool", ""), call.get("parameters", ""))
                    self._executed_calls.append({"signature": self._signature(call), "tool": call.get("tool", "")})
                    tool_results.append(result)
                    if on_tool:
                        on_tool(result)
                    self._log_tool_result(call, result)
                    if result.get("status") == "success":
                        status(f"  OK: {self._summarize_result(result)}")
                        self._record_success()
                    else:
                        status(f"  Failed: {result.get('error', 'Unknown error')}")
                        self._record_failure()
                        step_ok = False
                plan_step["status"] = "done" if step_ok else "failed"
                self._emit_plan_update(step_num)
        else:
            tool_results = self._execute_reactive_loop(user_message, status, on_tool)
        return tool_results

    def _get_action_for_step(self, prompt: str, status: StatusCallback):
        full_prompt = self._get_prefix() + "\n\n" + prompt + "\n\nAssistant:"
        for _attempt in range(self.json_retries + 1):
            raw = self._ask(full_prompt)
            self._last_raw_response = raw
            data = extract_json(raw)
            if data is not None:
                return data
            full_prompt += "\nYour response was not valid JSON. Reply with ONLY a JSON object:\n"
        return None

    def _phase_verify(self, tool_results: list, status: StatusCallback) -> bool:
        self._current_phase = "verify"
        status("Verifying results...")
        all_ok = True
        for result in tool_results:
            if result.get("status") != "success":
                all_ok = False
                self._verify_failures.append(result)
        if self._plan:
            done = sum(1 for s in self._plan if s["status"] == "done")
            failed = sum(1 for s in self._plan if s["status"] == "failed")
            status(f"Plan: {done} done, {failed} failed")
        self._phase_log.append(f"VERIFY: {'OK' if all_ok else 'failures'}")
        return all_ok

    def _phase_continue(self, all_ok: bool, user_message: str, goal: str, tool_results: list, status: StatusCallback) -> bool:
        self._current_phase = "continue"
        if all_ok and self._plan:
            pending = [s for s in self._plan if s["status"] == "pending"]
            if not pending:
                status("All plan steps completed")
                return False
        return False

    def _phase_finish(self, user_message: str, goal: str, tool_results: list, status: StatusCallback) -> str:
        self._current_phase = "finish"
        status("Preparing final answer...")
        context = [f"Goal: {goal}", f"User asked: {user_message}", "", "Operations completed:"]
        for result in tool_results:
            tool = result.get("tool_name", "unknown")
            content = tool_content_for_context(result, max_chars=500) if result.get("status") == "success" else result.get("error", "Failed")
            marker = "OK" if result.get("status") == "success" else "FAIL"
            context.append(f"  [{marker}] {tool}: {content or 'Done'}")
        if self._plan:
            context.append("\nPlan progress:")
            for s in self._plan:
                context.append(f"  [{s['status']}] {s['step']}. {s['description']}")
        context.append("\nProvide a clear response summarizing what was done.")
        answer = self._ask("\n".join(context)).strip()
        if answer:
            parsed = extract_json(answer)
            if parsed and isinstance(parsed, dict) and parsed.get("answer"):
                answer = parsed["answer"].strip()
        if not answer:
            success = sum(1 for r in tool_results if r.get("status") == "success")
            answer = f"Completed {success}/{len(tool_results)} operations."
        self._phase_log.append(f"FINISH: {len(tool_results)} operations")
        self._current_phase = "idle"
        return answer

    # ------------------------------------------------------------------
    # Background summarization
    # ------------------------------------------------------------------
    def _maybe_summarize(self) -> None:
        """Check if conversation is too long and trigger summarization.

        This runs inline (not threaded) to keep things simple. For a
        real implementation, this would run in a background thread.
        """
        total_chars = sum(len(str(m.get("content", ""))) for m in self.conversation_history)
        if total_chars <= self._summary_inserter.threshold_chars:
            return
        # Build a summary of the conversation so far
        summary_parts = []
        for msg in self.conversation_history:
            role = msg.get("role", "")
            content = (msg.get("content") or "")[:300]
            if content:
                summary_parts.append(f"{role}: {content}")
        summary = "\n".join(summary_parts[-8:])
        self._summary_inserter.set_summary(summary)
        logger.info("Background summarization triggered (%d chars)", total_chars)

    def _inject_summary(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run the conversation history through the processor pipeline."""
        self._maybe_summarize()
        processed = self._history_pipeline(history)
        return processed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def process(
        self,
        user_message: str,
        on_status: Optional[StatusCallback] = None,
        on_tool: Optional[ToolCallback] = None,
        on_approval: Optional[ApprovalCallback] = None,
        on_plan_update: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Process *user_message* and return ``{"response": str, "tool_results": [...]}``."""
        self.conversation_history.append({"role": "user", "content": user_message})
        status = on_status or (lambda _msg: None)
        self._on_plan_update = on_plan_update or (lambda _data: None)
        self._step_log = []
        self._failed_signatures = {}
        self._plan = []
        self._plan_index = 0
        self._verify_failures = []
        self._phase_log = []
        self._current_phase = "idle"
        self._executed_calls: List[Dict[str, Any]] = []
        self._pending_directive = ""
        self._directive_rounds = 0

        # Context budget check — compact history if needed
        strategy = self._context_budget.check_budget(self.conversation_history)
        if strategy != "ok":
            status(f"📦 Compacting context ({strategy})...")
            self._context_budget.compact(self.conversation_history)

        # Inject memory context if available
        memory_ctx = self._memory_store.get_context(max_chars=1500)
        if memory_ctx:
            self.conversation_history.insert(0, {
                "role": "system",
                "content": memory_ctx,
            })

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

            # 1b. Delegation: spawn read-only child for exploration (Mini-Coding pattern)
            if should_delegate(user_message):
                status("🔍 Spawning exploration agent...")
                child = ChildAgent(self.llm, self.workspace, self.tools, max_tokens=512)
                delegation_result = child.explore(user_message)
                if delegation_result.summary:
                    status(f"📋 Exploration complete ({len(delegation_result.tools_used)} tools used)")
                    # Inject the child's findings into context for the main agent
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": f"[Delegation result]: {delegation_result.summary}"
                    })
                    # Continue with main agent to formulate the answer

            tool_results: List[Dict[str, Any]] = []
            final_answer: Optional[str] = None

            # 2. Multi-step loop with a hard budget
            for step in range(1, self.max_steps + 1):
                # Check for graceful abort
                if self._abort and self._abort.is_aborted:
                    status(f"⏹ Aborted: {self._abort.reason}")
                    break

                if step > 1:
                    status(f"▶ Step {step}/{self.max_steps}")

                action = self._request_action()
                if action is None:
                    # Model could not produce valid JSON at all - fall back to chat
                    final_answer = self._last_raw_response or ""
                    if self._issue_directive(user_message, status):
                        continue
                    break

                reasoning = (action.get("reasoning") or "").strip()
                if reasoning:
                    status(f"💭 {reasoning}")

                calls = [
                    c for c in (action.get("tool_calls") or [])
                    if isinstance(c, dict) and c.get("tool")
                ]
                if not calls:
                    final_answer = self._finish(user_message, action, tool_results)
                    if self._issue_directive(user_message, status):
                        continue
                    # Check for reflection request
                    if self._should_reflect(action):
                        reflect_answer = self._execute_reflection(
                            user_message,
                            (action.get("reflect_reason") or "").strip(),
                            status, on_tool,
                        )
                        if reflect_answer:
                            final_answer = reflect_answer
                    break

                # Drop repeats of calls that already ran with a still-valid
                # result. If the model proposes nothing but stale repeats, wrap
                # up with its answer (or a synthesized one) instead of burning
                # the step budget on the same call.
                stale = stale_repeat_signatures(calls, self._executed_calls)
                new_calls = [c for c in calls if self._signature(c) not in stale]
                if not new_calls:
                    answer = (action.get("answer") or "").strip()
                    final_answer = answer or self._final_response(user_message, tool_results)
                    if self._issue_directive(user_message, status):
                        continue
                    break
                calls = new_calls

                self._announce_plan(calls, status)
                failures: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
                for index, call in enumerate(calls, 1):
                    if len(calls) > 1:
                        status(f"[{index}/{len(calls)}] {self._describe(call)}")
                    signature = self._signature(call)
                    if self._failed_signatures.get(signature, 0) >= 2:
                        status(f"  ⏭ Skipping repeated failing call: {self._describe(call)}")
                        continue
                    # --- Stuck detection (from OpenHands) ---
                    stuck_msg = self._check_stuck(call)
                    if stuck_msg:
                        status(f"  ⚠ {stuck_msg}")
                        self._consecutive_failures = MAX_CONSECUTIVE_FAILURES
                        failures.append((call, {"status": "error", "error": stuck_msg, "tool_name": call.get("tool", "")}))
                        break

                    # Validate tool call before execution
                    validation_error = validate_tool_call(call, self.tools)
                    if validation_error:
                        status(f"  ✗ Invalid call: {validation_error}")
                        self._failed_signatures[signature] = self._failed_signatures.get(signature, 0) + 1
                        self._record_failure()
                        failures.append((call, {"status": "error", "error": validation_error, "tool_name": call.get("tool", "")}))
                        continue

                    # --- Syntax validation (from SWE-agent bash -n) ---
                    syntax_error = self._validate_syntax(call.get("tool", ""), call.get("parameters", {}))
                    if syntax_error:
                        status(f"  ✗ Syntax error: {syntax_error}")
                        self._failed_signatures[signature] = self._failed_signatures.get(signature, 0) + 1
                        self._record_failure()
                        failures.append((call, {"status": "error", "error": syntax_error, "tool_name": call.get("tool", "")}))
                        continue

                    # --- Security risk assessment (from OpenHands) ---
                    risk = self._assess_risk(call.get("tool", ""), call.get("parameters", {}))
                    if risk == RISK_HIGH:
                        status(f"  🔴 High-risk action: {self._describe(call)}")

                    # Check approval before executing
                    if self.tools.requires_approval(call.get("tool", ""), call.get("parameters", {})):
                        approval_payload = {
                            "type": "approval",
                            "call": call,
                            "description": self._describe(call),
                            "workspace": str(self.workspace),
                            "risk": risk,
                        }
                        status(f"  🔐 Approval needed: {self._describe(call)}")
                        if not self._on_approval(approval_payload):
                            result = {"status": "error", "error": "Approval denied by the user",
                                      "tool_name": call.get("tool", "")}
                            self._executed_calls.append(
                                {"signature": signature, "tool": call.get("tool", "")}
                            )
                            tool_results.append(result)
                            if on_tool:
                                on_tool(result)
                            status(f"  ✗ Approval denied")
                            self._record_failure()
                            continue

                    # Backup file before modification (Aider undo pattern)
                    self._checkpoint_mgr.backup(
                        call.get("tool", ""), call.get("parameters", {}))
                    result = self.tools.execute(call.get("tool", ""), call.get("parameters", {}))
                    self._executed_calls.append(
                        {"signature": signature, "tool": call.get("tool", "")}
                    )
                    tool_results.append(result)
                    if on_tool:
                        on_tool(result)
                    self._log_tool_result(call, result)

                    if result.get("status") == "success":
                        status(f"  ✓ {self._summarize_result(result)}")
                        self._record_success()

                        # --- Post-edit verification (from Aider auto-lint) ---
                        verify_warn = self._verify_post_edit(call, result)
                        if verify_warn:
                            status(f"  ⚠ {verify_warn}")
                    else:
                        status(f"  ✗ {result.get('error', 'Unknown error')}")
                        self._failed_signatures[signature] = self._failed_signatures.get(signature, 0) + 1
                        self._record_failure()
                        failures.append((call, result))

                # 3. One corrective retry per failed call
                for failed_call, failed_result in failures:
                    fixed = self._request_fix(failed_call, failed_result)
                    if fixed is None:
                        continue
                    self._executed_calls.append(
                        {"signature": self._signature(failed_call), "tool": failed_call.get("tool", "")}
                    )
                    tool_results.append(fixed)
                    if on_tool:
                        on_tool(fixed)
                    self._log_tool_result(failed_call, fixed)
                    if fixed.get("status") == "success":
                        status(f"  ✓ retry succeeded: {self._summarize_result(fixed)}")
                    else:
                        status(f"  ✗ retry failed: {fixed.get('error', 'Unknown error')}")
                # Loop continues: results are in context, the model decides the next action.

            if final_answer is None:
                final_answer = self._final_response(user_message, tool_results)

            self.conversation_history.append({"role": "assistant", "content": final_answer})

            # Store useful facts from the session in persistent memory
            if tool_results:
                self._store_session_memories(user_message, final_answer, tool_results)

            return {"response": final_answer, "tool_results": tool_results, "plan": self._plan, "phase_log": self._phase_log}

        except Exception as e:
            logger.error("Agent error: %s", e)
            return {"response": f"Error: {e}", "tool_results": []}

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------
    def _system_prompt(self) -> str:
        """Build system prompt with workspace context and AGENTS.md injection."""
        # If model doesn't support system prompts, use a minimal prompt
        if self._model_profile and not self._model_profile.get("supports_system_prompt", True):
            base = "You are a helpful AI assistant. Help with documents."
        else:
            # Use router-provided prompt from model_families.json
            base = self._model_profile.get("system_prompt", "") if self._model_profile else ""
            if not base:
                base = "You are a helpful file assistant. Read files and help users."
        base = base.replace("__WORKSPACE__", str(self.workspace))
        workspace_ctx = self._workspace_ctx.build_context()
        if workspace_ctx:
            base += "\n\n" + workspace_ctx
        return base

    def _get_prefix(self) -> str:
        """Get the cached prompt prefix (system prompt + tools + workspace context)."""
        return self._prefix_cache.get_prefix(
            system_prompt=self._system_prompt(),
            workspace_context="",  # already embedded in system_prompt
            tool_descriptions=self.tools.describe(),
        )

    def _build_action_prompt(self, repair: str = "") -> str:
        """Prompt asking the model for the next JSON action.

        Uses cached prefix for the stable part (system prompt + tools),
        only rebuilds the variable suffix (transcript + repair + directive).
        """
        # Use cached prefix for the stable portion
        prefix = self._get_prefix()
        parts = [prefix, ""]
        for msg in self.conversation_history[-4:]:
            parts.append(f"{msg['role'].capitalize()}: {msg['content']}")
            parts.append("")
        if self._step_log:
            parts.append("Tool results:")
            parts.extend(self._step_log[-10:])
            parts.append("")
        if repair:
            parts.append(
                "Your previous response was not valid JSON. Reply with ONLY the JSON "
                "object described above - no markdown fences, no extra text."
            )
            parts.append("")
            parts.append("Your previous (invalid) response was:")
            parts.append(repair[:1500])
            parts.append("")
        # Include working memory for task context
        memory_text = self._memory.text()
        if self._memory.task:
            parts.append(memory_text)
            parts.append("")
        if self._pending_directive:
            parts.append("IMPORTANT - follow this instruction before replying:")
            parts.append(self._pending_directive)
            parts.append("")
        parts.append("Assistant:")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------
    def _ask(self, prompt: str) -> str:
        try:
            # Use retry handler with exponential backoff
            result = self._retry_handler.retry_llm(
                self.llm, args=(prompt,),
                kwargs={
                    "max_tokens": self.max_tokens,
                    "temperature": self._model_params.get("temperature", 0.1),
                },
            )
            # Track token usage (rough estimate: 1 token ~ 4 chars)
            self._total_llm_calls += 1
            self._step_tokens += len(result) // 4 if result else 0
            self._total_tokens += len(result) // 4 if result else 0
            return result or ""
        except Exception as e:
            logger.error("LLM call failed after retries: %s", e)
            return ""

    def _request_action(self) -> Optional[Dict[str, Any]]:
        """Ask for the next action, repairing malformed JSON up to json_retries times."""
        prompt = self._build_action_prompt()
        for _attempt in range(self.json_retries + 1):
            raw = self._ask(prompt)
            self._last_raw_response = raw
            data = extract_json(raw)
            if data is not None:
                return data
            prompt = self._build_action_prompt(repair=raw)
        return None

    def _request_fix(self, failed_call: Dict[str, Any], failed_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Ask the model to correct a failed tool call; execute the corrected call.

        Returns the corrected tool result, or None when the model supplies
        no replacement call.
        """
        tool_name = failed_call.get("tool", "")
        params = failed_call.get("parameters", {})
        error = failed_result.get("error", "Unknown error")
        prompt = (
            self._system_prompt() + "\n\n"
            "A tool call just failed. Correct the parameters and retry, or decide it cannot be done.\n\n"
            f"Failed tool: {tool_name}\n"
            f"Parameters used: {json.dumps(params, ensure_ascii=False)[:800]}\n"
            f"Error: {error}\n\n"
            f'Respond with ONLY the JSON object. Include at most one corrected tool_calls entry for "{tool_name}" '
            '(or "tool_calls": [] if the task cannot be completed with corrected parameters).\n'
            "Assistant:"
        )
        raw = self._ask(prompt)
        self._last_raw_response = raw
        data = extract_json(raw)
        if data is None:
            return None
        calls = [
            c for c in (data.get("tool_calls") or [])
            if isinstance(c, dict) and c.get("tool")
        ]
        if not calls:
            return None
        call = next((c for c in calls if c.get("tool") == tool_name), calls[0])
        return self.tools.execute(call.get("tool", ""), call.get("parameters", {}))

    # ------------------------------------------------------------------
    # Loop helpers
    # ------------------------------------------------------------------
    def _issue_directive(self, user_message: str, status: StatusCallback) -> bool:
        """Queue a read-coverage directive when summarize files remain unread.

        Returns True (and the loop continues) when the user asked for a
        folder-wide summary and readable files haven't been read yet; the
        next action prompt then tells the model to read them. The directive
        is surfaced to the UI as a status line. Capped so a stubborn model
        can't loop forever.
        """
        if self._directive_rounds >= self.max_directive_rounds:
            return False
        directive = summarize_directive(user_message, self.workspace, self._executed_calls)
        if not directive:
            self._pending_directive = ""
            return False
        self._pending_directive = directive
        self._directive_rounds += 1
        status("📖 Reading remaining files…")
        status(directive)
        return True

    def _finish(self, user_message: str, action: Dict[str, Any], tool_results: List[Dict[str, Any]]) -> str:
        answer = (action.get("answer") or "").strip()
        if answer:
            return answer
        if tool_results:
            return self._final_response(user_message, tool_results)
        return self._last_raw_response or "No further action needed."

    def _signature(self, call: Dict[str, Any]) -> str:
        try:
            params = json.dumps(call.get("parameters", {}), sort_keys=True, ensure_ascii=False)
        except Exception:  # noqa: BLE001 - defensive
            params = str(call.get("parameters"))
        return f"{call.get('tool', '')}:{params}"

    def _log_tool_result(self, call: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Append a compact tool outcome to the session log fed back to the model.

        The line format mirrors the few-shot example ("Tool result for <tool>:")
        so the model recognizes results it has already seen. Older entries are
        clipped more aggressively to prevent context flooding.
        """
        tool = call.get("tool", "unknown")
        outcome = "success" if result.get("status") == "success" else "error"
        content = tool_content_for_context(result)
        if content is not None:
            # Clip by age: recent results get more space
            recent_count = sum(1 for e in self._step_log[-3:] if e.startswith("Tool result"))
            limit = CLIP_RECENT if recent_count < 3 else CLIP_OLD
            summary = content[:limit] + ("..." if len(content) > limit else "")
        else:
            summary = self._summarize_result(result)
        line = f"Tool result for {tool}: {outcome} - {summary}"
        # Clip the summary line itself
        if len(line) > CLIP_STEP_LOG + 50:
            line = line[:CLIP_STEP_LOG] + "..."
        self._step_log.append(line)
        if len(self._step_log) > 30:
            self._step_log.pop(0)
        # Update working memory
        path = (result.get("path") or call.get("parameters", {}).get("path", ""))
        if path and tool in ("read_file", "write_file", "edit_file"):
            self._memory.remember_file(str(path))
        if reasoning := (call.get("reasoning") or "").strip():
            self._memory.add_note(reasoning)

    def _is_complex(self, message: str) -> bool:
        keywords = ["complex", "multiple", "several", "build", "create system"]
        return len(message.split()) > 20 or any(w in message.lower() for w in keywords)

    def _announce_plan(self, calls: List[Dict[str, Any]], status: StatusCallback) -> None:
        if not calls:
            return
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
            path = result.get("path", "")
            lines = result.get("lines", 0)
            return f"Read {path} ({lines} lines)" if path else f"Read {lines} lines"
        if tool == "list_directory":
            return f"Found {len(result.get('result', []))} items"
        if tool == "search_files":
            return f"Found {result.get('total_matches', 0)} matches" if result.get("total_matches") else "No matches"
        return "Done"

    def request_abort(self, reason: str = "User requested stop") -> None:
        """Request graceful abort of the current agent run."""
        if self._abort is not None:
            self._abort.abort(reason)
        else:
            abort = StreamAbort()
            abort.abort(reason)
            self._abort = abort

    def start_new_session(self, session_id: str) -> None:
        """Begin a new checkpoint session for undo support."""
        self._checkpoint_mgr.start_session(session_id)

    def end_session(self) -> Optional[str]:
        """End the current checkpoint session."""
        return self._checkpoint_mgr.end_session()

    def undo_last(self) -> list:
        """Undo the most recent file changes."""
        return self._checkpoint_mgr.undo_last()

    def get_performance_stats(self) -> Dict[str, Any]:
        """Return combined performance statistics."""
        return {
            "tokens": {
                "total": self._total_tokens,
                "llm_calls": self._total_llm_calls,
            },
            "retries": self._retry_handler.get_stats(),
            "checkpoints": self._checkpoint_mgr.get_stats(),
            "context": self._context_budget.get_stats(),
            "memories": self._memory_store.count(),
            "plugins": self._plugin_manager.get_loaded(),
            "auto_commit": self._auto_commit.get_stats(),
            "auto_test": self._auto_test.get_stats(),
            "cost": self._cost_estimator.summary(),
        }

    def _store_session_memories(self, user_message: str, answer: str,
                                tool_results: List[Dict[str, Any]]) -> None:
        """Extract and store useful facts from the session.

        Learns from file reads, edits, and command outputs to build
        persistent memory across sessions.
        """
        try:
            # Learn file paths the user works with
            for result in tool_results:
                if result.get("status") != "success":
                    continue
                path = result.get("path", "")
                if path and result.get("tool_name") in ("read_file", "write_file", "edit_file"):
                    ext = Path(path).suffix
                    if ext:
                        self._memory_store.remember(
                            f"user works with {ext} files",
                            f"{path} ({ext})",
                            category="pattern",
                        )

            # Learn from command outputs
            for result in tool_results:
                if result.get("tool_name") == "run_command" and result.get("status") == "success":
                    output = str(result.get("result", ""))[:200]
                    if output and len(output) > 10:
                        self._memory_store.remember(
                            f"command output: {user_message[:50]}",
                            output[:150],
                            category="context",
                            source="session",
                        )
        except Exception:
            pass  # Never crash on memory operations

    def _final_response(self, user_message: str, tool_results: List[Dict[str, Any]]) -> str:
        context = [f"User asked: {user_message}", "", "I completed these operations:"]
        for result in tool_results:
            tool = result.get("tool_name", "unknown")
            if result.get("status") == "success":
                content = tool_content_for_context(result, max_chars=2000)
                context.append(f"✓ {tool}: {content or 'Success'}")
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
