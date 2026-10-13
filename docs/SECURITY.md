# Security and privacy

Run locally for sensitive comparisons. The default servers bind to loopback.
A hosted instance processes uploads on that instance's server; this is not a browser-only app.

## Data boundaries

Inputs are parsed in memory and never stored by the API. The browser uses only React state.
Reports are generated in BytesIO and sent directly to the browser.
There is no database, upload directory, persistence identifier, analytics, or replay transport.
Downloaded exports are controlled by the user. Generated local artifacts are ignored and are not
part of publication; they are not accessed by the application.

No URL inside a HAR is contacted. Input names are sanitized for display and never interpreted
as filesystem paths. There is no upload extraction, shell execution, or target credential storage.

## Bounds and errors

- 5 MiB per input; 12 MiB actual streamed request-body limit before JSON decoding.
- 2,000 snapshot records or 500 HAR entries; 256 KiB capture bodies; 8,000-byte excerpts.
- Nesting and structural bounds; duplicate JSON keys, non-finite numbers, malformed Unicode,
  ambiguous tuples, invalid capture entries, and traversal paths are rejected safely.
- Two computations per process. Excess work returns 429; deployment concurrency limits are separate.
- Explicit host/origin allowlists, JSON-only POST endpoints, no cookie credentials, and no-store responses.
- Errors omit raw exceptions, input values, tracebacks, database IDs, and correlation IDs.
  API logs include only unexpected exception types, without uploaded data.

## Evidence and exports

Preserved normalization removes credential headers, cookie headers, secret JSON fields,
email/phone/address fields, token-like strings, URL query/fragment credentials, and recognized
secret assignments. HTML bodies are reduced to text and never rendered as HTML.
Sensitive JSON keys match common camelCase, underscore, and hyphen variants. Short labeled
credentials and Cookie headers in response text are redacted as well as token-like values.
Redaction is best effort and does not guarantee removal of all private/business data.
Request headers, cookies, raw queries, and request bodies never enter exported evidence.

React escapes displayed labels/evidence; ReportLab paragraphs escape markup.
CSV neutralizes formula prefixes even after leading whitespace.
Reports recompute from exact inputs; a client cannot submit a fabricated result object.

The nginx config disables request/response spooling for the comparison proxy and sets a restrictive
CSP and common security headers. No report/upload disk volume is configured.
Memory-only processing is not secure deletion of process memory or OS swap.

## Publication checks

scripts/verify-publication.py checks present tracked/non-ignored files for forbidden data paths,
runtime/database archives, and recognizable secret patterns. It also checks reachable historical
paths and blobs; CI fetches the full history for this check. Detection is best effort and does
not replace a manual review. Every committed example is synthetic.

The test-tool vulnerability in the older Vitest was addressed by pinning the
[patched version](https://github.com/advisories/GHSA-82fw-gwwq-j7x9).
The frontend lock file also uses `source-map-js` 1.2.2, addressing the indexed source-map
[denial-of-service advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).
Dependency audits are part of local checks and CI, not a guarantee of security against unknown issues.

The app intentionally has no account/authentication layer. Keep it on loopback or an operator-controlled
network. If exposed, configure HTTPS, trusted hosts/origins, upstream access controls, and resource limits.
