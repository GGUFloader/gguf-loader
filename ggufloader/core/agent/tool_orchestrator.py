"""
ToolOrchestrator — executes tool calls with parallel execution, retries,
and approval gating.

Extracted from GraphAgent._tools_node to separate tool execution concerns
from the agent loop.  The orchestrator owns:
  - Parallel execution of independent tools (ThreadPoolExecutor)
  - Sequential execution of approval-gated tools
  - Corrective retry per failure (one LLM round-trip)
  - Stale-repeat detection
  - Failed-call tracking

Deleting this module concentrates all tool execution logic in one place.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .tool_registry import ToolRegistry, validate_tool_call

logger = logging.getLogger(__name__)

# Type alias for the LLM callable used in fix retries
LLMCallable = Callable[..., Any]


class ToolOrchestrator:
    """Manages tool execution for a single agent turn.

    Parameters
    ----------
    tools : ToolRegistry
        Registry of available tools.
    workspace : str
        Workspace path (for approval descriptions).
    failed_signatures : dict
        Mutable dict tracking repeated failures (shared with the agent).
    """

    def __init__(
        self,
        tools: ToolRegistry,
        workspace: str,
        failed_signatures: Dict[str, int],
        system_prompt: Optional[str] = None,
    ) -> None:
        self.tools = tools
        self.workspace = workspace
        self._failed = failed_signatures
        self._system_prompt = system_prompt

    def execute_batch(
        self,
        calls: List[Dict[str, Any]],
        existing_results: List[Dict[str, Any]],
        existing_executed: List[Dict[str, str]],
        on_status: Callable[[str], None],
        on_tool: Callable[[Dict[str, Any]], None],
        check_cancel: Callable[[], None],
        announce_plan: Callable[[List, Any], None],
        writer: Any,
        approval_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
        llm_call: Optional[LLMCallable] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """Execute a batch of tool calls, returning updated results and executed list.

        Returns
        -------
        (tool_results, executed_calls) — updated lists.
        """
        tool_results = list(existing_results)
        executed_calls = list(existing_executed)
        announce_plan(calls, writer)

        # 1. Collect approvals for approval-gated tools
        approvals: Dict[int, bool] = {}
        if approval_fn:
            for index, call in enumerate(calls):
                if self.tools.requires_approval(call.get("tool", ""), call.get("parameters", {})):
                    payload = {
                        "type": "approval",
                        "call": call,
                        "description": self._describe(call),
                        "workspace": self.workspace,
                    }
                    writer({"event": "status", "text": f"[approve] Approval needed: {self._describe(call)}"})
                    approvals[index] = bool(approval_fn(payload))
        check_cancel()

        # 2. Separate into parallel (independent) and sequential (gated)
        independent: List[Tuple[int, Dict[str, Any]]] = []
        gated: List[Tuple[int, Dict[str, Any]]] = []
        for index, call in enumerate(calls):
            if self.tools.requires_approval(call.get("tool", ""), call.get("parameters", {})):
                gated.append((index, call))
            else:
                independent.append((index, call))

        failures: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

        # 3. Execute independent tools concurrently
        if independent:
            def _exec_one(idx_call: Tuple[int, Dict[str, Any]]) -> Tuple[int, str, Dict[str, Any], str]:
                idx, call = idx_call
                sig = self._signature(call)
                tool_name = call.get("tool", "")
                if self._failed.get(sig, 0) >= 2:
                    return idx, sig, {"status": "skipped", "tool_name": tool_name}, "skip"
                verr = validate_tool_call(call, self.tools)
                if verr:
                    return idx, sig, {"status": "error", "error": verr, "tool_name": tool_name}, "error"
                result = self.tools.execute(tool_name, call.get("parameters", {}))
                return idx, sig, result, "ok"

            with ThreadPoolExecutor(max_workers=min(len(independent), 4)) as pool:
                futures = {pool.submit(_exec_one, ic): ic for ic in independent}
                for future in as_completed(futures):
                    check_cancel()
                    idx, sig, result, status = future.result()
                    if status == "skip":
                        writer({"event": "status", "text": f"  [skip] Skipping repeated failing call: {self._describe(calls[idx])}"})
                        continue
                    if status == "error":
                        writer({"event": "status", "text": f"  [FAIL] Invalid call: {result.get('error', '')}"})
                        self._failed[sig] = self._failed.get(sig, 0) + 1
                        failures.append((calls[idx], result))
                        continue
                    tool_results.append(result)
                    executed_calls.append({"signature": sig, "tool": calls[idx].get("tool", "")})
                    writer({"event": "tool", "result": result})
                    if result.get("status") == "success":
                        writer({"event": "status", "text": f"  [OK] {self._summarize_result(result)}"})
                    else:
                        error_msg = result.get("error", "Unknown error")
                        writer({"event": "status", "text": f"  [FAIL] {error_msg}"})
                        self._failed[sig] = self._failed.get(sig, 0) + 1
                        failures.append((calls[idx], result))

        # 4. Execute approval-gated tools sequentially
        for idx, call in gated:
            check_cancel()
            sig = self._signature(call)
            writer({"event": "status", "text": f"-> {self._describe(call)}"})
            if approvals.get(idx) is not None and not approvals[idx]:
                result = {"status": "error", "error": "Approval denied",
                          "tool_name": call.get("tool", "")}
            else:
                result = self.tools.execute(call.get("tool", ""), call.get("parameters", {}))
                executed_calls.append({"signature": sig, "tool": call.get("tool", "")})
            tool_results.append(result)
            writer({"event": "tool", "result": result})
            if result.get("status") == "success":
                writer({"event": "status", "text": f"  [OK] {self._summarize_result(result)}"})
            else:
                error_msg = result.get("error", "Unknown error")
                writer({"event": "status", "text": f"  [FAIL] {error_msg}"})
                self._failed[sig] = self._failed.get(sig, 0) + 1
                failures.append((call, result))

        # 5. Retry failures (one corrective LLM round-trip per failure)
        if llm_call and failures:
            for failed_call, failed_result in failures:
                check_cancel()
                fixed = self._request_fix(failed_call, failed_result, llm_call, writer)
                if fixed is None:
                    continue
                executed_calls.append(
                    {"signature": self._signature(failed_call), "tool": failed_call.get("tool", "")}
                )
                tool_results.append(fixed)
                writer({"event": "tool", "result": fixed})
                if fixed.get("status") == "success":
                    writer({"event": "status", "text": f"  [OK] retry succeeded: {self._summarize_result(fixed)}"})
                else:
                    writer({"event": "status", "text": f"  [FAIL] retry failed: {fixed.get('error', 'Unknown error')}"})

        return tool_results, executed_calls

    # ── Internal ────────────────────────────────────────────────────────

    def _request_fix(
        self,
        failed_call: Dict[str, Any],
        failed_result: Dict[str, Any],
        llm_call: LLMCallable,
        writer: Any,
    ) -> Optional[Dict[str, Any]]:
        """Ask the model to correct a failed tool call; execute the corrected call."""
        from .prompt_builder import PromptBuilder
        pb = PromptBuilder(Path(self.workspace), self.tools, system_prompt_override=self._system_prompt)
        prompt = pb.fix_prompt(failed_call, failed_result)
        raw = llm_call(prompt)
        from .agent_engine import extract_json
        data = extract_json(raw)
        if data is None:
            return None
        calls = [c for c in (data.get("tool_calls") or []) if isinstance(c, dict) and c.get("tool")]
        if not calls:
            return None
        tool_name = failed_call.get("tool", "")
        call = next((c for c in calls if c.get("tool") == tool_name), calls[0])
        return self.tools.execute(call.get("tool", ""), call.get("parameters", {}))

    def _signature(self, call: Dict[str, Any]) -> str:
        try:
            params = json.dumps(call.get("parameters", {}), sort_keys=True, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            params = str(call.get("parameters"))
        return f"{call.get('tool', '')}:{params}"

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
        if tool == "run_command":
            return f"Run command: {params.get('command', '')}"
        if tool == "git":
            args = params.get("args") or []
            return "git " + " ".join(str(a) for a in args)
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
