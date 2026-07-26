# Final validation

Validation host: Windows, Python 3.12.10, Node.js 22 baseline, 2026-07-26.

## Executed results

- `python -m ruff format --check app tests scripts --no-cache`: 66 files formatted.
- `python -m ruff check app tests scripts --no-cache`: passed.
- `python -m mypy app --no-incremental --cache-dir C:\tmp\adpathlens-mypy-final`: 54 source files,
  no issues.
- `python -m pytest -q -p no:cacheprovider --cov=app --cov-report=term-missing
  --cov-report=json:coverage.json --cov-fail-under=65`: 14 passed; final 66.93% total coverage.
- `python -m bandit -r app -q`: passed with no reported findings.
- Empty SQLite Alembic upgrade/check/downgrade/upgrade: passed; migrated database 626,688 bytes.
- `npm.cmd run lint`: passed with no warnings.
- `npm.cmd run test:coverage`: 3 files/4 tests passed; 46.13% statements, 46.93% branches,
  39.59% functions, 50.47% lines.
- `npm.cmd run build`: TypeScript and Vite passed; 1,678 modules transformed.
- Final `npm.cmd run test:e2e`: 2/2 passed in 30.4 seconds using one worker: desktop 18.2 seconds,
  Chromium mobile 2.7 seconds.
- Axe in the tested login/dashboard, graph, and finding-detail workflow reported zero serious or
  critical violations.
- `python scripts/runtime_acceptance.py`: project and snapshot persisted across an actual backend
  restart; 35 nodes, 56 relationships, 667,648-byte database; port 8011 free after teardown.
- Post-Playwright listener inspection: no listeners on 8011 or 5174.

## Performance

Measured deterministic graphs:

| Nodes | Edges | Build | Bounded path | Peak traced memory |
|---:|---:|---:|---:|---:|
| 1,000 | 2,999 | 0.2278 s | 0.0010 s | 3.18 MiB |
| 5,000 | 14,999 | 1.2368 s | 0.0009 s | 15.89 MiB |
| 10,000 | 29,999 | 2.6115 s | 0.0011 s | 31.78 MiB |

The real 500-node/1,501-edge medium demo imported transactionally in 0.8334 seconds and searched in
0.0171 seconds. Snapshot comparison took 0.0474 seconds and JSON report generation took 0.0288
seconds. These are local deterministic measurements, not production scale claims.

## Clean installation

The staged manifest was exported without Git metadata, `.env`, virtual environments, node modules,
build output, caches, databases, logs, or browser artifacts. In that copy:

- a new Python virtual environment installed `.[dev]`;
- `npm ci` installed and audited 340 packages with zero vulnerabilities;
- empty SQLite migration and Alembic drift check passed;
- clean Ruff, strict MyPy, and 14 backend tests passed;
- clean ESLint, 3-file/4-test frontend suite, and production build passed;
- clean startup/restart persistence passed and port 8011 closed.

## Dependency and container status

The isolated `npm ci` audit found zero vulnerabilities across 340 packages. `pip-audit --local` was
denied by the execution policy because it would disclose the dependency inventory to an external
advisory endpoint; no Python dependency-audit result is claimed. Bandit passed.

Docker and `psql` were not installed. Dockerfiles, Compose, health checks, volumes, and proxy
configuration were inspected, but Docker/PostgreSQL runtime behavior is not claimed.

Release commit, annotated tag, archive path/size/checksum, and final Git status are reported from
the actual packaging commands rather than predicted in this document.
