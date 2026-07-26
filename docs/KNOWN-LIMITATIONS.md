# Known limitations

- No live AD/LDAP collection, credentials, exploitation, automatic remediation, or proof of
  compromise.
- SQLite is for local evaluation and tests, not shared production deployment.
- Analysis capacity and graph cache are process-local; horizontal coordination is future work.
- Reliable comparison needs stable external IDs and meaningful identity overlap.
- Automated accessibility checks cannot replace manual screen-reader and full keyboard review.
- Mobile uses accessible lists/cards for graph-heavy tasks; detailed Cytoscape manipulation is
  primarily desktop-oriented.
- Docker and PostgreSQL runtime integration were not executed on this host because neither Docker
  nor `psql` was installed.
- The external Python advisory refresh was not executed because the tool policy denied dependency
  inventory disclosure. The isolated npm installation did run its registry audit successfully.
- Frontend unit coverage is 46.13% statements/50.47% lines; the real browser journey carries much
  of the workflow coverage.
