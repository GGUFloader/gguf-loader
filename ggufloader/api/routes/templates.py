"""Template routes - manage prompt templates."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ggufloader.api.deps import get_workspace

router = APIRouter()
logger = logging.getLogger(__name__)


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    template: str
    variables: List[str] = []
    category: str = "general"
    tags: List[str] = []


class TemplateRender(BaseModel):
    template_id: str
    variables: dict = {}


@router.get("")
async def list_templates(category: Optional[str] = None) -> List[dict]:
    """List all templates, optionally filtered by category."""
    from pathlib import Path
    from ggufloader.core.agent.templates import TemplateManager

    workspace = Path(get_workspace()) if get_workspace() else None
    mgr = TemplateManager(workspace)
    if category:
        templates = mgr.list_by_category(category)
    else:
        templates = mgr.list_all()
    return [t.to_dict() for t in templates]


@router.get("/categories")
async def list_categories() -> List[dict]:
    """Get template categories with counts."""
    from pathlib import Path
    from ggufloader.core.agent.templates import TemplateManager

    workspace = Path(get_workspace()) if get_workspace() else None
    mgr = TemplateManager(workspace)
    return mgr.get_categories()


@router.get("/search")
async def search_templates(q: str = "") -> List[dict]:
    """Search templates by query."""
    from pathlib import Path
    from ggufloader.core.agent.templates import TemplateManager

    workspace = Path(get_workspace()) if get_workspace() else None
    mgr = TemplateManager(workspace)
    results = mgr.search(q) if q else mgr.list_all()
    return [t.to_dict() for t in results]


@router.get("/{template_id}")
async def get_template(template_id: str) -> dict:
    """Get a single template by ID."""
    from pathlib import Path
    from ggufloader.core.agent.templates import TemplateManager

    workspace = Path(get_workspace()) if get_workspace() else None
    mgr = TemplateManager(workspace)
    t = mgr.get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return t.to_dict()


@router.post("")
async def create_template(req: TemplateCreate) -> dict:
    """Create a new custom template."""
    from pathlib import Path
    from ggufloader.core.agent.templates import TemplateManager, PromptTemplate

    workspace = Path(get_workspace()) if get_workspace() else None
    mgr = TemplateManager(workspace)

    template_id = req.name.lower().replace(" ", "_").replace("-", "_")
    t = PromptTemplate(
        template_id=template_id,
        name=req.name,
        description=req.description,
        template=req.template,
        variables=req.variables,
        category=req.category,
        tags=req.tags,
    )
    mgr.save(t)
    return {"status": "created", "id": template_id}


@router.post("/render")
async def render_template(req: TemplateRender) -> dict:
    """Render a template with variable substitution."""
    from pathlib import Path
    from ggufloader.core.agent.templates import TemplateManager

    workspace = Path(get_workspace()) if get_workspace() else None
    mgr = TemplateManager(workspace)
    t = mgr.get(req.template_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Template '{req.template_id}' not found")

    missing = t.missing_variables(**req.variables)
    rendered = t.render(**req.variables)
    return {
        "rendered": rendered,
        "missing_variables": missing,
        "template_id": req.template_id,
    }


@router.post("/compose")
async def compose_templates(ids: List[str], variables: dict = {}) -> dict:
    """Compose multiple templates into one prompt."""
    from pathlib import Path
    from ggufloader.core.agent.templates import TemplateManager

    workspace = Path(get_workspace()) if get_workspace() else None
    mgr = TemplateManager(workspace)
    result = mgr.compose(ids, **variables)
    return {"composed": result, "template_ids": ids}


@router.delete("/{template_id}")
async def delete_template(template_id: str) -> dict:
    """Delete a custom template (cannot delete builtins)."""
    from pathlib import Path
    from ggufloader.core.agent.templates import TemplateManager

    workspace = Path(get_workspace()) if get_workspace() else None
    mgr = TemplateManager(workspace)
    deleted = mgr.delete(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found or is built-in")
    return {"status": "deleted", "id": template_id}
