"""Explainable changes between explicit access states or observed HTTP captures."""

from __future__ import annotations

import re
from typing import Any, Literal, cast

from app.comparison.engine import compare_observations
from app.comparison.normalization import redact_json, redact_text
from app.core.problems import ApiProblem
from app.parsers.states import CaptureRecord, Dataset, parse_input
from app.schemas.comparison import (
    AccessRecord,
    Change,
    CompareRequest,
    ComparisonResult,
    Summary,
)

ROLE_RANK = {
    "viewer": 0,
    "reader": 0,
    "read-only": 0,
    "developer": 1,
    "editor": 1,
    "admin": 2,
    "administrator": 2,
    "owner": 2,
}
ADMIN_ROLES = {"admin", "administrator", "owner"}
ADMIN_ACTIONS = {"admin", "administrator", "manage", "fullaccess"}
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
Severity = Literal["critical", "high", "medium", "low", "info"]
Direction = Literal["gained", "lost", "changed"]


def _state(record: AccessRecord | None) -> str:
    if record is None:
        return "Not listed"
    if record.effect == "deny":
        return "Denied"
    return record.role or "Allowed"


def _risk(
    record: AccessRecord,
    previous: AccessRecord | None,
    *,
    gained: bool,
) -> tuple[Severity, str, str]:
    rules: list[tuple[Severity, str, str]] = []
    sensitive = record.sensitive or bool(previous and previous.sensitive)
    if gained:
        new_grant = previous is None or previous.effect != "allow"
        admin_role = (record.role or "").casefold() in ADMIN_ROLES
        admin_action = (
            new_grant and re.split(r"[.:/]", record.action.casefold())[-1] in ADMIN_ACTIONS
        )
        admin = admin_role or admin_action
        wildcard = "*" in record.resource or "*" in record.action
        if record.principal == "Public":
            rules.append(
                (
                    "critical" if admin or wildcard or sensitive else "high",
                    "Public access",
                    "Unauthenticated users gained access to this resource.",
                )
            )
        if admin:
            rules.append(
                (
                    "high",
                    "Privilege escalation"
                    if previous and previous.effect == "allow"
                    else "New admin access",
                    "Administrator access permits management actions that were not previously "
                    "listed for this principal."
                    if admin_role
                    else "A new grant lists a management action that was not previously allowed "
                    "for this principal.",
                )
            )
        elif (
            previous
            and previous.effect == "allow"
            and ROLE_RANK.get((previous.role or "").casefold()) is not None
            and ROLE_RANK.get((record.role or "").casefold()) is not None
        ):
            rules.append(
                (
                    "medium",
                    "Privilege escalation",
                    "The listed role changed to a broader recognized role.",
                )
            )
        if wildcard:
            rules.append(
                (
                    "high",
                    "Broader permissions",
                    "The new grant contains a wildcard, which may cover additional actions "
                    "or resources. Wildcard coverage is not evaluated.",
                )
            )
        if sensitive:
            rules.append(
                (
                    "medium",
                    "Sensitive access",
                    "Access was gained to a resource explicitly marked sensitive in the input.",
                )
            )
        if previous and previous.effect == "deny":
            rules.append(
                (
                    "high",
                    "Explicit deny removed",
                    "An explicit denial was replaced by a listed grant.",
                )
            )
    if rules:
        severity, category, _ = min(rules, key=lambda rule: SEVERITY_ORDER[rule[0]])
        return severity, category, " ".join(dict.fromkeys(rule[2] for rule in rules))
    return "info", "Access gained", "A new access grant is listed in the After snapshot."


