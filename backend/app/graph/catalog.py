from dataclasses import asdict, dataclass

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


def serialize_catalog() -> dict[str, dict[str, object]]:
    return {key: asdict(value) for key, value in RELATIONSHIP_CATALOG.items()}
