from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

DIRECT_CONTROL = {
    "GenericAll",
    "GenericWrite",
    "WriteOwner",
    "WriteDACL",
    "ResetPassword",
    "ForceChangePassword",
    "AddMember",
    "AdminTo",
    "LocalAdmin",
    "AllExtendedRights",
}


@dataclass(frozen=True)
class Detection:
    rule_id: str
    title: str
    category: str
    base_severity: str
    confidence: str
    description: str
    impact: str
    remediation: str
    node_id: str | None = None
    relationship_id: str | None = None
    signals: tuple[str, ...] = ()
    reducing: tuple[str, ...] = ()
    evidence: dict[str, Any] | None = None


def score_detection(detection: Detection) -> tuple[float, str]:
    score = {"informational": 10.0, "low": 30.0, "medium": 50.0, "high": 75.0}[detection.base_severity]
    score += 10 if "direct_privileged_control" in detection.signals else 0
    score += 8 if "short_path" in detection.signals else 0
    score += min(8, 2 * sum(signal == "independent_path" for signal in detection.signals))
    score += min(6, 2 * sum(signal == "affected_asset" for signal in detection.signals))
    if detection.confidence == "medium":
        score -= 8
    elif detection.confidence in {"low", "unknown"}:
        score -= 15
    score -= 5 if "inherited_only" in detection.reducing else 0
    score -= 15 if "inactive_or_disabled" in detection.reducing else 0
    score -= 10 if "missing_evidence" in detection.reducing else 0
    score = max(0, min(100, score))
    if score < 20:
        severity = "informational"
    elif score < 40:
        severity = "low"
    elif score < 65:
        severity = "medium"
    elif score < 85:
        severity = "high"
    else:
        critical_gate = (
            detection.confidence == "high"
            and "direct_privileged_control" in detection.signals
            and len(set(detection.signals)) >= 3
        )
        severity = "critical" if critical_gate else "high"
    return score, severity


