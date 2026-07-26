import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DirectoryNode, Finding, Project, Snapshot } from "../src/types/api";

const project: Project = {
  id: "p",
  workspace_id: "w",
  name: "Synthetic Project",
  description: "Authorized fictional data",
  status: "active",
};
const snapshot: Snapshot = {
  id: "s",
  project_id: "p",
  dataset_id: "d",
  parent_snapshot_id: null,
  name: "NORTHBRIDGE small",
  snapshot_type: "imported",
  version: 1,
  revision: 1,
  created_at: "2026-07-26T00:00:00Z",
};
const node: DirectoryNode = {
  id: "n1",
  snapshot_id: "s",
  external_id: "user-mina",
  node_type: "User",
  name: "Mina Rahman",
  display_name: "Mina Rahman",
  description: "Fictional user",
  domain_name: "NORTHBRIDGE.LOCAL",
  enabled: true,
  high_value: false,
  privileged: false,
  risk_level: "medium",
};
const target: DirectoryNode = {
  ...node,
  id: "n2",
  external_id: "group-domain-admins",
  node_type: "Group",
  name: "Domain Admins",
  display_name: "Domain Admins",
  high_value: true,
  privileged: true,
};
const finding: Finding = {
  id: "f",
  project_id: "p",
  snapshot_id: "s",
  title: "Synthetic privilege route",
  category: "privilege_path",
  severity: "high",
  confidence: "high",
  internal_score: 75,
  priority: "high",
  status: "draft",
  description: "A fictional relationship requires review.",
  technical_explanation: "Stored evidence supports a possible route.",
  impact: "Modeled privilege exposure.",
  evidence: { source: "synthetic" },
  contributing_signals: ["direct_privileged_control"],
  reducing_signals: [],
  remediation: "Remove unnecessary permission.",
  validation_steps: ["Retest."],
  limitations: "A possible path is not proof of compromise.",
  reviewer_notes: "",
};

const apiMock = vi.fn(async (path: string, options?: { method?: string }) => {
  if (path === "/workspaces") return [{ id: "w", name: "Lab", description: "Fictional" }];
  if (path === "/projects") return [project];
  if (path === "/projects/p") return project;
  if (path === "/projects/p/snapshots") return [snapshot];
  if (path === "/projects/p/datasets") return [{ id: "d", project_id: "p", name: "Demo", source_type: "demo", import_status: "complete", progress_percent: 100, node_count: 35, relationship_count: 55, data_hash: "a".repeat(64) }];
  if (path === "/snapshots/s") return snapshot;
  if (path.includes("/graph/summary")) return { node_count: 35, relationship_count: 55, high_value_count: 5, privileged_count: 4, nodes_by_type: { User: 1, Group: 1 } };
  if (path.includes("/snapshots/s/graph?")) return { snapshot_id: "s", truncated: false, limits: { nodes: 500, relationships: 1500 }, nodes: [{ data: { id: "n1", label: "Mina Rahman" } }], relationships: [] };
  if (path.includes("/snapshots/s/nodes")) return { items: [node, target], page: 1, page_size: 100, total: 2 };
  if (path.includes("/snapshots/s/relationships")) return { items: [{ id: "r", snapshot_id: "s", external_id: "rel-helpdesk-priya", source_node_id: "n1", target_node_id: "n2", relationship_type: "ResetPassword", active: true, inherited: false, confidence: "high", risk_weight: 1, description: "Synthetic" }], page: 1, page_size: 100, total: 1 };
  if (path.includes("/snapshots/s/analyses"))
    return {
      id: "a",
      snapshot_id: "s",
      algorithm: "shortest_hops",
      status: "complete",
      path_count: 1,
      truncated: false,
      paths: [
        {
          id: "path",
          rank: 1,
          total_weight: 1,
          hop_count: 1,
          risk_score: 80,
          confidence: "high",
          explanation: "Possible path.",
          limitations: finding.limitations,
          steps: [
            {
              position: 1,
              source_node_id: "n1",
              source_name: "Mina Rahman",
              relationship_id: "r",
              relationship_type: "ResetPassword",
              target_node_id: "n2",
              target_name: "Domain Admins",
              step_explanation: "Stored evidence.",
              remediation_summary: "Remove right.",
              confidence: "high",
              risk_weight: 1,
            },
          ],
        },
      ],
    };
  if (path.includes("/projects/p/findings")) return options?.method === "POST" ? finding : { items: [finding], page: 1, page_size: 100, total: 1 };
  if (path === "/findings/f") return finding;
  if (path === "/findings/f/notes") return options?.method === "POST" ? { id: "note", body: "Reviewed", created_by: "u", created_at: "2026-07-26T00:00:00Z" } : [];
  if (path === "/findings/f/history") return [{ id: "h", previous_status: null, new_status: "draft", note: "Created", changed_at: "2026-07-26T00:00:00Z" }];
  if (path.includes("/remediation-plans")) return [];
  if (path.includes("/comparisons")) return [];
  if (path.includes("/reports")) return [];
  if (path.startsWith("/audit/events")) return { items: [], page: 1, page_size: 200, total: 0 };
  if (path === "/settings") return [{ key: "ui.default_theme", value: null, configured: false }];
  if (path === "/risk/rules") return [{ rule_id: "APL-001", title: "Synthetic rule", enabled: true, configuration_version: 0 }];
  if (path === "/users") return [{ id: "u", email: "admin@example.com", display_name: "Administrator", role: "administrator", is_active: true }];
  return {};
});

