import { Download, FileJson, FileText, ShieldCheck } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, errorMessage } from "../api/client";
import { ProjectNav } from "../components/common/ProjectNav";
import { StatusMessage } from "../components/common/StatusMessage";
import { useProjectData } from "../hooks/useProjectData";
import type { Report } from "../types/api";

export function ReportsPage() {
  const { projectId = "" } = useParams<{ projectId: string }>();
  const { project, snapshots } = useProjectData(projectId);
  const [reports, setReports] = useState<Report[]>([]);
  const [snapshotId, setSnapshotId] = useState("");
  const [format, setFormat] = useState("html");
  const [reportType, setReportType] = useState("findings");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      setReports(await api<Report[]>(`/projects/${projectId}/reports`));
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }, [projectId]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setSnapshotId((current) => current || snapshots[0]?.id || ""); }, [snapshots]);

  async function generate(event: FormEvent) {
    event.preventDefault();
    try {
      const report = await api<Report>(`/projects/${projectId}/reports`, {
        method: "POST",
        json: { snapshot_id: snapshotId, report_type: reportType, format },
      });
      setMessage(`Generated ${report.file_name}.`);
      await load();
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  return (
    <div className="page">
      <div className="page-heading"><div><p className="eyebrow">Sanitized exports</p><h1>{project?.name ?? "Project"} reports</h1><p>Every report records its source, content version, SHA-256 hash, and generating user.</p></div><FileText size={34} /></div>
      <ProjectNav projectId={projectId} snapshotId={snapshots[0]?.id} />
      <StatusMessage message={message} tone={message.startsWith("Generated") ? "success" : "info"} />
      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><h2>Generate report</h2><FileJson /></div>
          <form className="form-stack" onSubmit={(event) => void generate(event)}>
            <label>Snapshot<select value={snapshotId} onChange={(event) => setSnapshotId(event.target.value)}>{snapshots.map((snapshot) => <option key={snapshot.id} value={snapshot.id}>{snapshot.name} · v{snapshot.version}</option>)}</select></label>
            <label>Content<select value={reportType} onChange={(event) => setReportType(event.target.value)}><option value="findings">Detailed findings</option><option value="executive">Executive review</option></select></label>
            <fieldset><legend>Format</legend><div className="format-grid">{["html", "pdf", "json", "csv"].map((item) => <label className={format === item ? "selected" : ""} key={item}><input type="radio" name="format" value={item} checked={format === item} onChange={() => setFormat(item)} />{item.toUpperCase()}</label>)}</div></fieldset>
            <button className="primary-button" disabled={!snapshotId}>Generate sanitized report</button>
          </form>
        </section>
        <section className="panel callout-panel"><ShieldCheck /><h2>Export safety</h2><ul><li>HTML values are autoescaped.</li><li>PDF is built from structured text.</li><li>CSV formula prefixes are neutralized.</li><li>Downloads are checked against project ownership.</li><li>Generated filenames never reuse imported names.</li></ul></section>
      </div>
      <section className="panel">
        <div className="panel-heading"><h2>Report history</h2><span>{reports.length} generated</span></div>
        <div className="table-wrap"><table><thead><tr><th>File</th><th>Format</th><th>Status</th><th>SHA-256</th><th>Size</th><th>Download</th></tr></thead><tbody>{reports.map((report) => <tr key={report.id}><td>{report.file_name}<small>{new Date(report.generated_at).toLocaleString()}</small></td><td>{report.format.toUpperCase()}</td><td><span className="status-chip">{report.status}</span></td><td><code title={report.file_hash}>{report.file_hash.slice(0, 12)}…</code></td><td>{Math.ceil(report.size_bytes / 1024)} KiB</td><td><a className="text-link" href={`/api/v1/reports/${report.id}/download`}><Download size={15} />Download</a></td></tr>)}</tbody></table></div>
      </section>
    </div>
  );
}
