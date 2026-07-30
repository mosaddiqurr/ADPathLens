from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.dependencies import CsrfContextDep, CurrentUserDep, DbDep, SettingsDep
from app.audit.service import record_audit
from app.core.problems import ApiProblem
from app.models import Finding, Project, Report, Target, User
from app.reporting.generator import (
    canonical_payload_hash,
    render_csv,
    render_html,
    render_json,
    render_pdf,
)
from app.schemas.findings import ReportCreate, ReportRead
from app.services.authorization import project_for_user

router = APIRouter(tags=["reports"])


async def _report_for_user(db: DbDep, user: User, report_id: str) -> Report:
    report = await db.get(Report, report_id)
    if report is None:
        raise ApiProblem(404, "report_not_found", "The report was not found.")
    await project_for_user(db, user, report.project_id)
    return report


async def _payload(db: DbDep, project: Project) -> dict[str, object]:
    targets = (
        (await db.execute(select(Target).where(Target.project_id == project.id))).scalars().all()
    )
    findings = (
        (
            await db.execute(
                select(Finding).where(
                    Finding.project_id == project.id, Finding.deleted_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    generated_at = datetime.now(UTC).isoformat()
    payload: dict[str, object] = {
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
        },
        "generated_at": generated_at,
        "targets": [
            {
                "name": target.name,
                "base_url": target.base_url,
                "allowed_paths": target.allowed_path_prefixes,
                "allowed_methods": target.allowed_methods,
                "authorization_confirmed": target.authorization_confirmed,
                "authorization_expires_at": (
                    target.authorization_expires_at.isoformat()
                    if target.authorization_expires_at
                    else None
                ),
            }
            for target in targets
        ],
        "findings": [
            {
                "id": finding.id,
                "title": finding.title,
                "category": finding.category,
                "severity": finding.severity,
                "confidence": finding.confidence,
                "status": finding.status,
                "target": finding.target_snapshot,
                "endpoint": finding.endpoint_snapshot,
                "description": finding.description,
                "impact": finding.impact,
                "remediation": finding.remediation,
                "limitations": finding.limitations,
                "tags": finding.tags,
            }
            for finding in findings
        ],
        "redaction_summary": (
            "Cookies, authorization values, API keys, tokens and configured sensitive fields "
            "were excluded or redacted."
        ),
        "limitations": (
            "AuthZDiff identifies suspicious authorization differences. It does not independently "
            "prove exploitability, affected population or business impact."
        ),
    }
    payload["content_hash"] = canonical_payload_hash(payload)
    return payload


@router.get("/projects/{project_id}/reports", response_model=list[ReportRead])
async def list_reports(project_id: str, db: DbDep, user: CurrentUserDep) -> list[ReportRead]:
    await project_for_user(db, user, project_id)
    rows = (
        (
            await db.execute(
                select(Report)
                .where(Report.project_id == project_id)
                .order_by(Report.generated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [ReportRead.model_validate(row) for row in rows]


@router.post(
    "/projects/{project_id}/reports",
    response_model=ReportRead,
    status_code=201,
)
async def generate_report(
    project_id: str,
    payload: ReportCreate,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> ReportRead:
    project = await project_for_user(db, context.user, project_id)
    content = await _payload(db, project)
    content_hash = str(content["content_hash"])
    report = Report(
        project_id=project.id,
        format=payload.format,
        status="generating",
        generated_by=context.user.id,
        generated_at=datetime.now(UTC),
        file_name="pending",
        content_hash=content_hash,
    )
    db.add(report)
    await db.flush()
    storage_root = settings.report_storage_path.resolve()
    storage_root.mkdir(parents=True, exist_ok=True)
    file_name = f"authzdiff-{project.id[:8]}-{report.id}.{payload.format}"
    destination = (storage_root / file_name).resolve()
    if storage_root not in destination.parents:
        raise ApiProblem(500, "report_path_invalid", "The report path is invalid.")
    try:
        if payload.format == "json":
            data = render_json(content)
            destination.write_bytes(data)
        elif payload.format == "csv":
            data = render_csv(content)
            destination.write_bytes(data)
        elif payload.format == "html":
            data = render_html(content)
            destination.write_bytes(data)
        else:
            render_pdf(content, destination)
            data = destination.read_bytes()
        report.file_name = file_name
        report.storage_path = str(destination)
        report.file_hash = hashlib.sha256(data).hexdigest()
        report.status = "completed"
    except Exception as exc:
        report.status = "failed"
        report.error_message = "Report generation failed."
        await db.commit()
        raise ApiProblem(500, "report_generation_failed", "Report generation failed.") from exc
    await record_audit(
        db,
        request,
        action="report_generated",
        entity_type="report",
        entity_id=report.id,
        user_id=context.user.id,
        summary=f"Generated a redacted {payload.format.upper()} report.",
    )
    await db.commit()
    await db.refresh(report)
    return ReportRead.model_validate(report)


@router.get("/reports/{report_id}", response_model=ReportRead)
async def get_report(report_id: str, db: DbDep, user: CurrentUserDep) -> ReportRead:
    return ReportRead.model_validate(await _report_for_user(db, user, report_id))


@router.get("/reports/{report_id}/download")
async def download_report(
    report_id: str,
    request: Request,
    db: DbDep,
    user: CurrentUserDep,
    settings: SettingsDep,
) -> FileResponse:
    report = await _report_for_user(db, user, report_id)
    if report.status != "completed" or not report.storage_path:
        raise ApiProblem(409, "report_not_ready", "The report is not available for download.")
    storage_root = settings.report_storage_path.resolve()
    path = Path(report.storage_path).resolve()
    if storage_root not in path.parents or not path.is_file():
        raise ApiProblem(404, "report_file_missing", "The report file is missing.")
    media_types = {
        "json": "application/json",
        "csv": "text/csv",
        "html": "text/html",
        "pdf": "application/pdf",
    }
    await record_audit(
        db,
        request,
        action="report_downloaded",
        entity_type="report",
        entity_id=report.id,
        user_id=user.id,
        summary=f"Downloaded a redacted {report.format.upper()} report.",
    )
    await db.commit()
    return FileResponse(
        path,
        media_type=media_types[report.format],
        filename=report.file_name,
    )
