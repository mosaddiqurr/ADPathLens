import { CheckCircle2, Circle, Network, Play, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, errorMessage } from "../api/client";
import { StatusMessage } from "../components/common/StatusMessage";
import type { Dataset, Project, Snapshot, Workspace } from "../types/api";

export function DemoPage() {
  const [project, setProject] = useState<Project | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const projects = await api<Project[]>("/projects");
      const demoProject = projects.find((item) => item.name === "NORTHBRIDGE Guided Lab") ?? null;
      setProject(demoProject);
      if (demoProject) {
        const [snapshotData, datasetData] = await Promise.all([
          api<Snapshot[]>(`/projects/${demoProject.id}/snapshots`),
          api<Dataset[]>(`/projects/${demoProject.id}/datasets`),
        ]);
        setSnapshots(snapshotData); setDatasets(datasetData);
      } else { setSnapshots([]); setDatasets([]); }
    } catch (reason) { setMessage(errorMessage(reason)); }
  }
  useEffect(() => { void load(); }, []);

  async function startDemo() {
    setBusy(true);
    try {
      let activeProject = project;
      if (!activeProject) {
        let workspaces = await api<Workspace[]>("/workspaces");
        if (!workspaces.length) {
          workspaces = [await api<Workspace>("/workspaces", { method: "POST", json: { name: "NORTHBRIDGE Lab", description: "Fictional guided demo workspace" } })];
        }
        activeProject = await api<Project>("/projects", { method: "POST", json: { workspace_id: workspaces[0].id, name: "NORTHBRIDGE Guided Lab", description: "Entirely fictional defensive AD graph lab" } });
        setProject(activeProject);
      }
      if (!datasets.length) {
        await api<Snapshot>(`/projects/${activeProject.id}/datasets/import-demo`, { method: "POST", json: { demo: "small", authorization_confirmed: true } });
      }
      setMessage("The fictional NORTHBRIDGE lab is ready.");
      await load();
    } catch (reason) { setMessage(errorMessage(reason)); } finally { setBusy(false); }
  }

  async function resetDemo() {
    if (!project || !window.confirm("Reset the fictional demo and delete its analytical history?")) return;
    setBusy(true);
    try {
      for (const dataset of datasets) await api<void>(`/datasets/${dataset.id}`, { method: "DELETE" });
      await api<Snapshot>(`/projects/${project.id}/datasets/import-demo`, { method: "POST", json: { demo: "small", authorization_confirmed: true } });
      setMessage("Demo reset to the deterministic fictional starting snapshot.");
      await load();
    } catch (reason) { setMessage(errorMessage(reason)); } finally { setBusy(false); }
  }

  const snapshot = snapshots[0];
  const steps = [
    ["Create isolated project", Boolean(project)],
    ["Import NORTHBRIDGE synthetic data", Boolean(snapshot)],
    ["Inspect the bounded graph", false],
    ["Trace Mina Rahman to Domain Admins", false],
    ["Review and confirm a deterministic finding", false],
    ["Simulate remediation and create a derived snapshot", snapshots.some((item) => item.snapshot_type === "derived")],
    ["Compare exposure and export a sanitized report", false],
  ] as const;
  return <div className="page"><div className="page-heading"><div><p className="eyebrow">Guided fictional lab</p><h1>NORTHBRIDGE.LOCAL</h1><p>A deterministic, resettable journey through a modeled privilege path and defensive remediation.</p></div><Network size={38} /></div><StatusMessage message={message} tone={message.includes("ready") || message.includes("reset") ? "success" : "info"} /><div className="demo-hero"><div><span className="authorized-pill">100% fictional</span><h2>Mina Rahman → Domain Admins</h2><p>Follow stored group membership, reset rights, server administration, and session evidence. Every hop resolves to a persisted relationship ID.</p><div className="button-row"><button className="primary-button inline-button" onClick={() => void startDemo()} disabled={busy}><Play size={17} />{snapshot ? "Resume demo" : "Start demo"}</button>{snapshot && <button className="secondary-button inline-button" onClick={() => void resetDemo()} disabled={busy}><RotateCcw size={17} />Reset demo</button>}</div></div><ol className="demo-steps">{steps.map(([label, complete], index) => <li key={label}>{complete ? <CheckCircle2 /> : <Circle />}<span><small>Step {index + 1}</small><strong>{label}</strong></span></li>)}</ol></div>{project && snapshot && <div className="journey-links"><Link to={`/projects/${project.id}`}>Project overview</Link><Link to={`/snapshots/${snapshot.id}/graph`}>Inspect graph</Link><Link to={`/snapshots/${snapshot.id}/paths`}>Run Mina path</Link><Link to={`/projects/${project.id}/findings`}>Review findings</Link><Link to={`/projects/${project.id}/remediation`}>Simulate remediation</Link><Link to={`/projects/${project.id}/comparisons`}>Compare snapshots</Link><Link to={`/projects/${project.id}/reports`}>Export report</Link></div>}</div>;
}

