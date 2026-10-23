# Attack-path interpretation

ADPathLens calculates possible privilege paths from one persisted, authorized snapshot. It does not attempt exploitation or treat a path as proof of compromise.

The default UI traces one shortest route from each reachable enabled, non-privileged object to the selected target. A selected starting identity exposes three alternate algorithms: shortest hops, lowest confidence-adjusted relationship cost, and bounded multiple simple paths. The API also supports confidence, enabled-object, source/target-type, allowed/excluded relationship filters. When filters leave no eligible relationship types, traversal returns no path.

Traversal prevents repeated nodes and enforces graph-size, depth, result-count, expansion, deadline, and concurrency limits. Reverse searches share one deadline and expansion budget across their candidate sources. Results reaching a budget or return cap are marked partial. Deterministic ties use cost, hops, and ordered node/relationship identities.

Reverse queries honor source-type and disabled-object options for every candidate source. They evaluate candidates within the shared budget, rank discovered routes by review score, then apply the return cap. Alphabetical source order does not determine which discovered routes survive that cap. API ranks and exported reports use the same review-score order as Results.

Each response preserves ordered source/target names and types, relationship IDs/types, source evidence, confidence, relationship weight, explanation, remediation guidance, and score components. The review score is `100 - 3 * effective relationship cost - hop count`, clamped to 0-100. Confidence and inheritance adjust effective cost; destination criticality is reported as context. Priority bands are Critical >=85, High >=65, Medium >=35, and Low <35. They are sorting aids, not exploitation probabilities or CVSS scores.

The UI explains individual prerequisites. Membership delegates group rights; local administration may expose computer credentials; session evidence indicates possible privileged credential exposure; ACL/GPO relationships require confirming the specific effective permission and affected scope. Recommendations address the relationship responsible and count coverage only among returned paths.

No path means no eligible route was found in the supplied data under the selected filters and bounds. Missing data, collection errors, disabled objects, time/expansion caps, and unseen alternate routes can change the result. Review evidence against the real directory and retest with fresh authorized data after a fix.
