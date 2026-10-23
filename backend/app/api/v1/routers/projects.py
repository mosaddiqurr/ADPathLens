import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from sqlalchemy import func, or_, select

from app.api.deps import DB, CsrfUser, CurrentUser, EditorCsrf
from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.errors import AppError
from app.data.demos import get_demo
from app.graph.service import graph_cache
from app.importers.validator import (
    ValidationResult,
    validate_csv_bytes,
    validate_json_bytes,
    validate_records,
    validate_zip_bytes,
)
from app.models.entities import (
    AuditEvent,
    Dataset,
    DirectoryNode,
    DirectoryRelationship,
    GraphSnapshot,
    ImportedFile,
    ImportIssue,
    PathAnalysis,
    PrivilegePath,
    Project,
    RemediationPlan,
    Report,
    RiskFinding,
    SnapshotComparison,
    User,
    WorkspaceMembership,
)
from app.schemas.projects import (
    DatasetResponse,
    DemoImportRequest,
    ImportProgressResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectStatisticsResponse,
    ProjectUpdate,
    SnapshotResponse,
    ValidationResponse,
)
from app.services.authorization import project_or_404, workspace_membership

router = APIRouter(tags=["projects and datasets"])


def _stable_fingerprint(*parts: object) -> str:
    canonical = json.dumps(parts, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _remove_report_files(storage_paths: list[str]) -> None:
    report_root = get_settings().report_storage_path.resolve()
    for storage_path in storage_paths:
        path = Path(storage_path).resolve()
        if report_root not in path.parents:
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # Database deletion remains authoritative; an operator can remove an
            # inaccessible orphan after correcting storage permissions.
            continue


def _validation_response(result: ValidationResult) -> ValidationResponse:
    return ValidationResponse.model_validate(result.summary())


async def _import_result(
    *,
    db: DB,
    request: Request,
    user: User,
    project: Project,
    result: ValidationResult,
    source_type: str,
    source_filename: str | None,
    source_files: list[dict[str, object]],
    name: str,
    authorization_confirmed: bool,
    acknowledged_warning_codes: set[str] | None = None,
) -> tuple[Dataset, GraphSnapshot]:
    if not authorization_confirmed:
        raise AppError(
            422,
            "Authorization confirmation required",
            "Confirm that the data is synthetic or authorized.",
            code="authorization_required",
        )
    if not result.valid:
        raise AppError(
            422,
            "Dataset validation failed",
            "Resolve validation errors before importing.",
            code="validation_failed",
            extra={"validation": result.summary()},
        )
    warning_codes = {message.code for message in result.messages if message.level == "warning"}
    missing_acknowledgements = warning_codes - (acknowledged_warning_codes or set())
    if missing_acknowledgements:
        raise AppError(
            422,
            "Warning acknowledgement required",
            "Review and acknowledge every validation warning before importing.",
            code="warning_acknowledgement_required",
            extra={"warning_codes": sorted(missing_acknowledgements)},
        )
    duplicate = await db.scalar(
        select(Dataset.id).where(
            Dataset.project_id == project.id,
            Dataset.data_hash == result.digest,
            Dataset.import_status == "complete",
        )
    )
    if duplicate:
        raise AppError(
            409,
            "Dataset already imported",
            "This exact normalized dataset already exists in the project.",
            code="duplicate_dataset",
            extra={"dataset_id": duplicate},
        )
    next_version = (
        await db.scalar(
            select(func.coalesce(func.max(GraphSnapshot.version), 0)).where(GraphSnapshot.project_id == project.id)
        )
        or 0
    ) + 1
    dataset = Dataset(
        project_id=project.id,
        name=name[:256],
        source_type=source_type,
        source_filename=source_filename,
        authorization_confirmed=True,
        authorization_confirmed_by=user.id,
        authorization_confirmed_at=datetime.now(UTC),
        import_status="complete",
        validation_summary=result.summary(),
        node_count=len(result.nodes),
        relationship_count=len(result.relationships),
        warning_count=len(warning_codes),
        rejected_record_count=0,
        data_hash=result.digest,
        created_by=user.id,
    )
    db.add(dataset)
    await db.flush()
    imported_files: list[ImportedFile] = []
    for source in source_files:
        imported_file = ImportedFile(
            dataset_id=dataset.id,
            logical_name=str(source["logical_name"])[:256],
            original_name=str(source["original_name"])[:256],
            content_hash=str(source["content_hash"]),
            media_type=str(source["media_type"])[:128],
            size_bytes=int(str(source["size_bytes"])),
        )
        db.add(imported_file)
        imported_files.append(imported_file)
    await db.flush()
    provenance_file_id = imported_files[0].id if imported_files else None
    for message in result.messages:
        db.add(
            ImportIssue(
                dataset_id=dataset.id,
                level=message.level,
                code=message.code,
                message=message.message[:1000],
                location=message.location,
                acknowledged_by=(
                    user.id
                    if message.level == "warning" and message.code in (acknowledged_warning_codes or set())
                    else None
                ),
            )
        )
    snapshot = GraphSnapshot(
        project_id=project.id,
        dataset_id=dataset.id,
        name=name[:256],
        snapshot_type="imported",
        version=next_version,
        created_by=user.id,
    )
    db.add(snapshot)
    await db.flush()
    observed_at = snapshot.created_at
    previous_node_first_seen = {
        external_id: first_seen
        for external_id, first_seen in (
            await db.execute(
                select(DirectoryNode.external_id, func.min(DirectoryNode.first_seen_at))
                .join(GraphSnapshot, GraphSnapshot.id == DirectoryNode.snapshot_id)
                .where(GraphSnapshot.project_id == project.id, GraphSnapshot.id != snapshot.id)
                .group_by(DirectoryNode.external_id)
            )
        ).all()
    }
    previous_relationship_first_seen = {
        external_id: first_seen
        for external_id, first_seen in (
            await db.execute(
                select(DirectoryRelationship.external_id, func.min(DirectoryRelationship.first_seen_at))
                .join(GraphSnapshot, GraphSnapshot.id == DirectoryRelationship.snapshot_id)
                .where(GraphSnapshot.project_id == project.id, GraphSnapshot.id != snapshot.id)
                .group_by(DirectoryRelationship.external_id)
            )
        ).all()
    }
    node_lookup: dict[str, str] = {}
    for normalized in result.nodes:
        node = DirectoryNode(
            snapshot_id=snapshot.id,
            source_file_id=provenance_file_id,
            stable_fingerprint=_stable_fingerprint(
                normalized["external_id"],
                normalized["node_type"],
            ),
            first_seen_at=previous_node_first_seen.get(normalized["external_id"]) or observed_at,
            last_seen_at=observed_at,
            **normalized,
        )
        db.add(node)
        await db.flush()
        node_lookup[normalized["external_id"]] = node.id
    for normalized in result.relationships:
        relationship_data = dict(normalized)
        source_external_id = relationship_data.pop("source_external_id")
        target_external_id = relationship_data.pop("target_external_id")
        db.add(
            DirectoryRelationship(
                snapshot_id=snapshot.id,
                source_file_id=provenance_file_id,
                source_node_id=node_lookup[source_external_id],
                target_node_id=node_lookup[target_external_id],
                stable_fingerprint=_stable_fingerprint(
                    normalized["external_id"],
                    source_external_id,
                    target_external_id,
                    normalized["relationship_type"],
                ),
                first_seen_at=previous_relationship_first_seen.get(normalized["external_id"]) or observed_at,
                last_seen_at=observed_at,
                **relationship_data,
            )
        )
    await record_audit(
        db,
        request,
        "dataset.imported",
        "dataset",
        f"Imported {len(result.nodes)} nodes and {len(result.relationships)} relationships",
        user=user,
        entity_id=dataset.id,
        project_id=project.id,
        context={"snapshot_id": snapshot.id, "source_type": source_type},
    )
    await db.commit()
    await db.refresh(dataset)
    await db.refresh(snapshot)
    return dataset, snapshot


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(db: DB, user: CurrentUser) -> list[Project]:
    query = (
        select(Project)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Project.workspace_id)
        .where(WorkspaceMembership.user_id == user.id)
        .order_by(Project.updated_at.desc())
    )
    return list((await db.scalars(query)).all())


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(payload: ProjectCreate, request: Request, db: DB, user: EditorCsrf) -> Project:
    await workspace_membership(db, user, payload.workspace_id, minimum_role="analyst")
    project = Project(
        workspace_id=payload.workspace_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        created_by=user.id,
    )
    db.add(project)
    await db.flush()
    await record_audit(
        db,
        request,
        "project.created",
        "project",
        "Project created",
        user=user,
        entity_id=project.id,
        project_id=project.id,
    )
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: DB, user: CurrentUser) -> Project:
    return await project_or_404(db, user, project_id)


