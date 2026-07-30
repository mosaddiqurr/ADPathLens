from __future__ import annotations

import ipaddress
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.api.dependencies import CsrfContextDep, CurrentUserDep, DbDep, SettingsDep
from app.audit.service import record_audit
from app.core.problems import ApiProblem
from app.models import Target, TargetAllowlistEntry
from app.schemas.core import (
    AllowlistEntryCreate,
    AllowlistEntryRead,
    AuthorizationConfirmation,
    LabConfirmation,
    TargetCreate,
    TargetRead,
    TargetUpdate,
    TargetValidation,
)
from app.security.ssrf import (
    AllowlistRule,
    DestinationPolicyError,
    normalize_hostname,
    normalize_url,
    resolve_all,
    validate_destination,
)
from app.services.authorization import project_for_user, target_for_user

router = APIRouter(tags=["targets"])


def _origin(destination) -> str:  # type: ignore[no-untyped-def]
    host = f"[{destination.hostname}]" if ":" in destination.hostname else destination.hostname
    default = 443 if destination.scheme == "https" else 80
    suffix = "" if destination.port == default else f":{destination.port}"
    return f"{destination.scheme}://{host}{suffix}"


async def _rules(db: DbDep, target_id: str) -> list[AllowlistRule]:
    rows = (
        (
            await db.execute(
                select(TargetAllowlistEntry).where(TargetAllowlistEntry.target_id == target_id)
            )
        )
        .scalars()
        .all()
    )
    return [AllowlistRule(entry.entry_type, entry.value, entry.allowed_port) for entry in rows]


