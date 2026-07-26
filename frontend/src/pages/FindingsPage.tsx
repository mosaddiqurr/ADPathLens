import { Filter, Search, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, errorMessage } from "../api/client";
import { ProjectNav } from "../components/common/ProjectNav";
import { StatusMessage } from "../components/common/StatusMessage";
import { useProjectData } from "../hooks/useProjectData";
import type { Finding, Page } from "../types/api";

export function FindingsPage() {
  const { projectId = "" } = useParams<{ projectId: string }>();
  const { project, snapshots } = useProjectData(projectId);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    const query = new URLSearchParams({ page_size: "100", search, severity, status });
    try {
      const response = await api<Page<Finding>>(`/projects/${projectId}/findings?${query}`);
      setFindings(response.items);
      setTotal(response.total);
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }, [projectId, search, severity, status]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runScan() {
    const snapshot = snapshots[0];
    if (!snapshot) return setMessage("Import a snapshot before running a risk scan.");
    try {
      const summary = await api<{ total: number }>(`/snapshots/${snapshot.id}/risk-scan`, { method: "POST" });
      setMessage(`Created ${summary.total} draft findings for human review.`);
      await load();
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  return (
    <div className="page">
      <div className="page-heading"><div><p className="eyebrow">Human-reviewed findings</p><h1>{project?.name ?? "Project"} findings</h1><p>Severity and confidence lead; deterministic scores remain secondary evidence.</p></div><button className="primary-button inline-button" onClick={() => void runScan()}><ShieldAlert size={17} />Run scan</button></div>
      <ProjectNav projectId={projectId} snapshotId={snapshots[0]?.id} />
      <StatusMessage message={message} tone={message.startsWith("Created") ? "success" : "info"} />
      <div className="filter-bar">
        <label className="search-control"><Search size={16} /><span className="sr-only">Search findings</span><input placeholder="Search title or description" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
        <label><Filter size={15} />Severity<select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="">All</option>{["informational", "low", "medium", "high", "critical"].map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All</option>{["draft", "open", "confirmed", "false_positive", "planned_remediation", "resolved", "retest_required", "closed"].map((item) => <option key={item}>{item}</option>)}</select></label>
        <span>{total} results</span>
      </div>
      <section className="panel">
        <div className="table-wrap"><table><thead><tr><th>Finding</th><th>Severity</th><th>Confidence</th><th>Status</th><th>Priority</th><th>Action</th></tr></thead><tbody>
          {findings.map((finding) => <tr key={finding.id}><td><strong>{finding.title}</strong><small>{finding.category}</small></td><td><span className={`severity severity-${finding.severity}`}>{finding.severity}</span></td><td>{finding.confidence}</td><td><span className="status-chip">{finding.status}</span></td><td>{finding.priority}</td><td><Link className="text-link" to={`/findings/${finding.id}`}>Review evidence</Link></td></tr>)}
        </tbody></table></div>
        {!findings.length && <div className="empty-state"><ShieldAlert /><p>No findings match these filters.</p></div>}
      </section>
    </div>
  );
}