@router.get("/projects/{project_id}/statistics", response_model=ProjectStatisticsResponse)
async def project_statistics(project_id: str, db: DB, user: CurrentUser) -> ProjectStatisticsResponse:
    await project_or_404(db, user, project_id)
    latest_import_at = await db.scalar(select(func.max(Dataset.created_at)).where(Dataset.project_id == project_id))
    snapshot_ids = select(GraphSnapshot.id).where(GraphSnapshot.project_id == project_id)

    async def count(column: Any, condition: Any) -> int:
        return int(await db.scalar(select(func.count(column)).where(condition)) or 0)

    activity = list(
        (
            await db.scalars(
                select(AuditEvent)
                .where(AuditEvent.project_id == project_id)
                .order_by(AuditEvent.created_at.desc())
                .limit(10)
            )
        ).all()
    )
    return ProjectStatisticsResponse(
        project_id=project_id,
        latest_import_at=latest_import_at,
        import_count=await count(Dataset.id, Dataset.project_id == project_id),
        snapshot_count=await count(GraphSnapshot.id, GraphSnapshot.project_id == project_id),
        node_count=await count(DirectoryNode.id, DirectoryNode.snapshot_id.in_(snapshot_ids)),
        relationship_count=await count(
            DirectoryRelationship.id,
            DirectoryRelationship.snapshot_id.in_(snapshot_ids),
        ),
        finding_count=await count(RiskFinding.id, RiskFinding.project_id == project_id),
        path_count=int(
            await db.scalar(
                select(func.count(PrivilegePath.id))
                .join(PathAnalysis, PathAnalysis.id == PrivilegePath.path_analysis_id)
                .where(PathAnalysis.project_id == project_id)
            )
            or 0
        ),
        remediation_plan_count=await count(RemediationPlan.id, RemediationPlan.project_id == project_id),
        comparison_count=await count(SnapshotComparison.id, SnapshotComparison.project_id == project_id),
        report_count=await count(Report.id, Report.project_id == project_id),
        recent_activity=[
            {
                "id": event.id,
                "action": event.action,
                "summary": event.summary,
                "outcome": event.outcome,
                "created_at": event.created_at,
            }
            for event in activity
        ],
    )


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str, payload: ProjectUpdate, request: Request, db: DB, user: EditorCsrf
) -> Project:
    project = await project_or_404(db, user, project_id, minimum_role="analyst")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value.strip() if isinstance(value, str) else value)
    await record_audit(
        db,
        request,
        "project.updated",
        "project",
        "Project updated",
        user=user,
        entity_id=project.id,
        project_id=project.id,
    )
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, request: Request, db: DB, user: CsrfUser) -> None:
    project = await project_or_404(db, user, project_id, minimum_role="administrator")
    snapshot_ids = list(
        (await db.scalars(select(GraphSnapshot.id).where(GraphSnapshot.project_id == project.id))).all()
    )
    reports = list((await db.scalars(select(Report).where(Report.project_id == project.id))).all())
    report_paths = [report.storage_path for report in reports]
    for report in reports:
        await db.delete(report)
    await record_audit(
        db,
        request,
        "project.deleted",
        "project",
        "Project deleted",
        user=user,
        entity_id=project.id,
        project_id=project.id,
    )
    await db.delete(project)
    await db.commit()
    _remove_report_files(report_paths)
    for snapshot_id in snapshot_ids:
        graph_cache.invalidate(snapshot_id)


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetResponse])
async def list_datasets(project_id: str, db: DB, user: CurrentUser) -> list[Dataset]:
    await project_or_404(db, user, project_id)
    return list(
        (
            await db.scalars(
                select(Dataset).where(Dataset.project_id == project_id).order_by(Dataset.created_at.desc())
            )
        ).all()
    )


