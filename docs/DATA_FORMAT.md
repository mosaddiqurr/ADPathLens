# Import data format

JSON contains `metadata`, `nodes`, and `relationships`. CSV import requires root-level `nodes.csv`
and `relationships.csv`, supplied as a pair or as the only two files in a ZIP archive. IDs are
stable strings. Relationship endpoints reference node IDs.

Validation emits a digest and ordered messages. Errors block import; warnings must be
acknowledged. Import revalidates the same bytes and digest before an atomic transaction.

Defaults: 50 MiB compressed input, 100 archive entries, 200 MiB uncompressed data, JSON depth 20,
25,000 nodes, 100,000 relationships, 125,000 CSV rows, 256-character names, 4,000-character
descriptions, and 64 KiB metadata objects.

Non-UTF-8 input, traversal, absolute paths, symlinks, nested archives, unexpected entries,
executable signatures, duplicate IDs/entries, missing endpoints, prohibited loops, unsupported
types, invalid booleans, and compression limit violations are rejected.

See [IMPORTS.md](IMPORTS.md) for the validation/import transaction, provenance, warning/rejected
counters, and stable lifecycle identity methodology.
