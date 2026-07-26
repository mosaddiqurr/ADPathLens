import csv
import io
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import func, select

from app.api.deps import (
    DB,
    Administrator,
    AdministratorCsrf,
    CurrentUser,
)
from app.audit.service import record_audit
from app.core.errors import AppError
from app.graph.catalog import RELATIONSHIP_CATALOG
from app.graph.service import graph_cache
from app.models.entities import (
    ApplicationSetting,
    AuditEvent,
    RiskRuleConfiguration,
)
from app.reporting.service import safe_csv_cell
from app.schemas.administration import (
    AuditEventResponse,
    RiskRuleConfigurationCreate,
    RiskRuleConfigurationResponse,
    SettingUpdate,
)
from app.schemas.graph import PageResponse

router = APIRouter(tags=["administration"])

RULE_CATALOG: dict[str, str] = {
    "APL-001": "Non-privileged principal controls a privileged asset",
    "APL-002": "Lower-privileged group controls a privileged group",
    "APL-003": "Administrative access to a host with a privileged session",
    "APL-004": "Editable GPO affects privileged systems",
    "APL-005": "Privileged account present on a lower-trust workstation",
    "APL-006": "Multiple low-privileged sources reach one high-value target",
    "APL-007": "Reset rights over a stronger account",
    "APL-008": "Lower-privileged control of certificate infrastructure",
    "APL-009": "Overprivileged service account",
    "APL-010": "Disabled account retains active permissions",
    "APL-011": "Excessive nested membership",
    "APL-012": "Unusually high control-edge degree",
    "APL-013": "Critical path depends on low-confidence evidence",
    "APL-014": "Missing or incomplete relationship evidence",
    "APL-015": "Administrative control over a high-value computer",
    "APL-016": "Delegation relationship requires review",
    "APL-017": "Relationship includes an unresolved entity type",
    "APL-018": "Broad privileged group membership requires review",
}

ALLOWED_SETTINGS: dict[str, type[int] | type[bool] | type[str]] = {
    "ui.default_page_size": int,
    "analysis.default_maximum_depth": int,
    "graph.render_warning_nodes": int,
    "ui.default_theme": str,
    "demo.guided_walkthrough": bool,
}


@router.get("/capabilities")
async def capabilities(user: CurrentUser) -> dict[str, object]:
    return {
        "role": user.role,
        "can_administer": user.role == "administrator",
        "can_edit": user.role in {"administrator", "analyst"},
        "can_view": True,
        "demo_mode": True,
        "report_formats": ["html", "pdf", "json", "csv"],
        "analysis_algorithms": [
            "shortest_hops",
            "lowest_cost",
            "top_paths",
            "reverse_reachability",
        ],
    }


@router.get("/risk/rules")
async def risk_rules(db: DB, _: CurrentUser) -> list[dict[str, object]]:
    configurations = list(
        (
            await db.scalars(
                select(RiskRuleConfiguration).order_by(
                    RiskRuleConfiguration.rule_id,
                    RiskRuleConfiguration.version.desc(),
                )
            )
        ).all()
    )
    latest: dict[str, RiskRuleConfiguration] = {}
    for configuration in configurations:
        latest.setdefault(configuration.rule_id, configuration)
    return [
        {
            "rule_id": rule_id,
            "title": title,
            "catalog_version": "1.0",
            "enabled": latest[rule_id].enabled if rule_id in latest else True,
            "configuration_version": latest[rule_id].version if rule_id in latest else 0,
            "configuration": (latest[rule_id].configuration_json if rule_id in latest else {}),
        }
        for rule_id, title in RULE_CATALOG.items()
    ]


