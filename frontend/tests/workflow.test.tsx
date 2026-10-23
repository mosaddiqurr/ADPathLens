import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fixtures = vi.hoisted(() => ({
  api: vi.fn(),
  state: {} as Record<string, unknown>,
  signOut: vi.fn(),
}));
vi.mock("../src/api/client", () => ({
  api: fixtures.api,
  errorMessage: (e: Error) => e.message,
}));
vi.mock("../src/features/product/ProductContext", () => ({
  useProduct: () => fixtures.state,
}));
vi.mock("../src/features/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "user" },
    localMode: false,
    signOut: fixtures.signOut,
  }),
}));
import { AnalyzePage } from "../src/pages/ProductPages";
import { ImportPanel } from "../src/components/ImportPanel";
import { AppLayout } from "../src/layouts/AppLayout";

function Location() {
  return <output aria-label="Current route">{useLocation().pathname}</output>;
}
function renderPage(children: React.ReactNode, url = "/analyze") {
  return render(
    <MemoryRouter initialEntries={[url]}>
      {children}
      <Location />
    </MemoryRouter>,
  );
}
const nodes = [
  {
    id: "person",
    display_name: "Mina",
    high_value: false,
    enabled: true,
    node_type: "User",
  },
  {
    id: "admins",
    display_name: "Domain Admins",
    high_value: true,
    enabled: true,
    node_type: "Group",
  },
];
function directory() {
  return {
    snapshot: { id: "snapshot", name: "Fictional directory" },
    snapshotId: "snapshot",
    project: { id: "demo", name: "NORTHBRIDGE Guided Lab" },
    projectId: "demo",
    projects: [],
    snapshots: [],
    loading: false,
    error: "",
    canEdit: true,
    runAnalysis: vi.fn(),
    openDemo: vi.fn(),
    ensureImportProject: vi.fn().mockResolvedValue("imported"),
    selectImportedSnapshot: vi.fn(),
  };
}
beforeEach(() => {
  fixtures.state = directory();
  fixtures.api.mockResolvedValue({ items: nodes, total: nodes.length });
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  fixtures.api.mockReset();
  fixtures.signOut.mockReset();
});

describe("analysis workflow", () => {
  it("shows progress, recovers from a failed analysis, and opens successful results", async () => {
    let rejectAnalysis!: (e: Error) => void;
    const run = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            rejectAnalysis = reject;
          }),
      )
      .mockResolvedValueOnce({});
    fixtures.state.runAnalysis = run;
    renderPage(<AnalyzePage />);
    const user = userEvent.setup();
    const button = await screen.findByRole("button", { name: "Run analysis" });
    await user.click(button);
    expect(
      screen.getByRole("button", { name: "Analyzing directory…" }),
    ).toBeDisabled();
    expect(screen.getByText(/Tracing eligible relationships/)).toBeVisible();
    rejectAnalysis(new Error("Analysis unavailable. Try again."));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Analysis unavailable",
    );
    await user.click(
      await screen.findByRole("button", { name: "Run analysis" }),
    );
    expect(run).toHaveBeenLastCalledWith("admins", "", {
      maximum_depth: 12,
      minimum_confidence: "low",
      algorithm: "reverse_reachability",
    });
    await waitFor(() =>
      expect(screen.getByLabelText("Current route")).toHaveTextContent(
        "/results",
      ),
    );
  });
  it("uses explicit source and confidence/algorithm limits for a targeted analysis", async () => {
    const run = vi.fn().mockResolvedValue({});
    fixtures.state.runAnalysis = run;
    renderPage(<AnalyzePage />);
    const user = userEvent.setup();
    await screen.findByRole("button", { name: "Run analysis" });
    await user.selectOptions(
      screen.getByLabelText("Starting identity"),
      "person",
    );
    await user.click(screen.getByText("Analysis limits & options"));
    await user.selectOptions(
      screen.getByLabelText("Path algorithm"),
      "lowest_cost",
    );
    await user.clear(screen.getByLabelText("Maximum relationships"));
    await user.type(screen.getByLabelText("Maximum relationships"), "8");
    await user.selectOptions(
      screen.getByLabelText("Minimum confidence"),
      "high",
    );
    await user.click(screen.getByRole("button", { name: "Run analysis" }));
    expect(run).toHaveBeenCalledWith("admins", "person", {
      maximum_depth: 8,
      minimum_confidence: "high",
      algorithm: "lowest_cost",
    });
  });
  it("explains missing high-value flags and exposes asset-loading failures", async () => {
    fixtures.api.mockResolvedValue({ items: [nodes[0]], total: 1 });
    renderPage(<AnalyzePage />);
    expect(
      await screen.findByText(/No asset is marked high value/),
    ).toBeVisible();
    cleanup();
    fixtures.api.mockRejectedValue(
      new Error("Directory objects could not be loaded"),
    );
    renderPage(<AnalyzePage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Directory objects could not be loaded",
    );
    expect(screen.getByRole("button", { name: "Run analysis" })).toBeDisabled();
  });
  it("recovers a failed demo load and supports the direct demo URL", async () => {
    fixtures.state = { ...directory(), snapshot: undefined, snapshotId: "" };
    const openDemo = vi
      .fn()
      .mockRejectedValueOnce(new Error("Demo unavailable"))
      .mockResolvedValue(undefined);
    fixtures.state.openDemo = openDemo;
    renderPage(<AnalyzePage />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Load demo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Demo unavailable",
    );
    await user.click(screen.getByRole("button", { name: "Load demo" }));
    expect(openDemo).toHaveBeenCalledTimes(2);
    cleanup();
    renderPage(<AnalyzePage />, "/analyze?demo=1");
    await waitFor(() => expect(openDemo).toHaveBeenCalledTimes(3));
  });
});

