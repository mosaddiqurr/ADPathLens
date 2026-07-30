# Comparison logic

The initial deterministic engine version is `authzdiff-rules/1.0`. It does not use an AI model and
does not emit vulnerability probabilities.

Observations compare status, content type, redirect outcome, response length, safe headers,
normalized JSON structure and values, bounded text, denial/challenge/existence markers, sensitive
field overlap, and binary hashes. Volatile headers have conservative defaults. JSON/body fields
are ignored only when a project or test case explicitly configures them. Unordered arrays require
an explicit path.

Expected higher-role success plus lower-role 401/403 or a validated login redirect is an expected
control. Similar successful responses contrary to denial, ownership, tenant, method, or
sensitive-field expectations create a review candidate with vertical, horizontal/IDOR,
tenant-scope, method-inconsistency, existence-leak, or exposure language. Anonymous comparisons
are distinguished from authenticated role comparisons.

Truncation, parse errors, authentication expiry, transport failures, generic wrapped errors, and
contradictory signals force an ambiguous or inconclusive result. Confidence is `low`, `medium`, or
`high`; it is not statistical. Every result records rationale, alternatives, limitations, and
manual checks.
