# Fictional example inputs

Every principal, resource, response, and domain in this directory is synthetic.
There are no captured production requests, credentials, or private fixtures.

- snapshot-before.json + snapshot-after.json: five changes (3 gained, 1 lost, 3 risky, 1 review).
  Risky overlaps gained/lost; a removed deny is a review item, not an inferred gain.
- snapshot-before.csv is equivalent to snapshot-before.json.
- capture-before.har + capture-after.har: one context-confirmed observed gain and one loss.
  The reserved example.invalid domain is never contacted.

See ../docs/INPUTS.md for the format contract.