@router.post(
    "/risk/rules/{rule_id}/configuration",
    response_model=RiskRuleConfigurationResponse,
    status_code=201,
)
async def configure_risk_rule(
    rule_id: str,
    payload: RiskRuleConfigurationCreate,
    request: Request,
    db: DB,
    user: AdministratorCsrf,
) -> RiskRuleConfiguration:
    if rule_id not in RULE_CATALOG:
        raise AppError(404, "Rule not found", "Choose a rule from the catalog.", code="not_found")
    unknown_relationships = set(payload.relationship_weights) - set(RELATIONSHIP_CATALOG)
    if unknown_relationships:
        raise AppError(
            422,
            "Unknown relationship type",
            "All configured weights must use catalog relationship types.",
            code="relationship_type",
        )
    latest_version = (
        await db.scalar(
            select(func.coalesce(func.max(RiskRuleConfiguration.version), 0)).where(
                RiskRuleConfiguration.rule_id == rule_id
            )
        )
        or 0
    )
    configuration = RiskRuleConfiguration(
        rule_id=rule_id,
        version=latest_version + 1,
        enabled=payload.enabled,
        configuration_json={
            "relationship_weights": payload.relationship_weights,
            "scoring_overrides": payload.scoring_overrides,
        },
        changed_by=user.id,
    )
    db.add(configuration)
    await record_audit(
        db,
        request,
        "risk_rule.configured",
        "risk_rule_configuration",
        "Risk rule configuration version created",
        user=user,
        entity_id=configuration.id,
        context={"rule_id": rule_id, "version": configuration.version},
    )
    await db.commit()
    await db.refresh(configuration)
    graph_cache.clear()
    return configuration


@router.get("/settings")
async def list_settings(db: DB, _: Administrator) -> list[dict[str, object]]:
    settings = list((await db.scalars(select(ApplicationSetting))).all())
    stored = {setting.key: setting for setting in settings}
    return [
        {
            "key": key,
            "value": stored[key].value_json.get("value") if key in stored else None,
            "configured": key in stored,
        }
        for key in ALLOWED_SETTINGS
    ]


@router.patch("/settings/{key}")
async def update_setting(
    key: str,
    payload: SettingUpdate,
    request: Request,
    db: DB,
    user: AdministratorCsrf,
) -> dict[str, object]:
    expected_type = ALLOWED_SETTINGS.get(key)
    if not expected_type:
        raise AppError(
            404,
            "Setting not found",
            "Only allow-listed non-secret settings can be changed.",
            code="not_found",
        )
    if type(payload.value) is not expected_type:
        raise AppError(
            422,
            "Invalid setting value",
            f"This setting requires {expected_type.__name__}.",
            code="setting_type",
        )
    setting = await db.get(ApplicationSetting, key)
    if setting:
        setting.value_json = {"value": payload.value}
        setting.changed_by = user.id
    else:
        setting = ApplicationSetting(key=key, value_json={"value": payload.value}, changed_by=user.id)
        db.add(setting)
    await record_audit(
        db,
        request,
        "setting.updated",
        "application_setting",
        "Allow-listed application setting updated",
        user=user,
        entity_id=key,
    )
    await db.commit()
    return {"key": key, "value": payload.value, "configured": True}


@router.get("/audit/events", response_model=PageResponse)
async def audit_events(
    db: DB,
    _: Administrator,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    action: str = "",
    entity_type: str = "",
) -> PageResponse:
    conditions = []
    if action:
        conditions.append(AuditEvent.action == action)
    if entity_type:
        conditions.append(AuditEvent.entity_type == entity_type)
    total = await db.scalar(select(func.count(AuditEvent.id)).where(*conditions)) or 0
    events = list(
        (
            await db.scalars(
                select(AuditEvent)
                .where(*conditions)
                .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return PageResponse(
        items=[AuditEventResponse.model_validate(event).model_dump() for event in events],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/audit/events/export")
async def export_audit_events(db: DB, _: Administrator) -> Response:
    events = list((await db.scalars(select(AuditEvent).order_by(AuditEvent.created_at, AuditEvent.id))).all())
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "created_at",
            "user_id",
            "action",
            "entity_type",
            "entity_id",
            "summary",
            "source_ip",
        ]
    )
    for event in events:
        writer.writerow(
            [
                safe_csv_cell(event.created_at.isoformat()),
                safe_csv_cell(event.user_id),
                safe_csv_cell(event.action),
                safe_csv_cell(event.entity_type),
                safe_csv_cell(event.entity_id),
                safe_csv_cell(event.summary),
                safe_csv_cell(event.source_ip),
            ]
        )
    return Response(
        content=output.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="adpathlens-audit.csv"'},
    )
