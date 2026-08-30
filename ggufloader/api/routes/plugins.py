"""Plugin routes - manage agent plugins and marketplace."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

# Built-in plugin catalog (known plugins with metadata)
_BUILTIN_CATALOG = [
    {
        "id": "docker",
        "name": "Docker Manager",
        "description": "Manage Docker containers, images, and compose stacks from the agent",
        "category": "devops",
        "icon": "🐳",
        "author": "ggufloader",
        "version": "1.0.0",
        "tags": ["docker", "containers", "devops"],
        "install_command": "docker",
        "tool_count": 3,
    },
    {
        "id": "database",
        "name": "Database Query",
        "description": "Query SQLite and PostgreSQL databases with natural language",
        "category": "data",
        "icon": "🗄️",
        "author": "ggufloader",
        "version": "1.0.0",
        "tags": ["sql", "database", "query"],
        "install_command": "database",
        "tool_count": 2,
    },
    {
        "id": "web-scraper",
        "name": "Web Scraper",
        "description": "Scrape web pages and extract structured data for the agent",
        "category": "web",
        "icon": "🌐",
        "author": "ggufloader",
        "version": "1.0.0",
        "tags": ["web", "scraping", "http"],
        "install_command": "web-scraper",
        "tool_count": 2,
    },
    {
        "id": "image-gen",
        "name": "Image Generator",
        "description": "Generate images using Stable Diffusion or DALL-E APIs",
        "category": "creative",
        "icon": "🎨",
        "author": "ggufloader",
        "version": "1.0.0",
        "tags": ["image", "generation", "stable-diffusion"],
        "install_command": "image-gen",
        "tool_count": 1,
    },
    {
        "id": "email",
        "name": "Email Sender",
        "description": "Send and draft emails via SMTP or Gmail API",
        "category": "productivity",
        "icon": "📧",
        "author": "ggufloader",
        "version": "1.0.0",
        "tags": ["email", "smtp", "gmail"],
        "install_command": "email",
        "tool_count": 2,
    },
    {
        "id": "git-advanced",
        "name": "Git Advanced",
        "description": "Advanced git operations: bisect, rebase, interactive stash, PR creation",
        "category": "devops",
        "icon": "📦",
        "author": "ggufloader",
        "version": "1.0.0",
        "tags": ["git", "version-control", "github"],
        "install_command": "git-advanced",
        "tool_count": 4,
    },
    {
        "id": "testing",
        "name": "Test Runner",
        "description": "Run pytest, jest, go test and report results with coverage analysis",
        "category": "devops",
        "icon": "🧪",
        "author": "ggufloader",
        "version": "1.0.0",
        "tags": ["testing", "pytest", "jest"],
        "install_command": "testing",
        "tool_count": 3,
    },
    {
        "id": "pdf-tools",
        "name": "PDF Tools",
        "description": "Create, merge, split, and extract text from PDF files",
        "category": "files",
        "icon": "📄",
        "author": "ggufloader",
        "version": "1.0.0",
        "tags": ["pdf", "document", "extract"],
        "install_command": "pdf-tools",
        "tool_count": 3,
    },
]


@router.get("")
async def list_plugins() -> List[dict]:
    """List all installed plugins with metadata."""
    from ggufloader.api.deps import get_workspace
    from ggufloader.core.agent.plugin_manager import PluginManager

    workspace = Path(get_workspace()) if get_workspace() else Path(".")
    pm = PluginManager(workspace)
    loaded = pm.get_loaded()
    discovered = pm.discover()

    plugins = []
    for p in loaded:
        source = loaded[p]
        # Try to read metadata from the plugin file
        meta = _read_plugin_meta(Path(source)) if source else {}
        plugins.append({
            "id": p,
            "name": meta.get("name", p),
            "description": meta.get("description", ""),
            "category": meta.get("category", "other"),
            "icon": meta.get("icon", "🔧"),
            "status": "loaded",
            "enabled": True,
            "source": source,
            "type": Path(source).suffix if source else "unknown",
        })
    return plugins


@router.get("/stats")
async def plugin_stats() -> dict:
    """Get plugin statistics."""
    from ggufloader.api.deps import get_workspace
    from ggufloader.core.agent.plugin_manager import PluginManager

    workspace = Path(get_workspace()) if get_workspace() else Path(".")
    pm = PluginManager(workspace)
    loaded = pm.get_loaded()
    discovered = pm.discover()
    return {
        "total": len(loaded),
        "loaded": len(loaded),
        "discovered": len(discovered),
        "failed": max(0, len(discovered) - len(loaded)),
    }


@router.get("/catalog")
async def plugin_catalog(category: Optional[str] = None) -> List[dict]:
    """Browse available plugins from the built-in catalog."""
    from ggufloader.api.deps import get_workspace
    from ggufloader.core.agent.plugin_manager import PluginManager

    workspace = Path(get_workspace()) if get_workspace() else Path(".")
    pm = PluginManager(workspace)
    loaded = pm.get_loaded()

    catalog = []
    for item in _BUILTIN_CATALOG:
        if category and item["category"] != category:
            continue
        installed = item["id"] in loaded or item["name"] in loaded
        catalog.append({
            **item,
            "installed": installed,
        })
    return catalog


@router.get("/catalog/categories")
async def plugin_categories() -> List[dict]:
    """Get plugin categories with counts."""
    categories = {}
    for item in _BUILTIN_CATALOG:
        cat = item["category"]
        if cat not in categories:
            categories[cat] = {"name": cat, "count": 0, "icon": _CATEGORY_ICONS.get(cat, "📁")}
        categories[cat]["count"] += 1
    return list(categories.values())


_CATEGORY_ICONS = {
    "devops": "⚙️",
    "data": "📊",
    "web": "🌐",
    "creative": "🎨",
    "productivity": "📈",
    "files": "📁",
    "other": "🔧",
}


@router.post("/{name}/enable")
async def enable_plugin(name: str) -> dict:
    """Enable a plugin."""
    return {"name": name, "status": "enabled"}


@router.post("/{name}/disable")
async def disable_plugin(name: str) -> dict:
    """Disable a plugin."""
    return {"name": name, "status": "disabled"}


def _read_plugin_meta(path: Path) -> dict:
    """Try to read metadata from a plugin file."""
    try:
        if path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            return {
                "name": data.get("name", path.stem),
                "description": data.get("description", ""),
                "category": data.get("category", "other"),
                "icon": data.get("icon", "🔧"),
            }
    except Exception:
        pass
    return {}
