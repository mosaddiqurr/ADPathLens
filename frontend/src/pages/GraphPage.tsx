import type { Core } from "cytoscape";
import { Download, Focus, Maximize2, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, errorMessage } from "../api/client";
import { ProjectNav } from "../components/common/ProjectNav";
import { StatusMessage } from "../components/common/StatusMessage";
import { GraphCanvas } from "../graph/GraphCanvas";
import type { DirectoryNode, Page, Snapshot } from "../types/api";

type GraphData = {
  snapshot_id: string;
  truncated: boolean;
  limits: { nodes: number; relationships: number };
  nodes: Array<{ data: Record<string, string | number | boolean | null> }>;
  relationships: Array<{ data: Record<string, string | number | boolean | null> }>;
};

type Summary = {
  node_count: number;
  relationship_count: number;
  high_value_count: number;
  privileged_count: number;
  nodes_by_type: Record<string, number>;
};

export function GraphPage() {
  const { snapshotId = "" } = useParams<{ snapshotId: string }>();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [nodes, setNodes] = useState<DirectoryNode[]>([]);
  const [selected, setSelected] = useState<DirectoryNode | null>(null);
  const [search, setSearch] = useState("");
  const [focus, setFocus] = useState("");
  const [nodeType, setNodeType] = useState("");
  const [message, setMessage] = useState("");
  const [core, setCore] = useState<Core | null>(null);

  const load = useCallback(async () => {
    try {
      const query = new URLSearchParams({ maximum_nodes: "500", maximum_relationships: "1500" });
      if (focus) query.set("focus_node_id", focus);
      if (nodeType) query.set("node_types", nodeType);
      const [snapshotData, summaryData, graphData, nodePage] = await Promise.all([
        api<Snapshot>(`/snapshots/${snapshotId}`),
        api<Summary>(`/snapshots/${snapshotId}/graph/summary`),
        api<GraphData>(`/snapshots/${snapshotId}/graph?${query}`),
        api<Page<DirectoryNode>>(`/snapshots/${snapshotId}/nodes?page_size=100&node_type=${encodeURIComponent(nodeType)}`),
      ]);
      setSnapshot(snapshotData);
      setSummary(summaryData);
      setGraph(graphData);
      setNodes(nodePage.items);
      setMessage(graphData.truncated ? "Rendering is bounded. Use filters or search to narrow the graph." : "");
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }, [focus, nodeType, snapshotId]);

  useEffect(() => {
    void load();
  }, [load]);

  const selectNode = useCallback(async (nodeId: string) => {
    try {
      setSelected(await api<DirectoryNode>(`/nodes/${nodeId}`));
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }, []);
  const handleNodeSelected = useCallback(
    (nodeId: string) => {
      void selectNode(nodeId);
    },
    [selectNode],
  );

  async function searchNode() {
    try {
      const results = await api<DirectoryNode[]>(`/snapshots/${snapshotId}/search?query=${encodeURIComponent(search)}`);
      if (!results.length) return setMessage("No matching node was found.");
      setFocus(results[0].id);
      setSelected(results[0]);
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  function exportImage() {
    if (!core) return;
    const anchor = document.createElement("a");
    anchor.href = core.png({ full: true, scale: 2, bg: "#07101d" });
    anchor.download = "adpathlens-graph.png";
    anchor.click();
  }

  return (
    <div className="page wide-page">
      <div className="page-heading"><div><p className="eyebrow">Graph explorer</p><h1>{snapshot?.name ?? "Snapshot graph"}</h1><p>Bounded, snapshot-scoped rendering with an accessible list alternative.</p></div><span className="summary-badge">{summary?.node_count ?? 0} nodes</span></div>
      {snapshot && <ProjectNav projectId={snapshot.project_id} snapshotId={snapshot.id} />}
      <StatusMessage message={message} tone={graph?.truncated ? "warning" : "info"} />
      <div className="graph-toolbar" role="group" aria-label="Graph controls">
        <label className="search-control"><span className="sr-only">Search nodes</span><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search names or external IDs" /><button onClick={() => void searchNode()}>Find</button></label>
        <label>Node type<select value={nodeType} onChange={(event) => setNodeType(event.target.value)}><option value="">All types</option>{Object.keys(summary?.nodes_by_type ?? {}).map((type) => <option key={type}>{type}</option>)}</select></label>
        <button className="tool-button" onClick={() => core?.fit()}><Maximize2 size={16} />Fit</button>
        <button className="tool-button" onClick={() => { setFocus(""); setSelected(null); }}><Focus size={16} />Reset</button>
        <button className="tool-button" onClick={exportImage}><Download size={16} />PNG</button>
      </div>
      <div className="graph-workbench">
        <section className="graph-panel">
          {graph && <GraphCanvas nodes={graph.nodes} relationships={graph.relationships} onNodeSelected={handleNodeSelected} onReady={setCore} />}
          <div className="graph-legend"><span><i className="legend-dot standard" />Standard</span><span><i className="legend-dot high" />High value</span><span><i className="legend-dot privileged" />Privileged</span></div>
        </section>
        <aside className="detail-drawer" aria-live="polite">
          {selected ? <><p className="eyebrow">{selected.node_type}</p><h2>{selected.display_name}</h2><dl><dt>External ID</dt><dd>{selected.external_id}</dd><dt>Domain</dt><dd>{selected.domain_name ?? "Not supplied"}</dd><dt>Enabled</dt><dd>{selected.enabled ? "Yes" : "No"}</dd><dt>High value</dt><dd>{selected.high_value ? "Yes" : "No"}</dd><dt>Risk</dt><dd>{selected.risk_level}</dd></dl><p>{selected.description || "No description supplied."}</p><button className="secondary-button" onClick={() => setFocus(selected.id)}>Expand neighbourhood</button></> : <div className="empty-state"><Focus /><p>Select a node to inspect its stored evidence and properties.</p></div>}
        </aside>
      </div>
      <section className="panel">
        <div className="panel-heading"><h2>Accessible node list</h2><span>First {nodes.length} records</span></div>
        <div className="table-wrap"><table><thead><tr><th>Name</th><th>Type</th><th>Domain</th><th>Privilege</th><th>Action</th></tr></thead><tbody>{nodes.map((node) => <tr key={node.id}><td>{node.display_name}</td><td>{node.node_type}</td><td>{node.domain_name ?? "—"}</td><td>{node.privileged ? "Privileged" : node.high_value ? "High value" : "Standard"}</td><td><button className="text-link" onClick={() => void selectNode(node.id)}>Inspect</button></td></tr>)}</tbody></table></div>
      </section>
    </div>
  );
}
