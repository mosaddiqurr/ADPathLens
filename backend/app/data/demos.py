from __future__ import annotations

from typing import Any

DOMAIN = "NORTHBRIDGE.LOCAL"


def _node(
    node_id: str,
    node_type: str,
    name: str,
    *,
    privileged: bool = False,
    high_value: bool = False,
    enabled: bool = True,
    description: str = "",
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "name": name,
        "display_name": name,
        "domain": DOMAIN,
        "enabled": enabled,
        "privileged": privileged,
        "high_value": high_value,
        "description": description,
        "metadata": {"fictional": True},
    }


def _relationship(
    relationship_id: str,
    source: str,
    target: str,
    relationship_type: str,
    confidence: str = "high",
) -> dict[str, Any]:
    return {
        "id": relationship_id,
        "source": source,
        "target": target,
        "type": relationship_type,
        "confidence": confidence,
        "evidence": {"source": "Synthetic ADPathLens lab", "fictional": True},
    }


def small_demo() -> dict[str, Any]:
    nodes = [
        _node("user-alex", "User", "Alex Carter"),
        _node("user-mina", "User", "Mina Rahman"),
        _node("user-jordan", "User", "Jordan Lee"),
        _node("user-priya", "User", "Priya Nair", privileged=True),
        _node("user-omar", "User", "Omar Hassan", privileged=True, high_value=True),
        _node("svc-backup", "ServiceAccount", "svc_backup", privileged=True),
        _node("svc-web", "ServiceAccount", "svc_web"),
        _node("user-old-admin", "User", "old_admin", privileged=True, enabled=False),
        _node("group-employees", "Group", "Employees"),
        _node("group-helpdesk", "Group", "Helpdesk"),
        _node("group-it", "Group", "IT Support"),
        _node("group-server-ops", "Group", "Server Operators", privileged=True),
        _node("group-workstation-admins", "Group", "Workstation Admins"),
        _node("group-backup-ops", "Group", "Backup Operators", privileged=True),
        _node(
            "group-domain-admins",
            "Group",
            "Domain Admins",
            privileged=True,
            high_value=True,
        ),
        _node(
            "group-enterprise-admins",
            "Group",
            "Enterprise Admins",
            privileged=True,
            high_value=True,
        ),
        _node("computer-ws101", "Computer", "NB-WS-101"),
        _node("computer-ws102", "Computer", "NB-WS-102"),
        _node("computer-helpdesk", "Computer", "NB-HELPDESK-01"),
        _node("computer-file", "Computer", "NB-FILE-01", high_value=True),
        _node("computer-web", "Computer", "NB-WEB-01", high_value=True),
        _node("computer-dc1", "Computer", "NB-DC-01", privileged=True, high_value=True),
        _node("computer-dc2", "Computer", "NB-DC-02", privileged=True, high_value=True),
        _node("ou-employees", "OrganizationalUnit", "Employees OU"),
        _node("ou-workstations", "OrganizationalUnit", "Workstations OU"),
        _node("ou-servers", "OrganizationalUnit", "Servers OU"),
        _node("ou-dcs", "OrganizationalUnit", "Domain Controllers OU", high_value=True),
        _node("gpo-baseline", "GroupPolicyObject", "Workstation Baseline"),
        _node("gpo-helpdesk", "GroupPolicyObject", "Helpdesk Delegation"),
        _node("gpo-server", "GroupPolicyObject", "Server Administration"),
        _node("gpo-dc", "GroupPolicyObject", "Domain Controller Security", high_value=True),
        _node("domain-northbridge", "Domain", DOMAIN, privileged=True, high_value=True),
        _node("ca-nb", "CertificateAuthority", "NB-CA-01", high_value=True),
        _node("template-web", "CertificateTemplate", "Northbridge Web Server"),
        _node("share-finance", "FileShare", "Finance Restricted Share", high_value=True),
    ]
    relationships = [
        _relationship("rel-mina-helpdesk", "user-mina", "group-helpdesk", "MemberOf"),
        _relationship("rel-helpdesk-priya", "group-helpdesk", "user-priya", "ResetPassword"),
        _relationship("rel-priya-serverops", "user-priya", "group-server-ops", "MemberOf"),
        _relationship("rel-serverops-web", "group-server-ops", "computer-web", "AdminTo"),
        _relationship("rel-web-omar", "computer-web", "user-omar", "HasSession"),
        _relationship("rel-omar-da", "user-omar", "group-domain-admins", "MemberOf"),
        _relationship("rel-alex-employees", "user-alex", "group-employees", "MemberOf"),
        _relationship("rel-jordan-it", "user-jordan", "group-it", "MemberOf"),
        _relationship("rel-it-gpo", "group-it", "gpo-helpdesk", "CanEditGPO"),
        _relationship("rel-gpo-workstations", "gpo-helpdesk", "ou-workstations", "LinkedGPO"),
        _relationship("rel-gpo-ws101", "gpo-helpdesk", "computer-ws101", "AppliesGPO"),
        _relationship("rel-backup-backupops", "svc-backup", "group-backup-ops", "MemberOf"),
        _relationship("rel-backupops-file", "group-backup-ops", "computer-file", "AdminTo"),
        _relationship("rel-file-omar", "computer-file", "user-omar", "HasSession"),
        _relationship("rel-oldadmin-da", "user-old-admin", "group-domain-admins", "MemberOf"),
        _relationship("rel-helpdesk-helpdeskpc", "group-helpdesk", "computer-helpdesk", "LocalAdmin"),
        _relationship("rel-helpdeskpc-omar", "computer-helpdesk", "user-omar", "HasSession"),
        _relationship("rel-da-dc1", "group-domain-admins", "computer-dc1", "AdminTo"),
        _relationship("rel-da-dc2", "group-domain-admins", "computer-dc2", "AdminTo"),
        _relationship("rel-ea-domain", "group-enterprise-admins", "domain-northbridge", "GenericAll"),
        _relationship("rel-da-domain", "group-domain-admins", "domain-northbridge", "GenericAll"),
        _relationship("rel-dc1-domain", "computer-dc1", "domain-northbridge", "Contains"),
        _relationship("rel-dc2-domain", "computer-dc2", "domain-northbridge", "Contains"),
        _relationship("rel-domain-ouemployees", "domain-northbridge", "ou-employees", "Contains"),
        _relationship("rel-domain-ouworkstations", "domain-northbridge", "ou-workstations", "Contains"),
        _relationship("rel-domain-ouservers", "domain-northbridge", "ou-servers", "Contains"),
        _relationship("rel-domain-oudcs", "domain-northbridge", "ou-dcs", "Contains"),
        _relationship("rel-servergpo-servers", "gpo-server", "ou-servers", "LinkedGPO"),
        _relationship("rel-dcgpo-dcs", "gpo-dc", "ou-dcs", "LinkedGPO"),
        _relationship("rel-baseline-workstations", "gpo-baseline", "ou-workstations", "LinkedGPO"),
        _relationship("rel-web-svcweb", "computer-web", "svc-web", "ServiceRunsAs"),
        _relationship("rel-priya-web", "user-priya", "computer-web", "CanRDP"),
        _relationship("rel-workadmins-ws101", "group-workstation-admins", "computer-ws101", "AdminTo"),
        _relationship("rel-workadmins-ws102", "group-workstation-admins", "computer-ws102", "AdminTo"),
        _relationship("rel-it-workadmins", "group-it", "group-workstation-admins", "NestedMemberOf"),
        _relationship("rel-template-ca", "ca-nb", "template-web", "PublishedTemplate"),
        _relationship("rel-it-template", "group-it", "template-web", "Enroll"),
        _relationship("rel-domain-ca", "domain-northbridge", "ca-nb", "TrustedBy"),
        _relationship("rel-file-share", "computer-file", "share-finance", "Hosts"),
        _relationship("rel-employees-alex", "group-employees", "user-alex", "Manages", "low"),
    ]
    context_targets = [
        "group-employees",
        "group-it",
        "group-helpdesk",
        "group-workstation-admins",
        "computer-file",
        "computer-web",
        "computer-dc1",
        "computer-dc2",
        "ou-employees",
        "ou-workstations",
        "ou-servers",
        "ou-dcs",
        "gpo-baseline",
        "gpo-server",
        "share-finance",
    ]
    for index, target in enumerate(context_targets, start=1):
        source = f"computer-ws{101 if index % 2 else 102}"
        relationships.append(_relationship(f"rel-context-{index:02}", source, target, "ConnectedTo", "medium"))
    relationships.append(_relationship("rel-ws101-omar", "computer-ws101", "user-omar", "HasSession"))
    return {
        "metadata": {
            "name": "Northbridge Small Lab",
            "description": "Entirely fictional synthetic Active Directory lab.",
            "version": "1.0",
            "fictional": True,
        },
        "nodes": nodes,
        "relationships": relationships,
    }


