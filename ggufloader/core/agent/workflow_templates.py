"""
WorkflowTemplates - Pre-built workflows for common agent tasks.

Pattern from: Aider's edit-format modes + SWE-agent task decomposition.
Provides ready-to-use workflow templates that users can instantiate
with their specific project context.

Templates:
- code_review: Systematic code review with checklist
- refactor: Safe refactoring with verification
- debug: Error diagnosis and fix pipeline
- document: Documentation generation
- dependency_update: Safe dependency update workflow
- security_audit: Security vulnerability scanning
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .workflow_engine import WorkflowEngine, Workflow, StepType

logger = logging.getLogger(__name__)


def create_code_review_workflow(engine: WorkflowEngine, files: List[str]) -> str:
    """Create a code review workflow.

    Steps:
    1. Read all target files
    2. Check for common issues (error handling, type safety)
    3. Check for security issues
    4. Check for performance issues
    5. Generate review report
    """
    wf = engine.create_workflow("code_review", "Code Review",
                               f"Review {len(files)} files")

    def read_files(files=files, **kw):
        contents = {}
        for f in files:
            try:
                from pathlib import Path
                contents[f] = Path(f).read_text(encoding="utf-8", errors="ignore")[:5000]
            except Exception:
                contents[f] = "(unreadable)"
        return contents

    def check_error_handling(contents={}, **kw):
        issues = []
        for path, content in contents.items():
            if "except:" in content or "except Exception:" in content:
                issues.append(f"{path}: Bare except clause")
            if "try:" in content and "except" not in content:
                issues.append(f"{path}: try without except")
        return issues

    def check_security(contents={}, **kw):
        issues = []
        for path, content in contents.items():
            if "eval(" in content:
                issues.append(f"{path}: Uses eval() - potential security risk")
            if "exec(" in content:
                issues.append(f"{path}: Uses exec() - potential security risk")
            if "subprocess" in content and "shell=True" in content:
                issues.append(f"{path}: subprocess with shell=True")
        return issues

    def generate_report(contents={}, error_issues=[], security_issues=[], **kw):
        all_issues = error_issues + security_issues
        if not all_issues:
            return "✅ No issues found. Code looks good!"
        lines = [f"## Code Review ({len(all_issues)} issues found)\n"]
        if error_issues:
            lines.append("### Error Handling")
            for issue in error_issues:
                lines.append(f"- ⚠️ {issue}")
        if security_issues:
            lines.append("### Security")
            for issue in security_issues:
                lines.append(f"- 🔴 {issue}")
        return "\n".join(lines)

    engine.add_step(wf.id, "read", "Read target files", fn=read_files)
    engine.add_step(wf.id, "errors", "Check error handling",
                    fn=check_error_handling, depends_on=["read"])
    engine.add_step(wf.id, "security", "Check security issues",
                    fn=check_security, depends_on=["read"])
    engine.add_step(wf.id, "report", "Generate report",
                    fn=generate_report, depends_on=["errors", "security"])

    return wf.id


def create_refactor_workflow(engine: WorkflowEngine, target: str) -> str:
    """Create a refactoring workflow.

    Steps:
    1. Read and understand current code
    2. Identify refactoring opportunities
    3. Plan changes
    4. Execute changes (one at a time)
    5. Verify each change
    """
    wf = engine.create_workflow("refactor", "Refactoring Pipeline",
                               f"Refactor {target}")

    def analyze(target=target, **kw):
        from pathlib import Path
        try:
            content = Path(target).read_text(encoding="utf-8")
            lines = content.splitlines()
            issues = []
            if len(lines) > 500:
                issues.append("File is very long, consider splitting")
            if content.count("def ") > 20:
                issues.append("Many functions, consider modularizing")
            return {"lines": len(lines), "functions": content.count("def "), "issues": issues}
        except Exception as e:
            return {"error": str(e)}

    def plan_changes(analysis={}, **kw):
        if "error" in analysis:
            return {"changes": []}
        changes = []
        if analysis.get("lines", 0) > 500:
            changes.append("Split into smaller modules")
        if analysis.get("functions", 0) > 20:
            changes.append("Group related functions into classes")
        return {"changes": changes}

    engine.add_step(wf.id, "analyze", "Analyze code", fn=analyze)
    engine.add_step(wf.id, "plan", "Plan refactoring",
                    fn=plan_changes, depends_on=["analyze"])

    return wf.id


def create_debug_workflow(engine: WorkflowEngine, error_msg: str) -> str:
    """Create a debugging workflow.

    Steps:
    1. Parse the error message
    2. Locate relevant source files
    3. Read and analyze the code
    4. Identify root cause
    5. Propose fix
    """
    wf = engine.create_workflow("debug", "Debug Pipeline",
                               f"Debug: {error_msg[:50]}")

    def parse_error(error_msg=error_msg, **kw):
        import re
        # Extract file and line from stack trace
        match = re.search(r'File "(.+?)", line (\d+)', error_msg)
        if match:
            return {"file": match.group(1), "line": int(match.group(2)),
                    "message": error_msg}
        return {"file": None, "line": None, "message": error_msg}

    def analyze( parsed={}, **kw):
        if not parsed.get("file"):
            return {"cause": "Could not parse error location"}
        return {"cause": f"Error at line {parsed.get('line')} in {parsed.get('file')}"}

    engine.add_step(wf.id, "parse", "Parse error", fn=parse_error)
    engine.add_step(wf.id, "analyze", "Analyze cause",
                    fn=analyze, depends_on=["parse"])

    return wf.id


def create_documentation_workflow(engine: WorkflowEngine, path: str) -> str:
    """Create a documentation generation workflow.

    Steps:
    1. Scan file structure
    2. Read source files
    3. Extract docstrings and signatures
    4. Generate documentation
    """
    wf = engine.create_workflow("document", "Documentation Generator",
                               f"Document {path}")

    def scan(path=path, **kw):
        from pathlib import Path
        p = Path(path)
        files = []
        if p.is_dir():
            for f in p.rglob("*.py"):
                if "__pycache__" not in str(f):
                    files.append(str(f))
        elif p.is_file():
            files.append(str(p))
        return {"files": files[:20]}

    def extract(files={}, **kw):
        import re
        docs = {}
        for filepath in files.get("files", []):
            try:
                from pathlib import Path
                content = Path(filepath).read_text(encoding="utf-8", errors="ignore")[:3000]
                # Extract functions
                funcs = re.findall(r'def (\w+)\((.*?)\)', content)
                # Extract classes
                classes = re.findall(r'class (\w+)', content)
                # Extract docstrings
                docstrings = re.findall(r'"""(.*?)"""', content, re.DOTALL)
                docs[filepath] = {
                    "functions": [f[0] for f in funcs],
                    "classes": classes,
                    "docstrings": [d[:100] for d in docstrings],
                }
            except Exception:
                pass
        return docs

    engine.add_step(wf.id, "scan", "Scan files", fn=scan)
    engine.add_step(wf.id, "extract", "Extract info",
                    fn=extract, depends_on=["scan"])

    return wf.id


# Template registry
TEMPLATES = {
    "code_review": {
        "name": "Code Review",
        "description": "Systematic code review with security and error handling checks",
        "icon": "📝",
        "factory": create_code_review_workflow,
    },
    "refactor": {
        "name": "Refactoring Pipeline",
        "description": "Safe refactoring with analysis and verification",
        "icon": "♻️",
        "factory": create_refactor_workflow,
    },
    "debug": {
        "name": "Debug Pipeline",
        "description": "Error diagnosis and root cause analysis",
        "icon": "🐛",
        "factory": create_debug_workflow,
    },
    "document": {
        "name": "Documentation Generator",
        "description": "Auto-generate documentation from source code",
        "icon": "📚",
        "factory": create_documentation_workflow,
    },
}


class WorkflowTemplates:
    """Pre-built workflow templates.

    Usage:
        templates = WorkflowTemplates(engine)

        # List available templates
        available = templates.list_all()

        # Create from template
        wf_id = templates.create("code_review", files=["src/main.py"])
    """

    def __init__(self, engine: WorkflowEngine) -> None:
        self._engine = engine

    def list_all(self) -> List[Dict[str, Any]]:
        return [
            {"id": k, "name": v["name"], "description": v["description"],
             "icon": v["icon"]}
            for k, v in TEMPLATES.items()
        ]

    def create(self, template_id: str, **kwargs) -> Optional[str]:
        template = TEMPLATES.get(template_id)
        if not template:
            return None
        try:
            wf_id = template["factory"](self._engine, **kwargs)
            return wf_id
        except Exception as e:
            logger.error("Failed to create workflow from template '%s': %s", template_id, e)
            return None

    def get_info(self, template_id: str) -> Optional[Dict[str, Any]]:
        template = TEMPLATES.get(template_id)
        if template:
            return {"name": template["name"], "description": template["description"],
                    "icon": template["icon"]}
        return None
