from __future__ import annotations

import asyncio
import os
import socket
import uuid
from contextlib import suppress
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal, engine
from app.models import ExecutionJob
from app.services.coordinator import coordinator

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger()


async def claim_next_job(worker_id: str) -> str | None:
    async with SessionLocal() as db:
        candidate = (
            select(ExecutionJob.id)
            .where(
                ExecutionJob.status == "queued",
                ExecutionJob.cancellation_requested.is_(False),
            )
            .order_by(ExecutionJob.created_at, ExecutionJob.id)
            .limit(1)
            .scalar_subquery()
        )
        now = datetime.now(UTC)
        claimed = (
            await db.execute(
                update(ExecutionJob)
                .where(
                    ExecutionJob.id == candidate,
                    ExecutionJob.status == "queued",
                )
                .values(
                    status="claimed",
                    worker_id=worker_id,
                    claimed_at=now,
                    heartbeat_at=now,
                    attempt_count=ExecutionJob.attempt_count + 1,
                )
                .returning(ExecutionJob.id)
            )
        ).scalar_one_or_none()
        await db.commit()
        return claimed


async def cancel_pending_jobs() -> int:
    async with SessionLocal() as db:
        job_ids = (
            (
                await db.execute(
                    select(ExecutionJob.id).where(
                        ExecutionJob.status == "cancelling",
                        ExecutionJob.worker_id.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
    for job_id in job_ids:
        await coordinator.finalize_cancelled(job_id)
    return len(job_ids)


async def heartbeat(job_id: str, worker_id: str, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.replay_worker_heartbeat_seconds)
        except TimeoutError:
            async with SessionLocal() as db:
                await db.execute(
                    update(ExecutionJob)
                    .where(
                        ExecutionJob.id == job_id,
                        ExecutionJob.worker_id == worker_id,
                        ExecutionJob.status.in_(["claimed", "running", "cancelling"]),
                    )
                    .values(heartbeat_at=datetime.now(UTC))
                )
                await db.commit()


async def run_claimed_job(job_id: str, worker_id: str) -> None:
    stop = asyncio.Event()
    heartbeat_task = asyncio.create_task(
        heartbeat(job_id, worker_id, stop),
        name=f"authzdiff-heartbeat-{job_id}",
    )
    try:
        await coordinator.execute(job_id, worker_id=worker_id)
    finally:
        stop.set()
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task


async def run_worker() -> None:
    worker_id = (
        os.environ.get("AUTHZDIFF_WORKER_ID")
        or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    )
    recovered = await coordinator.recover_stale()
    logger.info("replay_worker_started", worker_id=worker_id, stale_jobs_recovered=recovered)
    try:
        while True:
            await cancel_pending_jobs()
            job_id = await claim_next_job(worker_id)
            if job_id is None:
                await asyncio.sleep(settings.replay_worker_poll_ms / 1000)
                continue
            logger.info("replay_job_claimed", worker_id=worker_id, job_id=job_id)
            await run_claimed_job(job_id, worker_id)
    finally:
        await engine.dispose()
        logger.info("replay_worker_stopped", worker_id=worker_id)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
