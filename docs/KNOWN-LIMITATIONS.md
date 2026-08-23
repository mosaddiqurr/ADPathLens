# Known limitations

- AuthZDiff is a single-workspace, single-node black-box HTTP tester. It is not an IAM/RBAC policy
  parser, group-graph analyzer, inherited-permission resolver, or semantic allow/deny diff engine.
- It compares one configured request under two controlled profiles. It does not discover, crawl,
  enumerate, exploit, or automate browser authentication.
- The database queue survives API restarts but is not a general distributed task platform.
- SQLite is the runtime-tested local/test backend. PostgreSQL support is configured but remains
  runtime-unverified for this release candidate.
- Dockerfiles and Compose topology are present and statically reviewed, but Docker runtime remains
  unverified for this release candidate.
- State-changing target requests cannot be rolled back. They require multiple confirmations and are
  never retried automatically.
- External cancellation is cooperative; an in-flight socket operation finishes or times out before
  cancellation finalizes.
- Response evidence is bounded and redacted before persistence. Truncation can make a comparison
  inconclusive. Operators remain responsible for database/report retention and access control.
- Project deletion is soft deletion. It hides the project from normal workflows but retains child
  rows, observations, finding evidence, audit history, and generated report files. No automatic
  purge or cryptographic deletion is provided.
- Reports use local node storage. External object storage and retention automation are out of scope.
- HAR support is preview only. No HAR entry is saved or executed through that endpoint.
- Statement and branch coverage thresholds are not configured.
- Playwright includes desktop/mobile workflows and axe scans, but it is not a declaration of WCAG
  compliance and does not currently include a keyboard-only navigation suite.
- Semgrep and Trivy are not required CI gates because they are not available in the validated local
  environment. Bandit is the configured Python static-security gate.
