import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Analysis, PathResult } from "../src/types/api";

const fixtures = vi.hoisted(() => ({
  api: vi.fn(),
  state: {} as Record<string, unknown>,
}));
vi.mock("../src/api/client", () => ({
  api: fixtures.api,
  errorMessage: (e: Error) => e.message,
}));
vi.mock("../src/features/product/ProductContext", () => ({
  useProduct: () => fixtures.state,
}));
vi.mock("../src/features/product/FocusedPathGraph", () => ({
  FocusedPathGraph: () => <div role="img" aria-label="Selected path graph" />,
}));
import { ResultsPage } from "../src/pages/ResultsPage";

function path(
  id: string,
  name: string,
  type: string,
  score: number,
): PathResult {
  return {
    id,
    rank: 1,
    total_weight: 1,
    hop_count: 1,
    risk_score: score,
    severity: "high",
    scoring_components: {},
    confidence: "high",
    explanation: "Modeled access",
    limitations: "Requires validation.",
    steps: [
      {
        position: 1,
        source_node_id: id,
        source_name: name,
        source_type: type,
        relationship_id: `r-${id}`,
        relationship_type: "GenericAll",
        target_node_id: "target",
        target_name: "Domain Admins",
        target_type: "Group",
        step_explanation: "Full control",
        remediation_summary: "Review ACL",
        confidence: "high",
        risk_weight: 1,
        evidence: { source: "Fictional ACL export" },
      },
    ],
  };
}
function setup(
  paths = [
    path("user", "Mina", "User", 90),
    path("computer", "SERVER-01", "Computer", 70),
  ],
) {
  const analysis: Analysis = {
    id: "analysis",
    snapshot_id: "snapshot",
    algorithm: "top_paths",
    status: "complete",
    path_count: paths.length,
    paths,
    truncated: false,
  };
  fixtures.state = {
    projectId: "project",
    project: { name: "Fictional" },
    snapshotId: "snapshot",
    snapshot: { name: "Demo" },
    analysis,
    fixes: paths.map((p) => ({
      id: p.steps[0].relationship_id,
      title: "Review ACL",
      summary: "Remove unnecessary full control",
      paths: 1,
    })),
    loading: false,
    error: "",
    canEdit: true,
  };
  render(
    <MemoryRouter>
      <ResultsPage />
    </MemoryRouter>,
  );
}
afterEach(() => {
  cleanup();
  fixtures.api.mockReset();
});
describe("focused results", () => {
  it("prioritizes paths and keeps source evidence and entity filters aligned", async () => {
    setup();
    const user = userEvent.setup();
    expect(
      screen.getByRole("button", { name: /Inspect path from Mina/ }),
    ).toHaveAttribute("aria-pressed", "true");
    await user.click(
      screen.getByText("Source evidence", { selector: "summary" }),
    );
    expect(screen.getByText(/Fictional ACL export/)).toBeVisible();
    await user.selectOptions(screen.getByLabelText("Entity type"), "Computer");
    expect(
      screen.queryByRole("button", { name: /Inspect path from Mina/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Inspect path from SERVER-01/ }),
    ).toHaveAttribute("aria-pressed", "true");
    await user.selectOptions(screen.getByLabelText("Severity"), "critical");
    expect(
      screen.getByRole("heading", { name: "No paths match these filters" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(
      screen.getAllByRole("button", { name: /Inspect path from/ }),
    ).toHaveLength(2);
  });
  it("exports the selected snapshot and exposes an actionable failure", async () => {
    setup();
    fixtures.api.mockRejectedValueOnce(new Error("Report storage unavailable"));
    await userEvent.click(
      screen.getByRole("button", { name: "Export report" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Report storage unavailable",
    );
    fixtures.api.mockResolvedValueOnce({ id: "report", format: "json" });
    await userEvent.selectOptions(
      screen.getByLabelText("Report format"),
      "json",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Export report" }),
    );
    expect(
      await screen.findByRole("link", { name: "Download JSON report" }),
    ).toHaveAttribute("href", "/api/v1/reports/report/download");
    expect(fixtures.api).toHaveBeenCalledWith(
      "/projects/project/reports",
      expect.objectContaining({
        json: expect.objectContaining({
          snapshot_id: "snapshot",
          format: "json",
        }),
      }),
    );
  });
  it("bounds the meaning of a no-path result", () => {
    setup([]);
    expect(
      screen.getByRole("heading", {
        name: "No eligible path found in this scope",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Missing routes do not establish/),
    ).toBeInTheDocument();
  });
});
