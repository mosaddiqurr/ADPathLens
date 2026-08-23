# Application authorization model

AuthZDiff has one shared workspace and two application roles:

- `administrator`: workspace oversight, API user provisioning, settings, and global audit access;
- `analyst`: access only to projects whose `created_by` matches that analyst.

This application role model is not an imported IAM/RBAC policy model and is not what the comparison
engine semantically diffs.

There is no public self-registration. Initial setup creates the first administrator using an
environment setup token and authorized-use acknowledgement. Administrators provision users through
the authenticated API with temporary passwords. After login, a provisioned user is restricted to
the mandatory password-change page and logout. The backend validates the temporary password,
enforces the normal password policy, rotates the session/CSRF material, invalidates other sessions,
and clears the flag only after success.

Project authorization is enforced server-side. Targets, profiles, collections, requests, test cases,
jobs, runs, observations, differences, findings, evidence, and reports inherit the project boundary.
A cross-owner identifier produces the same 404-style response as an unknown identifier. Report files
are served only after ownership and configured-root checks.

Administrators may inspect projects workspace-wide. This is intentional and audited, but does not
bypass target authorization, allowlists, state-change confirmations, request budgets, canonical path
checks, DNS/network policy, or response bounds.
