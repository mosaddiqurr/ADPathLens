import {
  ArrowRight,
  Database,
  Network,
  ScanSearch,
  FileSearch,
  GitBranch,
  SlidersHorizontal,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useHistory, useLocation } from "react-router-dom";
import { errorMessage } from "../api/client";
import { StatusMessage } from "../components/common/StatusMessage";
import { useProduct } from "../features/product/ProductContext";
import { readAll } from "../features/product/analysis";
import type { DirectoryNode } from "../types/api";
import { ImportPanel } from "../components/ImportPanel";

export function PageHeading({
  label,
  title,
  description,
  children,
}: {
  label?: string;
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {label && <p className="eyebrow">{label}</p>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children}
    </div>
  );
}
export function DemoButton() {
  const product = useProduct();
  const history = useHistory();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function open() {
    setBusy(true);
    setMessage("");
    try {
      await product.openDemo();
      history.push("/analyze");
    } catch (e) {
      setMessage(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="demo-action">
      <button
        className="secondary-button"
        disabled={busy || !product.canEdit}
        onClick={() => void open()}
      >
        <Network size={16} />
        {busy ? "Loading demo…" : "Load demo"}
      </button>
      <StatusMessage message={message} tone="danger" />
    </div>
  );
}
export function EmptyEnvironment() {
  return (
    <section className="empty-environment">
      <ScanSearch size={28} />
      <h2>Start with directory data</h2>
      <p>
        Import your relationships or explore the fictional NORTHBRIDGE demo.
      </p>
      <Link className="primary-button" to="/analyze">
        Analyze AD data
        <ArrowRight size={16} />
      </Link>
    </section>
  );
}
export function AnalyzePage() {
  const p = useProduct();
  const history = useHistory();
  const location = useLocation();
  const [nodes, setNodes] = useState<DirectoryNode[]>([]);
  const [target, setTarget] = useState("");
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [upload, setUpload] = useState(false);
  const [depth, setDepth] = useState(12);
  const [confidence, setConfidence] = useState("low");
  const [algorithm, setAlgorithm] = useState("top_paths");
  const [nodesLoading, setNodesLoading] = useState(false);
  useEffect(() => {
    let alive = true;
    setNodes([]);
    setTarget("");
    setSource("");
    setMessage("");
    if (!p.snapshotId) {
      setNodesLoading(false);
      return;
    }
    setNodesLoading(true);
    readAll<DirectoryNode>(`/snapshots/${p.snapshotId}/nodes`)
      .then((data) => {
        if (!alive) return;
        setNodes(data);
        setTarget(
          data.find((n) => n.high_value && n.display_name === "Domain Admins")
            ?.id ??
            data.find((n) => n.high_value)?.id ??
            data[0]?.id ??
            "",
        );
      })
      .catch((e) => {
        if (alive) setMessage(errorMessage(e));
      })
      .finally(() => {
        if (alive) setNodesLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [p.snapshotId]);
  useEffect(() => {
    if (new URLSearchParams(location.search).get("demo") !== "1") return;
    let alive = true;
    setBusy(true);
    p.openDemo()
      .then(() => {
        if (alive) history.replace("/analyze");
      })
      .catch((e) => {
        if (alive) setMessage(errorMessage(e));
      })
      .finally(() => {
        if (alive) setBusy(false);
      });
    return () => {
      alive = false;
    };
    // The query is a navigation action; product state changes during import.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search, history]);
  async function analyze() {
    setBusy(true);
    setMessage("");
    try {
      await p.runAnalysis(target, source, {
        maximum_depth: depth,
        minimum_confidence: confidence,
        algorithm: source ? algorithm : "reverse_reachability",
      });
      history.push("/results");
    } catch (e) {
      setMessage(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  const targets = nodes.filter((n) => n.high_value);
  return (
    <div className="page analyze-page">
      <PageHeading
        label="Directory workspace"
        title="Analyze"
        description="Import relationships, choose a privileged target, and trace the access that leads to it."
      >
        {p.analysis && (
          <Link className="text-link previous-results" to="/results">
            View previous results <ArrowRight size={14} />
          </Link>
        )}
      </PageHeading>
      <StatusMessage message={message || p.error} tone="danger" />
      <div className="analyze-workspace">
        <section className="panel analysis-input" aria-labelledby="input-title">
          <div className="analysis-card-heading">
            <h2 id="input-title">
              {p.snapshot && !upload
                ? "Analysis scope"
                : "Import directory data"}
            </h2>
            <p>
              {p.snapshot && !upload
                ? "Choose the access you want to investigate."
                : "Start with a snapshot of your directory relationships."}
            </p>
          </div>
          {p.loading && <p role="status">Loading directory data…</p>}
          {p.snapshot && !upload && (
            <div className="snapshot-summary">
              <span className="snapshot-icon">
                <Database size={17} />
              </span>
              <div>
                <strong>{p.snapshot.name}</strong>
                <small>
                  <span className="snapshot-ready" />
                  Directory data loaded
                </small>
              </div>
              <button
                className="text-link"
                disabled={busy}
                onClick={() => setUpload(true)}
              >
                Import new data
              </button>
            </div>
          )}
          {(!p.snapshot || upload) && (
            <>
              {upload && (
                <button
                  className="text-link upload-cancel"
                  onClick={() => setUpload(false)}
                >
                  Use current snapshot
                </button>
              )}
              <ImportPanel
                projectId={
                  p.project?.name === "NORTHBRIDGE Guided Lab"
                    ? ""
                    : p.projectId
                }
                prepareProject={p.ensureImportProject}
                onImported={async (id, collectionId) => {
                  await p.selectImportedSnapshot(collectionId, id);
                  setUpload(false);
                }}
              />
            </>
          )}
          {p.snapshot && !upload && (
            <fieldset
              className="analysis-options"
              disabled={busy || nodesLoading}
            >
              <legend className="sr-only">Analysis options</legend>
              <label>
                Privileged target
                <select
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                >
                  {(targets.length ? targets : nodes).map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.display_name}
                    </option>
                  ))}
                  {targets.length > 0 && targets.length < nodes.length && (
                    <optgroup label="Other directory objects">
                      {nodes
                        .filter((n) => !n.high_value)
                        .map((n) => (
                          <option key={n.id} value={n.id}>
                            {n.display_name} · {n.node_type}
                          </option>
                        ))}
                    </optgroup>
                  )}
                </select>
              </label>
              {!targets.length && !nodesLoading && (
                <p className="muted">
                  No asset is marked high value. Choose an object to
                  investigate.
                </p>
              )}
              <label>
                Starting identity
                <select
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                >
                  <option value="">Any standard identity</option>
                  {nodes
                    .filter((n) => n.enabled)
                    .map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.display_name} · {n.node_type}
                      </option>
                    ))}
                </select>
              </label>
              <small className="scope-description">
                {source
                  ? "Explore alternative routes from this identity."
                  : "Returns one shortest path per reachable, enabled, non-privileged object."}{" "}
              </small>
              <details className="advanced analysis-advanced">
                <summary>
                  <SlidersHorizontal size={14} />
                  Analysis limits & options
                </summary>
                <div className="form-stack">
                  {p.projects.length > 1 && (
                    <label>
                      Data collection
                      <select
                        value={p.projectId}
                        onChange={(e) => p.setProjectId(e.target.value)}
                      >
                        {p.projects.map((project) => (
                          <option value={project.id} key={project.id}>
                            {project.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  {p.snapshots.length > 1 && (
                    <label>
                      Snapshot
                      <select
                        value={p.snapshotId}
                        onChange={(e) => p.setSnapshotId(e.target.value)}
                      >
                        {p.snapshots.map((s) => (
                          <option value={s.id} key={s.id}>
                            {s.name}
                            {s.snapshot_type === "derived"
                              ? " (simulation)"
                              : ""}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  {source && (
                    <label>
                      Path algorithm
                      <select
                        value={algorithm}
                        onChange={(e) => setAlgorithm(e.target.value)}
                      >
                        <option value="top_paths">
                          Multiple paths by relationship cost
                        </option>
                        <option value="shortest_hops">
                          Shortest path by hops
                        </option>
                        <option value="lowest_cost">
                          Lowest relationship cost
                        </option>
                      </select>
                    </label>
                  )}
                  <label>
                    Maximum relationships
                    <input
                      type="number"
                      min={1}
                      max={12}
                      value={depth}
                      onChange={(e) => setDepth(Number(e.target.value))}
                    />
                  </label>
                  <label>
                    Minimum confidence
                    <select
                      value={confidence}
                      onChange={(e) => setConfidence(e.target.value)}
                    >
                      <option value="unknown">Include unknown</option>
                      <option value="low">Low or higher</option>
                      <option value="medium">Medium or higher</option>
                      <option value="high">High only</option>
                    </select>
                  </label>
                </div>
              </details>
              <div className="analysis-actions">
                <small>
                  Up to 25 paths
                  <span>Maximum {depth} relationships per path</span>
                </small>
                <button
                  className="primary-button run-analysis"
                  disabled={
                    !target ||
                    !p.canEdit ||
                    !Number.isInteger(depth) ||
                    depth < 1 ||
                    depth > 12
                  }
                  onClick={() => void analyze()}
                >
                  {busy
                    ? "Analyzing directory…"
                    : nodesLoading
                      ? "Loading assets…"
                      : "Run analysis"}
                  <ArrowRight size={16} />
                </button>
              </div>
            </fieldset>
          )}
          {busy && (
            <p role="status" className="analysis-progress">
              Tracing eligible relationships and preserving evidence. Large
              snapshots may take a few seconds.
            </p>
          )}
          {!p.canEdit && (
            <p className="muted">
              Your viewer session can inspect existing results. An analyst can
              import data and run analysis.
            </p>
          )}
        </section>
        <aside className="analysis-guide" aria-label="Analysis guidance">
          {!p.snapshot || upload ? (
            <div className="analysis-demo">
              <span className="section-label">A directory to explore</span>
              <h2>Try the sample.</h2>
              <p>
                No data ready? NORTHBRIDGE is a fictional directory with several
                routes to Domain Admins.
              </p>
              <DemoButton />
            </div>
          ) : (
            <div className="analysis-outcomes">
              <span className="section-label">From access to evidence</span>
              <h2>See how it connects.</h2>
              <div>
                <GitBranch size={17} />
                <p>
                  <strong>Trace the relationships</strong>See the route from an
                  identity to your selected target.
                </p>
              </div>
              <div>
                <FileSearch size={17} />
                <p>
                  <strong>Review the evidence</strong>Inspect the source and
                  confidence behind each step.
                </p>
              </div>
              <Link className="text-link" to="/about">
                How to read a path <ArrowRight size={14} />
              </Link>
            </div>
          )}
          <details className="analysis-input-help">
            <summary>Input formats & example</summary>
            <p>
              ADPathLens JSON, paired CSV files, or a ZIP containing{" "}
              <code>nodes.csv</code> and <code>relationships.csv</code>.
              Collector exports need conversion to the documented schema.
            </p>
            <a className="text-link" href="/northbridge-demo.json" download>
              Download example JSON <ArrowRight size={14} />
            </a>
          </details>
        </aside>
      </div>
    </div>
  );
}
