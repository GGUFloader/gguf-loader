"""
PromptTemplate - Reusable prompt templates with variables.

Features:
- Save/load templates from JSON files
- Variable substitution: {{variable_name}} syntax
- Template composition: nest templates inside other templates
- Categories and tags for organization
- Built-in template library for common tasks
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Built-in templates
BUILTIN_TEMPLATES = [
    {
        "id": "code_review",
        "name": "Code Review",
        "description": "Review code for bugs, style, and performance issues",
        "category": "development",
        "tags": ["code", "review", "quality"],
        "template": "Review the following code for bugs, style issues, and performance improvements:\n\n{{code}}\n\nFocus on:\n1. Potential bugs or logic errors\n2. Code style and readability\n3. Performance optimizations\n4. Security concerns",
        "variables": ["code"],
        "builtin": True,
    },
    {
        "id": "explain_code",
        "name": "Explain Code",
        "description": "Explain what code does step by step",
        "category": "learning",
        "tags": ["code", "explain", "tutorial"],
        "template": "Explain the following code step by step. Describe what each section does and how it fits together:\n\n{{code}}",
        "variables": ["code"],
        "builtin": True,
    },
    {
        "id": "refactor",
        "name": "Refactor Code",
        "description": "Suggest refactoring improvements for code",
        "category": "development",
        "tags": ["code", "refactor", "improve"],
        "template": "Refactor the following code to improve readability, maintainability, and performance:\n\n{{code}}\n\nGoal: {{goal}}\nConstraints: {{constraints}}",
        "variables": ["code", "goal", "constraints"],
        "builtin": True,
    },
    {
        "id": "write_tests",
        "name": "Write Tests",
        "description": "Generate unit tests for code",
        "category": "testing",
        "tags": ["code", "tests", "unittest"],
        "template": "Write comprehensive unit tests for the following code:\n\n{{code}}\n\nFramework: {{framework}}\nCoverage: include edge cases, error handling, and happy path",
        "variables": ["code", "framework"],
        "builtin": True,
    },
    {
        "id": "debug_error",
        "name": "Debug Error",
        "description": "Diagnose and fix an error",
        "category": "development",
        "tags": ["debug", "error", "fix"],
        "template": "I'm getting this error:\n\n```\n{{error}}\n```\n\nIn this code:\n```{{language}}\n{{code}}\n```\n\nPlease diagnose the root cause and suggest a fix.",
        "variables": ["error", "code", "language"],
        "builtin": True,
    },
    {
        "id": "summarize",
        "name": "Summarize",
        "description": "Summarize text or documents",
        "category": "writing",
        "tags": ["summary", "text", "brief"],
        "template": "Summarize the following {{format}} in {{length}}:\n\n{{content}}",
        "variables": ["format", "length", "content"],
        "builtin": True,
    },
    {
        "id": "api_docs",
        "name": "API Documentation",
        "description": "Generate API documentation for code",
        "category": "documentation",
        "tags": ["api", "docs", "openapi"],
        "template": "Generate API documentation for the following code. Include endpoint descriptions, parameters, return types, and example requests:\n\n{{code}}\n\nFormat: {{format}}",
        "variables": ["code", "format"],
        "builtin": True,
    },
    {
        "id": "commit_message",
        "name": "Commit Message",
        "description": "Generate a conventional commit message from a diff",
        "category": "git",
        "tags": ["git", "commit", "message"],
        "template": "Generate a conventional commit message for the following changes:\n\n{{diff}}\n\nUse the format: type(scope): description\nTypes: feat, fix, docs, style, refactor, test, chore",
        "variables": ["diff"],
        "builtin": True,
    },
]


class PromptTemplate:
    """A reusable prompt template with variable substitution."""

    def __init__(
        self,
        template_id: str,
        name: str,
        description: str,
        template: str,
        variables: List[str],
        category: str = "general",
        tags: Optional[List[str]] = None,
        builtin: bool = False,
    ) -> None:
        self.id = template_id
        self.name = name
        self.description = description
        self.template = template
        self.variables = variables
        self.category = category
        self.tags = tags or []
        self.builtin = builtin
        self.created_at = time.time()

    def render(self, **kwargs: Any) -> str:
        """Render the template with variable substitution."""
        result = self.template
        for var in self.variables:
            value = kwargs.get(var, f"{{{{{var}}}}}")
            result = result.replace(f"{{{{{var}}}}}", str(value))
        return result

    def missing_variables(self, **kwargs: Any) -> List[str]:
        """Return list of variables not provided."""
        return [v for v in self.variables if v not in kwargs]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "variables": self.variables,
            "category": self.category,
            "tags": self.tags,
            "builtin": self.builtin,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptTemplate":
        t = cls(
            template_id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            template=data["template"],
            variables=data.get("variables", []),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            builtin=data.get("builtin", False),
        )
        t.created_at = data.get("created_at", time.time())
        return t


class TemplateManager:
    """Manage prompt templates: save, load, list, compose."""

    def __init__(self, workspace: Optional[Path] = None) -> None:
        self.workspace = workspace or Path.home() / ".ggufloader"
        self._templates_dir = self.workspace / "templates"
        self._templates_dir.mkdir(parents=True, exist_ok=True)
        self._templates: Dict[str, PromptTemplate] = {}
        self._load_builtin()
        self._load_custom()

    def _load_builtin(self) -> None:
        for data in BUILTIN_TEMPLATES:
            t = PromptTemplate.from_dict(data)
            self._templates[t.id] = t

    def _load_custom(self) -> None:
        for f in self._templates_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                t = PromptTemplate.from_dict(data)
                self._templates[t.id] = t
            except Exception as e:
                logger.warning("Failed to load template %s: %s", f.name, e)

    def list_all(self) -> List[PromptTemplate]:
        return list(self._templates.values())

    def list_by_category(self, category: str) -> List[PromptTemplate]:
        return [t for t in self._templates.values() if t.category == category]

    def get(self, template_id: str) -> Optional[PromptTemplate]:
        return self._templates.get(template_id)

    def save(self, template: PromptTemplate) -> None:
        """Save a custom template to disk."""
        self._templates[template.id] = template
        path = self._templates_dir / f"{template.id}.json"
        path.write_text(json.dumps(template.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def delete(self, template_id: str) -> bool:
        """Delete a custom template (cannot delete builtins)."""
        template = self._templates.get(template_id)
        if not template or template.builtin:
            return False
        self._templates.pop(template_id, None)
        path = self._templates_dir / f"{template_id}.json"
        path.unlink(missing_ok=True)
        return True

    def search(self, query: str) -> List[PromptTemplate]:
        """Search templates by name, description, or tags."""
        query_lower = query.lower()
        results = []
        for t in self._templates.values():
            if (query_lower in t.name.lower() or
                query_lower in t.description.lower() or
                any(query_lower in tag.lower() for tag in t.tags)):
                results.append(t)
        return results

    def get_categories(self) -> List[Dict[str, Any]]:
        """Get categories with counts."""
        cats: Dict[str, int] = {}
        for t in self._templates.values():
            cats[t.category] = cats.get(t.category, 0) + 1
        return [{"name": c, "count": n} for c, n in sorted(cats.items())]

    def compose(self, template_ids: List[str], **kwargs: Any) -> str:
        """Compose multiple templates into one prompt.

        Templates are rendered in order and joined with double newlines.
        """
        parts = []
        for tid in template_ids:
            t = self.get(tid)
            if t:
                parts.append(t.render(**kwargs))
        return "\n\n".join(parts)

    def render(self, template_id: str, **kwargs: Any) -> str:
        """Render a single template with variables."""
        t = self.get(template_id)
        if not t:
            return ""
        return t.render(**kwargs)

    def categories(self) -> List[str]:
        """Get all unique categories."""
        return sorted(set(t.category for t in self._templates.values()))
