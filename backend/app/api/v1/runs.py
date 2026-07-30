from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

from fastapi import APIRouter, Request
from sqlalchemy import func, select, update

from app.api.dependencies import CsrfContextDep, CurrentUserDep, DbDep, SettingsDep
from app.audit.service import record_audit
from app.core.problems import ApiProblem
from app.models import (
    AppSetting,
    ComparisonRun,
    DiffResult,
    ExecutionJob,
    ImportedRequest,
    Observation,
    Target,
    TestCase,
    TestCaseVariable,
    TestSession,
    User,
)
from app.schemas.runs import (
    JobRead,
    ObservationRead,
    RunAuthorization,
    RunDetail,
    RunRead,
    TestCaseCreate,
    TestCaseRead,
)
from app.security.crypto import KeyRing
from app.services.authorization import project_for_user, target_for_user
from app.services.coordinator import coordinator
from app.services.leases import acquire_lease
from app.services.request_policy import validate_request_policy

router = APIRouter(tags=["comparison runs"])


@lru_cache
def _keyring(active: str, old: str) -> KeyRing:
    return KeyRing.from_settings(active, old)


async def _test_case_for_user(db: DbDep, user: User, test_case_id: str) -> TestCase:
    test_case = await db.get(TestCase, test_case_id)
    if test_case is None:
        raise ApiProblem(404, "test_case_not_found", "The test case was not found.")
    await project_for_user(db, user, test_case.project_id)
    return test_case


async def _run_for_user(db: DbDep, user: User, run_id: str) -> tuple[ComparisonRun, TestCase]:
    run = await db.get(ComparisonRun, run_id)
    if run is None:
        raise ApiProblem(404, "run_not_found", "The comparison run was not found.")
    test_case = await _test_case_for_user(db, user, run.test_case_id)
    return run, test_case


