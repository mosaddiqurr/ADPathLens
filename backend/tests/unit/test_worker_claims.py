from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import worker
from app.db.base import Base
from app.models import ComparisonRun, ExecutionJob
from app.services import coordinator as coordinator_service


@pytest.fixture
async def worker_sessions(tmp_path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'worker.sqlite').as_posix()}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    original = worker.SessionLocal
    original_coordinator = coordinator_service.SessionLocal
    worker.SessionLocal = sessions
    coordinator_service.SessionLocal = sessions
    try:
        yield sessions
    finally:
        worker.SessionLocal = original
        coordinator_service.SessionLocal = original_coordinator
        await engine.dispose()


@pytest.mark.asyncio
async def test_job_claim_is_atomic(
    worker_sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with worker_sessions() as db:
        job = ExecutionJob(
            project_id="project",
            comparison_run_id="run",
            status="queued",
            requested_by="user",
            request_count=2,
            completed_count=0,
            cancellation_requested=False,
        )
        db.add(job)
        await db.commit()
        job_id = job.id

    claims = await asyncio.gather(
        worker.claim_next_job("worker-one"),
        worker.claim_next_job("worker-two"),
    )
    assert claims.count(job_id) == 1
    assert claims.count(None) == 1

    async with worker_sessions() as db:
        claimed = (
            await db.execute(select(ExecutionJob).where(ExecutionJob.id == job_id))
        ).scalar_one()
        assert claimed.status == "claimed"
        assert claimed.worker_id in {"worker-one", "worker-two"}
        assert claimed.attempt_count == 1
        assert claimed.claimed_at is not None
        assert claimed.heartbeat_at is not None


@pytest.mark.asyncio
async def test_user_cancellation_has_a_distinct_terminal_state(
    worker_sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with worker_sessions() as db:
        run = ComparisonRun(
            test_case_id="case",
            status="cancelling",
            initiated_by="user",
            cancellation_requested=True,
            progress_completed=0,
            progress_total=2,
        )
        db.add(run)
        await db.flush()
        job = ExecutionJob(
            project_id="project",
            comparison_run_id=run.id,
            status="cancelling",
            requested_by="user",
            request_count=2,
            completed_count=0,
            cancellation_requested=True,
        )
        db.add(job)
        await db.commit()
        job_id = job.id
        run_id = run.id

    await coordinator_service.coordinator.finalize_cancelled(job_id)

    async with worker_sessions() as db:
        cancelled_job = await db.get(ExecutionJob, job_id)
        cancelled_run = await db.get(ComparisonRun, run_id)
        assert cancelled_job is not None
        assert cancelled_run is not None
        assert cancelled_job.status == "cancelled"
        assert cancelled_run.status == "cancelled"
        assert cancelled_run.completed_at is not None
