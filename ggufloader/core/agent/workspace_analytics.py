"""
WorkspaceAnalytics - Code metrics, project health, and actionable insights.

Pattern from: Aider repo-map + CodeClimate metrics.
Scans the workspace to compute:
- File statistics (count, size, languages)
- Code metrics (lines, complexity indicators)
- Project health (missing tests, no README, etc.)
- Actionable insights for the agent
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Language detection by extension
LANG_MAP = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "React", ".tsx": "React TSX",
    ".rs": "Rust", ".go": "Go", ".java": "Java",
    ".c": "C", ".cpp": "C++", ".h": "C/C++",
    ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
    ".kt": "Kotlin", ".sh": "Shell", ".bash": "Bash",
    ".yaml": "YAML", ".yml": "YAML", ".json": "JSON",
    ".toml": "TOML", ".xml": "XML", ".html": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".sql": "SQL",
    ".md": "Markdown", ".txt": "Text",
}

# Skip directories
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".idea", ".vscode", ".gguf-undo",
    ".gguf-sessions", "env", ".env", ".tox",
}

# Binary extensions (skip for line counting)
BINARY_EXTS = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".gguf", ".pt", ".pth", ".safetensors",
}


class WorkspaceAnalytics:
    """Scan workspace and compute metrics.

    Usage:
        analytics = WorkspaceAnalytics(workspace_path)
        report = analytics.generate_report()
        insights = analytics.get_insights()
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._report: Optional[Dict[str, Any]] = None

    def scan(self) -> Dict[str, Any]:
        """Scan the workspace and return raw metrics."""
        metrics: Dict[str, Any] = {
            "total_files": 0,
            "total_directories": 0,
            "total_size_bytes": 0,
            "languages": {},
            "file_types": {},
            "largest_files": [],
            "deepest_path": "",
            "max_depth": 0,
        }

        all_files: List[Dict[str, Any]] = []

        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            # Calculate depth
            rel_root = Path(root).relative_to(self.workspace)
            depth = len(rel_root.parts)
            metrics["total_directories"] += len(dirs)
            if depth > metrics["max_depth"]:
                metrics["max_depth"] = depth
                metrics["deepest_path"] = str(rel_root)

            for name in files:
                if name.startswith("."):
                    continue
                filepath = Path(root) / name
                ext = filepath.suffix.lower()

                if ext in BINARY_EXTS:
                    continue

                try:
                    stat = filepath.stat()
                except OSError:
                    continue

                rel_path = str(filepath.relative_to(self.workspace))
                size = stat.st_size
                metrics["total_files"] += 1
                metrics["total_size_bytes"] += size

                # Track by extension
                metrics["file_types"][ext] = metrics["file_types"].get(ext, 0) + 1

                # Track by language
                lang = LANG_MAP.get(ext, ext.lstrip(".") or "Other")
                if lang not in metrics["languages"]:
                    metrics["languages"][lang] = {"count": 0, "total_bytes": 0, "total_lines": 0}
                metrics["languages"][lang]["count"] += 1
                metrics["languages"][lang]["total_bytes"] += size

                # Count lines for code files
                if ext in (".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go",
                           ".java", ".c", ".cpp", ".h", ".rb", ".php", ".sh"):
                    try:
                        content = filepath.read_text(encoding="utf-8", errors="ignore")
                        lines = len(content.splitlines())
                        metrics["languages"][lang]["total_lines"] += lines
                    except (OSError, UnicodeDecodeError):
                        pass

                all_files.append({"path": rel_path, "size": size, "ext": ext})

        # Sort and get largest files
        all_files.sort(key=lambda f: -f["size"])
        metrics["largest_files"] = [
            {"path": f["path"], "size_kb": round(f["size"] / 1024, 1)}
            for f in all_files[:10]
        ]

        self._report = metrics
        return metrics

    def generate_report(self) -> Dict[str, Any]:
        """Generate a full analytics report with health indicators."""
        if self._report is None:
            self.scan()

        metrics = self._report
        health = self._assess_health(metrics)
        insights = self._generate_insights(metrics, health)

        return {
            "metrics": metrics,
            "health": health,
            "insights": insights,
        }

    def get_insights(self) -> List[str]:
        """Get actionable insights for the agent."""
        if self._report is None:
            self.scan()
        health = self._assess_health(self._report)
        return self._generate_insights(self._report, health)

    def get_language_summary(self) -> str:
        """Get a human-readable language summary."""
        if self._report is None:
            self.scan()

        langs = self._report.get("languages", {})
        if not langs:
            return "No code files found"

        # Sort by lines of code
        sorted_langs = sorted(langs.items(), key=lambda x: -x[1].get("total_lines", 0))
        parts = []
        for lang, data in sorted_langs[:5]:
            lines = data.get("total_lines", 0)
            count = data.get("count", 0)
            if lines > 0:
                parts.append(f"{lang}: {lines} lines ({count} files)")
            else:
                parts.append(f"{lang}: {count} files")
        return ", ".join(parts)

    def _assess_health(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Assess project health indicators."""
        health: Dict[str, Any] = {
            "score": 100,  # starts perfect, deductions for issues
            "issues": [],
            "strengths": [],
        }

        # Check for README
        if not (self.workspace / "README.md").exists():
            health["issues"].append("No README.md found")
            health["score"] -= 10

        # Check for tests
        has_tests = False
        for test_dir in ["tests", "test", "__tests__", "spec"]:
            if (self.workspace / test_dir).is_dir():
                has_tests = True
                break
        if not has_tests:
            # Check for test files at any level
            test_files = list(self.workspace.rglob("test_*.py"))[:1]
            if not test_files:
                test_files = list(self.workspace.rglob("*.test.js"))[:1]
            if not test_files:
                test_files = list(self.workspace.rglob("*.test.ts"))[:1]
            if not test_files:
                health["issues"].append("No test directory or test files found")
                health["score"] -= 15

        # Check for version control
        if not (self.workspace / ".git").is_dir():
            health["issues"].append("Not a git repository")
            health["score"] -= 10

        # Check for config files
        has_config = False
        for cfg in ["pyproject.toml", "package.json", "Cargo.toml", "go.mod"]:
            if (self.workspace / cfg).exists():
                has_config = True
                break
        if not has_config:
            health["issues"].append("No project configuration file found")
            health["score"] -= 5

        # Check for .gitignore
        if not (self.workspace / ".gitignore").exists():
            health["issues"].append("No .gitignore found")
            health["score"] -= 5

        # Strengths
        if (self.workspace / "README.md").exists():
            health["strengths"].append("Has README.md")
        if has_tests:
            health["strengths"].append("Has test files")
        if has_config:
            health["strengths"].append("Has project configuration")
        if (self.workspace / ".git").is_dir():
            health["strengths"].append("Git repository")

        # Check for linting
        for linter in [".flake8", ".pylintrc", "ruff.toml", ".eslintrc"]:
            if (self.workspace / linter).exists():
                health["strengths"].append(f"Has {linter} config")
                break

        health["score"] = max(0, health["score"])
        return health

    def _generate_insights(self, metrics: Dict[str, Any],
                           health: Dict[str, Any]) -> List[str]:
        """Generate actionable insights."""
        insights = []

        # Health-based insights
        if health["score"] < 50:
            insights.append("⚠️ Project health is low — consider addressing the issues above")
        elif health["score"] < 80:
            insights.append("💡 Project could be improved with better documentation or tests")

        # Size-based insights
        total_files = metrics.get("total_files", 0)
        if total_files > 100:
            insights.append(f"📁 Large project ({total_files} files) — use search_files to find specific code")
        elif total_files < 5:
            insights.append("📁 Small project — read all files to understand the codebase")

        # Language insights
        langs = metrics.get("languages", {})
        if "Python" in langs:
            py_lines = langs["Python"].get("total_lines", 0)
            if py_lines > 5000:
                insights.append("🐍 Large Python codebase — consider using AST for code navigation")

        # Depth insights
        max_depth = metrics.get("max_depth", 0)
        if max_depth > 6:
            insights.append("📂 Deep directory structure — use list_directory to navigate")

        # Missing test insight
        if any("No test" in issue for issue in health.get("issues", [])):
            insights.append("🧪 No tests found — the agent should verify changes carefully")

        return insights