@router.get("/projects/{project_id}/test-cases", response_model=list[TestCaseRead])
async def list_test_cases(project_id: str, db: DbDep, user: CurrentUserDep) -> list[TestCaseRead]:
    await project_for_user(db, user, project_id)
    rows = (
        (
            await db.execute(
                select(TestCase)
                .where(TestCase.project_id == project_id)
                .order_by(TestCase.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [TestCaseRead.model_validate(row) for row in rows]


@router.post(
    "/projects/{project_id}/test-cases",
    response_model=TestCaseRead,
    status_code=201,
)
async def create_test_case(
    project_id: str,
    payload: TestCaseCreate,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> TestCaseRead:
    await project_for_user(db, context.user, project_id)
    target = await target_for_user(db, context.user, payload.target_id)
    request_definition = await db.get(ImportedRequest, payload.imported_request_id)
    high_session = await db.get(TestSession, payload.high_privilege_session_id)
    low_session = await db.get(TestSession, payload.low_privilege_session_id)
    if request_definition is None or high_session is None or low_session is None:
        raise ApiProblem(
            422,
            "test_case_scope_mismatch",
            "The request, target, and session profiles must belong to the same project.",
        )
    scoped = (
        target.project_id == project_id
        and request_definition.project_id == project_id
        and request_definition.target_id == target.id
        and high_session.project_id == project_id
        and low_session.project_id == project_id
        and high_session.target_id == target.id
        and low_session.target_id == target.id
    )
    if not scoped:
        raise ApiProblem(
            422,
            "test_case_scope_mismatch",
            "The request, target, and session profiles must belong to the same project.",
        )
    if request_definition.is_state_changing and not payload.approved_state_change:
        raise ApiProblem(
            422,
            "state_change_approval_required",
            "State-changing test cases require explicit approval.",
        )
    test_case = TestCase(
        project_id=project_id,
        target_id=target.id,
        imported_request_id=request_definition.id,
        name=payload.name.strip(),
        description=payload.description,
        high_privilege_session_id=high_session.id,
        low_privilege_session_id=low_session.id,
        expected_behaviour=payload.expected_behaviour,
        custom_expectation=payload.custom_expectation,
        approved_state_change=payload.approved_state_change,
        state_change_approved_by=(context.user.id if payload.approved_state_change else None),
        state_change_approved_at=(datetime.now(UTC) if payload.approved_state_change else None),
        ignored_json_paths=payload.ignored_json_paths,
        unordered_json_paths=payload.unordered_json_paths,
        ignored_headers=payload.ignored_headers,
        ignored_text_patterns=payload.ignored_text_patterns,
        created_by=context.user.id,
    )
    db.add(test_case)
    await db.flush()
    ring = _keyring(settings.encryption_master_key, settings.encryption_old_keys)
    for item in payload.variables:
        variable = TestCaseVariable(
            test_case_id=test_case.id,
            scope=item.scope,
            name=item.name,
            encrypted_value=b"pending",
            is_secret=item.is_secret,
        )
        db.add(variable)
        await db.flush()
        variable.encrypted_value = ring.encrypt(
            item.value.encode(), f"test_case_variable:{variable.id}:value"
        )
    await record_audit(
        db,
        request,
        action=(
            "state_changing_test_case_approved"
            if payload.approved_state_change
            else "test_case_created"
        ),
        entity_type="test_case",
        entity_id=test_case.id,
        user_id=context.user.id,
        summary="Created an explicit two-profile authorization comparison.",
    )
    await db.commit()
    await db.refresh(test_case)
    return TestCaseRead.model_validate(test_case)


@router.get("/test-cases/{test_case_id}/preview")
async def preview_test_case(
    test_case_id: str, db: DbDep, user: CurrentUserDep
) -> dict[str, object]:
    test_case = await _test_case_for_user(db, user, test_case_id)
    target = await db.get(Target, test_case.target_id)
    request_definition = await db.get(ImportedRequest, test_case.imported_request_id)
    high = await db.get(TestSession, test_case.high_privilege_session_id)
    low = await db.get(TestSession, test_case.low_privilege_session_id)
    if target is None or request_definition is None or high is None or low is None:
        raise ApiProblem(409, "test_case_incomplete", "The test case has missing dependencies.")
    return {
        "destination": target.base_url,
        "method": request_definition.method,
        "path": request_definition.path,
        "profiles": [
            {"id": high.id, "name": high.name, "role": high.role_label},
            {"id": low.id, "name": low.name, "role": low.role_label},
        ],
        "request_count": 2,
        "state_changing": request_definition.is_state_changing,
        "data_leaving_application": [
            "rendered path and query values",
            "request body",
            "selected profile credentials",
        ],
        "persisted": [
            "normalized status and response metadata",
            "redacted structural evidence",
            "sanitized bounded excerpt",
        ],
        "not_persisted": ["plaintext profile credentials", "raw reusable cookies or tokens"],
    }


@router.post("/test-cases/{test_case_id}/run", response_model=JobRead, status_code=202)
async def start_run(
    test_case_id: str,
    payload: RunAuthorization,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> JobRead:
    if not payload.authorization_confirmed:
        raise ApiProblem(422, "run_authorization_required", "Confirm authorization before running.")
    test_case = await _test_case_for_user(db, context.user, test_case_id)
    target = await db.get(Target, test_case.target_id)
    request_definition = await db.get(ImportedRequest, test_case.imported_request_id)
    if target is None or request_definition is None:
        raise ApiProblem(409, "test_case_incomplete", "The test case has missing dependencies.")
    validate_request_policy(
        target,
        method=request_definition.method,
        path=request_definition.path,
        approved_state_change=(
            request_definition.approved_state_change and test_case.approved_state_change
        ),
        require_active=True,
    )
    if request_definition.is_state_changing and (
        not payload.test_data_confirmed or payload.typed_confirmation != "AUTHORIZE CHANGE"
    ):
        raise ApiProblem(
            422,
            "state_change_confirmation_required",
            "Confirm test data and type AUTHORIZE CHANGE for this request.",
        )
    if request_definition.is_state_changing:
        application_policy = (
            await db.execute(select(AppSetting).where(AppSetting.singleton_key == "global"))
        ).scalar_one_or_none()
        if application_policy is None or not application_policy.global_state_changes_enabled:
            raise ApiProblem(
                403,
                "global_state_changes_disabled",
                "State-changing replay is disabled by the global application policy.",
            )
    active_user_jobs = (
        await db.execute(
            select(func.count(ExecutionJob.id)).where(
                ExecutionJob.requested_by == context.user.id,
                ExecutionJob.status.in_(["queued", "claimed", "running", "cancelling"]),
            )
        )
    ).scalar_one()
    if active_user_jobs >= 2:
        raise ApiProblem(429, "user_concurrency_limit", "This user already has two active runs.")
    active_project_jobs = (
        await db.execute(
            select(func.count(ExecutionJob.id)).where(
                ExecutionJob.project_id == test_case.project_id,
                ExecutionJob.status.in_(["queued", "claimed", "running", "cancelling"]),
            )
        )
    ).scalar_one()
    if active_project_jobs >= target.concurrency_limit:
        raise ApiProblem(
            429,
            "project_concurrency_limit",
            "The target concurrency limit has been reached.",
        )
    reserved_target = (
        await db.execute(
            update(Target)
            .where(
                Target.id == target.id,
                Target.request_count_used + 2 <= Target.request_budget,
            )
            .values(
                request_count_used=Target.request_count_used + 2,
                last_execution_at=datetime.now(UTC),
            )
            .returning(Target.id)
        )
    ).scalar_one_or_none()
    if reserved_target is None:
        raise ApiProblem(
            403,
            "target_request_budget_exhausted",
            "The target request budget does not have two remaining request slots.",
        )
    run = ComparisonRun(
        test_case_id=test_case.id,
        status="queued",
        initiated_by=context.user.id,
        engine_version="authzdiff-rules/1.0",
        cancellation_requested=False,
        progress_completed=0,
        progress_total=2,
    )
    db.add(run)
    await db.flush()
    lease_ttl = max(120, target.per_run_timeout_seconds + 60)
    global_lease = await acquire_lease(
        db,
        scope_type="global",
        scope_id="global",
        slots=5,
        holder_id=run.id,
        ttl_seconds=lease_ttl,
    )
    user_lease = await acquire_lease(
        db,
        scope_type="user",
        scope_id=context.user.id,
        slots=2,
        holder_id=run.id,
        ttl_seconds=lease_ttl,
    )
    if not global_lease or not user_lease:
        await db.rollback()
        raise ApiProblem(
            429,
            "run_concurrency_limit",
            "No comparison execution slot is currently available.",
        )
    job = ExecutionJob(
        project_id=test_case.project_id,
        comparison_run_id=run.id,
        status="queued",
        requested_by=context.user.id,
        request_count=2,
        completed_count=0,
        cancellation_requested=False,
        correlation_id=str(request.state.request_id),
        attempt_count=0,
    )
    db.add(job)
    await db.flush()
    await record_audit(
        db,
        request,
        action="comparison_queued",
        entity_type="comparison_run",
        entity_id=run.id,
        user_id=context.user.id,
        summary="Queued two bounded requests against an authorized target.",
    )
    await db.commit()
    await db.refresh(job)
    if settings.replay_execution_mode == "inprocess":
        coordinator.launch(job.id)
    return JobRead.model_validate(job)


@router.get("/projects/{project_id}/runs", response_model=list[RunRead])
async def list_runs(project_id: str, db: DbDep, user: CurrentUserDep) -> list[RunRead]:
    await project_for_user(db, user, project_id)
    rows = (
        (
            await db.execute(
                select(ComparisonRun)
                .join(TestCase, TestCase.id == ComparisonRun.test_case_id)
                .where(TestCase.project_id == project_id)
                .order_by(ComparisonRun.started_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [RunRead.model_validate(row) for row in rows]


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, db: DbDep, user: CurrentUserDep) -> RunDetail:
    run, test_case = await _run_for_user(db, user, run_id)
    job = (
        await db.execute(select(ExecutionJob).where(ExecutionJob.comparison_run_id == run.id))
    ).scalar_one_or_none()
    observations = (
        (
            await db.execute(
                select(Observation)
                .where(Observation.comparison_run_id == run.id)
                .order_by(Observation.created_at)
            )
        )
        .scalars()
        .all()
    )
    diff = (
        await db.execute(select(DiffResult).where(DiffResult.comparison_run_id == run.id))
    ).scalar_one_or_none()
    request_definition = await db.get(ImportedRequest, test_case.imported_request_id)
    target = await db.get(Target, test_case.target_id)
    high = await db.get(TestSession, test_case.high_privilege_session_id)
    low = await db.get(TestSession, test_case.low_privilege_session_id)
    variables = (
        (
            await db.execute(
                select(TestCaseVariable)
                .where(TestCaseVariable.test_case_id == test_case.id)
                .order_by(TestCaseVariable.scope, TestCaseVariable.name)
            )
        )
        .scalars()
        .all()
    )
    context_payload: dict[str, object] = {
        "test_case": {
            "id": test_case.id,
            "name": test_case.name,
            "expected_behaviour": test_case.expected_behaviour,
        },
        "target": {
            "id": target.id if target else None,
            "base_url": target.base_url if target else None,
        },
        "request": {
            "id": request_definition.id if request_definition else None,
            "name": request_definition.name if request_definition else None,
            "method": request_definition.method if request_definition else None,
            "path": request_definition.path if request_definition else None,
        },
        "profiles": [
            {
                "id": profile.id,
                "name": profile.name,
                "role": profile.role_label,
                "anonymous": profile.is_anonymous,
            }
            for profile in (high, low)
            if profile is not None
        ],
        "variables": [
            {
                "name": variable.name,
                "scope": variable.scope,
                "secret": variable.is_secret,
            }
            for variable in variables
        ],
    }
    difference: dict[str, object] | None = None
    if diff:
        difference = {
            "status": diff.status_code_difference,
            "redirects": diff.redirect_difference,
            "headers": diff.header_difference,
            "body_size_difference": diff.body_size_difference,
            "body_similarity": diff.body_similarity,
            "json_structure": diff.json_structural_difference,
            "json_values": diff.json_value_difference,
            "text_diff": diff.text_difference,
            "sensitive_field_overlap": diff.sensitive_field_overlap,
            "decision_signals": diff.decision_signals,
        }
    return RunDetail(
        run=RunRead.model_validate(run),
        job=JobRead.model_validate(job) if job else None,
        observations=[ObservationRead.model_validate(row) for row in observations],
        difference=difference,
        context=context_payload,
    )


@router.post("/runs/{run_id}/cancel", response_model=JobRead)
async def cancel_run(
    run_id: str,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> JobRead:
    run, _test_case = await _run_for_user(db, context.user, run_id)
    job = (
        await db.execute(select(ExecutionJob).where(ExecutionJob.comparison_run_id == run.id))
    ).scalar_one_or_none()
    if job is None or job.status not in {"queued", "claimed", "running", "cancelling"}:
        raise ApiProblem(409, "run_not_cancellable", "The comparison cannot be cancelled.")
    job.cancellation_requested = True
    job.status = "cancelling"
    run.cancellation_requested = True
    run.status = "cancelling"
    await record_audit(
        db,
        request,
        action="comparison_cancellation_requested",
        entity_type="comparison_run",
        entity_id=run.id,
        user_id=context.user.id,
        summary="Requested cancellation of a comparison run.",
    )
    await db.commit()
    coordinator.cancel(job.id)
    await db.refresh(job)
    return JobRead.model_validate(job)