describe("validated import", () => {
  it("requires authorization and warning acknowledgement and binds import to the validated collection", async () => {
    fixtures.api
      .mockResolvedValueOnce({
        valid: true,
        digest: "digest",
        node_count: 2,
        relationship_count: 1,
        messages: [
          {
            level: "warning",
            code: "confidence",
            location: "relationships[0]",
            message: "Review source confidence",
          },
        ],
      })
      .mockResolvedValueOnce({ id: "new-snapshot", name: "Directory" });
    const imported = vi.fn().mockResolvedValue(undefined);
    const prepare = vi.fn().mockResolvedValue("imported");
    renderPage(<ImportPanel prepareProject={prepare} onImported={imported} />);
    const user = userEvent.setup();
    await user.upload(
      screen.getByLabelText("JSON dataset"),
      new File(["{}"], "directory.json", { type: "application/json" }),
    );
    await user.click(screen.getByRole("button", { name: "Validate dataset" }));
    const load = await screen.findByRole("button", { name: "Import dataset" });
    expect(load).toBeDisabled();
    await user.click(
      screen.getByRole("checkbox", { name: /Authorized-use confirmation/ }),
    );
    expect(load).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: "Acknowledge" }));
    await user.click(load);
    await waitFor(() =>
      expect(imported).toHaveBeenCalledWith("new-snapshot", "imported"),
    );
    const [url, options] = fixtures.api.mock.calls[1];
    expect(url).toBe("/projects/imported/datasets/import-json");
    expect(options.body.get("validation_digest")).toBe("digest");
    expect(options.body.get("acknowledged_warnings")).toBe("confidence");
  });
  it("rejects malformed data and clears stale validation when the file changes", async () => {
    fixtures.api
      .mockResolvedValueOnce({
        valid: false,
        digest: "old",
        node_count: 0,
        relationship_count: 0,
        messages: [],
      })
      .mockResolvedValueOnce({
        valid: true,
        digest: "new",
        node_count: 2,
        relationship_count: 1,
        messages: [],
      });
    renderPage(<ImportPanel projectId="project" />);
    const user = userEvent.setup();
    const upload = screen.getByLabelText("JSON dataset");
    await user.upload(
      upload,
      new File(["bad"], "bad.json", { type: "application/json" }),
    );
    await user.click(screen.getByRole("button", { name: "Validate dataset" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This dataset has errors",
    );
    expect(
      screen.getByRole("button", { name: "Import dataset" }),
    ).toBeDisabled();
    await user.upload(
      upload,
      new File(["{}"], "good.json", { type: "application/json" }),
    );
    expect(
      screen.queryByRole("button", { name: "Import dataset" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Validate dataset" }));
    await screen.findByText(/Ready to load/);
    await user.click(screen.getByRole("radio", { name: "CSV" }));
    expect(
      screen.queryByRole("button", { name: "Import dataset" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Validate dataset" }),
    ).toBeDisabled();
    await user.upload(
      screen.getByLabelText("nodes.csv"),
      new File(["id,type,name"], "nodes.csv", { type: "text/csv" }),
    );
    expect(
      screen.getByRole("button", { name: "Validate dataset" }),
    ).toBeDisabled();
    await user.upload(
      screen.getByLabelText("relationships.csv"),
      new File(["source,target,type"], "relationships.csv", {
        type: "text/csv",
      }),
    );
    expect(
      screen.getByRole("button", { name: "Validate dataset" }),
    ).toBeEnabled();
    await user.click(screen.getByRole("radio", { name: "ZIP" }));
    expect(screen.getByLabelText("CSV ZIP")).toHaveAttribute("accept", ".zip");
  });
  it("keeps imported data available when validation fails so the user can resume analysis", async () => {
    fixtures.api.mockImplementation(async (url: string) =>
      url.includes("/nodes")
        ? { items: nodes, total: nodes.length }
        : {
            valid: false,
            digest: "",
            node_count: 0,
            relationship_count: 0,
            messages: [],
          },
    );
    renderPage(<AnalyzePage />);
    const user = userEvent.setup();
    await screen.findByRole("button", { name: "Run analysis" });
    await user.click(screen.getByRole("button", { name: "Import new data" }));
    await user.upload(
      screen.getByLabelText("JSON dataset"),
      new File(["bad"], "bad.json", { type: "application/json" }),
    );
    await user.click(screen.getByRole("button", { name: "Validate dataset" }));
    await screen.findByRole("alert");
    await user.click(
      screen.getByRole("button", { name: "Use current snapshot" }),
    );
    expect(screen.getByText("Directory data loaded")).toBeVisible();
    expect(screen.getByRole("button", { name: "Run analysis" })).toBeEnabled();
  });
});

it("supports keyboard menu dismissal, page titles, and shared-session sign out", async () => {
  renderPage(
    <AppLayout>
      <h1>Analyze</h1>
    </AppLayout>,
  );
  const user = userEvent.setup();
  expect(document.title).toBe("Analyze · ADPathLens");
  await user.click(screen.getByRole("button", { name: "Open navigation" }));
  expect(
    screen.getByRole("button", { name: "Close navigation" }),
  ).toHaveAttribute("aria-expanded", "true");
  await user.keyboard("{Escape}");
  expect(screen.getByRole("button", { name: "Open navigation" })).toHaveFocus();
  await user.click(screen.getByRole("link", { name: "About", exact: true }));
  expect(document.title).toBe("About · ADPathLens");
  await user.click(screen.getByRole("button", { name: "Sign out" }));
  expect(fixtures.signOut).toHaveBeenCalledOnce();
});
