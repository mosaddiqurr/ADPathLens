from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.dependencies import AdminUserDep, CsrfContextDep, DbDep
from app.audit.service import record_audit
from app.core.problems import ApiProblem
from app.models import AppSetting, AuditEvent
from app.schemas.core import AuditEventRead, SettingsRead, SettingsUpdate

router = APIRouter(tags=["administration"])


async def _settings(db: DbDep) -> AppSetting:
    settings = (
        await db.execute(select(AppSetting).where(AppSetting.singleton_key == "global"))
    ).scalar_one_or_none()
    if settings is None:
        raise ApiProblem(409, "setup_required", "Initial administrator setup is required.")
    return settings


@router.get("/settings", response_model=SettingsRead)
async def get_application_settings(db: DbDep, _admin: AdminUserDep) -> SettingsRead:
    settings = await _settings(db)
    return SettingsRead.model_validate(settings)


@router.patch("/settings", response_model=SettingsRead)
async def update_application_settings(
    payload: SettingsUpdate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> SettingsRead:
    if context.user.role != "administrator":
        raise ApiProblem(403, "administrator_required", "Administrator access is required.")
    settings = await _settings(db)
    settings.global_state_changes_enabled = payload.global_state_changes_enabled
    settings.updated_by = context.user.id
    settings.updated_at = datetime.now(UTC)
    await record_audit(
        db,
        request,
        action="settings_changed",
        entity_type="app_settings",
        entity_id=settings.id,
        user_id=context.user.id,
        summary="Changed global state-changing request policy.",
    )
    await db.commit()
    await db.refresh(settings)
    return SettingsRead.model_validate(settings)


@router.get("/audit-events", response_model=list[AuditEventRead])
async def list_audit_events(
    db: DbDep,
    _admin: AdminUserDep,
    action: str | None = None,
    user_id: str | None = None,
    entity_type: str | None = None,
    outcome: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[AuditEventRead]:
    limit = min(max(limit, 1), 500)
    offset = min(max(offset, 0), 100_000)
    statement = select(AuditEvent)
    if action:
        statement = statement.where(AuditEvent.action == action)
    if user_id:
        statement = statement.where(AuditEvent.user_id == user_id)
    if entity_type:
        statement = statement.where(AuditEvent.entity_type == entity_type)
    if outcome:
        statement = statement.where(AuditEvent.outcome == outcome)
    if date_from:
        statement = statement.where(AuditEvent.created_at >= date_from)
    if date_to:
        statement = statement.where(AuditEvent.created_at <= date_to)
    events = (
        (
            await db.execute(
                statement.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [AuditEventRead.model_validate(event) for event in events]


@router.get("/audit-events/export")
async def export_audit_events(db: DbDep, _admin: AdminUserDep) -> StreamingResponse:
    events = (
        (await db.execute(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(10_000)))
        .scalars()
        .all()
    )
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "created_at",
            "action",
            "outcome",
            "entity_type",
            "entity_id",
            "project_id",
            "user_id",
            "summary",
            "correlation_id",
            "source_ip",
        ]
    )
    for event in events:
        writer.writerow(
            [
                event.created_at.isoformat(),
                event.action,
                event.outcome,
                event.entity_type,
                event.entity_id or "",
                event.project_id or "",
                event.user_id or "",
                event.summary,
                event.correlation_id or "",
                event.source_ip or "",
            ]
        )
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="authzdiff-audit.csv"'},
    )
