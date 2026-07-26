# Threat model

Protected assets are authenticated sessions, project boundaries, normalized directory data,
analysis evidence, findings, reports, settings, and audit integrity.

Primary threats are credential/session theft, CSRF, IDOR, role bypass, malicious uploads, archive
exhaustion, stored XSS, report/CSV injection, cross-snapshot graph leakage, path explosion,
tampered provenance, secret leakage, and misleading analytical conclusions.

Controls include opaque revocable sessions, CSRF, server-side ownership, atomic imports,
archive/content budgets, escaping, formula neutralization, snapshot/revision cache keys, bounded
algorithms, immutable derived snapshots, hashes, audit records, and mandatory human review.

Residual risks include in-process analysis coordination in a single backend process, dependence on
stable external IDs for comparisons, SQLite's unsuitability for shared production use, and the fact
that modeled relationships may be incomplete or inaccurate.
