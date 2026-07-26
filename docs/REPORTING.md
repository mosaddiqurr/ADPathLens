# Reporting

Reports are project-scoped records with source provenance, format, MIME type, size, SHA-256 hash,
status, and generated UUID storage name. Download filenames are allow-listed and generated.

- JSON: versioned canonical payload, source IDs, generation time, limits, and payload hash.
- CSV: findings only, UTF-8, with cells beginning `=`, `+`, `-`, `@`, tab, or carriage return
  prefixed by an apostrophe.
- HTML: Jinja2 autoescaping and printable defensive-use/limitations text.
- PDF: ReportLab consumes structured escaped text; imported HTML is never rendered.

Downloads resolve report ownership before checking the stored file, preventing cross-project
existence disclosure.