@router.post("/projects/{project_id}/datasets/validate-json", response_model=ValidationResponse)
async def validate_json_dataset(
    project_id: str,
    db: DB,
    user: EditorCsrf,
    request: Request,
    file: Annotated[UploadFile, File()],
) -> ValidationResponse:
    project = await project_or_404(db, user, project_id, minimum_role="analyst")
    if not (file.filename or "").lower().endswith(".json"):
        raise AppError(415, "Unsupported file", "Upload a .json file.", code="unsupported_file")
    result = validate_json_bytes(await file.read(get_settings().max_upload_bytes + 1), get_settings())
    await record_audit(
        db,
        request,
        "dataset.validated",
        "project",
        "JSON dataset validation completed",
        user=user,
        entity_id=project.id,
        project_id=project.id,
        context={"valid": result.valid},
    )
    await db.commit()
    return _validation_response(result)


@router.post("/projects/{project_id}/datasets/validate-csv", response_model=ValidationResponse)
async def validate_csv_dataset(
    project_id: str,
    db: DB,
    user: EditorCsrf,
    request: Request,
    nodes_file: Annotated[UploadFile | None, File()] = None,
    relationships_file: Annotated[UploadFile | None, File()] = None,
    zip_file: Annotated[UploadFile | None, File()] = None,
) -> ValidationResponse:
    await project_or_404(db, user, project_id, minimum_role="analyst")
    settings = get_settings()
    if zip_file:
        if not (zip_file.filename or "").lower().endswith(".zip"):
            raise AppError(415, "Unsupported file", "Upload a .zip archive.", code="unsupported_file")
        result = validate_zip_bytes(await zip_file.read(settings.max_upload_bytes + 1), settings)
    elif nodes_file and relationships_file:
        if not (nodes_file.filename or "").lower().endswith(".csv") or not (
            relationships_file.filename or ""
        ).lower().endswith(".csv"):
            raise AppError(415, "Unsupported file", "Upload documented .csv files.", code="unsupported_file")
        result = validate_csv_bytes(await nodes_file.read(), await relationships_file.read(), settings)
    else:
        raise AppError(
            422,
            "Files required",
            "Upload a ZIP or both documented CSV files.",
            code="missing_files",
        )
    await record_audit(
        db,
        request,
        "dataset.validated",
        "project",
        "CSV dataset validation completed",
        user=user,
        entity_id=project_id,
        project_id=project_id,
        context={"valid": result.valid},
    )
    await db.commit()
    return _validation_response(result)


