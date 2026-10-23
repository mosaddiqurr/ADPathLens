"""Review priority for the existing deterministic path score; not exploit probability."""


def path_severity(score: float) -> str:
    if score >= 85:
        return "critical"
    if score >= 65:
        return "high"
    if score >= 35:
        return "medium"
    return "low"
