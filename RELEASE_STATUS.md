# Release status

Release candidate status: **locally qualified and packaged as `v1.0.0-rc1`**.

Every mandatory gate available on the 2026-07-30 Windows validation host passed. Exact command
evidence, counts, timings, and the clean-copy result are in `FINAL_VALIDATION.md`.

Release constraints:

- Docker, PostgreSQL-in-container, Semgrep, and Trivy were unavailable. Static Compose parsing and
  deployment-source inspection passed, but no runtime or scan pass is claimed.
- npm reports the documented React Router RSC-only advisory. AuthZDiff does not use RSC or server
  actions, and no patched `react-router-dom` release exists.
- The package remains a release candidate, not a production-readiness claim, until the unavailable
  container/PostgreSQL gates run successfully.

The release archive must be generated from the annotated tag's committed tracked files. Its
SHA-256 is distributed beside the archive rather than embedded in it.
