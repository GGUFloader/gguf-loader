"""Benchmark routes - model performance benchmarking."""

from __future__ import annotations

import logging

from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/prompts")
async def list_prompts() -> list:
    """List available benchmark prompts."""
    from ggufloader.core.agent.benchmark import ModelBenchmark
    bm = ModelBenchmark()
    return bm.list_prompts()


@router.get("/history")
async def benchmark_history(limit: int = 20) -> list:
    """Get benchmark history."""
    from ggufloader.core.agent.benchmark import ModelBenchmark
    bm = ModelBenchmark()
    return bm.get_history(limit)


@router.get("/reports")
async def list_reports() -> list:
    """List saved benchmark reports."""
    from ggufloader.core.agent.benchmark import ModelBenchmark
    bm = ModelBenchmark()
    return bm.list_reports()


@router.get("/reports/{report_id}")
async def get_report(report_id: str) -> dict:
    """Get a benchmark report."""
    from ggufloader.core.agent.benchmark import ModelBenchmark
    bm = ModelBenchmark()
    report = bm.get_report(report_id)
    if not report:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Report not found")
    return report
