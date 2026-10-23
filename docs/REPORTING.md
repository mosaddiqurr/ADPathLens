# Reporting

Results exports PDF or JSON without leaving the analysis screen. The request includes the selected snapshot and analysis ID. The API verifies both belong together and the analysis is complete; it cannot silently substitute a newer query. Older callers that omit an analysis ID retain the latest-completed-analysis behavior.

PDF prioritizes the summary, five highest-scoring paths, their affected objects/severity/confidence/relationship evidence, five shared-relationship fixes, and five findings. It includes explicit partial-result and abbreviation notices, methodology, human-review requirements, and page numbers. Evidence strings longer than 900 characters are shortened with a notice. JSON contains the complete returned paths, evidence, source IDs, analysis parameters, truncation flag, findings, and canonical payload hash. Complete returned records still reflect the bounded analysis scope.

HTML and CSV remain supported by the backend for compatibility. CSV is a findings export with formula neutralization; HTML uses Jinja autoescaping. PDF uses ReportLab structured escaped text and never renders imported HTML.

Report records store project scope, provenance, MIME type, size, SHA-256 hash, generation status, and UUID storage names. Download names are generated and allowlisted. Ownership is resolved before file existence is checked. Successful downloads create scoped audit events with correlation ID, format, and size, excluding internal storage paths.

Reports interpret stored evidence at generation time; their hashes provide integrity bookkeeping, not cryptographic proof of directory state. See [ATTACK-PATHS.md](ATTACK-PATHS.md) for scoring and scope.
