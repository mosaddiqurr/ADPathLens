import { CheckCircle2, MessageSquarePlus, ShieldAlert, Wrench } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, errorMessage } from "../api/client";
import { ProjectNav } from "../components/common/ProjectNav";
import { StatusMessage } from "../components/common/StatusMessage";
import type { Finding } from "../types/api";

type Note = { id: string; body: string; created_by: string; created_at: string };
type History = { id: string; previous_status: string | null; new_status: string; note: string; changed_at: string };

export function FindingDetailPage() {
  const { findingId = "" } = useParams<{ findingId: string }>();
  const [finding, setFinding] = useState<Finding | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [history, setHistory] = useState<History[]>([]);
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("confirmed");
  const [statusNote, setStatusNote] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const [findingData, noteData, historyData] = await Promise.all([
        api<Finding>(`/findings/${findingId}`),
        api<Note[]>(`/findings/${findingId}/notes`),
        api<History[]>(`/findings/${findingId}/history`),
      ]);
      setFinding(findingData);
      setNotes(noteData);
      setHistory(historyData);
      setStatus(findingData.status);
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }, [findingId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function addNote(event: FormEvent) {
    event.preventDefault();
    try {
      await api<Note>(`/findings/${findingId}/notes`, { method: "POST", json: { body: note } });
      setNote("");
      setMessage("Analyst note added.");
      await load();
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  async function updateStatus(event: FormEvent) {
    event.preventDefault();
    try {
      const updated = await api<Finding>(`/findings/${findingId}`, {
        method: "PATCH",
        json: { status, status_note: statusNote, reviewer_notes: statusNote },
      });
      setFinding(updated);
      setStatusNote("");
      setMessage("Review decision recorded.");
      await load();
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  if (!finding) return <div className="page"><StatusMessage message={message || "Loading finding…"} /></div>;
  return (
    <div className="page">
      <div className="page-heading"><div><p className="eyebrow">Finding review</p><h1>{finding.title}</h1><div className="finding-lead"><span className={`severity severity-${finding.severity}`}>{finding.severity}</span><span>{finding.confidence} confidence</span><span className="status-chip">{finding.status}</span></div></div><ShieldAlert size={36} /></div>
      <ProjectNav projectId={finding.project_id} snapshotId={finding.snapshot_id} />
      <StatusMessage message={message} tone={message.includes("recorded") || message.includes("added") ? "success" : "info"} />
      <div className="detail-grid">
        <article className="panel prose-panel">
          <h2>Why this matters</h2><p>{finding.description}</p>
          <h3>Technical explanation</h3><p>{finding.technical_explanation || finding.impact}</p>
          <h3>Potential impact</h3><p>{finding.impact}</p>
          <h3>Evidence</h3><pre>{JSON.stringify(finding.evidence, null, 2)}</pre>
          <div className="signal-grid"><div><h3>Contributing signals</h3><ul>{finding.contributing_signals.map((item) => <li key={item}>{item}</li>)}</ul></div><div><h3>Reducing signals</h3><ul>{finding.reducing_signals.map((item) => <li key={item}>{item}</li>)}</ul></div></div>
          <h3>Limitations</h3><p className="limitation">{finding.limitations}</p>
        </article>
        <aside className="stack">
          <section className="panel remediation-card"><Wrench /><h2>Recommended remediation</h2><p>{finding.remediation}</p><ol>{finding.validation_steps.map((step) => <li key={step}>{step}</li>)}</ol><Link className="primary-button inline-button" to={`/projects/${finding.project_id}/remediation?finding=${finding.id}`}>Plan simulated change</Link></section>
          <section className="panel">
            <h2>Record review decision</h2>
            <form className="form-stack" onSubmit={(event) => void updateStatus(event)}>
              <label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}>{["draft", "open", "confirmed", "acknowledged", "mitigated", "accepted_risk", "false_positive", "planned_remediation", "resolved", "retest_required", "closed"].map((item) => <option key={item}>{item}</option>)}</select></label>
              <label>Review note<textarea value={statusNote} onChange={(event) => setStatusNote(event.target.value)} rows={3} /></label>
              <button className="secondary-button"><CheckCircle2 size={16} />Save decision</button>
            </form>
          </section>
        </aside>
      </div>
      <div className="two-column">
        <section className="panel"><h2>Analyst notes</h2><form className="form-stack" onSubmit={(event) => void addNote(event)}><label>New note<textarea value={note} onChange={(event) => setNote(event.target.value)} required rows={3} /></label><button className="secondary-button"><MessageSquarePlus size={16} />Add note</button></form>{notes.map((item) => <article className="note" key={item.id}><p>{item.body}</p><small>{new Date(item.created_at).toLocaleString()}</small></article>)}</section>
        <section className="panel"><h2>Status history</h2><ol className="timeline">{history.map((item) => <li key={item.id}><strong>{item.new_status}</strong><p>{item.note || "No note supplied."}</p><small>{new Date(item.changed_at).toLocaleString()}</small></li>)}</ol></section>
      </div>
    </div>
  );
}
