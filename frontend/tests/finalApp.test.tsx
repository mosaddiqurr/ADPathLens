import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { Results } from "../src/components/Results";
import type { ComparisonResult } from "../src/types";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });
it("opens without login or bootstrap requests", async () => {
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  render(<App />);
  expect(screen.getByRole("heading", { name: "AuthZDiff" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "Compare access" }));
  expect(screen.getByRole("heading", { name: "Compare authorization" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Compare authorization" })).toBeDisabled();
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.queryByText("Sign in")).not.toBeInTheDocument();
});
it("keeps technical evidence collapsed and filters risk", async () => {
  const meta = { filename: "a.json", format: "snapshot" as const, format_label: "JSON", record_count: 1, warnings: [] };
  const result: ComparisonResult = { schema_version: "v1", engine_version: "v1", before: meta, after: meta,
    summary: { total: 1, gained: 1, lost: 0, risky: 1, review: 0, unchanged: 0 }, notes: [], limitations: [],
    changes: [{ principal: "Alice", resource: "Billing", action: "Read", before: "Viewer", after: "Admin", change: "gained",
      severity: "high", category: "Privilege escalation", summary: "Alice gained Admin.", why: "Management access.", recommendation: "Review.", evidence: { record: "sensitive evidence" } }],
  };
  render(<Results result={result} exporting={null} onExport={vi.fn()} />);
  expect(screen.getByText(/sensitive evidence/).closest("details")).not.toHaveAttribute("open");
  await userEvent.click(screen.getByRole("button", { name: "Lost" }));
  expect(screen.getByText("No changes match this filter.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Risky" }));
  expect(screen.getAllByText("Alice").length).toBeGreaterThan(0);
});
