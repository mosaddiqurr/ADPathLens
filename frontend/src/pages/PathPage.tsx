import { AlertTriangle, ArrowRight, Route, ScanSearch, ShieldAlert } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, errorMessage } from "../api/client";
import { ProjectNav } from "../components/common/ProjectNav";
import { StatusMessage } from "../components/common/StatusMessage";
import type { Analysis, DirectoryNode, Finding, Page, Snapshot } from "../types/api";

export function PathPage() {
  const { snapshotId = "" } = useParams<{ snapshotId: string }>();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [nodes, setNodes] = useState<DirectoryNode[]>([]);
  const [start, setStart] = useState("");
  const [target, setTarget] = useState("");
  const [targetKind, setTargetKind] = useState("specific");
  const [algorithm, setAlgorithm] = useState("shortest_hops");
  const [maximumDepth, setMaximumDepth] = useState(12);
  const [minimumConfidence, setMinimumConfidence] = useState("low");
  const [relationshipProfile, setRelationshipProfile] = useState("all");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      api<Snapshot>(`/snapshots/${snapshotId}`),
      api<Page<DirectoryNode>>(`/snapshots/${snapshotId}/nodes?page_size=100`),
    ])
      .then(([snapshotData, nodePage]) => {
        setSnapshot(snapshotData);
        setNodes(nodePage.items);
        const mina = nodePage.items.find((node) => node.display_name === "Mina Rahman");
        const domainAdmins = nodePage.items.find((node) => node.display_name === "Domain Admins");
        setStart(mina?.id ?? nodePage.items[0]?.id ?? "");
        setTarget(domainAdmins?.id ?? nodePage.items.find((node) => node.high_value)?.id ?? "");
      })
      .catch((reason) => setMessage(errorMessage(reason)));
  }, [snapshotId]);

  async function runAnalysis(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const result = await api<Analysis>(`/snapshots/${snapshotId}/analyses`, {
        method: "POST",
        json: {
          start_node_id: start,
          target_node_id: targetKind === "specific" || algorithm === "reverse_reachability" ? target : null,
          target_kind: targetKind,
          algorithm,
          maximum_depth: maximumDepth,
          maximum_paths: algorithm === "top_paths" ? 10 : 5,
          minimum_confidence: minimumConfidence,
          relationship_types:
            relationshipProfile === "guided"
              ? ["MemberOf", "ResetPassword", "AdminTo", "HasSession"]
              : [],
          include_disabled: false,
        },
      });
      setAnalysis(result);
      setMessage(result.path_count ? `Found ${result.path_count} bounded possible path(s).` : "No path was found within the selected bounds.");
    } catch (reason) {
      setMessage(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function createFinding(pathId: string) {
    if (!snapshot) return;
    try {
      const path = analysis?.paths.find((item) => item.id === pathId);
      const finding = await api<Finding>(`/projects/${snapshot.project_id}/findings`, {
        method: "POST",
        json: {
          snapshot_id: snapshot.id,
          privilege_path_id: pathId,
          title: `Possible privilege path requiring review`,
          category: "privilege_path",
          severity: path && path.risk_score >= 65 ? "high" : "medium",
          confidence: path?.confidence ?? "unknown",
          description: path?.explanation ?? "A bounded path was identified.",
          technical_explanation: path?.explanation ?? "",
          impact: "Imported relationships model a possible route to a stronger principal or high-value asset.",
          remediation: "Review each relationship, remove unnecessary control, and retest against a derived snapshot.",
          validation_steps: ["Confirm each relationship against an authorized source.", "Retest after remediation."],
          limitations: "A possible path is not evidence of compromise.",
        },
      });
      setMessage(`Finding created: ${finding.title}`);
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  async function scanRules() {
    try {
      const summary = await api<{ total: number }>(`/snapshots/${snapshotId}/risk-scan`, { method: "POST" });
      setMessage(`Deterministic scan created ${summary.total} draft finding(s).`);
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  return (
    <div className="page">
      <div className="page-heading"><div><p className="eyebrow">Bounded path analysis</p><h1>{snapshot?.name ?? "Path finder"}</h1><p>Lower cost indicates stronger modeled concern—not proof of real-world exploitability.</p></div><Route size={32} /></div>
      {snapshot && <ProjectNav projectId={snapshot.project_id} snapshotId={snapshot.id} />}
      <StatusMessage message={message} tone={analysis?.path_count ? "success" : "info"} />
      <div className="two-column analysis-layout">
        <section className="panel">
          <div className="panel-heading"><h2>Analysis request</h2><ScanSearch /></div>
          <form className="form-stack" onSubmit={(event) => void runAnalysis(event)}>
            <label>Source<select value={start} onChange={(event) => setStart(event.target.value)} required>{nodes.map((node) => <option value={node.id} key={node.id}>{node.display_name} · {node.node_type}</option>)}</select></label>
            <label>Target selector<select value={targetKind} onChange={(event) => setTargetKind(event.target.value)}><option value="specific">Specific node</option><option value="high_value">Any high-value asset</option><option value="privileged">Any privileged node</option></select></label>
            {(targetKind === "specific" || algorithm === "reverse_reachability") && <label>Target<select value={target} onChange={(event) => setTarget(event.target.value)} required>{nodes.map((node) => <option value={node.id} key={node.id}>{node.display_name} · {node.node_type}</option>)}</select></label>}
            <label>Algorithm<select value={algorithm} onChange={(event) => setAlgorithm(event.target.value)}><option value="shortest_hops">Shortest hops</option><option value="lowest_cost">Lowest modeled cost</option><option value="top_paths">Top bounded paths</option><option value="reverse_reachability">Reverse reachability</option></select></label>
            <label>Maximum depth <output>{maximumDepth}</output><input type="range" min="1" max="12" value={maximumDepth} onChange={(event) => setMaximumDepth(Number(event.target.value))} /></label>
            <label>Minimum confidence<select value={minimumConfidence} onChange={(event) => setMinimumConfidence(event.target.value)}><option value="unknown">Include unknown</option><option value="low">Low or higher</option><option value="medium">Medium or higher</option><option value="high">High only</option></select></label>
            <label>Relationship filter<select value={relationshipProfile} onChange={(event) => setRelationshipProfile(event.target.value)}><option value="all">All path-eligible relationships</option><option value="guided">Guided Mina path: membership, reset, admin, session</option></select></label>
            <button className="primary-button" disabled={busy || !start}>{busy ? "Analyzing…" : "Run bounded analysis"}</button>
            <button className="secondary-button" type="button" onClick={() => void scanRules()}><ShieldAlert size={17} />Run deterministic risk scan</button>
          </form>
        </section>
        <aside className="panel interpretation-panel">
          <AlertTriangle />
          <h2>Analysis boundary</h2>
          <p>Traversal stops at the configured depth, result, expansion, graph-size, and deadline budgets. Parallel relationships retain their stored IDs.</p>
          <p><strong>No path</strong> means no eligible route was found under these filters and limits. It does not prove that no route exists in the environment.</p>
        </aside>
      </div>
      {analysis && (
        <section className="results-stack" aria-live="polite">
          <div className="section-heading"><div><p className="eyebrow">Results</p><h2>{analysis.path_count} possible path{analysis.path_count === 1 ? "" : "s"}</h2></div>{snapshot && <Link className="text-link" to={`/projects/${snapshot.project_id}/findings`}>Open findings</Link>}</div>
          {analysis.paths.map((path) => (
            <article className="path-card" key={path.id}>
              <div className="path-card-head"><div><span className="rank">#{path.rank}</span><strong>{path.hop_count} hops · cost {path.total_weight.toFixed(2)}</strong><p>{path.confidence} confidence · risk indicator {path.risk_score.toFixed(0)}</p></div><button className="secondary-button" onClick={() => void createFinding(path.id)}>Create finding</button></div>
              <div className="path-visual" aria-label={`Path ${path.rank}`}>
                {path.steps.map((step, index) => <div className="path-hop" key={step.relationship_id}><span className="path-node">{step.source_name}</span><span className="path-edge"><ArrowRight size={16} />{step.relationship_type}</span>{index === path.steps.length - 1 && <span className="path-node target">{step.target_name}</span>}</div>)}
              </div>
              <details><summary>Step-by-step evidence and remediation</summary><ol className="evidence-list">{path.steps.map((step) => <li key={step.relationship_id}><strong>{step.source_name} → {step.relationship_type} → {step.target_name}</strong><p>{step.step_explanation}</p><p><span className="label">Remediation:</span> {step.remediation_summary}</p><small>Stored relationship {step.relationship_id} · {step.confidence} confidence · cost {step.risk_weight}</small></li>)}</ol></details>
              <p className="limitation">{path.limitations}</p>
            </article>
          ))}
          {!analysis.path_count && <div className="panel empty-state"><Route /><h3>No path within current bounds</h3><p>Try a different target, confidence filter, or depth while preserving bounded traversal.</p></div>}
        </section>
      )}
    </div>
  );
}
