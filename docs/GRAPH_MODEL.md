# Graph model

Nodes use the fixed v1 catalog: User, Group, Computer, ServiceAccount,
ManagedServiceAccount, OrganizationalUnit, GroupPolicyObject, Domain, PrivilegedRole,
CertificateTemplate, CertificateAuthority, Application, FileShare, and explicit Unknown.

Relationships follow the catalog in `backend/app/graph/catalog.py`. Catalog entries define
canonical direction, display meaning, base cost, path eligibility, and remediation guidance.
`SameAccountAs` and `ConnectedTo` are bidirectional. Parallel relationship IDs are preserved.
Inactive relationships never traverse.

Weighted cost is base cost multiplied by confidence (`high 1.0`, `medium 1.25`, `low 1.75`,
`unknown 2.0`) and by `1.15` for inherited evidence. Lower cost means stronger modeled defensive
concern, not easier exploitation.

Path signatures include ordered node and relationship IDs. Results always state that a possible
path is not evidence of exploitation or compromise.
