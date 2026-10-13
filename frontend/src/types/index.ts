export interface InputData { filename: string; content: string }
export interface InputSummary {
  filename: string; format: "snapshot" | "har"; format_label: string;
  record_count: number; warnings: string[];
}
export interface InputSlot {
  data: InputData | null; summary: InputSummary | null; pending: boolean; error: string | null;
}
export interface Change {
  principal: string; resource: string; action: string; before: string; after: string;
  change: "gained" | "lost" | "changed"; category: string; summary: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  why: string; recommendation: string; evidence: Record<string, unknown>;
}
export interface ComparisonResult {
  schema_version: string; engine_version: string; before: InputSummary; after: InputSummary;
  summary: { total: number; gained: number; lost: number; risky: number; review: number; unchanged: number };
  changes: Change[]; notes: string[]; limitations: string[];
}
export interface CompareRequest { before: InputData; after: InputData }
export type ExportFormat = "pdf" | "json" | "csv";
