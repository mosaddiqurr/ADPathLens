import { ArrowDownLeft, ArrowUpRight, CheckCircle2, ChevronDown, Download } from "lucide-react";
import { useState } from "react";

import type { ComparisonResult, ExportFormat } from "../types";

const filters = ["All", "Gained", "Lost", "Risky", "Review"] as const;
const PAGE_SIZE = 50;

export function Results({ result, exporting, onExport }: {
  result: ComparisonResult;
  exporting: ExportFormat | null;
  onExport: (format: ExportFormat) => void;
}) {
  const [filter, setFilter] = useState<(typeof filters)[number]>("All");
  const [page, setPage] = useState(0);
  const changes = result.changes.filter(change =>
    filter === "All" || (filter === "Risky" ? change.severity !== "info" :
      filter === "Review" ? change.change === "changed" : change.change === filter.toLowerCase()));
  const lastPage = Math.max(0, Math.ceil(changes.length / PAGE_SIZE) - 1);
  const currentPage = Math.min(page, lastPage);
  const visible = changes.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

  return (
    <section className="results" aria-labelledby="results-heading">
      <div className="results-title">
        <div><p className="eyebrow">Comparison complete</p>
          <h2 id="results-heading" tabIndex={-1}>{result.summary.total} authorization {result.summary.total === 1 ? "change" : "changes"}</h2></div>
        <div className="report-actions" aria-label="Report exports">
          <button className="button secondary" disabled={exporting !== null} onClick={() => { onExport("pdf"); }}>
            <Download size={15} aria-hidden="true" />{exporting === "pdf" ? "Generating…" : "Export PDF"}</button>
          <button className="button text-button" disabled={exporting !== null} onClick={() => { onExport("json"); }}>
            {exporting === "json" ? "Generating…" : "Export JSON"}</button>
        </div>
      </div>
      <dl className="summary-bar" aria-label="Change summary">
        <div><dt><ArrowUpRight size={16} aria-hidden="true" /> Gained</dt><dd>{result.summary.gained}</dd></div>
        <div><dt><ArrowDownLeft size={16} aria-hidden="true" /> Lost</dt><dd>{result.summary.lost}</dd></div>
        <div><dt>Risky</dt><dd className={result.summary.risky ? "risk-number" : ""}>{result.summary.risky}</dd></div>
      </dl>
      {result.summary.total === 0 ? (
        <div className="no-changes"><CheckCircle2 size={28} aria-hidden="true" /><h3>No authorization changes found</h3>
          <p>The comparable evidence is unchanged.</p></div>
      ) : (
        <>
          <div className="change-toolbar"><div className="filter-buttons" aria-label="Filter changes">
            {filters.map(value => <button key={value} aria-pressed={filter === value} onClick={() => { setFilter(value); setPage(0); }}>{value}</button>)}
          </div><span className="subtle">{changes.length} {changes.length === 1 ? "change" : "changes"}</span></div>
          <div className="change-list">
            {visible.map((change, index) => (
              <details className="change-row" key={`${change.principal}-${change.resource}-${change.action}-${String(index)}`}>
                <summary>
                  <div className="change-who"><strong>{change.principal}</strong><span>{change.action} · {change.resource}</span></div>
                  <span className="state-transition">{change.before}<span aria-label="to">→</span>{change.after}</span>
                  <span className={`change-badge ${change.change}`}>{change.change === "changed" ? "Review" : change.change}</span>
                  <span className={`severity ${change.severity}`}>{change.severity}</span>
                  <ChevronDown className="disclosure-icon" size={17} aria-hidden="true" />
                </summary>
                <div className="change-details">
                  <p className="change-description">{change.summary}</p>
                  <dl className="detail-grid">
                    <div><dt>Who</dt><dd>{change.principal}</dd></div>
                    <div><dt>Resource</dt><dd>{change.resource}</dd></div>
                    <div><dt>Before</dt><dd>{change.before}</dd></div>
                    <div><dt>After</dt><dd>{change.after}</dd></div>
                  </dl>
                  <h3>Why it matters</h3><p>{change.why}</p>
                  <details className="technical-evidence"><summary>Technical evidence</summary>
                    <pre tabIndex={0} role="region" aria-label="Redacted technical evidence">{JSON.stringify(change.evidence, null, 2)}</pre></details>
                </div>
              </details>
            ))}
          </div>
          {changes.length === 0 && <p className="filtered-empty">No changes match this filter.</p>}
          {lastPage > 0 && <div className="pagination">
            <button className="button secondary" disabled={currentPage === 0} onClick={() => { setPage(currentPage - 1); }}>Previous</button>
            <span>Page {currentPage + 1} of {lastPage + 1}</span>
            <button className="button secondary" disabled={currentPage === lastPage} onClick={() => { setPage(currentPage + 1); }}>Next</button>
          </div>}
        </>
      )}
      {result.notes.length > 0 && <p className="context-note" role="status">Some capture evidence needs contextual review. See comparison notes.</p>}
      <details className="comparison-notes"><summary>Comparison notes &amp; limitations</summary>
        <p>Risky changes may also appear in Gained or Lost. {result.summary.unchanged} records are unchanged.</p>
        {result.notes.map(note => <p key={note}>{note}</p>)}
        <ul>{result.limitations.map(note => <li key={note}>{note}</li>)}</ul>
        <button className="button text-button" disabled={exporting !== null} onClick={() => { onExport("csv"); }}>
          {exporting === "csv" ? "Generating…" : "Export CSV changes"}</button>
      </details>
    </section>
  );
}
