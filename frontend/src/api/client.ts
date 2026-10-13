import { z } from "zod";
import type { CompareRequest, ComparisonResult, ExportFormat, InputData, InputSummary } from "../types";

const summarySchema = z.object({
  filename: z.string(), format: z.enum(["snapshot", "har"]), format_label: z.string(),
  record_count: z.number().int().nonnegative(), warnings: z.array(z.string()),
});
const resultSchema = z.object({
  schema_version: z.string(), engine_version: z.string(), before: summarySchema, after: summarySchema,
  summary: z.object({ total: z.number(), gained: z.number(), lost: z.number(), risky: z.number(), review: z.number(), unchanged: z.number() }),
  changes: z.array(z.object({
    principal: z.string(), resource: z.string(), action: z.string(), before: z.string(), after: z.string(),
    change: z.enum(["gained", "lost", "changed"]), category: z.string(), summary: z.string(),
    severity: z.enum(["critical", "high", "medium", "low", "info"]), why: z.string(),
    recommendation: z.string(), evidence: z.record(z.unknown()),
  })),
  notes: z.array(z.string()), limitations: z.array(z.string()),
});
const safeMessages = new Set([
  "This file format is not supported.", "The Before dataset could not be parsed.",
  "The After dataset could not be parsed.", "The input dataset could not be parsed.",
  "The input could not be parsed.", "No comparable authorization records were found.",
  "The two inputs use incompatible formats.", "Each input must be 5 MB or smaller.",
  "The request is too large.", "The comparison service is busy. Try again shortly.",
  "The request could not be completed.", "This origin is not allowed.",
]);
export class UserError extends Error {}
export function userMessage(error: unknown, fallback = "The request could not be completed."): string {
  return error instanceof UserError ? error.message : fallback;
}
async function post(path: string, data: unknown, signal?: AbortSignal): Promise<Response> {
  let response: Response;
  const apiOrigin: unknown = import.meta.env.VITE_API_URL;
  const apiBase = typeof apiOrigin === "string" ? apiOrigin.replace(/\/$/, "") : "";
  try {
    response = await fetch(`${apiBase}/api/v1${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      credentials: "omit", cache: "no-store", body: JSON.stringify(data),
      signal: signal ?? AbortSignal.timeout(60_000),
    });
  } catch {
    if (signal?.aborted) throw new UserError("The comparison was cancelled.");
    throw new UserError("The comparison service is unavailable. Check your connection and try again.");
  }
  if (!response.ok) {
    let body: unknown;
    try { body = await response.json(); } catch { body = null; }
    const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
    throw new UserError(typeof detail === "string" && safeMessages.has(detail)
      ? detail : "The request could not be completed.");
  }
  return response;
}
async function parsed<T>(response: Response, schema: z.ZodType<T>): Promise<T> {
  try {
    const data: unknown = await response.json();
    return schema.parse(data);
  } catch { throw new UserError("The request could not be completed."); }
}
export async function inspectInput(data: InputData, signal?: AbortSignal): Promise<InputSummary> {
  return parsed(await post("/inspect", data, signal), summarySchema);
}
export async function compareInputs(data: CompareRequest, signal?: AbortSignal): Promise<ComparisonResult> {
  return parsed(await post("/compare", data, signal), resultSchema);
}
export async function exportReport(data: CompareRequest, format: ExportFormat): Promise<void> {
  const response = await post(`/reports/${format}`, data);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = `authzdiff-report.${format}`;
  document.body.append(anchor); anchor.click(); anchor.remove();
  window.setTimeout(() => { URL.revokeObjectURL(url); }, 1000);
}
