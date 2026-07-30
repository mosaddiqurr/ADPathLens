from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


async def record_audit(
    db: AsyncSession,
    request: Request,
    *,
    action: str,
    entity_type: str,
    summary: str,
    user_id: str | None = None,
    entity_id: str | None = None,
    project_id: str | None = None,
    outcome: str = "success",
    safe_metadata: dict[str, object] | None = None,
) -> AuditEvent:
    source_ip = request.client.host if request.client else None
    event = AuditEvent(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        project_id=project_id,
        outcome=outcome,
        summary=summary[:500],
        safe_metadata=safe_metadata or {},
        source_ip=source_ip,
        request_id=getattr(request.state, "request_id", None),
        correlation_id=getattr(request.state, "request_id", None),
        created_at=datetime.now(UTC),
    )
    db.add(event)
    return event
