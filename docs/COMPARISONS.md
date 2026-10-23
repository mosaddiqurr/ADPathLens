# Historical comparison methodology

Comparisons are persisted, project-scoped records between two distinct compatible snapshots.
Nodes match by stable external ID and relationships by stable relationship external ID. Snapshots
with insufficient identity overlap are rejected.

The deterministic diff stores added, removed, changed, and unchanged node/relationship counts;
added, removed, and unchanged path fingerprints; added, resolved, reopened, and severity-changed
finding fingerprints; total deterministic risk before/after; and remediation outcome flags.

Outcome flags distinguish removed/changed paths, resolved/reopened findings, no measurable change,
new risk, and unavailable verification. They summarize modeled evidence only and preserve the
original records.

Each category is paginated from the persisted result. The safe CSV export has a generated filename,
a fixed schema, a 10,000-row bound, ownership enforcement, and formula-injection neutralization.
The UI labels baseline/current snapshots, stored status, regression/reduction, unchanged counts,
finding changes, and remediation outcomes.