@router.post("/projects/{project_id}/datasets/import-demo", response_model=SnapshotResponse, status_code=201)
async def import_demo(
    project_id: str,
    payload: DemoImportRequest,
    request: Request,
    db: DB,
    user: EditorCsrf,
) -> GraphSnapshot:
    project = await project_or_404(db, user, project_id, minimum_role="analyst")
    demo = get_demo(payload.demo)
    canonical = json.dumps(demo, sort_keys=True, separators=(",", ":")).encode()
    result = validate_records(
        demo["nodes"],
        demo["relationships"],
        hashlib.sha256(canonical).hexdigest(),
        get_settings(),
    )
    _, snapshot = await _import_result(
        db=db,
        request=request,
        user=user,
        project=project,
        result=result,
        source_type="demo",
        source_filename=None,
        source_files=[
            {
                "logical_name": "synthetic-demo.json",
                "original_name": f"{payload.demo}-demo.json",
                "content_hash": hashlib.sha256(canonical).hexdigest(),
                "media_type": "application/json",
                "size_bytes": len(canonical),
            }
        ],
        name=str(demo["metadata"]["name"]),
        authorization_confirmed=payload.authorization_confirmed,
        acknowledged_warning_codes={message.code for message in result.messages if message.level == "warning"},
    )
    return snapshot


@router.post("/projects/{project_id}/datasets/import-json", response_model=SnapshotResponse, status_code=201)
async def import_json_dataset(
    project_id: str,
    request: Request,
    db: DB,
    user: EditorCsrf,
    file: Annotated[UploadFile, File()],
    validation_digest: Annotated[str, Form()],
    authorization_confirmed: Annotated[bool, Form()],
    acknowledged_warnings: Annotated[str, Form()] = "",
    name: Annotated[str, Form()] = "Imported JSON dataset",
) -> GraphSnapshot:
    project = await project_or_404(db, user, project_id, minimum_role="analyst")
    if not (file.filename or "").lower().endswith(".json"):
        raise AppError(415, "Unsupported file", "Upload a .json file.", code="unsupported_file")
    raw = await file.read(get_settings().max_upload_bytes + 1)
    result = validate_json_bytes(raw, get_settings())
    if result.digest != validation_digest:
        raise AppError(409, "File changed", "Validate this exact file again.", code="digest_mismatch")
    _, snapshot = await _import_result(
        db=db,
        request=request,
        user=user,
        project=project,
        result=result,
        source_type="json",
        source_filename=file.filename,
        source_files=[
            {
                "logical_name": "dataset.json",
                "original_name": file.filename or "dataset.json",
                "content_hash": hashlib.sha256(raw).hexdigest(),
                "media_type": file.content_type or "application/json",
                "size_bytes": len(raw),
            }
        ],
        name=name,
        authorization_confirmed=authorization_confirmed,
        acknowledged_warning_codes={code.strip() for code in acknowledged_warnings.split(",") if code.strip()},
    )
    return snapshot


