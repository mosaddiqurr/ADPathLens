# Findings

Deterministic candidates remain reviewer-controlled. AuthZDiff uses cautious language such as
“observed authorization difference” and never automatically assigns critical severity or claims
confirmed exploitability.

A stable SHA-256 fingerprint includes project, target, method, path, comparison category, and the
two role labels. Repeating the same comparison updates `last_seen_at`, recurrence count, current
run, confidence, and observed behavior instead of producing uncontrolled duplicates. A resolved
finding that recurs becomes reopened and receives a lifecycle-history event.

Lifecycle values include candidate/open, triaged, in progress, needs review, confirmed, false
positive, accepted risk, resolved, and reopened where applicable. Status changes record actor,
timestamp, and reviewer note. Findings also carry first/last seen, priority, tags, impact,
remediation, redaction summary, and limitations.

Evidence rows reference the exact run and observations used. They contain only a bounded sanitized
excerpt, hash, role, response metadata, redaction/truncation flags, and binary-hash-only indicator.
They do not change when a later run updates the finding.
