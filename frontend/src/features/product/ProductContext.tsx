import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../auth/AuthContext";
import type {
  Analysis,
  DirectoryNode,
  Finding,
  Project,
  Snapshot,
  Workspace,
} from "../../types/api";

import { readAll, recommendations } from "./analysis";
function useProductState() {
  const { user } = useAuth();
  const userId = user?.id;
  const storageKey = `adpathlens.environment.${user?.id ?? "guest"}`;
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(
    () => localStorage.getItem(storageKey) ?? "",
  );
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [snapshotId, setSnapshotId] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const selectedSnapshot = useRef(snapshotId);
  const demoOpening = useRef<Promise<void> | null>(null);
  useEffect(() => {
    selectedSnapshot.current = snapshotId;
  }, [snapshotId]);
  useEffect(() => {
    if (snapshotId && snapshots.some((s) => s.id === snapshotId))
      localStorage.setItem(`${storageKey}.snapshot.${projectId}`, snapshotId);
  }, [storageKey, projectId, snapshotId, snapshots]);
  const reloadProjects = useCallback(async () => {
    const data = await api<Project[]>("/projects");
    setProjects(data);
    setProjectId((current) =>
      data.some((p) => p.id === current)
        ? current
        : (data.find((p) => p.id === localStorage.getItem(storageKey))?.id ??
          data.find((p) => p.status !== "archived")?.id ??
          ""),
    );
    return data;
  }, [storageKey]);
  useEffect(() => {
    let alive = true;
    if (!userId) {
      setLoading(false);
      setProjects([]);
      setProjectId("");
      return;
    }
    setLoading(true);
    reloadProjects()
      .catch((e) => {
        if (alive) setError(errorMessage(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [reloadProjects, userId]);
  useEffect(() => {
    if (userId && projectId) localStorage.setItem(storageKey, projectId);
  }, [projectId, storageKey, userId]);
  useEffect(() => {
    let alive = true;
    setSnapshots([]);
    setSnapshotId("");
    setAnalysis(null);
    setFindings([]);
    if (!projectId) return;
    setLoading(true);
    api<Snapshot[]>(`/projects/${projectId}/snapshots`)
      .then((data) => {
        if (alive) {
          setSnapshots(data);
          const remembered = localStorage.getItem(
            `${storageKey}.snapshot.${projectId}`,
          );
          setSnapshotId(
            data.find((s) => s.id === remembered)?.id ??
              data.find((s) => s.snapshot_type === "imported")?.id ??
              data[0]?.id ??
              "",
          );
        }
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [projectId, storageKey]);
  useEffect(() => {
    let alive = true;
    setAnalysis(null);
    setFindings([]);
    setError("");
    if (!snapshotId) return;
    setLoading(true);
    Promise.all([
      api<Analysis | null>(`/snapshots/${snapshotId}/analyses/latest`),
      readAll<Finding>(
        `/projects/${projectId}/findings?snapshot_id=${snapshotId}`,
      ),
    ])
      .then(([a, f]) => {
        if (alive) {
          setAnalysis(a);
          setFindings(f);
        }
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [projectId, snapshotId]);
  async function refresh() {
    if (!projectId) return;
    const data = await api<Snapshot[]>(`/projects/${projectId}/snapshots`);
    setSnapshots(data);
    if (snapshotId) {
      const [a, f] = await Promise.all([
        api<Analysis | null>(`/snapshots/${snapshotId}/analyses/latest`),
        readAll<Finding>(
          `/projects/${projectId}/findings?snapshot_id=${snapshotId}`,
        ),
      ]);
      setAnalysis(a);
      setFindings(f);
    }
  }
  function openDemo() {
    if (!demoOpening.current) {
      demoOpening.current = importDemo().finally(() => {
        demoOpening.current = null;
      });
    }
    return demoOpening.current;
  }
  async function importDemo() {
    const data = await api<Project[]>("/projects");
    let demo = data.find((p) => p.name === "NORTHBRIDGE Guided Lab");
    if (!demo) {
      let workspaces = await api<Workspace[]>("/workspaces");
      if (!workspaces.length)
        workspaces = [
          await api<Workspace>("/workspaces", {
            method: "POST",
            json: {
              name: "NORTHBRIDGE Lab",
              description: "Fictional directory environment",
            },
          }),
        ];
      demo = await api<Project>("/projects", {
        method: "POST",
        json: {
          workspace_id: workspaces[0].id,
          name: "NORTHBRIDGE Guided Lab",
          description: "Fictional Active Directory environment",
        },
      });
    }
    const existing = await api<Snapshot[]>(`/projects/${demo.id}/snapshots`);
    if (!existing.length)
      await api<Snapshot>(`/projects/${demo.id}/datasets/import-demo`, {
        method: "POST",
        json: { demo: "small", authorization_confirmed: true },
      });
    await reloadProjects();
    setProjectId(demo.id);
    const loaded = await api<Snapshot[]>(`/projects/${demo.id}/snapshots`);
    setSnapshots(loaded);
    setSnapshotId(
      loaded.find((s) => s.snapshot_type === "imported")?.id ??
        loaded[0]?.id ??
        "",
    );
  }
  async function ensureImportProject() {
    if (projectId && project?.name !== "NORTHBRIDGE Guided Lab")
      return projectId;
    const existing = projects.find(
      (p) => p.name === "Imported directory" && p.status !== "archived",
    );
    if (existing) {
      return existing.id;
    }
    const workspaces = await api<Workspace[]>("/workspaces");
    const workspace =
      workspaces[0] ??
      (await api<Workspace>("/workspaces", {
        method: "POST",
        json: {
          name: "Directory analysis",
          description: "Authorized directory data",
        },
      }));
    const imported = await api<Project>("/projects", {
      method: "POST",
      json: {
        workspace_id: workspace.id,
        name: "Imported directory",
        description: "Authorized directory data",
      },
    });
    await reloadProjects();
    return imported.id;
  }
  async function selectImportedSnapshot(nextProjectId: string, id: string) {
    const data = await api<Snapshot[]>(`/projects/${nextProjectId}/snapshots`);
    localStorage.setItem(`${storageKey}.snapshot.${nextProjectId}`, id);
    setProjectId(nextProjectId);
    setSnapshots(data);
    setSnapshotId(id);
  }
  async function runAnalysis(
    target: string,
    source = "",
    advanced: Record<string, unknown> = {},
  ) {
    const nodes = await readAll<DirectoryNode>(
      `/snapshots/${snapshotId}/nodes`,
    );
    const start =
      source ||
      nodes.find((n) => n.enabled && !n.privileged)?.id ||
      nodes[0]?.id;
    if (!start || !target)
      throw new Error("Choose a critical asset before analyzing.");
    const result = await api<Analysis>(`/snapshots/${snapshotId}/analyses`, {
      method: "POST",
      json: {
        start_node_id: start,
        target_node_id: target,
        target_kind: "specific",
        algorithm: source ? "top_paths" : "reverse_reachability",
        maximum_depth: 12,
        maximum_paths: 25,
        minimum_confidence: "low",
        ...advanced,
      },
    });
    if (selectedSnapshot.current !== snapshotId)
      throw new Error(
        "The selected dataset changed. Open its analysis to continue.",
      );
    setAnalysis(result);
    await api(`/snapshots/${snapshotId}/risk-scan`, { method: "POST" });
    const nextFindings = await readAll<Finding>(
      `/projects/${projectId}/findings?snapshot_id=${snapshotId}`,
    );
    if (selectedSnapshot.current === snapshotId) setFindings(nextFindings);
    return result;
  }
  const project = projects.find((p) => p.id === projectId);
  const snapshot = snapshots.find((s) => s.id === snapshotId);
  const fixes = useMemo(() => recommendations(analysis), [analysis]);
  return {
    projects,
    project,
    projectId,
    setProjectId,
    snapshots,
    snapshot,
    snapshotId,
    setSnapshotId,
    analysis,
    setAnalysis,
    findings,
    fixes,
    loading,
    error,
    refresh,
    reloadProjects,
    openDemo,
    ensureImportProject,
    selectImportedSnapshot,
    runAnalysis,
    canEdit: Boolean(user) && user?.role !== "viewer",
  };
}
const ProductContext = createContext<ReturnType<typeof useProductState> | null>(
  null,
);
export function ProductProvider({ children }: { children: React.ReactNode }) {
  const state = useProductState();
  return (
    <ProductContext.Provider value={state}>{children}</ProductContext.Provider>
  );
}
// Context hooks intentionally share this module with their provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useProduct() {
  const value = useContext(ProductContext);
  if (!value) throw new Error("ProductProvider is required");
  return value;
}
