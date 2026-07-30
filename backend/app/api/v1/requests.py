from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from fastapi import APIRouter, File, Request, UploadFile
from sqlalchemy import select

from app.api.dependencies import (
    CsrfContextDep,
    CurrentUserDep,
    DbDep,
    SettingsDep,
)
from app.audit.service import record_audit
from app.core.problems import ApiProblem
from app.models import ImportedRequest, RequestCollection, Target, User
from app.parsers.request_import import (
    STATE_CHANGING_METHODS,
    ParsedRequest,
    RequestImportError,
    parse_curl,
    parse_har,
    parse_raw_http,
    split_headers,
    validate_method,
    validate_relative_path,
)
from app.schemas.requests import (
    CurlRequestImport,
    HarCandidate,
    ImportedRequestRead,
    ManualRequestCreate,
    RawRequestImport,
    RequestCollectionCreate,
    RequestCollectionRead,
)
from app.security.crypto import KeyRing
from app.services.authorization import project_for_user, target_for_user
from app.services.request_policy import validate_request_policy

router = APIRouter(tags=["request definitions"])


@lru_cache
def _keyring(active: str, old: str) -> KeyRing:
    return KeyRing.from_settings(active, old)


async def _collection_for_user(db: DbDep, user: User, collection_id: str) -> RequestCollection:
    collection = await db.get(RequestCollection, collection_id)
    if collection is None:
        raise ApiProblem(404, "collection_not_found", "The request collection was not found.")
    await project_for_user(db, user, collection.project_id)
    return collection


