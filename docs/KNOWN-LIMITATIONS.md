# Known limitations

- Listed snapshots are not effective-policy evaluation. No inheritance, conditions, cross-rule deny precedence,
  wildcard expansion, or cloud IAM semantics are implemented.
- Not listed is an input state, not proof that a live system denies access.
- Recognized role ordering is a documented convention; arbitrary labels do not establish a hierarchy.
- HAR annotations must come from trusted identity/authorization context. HTTP codes alone are insufficient.
- Incomplete bodies, truncation, redirects, changed query/body context, and unmatched capture coverage require review.
- Repeated requests are rejected, rather than heuristically pairing observations across time.
- Sensitivity is explicitly supplied; arbitrary sensitive business content cannot be identified automatically.
- Redaction is best effort. JSON keys/resource names and unrecognized personal or business data may remain.
- Inputs are bounded; empty and incompatible inputs are rejected. Large datasets need preprocessing.
- PDF prioritizes 100 changes and has limited complex-script/RTL support; JSON preserves all Unicode evidence.
- No authentication is included. Local/network containment and hosted access limits are operator responsibilities.
- Memory-only does not imply cryptographic memory erasure or protection against OS swap.
- Docker and Linux/macOS deployment have not been runtime-validated in the Windows release checks.
- Publication scanning covers current publishable files and reachable Git history. Its recognizable
  credential patterns cannot identify every possible secret or private business record.
