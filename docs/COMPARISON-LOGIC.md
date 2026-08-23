# Comparison logic

The deterministic engine version is `authzdiff-rules/1.1`. It compares bounded, normalized HTTP
responses; it does not use an AI model, emit vulnerability probabilities, or evaluate authorization
policy semantics.

The engine records actual status, redirect outcome, safe response-header differences, response
length, content type, normalized JSON structure, redacted JSON value differences, bounded text
differences, denial/challenge/existence markers, sensitive-field path overlap, and binary hashes.
It never presents placeholder redirect, header, or JSON-value evidence.

Test-case configuration is applied as follows:

- ignored JSON paths are removed from structural/value comparison;
- explicitly unordered JSON arrays are canonicalized before comparison;
- ignored safe response headers are removed from header comparison;
- ignored text patterns are literal bounded-text replacements, not regular expressions;
- project-level volatile headers/text settings combine with the test-case settings.

Expected higher-profile success plus lower-profile 401/403 is treated as an expected access
control. Similar successful responses contrary to denial, ownership, tenant, method, authentication,
or sensitive-field expectations may create a vertical, horizontal/IDOR, tenant-scope,
method-inconsistency, existence-leak, or exposure review candidate. Anonymous comparisons are
identified separately.

This is heuristic black-box response comparison. It does not parse principals, users, groups,
nested groups, roles, resources, actions, wildcards, inherited permissions, explicit deny rules, or
equivalent IAM/RBAC policies. It cannot explain a policy-state change because no policy-state model
is ingested.

Transport failures and truncated evidence produce failed or inconclusive results. Confidence is
`low`, `medium`, or `high`; it is deterministic labeling rather than a statistical probability.
Every candidate includes limitations and alternative explanations and requires human review.
