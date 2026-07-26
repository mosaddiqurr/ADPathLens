# Requirements audit

| Area | Implementation evidence | Automated evidence |
|---|---|---|
| Authentication/CSRF/RBAC | Session, auth, user, workspace and authorization services | Backend auth/isolation/security tests; Playwright login/IDOR |
| Secure import/provenance | JSON/CSV/ZIP validators and atomic project routes | Import and archive attack tests |
| Graph persistence | Snapshot entities, catalog, cache and graph APIs | Graph tests; browser graph inspection |
| Bounded paths | Deterministic edge-aware algorithms and persistence | Path unit/API test; exact Mina browser assertion |
| Findings/review | Findings, evidence, notes and status history APIs | Service journey and browser note/status flow |
| Remediation | Typed actions, preview, outcome, derived snapshot | Service journey and browser retest |
| Comparisons | Stored diff metrics/items with ownership | Removed-edge assertion and browser comparison |
| Reports | JSON/CSV/HTML/PDF, hashes and safe downloads | Injection tests; all four backend formats; HTML browser download |
| Audit/admin | Capabilities, users, settings, rules, audit routes | Security test and administrator browser flow |
| Isolation | Workspace/project ownership resolution and 404 behavior | Cross-user backend and Playwright assertions |
| Accessibility | Labels, focus, responsive navigation and list alternatives | Axe serious/critical gate on desktop/mobile |
| Persistence | SQLAlchemy/Alembic plus report storage | Actual process restart acceptance |
| Performance | Runtime-generated bounded fixtures | 1k/5k/10k and medium workflow tests |
| Fictional data | NORTHBRIDGE deterministic generators | Browser journey uses only fictional names |

Not executed: Docker/PostgreSQL runtime because tools were absent; fresh external advisory refreshes
because dependency-inventory transmission was denied by policy. These limitations are explicit and
must not be interpreted as passing results.
