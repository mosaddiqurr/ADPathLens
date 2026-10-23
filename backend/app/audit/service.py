from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AuditEvent, User


async def record_audit(
    db: AsyncSession,
    request: Request,
    action: str,
    entity_type: str,
    summary: str,
    *,
    user: User | None = None,
    entity_id: str | None = None,
    project_id: str | None = None,
    outcome: str = "success",
    context: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        user_id=user.id if user else None,
        project_id=project_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary[:1000],
        source_ip=request.client.host if request.client else None,
        outcome=outcome[:32],
        correlation_id=getattr(request.state, "request_id", None),
        context_json=context or {},
    )
    db.add(event)
    return event
