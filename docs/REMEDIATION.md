# Remediation methodology

Remediation in ADPathLens is planning and simulation only. It never executes an Active Directory
change.

A project-scoped plan selects an immutable source snapshot. Typed actions reference stored nodes,
relationships, and optionally findings. Actions record description, before/proposed values,
priority, assignee, due date, progress, expected outcome, actual outcome, verification state,
completion time, notes, and append-only status/progress history.

Meaningful tracking states include Proposed, Planned, In Progress, Blocked, Completed, Verified,
Rejected, Simulated, and Cancelled. Marking an action complete does not prove the issue resolved.
Verification states distinguish path removed/shortened/changed, finding resolved/reopened, no
measurable change, new risk, unavailable verification, and verified review.

Preview applies actions to counts without changing the source. Creating a derived snapshot clones
unchanged stable identity/provenance, applies only the proposed model changes, records parent/plan
provenance, and leaves the original snapshot logically unchanged. Analysts rerun rules/paths on the
derived snapshot and compare it with the source.
