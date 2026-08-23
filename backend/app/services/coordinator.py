from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select

from app.comparison.engine import ENGINE_VERSION, compare_observations
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    AuditEvent,
    ComparisonReview,
    ComparisonRun,
    ConcurrencyLease,
    DiffResult,
    ExecutionJob,
    Finding,
    FindingEvidence,
    FindingStatusHistory,
    ImportedRequest,
    Observation,
    ProjectPolicy,
    Target,
    TestCase,
    TestSession,
)
from app.replay.executor import ReplayError, execute_request
from app.services.leases import release_leases


class RunCoordinator:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._global_semaphore = asyncio.Semaphore(get_settings().replay_global_concurrency)

    async def recover_interrupted(self, *, include_queued: bool = True) -> int:
        now = datetime.now(UTC)
        statuses = ["claimed", "running", "cancelling"]
        if include_queued:
            statuses.append("queued")
        async with SessionLocal() as db:
            jobs = (
                (await db.execute(select(ExecutionJob).where(ExecutionJob.status.in_(statuses))))
                .scalars()
                .all()
            )
            for job in jobs:
                job.status = "interrupted"
                job.error_code = "worker_restarted"
                job.error_message = "The worker restarted before the job completed."
                run = await db.get(ComparisonRun, job.comparison_run_id)
                if run is not None:
                    run.status = "interrupted"
                    run.completed_at = now
                    run.error_code = "worker_restarted"
                    run.error_message = "The worker restarted before the run completed."
                    await release_leases(db, run.id)
            if include_queued:
                await db.execute(delete(ConcurrencyLease))
            await db.commit()
            return len(jobs)

    async def recover_stale(self) -> int:
        settings = get_settings()
        cutoff = datetime.now(UTC) - timedelta(seconds=settings.replay_stale_after_seconds)
        async with SessionLocal() as db:
            stale = (
                (
                    await db.execute(
                        select(ExecutionJob).where(
                            ExecutionJob.status.in_(["claimed", "running", "cancelling"]),
                            or_(
                                ExecutionJob.heartbeat_at < cutoff,
                                (
                                    ExecutionJob.heartbeat_at.is_(None)
                                    & (ExecutionJob.claimed_at < cutoff)
                                ),
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for job in stale:
                job.status = "interrupted"
                job.error_code = "worker_heartbeat_stale"
                job.error_message = "The worker heartbeat expired before completion."
                run = await db.get(ComparisonRun, job.comparison_run_id)
                if run is not None:
                    run.status = "interrupted"
                    run.completed_at = datetime.now(UTC)
                    run.error_code = job.error_code
                    run.error_message = job.error_message
                    await release_leases(db, run.id)
            await db.commit()
            return len(stale)

    def launch(self, job_id: str) -> None:
        if job_id in self._tasks:
            return
        worker_id = f"inprocess:{os.getpid()}"
        task = asyncio.create_task(
            self.execute(job_id, worker_id=worker_id),
            name=f"authzdiff-job-{job_id}",
        )
        self._tasks[job_id] = task
        task.add_done_callback(lambda _task: self._tasks.pop(job_id, None))

    def cancel(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if task is None:
            return False
        task.cancel()
        return True

    async def execute(self, job_id: str, *, worker_id: str) -> None:
        async with self._global_semaphore:
            try:
                await self._execute_inner(job_id, worker_id=worker_id)
            except asyncio.CancelledError:
                await self._mark_cancelled(job_id)
            except ReplayError as exc:
                await self._mark_failed(job_id, exc.code, exc.detail)
            except Exception:
                await self._mark_failed(
                    job_id,
                    "internal_execution_error",
                    "The comparison failed unexpectedly. "
                    "No secret values were retained in this error.",
                )

    async def _execute_inner(self, job_id: str, *, worker_id: str) -> None:
        settings = get_settings()
        async with SessionLocal() as db:
            job = await db.get(ExecutionJob, job_id)
            if job is None:
                return
            if job.status not in {"queued", "claimed", "running", "cancelling"}:
                return
            if job.cancellation_requested:
                raise asyncio.CancelledError
            run = await db.get(ComparisonRun, job.comparison_run_id)
            if run is None:
                return
            test_case = await db.get(TestCase, run.test_case_id)
            if test_case is None:
                await self._mark_failed(
                    job_id, "test_case_missing", "The test case no longer exists."
                )
                return
            target = await db.get(Target, test_case.target_id)
            request_definition = await db.get(ImportedRequest, test_case.imported_request_id)
            high_session = await db.get(TestSession, test_case.high_privilege_session_id)
            low_session = await db.get(TestSession, test_case.low_privilege_session_id)
            if (
                target is None
                or request_definition is None
                or high_session is None
                or low_session is None
            ):
                await self._mark_failed(
                    job_id, "run_dependency_missing", "A run dependency no longer exists."
                )
                return
            project_policy = (
                await db.execute(
                    select(ProjectPolicy).where(ProjectPolicy.project_id == test_case.project_id)
                )
            ).scalar_one_or_none()
            redaction_keys = project_policy.redaction_keys if project_policy else []
            ignored_headers = sorted(
                set(test_case.ignored_headers)
                | set(project_policy.ignored_headers if project_policy else [])
            )
            ignored_text_patterns = sorted(
                set(test_case.ignored_text_patterns)
                | set(project_policy.ignored_text_patterns if project_policy else [])
            )
            job.status = "running"
            job.worker_id = worker_id
            job.claimed_at = job.claimed_at or datetime.now(UTC)
            job.heartbeat_at = datetime.now(UTC)
            if job.attempt_count == 0:
                job.attempt_count = 1
            run.status = "running"
            run.started_at = datetime.now(UTC)
            db.add(
                AuditEvent(
                    user_id=run.initiated_by,
                    action="comparison_started",
                    entity_type="comparison_run",
                    entity_id=run.id,
                    project_id=test_case.project_id,
                    outcome="success",
                    summary="Started a controlled authorization comparison.",
                    safe_metadata={"worker_id": worker_id},
                    correlation_id=job.correlation_id,
                    created_at=datetime.now(UTC),
                )
            )
            await db.commit()
            observations: list[Observation] = []
            for scope, session in (("high", high_session), ("low", low_session)):
                await db.refresh(job)
                if job.cancellation_requested:
                    raise asyncio.CancelledError
                job.heartbeat_at = datetime.now(UTC)
                try:
                    result = await asyncio.wait_for(
                        execute_request(
                            db,
                            test_case=test_case,
                            target=target,
                            request_definition=request_definition,
                            session=session,
                            scope=scope,
                            settings=settings,
                            redaction_keys=redaction_keys,
                        ),
                        timeout=target.per_run_timeout_seconds,
                    )
                    observation = Observation(
                        project_id=test_case.project_id,
                        comparison_run_id=run.id,
                        request_id=request_definition.id,
                        session_id=session.id,
                        status_code=result.status_code,
                        redirect_outcome=("followed" if result.redirect_chain else "none"),
                        content_type=result.content_type,
                        safe_headers=result.normalized.safe_headers,
                        response_length=result.normalized.response_length,
                        duration_ms=result.elapsed_ms,
                        json_shape=result.normalized.json_shape,
                        top_level_json_keys=result.normalized.top_level_keys,
                        structural_representation=result.normalized.structural,
                        sanitized_body_hash=result.normalized.body_hash,
                        sanitized_excerpt=result.normalized.excerpt,
                        error_category=None,
                        auth_challenge=result.normalized.auth_challenge,
                        access_denied_marker=result.normalized.denied,
                        object_existence_marker=result.normalized.object_marker,
                        success_markers=result.normalized.success_markers,
                        body_truncated=result.normalized.truncated,
                        is_binary=result.normalized.binary,
                    )
                except TimeoutError as exc:
                    raise ReplayError(
                        "run_timeout", "The target exceeded the per-run timeout."
                    ) from exc
                except ReplayError as exc:
                    observation = Observation(
                        project_id=test_case.project_id,
                        comparison_run_id=run.id,
                        request_id=request_definition.id,
                        session_id=session.id,
                        status_code=None,
                        redirect_outcome="failed",
                        safe_headers=[],
                        response_length=0,
                        duration_ms=0,
                        top_level_json_keys=[],
                        error_category=exc.code,
                        auth_challenge=False,
                        access_denied_marker=False,
                        object_existence_marker=False,
                        success_markers=[],
                        body_truncated=False,
                        is_binary=False,
                    )
                    db.add(observation)
                    observations.append(observation)
                    job.completed_count += 1
                    run.progress_completed += 1
                    await db.commit()
                    raise
                db.add(observation)
                observations.append(observation)
                session.last_used_at = datetime.now(UTC)
                job.completed_count += 1
                run.progress_completed += 1
                await db.commit()
            await db.refresh(job)
            if job.cancellation_requested:
                raise asyncio.CancelledError
            decision = compare_observations(
                observations[0],
                observations[1],
                expected_behaviour=test_case.expected_behaviour,
                is_state_changing=request_definition.is_state_changing,
                high_is_anonymous=high_session.is_anonymous,
                low_is_anonymous=low_session.is_anonymous,
                ignored_json_paths=test_case.ignored_json_paths,
                unordered_json_paths=test_case.unordered_json_paths,
                ignored_headers=ignored_headers,
                ignored_text_patterns=ignored_text_patterns,
            )
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            run.automated_classification = decision.classification
            run.confidence = decision.confidence
            run.explanation = decision.explanation
            run.engine_version = ENGINE_VERSION
            job.status = "completed"
            db.add(
                DiffResult(
                    comparison_run_id=run.id,
                    status_code_difference=decision.differences["status"],
                    redirect_difference=decision.differences["redirect"],
                    header_difference=decision.differences["headers"],
                    body_size_difference=decision.differences["response_length"]["delta"],
                    body_similarity=decision.differences["body_similarity"],
                    json_structural_difference=[
                        {"only_high": decision.differences["structure_only_high"]},
                        {"only_low": decision.differences["structure_only_low"]},
                    ],
                    json_value_difference=decision.differences["json_value_difference"],
                    text_difference=decision.differences["text_diff"],
                    sensitive_field_overlap=decision.differences["sensitive_field_overlap"],
                    decision_signals={
                        **decision.signals,
                        "classification": decision.classification,
                        "severity": decision.severity,
                        "explanation": decision.explanation,
                        "alternative_explanations": list(decision.alternative_explanations),
                        "limitations": list(decision.limitations),
                        "remediation": decision.remediation,
                    },
                    created_at=datetime.now(UTC),
                )
            )
            db.add(ComparisonReview(comparison_run_id=run.id, disposition="unreviewed"))
            if decision.candidate:
                fingerprint = hashlib.sha256(
                    (
                        f"{test_case.project_id}|{target.id}|{request_definition.method}|"
                        f"{request_definition.path}|{decision.classification}|"
                        f"{high_session.role_label}|{low_session.role_label}"
                    ).encode()
                ).hexdigest()
                now = datetime.now(UTC)
                finding = (
                    await db.execute(
                        select(Finding).where(
                            Finding.project_id == test_case.project_id,
                            Finding.fingerprint == fingerprint,
                            Finding.deleted_at.is_(None),
                        )
                    )
                ).scalar_one_or_none()
                if finding is None:
                    finding = Finding(
                        project_id=test_case.project_id,
                        comparison_run_id=run.id,
                        fingerprint=fingerprint,
                        title=f"Review {request_definition.method} {request_definition.path}",
                        category=decision.classification,
                        severity=decision.severity,
                        confidence=decision.confidence,
                        status="candidate",
                        target_snapshot=target.base_url,
                        endpoint_snapshot=request_definition.path,
                        expected_behaviour=test_case.expected_behaviour,
                        observed_behaviour=decision.explanation,
                        description=(
                            "AuthZDiff observed an authorization-relevant difference. "
                            "A reviewer must confirm whether it represents a security defect."
                        ),
                        impact="Not assessed automatically.",
                        reproduction_summary=(
                            "Repeat this saved comparison only against the authorized target."
                        ),
                        remediation=decision.remediation,
                        reviewer_notes="",
                        priority="normal",
                        tags=["automated-candidate"],
                        redaction_summary=(
                            "Reusable authentication material and configured sensitive fields "
                            "were redacted before persistence."
                        ),
                        limitations=" ".join(decision.limitations),
                        created_by=run.initiated_by,
                        first_seen_at=now,
                        last_seen_at=now,
                        recurrence_count=1,
                    )
                    db.add(finding)
                    await db.flush()
                    db.add(
                        FindingStatusHistory(
                            finding_id=finding.id,
                            from_status=None,
                            to_status="candidate",
                            changed_by=run.initiated_by,
                            note="Created from deterministic comparison evidence.",
                            created_at=now,
                        )
                    )
                else:
                    old_status = finding.status
                    finding.comparison_run_id = run.id
                    finding.last_seen_at = now
                    finding.recurrence_count += 1
                    finding.observed_behaviour = decision.explanation
                    finding.confidence = decision.confidence
                    if old_status == "resolved":
                        finding.status = "reopened"
                        db.add(
                            FindingStatusHistory(
                                finding_id=finding.id,
                                from_status=old_status,
                                to_status="reopened",
                                changed_by=run.initiated_by,
                                note="Reopened after the same stable fingerprint recurred.",
                                created_at=now,
                            )
                        )
                for role, observation in zip(
                    ("higher-privilege", "lower-privilege"), observations, strict=True
                ):
                    excerpt = observation.sanitized_excerpt or (
                        "Binary response: raw bytes were not retained."
                        if observation.is_binary
                        else "No response body excerpt was retained."
                    )
                    db.add(
                        FindingEvidence(
                            finding_id=finding.id,
                            observation_id=observation.id,
                            comparison_run_id=run.id,
                            evidence_type="response_observation",
                            sanitized_excerpt=excerpt,
                            excerpt_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
                            safe_metadata={
                                "role": role,
                                "status_code": observation.status_code,
                                "content_type": observation.content_type,
                                "response_length": observation.response_length,
                                "body_hash": observation.sanitized_body_hash,
                                "truncated": observation.body_truncated,
                                "binary_hash_only": observation.is_binary,
                            },
                        )
                    )
            db.add(
                AuditEvent(
                    user_id=run.initiated_by,
                    action="comparison_completed",
                    entity_type="comparison_run",
                    entity_id=run.id,
                    project_id=test_case.project_id,
                    outcome="success",
                    summary=f"Comparison completed with classification {decision.classification}.",
                    safe_metadata={
                        "classification": decision.classification,
                        "confidence": decision.confidence,
                    },
                    correlation_id=job.correlation_id,
                    created_at=datetime.now(UTC),
                )
            )
            await release_leases(db, run.id)
            await db.commit()

    async def _mark_failed(self, job_id: str, code: str, detail: str) -> None:
        async with SessionLocal() as db:
            job = await db.get(ExecutionJob, job_id)
            if job is None:
                return
            if job.status not in {"queued", "claimed", "running", "cancelling"}:
                return
            run = await db.get(ComparisonRun, job.comparison_run_id)
            job.status = "failed"
            job.error_code = code
            job.error_message = detail
            if run:
                run.status = "failed"
                run.error_code = code
                run.error_message = detail
                run.completed_at = datetime.now(UTC)
                db.add(
                    AuditEvent(
                        user_id=run.initiated_by,
                        action="comparison_failed",
                        entity_type="comparison_run",
                        entity_id=run.id,
                        project_id=job.project_id,
                        outcome="failed",
                        summary=f"Comparison failed with sanitized category {code}.",
                        safe_metadata={"error_code": code},
                        correlation_id=job.correlation_id,
                        created_at=datetime.now(UTC),
                    )
                )
                await release_leases(db, run.id)
            await db.commit()

    async def finalize_cancelled(self, job_id: str) -> None:
        await self._mark_cancelled(job_id)

    async def _mark_cancelled(self, job_id: str) -> None:
        async with SessionLocal() as db:
            job = await db.get(ExecutionJob, job_id)
            if job is None:
                return
            if job.status not in {"queued", "claimed", "running", "cancelling"}:
                return
            run = await db.get(ComparisonRun, job.comparison_run_id)
            job.status = "cancelled"
            job.cancellation_requested = True
            if run:
                run.status = "cancelled"
                run.cancellation_requested = True
                run.completed_at = datetime.now(UTC)
                await release_leases(db, run.id)
                db.add(
                    AuditEvent(
                        user_id=run.initiated_by,
                        action="comparison_cancelled",
                        entity_type="comparison_run",
                        entity_id=run.id,
                        project_id=job.project_id,
                        outcome="cancelled",
                        summary="User cancelled a comparison run.",
                        safe_metadata={},
                        correlation_id=job.correlation_id,
                        created_at=datetime.now(UTC),
                    )
                )
            await db.commit()


coordinator = RunCoordinator()
