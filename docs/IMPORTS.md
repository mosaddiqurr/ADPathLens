# Import methodology

Supported sources are the normalized ADPathLens JSON schema, a `nodes.csv` and
`relationships.csv` pair, a ZIP containing only those two root-level files, and built-in fictional
NORTHBRIDGE fixtures. No live LDAP, BloodHound collector, credential, or arbitrary archive format
is supported.

The browser first validates selected bytes. Validation returns a canonical digest, normalized
counts, and ordered messages with stable codes and locations. Errors block import; every warning
code must be explicitly acknowledged. Import revalidates the submitted bytes and digest to prevent
a validation/import time-of-check difference.

The validator enforces upload, row, node, relationship, metadata, depth, archive-entry,
uncompressed-size, and compression-ratio limits. It rejects unsupported types, invalid booleans,
duplicates, missing endpoints, prohibited loops, non-UTF-8 data, executables, symlinks, nested
archives, traversal/absolute paths, unexpected ZIP entries, and malformed structures.

Persistence is one transaction: dataset, provenance, messages, snapshot, nodes, and relationships
either commit together or roll back. Stable fingerprints use normalized external identities and
relationship endpoints/types. First-seen timestamps propagate across project snapshots with the
same external ID; last-seen is the observation time for the new snapshot. Source bytes are
discarded after parsing.

The UI reports progress, normalized record counts, warnings, rejected records, cancellation state,
and errors. Completed imports cannot be cancelled; deleting one removes its project-owned derived
analytical records through declared cascades.