def _snapshot_changes(before: Dataset, after: Dataset) -> tuple[list[Change], int]:
    old = {r.key: r for r in cast(list[AccessRecord], before.records)}
    new = {r.key: r for r in cast(list[AccessRecord], after.records)}
    changes: list[Change] = []
    unchanged = 0
    for key in sorted(old.keys() | new.keys()):
        previous, current = old.get(key), new.get(key)
        if (
            previous
            and current
            and (previous.effect, previous.role)
            == (
                current.effect,
                current.role,
            )
        ):
            unchanged += 1
            continue
        record = current or previous
        if record is None:
            raise ValueError("Inconsistent comparison records.")
        direction: Direction = "changed"
        severity: Severity = "info"
        category, why = "Access rule changed", "The listed access rule changed."
        if (
            current
            and current.effect == "allow"
            and (previous is None or previous.effect != "allow")
        ):
            direction = "gained"
        elif (
            previous
            and previous.effect == "allow"
            and (current is None or current.effect != "allow")
        ):
            direction = "lost"
        elif previous and current and previous.effect == current.effect == "allow":
            previous_rank = ROLE_RANK.get((previous.role or "").casefold())
            current_rank = ROLE_RANK.get((current.role or "").casefold())
            if (
                previous_rank is not None
                and current_rank is not None
                and previous_rank != current_rank
            ):
                direction = "gained" if current_rank > previous_rank else "lost"
            else:
                category = "Role changed"
                why = (
                    "The role label changed. These labels do not establish a permission hierarchy."
                )
                if (current.role or "").casefold() in ADMIN_ROLES and (
                    previous.role or ""
                ).casefold() not in ADMIN_ROLES:
                    severity, category = "high", "New admin role"
                    why = "The role changed to an administrator label. The preceding role's "
                    why += "permissions are unknown, so the scope of the gain needs review."
        if direction == "gained":
            if current is None:
                raise ValueError("Inconsistent gained record.")
            severity, category, why = _risk(record, previous, gained=True)
            summary = (
                f"{record.principal} gained {current.role or record.action} on {record.resource}."
            )
        elif direction == "lost":
            if previous is None:
                raise ValueError("Inconsistent lost record.")
            category = "Access lost"
            why = (
                "Previously listed access is explicitly denied in the After snapshot."
                if current
                else "Previously listed access is absent from the After snapshot. "
                "This does not prove that live access is blocked."
            )
            summary = (
                f"{record.principal} lost {previous.role or record.action} on {record.resource}."
            )
        elif previous and previous.effect == "deny" and current is None:
            severity, category = "medium", "Explicit deny removed"
            why = (
                "A denial is no longer listed. This does not establish that access is now allowed."
            )
            summary = f"An explicit deny for {record.principal} on {record.resource} was removed."
        elif current and current.effect == "deny" and not previous:
            category = "Explicit deny added"
            why = "The After snapshot contains a new explicit denial."
            summary = f"An explicit deny for {record.principal} on {record.resource} was added."
        else:
            summary = (
                f"{record.principal}: {_state(previous)} → {_state(current)} on {record.resource}."
            )
        evidence: dict[str, Any] = {
            "before": previous.model_dump(exclude_none=True) if previous else None,
            "after": current.model_dump(exclude_none=True) if current else None,
        }
        changes.append(
            Change(
                principal=redact_text(record.principal),
                resource=redact_text(record.resource),
                action=redact_text(record.action),
                before=redact_text(_state(previous)),
                after=redact_text(_state(current)),
                change=direction,
                category=category,
                summary=redact_text(summary),
                severity=severity,
                why=why,
                recommendation=(
                    "Review whether this access was intended and restrict it to the required scope."
                    if severity != "info"
                    else "Confirm that the listed change was intended."
                ),
                evidence=redact_json(evidence),
            )
        )
    return changes, unchanged


def _capture_state(record: CaptureRecord | None) -> str:
    if record is None:
        return "Not captured"
    status = record.observation.status_code
    label = record.access.capitalize() if record.access != "unknown" else "Response"
    return f"{label} · HTTP {status}"


