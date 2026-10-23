import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ProductProvider,
  useProduct,
} from "../src/features/product/ProductContext";
const mockApi = vi.hoisted(() => vi.fn());
const auth = vi.hoisted(() => ({
  user: { id: "u", role: "administrator" } as {
    id: string;
    role: string;
  } | null,
}));
vi.mock("../src/api/client", () => ({
  api: (path: string, options?: unknown) => mockApi(path, options),
  errorMessage: () => "Load failed",
}));
vi.mock("../src/features/auth/AuthContext", () => ({
  useAuth: () => auth,
}));
function Probe() {
  const p = useProduct();
  return (
    <>
      <span>{p.snapshot?.name ?? "Loading"}</span>
      <span>{p.analysis?.path_count ?? "No analysis"} paths</span>
      <button onClick={() => p.setSnapshotId("older")}>Earlier data</button>
      <span>{p.findings.map((f) => f.title).join(",")}</span>
      <button onClick={() => void p.ensureImportProject()}>
        Prepare import
      </button>
      <button
        onClick={() => void p.selectImportedSnapshot("import", "uploaded")}
      >
        Select upload
      </button>
      <button
        onClick={() =>
          void p.runAnalysis("target", "person", { algorithm: "lowest_cost" })
        }
      >
        Analyze source
      </button>
      <button onClick={() => void p.openDemo()}>Open demo</button>
    </>
  );
}
afterEach(() => {
  cleanup();
  localStorage.clear();
  mockApi.mockReset();
  auth.user = { id: "u", role: "administrator" };
});
describe("environment persistence", () => {
  it("restores a selected dataset and its latest analysis rather than mixing historical totals", async () => {
    mockApi.mockImplementation(async (path: string) => {
      if (path === "/projects")
        return [{ id: "p", name: "Directory", status: "active" }];
      if (path === "/projects/p/snapshots")
        return [
          { id: "new", name: "Latest directory", snapshot_type: "imported" },
          { id: "older", name: "Earlier directory", snapshot_type: "imported" },
        ];
      if (path.includes("/analyses/latest"))
        return {
          id: "a",
          path_count: path.includes("older") ? 2 : 5,
          paths: [],
        };
      if (path.includes("/findings"))
        return {
          items: [
            {
              title: path.includes("older")
                ? "Earlier finding"
                : "Current finding",
            },
          ],
          total: 1,
        };
      return [];
    });
    const view = render(
      <ProductProvider>
        <Probe />
      </ProductProvider>,
    );
    expect(await screen.findByText("5 paths")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Earlier data" }));
    expect(await screen.findByText("2 paths")).toBeInTheDocument();
    expect(screen.getByText("Earlier finding")).toBeInTheDocument();
    expect(screen.queryByText("Current finding")).not.toBeInTheDocument();
    view.unmount();
    render(
      <ProductProvider>
        <Probe />
      </ProductProvider>,
    );
    expect(await screen.findByText("Earlier directory")).toBeInTheDocument();
    expect(await screen.findByText("2 paths")).toBeInTheDocument();
  });
  it("restores the remembered collection after asynchronous authentication", async () => {
    localStorage.setItem("adpathlens.environment.u", "demo");
    auth.user = null;
    mockApi.mockImplementation(async (path: string) => {
      if (path === "/projects")
        return [
          { id: "empty", name: "Imported directory" },
          { id: "demo", name: "Demo" },
        ];
      if (path === "/projects/demo/snapshots")
        return [
          { id: "s", name: "Remembered demo", snapshot_type: "imported" },
        ];
      if (path.includes("/analyses/latest"))
        return { id: "a", path_count: 3, paths: [] };
      if (path.includes("/findings")) return { items: [], total: 0 };
      return [];
    });
    const view = render(
      <ProductProvider>
        <Probe />
      </ProductProvider>,
    );
    expect(mockApi).not.toHaveBeenCalled();
    auth.user = { id: "u", role: "analyst" };
    view.rerender(
      <ProductProvider>
        <Probe />
      </ProductProvider>,
    );
    expect(await screen.findByText("Remembered demo")).toBeInTheDocument();
    expect(await screen.findByText("3 paths")).toBeInTheDocument();
    expect(localStorage.getItem("adpathlens.environment.u")).toBe("demo");
  });
  it("keeps the current demo during validation and switches only after a successful import", async () => {
    localStorage.setItem("adpathlens.environment.u", "demo");
    const projects = [
      { id: "demo", name: "NORTHBRIDGE Guided Lab", status: "active" },
    ];
    mockApi.mockImplementation(
      async (path: string, options?: { method?: string }) => {
        if (path === "/projects" && options?.method === "POST") {
          const imported = {
            id: "import",
            name: "Imported directory",
            status: "active",
          };
          projects.push(imported);
          return imported;
        }
        if (path === "/projects") return [...projects];
        if (path === "/workspaces") return [{ id: "workspace" }];
        if (path === "/projects/demo/snapshots")
          return [{ id: "s", name: "Current demo", snapshot_type: "imported" }];
        if (path === "/projects/import/snapshots")
          return [
            {
              id: "uploaded",
              name: "Uploaded directory",
              snapshot_type: "imported",
            },
          ];
        if (path.includes("/analyses/latest")) return null;
        if (path.includes("/findings")) return { items: [], total: 0 };
        return [];
      },
    );
    render(
      <ProductProvider>
        <Probe />
      </ProductProvider>,
    );
    await screen.findByText("Current demo");
    await userEvent.click(
      screen.getByRole("button", { name: "Prepare import" }),
    );
    await waitFor(() =>
      expect(mockApi).toHaveBeenCalledWith(
        "/projects",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(screen.getByText("Current demo")).toBeInTheDocument();
    expect(localStorage.getItem("adpathlens.environment.u")).toBe("demo");
    await userEvent.click(
      screen.getByRole("button", { name: "Select upload" }),
    );
    expect(await screen.findByText("Uploaded directory")).toBeInTheDocument();
    expect(
      localStorage.getItem("adpathlens.environment.u.snapshot.import"),
    ).toBe("uploaded");
  });
  it("runs a targeted analysis and updates findings only for that selected snapshot", async () => {
    mockApi.mockImplementation(
      async (path: string, options?: { method?: string }) => {
        if (path === "/projects") return [{ id: "demo", name: "Directory" }];
        if (path === "/projects/demo/snapshots")
          return [
            { id: "s", name: "Selected directory", snapshot_type: "imported" },
          ];
        if (path.includes("/analyses/latest")) return null;
        if (path.includes("/nodes"))
          return {
            items: [{ id: "person", enabled: true, privileged: false }],
            total: 1,
          };
        if (path.endsWith("/analyses") && options?.method === "POST")
          return { id: "a", path_count: 4, paths: [] };
        if (path.includes("/findings"))
          return { items: [{ title: "Validated finding" }], total: 1 };
        return {};
      },
    );
    render(
      <ProductProvider>
        <Probe />
      </ProductProvider>,
    );
    await screen.findByText("Selected directory");
    await userEvent.click(
      screen.getByRole("button", { name: "Analyze source" }),
    );
    expect(await screen.findByText("4 paths")).toBeInTheDocument();
    expect(mockApi).toHaveBeenCalledWith(
      "/snapshots/s/analyses",
      expect.objectContaining({
        json: expect.objectContaining({
          start_node_id: "person",
          target_node_id: "target",
          algorithm: "lowest_cost",
          maximum_paths: 25,
        }),
      }),
    );
    await waitFor(() =>
      expect(mockApi).toHaveBeenCalledWith("/snapshots/s/risk-scan", {
        method: "POST",
      }),
    );
    expect(screen.getByText("Validated finding")).toBeInTheDocument();
  });
});
