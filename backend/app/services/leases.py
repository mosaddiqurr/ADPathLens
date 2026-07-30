from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConcurrencyLease


async def acquire_lease(
    db: AsyncSession,
    *,
    scope_type: str,
    scope_id: str,
    slots: int,
    holder_id: str,
    ttl_seconds: int,
) -> bool:
    """Atomically claim one bounded slot using the database uniqueness constraint."""
    now = datetime.now(UTC)
    await db.execute(delete(ConcurrencyLease).where(ConcurrencyLease.expires_at <= now))
    for slot in range(slots):
        try:
            async with db.begin_nested():
                db.add(
                    ConcurrencyLease(
                        scope_type=scope_type,
                        scope_id=scope_id,
                        slot=slot,
                        holder_id=holder_id,
                        expires_at=now + timedelta(seconds=ttl_seconds),
                    )
                )
                await db.flush()
            return True
        except IntegrityError:
            continue
    return False


async def release_leases(db: AsyncSession, holder_id: str) -> None:
    await db.execute(delete(ConcurrencyLease).where(ConcurrencyLease.holder_id == holder_id))
