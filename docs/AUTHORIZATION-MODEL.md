# Authorization model

AuthZDiff is one shared workspace with two roles:

- `administrator`: workspace oversight, user provisioning, settings, and global audit access.
- `analyst`: access only to projects whose `created_by` equals the analyst user ID.

There is no public self-registration. Initial setup creates the first administrator using an
environment setup token and authorized-use acknowledgement. Administrators provision analysts
with one-time passwords; analysts must change them before normal use.

Project authorization is evaluated on the server. Targets, profiles, collections, imported
requests, test cases, jobs, runs, observations, comparisons, findings, evidence, and reports all
inherit their project boundary. A resource ID from another analyst's project produces the same
404-style response as an unknown ID. Report files are resolved only after this ownership check and
must remain beneath the configured report root.

Administrators may inspect projects workspace-wide. This is intentional and audited. An
administrator does not bypass target authorization, allowlists, state-change confirmations,
budget, DNS policy, or response bounds.
