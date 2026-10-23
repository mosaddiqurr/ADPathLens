import os
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.deps import DB
from app.api.v1.routers import (
    administration,
    analysis,
    auth,
    comparisons,
    findings,
    graph,
    projects,
    remediation,
    reports,
    users,
    workspaces,
)
from app.core.config import get_settings
from app.graph.catalog import RELATIONSHIP_CATALOG
from app.models.entities import Project, RemediationAction

router = APIRouter()
router.include_router(administration.router)
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(workspaces.router)
router.include_router(projects.router)
router.include_router(graph.router)
router.include_router(analysis.router)
router.include_router(findings.router)
router.include_router(remediation.router)
router.include_router(comparisons.router)
router.include_router(reports.router)


@router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/ready", tags=["system"], response_model=dict[str, object])
async def ready(db: DB) -> Any:
    checks: dict[str, dict[str, object]] = {}
    try:
        await db.scalar(select(Project.id).limit(1))
        await db.scalar(select(RemediationAction.progress_percent).limit(1))
        checks["database"] = {"status": "healthy"}
    except Exception:
        checks["database"] = {"status": "unavailable", "code": "database_unavailable"}
    report_root = get_settings().report_storage_path.resolve()
    storage_ready = report_root.is_dir() and os.access(report_root, os.W_OK)
    checks["report_storage"] = {
        "status": "healthy" if storage_ready else "unavailable",
        "code": None if storage_ready else "report_storage_unavailable",
    }
    checks["graph_catalog"] = {
        "status": "healthy" if RELATIONSHIP_CATALOG else "unavailable",
        "relationship_types": len(RELATIONSHIP_CATALOG),
    }
    ready_state = all(check["status"] == "healthy" for check in checks.values())
    payload: dict[str, object] = {
        "status": "ready" if ready_state else "not_ready",
        "checks": checks,
    }
    if not ready_state:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/version", tags=["system"])
async def version() -> dict[str, str]:
    return {"name": "ADPathLens", "version": "1.0.0-rc1"}