@router.get(
    "/projects/{project_id}/request-collections",
    response_model=list[RequestCollectionRead],
)
async def list_collections(
    project_id: str, db: DbDep, user: CurrentUserDep
) -> list[RequestCollectionRead]:
    await project_for_user(db, user, project_id)
    rows = (
        (
            await db.execute(
                select(RequestCollection)
                .where(RequestCollection.project_id == project_id)
                .order_by(RequestCollection.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [RequestCollectionRead.model_validate(row) for row in rows]


@router.post(
    "/projects/{project_id}/request-collections",
    response_model=RequestCollectionRead,
    status_code=201,
)
async def create_collection(
    project_id: str,
    payload: RequestCollectionCreate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> RequestCollectionRead:
    await project_for_user(db, context.user, project_id)
    target = await target_for_user(db, context.user, payload.target_id)
    if target.project_id != project_id:
        raise ApiProblem(404, "target_not_found", "The target was not found in this project.")
    collection = RequestCollection(
        project_id=project_id,
        target_id=target.id,
        name=payload.name.strip(),
        description=payload.description,
        created_by=context.user.id,
    )
    db.add(collection)
    await db.flush()
    await record_audit(
        db,
        request,
        action="request_collection_created",
        entity_type="request_collection",
        entity_id=collection.id,
        user_id=context.user.id,
        summary="Created a bounded request collection.",
    )
    await db.commit()
    await db.refresh(collection)
    return RequestCollectionRead.model_validate(collection)


def _validate_body(parsed: ParsedRequest, max_bytes: int) -> None:
    if len(parsed.body.encode()) > max_bytes:
        raise ApiProblem(413, "request_body_too_large", "The request body exceeds the limit.")
    if parsed.content_type and "json" in parsed.content_type.lower() and parsed.body:
        try:
            json.loads(parsed.body)
        except json.JSONDecodeError as exc:
            raise ApiProblem(422, "invalid_json_body", "The JSON request body is invalid.") from exc


async def _store_request(
    *,
    project_id: str,
    collection: RequestCollection,
    target: Target,
    name: str,
    import_type: str,
    parsed: ParsedRequest,
    approved_state_change: bool,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
    expected_markers: list[str] | None = None,
    tags: list[str] | None = None,
    sensitivity: str = "internal",
) -> ImportedRequest:
    _validate_body(parsed, settings.max_request_body_bytes)
    state_changing = parsed.method in STATE_CHANGING_METHODS
    validate_request_policy(
        target,
        method=parsed.method,
        path=parsed.path,
        approved_state_change=approved_state_change,
    )
    entity = ImportedRequest(
        project_id=project_id,
        collection_id=collection.id,
        target_id=target.id,
        name=name.strip(),
        import_type=import_type,
        method=parsed.method,
        scheme=target.scheme,
        hostname=target.hostname,
        port=target.port,
        path=parsed.path,
        query_parameters=parsed.query,
        sanitized_headers=parsed.headers,
        content_type=parsed.content_type,
        body_template=parsed.body,
        body_hash=hashlib.sha256(parsed.body.encode()).hexdigest(),
        is_state_changing=state_changing,
        approved_state_change=approved_state_change,
        expected_markers=expected_markers or [],
        tags=tags or [],
        sensitivity=sensitivity,
        created_by=context.user.id,
    )
    db.add(entity)
    await db.flush()
    if parsed.secret_headers:
        ring = _keyring(settings.encryption_master_key, settings.encryption_old_keys)
        entity.encrypted_secret_headers = ring.encrypt(
            json.dumps(parsed.secret_headers, separators=(",", ":")).encode(),
            f"imported_request:{entity.id}:secret_headers",
        )
    await record_audit(
        db,
        request,
        action="request_imported",
        entity_type="imported_request",
        entity_id=entity.id,
        user_id=context.user.id,
        summary=f"Created an explicit {parsed.method} request definition by {import_type}.",
    )
    return entity


async def _resolve_scope(
    db: DbDep,
    context: CsrfContextDep,
    project_id: str,
    collection_id: str,
    target_id: str,
) -> tuple[RequestCollection, Target]:
    await project_for_user(db, context.user, project_id)
    collection = await _collection_for_user(db, context.user, collection_id)
    target = await target_for_user(db, context.user, target_id)
    if collection.project_id != project_id or collection.target_id != target.id:
        raise ApiProblem(404, "collection_not_found", "The request collection was not found.")
    return collection, target


@router.get(
    "/projects/{project_id}/requests",
    response_model=list[ImportedRequestRead],
)
async def list_requests(
    project_id: str, db: DbDep, user: CurrentUserDep
) -> list[ImportedRequestRead]:
    await project_for_user(db, user, project_id)
    rows = (
        (
            await db.execute(
                select(ImportedRequest)
                .where(ImportedRequest.project_id == project_id)
                .order_by(ImportedRequest.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [ImportedRequestRead.model_validate(row) for row in rows]


@router.post(
    "/projects/{project_id}/requests/manual",
    response_model=ImportedRequestRead,
    status_code=201,
)
async def create_manual_request(
    project_id: str,
    payload: ManualRequestCreate,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> ImportedRequestRead:
    collection, target = await _resolve_scope(
        db, context, project_id, payload.collection_id, payload.target_id
    )
    try:
        path, parsed_query = validate_relative_path(payload.path)
        safe, secret = split_headers([[header.name, header.value] for header in payload.headers])
        method = validate_method(payload.method)
    except RequestImportError as exc:
        raise ApiProblem(422, exc.code, exc.detail) from exc
    query = parsed_query + [[pair.name, pair.value] for pair in payload.query_parameters]
    parsed = ParsedRequest(
        method=method,
        path=path,
        query=query,
        headers=safe,
        secret_headers=secret,
        body=payload.body,
        content_type=payload.content_type,
    )
    entity = await _store_request(
        project_id=project_id,
        collection=collection,
        target=target,
        name=payload.name,
        import_type="manual",
        parsed=parsed,
        approved_state_change=payload.approved_state_change,
        request=request,
        db=db,
        settings=settings,
        context=context,
        expected_markers=payload.expected_markers,
        tags=payload.tags,
        sensitivity=payload.sensitivity,
    )
    await db.commit()
    await db.refresh(entity)
    return ImportedRequestRead.model_validate(entity)


@router.post(
    "/projects/{project_id}/requests/import-raw",
    response_model=ImportedRequestRead,
    status_code=201,
)
async def import_raw_request(
    project_id: str,
    payload: RawRequestImport,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> ImportedRequestRead:
    collection, target = await _resolve_scope(
        db, context, project_id, payload.collection_id, payload.target_id
    )
    try:
        parsed = parse_raw_http(payload.raw_request)
    except RequestImportError as exc:
        raise ApiProblem(422, exc.code, exc.detail) from exc
    entity = await _store_request(
        project_id=project_id,
        collection=collection,
        target=target,
        name=payload.name,
        import_type="raw",
        parsed=parsed,
        approved_state_change=payload.approved_state_change,
        request=request,
        db=db,
        settings=settings,
        context=context,
    )
    await db.commit()
    await db.refresh(entity)
    return ImportedRequestRead.model_validate(entity)


@router.post(
    "/projects/{project_id}/requests/import-curl",
    response_model=ImportedRequestRead,
    status_code=201,
)
async def import_curl_request(
    project_id: str,
    payload: CurlRequestImport,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> ImportedRequestRead:
    collection, target = await _resolve_scope(
        db, context, project_id, payload.collection_id, payload.target_id
    )
    try:
        parsed = parse_curl(payload.command)
    except RequestImportError as exc:
        raise ApiProblem(422, exc.code, exc.detail) from exc
    entity = await _store_request(
        project_id=project_id,
        collection=collection,
        target=target,
        name=payload.name,
        import_type="curl",
        parsed=parsed,
        approved_state_change=payload.approved_state_change,
        request=request,
        db=db,
        settings=settings,
        context=context,
    )
    await db.commit()
    await db.refresh(entity)
    return ImportedRequestRead.model_validate(entity)


@router.post(
    "/projects/{project_id}/requests/preview-har",
    response_model=list[HarCandidate],
)
async def preview_har(
    project_id: str,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
    file: UploadFile = File(...),
) -> list[HarCandidate]:
    await project_for_user(db, context.user, project_id)
    data = await file.read(settings.max_har_upload_bytes + 1)
    if len(data) > settings.max_har_upload_bytes:
        raise ApiProblem(413, "har_too_large", "The HAR upload exceeds the size limit.")
    try:
        candidates = parse_har(data)
    except RequestImportError as exc:
        raise ApiProblem(422, exc.code, exc.detail) from exc
    return [
        HarCandidate(
            index=index,
            method=item.method,
            path=item.path,
            content_type=item.content_type,
            has_secrets=bool(item.secret_headers),
            is_state_changing=item.method in STATE_CHANGING_METHODS,
        )
        for index, item in enumerate(candidates)
    ]
