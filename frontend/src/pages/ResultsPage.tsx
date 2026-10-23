import { apiUrl } from "../api/url";
import {
  ArrowRight,
  ChevronDown,
  Download,
  FileSearch,
  Filter,
  GitBranch,
  ScanSearch,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useHistory, useLocation } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { StatusMessage } from "../components/common/StatusMessage";
import { useProduct } from "../features/product/ProductContext";
import { FocusedPathGraph } from "../features/product/FocusedPathGraph";
import { pathSeverity } from "../features/product/analysis";
import type { PathResult, Report } from "../types/api";
import { EmptyEnvironment, PageHeading } from "./ProductPages";

function relationshipLabel(type: string) {
  return type
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace("DACL", "permissions");
}

export function ResultsPage() {
  const p = useProduct();
  const history = useHistory();
  const location = useLocation();
  const [severity, setSeverity] = useState("");
  const [entity, setEntity] = useState("");
  const [relationship, setRelationship] = useState("");
  const [search, setSearch] = useState("");
  const [format, setFormat] = useState("pdf");
  const [report, setReport] = useState<Report | null>(null);
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState("");
  const currentAnalysis = useRef(p.analysis?.id);
  const selectedId = new URLSearchParams(location.search).get("path");
  const paths = useMemo(
    () =>
      [...(p.analysis?.paths ?? [])].sort(
        (a, b) =>
          b.risk_score - a.risk_score ||
          a.hop_count - b.hop_count ||
          a.id.localeCompare(b.id),
      ),
    [p.analysis],
  );
  const filtered = paths.filter(
    (path) =>
      (!severity || pathSeverity(path.risk_score) === severity) &&
      (!entity ||
        path.steps.some(
          (step) => step.source_type === entity || step.target_type === entity,
        )) &&
      (!relationship ||
        path.steps.some((step) => step.relationship_type === relationship)) &&
      (!search.trim() ||
        path.steps.some((step) =>
          `${step.source_name} ${step.target_name}`
            .toLowerCase()
            .includes(search.trim().toLowerCase()),
        )),
  );
  const selected =
    filtered.find((path) => path.id === selectedId) ?? filtered[0];
  const relationshipTypes = [
    ...new Set(
      paths.flatMap((path) => path.steps.map((step) => step.relationship_type)),
    ),
  ].sort();
  const priorityPaths = paths.filter((path) => path.risk_score >= 65).length;
  const target = paths[0]?.steps.at(-1)?.target_name ?? "Selected target";
  useEffect(() => {
    currentAnalysis.current = p.analysis?.id;
    setReport(null);
    setMessage("");
    setSeverity("");
    setEntity("");
    setRelationship("");
    setSearch("");
  }, [p.analysis?.id]);
  async function exportReport() {
    const analysisId = p.analysis?.id;
    setExporting(true);
    setMessage("");
    setReport(null);
    try {
      const result = await api<Report>(`/projects/${p.projectId}/reports`, {
        method: "POST",
        json: {
          snapshot_id: p.snapshotId,
          analysis_id: analysisId,
          report_type: "executive",
          format,
        },
      });
      if (analysisId === currentAnalysis.current) setReport(result);
    } catch (e) {
      setMessage(errorMessage(e));
    } finally {
      setExporting(false);
    }
  }
  function choose(path: PathResult) {
    history.replace(`/results?path=${encodeURIComponent(path.id)}`);
  }
  return (
    <div className="page results-page">
      <PageHeading
        label="Attack-path intelligence"
        title="Results"
        description={
          p.snapshot
            ? `${p.snapshot.name} · ${p.project?.name ?? "Directory data"}`
            : "Inspect risky routes, their supporting evidence, and the steps that break them."
        }
      >
        <div className="results-actions">
          <Link className="secondary-button" to="/analyze">
            <ScanSearch size={16} />
            New analysis
          </Link>
          {p.analysis && (
            <div className="export-control">
              <div className="report-format-field">
                <label className="sr-only" htmlFor="export-format">
                  Report format
                </label>
                <select
                  id="export-format"
                  value={format}
                  disabled={exporting}
                  onChange={(e) => {
                    setFormat(e.target.value);
                    setReport(null);
                  }}
                >
                  <option value="pdf">PDF</option>
                  <option value="json">JSON</option>
                </select>
                <ChevronDown size={14} aria-hidden="true" />
              </div>
              <button
                className="primary-button"
                disabled={exporting || !p.canEdit || p.loading}
                onClick={() => void exportReport()}
              >
                <Download size={16} />
                {exporting ? "Preparing…" : "Export report"}
              </button>
            </div>
          )}
        </div>
      </PageHeading>
      <StatusMessage message={p.error || message} tone="danger" />
      {report && (
        <div className="export-ready" role="status">
          <ShieldCheck size={17} />
          <span>Your {report.format.toUpperCase()} report is ready.</span>
          <a
            className="text-link"
            href={apiUrl(`/reports/${report.id}/download`)}
            download
          >
            Download {report.format.toUpperCase()} report
            <Download size={14} />
          </a>
        </div>
      )}
      {p.loading ? (
        <p className="loading-state" role="status">
          Loading analysis and evidence…
        </p>
      ) : !p.snapshot ? (
        <EmptyEnvironment />
      ) : !p.analysis ? (
        <section className="empty-environment">
          <ScanSearch size={28} />
          <h2>Your snapshot is ready to analyze</h2>
          <p>Choose a privileged target to discover possible routes to it.</p>
          <Link className="primary-button" to="/analyze">
            Run an analysis
            <ArrowRight size={16} />
          </Link>
        </section>
      ) : (
        <>
          <dl className="results-summary">
            <div>
              <dt>Returned attack paths</dt>
              <dd>{paths.length}</dd>
            </div>
            <div>
              <dt>Critical & high priority</dt>
              <dd className={priorityPaths ? "risk-count" : ""}>
                {priorityPaths}
              </dd>
            </div>
            <div>
              <dt>Privileged target</dt>
              <dd className="summary-asset">{target}</dd>
            </div>
            <div>
              <dt>Highest priority score</dt>
              <dd>
                {paths[0] ? Math.round(paths[0].risk_score) : "—"}
                <small>{paths[0] ? " / 100" : ""}</small>
              </dd>
            </div>
          </dl>
          <div
            className={`analysis-scope ${p.analysis.truncated ? "is-partial" : ""}`}
            role={p.analysis.truncated ? "status" : undefined}
          >
            <ShieldCheck size={16} />
            <p>
              <strong>
                {p.analysis.truncated ? "Partial results." : "Analysis scope."}
              </strong>{" "}
              {p.analysis.algorithm === "reverse_reachability"
                ? "One shortest route per reachable standard object"
                : "Routes from the selected identity"}{" "}
              · maximum {p.analysis.maximum_depth ?? 12} relationships ·{" "}
              {String(
                p.analysis.request_parameters?.minimum_confidence ?? "low",
              )}{" "}
              or higher confidence.{" "}
              {p.analysis.truncated
                ? "A return or work limit was reached; additional paths may exist."
                : "Possible paths require validation against the directory."}
            </p>
          </div>
          {!paths.length ? (
            <section className="empty-environment">
              <ShieldCheck size={28} />
              <h2>No eligible path found in this scope</h2>
              <p>
                Review your target, depth, and confidence limits. Missing routes
                do not establish that the directory is secure.
              </p>
              <Link className="secondary-button" to="/analyze">
                Review analysis scope
                <ArrowRight size={16} />
              </Link>
            </section>
          ) : (
            <>
              <section
                className="results-filters"
                aria-label="Filter attack paths"
              >
                <div className="filter-caption">
                  <Filter size={16} />
                  <strong>Filter paths</strong>
                </div>
                <label>
                  Entity name
                  <input
                    type="search"
                    placeholder="User, group, or computer"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
                <label>
                  Severity
                  <select
                    value={severity}
                    onChange={(e) => setSeverity(e.target.value)}
                  >
                    <option value="">All severities</option>
                    {["critical", "high", "medium", "low"].map((s) => (
                      <option value={s} key={s}>
                        {s[0].toUpperCase() + s.slice(1)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Entity type
                  <select
                    value={entity}
                    onChange={(e) => setEntity(e.target.value)}
                  >
                    <option value="">All entities</option>
                    {["User", "Group", "Computer", "ServiceAccount"].map(
                      (type) => (
                        <option key={type} value={type}>
                          {type.replace("Account", " account")}
                        </option>
                      ),
                    )}
                  </select>
                </label>
                <label>
                  Relationship type
                  <select
                    value={relationship}
                    onChange={(e) => setRelationship(e.target.value)}
                  >
                    <option value="">All relationships</option>
                    {relationshipTypes.map((type) => (
                      <option value={type} key={type}>
                        {relationshipLabel(type)}
                      </option>
                    ))}
                  </select>
                </label>
              </section>
              {!filtered.length ? (
                <section className="empty-environment filter-empty">
                  <FileSearch size={27} />
                  <h2>No paths match these filters</h2>
                  <p>Try another entity, severity, or relationship type.</p>
                  <button
                    className="secondary-button"
                    onClick={() => {
                      setSearch("");
                      setSeverity("");
                      setEntity("");
                      setRelationship("");
                    }}
                  >
                    Clear filters
                  </button>
                </section>
              ) : (
                <div className="results-workbench">
                  <aside
                    className="path-index"
                    aria-label="Ranked attack paths"
                  >
                    <div className="path-index-heading">
                      <h2>Priority paths</h2>
                      <span role="status">
                        {filtered.length} of {paths.length}
                      </span>
                    </div>
                    <ol>
                      {filtered.map((path) => (
                        <li key={path.id}>
                          <button
                            className={`path-choice ${selected?.id === path.id ? "is-selected" : ""}`}
                            aria-pressed={selected?.id === path.id}
                            onClick={() => choose(path)}
                            aria-label={`Inspect path from ${path.steps[0]?.source_name} to ${path.steps.at(-1)?.target_name}`}
                          >
                            <div className="path-choice-meta">
                              <span
                                className={`severity severity-${pathSeverity(path.risk_score)}`}
                              >
                                {pathSeverity(path.risk_score)}
                              </span>
                              <strong>
                                {Math.round(path.risk_score)}
                                <small>/100</small>
                              </strong>
                            </div>
                            <span className="path-choice-source">
                              {path.steps[0]?.source_name}
                            </span>
                            <span className="path-choice-target">
                              <ArrowRight size={13} />
                              {path.steps.at(-1)?.target_name}
                            </span>
                            <small>
                              {path.hop_count} relationships · {path.confidence}{" "}
                              confidence
                            </small>
                          </button>
                        </li>
                      ))}
                    </ol>
                  </aside>
                  {selected && (
                    <div className="selected-path" key={selected.id}>
                      <section
                        className="panel graph-section"
                        aria-labelledby="selected-path-title"
                      >
                        <div className="selected-path-heading">
                          <div>
                            <span className="section-label">
                              Selected attack path
                            </span>
                            <h2 id="selected-path-title">
                              {selected.steps[0]?.source_name}
                              <ArrowRight size={19} />
                              {selected.steps.at(-1)?.target_name}
                            </h2>
                          </div>
                          <span
                            className={`severity severity-${pathSeverity(selected.risk_score)}`}
                          >
                            {pathSeverity(selected.risk_score)}
                          </span>
                        </div>
                        <FocusedPathGraph
                          path={selected}
                          snapshotId={p.snapshotId}
                        />
                      </section>
                      <PathDetails path={selected} />
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

function PathDetails({ path }: { path: PathResult }) {
  const p = useProduct();
  const fixes = p.fixes
    .filter((fix) => path.steps.some((step) => step.relationship_id === fix.id))
    .slice(0, 3);
  return (
    <>
      <section className="panel path-explanation">
        <div>
          <GitBranch size={19} />
          <h2>Why this matters</h2>
          <p>
            This route connects <strong>{path.steps[0]?.source_name}</strong> to{" "}
            <strong>{path.steps.at(-1)?.target_name}</strong> through{" "}
            {path.hop_count} imported relationships. Control over the starting
            object could let an attacker accumulate access along the chain, if
            each step’s prerequisites hold.
          </p>
          <small>{path.limitations}</small>
        </div>
        <dl className="path-facts">
          <div>
            <dt>Review priority</dt>
            <dd>{Math.round(path.risk_score)} / 100</dd>
          </div>
          <div>
            <dt>Confidence</dt>
            <dd>{path.confidence}</dd>
          </div>
          <div>
            <dt>Affected entities</dt>
            <dd>
              {
                new Set(
                  path.steps.flatMap((step) => [
                    step.source_node_id,
                    step.target_node_id,
                  ]),
                ).size
              }
            </dd>
          </div>
        </dl>
      </section>
      <section className="panel path-evidence" aria-labelledby="evidence-title">
        <div className="section-heading">
          <h2 id="evidence-title">Path details & evidence</h2>
          <FileSearch size={19} />
        </div>
        <p className="muted section-description">
          Follow the chain in order. Expand a relationship to inspect its
          imported evidence.
        </p>
        <ol className="evidence-chain">
          {path.steps.map((step) => (
            <li key={`${step.position}-${step.relationship_id}`}>
              <span className="step-number">{step.position}</span>
              <div className="step-body">
                <div className="step-entities">
                  <strong>
                    {step.source_name}
                    <small>{step.source_type}</small>
                  </strong>
                  <ArrowRight size={16} />
                  <strong>
                    {step.target_name}
                    <small>{step.target_type}</small>
                  </strong>
                </div>
                <div className="step-relationship">
                  <span>{relationshipLabel(step.relationship_type)}</span>
                  <small>{step.confidence} confidence</small>
                </div>
                <p>{step.step_explanation}</p>
                <details className="step-evidence">
                  <summary>Source evidence</summary>
                  <pre>
                    {Object.keys(step.evidence ?? {}).length
                      ? JSON.stringify(step.evidence, null, 2)
                      : "No additional source evidence was supplied for this relationship."}
                  </pre>
                  <small>
                    Relationship ID: <code>{step.relationship_id}</code> ·
                    imported cost {step.risk_weight}
                  </small>
                </details>
              </div>
            </li>
          ))}
        </ol>
        <details className="advanced scoring-details">
          <summary>How this path is scored</summary>
          <p>
            Score = 100 − (effective relationship cost × 3) − hop count, bounded
            to 0–100. Confidence can increase effective cost. Higher scores
            prioritize review, independently of evidence confidence.
          </p>
          <pre>{JSON.stringify(path.scoring_components, null, 2)}</pre>
        </details>
      </section>
      <section
        className="panel path-remediation"
        aria-labelledby="remediation-title"
      >
        <div className="section-heading">
          <h2 id="remediation-title">Break this path</h2>
          <Wrench size={19} />
        </div>
        <p className="muted section-description">
          Review one of these relationships with its owner. Removing a necessary
          control requires an alternative that preserves legitimate access.
        </p>
        <ol className="remediation-list">
          {fixes.map((fix) => (
            <li key={fix.id}>
              <span className="fix-icon">
                <Wrench size={17} />
              </span>
              <div>
                <h3>{fix.title}</h3>
                <p>{fix.summary}</p>
                <small>
                  Shared by {fix.paths} returned path
                  {fix.paths === 1 ? "" : "s"}.
                </small>
              </div>
            </li>
          ))}
        </ol>
        <div className="retest-note">
          <ShieldCheck size={17} />
          <p>
            After an approved change, import a fresh snapshot and rerun the same
            query to verify that the route is broken.
          </p>
        </div>
      </section>
    </>
  );
}
