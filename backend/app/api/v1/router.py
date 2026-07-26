from fastapi import APIRouter

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


@router.get("/ready", tags=["system"])
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/version", tags=["system"])
async def version() -> dict[str, str]:
    return {"name": "ADPathLens", "version": "0.1.0"}
