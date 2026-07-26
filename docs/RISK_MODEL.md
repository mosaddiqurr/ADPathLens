# Risk model

Risk scans use deterministic, versioned rules. They produce Draft findings only; a human explicitly
confirms, rejects, accepts, plans, resolves, requests retest, or closes each result.

Base points are Informational 10, Low 30, Medium 50, and High 75. Direct high-value control,
short paths, independent support, and affected-asset counts add points. Lower confidence,
inherited-only, inactive/disabled-only, and missing evidence reduce points. Scores are clamped to
0–100 and labels are derived from documented thresholds.

Critical requires high-confidence active evidence, direct privileged/high-value impact, and two
independent strong signals. Rule configuration and relationship weight changes are administrator
only, versioned, audited, and affect new work without rewriting history.
