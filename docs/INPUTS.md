# Inputs

Each upload is UTF-8 JSON, CSV, or HAR, at most 5 MiB.
The limit is enforced in the browser and backend. Two-input JSON API requests are bounded to 12 MiB.
There is no filename-based filesystem access or archive extraction.

## Snapshots

An array of records is accepted, or:

```json
{
  "schema": "authzdiff/snapshot-v1",
  "records": [
    {"principal": "Alice", "resource": "Billing", "action": "Read", "effect": "allow", "role": "Viewer", "sensitive": false}
  ]
}
```

Required fields: principal, resource, action, effect (allow or deny).
Optional fields: role, sensitive (JSON boolean).
An optional wrapper name is display-neutral metadata. Unknown fields/schema versions are rejected.
A maximum of 2,000 records is supported. Empty inputs and duplicate principal/resource/action tuples
are rejected. Do not supply overlapping rule sets that need deny precedence or policy evaluation.

CSV has the same headers. Required columns are principal,resource,action,effect.
Optional role may be blank; sensitive accepts true, false, or blank.
The CSV header names are exact and duplicate/unknown columns are rejected.
JSON and CSV describe the same model and can be compared together.

Labels are trimmed and reject control characters or invalid Unicode. Principal/action labels are
bounded to 256 characters, resources to 512, roles to 128. Other principal/resource/action case is
preserved. *, Public, Anonymous, and Unauthenticated principal names normalize to Public.

## HAR captures

A HAR has log.entries containing request and response objects. At most 500 entries are supported.
The request needs method and an absolute HTTP(S) URL. The response needs a valid integer status
and may include headers and content. Content text supports plain UTF-8 or HAR base64 encoding.
Bodies are limited to 256 KiB, normalized excerpts to 8,000 bytes, and nesting to 30 levels.
URLs with embedded credentials, traversal/ambiguous path encoding, or invalid origins are rejected.

Identity and access context may be supplied on log._authzdiff or per entry:

```json
"_authzdiff": {"principal": "Alice", "access": "denied", "sensitive": true}
```

Allowed access values are allowed, denied, and unknown. Per-entry fields override log fields.
Supply these annotations from known identity/authorization evidence; never manufacture them
from a status code alone. Unannotated captures are accepted for response review and do not
produce confirmed access gains/losses.

Truncation flags and positive content.size larger than captured bytes make the response incomplete.
Evidence trimmed by array/excerpt bounds is also inconclusive for authorization transitions.
Repeated identical requests within a capture are rejected as ambiguous. Preselect one request
per identity/context before comparing an ordinary browser capture with repeats.

Different request bodies or non-credential queries are different contexts. Different origins
are also different resources; cross-environment equivalence is not guessed.
Exact encoded paths, non-credential request headers (including tenant headers), content types,
and form parameters are part of matching. Changed context becomes capture coverage review.
Credential header/query rotation is excluded from matching; the supplied principal annotation
must accurately identify the same actor. Request headers and body/form content are hashed for
matching and never included in evidence or exports. Empty/header-only CSV and empty HAR are rejected.

## Examples

../examples/snapshot-before.json and snapshot-after.json demonstrate the full risk workflow.
snapshot-before.csv is equivalent to the JSON baseline.
capture-before.har and capture-after.har demonstrate corroborated 403 -> 200 and 200 -> 403
transitions. All sample names and content are fictional; example.invalid is never contacted.

AWS IAM policies, role graphs, raw HTTP, cURL, and arbitrary JSON are not accepted product inputs.