def run_rules(
    graph: nx.MultiDiGraph[str, dict[str, Any], dict[str, Any]],
) -> list[Detection]:
    findings: list[Detection] = []
    seen: set[tuple[str, str | None, str | None]] = set()

    def add(detection: Detection) -> None:
        key = (detection.rule_id, detection.node_id, detection.relationship_id)
        if key not in seen:
            seen.add(key)
            findings.append(detection)

    for source, target, data in graph.edges(data=True):
        source_data = graph.nodes[source]
        target_data = graph.nodes[target]
        confidence = data["confidence"]
        relationship_id = data["relationship_id"]
        evidence = data.get("evidence") or {}
        if data["type"] in DIRECT_CONTROL and not source_data["privileged"] and target_data["privileged"]:
            add(
                Detection(
                    "APL-001",
                    "Non-privileged principal controls a privileged asset",
                    "dangerous_object_permission",
                    "high",
                    confidence,
                    f"{source_data['display_name']} has {data['type']} to privileged {target_data['display_name']}.",
                    "The imported relationship may create a direct route to greater privilege.",
                    data["remediation"],
                    node_id=source,
                    relationship_id=relationship_id,
                    signals=("direct_privileged_control", "short_path"),
                    evidence=evidence,
                )
            )
        if data["type"] in {"AdminTo", "LocalAdmin"} and target_data["high_value"]:
            add(
                Detection(
                    "APL-015",
                    "Administrative control over a high-value computer",
                    "excessive_local_administration",
                    "high",
                    confidence,
                    f"{source_data['display_name']} has administrative control over high-value "
                    f"{target_data['display_name']}.",
                    "Direct administration of a high-value computer warrants priority review.",
                    "Restrict administrative access to dedicated, approved operator groups.",
                    node_id=target,
                    relationship_id=relationship_id,
                    signals=("direct_privileged_control", "affected_asset"),
                    evidence=evidence,
                )
            )
        if data["type"] in {
            "ConstrainedDelegation",
            "UnconstrainedDelegation",
            "ResourceBasedConstrainedDelegation",
            "DelegatedTo",
            "AllowedToDelegate",
        }:
            add(
                Detection(
                    "APL-016",
                    "Delegation relationship requires review",
                    "excessive_delegation",
                    "medium",
                    confidence,
                    "Imported delegation may extend the effective control scope of a principal.",
                    "Delegation can create indirect privilege paths when combined with other rights.",
                    "Limit delegation to documented services and validate every target.",
                    node_id=source,
                    relationship_id=relationship_id,
                    signals=("affected_asset",) if target_data["high_value"] else (),
                    evidence=evidence,
                )
            )
        if source_data["type"] == "Unknown" or target_data["type"] == "Unknown":
            add(
                Detection(
                    "APL-017",
                    "Relationship includes an unresolved entity type",
                    "data_quality_warning",
                    "low",
                    confidence,
                    "An imported relationship includes an entity represented as Unknown.",
                    "Incomplete typing may hide or overstate the meaning of a control path.",
                    "Resolve the source entity type and re-import the authorised dataset.",
                    node_id=source if source_data["type"] == "Unknown" else target,
                    relationship_id=relationship_id,
                    reducing=("missing_evidence",),
                    evidence=evidence,
                )
            )
        if (
            source_data["type"] == "Group"
            and target_data["type"] == "Group"
            and not source_data["privileged"]
            and target_data["privileged"]
            and data["type"] in DIRECT_CONTROL
        ):
            add(
                Detection(
                    "APL-002",
                    "Lower-privileged group controls a privileged group",
                    "excessive_group_membership",
                    "high",
                    confidence,
                    "A lower-privileged group has a direct control relationship to a privileged group.",
                    "Members of the lower-privileged group may inherit a possible control route.",
                    "Remove excessive delegation and review nested group membership.",
                    node_id=source,
                    relationship_id=relationship_id,
                    signals=("direct_privileged_control", "affected_asset"),
                    evidence=evidence,
                )
            )
        if source_data["type"] in {"ServiceAccount", "ManagedServiceAccount"} and data["type"] in DIRECT_CONTROL:
            if graph.out_degree(source) >= 2:
                add(
                    Detection(
                        "APL-004",
                        "Service account has excessive administrative rights",
                        "service_account_overprivilege",
                        "medium",
                        confidence,
                        "A service account has multiple security-relevant control relationships.",
                        "Broad service-account permissions increase exposure if the account is misused.",
                        "Reduce group membership, logon scope, and administrative rights.",
                        node_id=source,
                        relationship_id=relationship_id,
                        evidence=evidence,
                    )
                )
        if not source_data["enabled"] and data["active"] and data["path_eligible"]:
            add(
                Detection(
                    "APL-006",
                    "Disabled account retains an active permission",
                    "stale_privileged_account",
                    "medium",
                    confidence,
                    "A disabled account remains connected to an active security-relevant permission.",
                    "Stale permissions complicate access governance and may be restored unexpectedly.",
                    "Remove obsolete permissions, ownership, and memberships.",
                    node_id=source,
                    relationship_id=relationship_id,
                    reducing=("inactive_or_disabled",),
                    evidence=evidence,
                )
            )
        if data["type"] == "HasSession" and target_data["privileged"] and not source_data["high_value"]:
            add(
                Detection(
                    "APL-007",
                    "Privileged session appears on a lower-trust computer",
                    "privileged_session_exposure",
                    "high",
                    confidence,
                    "Imported session evidence places a privileged account on a lower-trust computer.",
                    "Administrative access to the computer may combine with this exposure.",
                    "Use privileged-access workstations and remove stale privileged sessions.",
                    node_id=source,
                    relationship_id=relationship_id,
                    signals=("affected_asset",),
                    evidence=evidence,
                )
            )
        if data["type"] == "NestedMemberOf" and target_data["privileged"]:
            add(
                Detection(
                    "APL-008",
                    "Nested group membership creates privilege exposure",
                    "excessive_group_membership",
                    "medium",
                    confidence,
                    "Nested membership connects a lower-tier principal to a privileged group.",
                    "Nested groups can make effective privileges difficult to review.",
                    "Flatten or document nesting and remove unnecessary members.",
                    node_id=source,
                    relationship_id=relationship_id,
                    evidence=evidence,
                )
            )
        if data["type"] == "ResetPassword" and target_data["privileged"]:
            add(
                Detection(
                    "APL-011",
                    "Password-reset right targets a stronger account",
                    "password_reset_privilege",
                    "high",
                    confidence,
                    "A lower-tier principal can reset a more privileged account.",
                    "Delegated reset rights may create a possible direct control path.",
                    "Separate helpdesk rights from privileged-account administration.",
                    node_id=source,
                    relationship_id=relationship_id,
                    signals=("direct_privileged_control", "short_path"),
                    evidence=evidence,
                )
            )
        if data["type"] == "ControlsCertificateTemplate" and target_data["type"] in {
            "CertificateTemplate",
            "CertificateAuthority",
        }:
            add(
                Detection(
                    "APL-012",
                    "Lower-privileged principal controls certificate services",
                    "certificate_services_exposure",
                    "high",
                    confidence,
                    "A principal controls a certificate template or authority.",
                    "Certificate-services control requires specialist validation before drawing conclusions.",
                    "Restrict template and authority control to dedicated administrators.",
                    node_id=source,
                    relationship_id=relationship_id,
                    signals=("affected_asset",),
                    evidence=evidence,
                )
            )
        if confidence in {"low", "unknown"} and (source_data["high_value"] or target_data["high_value"]):
            add(
                Detection(
                    "APL-013",
                    "Important relationship depends on low-confidence data",
                    "data_quality_warning",
                    "informational",
                    confidence,
                    "A security-relevant relationship near a high-value asset has weak confidence.",
                    "Incorrect assumptions can distort path and remediation priorities.",
                    "Validate the source and update or remove unsupported evidence.",
                    relationship_id=relationship_id,
                    reducing=("missing_evidence",),
                    evidence=evidence,
                )
            )
        if not evidence:
            add(
                Detection(
                    "APL-014",
                    "Relationship evidence is incomplete",
                    "data_quality_warning",
                    "low",
                    confidence,
                    "The imported relationship has no supporting evidence.",
                    "Reviewers cannot independently validate this relationship from the dataset.",
                    "Attach authorized source evidence or mark the relationship uncertain.",
                    relationship_id=relationship_id,
                    reducing=("missing_evidence",),
                )
            )
    for node_id, data in graph.nodes(data=True):
        eligible_degree = sum(1 for _, _, edge in graph.out_edges(node_id, data=True) if edge["path_eligible"])
        if eligible_degree >= 5:
            add(
                Detection(
                    "APL-009",
                    "Principal has unusually many control relationships",
                    "excessive_delegation",
                    "medium",
                    "high",
                    f"{data['display_name']} has {eligible_degree} path-eligible outgoing relationships.",
                    "Broad control increases the number of assets potentially affected.",
                    "Review the principal against least-privilege requirements.",
                    node_id=node_id,
                    signals=("affected_asset", "affected_asset"),
                )
            )
        if data["type"] == "Group" and data["privileged"]:
            direct_members = sum(
                1 for _, _, edge in graph.in_edges(node_id, data=True) if edge["type"] in {"MemberOf", "NestedMemberOf"}
            )
            if direct_members >= 5:
                add(
                    Detection(
                        "APL-018",
                        "Privileged group has broad membership",
                        "excessive_group_membership",
                        "high",
                        "high",
                        f"{data['display_name']} has {direct_members} direct or nested members.",
                        "Large privileged groups increase exposure and complicate access review.",
                        "Remove unnecessary members and use role-specific administrative groups.",
                        node_id=node_id,
                        signals=("affected_asset", "affected_asset"),
                    )
                )
    # GPO rule.
    for source, gpo, data in graph.edges(data=True):
        if data["type"] not in {"CanEditGPO", "ControlsGPO"}:
            continue
        applies_to_important = any(
            edge["type"] in {"LinkedGPO", "AppliesGPO"} and graph.nodes[target]["high_value"]
            for _, target, edge in graph.out_edges(gpo, data=True)
        )
        if applies_to_important or graph.nodes[gpo]["type"] == "GroupPolicyObject":
            add(
                Detection(
                    "APL-005",
                    "Principal can edit a security-relevant GPO",
                    "group_policy_control",
                    "high",
                    data["confidence"],
                    "A principal can edit a GPO linked to directory assets.",
                    "GPO changes may affect managed systems and require scope validation.",
                    "Restrict GPO editing and review inherited delegation.",
                    node_id=source,
                    relationship_id=data["relationship_id"],
                    signals=("affected_asset",),
                    evidence=data.get("evidence"),
                )
            )
    # Host-admin plus privileged-session rule.
    for principal, computer, admin_edge in graph.edges(data=True):
        if admin_edge["type"] not in {"AdminTo", "LocalAdmin"}:
            continue
        for _, account, session_edge in graph.out_edges(computer, data=True):
            if session_edge["type"] == "HasSession" and graph.nodes[account]["privileged"]:
                add(
                    Detection(
                        "APL-003",
                        "Administrative access intersects a privileged session",
                        "privileged_session_exposure",
                        "high",
                        min(
                            (admin_edge["confidence"], session_edge["confidence"]),
                            key=lambda item: {"unknown": 0, "low": 1, "medium": 2, "high": 3}[item],
                        ),
                        "Administrative rights and an imported privileged session intersect on one computer.",
                        "This combination may create a possible route toward the privileged account.",
                        "Remove broad local administration and use dedicated administrative workstations.",
                        node_id=principal,
                        relationship_id=admin_edge["relationship_id"],
                        signals=("short_path", "independent_path"),
                        evidence={
                            "admin_relationship": admin_edge["relationship_id"],
                            "session_relationship": session_edge["relationship_id"],
                        },
                    )
                )
    # Shared high-value reachability rule.
    for target, data in graph.nodes(data=True):
        if not data["high_value"]:
            continue
        ancestors = [
            node
            for node in nx.ancestors(graph, target)
            if not graph.nodes[node]["privileged"] and graph.nodes[node]["enabled"]
        ]
        if len(ancestors) >= 2:
            add(
                Detection(
                    "APL-010",
                    "Multiple lower-privileged principals can reach a high-value asset",
                    "multiple_paths_to_high_value",
                    "high",
                    "high",
                    f"{len(ancestors)} lower-privileged nodes may reach {data['display_name']}.",
                    "Multiple possible routes reduce the benefit of fixing only one relationship.",
                    "Review and remove independent control paths in priority order.",
                    node_id=target,
                    signals=("independent_path", "independent_path", "affected_asset"),
                )
            )
    return findings