def medium_demo() -> dict[str, Any]:
    demo = small_demo()
    nodes = list(demo["nodes"])
    relationships = list(demo["relationships"])
    for index in range(465):
        node_id = f"generated-user-{index:04}"
        nodes.append(_node(node_id, "User", f"Synthetic User {index:04}"))
        relationships.append(
            _relationship(
                f"generated-membership-{index:04}",
                node_id,
                "group-employees",
                "MemberOf",
            )
        )
    for index in range(980):
        source = f"generated-user-{index % 465:04}"
        target_index = (index * 7 + index // 465 + 1) % 465
        target = f"generated-user-{target_index:04}"
        relationship_type = ["CanRDP", "ConnectedTo", "SameAccountAs"][index % 3]
        relationships.append(
            _relationship(
                f"generated-context-{index:04}",
                source,
                target,
                relationship_type,
                "medium",
            )
        )
    demo["metadata"] = {
        "name": "Northbridge Medium Lab",
        "description": "Entirely fictional medium synthetic dataset.",
        "version": "1.0",
        "fictional": True,
    }
    demo["nodes"] = nodes
    demo["relationships"] = relationships
    return demo


def get_demo(name: str) -> dict[str, Any]:
    if name == "medium":
        return medium_demo()
    demo = small_demo()
    if name == "after":
        removed = {
            "rel-helpdesk-priya",
            "rel-helpdeskpc-omar",
            "rel-it-gpo",
            "rel-oldadmin-da",
            "rel-backupops-file",
        }
        demo["relationships"] = [
            relationship for relationship in demo["relationships"] if relationship["id"] not in removed
        ]
        demo["metadata"]["name"] = "Northbridge After Remediation"
    elif name == "before":
        demo["metadata"]["name"] = "Northbridge Before Remediation"
    return demo
