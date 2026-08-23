from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.reports import _payload
from app.db.base import Base
from app.db.session import _enable_sqlite_foreign_keys
from app.models import (
    ComparisonRun,
    Finding,
    FindingEvidence,
    ImportedRequest,
    Observation,
    Project,
    ProjectPolicy,
    Target,
    User,
)
from app.models import (
    TestCase as _TestCaseModel,
)
from app.models import (
    TestSession as _TestSessionModel,
)
from app.replay.normalization import normalize_response
from app.reporting.generator import render_csv, render_html, render_json, render_pdf


@pytest.mark.asyncio
async def test_sensitive_values_never_reach_persistence_or_reports(tmp_path) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "redaction.sqlite"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")
    event.listen(test_engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    secret_values = {
        "national_id": "NATIONAL-ID-MUST-NOT-PERSIST",
        "private_key": "PRIVATE-KEY-MUST-NOT-PERSIST",
        "secret": "SECRET-MUST-NOT-PERSIST",
        "token": "TOKEN-MUST-NOT-PERSIST",
        "custom_sensitive": "CUSTOM-MUST-NOT-PERSIST",
    }
    now = datetime.now(UTC)
    async with sessions() as db:
        user = User(
            email="redaction@example.invalid",
            display_name="Redaction Fixture",
            password_hash=hashlib.sha256(b"fixture-password-hash").hexdigest(),
            role="administrator",
            is_active=True,
            must_change_password=False,
        )
        db.add(user)
        await db.flush()
        project = Project(
            name="Redaction project",
            description="Synthetic persistence fixture.",
            status="active",
            created_by=user.id,
        )
        db.add(project)
        await db.flush()
        policy = ProjectPolicy(
            project_id=project.id,
            redaction_keys=["custom_sensitive"],
            ignored_headers=[],
            ignored_text_patterns=[],
        )
        target = Target(
            project_id=project.id,
            name="Synthetic target",
            base_url="https://example.invalid",
            scheme="https",
            hostname="example.invalid",
            port=443,
            authorization_confirmed=True,
            allowed_path_prefixes=["/safe"],
            allowed_methods=["GET"],
            is_active=True,
            created_by=user.id,
        )
        db.add_all([policy, target])
        await db.flush()
        high = _TestSessionModel(
            project_id=project.id,
            target_id=target.id,
            name="High",
            role_label="administrator",
            secret_fingerprint=f"hmac:{hashlib.sha256(b'high').hexdigest()[:12]}",
            is_anonymous=True,
            is_active=True,
            created_by=user.id,
        )
        low = _TestSessionModel(
            project_id=project.id,
            target_id=target.id,
            name="Low",
            role_label="anonymous",
            secret_fingerprint=f"hmac:{hashlib.sha256(b'low').hexdigest()[:12]}",
            is_anonymous=True,
            is_active=True,
            created_by=user.id,
        )
        db.add_all([high, low])
        await db.flush()
        request = ImportedRequest(
            project_id=project.id,
            target_id=target.id,
            name="Safe request",
            import_type="manual",
            method="GET",
            scheme="https",
            hostname="example.invalid",
            port=443,
            path="/safe/item",
            query_parameters=[],
            sanitized_headers=[],
            body_template="",
            body_hash=hashlib.sha256(b"").hexdigest(),
            is_state_changing=False,
            approved_state_change=False,
            expected_markers=[],
            tags=[],
            sensitivity="restricted",
            created_by=user.id,
        )
        db.add(request)
        await db.flush()
        test_case = _TestCaseModel(
            project_id=project.id,
            target_id=target.id,
            imported_request_id=request.id,
            name="Redaction comparison",
            high_privilege_session_id=high.id,
            low_privilege_session_id=low.id,
            expected_behaviour="sensitive_fields_limited",
            ignored_json_paths=[],
            unordered_json_paths=[],
            ignored_headers=[],
            ignored_text_patterns=[],
            created_by=user.id,
        )
        db.add(test_case)
        await db.flush()
        run = ComparisonRun(
            test_case_id=test_case.id,
            status="completed",
            started_at=now,
            completed_at=now,
            initiated_by=user.id,
            engine_version="authzdiff-rules/1.1",
        )
        db.add(run)
        await db.flush()

        normalized = normalize_response(
            status_code=200,
            headers=[("Content-Type", "application/json")],
            body=json.dumps(secret_values).encode(),
            content_type="application/json",
            max_excerpt_bytes=10_000,
            expected_markers=[],
            redaction_keys=policy.redaction_keys,
        )
        observation = Observation(
            project_id=project.id,
            comparison_run_id=run.id,
            request_id=request.id,
            session_id=low.id,
            status_code=200,
            redirect_outcome="none",
            content_type="application/json",
            safe_headers=normalized.safe_headers,
            response_length=normalized.response_length,
            duration_ms=1,
            json_shape=normalized.json_shape,
            top_level_json_keys=normalized.top_level_keys,
            structural_representation=normalized.structural,
            sanitized_body_hash=normalized.body_hash,
            sanitized_excerpt=normalized.excerpt,
            auth_challenge=False,
            access_denied_marker=False,
            object_existence_marker=False,
            success_markers=[],
            body_truncated=False,
            is_binary=False,
        )
        db.add(observation)
        await db.flush()
        finding = Finding(
            project_id=project.id,
            comparison_run_id=run.id,
            fingerprint=hashlib.sha256(b"redaction-fixture").hexdigest(),
            title="Synthetic redaction finding",
            category="potential_sensitive_field_exposure",
            severity="medium",
            confidence="high",
            status="candidate",
            target_snapshot=target.base_url,
            endpoint_snapshot=request.path,
            expected_behaviour=test_case.expected_behaviour,
            observed_behaviour="Redacted evidence requires review.",
            description="Only normalized redacted response evidence is retained.",
            remediation="Validate field-level authorization.",
            redaction_summary="Sensitive values were redacted before persistence.",
            limitations="Synthetic fixture.",
            created_by=user.id,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(finding)
        await db.flush()
        excerpt = observation.sanitized_excerpt or ""
        db.add(
            FindingEvidence(
                finding_id=finding.id,
                observation_id=observation.id,
                comparison_run_id=run.id,
                evidence_type="response_observation",
                sanitized_excerpt=excerpt,
                excerpt_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
                safe_metadata={"body_hash": normalized.body_hash},
            )
        )
        await db.commit()

        report_payload = await _payload(db, project)
        report_bytes = [
            render_json(report_payload),
            render_csv(report_payload),
            render_html(report_payload),
        ]
        pdf_path = tmp_path / "redaction.pdf"
        render_pdf(report_payload, pdf_path)
        report_bytes.append(pdf_path.read_bytes())
        for original in secret_values.values():
            assert all(original.encode() not in content for content in report_bytes)

    await test_engine.dispose()
    database_bytes = database.read_bytes()
    for original in secret_values.values():
        assert original.encode() not in database_bytes
