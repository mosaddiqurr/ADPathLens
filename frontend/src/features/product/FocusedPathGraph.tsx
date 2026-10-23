import { Maximize2, Minus, Plus } from "lucide-react";
import type { Core } from "cytoscape";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api, errorMessage } from "../../api/client";
import type { PathResult } from "../../types/api";
type Element = { data: Record<string, string | number | boolean | null> };
type Elements = {
  nodes: Element[];
  relationships: Element[];
  truncated?: boolean;
};
const GraphCanvas = lazy(() =>
  import("../../graph/GraphCanvas").then((module) => ({
    default: module.GraphCanvas,
  })),
);
export function FocusedPathGraph({
  path,
  snapshotId,
}: {
  path: PathResult;
  snapshotId: string;
}) {
  const [neighbors, setNeighbors] = useState<Elements | null>(null);
  const [nearby, setNearby] = useState(false);
  const [loading, setLoading] = useState(false);
  const [core, setCore] = useState<Core | null>(null);
  const [message, setMessage] = useState("");
  const [name, setName] = useState("");
  const highlighted = useMemo(
    () => path.steps.map((step) => step.relationship_id),
    [path],
  );
  const orderedNodes = useMemo(
    () => [
      ...new Set(
        path.steps.flatMap((step) => [
          step.source_node_id,
          step.target_node_id,
        ]),
      ),
    ],
    [path],
  );
  const data = useMemo(() => {
    const n = new Map(
      neighbors?.nodes.map((node) => [node.data.id, node]) ?? [],
    );
    const r = new Map(
      neighbors?.relationships.map((edge) => [edge.data.id, edge]) ?? [],
    );
    path.steps.forEach((step, index) => {
      n.set(step.source_node_id, {
        data: {
          id: step.source_node_id,
          label: step.source_name,
          type: step.source_type,
          high_value: false,
        },
      });
      n.set(step.target_node_id, {
        data: {
          id: step.target_node_id,
          label: step.target_name,
          type: step.target_type,
          high_value: index === path.steps.length - 1,
        },
      });
      r.set(step.relationship_id, {
        data: {
          id: step.relationship_id,
          source: step.source_node_id,
          target: step.target_node_id,
          type: step.relationship_type,
          label: step.relationship_type.replace(/([a-z])([A-Z])/g, "$1 $2"),
        },
      });
    });
    return { nodes: [...n.values()], relationships: [...r.values()] };
  }, [path, neighbors]);
  const select = useCallback(
    (id: string) => {
      const node = data.nodes.find((n) => n.data.id === id);
      setName(node ? `${node.data.label} · ${node.data.type}` : "");
    },
    [data],
  );
  useEffect(() => {
    let alive = true;
    setNeighbors(null);
    setMessage("");
    if (!nearby || !path.steps.length) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api<Elements>(
      `/snapshots/${snapshotId}/graph?focus_node_id=${path.steps[0].source_node_id}&depth=1&maximum_nodes=40&maximum_relationships=80`,
    )
      .then((result) => {
        if (alive) setNeighbors(result);
      })
      .catch((e) => {
        if (alive) setMessage(errorMessage(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [path, snapshotId, nearby]);
  function zoom(factor: number) {
    if (core)
      core.zoom({
        level: Math.min(2.5, Math.max(0.25, core.zoom() * factor)),
        renderedPosition: { x: core.width() / 2, y: core.height() / 2 },
      });
  }
  return (
    <section
      className="focused-path-graph"
      aria-label="Focused path exploration"
    >
      <div className="focused-graph-toolbar">
        <span>
          {nearby ? "Path and nearby relationships" : "Selected path only"}
        </span>
        <button
          className="text-link"
          disabled={loading}
          onClick={() => {
            setName("");
            setNearby(!nearby);
          }}
        >
          {nearby ? "Path only" : "Show nearby relationships"}
        </button>
        <div className="graph-zoom-controls" aria-label="Graph controls">
          <button
            className="tool-button"
            aria-label="Zoom out"
            onClick={() => zoom(1 / 1.25)}
          >
            <Minus size={15} />
          </button>
          <button
            className="tool-button"
            aria-label="Zoom in"
            onClick={() => zoom(1.25)}
          >
            <Plus size={15} />
          </button>
          <button
            className="tool-button"
            aria-label="Fit graph"
            onClick={() => core?.fit(core.elements(), 30)}
          >
            <Maximize2 size={15} />
          </button>
        </div>
      </div>
      {message && <p role="alert">{message}</p>}
      {loading && <p role="status">Loading nearby relationships…</p>}
      <Suspense
        fallback={
          <p role="status" className="graph-canvas">
            Opening path graph…
          </p>
        }
      >
        <GraphCanvas
          nodes={data.nodes}
          relationships={data.relationships}
          highlightedRelationships={highlighted}
          orderedNodeIds={orderedNodes}
          onNodeSelected={select}
          onReady={setCore}
        />
      </Suspense>
      <div className="graph-bottom">
        <div className="graph-key" aria-label="Graph legend">
          <span>
            <i className="key-user" />
            User
          </span>
          <span>
            <i className="key-group" />
            Group
          </span>
          <span>
            <i className="key-computer" />
            Computer
          </span>
          <span>
            <i className="key-target" />
            Target
          </span>
          <span>
            <i className="key-path" />
            Selected route
          </span>
        </div>
        <small role="status">
          {name || "Drag to pan · scroll or pinch to zoom"}
        </small>
      </div>
      {neighbors?.truncated && (
        <small>
          Nearby context reached its display limit. The full selected path is
          preserved.
        </small>
      )}
    </section>
  );
}