def _temporal_evidence(value: Any) -> Any:
    """Present preserved response-rule evidence with the current product's time labels."""
    labels = {
        "high": "before",
        "low": "after",
        "only_high": "only_before",
        "only_low": "only_after",
        "structure_only_high": "structure_only_before",
        "structure_only_low": "structure_only_after",
    }
    if isinstance(value, dict):
        return {labels.get(key, key): _temporal_evidence(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_temporal_evidence(item) for item in value]
    return value


def _har_changes(before: Dataset, after: Dataset) -> tuple[list[Change], int]:
    old = {r.key: r for r in cast(list[CaptureRecord], before.records)}
    new = {r.key: r for r in cast(list[CaptureRecord], after.records)}
    changes: list[Change] = []
    unchanged = 0
    for key in sorted(old.keys() | new.keys()):
        previous, current = old.get(key), new.get(key)
        record = current or previous
        if record is None:
            raise ValueError("Inconsistent capture records.")
        differences: dict[str, Any] = {}
        direction: Direction = "changed"
        severity: Severity = "info"
        category = "Observed response change"
        why = "Response changes alone do not establish an authorization change. "
        why += "Verify the same principal, request context, and actual authorization decision."
        if previous and current:
            # Preserve the existing JSON/header/redirect/text reasoning, without its old
            # higher-role/lower-role product model or database-backed observations.
            decision = compare_observations(
                previous.observation,
                current.observation,
                expected_behaviour="same_access",
                is_state_changing=record.action in {"POST", "PUT", "PATCH", "DELETE"},
            )
            differences = _temporal_evidence(decision.differences)
            differences["text_diff"] = differences["text_diff"].replace(
                "--- higher-role\n+++ lower-role", "--- Before\n+++ After", 1
            )
            same = (
                previous.observation.status_code == current.observation.status_code
                and previous.observation.sanitized_body_hash
                == current.observation.sanitized_body_hash
                and previous.observation.safe_headers == current.observation.safe_headers
                and previous.access == current.access
                and previous.observation.body_truncated == current.observation.body_truncated
            )
            if same:
                unchanged += 1
                continue
            if previous.access == "denied" and current.access == "allowed":
                direction = "gained"
                sensitive = current.sensitive or previous.sensitive
                severity = (
                    "critical"
                    if record.principal == "Public" and sensitive
                    else "high"
                    if record.principal == "Public" or sensitive
                    else "medium"
                )
                category = (
                    "Public access" if record.principal == "Public" else "Observed access gained"
                )
                why = "The same annotated principal and request changed from a corroborated "
                why += "denial to a corroborated allowed response. Confirm the change was intended."
            elif previous.access == "allowed" and current.access == "denied":
                direction, category = "lost", "Observed access lost"
                why = "The same annotated principal and request changed from a corroborated "
                why += "allowed response to a denial."
        else:
            category = "Capture coverage changed"
            why = "This request appears in only one capture. Capture coverage does not prove "
            why += "that access was gained or lost."
        summary = (
            f"{record.principal} {'gained' if direction == 'gained' else 'lost'} "
            f"{record.action} access to {record.resource}."
            if direction != "changed"
            else f"{record.action} {record.resource}: "
            f"{_capture_state(previous)} → {_capture_state(current)}."
        )
        changes.append(
            Change(
                principal=redact_text(record.principal),
                resource=redact_text(record.resource),
                action=record.action,
                before=_capture_state(previous),
                after=_capture_state(current),
                change=direction,
                category=category,
                summary=redact_text(summary),
                severity=severity,
                why=why,
                recommendation="Verify the authorization decision and whether "
                "the change was intended.",
                evidence={
                    "before": previous.evidence if previous else None,
                    "after": current.evidence if current else None,
                    "response_difference": differences,
                },
            )
        )
    return changes, unchanged


def compare(request: CompareRequest) -> ComparisonResult:
    before = parse_input(request.before, "Before")
    after = parse_input(request.after, "After")
    if before.summary.format != after.summary.format:
        raise ApiProblem(422, "incompatible_inputs", "The two inputs use incompatible formats.")
    if before.summary.format == "snapshot":
        changes, unchanged = _snapshot_changes(before, after)
        limitations = [
            "Snapshots describe explicit listed access, not effective IAM policy evaluation. "
            "Inheritance, conditions, deny precedence across rules, "
            "and wildcard coverage are not evaluated.",
            "Not listed means absent from this input; "
            "it does not prove that live access is blocked.",
            "Only Viewer/Reader, Developer/Editor, and Admin/Administrator/Owner roles have a "
            "recognized ordering. Other role changes require review.",
        ]
    else:
        changes, unchanged = _har_changes(before, after)
        limitations = [
            "HAR captures are observations, not proof of exploitability. HTTP status alone never "
            "establishes an access gain or loss.",
            "Confirmed observed transitions require matching principal/request context, explicit "
            "access annotations, corroborating responses, and complete evidence.",
            "Missing requests, changing query/body context, redirects, and incomplete evidence "
            "remain review items. Repeated identical requests within a capture "
            "are rejected as ambiguous.",
        ]
    changes.sort(
        key=lambda change: (
            SEVERITY_ORDER[change.severity],
            change.principal,
            change.resource,
            change.action,
        )
    )
    return ComparisonResult(
        before=before.summary,
        after=after.summary,
        summary=Summary(
            total=len(changes),
            gained=sum(change.change == "gained" for change in changes),
            lost=sum(change.change == "lost" for change in changes),
            risky=sum(change.severity != "info" for change in changes),
            review=sum(change.change == "changed" for change in changes),
            unchanged=unchanged,
        ),
        changes=changes,
        notes=list(dict.fromkeys([*before.summary.warnings, *after.summary.warnings])),
        limitations=[
            *limitations,
            "Risk levels are review priorities based on the supplied evidence, "
            "not a vulnerability score.",
            "Credential redaction is best effort. Review exports before sharing sensitive data.",
        ],
    )
