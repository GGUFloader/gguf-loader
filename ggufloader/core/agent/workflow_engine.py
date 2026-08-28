"""
WorkflowEngine - Multi-step workflow orchestration.

Pattern from: Aider's edit-format modes + OpenHands automation builder.
Enables complex multi-step workflows like:
- Code review with checklist
- Refactoring pipeline (analyze → plan → execute → verify)
- Documentation generation
- Dependency updates

Workflows are defined as DAGs of steps with conditions and loops.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepType(Enum):
    ACTION = "action"       # Execute a function
    CONDITION = "condition"  # Branch based on result
    PARALLEL = "parallel"    # Run steps in parallel
    LOOP = "loop"            # Repeat until condition


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    id: str
    name: str
    step_type: StepType = StepType.ACTION
    fn: Optional[Callable] = None
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    condition: Optional[Callable] = None  # for CONDITION type
    max_iterations: int = 10  # for LOOP type
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    start_time: float = 0
    end_time: float = 0

    @property
    def duration_ms(self) -> int:
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time) * 1000)
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.step_type.value,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class Workflow:
    """A complete workflow definition."""
    id: str
    name: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    created_at: float = 0
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
        }


class WorkflowEngine:
    """Execute multi-step workflows with dependency resolution.

    Usage:
        engine = WorkflowEngine()

        # Define workflow
        workflow = engine.create_workflow("review", "Code Review", "Review code quality")
        engine.add_step(workflow.id, "scan", "Scan files", fn=scan_files)
        engine.add_step(workflow.id, "analyze", "Analyze code", fn=analyze, depends_on=["scan"])
        engine.add_step(workflow.id, "report", "Generate report", fn=report, depends_on=["analyze"])

        # Execute
        result = engine.execute(workflow.id)
    """

    def __init__(self) -> None:
        self._workflows: Dict[str, Workflow] = {}
        self._on_step_complete: Optional[Callable[[WorkflowStep], None]] = None
        self._on_workflow_complete: Optional[Callable[[Workflow], None]] = None

    def set_step_callback(self, callback: Callable[[WorkflowStep], None]) -> None:
        self._on_step_complete = callback

    def set_workflow_callback(self, callback: Callable[[Workflow], None]) -> None:
        self._on_workflow_complete = callback

    def create_workflow(self, workflow_id: str, name: str, description: str = "") -> Workflow:
        workflow = Workflow(
            id=workflow_id, name=name, description=description,
            created_at=time.time(),
        )
        self._workflows[workflow_id] = workflow
        return workflow

    def add_step(self, workflow_id: str, step_id: str, name: str,
                 fn: Callable = None, step_type: StepType = StepType.ACTION,
                 depends_on: List[str] = None, params: Dict[str, Any] = None,
                 condition: Callable = None, max_iterations: int = 10) -> WorkflowStep:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        step = WorkflowStep(
            id=step_id, name=name, step_type=step_type,
            fn=fn, params=params or {},
            depends_on=depends_on or [],
            condition=condition, max_iterations=max_iterations,
        )
        workflow.steps.append(step)
        return step

    def execute(self, workflow_id: str) -> Dict[str, Any]:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return {"status": "error", "error": f"Workflow '{workflow_id}' not found"}

        workflow.status = "running"
        start_time = time.time()

        # Topological execution
        completed = set()
        while True:
            # Find ready steps (all dependencies met)
            ready = []
            for step in workflow.steps:
                if step.status != StepStatus.PENDING:
                    continue
                if all(dep in completed for dep in step.depends_on):
                    ready.append(step)

            if not ready:
                break

            for step in ready:
                step.status = StepStatus.RUNNING
                step.start_time = time.time()

                try:
                    if step.step_type == StepType.CONDITION:
                        result = self._execute_condition(step, workflow)
                    elif step.step_type == StepType.LOOP:
                        result = self._execute_loop(step, workflow)
                    elif step.step_type == StepType.PARALLEL:
                        result = self._execute_parallel(step, workflow)
                    else:
                        result = self._execute_action(step)

                    step.result = result
                    step.status = StepStatus.COMPLETED
                    completed.add(step.id)

                except Exception as e:
                    step.error = str(e)
                    step.status = StepStatus.FAILED
                    logger.error("Step %s failed: %s", step.id, e)

                finally:
                    step.end_time = time.time()
                    if self._on_step_complete:
                        try:
                            self._on_step_complete(step)
                        except Exception:
                            pass

        # Mark skipped steps
        for step in workflow.steps:
            if step.status == StepStatus.PENDING:
                step.status = StepStatus.SKIPPED

        workflow.status = "completed" if all(
            s.status == StepStatus.COMPLETED for s in workflow.steps
        ) else "failed"

        elapsed = time.time() - start_time

        if self._on_workflow_complete:
            try:
                self._on_workflow_complete(workflow)
            except Exception:
                pass

        return {
            "status": workflow.status,
            "duration_ms": int(elapsed * 1000),
            "steps": [s.to_dict() for s in workflow.steps],
        }

    def _execute_action(self, step: WorkflowStep) -> Any:
        if step.fn:
            return step.fn(**step.params)
        return None

    def _execute_condition(self, step: WorkflowStep, workflow: Workflow) -> Any:
        if step.condition:
            result = step.condition()
            if not result:
                step.status = StepStatus.SKIPPED
            return result
        return True

    def _execute_loop(self, step: WorkflowStep, workflow: Workflow) -> List[Any]:
        results = []
        for i in range(step.max_iterations):
            if step.fn:
                result = step.fn(iteration=i, **step.params)
                results.append(result)
                if step.condition and not step.condition(result):
                    break
        return results

    def _execute_parallel(self, step: WorkflowStep, workflow: Workflow) -> List[Any]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        if not step.fn:
            return []

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(step.fn, **step.params, worker=i): i
                for i in range(step.params.get("workers", 4))
            }
            return [f.result() for f in as_completed(futures)]

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> List[Dict[str, Any]]:
        return [w.to_dict() for w in self._workflows.values()]

    def cancel(self, workflow_id: str) -> bool:
        workflow = self._workflows.get(workflow_id)
        if workflow:
            workflow.status = "cancelled"
            for step in workflow.steps:
                if step.status == StepStatus.RUNNING:
                    step.status = StepStatus.SKIPPED
            return True
        return False
