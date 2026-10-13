# Comparison logic

## Explicit snapshots

Match the exact (principal, resource, action) tuple. Labels are case-sensitive except public
aliases and recognized role names. Reject duplicate tuples instead of resolving conflicting rules.

- New allow or deny -> allow: gained.
- Allow -> absent/deny: lost.
- Recognized role increase/decrease on an existing allow: gained/lost.
- Removed deny with no new allow: review, medium priority; never an inferred gain.
- Other role changes: review. A new admin label remains high priority even with an unknown prior hierarchy.
- Identical effect/role: unchanged. Sensitivity-only metadata changes are not authorization changes.

Recognized role tiers are Viewer/Reader/Read-only < Developer/Editor < Admin/Administrator/Owner.
This is a documented label convention, not universal application-policy semantics.

Public gain is high, or critical with sensitive/admin/wildcard context. New admin or wildcard
grants are high. Explicit sensitive-resource gains and non-admin role increases are medium.
Replacing a deny with an allow is high. Ordinary gains/losses are Info.
Sensitivity on either side is retained for risk assessment. Wildcards are detected literally;
their effective coverage is not evaluated.
New grants of actions named Admin, Administrator, Manage, or FullAccess are high priority.
The final component of a dotted, colon, or slash-separated action name is checked exactly;
unrelated names such as `not-admin` do not match. An already allowed management action does
not become new admin access merely because its role label moves up a non-admin tier.

## Captures

Match principal + exact origin/encoded path + method + non-credential query/header context +
exact request-body/form context, including content type. Paths are validated for traversal and
invalid encodings, but distinct encoded targets are not collapsed into the same resource.
Queries, headers, and request bodies contribute to internal matching but never appear in reports.
Credentials, cookies, and request headers are excluded from retained evidence.

Keep the existing safe-header, redirect, JSON structure/value, and redacted text difference logic.
The internal authzdiff-rules/1.1 API remains database-independent and tested.
The temporal adapter uses it for evidence, not to mistake higher/lower profiles for Before/After.

A confirmed observed gain/loss requires the same annotated principal and request context,
explicit allowed/denied annotations, corroboration from the response, and complete evidence.
A success containing denial markers cannot corroborate allowed. Failed/truncated responses,
missing body evidence, status-only changes, and unmatched coverage remain review items.

A record present in only one capture is not proof of gained/lost access.
Repeated matching requests inside a capture are rejected instead of arbitrarily pairing them.
No timestamps, response latency, or dropped credential values are used to infer access.
