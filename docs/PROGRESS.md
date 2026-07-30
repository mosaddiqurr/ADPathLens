# Progress

Last updated: 2026-07-30.

Implementation phases A through D are complete in source: backend workflows, external replay
worker, React workflows, deterministic demo, owned-process launchers, Compose assets, and
documentation are present. Focused backend, migration, demo, frontend lint and TypeScript checks
were used during implementation.

The consolidated release phase remains authoritative. Exact results are recorded in
`FINAL_VALIDATION.md` and `RELEASE_STATUS.md` only after commands run. A release commit and
`authzdiff-v1.0.0-rc1` tag must not be created while a locally available mandatory gate is
failing or unexecuted.

Current implementation highlights:

- Atomic queued-to-claimed worker transition and worker heartbeat metadata.
- Restart and stale-heartbeat reconciliation to interrupted state.
- Lifetime target request-budget reservation and per-target response-size policy.
- Profile ciphertext binding to project, target, profile, and field.
- Stable finding fingerprints, recurrence timestamps/count, and sanitized observation evidence.
- Real policy editing, profile rotation/deletion, cURL import, evidence, finding history,
  reporting, audit filtering, and guided demo UI.
- PowerShell and Unix runtime commands; PowerShell is the locally exercised launcher.

Known environmental status must be read from `RELEASE_STATUS.md`; it is not inferred here.