vi.mock("../src/api/client", () => ({
  api: (path: string, options?: { method?: string }) => apiMock(path, options),
  errorMessage: () => "Request failed.",
}));
vi.mock("../src/features/auth/AuthContext", () => ({
  useAuth: () => ({ user: { id: "u", display_name: "Administrator", role: "administrator" } }),
}));
vi.mock("../src/graph/GraphCanvas", () => ({
  GraphCanvas: () => <div role="img" aria-label="Interactive privilege relationship graph" />,
}));

import { AuditPage, SettingsPage } from "../src/pages/AdminPages";
import { ComparisonPage } from "../src/pages/ComparisonPage";
import { DashboardPage } from "../src/pages/DashboardPage";
import { DemoPage } from "../src/pages/DemoPage";
import { FindingDetailPage } from "../src/pages/FindingDetailPage";
import { FindingsPage } from "../src/pages/FindingsPage";
import { GraphPage } from "../src/pages/GraphPage";
import { ImportPage } from "../src/pages/ImportPage";
import { PathPage } from "../src/pages/PathPage";
import { ProjectPage } from "../src/pages/ProjectPage";
import { RemediationPage } from "../src/pages/RemediationPage";
import { ReportsPage } from "../src/pages/ReportsPage";

afterEach(() => {
  cleanup();
  apiMock.mockClear();
});

function route(path: string, pattern: string, component: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Route path={pattern}>{component}</Route>
    </MemoryRouter>,
  );
}

describe("application pages", () => {
  it("renders dashboard and all project workflows from API data", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(await screen.findByText("Synthetic Project")).toBeInTheDocument();
    cleanup();

    route("/projects/p", "/projects/:projectId", <ProjectPage />);
    expect(await screen.findByRole("heading", { name: "Synthetic Project" })).toBeInTheDocument();
    cleanup();

    route("/projects/p/imports", "/projects/:projectId/imports", <ImportPage />);
    expect(await screen.findByText("Import history")).toBeInTheDocument();
    cleanup();

    route("/snapshots/s/graph", "/snapshots/:snapshotId/graph", <GraphPage />);
    expect(await screen.findByRole("img", { name: /Interactive privilege/ })).toBeInTheDocument();
    cleanup();

    route("/snapshots/s/paths", "/snapshots/:snapshotId/paths", <PathPage />);
    await screen.findByLabelText("Source");
    await user.click(screen.getByRole("button", { name: "Run bounded analysis" }));
    expect(await screen.findByText(/Found 1 bounded possible path/)).toBeInTheDocument();
    cleanup();

    route("/projects/p/findings", "/projects/:projectId/findings", <FindingsPage />);
    expect(await screen.findByText("Synthetic privilege route")).toBeInTheDocument();
    cleanup();

    route("/findings/f", "/findings/:findingId", <FindingDetailPage />);
    expect(await screen.findByRole("heading", { name: "Why this matters" })).toBeInTheDocument();
    cleanup();

    route("/projects/p/remediation", "/projects/:projectId/remediation", <RemediationPage />);
    expect(await screen.findByText(/Simulation only/)).toBeInTheDocument();
    cleanup();

    route("/projects/p/comparisons", "/projects/:projectId/comparisons", <ComparisonPage />);
    expect(await screen.findByRole("button", { name: "Compare snapshots" })).toBeInTheDocument();
    cleanup();

    route("/projects/p/reports", "/projects/:projectId/reports", <ReportsPage />);
    expect(await screen.findByRole("button", { name: "Generate sanitized report" })).toBeInTheDocument();
  });

  it("renders demo, audit, and administrator workflows", async () => {
    render(<MemoryRouter><DemoPage /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "NORTHBRIDGE.LOCAL" })).toBeInTheDocument();
    cleanup();
    render(<MemoryRouter><AuditPage /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Audit events" })).toBeInTheDocument();
    cleanup();
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Users, rules & settings" })).toBeInTheDocument();
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith("/risk/rules", undefined));
  });
});
