from dataclasses import asdict, dataclass, replace

NODE_TYPES = {
    "User",
    "Group",
    "Computer",
    "ServiceAccount",
    "ManagedServiceAccount",
    "OrganizationalUnit",
    "GroupPolicyObject",
    "Domain",
    "PrivilegedRole",
    "CertificateTemplate",
    "CertificateAuthority",
    "Application",
    "FileShare",
    "Unknown",
}


@dataclass(frozen=True)
class RelationshipDefinition:
    name: str
    category: str
    weight: float
    path_eligible: bool
    explanation: str
    remediation: str
    direction: str = "forward"


def _definition(
    name: str,
    category: str,
    weight: float,
    path_eligible: bool = True,
    direction: str = "forward",
) -> RelationshipDefinition:
    readable = "".join(f" {character}" if character.isupper() else character for character in name).strip()
    return RelationshipDefinition(
        name=readable,
        category=category,
        weight=weight,
        path_eligible=path_eligible,
        explanation=(
            "{source} has the security-relevant relationship "
            f"'{readable}' to {{target}}. This may contribute to a possible control path."
        ),
        remediation=(
            f"Review whether {readable} is required, remove excessive access, and validate the imported evidence."
        ),
        direction=direction,
    )


RELATIONSHIP_CATALOG: dict[str, RelationshipDefinition] = {}

for relationship in (
    "GenericAll",
    "WriteDACL",
    "WriteOwner",
    "ResetPassword",
    "ForceChangePassword",
    "AddMember",
    "AdminTo",
    "LocalAdmin",
    "HasSession",
    "ContainsSession",
    "Owns",
    "OwnsObject",
    "AllExtendedRights",
):
    RELATIONSHIP_CATALOG[relationship] = _definition(relationship, "direct_control", 1)

for relationship in (
    "CanEditGPO",
    "ControlsGPO",
    "GenericWrite",
    "WriteSensitiveProperty",
    "ConstrainedDelegation",
    "UnconstrainedDelegation",
    "ResourceBasedConstrainedDelegation",
    "ServiceRunsAs",
    "DelegatedTo",
    "AllowedToDelegate",
    "ControlsCertificateTemplate",
):
    RELATIONSHIP_CATALOG[relationship] = _definition(relationship, "delegated_control", 2)

for relationship in (
    "CanRDP",
    "CanRemoteManage",
    "CanPSRemote",
    "MemberOf",
    "NestedMemberOf",
    "HasRole",
    "LinkedGPO",
    "AppliesGPO",
    "LinksTo",
):
    RELATIONSHIP_CATALOG[relationship] = _definition(relationship, "access", 3)

RELATIONSHIP_CATALOG["SameAccountAs"] = _definition("SameAccountAs", "identity", 3, direction="bidirectional")
RELATIONSHIP_CATALOG["ReadSensitiveProperty"] = _definition("ReadSensitiveProperty", "permission", 4)
RELATIONSHIP_CATALOG["Manages"] = _definition("Manages", "infrastructure", 4)

for relationship in ("Enroll", "AutoEnroll", "PublishedTemplate", "TrustedBy"):
    RELATIONSHIP_CATALOG[relationship] = _definition(relationship, "certificate_services", 4, path_eligible=False)

for relationship in ("Hosts", "Trusts", "Contains"):
    RELATIONSHIP_CATALOG[relationship] = _definition(relationship, "infrastructure", 5, path_eligible=False)
RELATIONSHIP_CATALOG["ConnectedTo"] = _definition(
    "ConnectedTo",
    "infrastructure",
    5,
    path_eligible=False,
    direction="bidirectional",
)
RELATIONSHIP_CATALOG["CustomRelationship"] = _definition("CustomRelationship", "custom", 5, path_eligible=False)

_guidance = {
    "MemberOf": (
        "{source} is a member of {target} and may inherit the group's granted access.",
        "Review membership and delegated rights; remove unnecessary members and retest inherited access.",
    ),
    "ResetPassword": (
        "{source} can reset {target}'s password, potentially enabling account takeover if other controls permit it.",
        "Remove unnecessary password-reset delegation, restrict who can reset privileged accounts, and verify the ACL.",
    ),
    "AdminTo": (
        "{source} has administrative access to {target}, which may allow control of that computer.",
        "Restrict local admin access to approved operators and separate privileged administration from routine use.",
    ),
    "LocalAdmin": (
        "{source} has local administrator rights on {target}, creating a possible route to host control.",
        "Remove excessive local administrator membership and verify effective rights on the computer.",
    ),
    "HasSession": (
        "{target} has a session on {source}. Host control may expose that identity if credential protections fail.",
        "Keep privileged sessions off lower-trust hosts, end stale sessions, and validate credential protections.",
    ),
    "GenericAll": (
        "{source} has full control over {target}; the effect depends on the target object and effective permissions.",
        "Review the object's ACL and remove unnecessary full-control grants, then verify effective permissions.",
    ),
    "WriteDACL": (
        "{source} can change permissions on {target}, potentially granting further control.",
        "Restrict permission-management rights to approved administrators and inspect inherited ACL entries.",
    ),
    "CanEditGPO": (
        "{source} can modify {target}. Linked policy scope determines which computers could be affected.",
        "Restrict GPO edit permissions and verify links, security filtering, and the resulting policy scope.",
    ),
}
for _kind, (_explanation, _remediation) in _guidance.items():
    RELATIONSHIP_CATALOG[_kind] = replace(
        RELATIONSHIP_CATALOG[_kind], explanation=_explanation, remediation=_remediation
    )


def serialize_catalog() -> dict[str, dict[str, object]]:
    return {key: asdict(value) for key, value in RELATIONSHIP_CATALOG.items()}
