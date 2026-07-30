# Reporting

Project reports are available as JSON, CSV, HTML, and PDF. The generator reads only project-owned
targets and non-deleted findings. Reports contain scope, target-policy summaries, findings,
confidence, remediation, limitations, timestamps, and redaction language.

JSON is canonicalized for a content hash. CSV fields with spreadsheet formula prefixes are
neutralized. HTML templates autoescape untrusted text. PDF uses drawing primitives. Filenames are
generated from server-side UUIDs and paths are resolved beneath the configured private report
root. A canonical content hash and a separate final-file SHA-256 avoid self-referential hashing.

The download route rechecks project ownership, resolved storage root, completion status, file
existence, content type, and safe filename, then records an audit event. Reports never include raw
profile credentials, encrypted blobs, cookies, authorization headers, CSRF tokens, stack traces,
or local filesystem paths.
