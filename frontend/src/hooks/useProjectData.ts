import { useCallback, useEffect, useState } from "react";

import { api, errorMessage } from "../api/client";
import type { Dataset, Project, Snapshot } from "../types/api";

export function useProjectData(projectId: string) {
  const [project, setProject] = useState<Project | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    if (!projectId) return;
    try {
      const [projectData, snapshotData, datasetData] = await Promise.all([
        api<Project>(`/projects/${projectId}`),
        api<Snapshot[]>(`/projects/${projectId}/snapshots`),
        api<Dataset[]>(`/projects/${projectId}/datasets`),
      ]);
      setProject(projectData);
      setSnapshots(snapshotData);
      setDatasets(datasetData);
      setError("");
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }, [projectId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { project, snapshots, datasets, error, reload };
}

