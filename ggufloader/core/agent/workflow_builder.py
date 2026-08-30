"""
WorkflowBuilder - Build and execute multi-step agent workflows as DAGs.

Features:
- Define workflows as a directed acyclic graph of steps
- Each step: LLM call, tool call, or conditional branch
- Variable passing between steps
- Reusable workflow templates
- Execute workflows with the agent engine
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    id: str
    type: str  # "llm", "tool", "condition", "transform"
    name: str
    config: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    inputs: Dict[str, str] = field(default_factory=dict)  # maps step outputs to this step's inputs
    outputs: List[str] = field(default_factory=list)  # named outputs this step produces
    condition: str = ""  # for conditional steps: expression to evaluate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "config": self.config,
            "depends_on": self.depends_on,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowStep":
        return cls(
            id=data["id"],
            type=data.get("type", "llm"),
            name=data.get("name", data["id"]),
            config=data.get("config", {}),
            depends_on=data.get("depends_on", []),
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", []),
            condition=data.get("condition", ""),
        )


@dataclass
class Workflow:
    """A complete workflow definition."""
    id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    variables: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "variables": self.variables,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            steps=[WorkflowStep.from_dict(s) for s in data.get("steps", [])],
            variables=data.get("variables", {}),
            created_at=data.get("created_at", 0),
            updated_at=data.get("updated_at", 0),
            tags=data.get("tags", []),
        )

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def validate(self) -> List[str]:
        """Validate the workflow DAG. Returns list of errors (empty = valid)."""
        errors = []
        step_ids = {s.id for s in self.steps}

        for step in self.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(f"Step '{step.id}' depends on unknown step '{dep}'")

        # Check for cycles
        if self._has_cycle():
            errors.append("Workflow contains a cycle")

        return errors

    def _has_cycle(self) -> bool:
        """Check for cycles using DFS."""
        visited = set()
        rec_stack = set()
        adj = {s.id: s.depends_on for s in self.steps}

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for node in adj:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def execution_order(self) -> List[str]:
        """Return topologically sorted step IDs."""
        in_degree = {s.id: 0 for s in self.steps}
        adj: Dict[str, List[str]] = {s.id: [] for s in self.steps}

        for step in self.steps:
            for dep in step.depends_on:
                if dep in adj:
                    adj[dep].append(step.id)
                    in_degree[step.id] += 1

        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        order = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order


class WorkflowBuilder:
    """Build, manage, and execute workflows."""

    def __init__(self, workspace: Optional[Path] = None) -> None:
        self.workspace = workspace or Path.home() / ".ggufloader"
        self._workflows_dir = self.workspace / "workflows"
        self._workflows_dir.mkdir(parents=True, exist_ok=True)
        self._workflows: Dict[str, Workflow] = {}
        self._load_workflows()

    def list_all(self) -> List[Workflow]:
        return sorted(self._workflows.values(), key=lambda w: w.updated_at or w.created_at, reverse=True)

    def get(self, workflow_id: str) -> Optional[Workflow]:
        return self._workflows.get(workflow_id)

    def save(self, workflow: Workflow) -> None:
        workflow.updated_at = time.time()
        if not workflow.created_at:
            workflow.created_at = time.time()
        self._workflows[workflow.id] = workflow
        path = self._workflows_dir / f"{workflow.id}.json"
        path.write_text(json.dumps(workflow.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def delete(self, workflow_id: str) -> bool:
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
            path = self._workflows_dir / f"{workflow_id}.json"
            path.unlink(missing_ok=True)
            return True
        return False

    def duplicate(self, workflow_id: str, new_name: str = "") -> Optional[Workflow]:
        """Duplicate a workflow with a new ID."""
        source = self._workflows.get(workflow_id)
        if not source:
            return None
        import hashlib
        new_id = hashlib.sha256(f"{workflow_id}_{time.time()}".encode()).hexdigest()[:8]
        new_wf = Workflow(
            id=new_id,
            name=new_name or f"Copy of {source.name}",
            description=source.description,
            steps=[WorkflowStep.from_dict(s.to_dict()) for s in source.steps],
            variables=dict(source.variables),
            tags=list(source.tags),
        )
        self.save(new_wf)
        return new_wf

    def execute_dry_run(self, workflow_id: str, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """Dry-run a workflow: validate and show execution plan without running."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"error": "Workflow not found"}

        errors = wf.validate()
        if errors:
            return {"valid": False, "errors": errors}

        order = wf.execution_order()
        plan = []
        for sid in order:
            step = next((s for s in wf.steps if s.id == sid), None)
            if step:
                plan.append({
                    "step": step.id,
                    "name": step.name,
                    "type": step.type,
                    "depends_on": step.depends_on,
                    "config_preview": {k: str(v)[:50] for k, v in step.config.items()},
                })

        return {
            "valid": True,
            "step_count": len(plan),
            "execution_order": order,
            "plan": plan,
        }

    def create_from_template(self, template_type: str, name: str = "") -> Optional[Workflow]:
        """Create a workflow from a built-in template."""
        templates = {
            "code_review": Workflow(
                id="code_review_template",
                name="Code Review Pipeline",
                description="Read files, analyze code, generate review report",
                steps=[
                    WorkflowStep(id="find_files", type="tool", name="Find Source Files",
                                 config={"tool": "glob", "params": {"pattern": "**/*.py"}}),
                    WorkflowStep(id="read_files", type="tool", name="Read Files",
                                 config={"tool": "read_file", "params": {"path": "{{find_files.output}}"}},
                                 depends_on=["find_files"]),
                    WorkflowStep(id="review", type="llm", name="Code Review",
                                 config={"prompt": "Review this code for bugs, style, and performance:\n{{read_files.output}}"},
                                 depends_on=["read_files"], outputs=["review"]),
                    WorkflowStep(id="report", type="transform", name="Format Report",
                                 config={"template": "# Code Review\n\n{{review.output}}"},
                                 depends_on=["review"]),
                ],
            ),
            "refactor": Workflow(
                id="refactor_template",
                name="Refactor Pipeline",
                description="Read code, plan refactor, apply changes, verify",
                steps=[
                    WorkflowStep(id="read", type="tool", name="Read Code",
                                 config={"tool": "read_file", "params": {"path": "{{file_path}}"}}),
                    WorkflowStep(id="plan", type="llm", name="Plan Refactor",
                                 config={"prompt": "Plan refactoring for:\n{{read.output}}"},
                                 depends_on=["read"], outputs=["plan"]),
                    WorkflowStep(id="apply", type="tool", name="Apply Changes",
                                 config={"tool": "edit_file", "params": {"path": "{{file_path}}", "changes": "{{plan.output}}"}},
                                 depends_on=["plan"]),
                    WorkflowStep(id="verify", type="llm", name="Verify Changes",
                                 config={"prompt": "Verify the refactored code is correct:\n{{apply.output}}"},
                                 depends_on=["apply"]),
                ],
            ),
            "summarize_project": Workflow(
                id="summarize_project_template",
                name="Project Summary Pipeline",
                description="Scan project structure, read key files, generate summary",
                steps=[
                    WorkflowStep(id="scan", type="tool", name="Scan Project",
                                 config={"tool": "list_directory", "params": {"path": "."}}),
                    WorkflowStep(id="read_key", type="tool", name="Read Key Files",
                                 config={"tool": "read_file", "params": {"path": "README.md"}},
                                 depends_on=["scan"]),
                    WorkflowStep(id="summarize", type="llm", name="Generate Summary",
                                 config={"prompt": "Summarize this project:\nStructure: {{scan.output}}\nREADME: {{read_key.output}}"},
                                 depends_on=["read_key"], outputs=["summary"]),
                ],
            ),
        }

        template = templates.get(template_type)
        if not template:
            return None

        import hashlib
        new_id = hashlib.sha256(f"{template_type}_{time.time()}".encode()).hexdigest()[:8]
        wf = Workflow(
            id=new_id,
            name=name or template.name,
            description=template.description,
            steps=template.steps,
            tags=template.tags,
        )
        self.save(wf)
        return wf

    def list_templates(self) -> List[Dict[str, Any]]:
        """List available workflow templates."""
        return [
            {"id": "code_review", "name": "Code Review Pipeline", "description": "Read, analyze, and report on code quality"},
            {"id": "refactor", "name": "Refactor Pipeline", "description": "Read, plan, apply, and verify code refactoring"},
            {"id": "summarize_project", "name": "Project Summary", "description": "Scan, read, and summarize a project"},
        ]

    def _load_workflows(self) -> None:
        for f in self._workflows_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                wf = Workflow.from_dict(data)
                self._workflows[wf.id] = wf
            except Exception:
                continue
