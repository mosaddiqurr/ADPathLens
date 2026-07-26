# Release checklist

- [x] Ruff and formatting
- [x] Strict MyPy
- [x] Backend tests and coverage threshold
- [x] Bandit
- [x] Empty SQLite Alembic upgrade/check/downgrade/upgrade
- [x] Frontend ESLint, unit coverage, TypeScript, and Vite build
- [x] Desktop and Chromium mobile Playwright journeys
- [x] Zero serious/critical axe violations in tested pages
- [x] Runtime restart persistence and closed acceptance listeners
- [x] Deterministic performance measurements
- [ ] Fresh external Python advisory lookup (blocked by execution policy)
- [x] Clean `npm ci` audit: 340 packages, zero vulnerabilities
- [ ] Docker/PostgreSQL runtime (tools unavailable)
- [x] Clean staged-source installation
- [ ] Release commit, tag, archive, and checksum

The commit and tag are created only after the remaining staged-manifest inspection.
