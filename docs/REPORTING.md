# Reporting and retention

Project reports are generated as JSON, CSV, HTML, or PDF from project-owned targets and non-deleted
findings. They include target-policy summaries, finding classifications, confidence, remediation,
limitations, timestamps, and redaction statements. Raw observation bodies and profile credentials
are not report inputs.

JSON receives a canonical content hash. CSV formula-leading values are neutralized. HTML and PDF
escape untrusted text. Server-generated UUID filenames are resolved beneath the configured private
report root. The download route rechecks project ownership, root containment, completion, file
existence, content type, and filename, then records an audit event.

Response redaction happens before observations and finding evidence are stored, not only while a
report is displayed. Reports therefore inherit already-sanitized finding content.

Report files are retained on local storage. Soft project deletion hides a project from normal API/UI
workflows but does not remove child database rows, observations, evidence, audit history, or report
files. Operators must define and execute their own approved database/report retention and purge
procedure; AuthZDiff does not claim automatic or cryptographic deletion.
