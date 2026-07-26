import { ArrowDown, ArrowUp, GitCompare, Minus } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, errorMessage } from "../api/client";
import { ProjectNav } from "../components/common/ProjectNav";
import { StatusMessage } from "../components/common/StatusMessage";
import { useProjectData } from "../hooks/useProjectData";
import type { Comparison } from "../types/api";

type ComparisonItems = {
  comparison_id: string;
  category: string;
  items: Array<Record<string, unknown>>;
  total: number;
};

export function ComparisonPage() {
  const { projectId = "" } = useParams<{ projectId: string }>();
  const { project, snapshots } = useProjectData(projectId);
  const [before, setBefore] = useState("");
  const [after, setAfter] = useState("");
  const [comparisons, setComparisons] = useState<Comparison[]>([]);
  const [selected, setSelected] = useState<Comparison | null>(null);
  const [category, setCategory] = useState("relationships");
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [message, setMessage] = useState("");

  const loadComparisons = useCallback(async () => {
    try {
      const data = await api<Comparison[]>(`/projects/${projectId}/comparisons`);
      setComparisons(data);
      setSelected((current) => current ?? data[0] ?? null);
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }, [projectId]);

  useEffect(() => {
    void loadComparisons();
  }, [loadComparisons]);
  useEffect(() => {
    setBefore((current) => current || snapshots.at(-1)?.id || "");
    setAfter((current) => current || snapshots[0]?.id || "");
  }, [snapshots]);
  useEffect(() => {
    if (!selected) return setItems([]);
    api<ComparisonItems>(`/comparisons/${selected.id}/${category}?page_size=100`)
      .then((data) => setItems(data.items))
      .catch((reason) => setMessage(errorMessage(reason)));
  }, [category, selected]);

  async function compare(event: FormEvent) {
    event.preventDefault();
    try {
      const result = await api<Comparison>(`/projects/${projectId}/comparisons`, {
        method: "POST",
        json: { before_snapshot_id: before, after_snapshot_id: after },
      });
      setSelected(result);
      setMessage("Stored snapshot comparison created.");
      await loadComparisons();
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  const riskDelta = selected ? selected.risk_score_after - selected.risk_score_before : 0;
  return (
    <div className="page">
      <div className="page-heading"><div><p className="eyebrow">Snapshot comparison</p><h1>{project?.name ?? "Project"} change analysis</h1><p>Stable external identities reveal added, removed, and changed exposure without rewriting history.</p></div><GitCompare size={34} /></div>
      <ProjectNav projectId={projectId} snapshotId={snapshots[0]?.id} />
      <StatusMessage message={message} tone={message.includes("created") ? "success" : "info"} />
      <section className="panel">
        <form className="comparison-form" onSubmit={(event) => void compare(event)}>
          <label>Before<select value={before} onChange={(event) => setBefore(event.target.value)}>{snapshots.map((snapshot) => <option key={snapshot.id} value={snapshot.id}>{snapshot.name} · v{snapshot.version}</option>)}</select></label>
          <span aria-hidden="true">→</span>
          <label>After<select value={after} onChange={(event) => setAfter(event.target.value)}>{snapshots.map((snapshot) => <option key={snapshot.id} value={snapshot.id}>{snapshot.name} · v{snapshot.version}</option>)}</select></label>
          <button className="primary-button" disabled={!before || !after || before === after}>Compare snapshots</button>
        </form>
      </section>
      {comparisons.length > 0 && <label className="history-select">Stored comparison<select value={selected?.id ?? ""} onChange={(event) => setSelected(comparisons.find((item) => item.id === event.target.value) ?? null)}>{comparisons.map((comparison) => <option value={comparison.id} key={comparison.id}>{comparison.before_snapshot_id.slice(0, 8)} → {comparison.after_snapshot_id.slice(0, 8)}</option>)}</select></label>}
      {selected && <>
        <div className="metric-grid comparison-metrics">
          <Metric label="Nodes" added={selected.nodes_added} removed={selected.nodes_removed} changed={selected.nodes_changed} />
          <Metric label="Relationships" added={selected.relationships_added} removed={selected.relationships_removed} changed={selected.relationships_changed} />
          <article className="metric-card"><span>Modeled risk total</span><strong>{selected.risk_score_before.toFixed(0)} → {selected.risk_score_after.toFixed(0)}</strong><span className={riskDelta > 0 ? "regression" : "improvement"}>{riskDelta > 0 ? <ArrowUp /> : riskDelta < 0 ? <ArrowDown /> : <Minus />}{riskDelta > 0 ? "Regression" : riskDelta < 0 ? "Reduced" : "Unchanged"}</span></article>
        </div>
        {riskDelta > 0 && <div className="notice notice-danger"><ArrowUp />Regression warning: deterministic finding scores increased in the later snapshot.</div>}
        <section className="panel">
          <div className="tab-list" role="tablist" aria-label="Comparison categories">{["nodes", "relationships", "paths", "findings", "severity"].map((item) => <button role="tab" aria-selected={category === item} className={category === item ? "active" : ""} onClick={() => setCategory(item)} key={item}>{item}</button>)}</div>
          <div className="diff-list">{items.map((item, index) => <article key={`${String(item.external_id ?? item.identity ?? item.signature)}-${index}`} className={`diff-item ${String(item.change ?? "changed")}`}><span>{String(item.change ?? "severity change")}</span><strong>{String(item.external_id ?? item.identity ?? item.signature ?? "Stored difference")}</strong>{item.relationship_type ? <small>{String(item.relationship_type)}</small> : null}{item.fields ? <pre>{JSON.stringify(item.fields, null, 2)}</pre> : null}</article>)}</div>
          {!items.length && <p className="empty-state">No stored {category} differences.</p>}
        </section>
      </>}
    </div>
  );
}

function Metric({ label, added, removed, changed }: { label: string; added: number; removed: number; changed: number }) {
  return <article className="metric-card"><span>{label}</span><strong>{added + removed + changed}</strong><span className="metric-small">+{added} / −{removed} / Δ{changed}</span></article>;
}
