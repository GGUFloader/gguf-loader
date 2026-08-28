"""
DocsGenerator - Generate comprehensive agent documentation.

Pattern from: Aider's docs/ + Claude Code's CLAUDE.md generator.
Automatically generates documentation from the feature index,
code structure, and configuration:
- User guide (markdown)
- API reference (module listing)
- Configuration reference
- Feature matrix
- Getting started guide
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .feature_index import FEATURES, get_feature_count, get_features_by_phase
from .presets import PRESETS

logger = logging.getLogger(__name__)


class DocsGenerator:
    """Generate comprehensive documentation.

    Usage:
        gen = DocsGenerator(workspace_path)
        gen.generate_all()
        # Writes docs/ directory with all documentation
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._docs_dir = workspace / "docs" / "agent"

    def generate_all(self) -> Dict[str, str]:
        """Generate all documentation files."""
        self._docs_dir.mkdir(parents=True, exist_ok=True)
        files = {}

        files["README.md"] = self._write_file("README.md", self._generate_readme())
        files["FEATURES.md"] = self._write_file("FEATURES.md", self._generate_features())
        files["CONFIGURATION.md"] = self._write_file("CONFIGURATION.md", self._generate_config())
        files["PRESETS.md"] = self._write_file("PRESETS.md", self._generate_presets())
        files["API.md"] = self._write_file("API.md", self._generate_api())

        logger.info("Generated %d doc files in %s", len(files), self._docs_dir)
        return files

    def _write_file(self, name: str, content: str) -> str:
        filepath = self._docs_dir / name
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def _generate_readme(self) -> str:
        counts = get_feature_count()
        return f"""# GGUFLoader Agent — User Guide

> Auto-generated documentation for the GGUFLoader Agent System

## Overview

The GGUFLoader Agent is a local AI coding agent with **{counts['total']} features**
across {len(counts['by_phase'])} implementation phases.

## Quick Start

1. **Load a model** — Select a GGUF model file from the sidebar
2. **Enable Agent Mode** — Toggle the Agent Mode button
3. **Select a preset** — Choose from 6 task-specific presets
4. **Start chatting** — Type your request and the agent will use tools to help

## Agent Modes

| Mode | Icon | Description |
|------|------|-------------|
| Research | 🔍 | Read-only exploration |
| Code Review | 📝 | Structured analysis |
| Refactor | ♻️ | Safe refactoring with verify |
| Debug | 🐛 | Error diagnosis |
| Full Stack | 🚀 | All tools enabled |
| Quick Fix | ⚡ | Fast minimal changes |

## Available Tools

- **list_directory** — List files and folders
- **read_file** — Read text/PDF/DOCX files
- **write_file** — Create or overwrite files
- **edit_file** — Modify files with replace/insert/delete
- **search_files** — Search for text in files
- **run_command** — Execute shell commands (requires approval)
- **run_python** — Execute Python code (requires approval)
- **git** — Git operations (writes require approval)
- **batch_execute** — Run multiple tools in sequence
- **python_interpreter** — Sandboxed Python execution

## Slash Commands

| Command | Description |
|---------|-------------|
| /add | Add file to context |
| /drop | Remove file from context |
| /clear | Clear chat |
| /undo | Undo last change |
| /help | Show help |
| /map | Show workspace map |
| /diff | Show recent changes |
| /memory | Show agent memory |
| /status | Show agent status |
| /export | Export conversation |

## Configuration

Create `.ggufloader.json` in your project root:

```json
{{
  "agent": {{
    "max_steps": 8,
    "temperature": 0.1,
    "preset": "full_stack"
  }},
  "tools": {{
    "auto_approve_read": true,
    "auto_approve_write": false
  }}
}}
```

## Features

See `FEATURES.md` for the complete feature catalog.
"""

    def _generate_features(self) -> str:
        lines = ["# Feature Catalog\n"]
        lines.append(f"**Total: {len(FEATURES)} features**\n")

        for phase in range(1, 15):
            features = get_features_by_phase(phase)
            if not features:
                continue
            lines.append(f"\n## Phase {phase} ({len(features)} features)\n")
            lines.append("| ID | Name | Module | Status | Tags |")
            lines.append("|----|------|--------|--------|------|")
            for f in features:
                tags = ", ".join(f.tags)
                lines.append(f"| {f.id} | **{f.name}** | `{f.module}` | {f.status} | {tags} |")

        return "\n".join(lines)

    def _generate_config(self) -> str:
        return """# Configuration Reference

## Config File Locations

1. **Project-level**: `.ggufloader.json` in project root
2. **Global**: `~/.ggufloader/config.json`
3. **Environment**: `GGUF_AGENT_*` variables

## Configuration Sections

### Agent Behavior

| Key | Default | Description |
|-----|---------|-------------|
| agent.max_steps | 8 | Maximum agent loop iterations |
| agent.max_tokens | 2048 | Max tokens per LLM response |
| agent.temperature | 0.1 | Sampling temperature |
| agent.json_retries | 2 | Retries for malformed JSON |
| agent.preset | full_stack | Default agent preset |

### Tool Permissions

| Key | Default | Description |
|-----|---------|-------------|
| tools.auto_approve_read | true | Auto-approve read-only tools |
| tools.auto_approve_write | false | Auto-approve file writes |
| tools.auto_approve_command | false | Auto-approve shell commands |
| tools.blocked_commands | [...] | Commands that are never allowed |

### Context Management

| Key | Default | Description |
|-----|---------|-------------|
| context.budget_tokens | 8192 | Token budget for conversation |
| context.system_prompt_tokens | 500 | Reserved for system prompt |

### Features

| Key | Default | Description |
|-----|---------|-------------|
| features.mcp_enabled | false | Enable MCP tool servers |
| features.plugins_enabled | true | Enable custom plugins |
| features.memory_enabled | true | Enable persistent memory |
| features.knowledge_enabled | true | Enable knowledge base |
| features.health_enabled | true | Enable health monitoring |
| features.audit_enabled | true | Enable audit logging |

### Environment Variable Overrides

| Variable | Config Key |
|----------|------------|
| GGUF_AGENT_MAX_STEPS | agent.max_steps |
| GGUF_AGENT_TEMPERATURE | agent.temperature |
| GGUF_AGENT_MAX_TOKENS | agent.max_tokens |
"""

    def _generate_presets(self) -> str:
        lines = ["# Agent Presets\n"]
        lines.append("| Preset | Icon | Max Steps | Temp | Auto-Commit | Auto-Test |")
        lines.append("|--------|------|-----------|------|-------------|-----------|")
        for pid, preset in PRESETS.items():
            lines.append(
                f"| **{preset.name}** | {preset.icon} | {preset.max_steps} | "
                f"{preset.temperature} | {'✅' if preset.auto_commit else '❌'} | "
                f"{'✅' if preset.auto_test else '❌'} |"
            )

        lines.append("\n## Preset Descriptions\n")
        for pid, preset in PRESETS.items():
            lines.append(f"### {preset.icon} {preset.name}")
            lines.append(f"{preset.description}\n")
            if preset.system_prompt_addition:
                lines.append("**System prompt addition:**")
                lines.append(f"```{preset.system_prompt_addition}```\n")

        return "\n".join(lines)

    def _generate_api(self) -> str:
        return """# API Reference

## Core Classes

### AgentEngine
Main agent loop. Processes user messages through multi-step tool execution.

```python
from ggufloader.core.agent import AgentEngine

engine = AgentEngine(llm=my_llm_fn, workspace="/path/to/project")
result = engine.process("Read the README")
print(result["response"])
```

### ToolRegistry
Registry of sandboxed tools bound to a workspace.

```python
from ggufloader.core.agent import ToolRegistry

registry = ToolRegistry("/path/to/workspace")
print(registry.names())  # ['list_directory', 'read_file', ...]
result = registry.execute("read_file", {"path": "README.md"})
```

### PluginManager
Load custom tools from JSON or Python files.

```python
from ggufloader.core.agent import PluginManager

pm = PluginManager(workspace)
results = pm.load_all(registry)
```

### ConfigManager
Unified configuration with layered sources.

```python
from ggufloader.core.agent import ConfigManager

mgr = ConfigManager(workspace)
config = mgr.load()
print(config.max_steps)  # 8
```

## PresetManager

```python
from ggufloader.core.agent import PresetManager

pm = PresetManager()
preset = pm.get("debug")
print(preset.system_prompt_addition)
```

## ErrorPatternDetector

```python
from ggufloader.core.agent import ErrorPatternDetector

detector = ErrorPatternDetector(workspace)
detector.record_error("syntax", "invalid syntax at line 5")
patterns = detector.get_patterns()
```

## BenchmarkSuite

```python
from ggufloader.core.agent import BenchmarkSuite

suite = BenchmarkSuite(agent_fn)
suite.add_all_presets()
report = suite.run_all()
print(report["summary"])
```
"""
