"""
AgentsMd - Auto-generate AGENTS.md from workspace scan.

Pattern from: Claude Code's CLAUDE.md + Aider's repo-map.
Scans the workspace to detect project type, structure, dependencies,
and conventions, then generates an AGENTS.md file that gives the agent
context about the project.

Features:
- Auto-detect project type (Python, Node, Rust, Go, etc.)
- Scan directory structure and key files
- Detect dependencies and frameworks
- Generate structured markdown with conventions
- Update existing AGENTS.md without overwriting manual edits
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Project type detection
PROJECT_TYPES = {
    "python": {
        "indicators": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"],
        "test_dirs": ["tests", "test"],
        "src_dirs": ["src", "."],
        "config_files": [".flake8", ".pylintrc", "mypy.ini", ".mypy.ini", "ruff.toml"],
    },
    "node": {
        "indicators": ["package.json"],
        "test_dirs": ["test", "tests", "__tests__", "spec"],
        "src_dirs": ["src", "lib", "."],
        "config_files": [".eslintrc*", "tsconfig.json", ".prettierrc*"],
    },
    "rust": {
        "indicators": ["Cargo.toml"],
        "test_dirs": ["tests"],
        "src_dirs": ["src"],
        "config_files": ["rustfmt.toml", ".clippy.toml"],
    },
    "go": {
        "indicators": ["go.mod"],
        "test_dirs": ["."],
        "src_dirs": ["cmd", "pkg", "internal", "."],
        "config_files": [".golangci.yml"],
    },
}

# File importance markers
IMPORTANT_FILES = {
    "README.md": "Project documentation",
    "CONTRIBUTING.md": "Contribution guidelines",
    "AGENTS.md": "Agent context (auto-generated)",
    "CLAUDE.md": "Claude agent context",
    "Makefile": "Build automation",
    "Dockerfile": "Container configuration",
    "docker-compose.yml": "Multi-container setup",
    ".env.example": "Environment variables template",
    ".gitignore": "Git ignore rules",
}


class AgentsMdGenerator:
    """Generate AGENTS.md from workspace scan.

    Usage:
        gen = AgentsMdGenerator(workspace_path)
        content = gen.generate()
        gen.write()  # writes AGENTS.md to workspace
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._project_type: Optional[str] = None
        self._project_info: Dict[str, Any] = {}

    def scan(self) -> Dict[str, Any]:
        """Scan the workspace and return project info."""
        info: Dict[str, Any] = {
            "type": "unknown",
            "name": self.workspace.name,
            "structure": {},
            "dependencies": [],
            "test_framework": None,
            "linters": [],
            "important_files": [],
            "src_dirs": [],
            "test_dirs": [],
            "languages": set(),
        }

        # Detect project type
        for ptype, config in PROJECT_TYPES.items():
            for indicator in config["indicators"]:
                if (self.workspace / indicator).exists():
                    info["type"] = ptype
                    self._project_type = ptype
                    info["src_dirs"] = config["src_dirs"]
                    info["test_dirs"] = config["test_dirs"]
                    break
            if info["type"] != "unknown":
                break

        # Scan top-level structure
        info["structure"] = self._scan_structure()

        # Detect dependencies
        info["dependencies"] = self._detect_dependencies()

        # Detect languages
        info["languages"] = self._detect_languages()

        # Find important files
        for filename, desc in IMPORTANT_FILES.items():
            if (self.workspace / filename).exists():
                info["important_files"].append({"name": filename, "description": desc})

        # Detect linters
        info["linters"] = self._detect_linters()

        # Detect test framework
        info["test_framework"] = self._detect_test_framework()

        self._project_info = info
        return info

    def generate(self) -> str:
        """Generate AGENTS.md content."""
        if not self._project_info:
            self.scan()

        info = self._project_info
        lines = [
            f"# AGENTS.md — {info['name']}",
            "",
            f"Project type: **{info['type']}**",
            "",
        ]

        # Structure overview
        lines.append("## Project Structure")
        lines.append("")
        for key, value in info.get("structure", {}).items():
            if isinstance(value, list):
                lines.append(f"- **{key}/**: {', '.join(value[:10])}")
            else:
                lines.append(f"- **{key}**: {value}")
        lines.append("")

        # Languages
        if info.get("languages"):
            lines.append("## Languages")
            lines.append("")
            for lang in sorted(info["languages"]):
                lines.append(f"- {lang}")
            lines.append("")

        # Dependencies
        deps = info.get("dependencies", [])
        if deps:
            lines.append("## Key Dependencies")
            lines.append("")
            for dep in deps[:20]:
                lines.append(f"- `{dep}`")
            lines.append("")

        # Test framework
        if info.get("test_framework"):
            lines.append("## Testing")
            lines.append("")
            lines.append(f"Test framework: **{info['test_framework']}**")
            lines.append("")
            lines.append("Run tests with:")
            if info["test_framework"] == "pytest":
                lines.append("```bash")
                lines.append("python -m pytest tests/ -x -q")
                lines.append("```")
            elif info["test_framework"] == "npm":
                lines.append("```bash")
                lines.append("npm test")
                lines.append("```")
            elif info["test_framework"] == "cargo":
                lines.append("```bash")
                lines.append("cargo test")
                lines.append("```")
            elif info["test_framework"] == "go":
                lines.append("```bash")
                lines.append("go test ./...")
                lines.append("```")
            lines.append("")

        # Linters
        if info.get("linters"):
            lines.append("## Code Quality")
            lines.append("")
            lines.append("Linters configured: " + ", ".join(info["linters"]))
            lines.append("")

        # Important files
        if info.get("important_files"):
            lines.append("## Important Files")
            lines.append("")
            for f in info["important_files"]:
                lines.append(f"- **{f['name']}**: {f['description']}")
            lines.append("")

        # Conventions (auto-detected)
        lines.append("## Conventions")
        lines.append("")
        conventions = self._detect_conventions()
        for conv in conventions:
            lines.append(f"- {conv}")
        lines.append("")

        # Agent instructions
        lines.append("## Agent Instructions")
        lines.append("")
        lines.append("- Read existing code before writing new code")
        lines.append("- Match the project's existing style and conventions")
        lines.append("- Run tests after making changes")
        lines.append("- Don't modify files outside the project without asking")
        lines.append("- If unsure about a change, ask the user")

        return "\n".join(lines)

    def write(self, force: bool = False) -> bool:
        """Write AGENTS.md to the workspace.

        Args:
            force: Overwrite existing AGENTS.md

        Returns:
            True if written, False if skipped (exists and not forced).
        """
        agents_file = self.workspace / "AGENTS.md"
        if agents_file.exists() and not force:
            logger.info("AGENTS.md already exists, skipping (use force=True to overwrite)")
            return False

        content = self.generate()
        agents_file.write_text(content, encoding="utf-8")
        logger.info("Wrote AGENTS.md (%d bytes)", len(content))
        return True

    def _scan_structure(self) -> Dict[str, Any]:
        """Scan top-level directory structure."""
        structure: Dict[str, Any] = {}
        try:
            for item in sorted(self.workspace.iterdir()):
                if item.name.startswith(".") or item.name in ("__pycache__", "node_modules"):
                    continue
                if item.is_dir():
                    # List contents (shallow)
                    try:
                        contents = sorted([f.name for f in item.iterdir() if not f.name.startswith(".")])[:10]
                        structure[item.name] = contents
                    except OSError:
                        structure[item.name] = []
                else:
                    structure[item.name] = "file"
        except OSError:
            pass
        return structure

    def _detect_dependencies(self) -> List[str]:
        """Detect project dependencies."""
        deps = []

        # Python
        req_file = self.workspace / "requirements.txt"
        if req_file.exists():
            try:
                for line in req_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        deps.append(line.split("==")[0].split(">=")[0].split("<=")[0].strip())
            except Exception:
                pass

        # Node
        pkg_file = self.workspace / "package.json"
        if pkg_file.exists():
            try:
                pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
                for key in ("dependencies", "devDependencies"):
                    for name in (pkg.get(key) or {}):
                        deps.append(name)
            except Exception:
                pass

        # Rust
        cargo_file = self.workspace / "Cargo.toml"
        if cargo_file.exists():
            try:
                content = cargo_file.read_text(encoding="utf-8")
                import re
                for m in re.finditer(r'(\w[\w-]*)\s*=\s*"[^"]*"', content):
                    name = m.group(1)
                    if name not in ("name", "version", "edition", "authors", "description", "license"):
                        deps.append(name)
            except Exception:
                pass

        return deps

    def _detect_languages(self) -> set:
        """Detect programming languages by file extensions."""
        ext_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".jsx": "React JSX", ".tsx": "React TSX",
            ".rs": "Rust", ".go": "Go", ".java": "Java",
            ".c": "C", ".cpp": "C++", ".h": "C/C++ Header",
            ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
            ".kt": "Kotlin", ".sh": "Shell", ".bash": "Bash",
        }
        languages = set()
        count = 0
        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv", ".venv")]
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in ext_map:
                    languages.add(ext_map[ext])
                    count += 1
                if count >= 500:  # cap scanning
                    return languages
        return languages

    def _detect_linters(self) -> List[str]:
        """Detect configured linters."""
        linters = []
        checks = [
            (".flake8", "flake8"),
            (".pylintrc", "pylint"),
            ("mypy.ini", "mypy"),
            (".mypy.ini", "mypy"),
            ("ruff.toml", "ruff"),
            (".eslintrc", "eslint"),
            (".eslintrc.js", "eslint"),
            (".eslintrc.json", "eslint"),
            ("tsconfig.json", "typescript"),
            (".prettierrc", "prettier"),
            ("rustfmt.toml", "rustfmt"),
            (".golangci.yml", "golangci-lint"),
        ]
        for filename, name in checks:
            if (self.workspace / filename).exists():
                linters.append(name)
        return linters

    def _detect_test_framework(self) -> Optional[str]:
        """Detect the test framework."""
        checks = [
            ("pytest.ini", "pytest"),
            ("pyproject.toml", "pytest"),  # may have [tool.pytest]
            ("jest.config.js", "jest"),
            ("jest.config.ts", "jest"),
            ("vitest.config.ts", "vitest"),
            ("Cargo.toml", "cargo"),
            ("go.mod", "go"),
        ]
        for filename, framework in checks:
            if (self.workspace / filename).exists():
                return framework
        return None

    def _detect_conventions(self) -> List[str]:
        """Auto-detect coding conventions."""
        conventions = []

        # Check for existing code style
        py_files = list(self.workspace.rglob("*.py"))[:5]
        if py_files:
            # Check quote style
            try:
                content = py_files[0].read_text(encoding="utf-8")[:2000]
                if '"""' in content or "'''" in content:
                    conventions.append("Uses docstrings (triple quotes)")
                if content.count('"') > content.count("'"):
                    conventions.append("Prefers double quotes for strings")
                else:
                    conventions.append("Prefers single quotes for strings")
            except Exception:
                pass

        # Check for type hints
        if py_files:
            try:
                content = py_files[0].read_text(encoding="utf-8")[:3000]
                if "-> " in content or ": str" in content or ": int" in content:
                    conventions.append("Uses Python type hints")
            except Exception:
                pass

        # Check for async
        if py_files:
            try:
                content = py_files[0].read_text(encoding="utf-8")[:3000]
                if "async def" in content or "await " in content:
                    conventions.append("Uses async/await patterns")
            except Exception:
                pass

        conventions.append("Follow existing code patterns in the project")
        return conventions
