"""Search routes - advanced search across sessions and code."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    pattern: str
    search_type: str = "text"
    case_sensitive: bool = False
    scope: str = "all"
    limit: int = 50


class SaveQueryRequest(BaseModel):
    name: str
    pattern: str
    search_type: str = "text"
    case_sensitive: bool = False
    scope: str = "all"


@router.post("")
async def search(req: SearchRequest) -> dict:
    """Search across all sessions."""
    from ggufloader.core.agent.advanced_search import AdvancedSearch
    searcher = AdvancedSearch()
    results = searcher.search(
        req.pattern,
        search_type=req.search_type,
        case_sensitive=req.case_sensitive,
        scope=req.scope,
        limit=req.limit,
    )
    return {"query": req.pattern, "results": results, "count": len(results)}


@router.get("/queries")
async def list_queries() -> list:
    """List saved search queries."""
    from ggufloader.core.agent.advanced_search import AdvancedSearch
    searcher = AdvancedSearch()
    return searcher.list_queries()


@router.post("/queries")
async def save_query(req: SaveQueryRequest) -> dict:
    """Save a search query."""
    from ggufloader.core.agent.advanced_search import AdvancedSearch
    searcher = AdvancedSearch()
    q = searcher.save_query(req.name, req.pattern, req.search_type, req.case_sensitive, req.scope)
    return {"status": "saved", **q.to_dict()}


@router.delete("/queries/{query_id}")
async def delete_query(query_id: str) -> dict:
    """Delete a saved query."""
    from ggufloader.core.agent.advanced_search import AdvancedSearch
    searcher = AdvancedSearch()
    deleted = searcher.delete_query(query_id)
    return {"status": "deleted" if deleted else "not_found"}


@router.get("/history")
async def search_history(limit: int = 20) -> list:
    """Get recent search history."""
    from ggufloader.core.agent.advanced_search import AdvancedSearch
    searcher = AdvancedSearch()
    return searcher.get_history(limit)


@router.delete("/history")
async def clear_history() -> dict:
    """Clear search history."""
    from ggufloader.core.agent.advanced_search import AdvancedSearch
    searcher = AdvancedSearch()
    searcher.clear_history()
    return {"status": "cleared"}


@router.get("/plugin-watcher/status")
async def plugin_watcher_status() -> dict:
    """Get plugin watcher status."""
    return {"watching": False, "message": "Plugin watcher is managed by the agent process"}
