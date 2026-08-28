"""
ProjectTemplates - Pre-configured agent setups for common project types.

Pattern from: Aider's project detection + Claude Code's auto-config.
Each template provides:
- Optimal agent preset
- Recommended configuration
- AGENTS.md content
- Sample .ggufloader.json
- Feature recommendations

Templates:
- python_web: Flask/FastAPI/Django projects
- python_lib: Python libraries/packages
- javascript: Node.js projects
- rust: Rust projects
- go: Go projects
- data_science: Jupyter/notebook projects
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProjectTemplate:
    """Configuration template for a project type."""
    id: str
    name: str
    description: str
    icon: str

    # Agent config
    preset: str = "full_stack"
    max_steps: int = 8
    auto_commit: bool = True
    auto_test: bool = True

    # Feature recommendations
    recommended_features: List[str] = field(default_factory=lambda: [
        "memory", "knowledge", "auto_commit", "auto_test",
    ])

    # Config overrides
    config_overrides: Dict[str, Any] = field(default_factory=dict)

    # AGENTS.md content
    agents_md_content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "preset": self.preset,
        }


# Template registry
TEMPLATES: Dict[str, ProjectTemplate] = {
    "python_web": ProjectTemplate(
        id="python_web",
        name="Python Web App",
        description="Flask, FastAPI, Django projects",
        icon="🌐",
        preset="full_stack",
        max_steps=12,
        agents_md_content=(
            "# Python Web Project\n\n"
            "This is a Python web application.\n\n"
            "## Conventions\n"
            "- Use type hints\n"
            "- Follow PEP 8\n"
            "- Use virtual environments\n"
            "- Tests in tests/ directory\n"
            "- Run with: python -m pytest\n"
        ),
    ),

    "python_lib": ProjectTemplate(
        id="python_lib",
        name="Python Library",
        description="Python packages and libraries",
        icon="📚",
        preset="full_stack",
        max_steps=10,
        agents_md_content=(
            "# Python Library\n\n"
            "This is a Python library/package.\n\n"
            "## Conventions\n"
            "- Use type hints throughout\n"
            "- Docstrings for all public APIs\n"
            "- Tests mirror source structure\n"
            "- Use pyproject.toml for config\n"
        ),
    ),

    "javascript": ProjectTemplate(
        id="javascript",
        name="JavaScript/TypeScript",
        description="Node.js, React, Next.js projects",
        icon="⚡",
        preset="full_stack",
        max_steps=10,
        agents_md_content=(
            "# JavaScript/TypeScript Project\n\n"
            "## Conventions\n"
            "- Use TypeScript when available\n"
            "- ESLint + Prettier for formatting\n"
            "- Tests in __tests__/ or *.test.js\n"
            "- Run with: npm test\n"
        ),
    ),

    "rust": ProjectTemplate(
        id="rust",
        name="Rust Project",
        description="Rust libraries and binaries",
        icon="🦀",
        preset="full_stack",
        max_steps=10,
        agents_md_content=(
            "# Rust Project\n\n"
            "## Conventions\n"
            "- Follow Rust API guidelines\n"
            "- Tests in tests/ and #[cfg(test)]\n"
            "- Use cargo clippy for linting\n"
            "- Run with: cargo test\n"
        ),
    ),

    "go": ProjectTemplate(
        id="go",
        name="Go Project",
        description="Go libraries and services",
        icon="🔵",
        preset="full_stack",
        max_steps=10,
        agents_md_content=(
            "# Go Project\n\n"
            "## Conventions\n"
            "- Follow Effective Go guidelines\n"
            "- Tests in *_test.go files\n"
            "- Use gofmt/goimports\n"
            "- Run with: go test ./...\n"
        ),
    ),

    "data_science": ProjectTemplate(
        id="data_science",
        name="Data Science",
        description="Jupyter notebooks, ML projects",
        icon="📊",
        preset="research",
        max_steps=15,
        agents_md_content=(
            "# Data Science Project\n\n"
            "## Conventions\n"
            "- Notebooks in notebooks/ directory\n"
            "- Scripts in src/ directory\n"
            "- Data in data/ (gitignored)\n"
            "- Models in models/ (gitignored)\n"
            "- Use pandas, numpy, scikit-learn\n"
        ),
    ),
}


class ProjectTemplateManager:
    """Manage and apply project templates.

    Usage:
        mgr = ProjectTemplateManager(workspace)

        # Auto-detect and apply
        template = mgr.auto_detect()
        if template:
            mgr.apply(template)

        # Or manually select
        mgr.apply(TEMPLATES["python_web"])
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def list_all(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in TEMPLATES.values()]

    def get(self, template_id: str) -> Optional[ProjectTemplate]:
        return TEMPLATES.get(template_id)

    def auto_detect(self) -> Optional[ProjectTemplate]:
        """Auto-detect the best template for this workspace."""
        # Check for Python web frameworks
        for indicator in ["requirements.txt", "pyproject.toml"]:
            if (self.workspace / indicator).exists():
                try:
                    content = (self.workspace / indicator).read_text(encoding="utf-8")
                    if any(fw in content for fw in ["flask", "fastapi", "django"]):
                        return TEMPLATES["python_web"]
                except Exception:
                    pass

        # Check for Python package
        if (self.workspace / "setup.py").exists() or (self.workspace / "pyproject.toml").exists():
            return TEMPLATES["python_lib"]

        # Check for JavaScript
        if (self.workspace / "package.json").exists():
            return TEMPLATES["javascript"]

        # Check for Rust
        if (self.workspace / "Cargo.toml").exists():
            return TEMPLATES["rust"]

        # Check for Go
        if (self.workspace / "go.mod").exists():
            return TEMPLATES["go"]

        # Check for notebooks
        notebooks = list(self.workspace.rglob("*.ipynb"))[:5]
        if notebooks:
            return TEMPLATES["data_science"]

        return None

    def apply(self, template: ProjectTemplate) -> Dict[str, Any]:
        """Apply a template to the workspace."""
        result = {"template": template.name, "steps": []}

        # Write AGENTS.md if not exists
        agents_md = self.workspace / "AGENTS.md"
        if not agents_md.exists() and template.agents_md_content:
            agents_md.write_text(template.agents_md_content, encoding="utf-8")
            result["steps"].append("Generated AGENTS.md")

        # Write config
        config_file = self.workspace / ".ggufloader.json"
        config = {
            "version": 2,
            "agent": {
                "preset": template.preset,
                "max_steps": template.max_steps,
                "auto_commit": template.auto_commit,
                "auto_test": template.auto_test,
            },
        }
        config.update(template.config_overrides)

        if config_file.exists():
            try:
                existing = json.loads(config_file.read_text(encoding="utf-8"))
                existing.update(config)
                config = existing
            except Exception:
                pass

        config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
        result["steps"].append(f"Created .ggufloader.json with {template.name} config")

        return result