@router.post(
    "/projects/{project_id}/datasets/import-csv",
    response_model=SnapshotResponse,
    status_code=201,
)
async def import_csv_dataset(
    project_id: str,
    request: Request,
    db: DB,
    user: EditorCsrf,
    validation_digest: Annotated[str, Form()],
    authorization_confirmed: Annotated[bool, Form()],
    nodes_file: Annotated[UploadFile | None, File()] = None,
    relationships_file: Annotated[UploadFile | None, File()] = None,
    zip_file: Annotated[UploadFile | None, File()] = None,
    acknowledged_warnings: Annotated[str, Form()] = "",
    name: Annotated[str, Form()] = "Imported CSV dataset",
) -> GraphSnapshot:
    project = await project_or_404(db, user, project_id, minimum_role="analyst")
    settings = get_settings()
    source_files: list[dict[str, object]]
    if zip_file:
        if not (zip_file.filename or "").lower().endswith(".zip"):
            raise AppError(415, "Unsupported file", "Upload a .zip archive.", code="unsupported_file")
        raw_zip = await zip_file.read(settings.max_upload_bytes + 1)
        result = validate_zip_bytes(raw_zip, settings)
        source_files = [
            {
                "logical_name": "dataset.zip",
                "original_name": zip_file.filename or "dataset.zip",
                "content_hash": hashlib.sha256(raw_zip).hexdigest(),
                "media_type": zip_file.content_type or "application/zip",
                "size_bytes": len(raw_zip),
            }
        ]
        filename = zip_file.filename
        source_type = "csv_zip"
    elif nodes_file and relationships_file:
        if not (nodes_file.filename or "").lower().endswith(".csv") or not (
            relationships_file.filename or ""
        ).lower().endswith(".csv"):
            raise AppError(415, "Unsupported file", "Upload documented .csv files.", code="unsupported_file")
        raw_nodes = await nodes_file.read(settings.max_upload_bytes + 1)
        raw_relationships = await relationships_file.read(settings.max_upload_bytes + 1)
        result = validate_csv_bytes(raw_nodes, raw_relationships, settings)
        source_files = [
            {
                "logical_name": "nodes.csv",
                "original_name": nodes_file.filename or "nodes.csv",
                "content_hash": hashlib.sha256(raw_nodes).hexdigest(),
                "media_type": nodes_file.content_type or "text/csv",
                "size_bytes": len(raw_nodes),
            },
            {
                "logical_name": "relationships.csv",
                "original_name": relationships_file.filename or "relationships.csv",
                "content_hash": hashlib.sha256(raw_relationships).hexdigest(),
                "media_type": relationships_file.content_type or "text/csv",
                "size_bytes": len(raw_relationships),
            },
        ]
        filename = f"{nodes_file.filename},{relationships_file.filename}"
        source_type = "csv"
    else:
        raise AppError(
            422,
            "Files required",
            "Upload a ZIP or both documented CSV files.",
            code="missing_files",
        )
    if result.digest != validation_digest:
        raise AppError(409, "File changed", "Validate these exact files again.", code="digest_mismatch")
    _, snapshot = await _import_result(
        db=db,
        request=request,
        user=user,
        project=project,
        result=result,
        source_type=source_type,
        source_filename=filename,
        source_files=source_files,
        name=name,
        authorization_confirmed=authorization_confirmed,
        acknowledged_warning_codes={code.strip() for code in acknowledged_warnings.split(",") if code.strip()},
    )
    return snapshot


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: str, db: DB, user: CurrentUser) -> Dataset:
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise AppError(404, "Dataset not found", "The import does not exist.", code="not_found")
    await project_or_404(db, user, dataset.project_id)
    return dataset


