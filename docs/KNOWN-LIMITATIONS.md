# Known limitations

- ADPathLens consumes supplied data. It does not collect from AD/LDAP, execute exploits, prove compromise, or apply remediation.
- Collector exports require conversion to the documented ADPathLens schema; native BloodHound formats are not accepted directly.
- Default reverse analysis returns one shortest route per eligible starting object, with at most 25 paths and 12 relationships per path in the UI. Alternative routes require a selected-source analysis. Limits are labelled as partial results when reached.
- Priority scores are deterministic review indicators, not CVSS or likelihood estimates. Confidence follows the supplied evidence. Recommendations require effective-permission and operational review.
- Local mode is restricted to development on loopback and uses SQLite. A shared deployment retains authentication and requires secure production configuration and persistent SQLite/report storage.
- Graph cache and analysis capacity are process-local. No distributed worker or cross-process queue is included.
- The graph is easiest to inspect on desktop. Mobile offers zoom/pan/fit and the ordered relationship/evidence cards; a long path may require panning.
- PDF is a concise selected-analysis narrative. JSON retains all returned records. Neither implies exhaustive coverage of an AD environment.
- Existing advanced findings/simulation/comparison/administration APIs remain for compatibility and retain backend tests. They have no standalone screens in the four-page product UI.
- Automated accessibility scans and keyboard checks do not constitute a complete screen-reader audit. Current browser acceptance uses Chromium.
- SQLite supports a single backend instance on a local persistent disk. Public hosting certificates/ingress, backup recovery, and other browsers need deployment-specific validation. See [TESTING.md](TESTING.md) for reproducible checks and current verification limits.
- Cross-site provider domains may have third-party cookies blocked by browsers. Prefer HTTPS app/API subdomains under one registrable domain with SameSite=Lax.
