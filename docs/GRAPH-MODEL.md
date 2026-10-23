# Graph model

Each persisted snapshot is rebuilt into its own NetworkX `MultiDiGraph`. Cache keys include the
snapshot ID and revision, and mutable graph state is never shared across snapshots or projects.
Parallel stored relationship IDs remain distinct.

The fixed node catalog is `User`, `Group`, `Computer`, `ServiceAccount`,
`ManagedServiceAccount`, `OrganizationalUnit`, `GroupPolicyObject`, `Domain`, `PrivilegedRole`,
`CertificateTemplate`, `CertificateAuthority`, `Application`, `FileShare`, and explicit `Unknown`.

The relationship catalog in `backend/app/graph/catalog.py` defines canonical direction, path
eligibility, base cost, explanation, and remediation. Imported direction cannot override fixed
semantics. `SameAccountAs` and `ConnectedTo` are bidirectional. Inactive relationships do not
traverse.

The API provides bounded graph summaries and render payloads, paginated node and relationship
lists, search, property/type/state/confidence filters, object and relationship detail, high-value
assets, and bounded one-to-three-hop neighborhood expansion. A large graph is never returned
without explicit server caps, and every response states when rendering was truncated.

Weighted cost is catalog cost multiplied by confidence (`high 1.0`, `medium 1.25`, `low 1.75`,
`unknown 2.0`) and by `1.15` for inherited evidence. Lower cost means stronger modeled defensive
concern, not easier exploitation or proof of compromise.