@router.get("/datasets/{dataset_id}/progress", response_model=ImportProgressResponse)
async def import_progress(dataset_id: str, db: DB, user: CurrentUser) -> ImportProgressResponse:
    dataset = await get_dataset(dataset_id, db, user)
    return ImportProgressResponse(
        id=dataset.id,
        status=dataset.import_status,
        progress_percent=dataset.progress_percent,
        node_count=dataset.node_count,
        relationship_count=dataset.relationship_count,
        warning_count=dataset.warning_count,
        rejected_record_count=dataset.rejected_record_count,
        validation_summary=dataset.validation_summary,
    )


@router.post("/datasets/{dataset_id}/cancel", response_model=ImportProgressResponse)
async def cancel_import(dataset_id: str, request: Request, db: DB, user: EditorCsrf) -> ImportProgressResponse:
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise AppError(404, "Dataset not found", "The import does not exist.", code="not_found")
    await project_or_404(db, user, dataset.project_id, minimum_role="analyst")
    if dataset.import_status == "complete":
        raise AppError(
            409,
            "Import already complete",
            "Completed imports cannot be cancelled; delete the import instead.",
            code="already_complete",
        )
    dataset.import_status = "cancelled"
    dataset.cancelled_at = datetime.now(UTC)
    await record_audit(
        db,
        request,
        "dataset.cancelled",
        "dataset",
        "Import cancelled",
        user=user,
        entity_id=dataset.id,
        project_id=dataset.project_id,
    )
    await db.commit()
    return ImportProgressResponse(
        id=dataset.id,
        status=dataset.import_status,
        progress_percent=dataset.progress_percent,
        node_count=dataset.node_count,
        relationship_count=dataset.relationship_count,
        warning_count=dataset.warning_count,
        rejected_record_count=dataset.rejected_record_count,
        validation_summary=dataset.validation_summary,
    )


@router.delete("/datasets/{dataset_id}", status_code=204)
async def delete_dataset(dataset_id: str, request: Request, db: DB, user: EditorCsrf) -> None:
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise AppError(404, "Dataset not found", "The import does not exist.", code="not_found")
    await project_or_404(db, user, dataset.project_id, minimum_role="analyst")
    snapshots = list((await db.scalars(select(GraphSnapshot).where(GraphSnapshot.dataset_id == dataset.id))).all())
    snapshot_ids = [snapshot.id for snapshot in snapshots]
    comparisons: list[SnapshotComparison] = []
    if snapshot_ids:
        comparisons = list(
            (
                await db.scalars(
                    select(SnapshotComparison).where(
                        SnapshotComparison.before_snapshot_id.in_(snapshot_ids)
                        | SnapshotComparison.after_snapshot_id.in_(snapshot_ids)
                    )
                )
            ).all()
        )
    comparison_ids = [comparison.id for comparison in comparisons]
    report_conditions = [Report.snapshot_id.in_(snapshot_ids)]
    if comparison_ids:
        report_conditions.append(Report.comparison_id.in_(comparison_ids))
    reports = list((await db.scalars(select(Report).where(or_(*report_conditions)))).all()) if snapshot_ids else []
    report_paths = [report.storage_path for report in reports]
    for report in reports:
        await db.delete(report)
    for comparison in comparisons:
        await db.delete(comparison)
    for snapshot in snapshots:
        await db.delete(snapshot)
    await db.delete(dataset)
    await record_audit(
        db,
        request,
        "dataset.deleted",
        "dataset",
        "Import deleted",
        user=user,
        entity_id=dataset.id,
        project_id=dataset.project_id,
    )
    await db.commit()
    _remove_report_files(report_paths)
    for snapshot_id in snapshot_ids:
        graph_cache.invalidate(snapshot_id)


@router.get("/projects/{project_id}/snapshots", response_model=list[SnapshotResponse])
async def list_snapshots(project_id: str, db: DB, user: CurrentUser) -> list[GraphSnapshot]:
    await project_or_404(db, user, project_id)
    return list(
        (
            await db.scalars(
                select(GraphSnapshot)
                .where(GraphSnapshot.project_id == project_id)
                .order_by(GraphSnapshot.version.desc())
            )
        ).all()
    )


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotResponse)
async def get_snapshot(snapshot_id: str, db: DB, user: CurrentUser) -> GraphSnapshot:
    snapshot = await db.get(GraphSnapshot, snapshot_id)
    if not snapshot:
        raise AppError(404, "Snapshot not found", "The snapshot does not exist.", code="not_found")
    await project_or_404(db, user, snapshot.project_id)
    return snapshot
