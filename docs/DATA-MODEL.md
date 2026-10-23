# Data model

ADPathLens stores analytical state in a relational database through async SQLAlchemy and Alembic.
UUID strings identify records and timestamps are UTC. Portable string enums and JSON columns keep
the existing SQLite schema and useful migration compatibility.

The ownership chain is:

`workspace → project → dataset/snapshot → graph/analysis/finding/remediation/comparison/report`

Every resource endpoint resolves that chain before returning or changing data. Workspace
memberships carry administrator, analyst, or viewer access. Unauthorized object identifiers return
a non-disclosing not-found response.

Datasets record source type, authorization confirmation, importing actor, canonical hash,
validation summary, warning/rejected counters, provenance records, normalized counts, state, and
progress. Source upload bytes are not retained.

Snapshots are immutable imported or derived graph states. Nodes and relationships are unique by
snapshot and external ID. They retain source provenance, stable identity fingerprints, first/last
seen timestamps, state, confidence, sanitized metadata, and an isolated snapshot ID.

Analyses persist their request bounds and status. Paths preserve a stable edge-aware signature,
ordered evidence steps, confidence, cost, risk indicator, and explainable score components.

Findings preserve rule/version, stable recurrence fingerprint, first/last seen timestamps,
recurrence count, evidence associations, human status, notes, and append-only status history.
Remediation actions preserve assignment, due date, progress, expected/actual outcome, verification
state, completion time, and append-only history.

Comparisons store bounded deterministic node, relationship, path, finding, severity, reopening, and
remediation-outcome differences plus unchanged counts. Reports store source provenance, format,
status, content version, MIME type, size, SHA-256 hash, and a generated storage name.

Audit events are append-only through the public API and include actor, project where applicable,
action, entity, outcome, correlation ID, source IP, safe context, and timestamp.
