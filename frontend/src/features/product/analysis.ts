import { api } from "../../api/client";
import type { Analysis, Page } from "../../types/api";
export async function readAll<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  for (let page = 1; ; page++) {
    const result = await api<Page<T>>(
      `${path}${path.includes("?") ? "&" : "?"}page_size=100&page=${page}`,
    );
    items.push(...result.items);
    if (items.length >= result.total || !result.items.length) return items;
  }
}
export function pathSeverity(score: number) {
  return score >= 85
    ? "critical"
    : score >= 65
      ? "high"
      : score >= 35
        ? "medium"
        : "low";
}
export function recommendations(analysis: Analysis | null) {
  const grouped = new Map<
    string,
    { id: string; title: string; summary: string; paths: number; score: number }
  >();
  for (const path of analysis?.paths ?? []) {
    for (const step of path.steps) {
      const existing = grouped.get(step.relationship_id);
      if (existing) {
        existing.paths++;
        existing.score = Math.max(existing.score, path.risk_score);
      } else
        grouped.set(step.relationship_id, {
          id: step.relationship_id,
          title: `Review ${step.source_name} → ${step.target_name}`,
          summary: step.remediation_summary,
          paths: 1,
          score: path.risk_score,
        });
    }
  }
  return [...grouped.values()].sort(
    (a, b) =>
      b.paths - a.paths || b.score - a.score || a.title.localeCompare(b.title),
  );
}
