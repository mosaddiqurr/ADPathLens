# AuthZDiff final requirements audit

Last updated: 2026-07-30.

| Area | Source implementation | Release validation |
|---|---|---|
| Authentication, opaque sessions, CSRF, rate limiting | Implemented | Passed unit/integration/browser gates |
| Analyst ownership and administrator oversight | Implemented server-side | Passed cross-user 404 and administrator browser gates |
| Target lifecycle, exact policy, DNS, pinned transport | Implemented | Passed policy/transport tests and loopback lab journey |
| Lifetime request budget and response limits | Implemented atomically | Passed deterministic exhaustion/bounds tests |
| AES-GCM write-only profiles and binding | Implemented | Passed encryption, masking, and API exposure tests |
| Manual/raw/cURL/HAR imports | Implemented | Passed parser tests and safe/rejected browser imports |
| External worker, atomic claim, heartbeat, recovery | Implemented | Passed atomic/recovery tests, restart proof, and live worker replay |
| Cancellation and read-only retry | Implemented | Passed live cancellation and deterministic retry/no-retry tests |
| Bounded observations and binary hash-only capture | Implemented | Passed response and persistence tests |
| Deterministic comparison engine | Implemented/versioned | Passed vertical/horizontal/tenant/field/method/drift fixtures |
| Stable findings, recurrence, evidence, lifecycle | Implemented | Passed persistence tests and live evidence/lifecycle journey |
| JSON/CSV/HTML/PDF reports and owned downloads | Implemented | Passed all-format content/filename checks, ownership denial, and secret tests |
| Sanitized audit context and filters | Implemented | Passed audit tests and browser/admin journey |
| Real React workflows and guided demo | Implemented | Passed desktop/mobile/axe acceptance |
| Owned local orchestration and Compose topology | Implemented | Local launcher passed; Docker unavailable and explicitly unclaimed |
| Documentation and packaging rules | Implemented | Evidence and release documents reconciled |

The locally executable requirements are complete. Container/PostgreSQL and external scanner
validation remain environment-qualified constraints, as recorded in `FINAL_VALIDATION.md`.