@router.get("/projects/{project_id}/targets", response_model=list[TargetRead])
async def list_targets(project_id: str, db: DbDep, _user: CurrentUserDep) -> list[TargetRead]:
    await project_for_user(db, _user, project_id)
    targets = (
        (
            await db.execute(
                select(Target)
                .where(Target.project_id == project_id)
                .order_by(Target.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [TargetRead.model_validate(target) for target in targets]


@router.post("/projects/{project_id}/targets", response_model=TargetRead, status_code=201)
async def create_target(
    project_id: str,
    payload: TargetCreate,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    context: CsrfContextDep,
) -> TargetRead:
    await project_for_user(db, context.user, project_id)
    try:
        destination = normalize_url(payload.base_url)
    except DestinationPolicyError as exc:
        raise ApiProblem(422, exc.code, exc.detail) from exc
    if destination.path != "/" or destination.query:
        raise ApiProblem(
            422,
            "target_origin_required",
            "Target base URLs must contain only a scheme, hostname, and optional port.",
        )
    if destination.scheme == "http":
        local_hosts = {"127.0.0.1", "::1", "localhost", "demo-target"}
        if (
            settings.app_env == "production"
            or not payload.local_test_target
            or destination.hostname not in local_hosts
        ):
            raise ApiProblem(
                422,
                "https_required",
                "HTTP is restricted to the explicitly designated local synthetic target.",
            )
    if payload.state_changes_enabled and not any(
        method in {"POST", "PUT", "PATCH", "DELETE"} for method in payload.allowed_methods
    ):
        raise ApiProblem(
            422,
            "state_change_method_required",
            "State-changing policy requires an explicitly allowed state-changing method.",
        )
    target = Target(
        project_id=project_id,
        name=payload.name.strip(),
        base_url=_origin(destination),
        scheme=destination.scheme,
        hostname=destination.hostname,
        port=destination.port,
        follow_redirects=payload.follow_redirects,
        maximum_redirects=payload.maximum_redirects,
        timeout_seconds=payload.timeout_seconds,
        per_run_timeout_seconds=payload.per_run_timeout_seconds,
        request_budget=payload.request_budget,
        request_count_used=0,
        maximum_response_bytes=payload.maximum_response_bytes,
        concurrency_limit=payload.concurrency_limit,
        allowed_path_prefixes=payload.allowed_path_prefixes,
        allowed_methods=payload.allowed_methods,
        tls_policy=payload.tls_policy,
        state_changes_enabled=payload.state_changes_enabled,
        local_test_target=payload.local_test_target,
        authorization_expires_at=payload.authorization_expires_at,
        is_active=False,
        created_by=context.user.id,
    )
    db.add(target)
    await db.flush()
    await record_audit(
        db,
        request,
        action="target_created",
        entity_type="target",
        entity_id=target.id,
        user_id=context.user.id,
        summary="Created an inactive target pending authorization and allowlisting.",
    )
    await db.commit()
    await db.refresh(target)
    return TargetRead.model_validate(target)


@router.get("/targets/{target_id}", response_model=TargetRead)
async def get_target(target_id: str, db: DbDep, _user: CurrentUserDep) -> TargetRead:
    return TargetRead.model_validate(await target_for_user(db, _user, target_id))


@router.patch("/targets/{target_id}", response_model=TargetRead)
async def update_target(
    target_id: str,
    payload: TargetUpdate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> TargetRead:
    target = await target_for_user(db, context.user, target_id)
    data = payload.model_dump(exclude_unset=True)
    if "allowed_path_prefixes" in data:
        data["allowed_path_prefixes"] = TargetCreate.validate_path_prefixes(
            data["allowed_path_prefixes"]
        )
    if "allowed_methods" in data:
        data["allowed_methods"] = TargetCreate.validate_methods(data["allowed_methods"])
    if data.get("is_active"):
        if not target.authorization_confirmed:
            raise ApiProblem(
                400, "target_not_authorized", "Confirm target authorization before activation."
            )
        if not await _rules(db, target.id):
            raise ApiProblem(
                400, "allowlist_required", "Add at least one allowlist entry before activation."
            )
        if target.allow_private_networks and not target.lab_network_confirmed:
            raise ApiProblem(
                400, "lab_confirmation_required", "Private targets require lab confirmation."
            )
        expires_at = data.get("authorization_expires_at", target.authorization_expires_at)
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= datetime.now(UTC):
                raise ApiProblem(
                    400,
                    "target_authorization_expired",
                    "The target authorization has expired.",
                )
    for key, value in data.items():
        setattr(target, key, value)
    await record_audit(
        db,
        request,
        action="target_updated",
        entity_type="target",
        entity_id=target.id,
        user_id=context.user.id,
        summary="Updated target policy.",
    )
    await db.commit()
    await db.refresh(target)
    return TargetRead.model_validate(target)


@router.post("/targets/{target_id}/confirm-authorization", response_model=TargetRead)
async def confirm_authorization(
    target_id: str,
    _payload: AuthorizationConfirmation,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> TargetRead:
    target = await target_for_user(db, context.user, target_id)
    now = datetime.now(UTC)
    target.authorization_confirmed = True
    target.authorization_confirmed_by = context.user.id
    target.authorization_confirmed_at = now
    await record_audit(
        db,
        request,
        action="target_authorization_confirmed",
        entity_type="target",
        entity_id=target.id,
        user_id=context.user.id,
        summary="Confirmed ownership or explicit authorization for a target.",
    )
    await db.commit()
    await db.refresh(target)
    return TargetRead.model_validate(target)


@router.post("/targets/{target_id}/confirm-lab", response_model=TargetRead)
async def confirm_lab(
    target_id: str,
    payload: LabConfirmation,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> TargetRead:
    if context.user.role != "administrator":
        raise ApiProblem(403, "administrator_required", "Administrator access is required.")
    target = await target_for_user(db, context.user, target_id)
    now = datetime.now(UTC)
    target.allow_private_networks = payload.allow_private_networks
    target.lab_network_confirmed = payload.allow_private_networks
    target.lab_network_confirmed_by = context.user.id if payload.allow_private_networks else None
    target.lab_network_confirmed_at = now if payload.allow_private_networks else None
    if not payload.allow_private_networks:
        target.is_active = False
    await record_audit(
        db,
        request,
        action="target_lab_policy_changed",
        entity_type="target",
        entity_id=target.id,
        user_id=context.user.id,
        summary="Changed private-network laboratory policy for a target.",
    )
    await db.commit()
    await db.refresh(target)
    return TargetRead.model_validate(target)


def _normalize_entry(payload: AllowlistEntryCreate) -> str:
    try:
        if payload.entry_type == "hostname":
            return normalize_hostname(payload.value)
        if payload.entry_type == "ip":
            return str(ipaddress.ip_address(payload.value))
        return str(ipaddress.ip_network(payload.value, strict=False))
    except (ValueError, DestinationPolicyError) as exc:
        raise ApiProblem(422, "invalid_allowlist_entry", "The allowlist entry is invalid.") from exc


@router.post(
    "/targets/{target_id}/allowlist",
    response_model=AllowlistEntryRead,
    status_code=201,
)
async def add_allowlist_entry(
    target_id: str,
    payload: AllowlistEntryCreate,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> AllowlistEntryRead:
    target = await target_for_user(db, context.user, target_id)
    entry = TargetAllowlistEntry(
        target_id=target.id,
        entry_type=payload.entry_type,
        value=_normalize_entry(payload),
        allowed_port=payload.allowed_port,
        notes=payload.notes,
        created_by=context.user.id,
    )
    db.add(entry)
    await record_audit(
        db,
        request,
        action="target_allowlist_changed",
        entity_type="target",
        entity_id=target.id,
        user_id=context.user.id,
        summary="Added a target allowlist entry.",
    )
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise ApiProblem(
            409, "allowlist_entry_exists", "This allowlist entry already exists."
        ) from exc
    await db.refresh(entry)
    return AllowlistEntryRead.model_validate(entry)


@router.get(
    "/targets/{target_id}/allowlist",
    response_model=list[AllowlistEntryRead],
)
async def list_allowlist(
    target_id: str, db: DbDep, _user: CurrentUserDep
) -> list[AllowlistEntryRead]:
    await target_for_user(db, _user, target_id)
    entries = (
        (
            await db.execute(
                select(TargetAllowlistEntry)
                .where(TargetAllowlistEntry.target_id == target_id)
                .order_by(TargetAllowlistEntry.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [AllowlistEntryRead.model_validate(entry) for entry in entries]


@router.delete(
    "/targets/{target_id}/allowlist/{entry_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
async def delete_allowlist_entry(
    target_id: str,
    entry_id: str,
    request: Request,
    db: DbDep,
    context: CsrfContextDep,
) -> None:
    target = await target_for_user(db, context.user, target_id)
    entry = await db.get(TargetAllowlistEntry, entry_id)
    if entry is None or entry.target_id != target.id:
        raise ApiProblem(404, "allowlist_entry_not_found", "The allowlist entry was not found.")
    await db.delete(entry)
    target.is_active = False
    await record_audit(
        db,
        request,
        action="target_allowlist_changed",
        entity_type="target",
        entity_id=target.id,
        user_id=context.user.id,
        summary="Removed a target allowlist entry and deactivated the target.",
    )
    await db.commit()


@router.post("/targets/{target_id}/validate", response_model=TargetValidation)
async def validate_target(target_id: str, db: DbDep, _user: CurrentUserDep) -> TargetValidation:
    target = await target_for_user(db, _user, target_id)
    destination = normalize_url(target.base_url)
    try:
        try:
            literal = ipaddress.ip_address(target.hostname)
            resolved = [str(literal)]
        except ValueError:
            resolved = await resolve_all(target.hostname, target.port)
        validated = validate_destination(
            destination,
            resolved,
            target.hostname,
            target.port,
            await _rules(db, target.id),
            authorization_confirmed=target.authorization_confirmed,
            allow_private_networks=target.allow_private_networks,
            lab_network_confirmed=target.lab_network_confirmed,
        )
    except DestinationPolicyError as exc:
        raise ApiProblem(422, exc.code, exc.detail) from exc
    return TargetValidation(
        valid=True,
        normalized_url=destination.url,
        resolved_addresses=validated,
    )
