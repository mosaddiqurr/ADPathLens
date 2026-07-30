from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CsrfContextDep, DbDep, SettingsDep
from app.audit.service import record_audit
from app.core.config import Settings, get_settings
from app.core.problems import ApiProblem
from app.db.session import get_db
from app.services.authorization import project_for_user

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    name: str
    version: str


class DemoResetRequest(BaseModel):
    project_id: str


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", name=settings.app_name, version=settings.app_version)


@router.get("/ready", response_model=HealthResponse)
async def ready(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    await db.execute(text("SELECT 1"))
    return HealthResponse(status="ready", name=settings.app_name, version=settings.app_version)


@router.get("/version", response_model=HealthResponse)
async def version(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", name=settings.app_name, version=settings.app_version)


@router.get("/capabilities")
async def capabilities() -> dict[str, object]:
    return {
        "request_imports": ["manual", "raw_http", "curl", "har_preview"],
        "report_formats": ["json", "csv", "html", "pdf"],
        "comparison_profiles": {"minimum": 2, "maximum_per_test_case": 2},
        "state_changing_requests": "explicit_opt_in_only",
        "automatic_discovery": False,
        "automatic_exploitation": False,
    }


@router.post("/demo/reset")
async def reset_demo_target(
    payload: DemoResetRequest,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> dict[str, str]:
    await project_for_user(db, context.user, payload.project_id)
    if settings.app_env == "production" or not settings.demo_mode:
        raise ApiProblem(403, "demo_reset_disabled", "Demo reset is disabled.")
    try:
        async with httpx.AsyncClient(
            timeout=5,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = await client.post(
                f"{settings.demo_target_url.rstrip('/')}/internal/reset",
                headers={"X-Demo-Reset-Token": settings.demo_reset_token},
            )
    except httpx.HTTPError as exc:
        raise ApiProblem(
            503,
            "demo_target_unavailable",
            "The isolated demo target is unavailable.",
        ) from exc
    if response.status_code != 200:
        raise ApiProblem(502, "demo_reset_failed", "The isolated demo target refused reset.")
    await record_audit(
        db,
        request,
        action="demo_reset",
        entity_type="demo_target",
        entity_id=None,
        project_id=payload.project_id,
        user_id=context.user.id,
        summary="Reset deterministic synthetic demo fixtures.",
    )
    await db.commit()
    return {"status": "reset"}
