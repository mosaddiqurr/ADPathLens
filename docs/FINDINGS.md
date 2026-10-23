# Findings methodology

Versioned deterministic rules and analyst-created path evidence produce project-scoped findings.
Automated results begin as Draft and require a human decision.

Each finding records category, severity, confidence, score, priority, rationale, impact, evidence,
affected node/relationship/path associations, remediation guidance, validation steps, limitations,
rule/version, stable fingerprint, first/last seen, recurrence count, reviewer, and timestamps.

Rule findings derive their stable fingerprint from rule ID plus stable node/relationship identity.
A repeated observation in a later snapshot retains the first-seen timestamp and increments
recurrence. Historical records are not silently rewritten.

Supported review states include Draft, Open, Confirmed, Acknowledged, Mitigated, Accepted Risk,
False Positive, Planned Remediation, Resolved, Retest Required, and Closed. Every status transition
adds append-only history. Notes are stored as plain text, project-scoped, author/timestamped, and
rendered without unsafe HTML.

Severity and confidence lead the UI; numeric scores are secondary. A finding derived from imported
relationships requires source validation and does not establish exploitation, intent, or
compromise.
