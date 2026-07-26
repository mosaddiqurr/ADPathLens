import { CheckCircle2, FileArchive, RotateCcw, UploadCloud } from "lucide-react";
import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, errorMessage } from "../api/client";
import { ProjectNav } from "../components/common/ProjectNav";
import { StatusMessage } from "../components/common/StatusMessage";
import { useProjectData } from "../hooks/useProjectData";
import type { Snapshot } from "../types/api";

type Validation = {
  valid: boolean;
  digest: string;
  node_count: number;
  relationship_count: number;
  messages: Array<{ level: string; code: string; message: string; location: string }>;
};

export function ImportPage() {
  const { projectId = "" } = useParams<{ projectId: string }>();
  const { project, snapshots, datasets, error, reload } = useProjectData(projectId);
  const [demo, setDemo] = useState("small");
  const [authorized, setAuthorized] = useState(false);
  const [sourceMode, setSourceMode] = useState<"json" | "csv" | "zip">("json");
  const [file, setFile] = useState<File | null>(null);
  const [relationshipsFile, setRelationshipsFile] = useState<File | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [acknowledged, setAcknowledged] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function importDemo(event: FormEvent) {
    event.preventDefault();
    if (!authorized) return setMessage("Confirm authorized use before importing.");
    setBusy(true);
    try {
      const snapshot = await api<Snapshot>(`/projects/${projectId}/datasets/import-demo`, {
        method: "POST",
        json: { demo, authorization_confirmed: true },
      });
      setMessage(`Imported ${snapshot.name}.`);
      await reload();
    } catch (reason) {
      setMessage(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function validateFile() {
    if (!file) return;
    setBusy(true);
    const form = new FormData();
    if (sourceMode === "json") form.append("file", file);
    else if (sourceMode === "zip") form.append("zip_file", file);
    else {
      form.append("nodes_file", file);
      if (relationshipsFile) form.append("relationships_file", relationshipsFile);
    }
    try {
      const endpoint = sourceMode === "json" ? "validate-json" : "validate-csv";
      const result = await api<Validation>(`/projects/${projectId}/datasets/${endpoint}`, {
        method: "POST",
        body: form,
      });
      setValidation(result);
      setAcknowledged([]);
      setMessage(result.valid ? "Validation completed." : "Validation found blocking errors.");
    } catch (reason) {
      setMessage(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function importFile() {
    if (!file || !validation || !authorized) return;
    const form = new FormData();
    if (sourceMode === "json") form.append("file", file);
    else if (sourceMode === "zip") form.append("zip_file", file);
    else {
      form.append("nodes_file", file);
      if (relationshipsFile) form.append("relationships_file", relationshipsFile);
    }
    form.append("validation_digest", validation.digest);
    form.append("authorization_confirmed", "true");
    form.append("acknowledged_warnings", acknowledged.join(","));
    form.append("name", file.name);
    setBusy(true);
    try {
      const endpoint = sourceMode === "json" ? "import-json" : "import-csv";
      const snapshot = await api<Snapshot>(`/projects/${projectId}/datasets/${endpoint}`, {
        method: "POST",
        body: form,
      });
      setMessage(`Imported ${snapshot.name}.`);
      setFile(null);
      setRelationshipsFile(null);
      setValidation(null);
      await reload();
    } catch (reason) {
      setMessage(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function deleteDataset(datasetId: string) {
    if (!window.confirm("Delete this dataset, its snapshots, and derived analytical records?")) return;
    try {
      await api<void>(`/datasets/${datasetId}`, { method: "DELETE" });
      setMessage("Dataset deleted. The demo can now be imported again.");
      await reload();
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  async function cancelDataset(datasetId: string) {
    try {
      await api(`/datasets/${datasetId}/cancel`, { method: "POST" });
      setMessage("Import cancellation requested.");
      await reload();
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  const warningCodes = validation?.messages.filter((item) => item.level === "warning").map((item) => item.code) ?? [];
  const allWarningsAcknowledged = warningCodes.every((code) => acknowledged.includes(code));
  return (
    <div className="page">
      <div className="page-heading"><div><p className="eyebrow">Secure import</p><h1>{project?.name ?? "Project"} data</h1><p>Source files are validated, normalized transactionally, and never retained.</p></div><UploadCloud size={32} /></div>
      <ProjectNav projectId={projectId} snapshotId={snapshots[0]?.id} />
      <StatusMessage message={error || message} tone={message.includes("Imported") ? "success" : "info"} />
      <label className="authorization-box"><input type="checkbox" checked={authorized} onChange={(event) => setAuthorized(event.target.checked)} /><span><strong>Authorized-use confirmation</strong> I am using synthetic data or information from systems I own or am explicitly authorized to assess.</span></label>
      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><h2>Fictional lab</h2><CheckCircle2 /></div>
          <form onSubmit={(event) => void importDemo(event)} className="form-stack">
            <label>Dataset<select value={demo} onChange={(event) => setDemo(event.target.value)}>
              <option value="small">NORTHBRIDGE small · guided journey</option>
              <option value="medium">NORTHBRIDGE medium · performance lab</option>
              <option value="before">Before remediation</option>
              <option value="after">After remediation</option>
            </select></label>
            <button className="primary-button" disabled={!authorized || busy}>{busy ? "Working…" : "Import demo snapshot"}</button>
          </form>
        </section>
        <section className="panel">
          <div className="panel-heading"><h2>Authorized files</h2><FileArchive /></div>
          <div className="form-stack">
            <fieldset><legend>Format</legend><div className="format-grid">
              {(["json", "csv", "zip"] as const).map((mode) => <label className={sourceMode === mode ? "selected" : ""} key={mode}><input type="radio" name="source-mode" checked={sourceMode === mode} onChange={() => { setSourceMode(mode); setFile(null); setRelationshipsFile(null); setValidation(null); }} />{mode.toUpperCase()}</label>)}
            </div></fieldset>
            <label>{sourceMode === "csv" ? "nodes.csv" : sourceMode === "zip" ? "Root-level CSV ZIP" : "JSON dataset"}<input type="file" accept={sourceMode === "json" ? ".json,application/json" : sourceMode === "zip" ? ".zip,application/zip" : ".csv,text/csv"} onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
            {sourceMode === "csv" && <label>relationships.csv<input type="file" accept=".csv,text/csv" onChange={(event) => setRelationshipsFile(event.target.files?.[0] ?? null)} /></label>}
            <button className="secondary-button" type="button" disabled={!file || (sourceMode === "csv" && !relationshipsFile) || busy} onClick={() => void validateFile()}>Validate before import</button>
            {validation && (
              <div className="validation-results">
                <strong>{validation.valid ? "Structurally valid" : "Blocked"} · {validation.node_count} nodes · {validation.relationship_count} relationships</strong>
                {validation.messages.map((item, index) => (
                  <div className={`validation-item ${item.level}`} key={`${item.code}-${index}`}>
                    <span>{item.level}</span><div><strong>{item.code}</strong><p>{item.message}</p><small>{item.location}</small></div>
                    {item.level === "warning" && <label><input type="checkbox" checked={acknowledged.includes(item.code)} onChange={(event) => setAcknowledged((current) => event.target.checked ? [...new Set([...current, item.code])] : current.filter((code) => code !== item.code))} />Acknowledge</label>}
                  </div>
                ))}
                <button className="primary-button" type="button" disabled={!authorized || !validation.valid || !allWarningsAcknowledged || busy} onClick={() => void importFile()}>Import atomically</button>
              </div>
            )}
          </div>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading"><h2>Import history</h2><span>{datasets.length} datasets</span></div>
        <div className="table-wrap"><table><thead><tr><th>Name</th><th>Source</th><th>Status</th><th>Progress</th><th>Records</th><th>Action</th></tr></thead><tbody>
          {datasets.map((dataset) => <tr key={dataset.id}><td>{dataset.name}</td><td>{dataset.source_type}</td><td><span className="status-chip">{dataset.import_status}</span></td><td><progress max="100" value={dataset.progress_percent}>{dataset.progress_percent}%</progress></td><td>{dataset.node_count} / {dataset.relationship_count}</td><td>{["validating", "importing"].includes(dataset.import_status) ? <button className="danger-link" onClick={() => void cancelDataset(dataset.id)}>Cancel</button> : <button className="danger-link" onClick={() => void deleteDataset(dataset.id)}><RotateCcw size={15} />Reset</button>}</td></tr>)}
        </tbody></table></div>
        {snapshots[0] && <Link className="text-link" to={`/snapshots/${snapshots[0].id}/graph`}>Open latest graph →</Link>}
      </section>
    </div>
  );
}
