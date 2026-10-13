# Changelog

Release notes for AuthZDiff, maintained in
[mosaddiqurr/ADPathLens](https://github.com/mosaddiqurr/ADPathLens).

## [1.0.0] - 2026-10-13

First stable release of the stateless Before/After authorization comparison application.

### Comparison and evidence

- Compare JSON and CSV access snapshots, or two annotated HAR captures.
- Identify access gained, access lost, recognized role escalation, public expansion,
  wildcard grants, and removed denies.
- Explain each change with Before/After states, risk priorities, and redacted evidence.
- Keep uncertain HAR changes and unsupported role hierarchies as review items.
- Export PDF summaries and complete JSON/CSV evidence from the current inputs.

### Application and deployment

- Responsive React/TypeScript interface with Home, Compare, and About pages.
- Stateless FastAPI backend with bounded parsing and in-memory report generation.
- Windows and Linux launchers, reproducible dependency locks, and container configuration.
- Synthetic examples, screenshots, and guides for inputs, comparison, security, and deployment.
- Backend, frontend, browser, accessibility, and publication checks in GitHub Actions.
- Backend CI invokes tests through Python so application imports resolve in a clean checkout.
- Updated the transitive `source-map-js` dependency to 1.2.2 to address
  [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).

### Scope

Snapshots describe explicitly listed access. Effective policy evaluation, inheritance,
conditional policies, and live request replay are outside this release's scope. The application
has no built-in authentication or persistent history. See the
[known limitations](docs/KNOWN-LIMITATIONS.md) before interpreting or sharing results.

[1.0.0]: https://github.com/mosaddiqurr/ADPathLens/releases/tag/v1.0.0
