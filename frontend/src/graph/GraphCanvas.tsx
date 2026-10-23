import cytoscape, { Core } from "cytoscape";
import { useEffect, useRef } from "react";
import { useAppearance } from "../features/appearance/AppearanceContext";
type Element = { data: Record<string, string | number | boolean | null> };
const emptyIds: string[] = [];
function graphStyles(): cytoscape.StylesheetJson {
  const root = getComputedStyle(document.documentElement);
  const c = (name: string) => root.getPropertyValue(name).trim();
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        color: c("--text"),
        "font-family": "Space Grotesk, Manrope, sans-serif",
        "font-size": 12,
        "font-weight": 600,
        "text-valign": "center",
        "text-halign": "center",
        "text-wrap": "wrap",
        "text-max-width": "100px",
        "background-color": c("--surface-2"),
        "border-width": 1.5,
        "border-color": c("--border-strong"),
        width: 112,
        height: 52,
        shape: "ellipse",
      },
    },
    {
      selector: "node[type = 'Group']",
      style: { shape: "round-rectangle", "background-color": c("--surface-2") },
    },
    {
      selector: "node[type = 'Computer']",
      style: { shape: "rectangle", "background-color": c("--surface-2") },
    },
    {
      selector: "node[?high_value]",
      style: {
        shape: "diamond",
        width: 146,
        height: 80,
        "background-color": c("--brand-soft"),
        "border-color": c("--brand"),
        color: c("--brand"),
        "text-max-width": "92px",
      },
    },
    {
      selector: "edge",
      style: {
        width: 1.5,
        "line-color": c("--quiet"),
        "target-arrow-color": c("--quiet"),
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        "arrow-scale": 1.2,
        opacity: 0.65,
      },
    },
    {
      selector: "edge.path-focus",
      style: {
        label: "data(label)",
        "font-size": 11,
        color: c("--muted"),
        "text-wrap": "wrap",
        "text-max-width": "105px",
        "text-background-color": c("--surface-deep"),
        "text-background-opacity": 1,
        "text-background-padding": "4px",
        "line-color": c("--brand"),
        "target-arrow-color": c("--brand"),
        width: 2.5,
        opacity: 1,
      },
    },
    {
      selector: "node:selected",
      style: {
        "border-width": 3,
        "border-color": c("--brand"),
        "overlay-opacity": 0,
        "background-color": c("--brand-soft"),
      },
    },
  ];
}

export function GraphCanvas({
  nodes,
  relationships,
  highlightedRelationships = emptyIds,
  orderedNodeIds = emptyIds,
  onNodeSelected,
  onReady,
}: {
  nodes: Element[];
  relationships: Element[];
  highlightedRelationships?: string[];
  orderedNodeIds?: string[];
  onNodeSelected: (nodeId: string) => void;
  onReady?: (core: Core) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const engine = useRef<Core | null>(null);
  const { theme } = useAppearance();
  useEffect(() => {
    engine.current?.style(graphStyles());
  }, [theme]);
  useEffect(() => {
    if (!container.current) return;
    const element = container.current;
    const core = cytoscape({
      container: element,
      elements: [...nodes, ...relationships],
      layout: { name: "preset" },
      minZoom: 0.25,
      maxZoom: 2.5,
      wheelSensitivity: 0.18,
      style: graphStyles(),
    });
    engine.current = core;
    highlightedRelationships.forEach((id) =>
      core.getElementById(id).addClass("path-focus"),
    );
    function layout() {
      core.resize();
      if (orderedNodeIds.length) {
        const width = element.clientWidth || 700;
        const columns = Math.min(
          orderedNodeIds.length,
          width >= 740 ? 4 : width >= 490 ? 3 : 2,
        );
        const rows = Math.ceil(orderedNodeIds.length / columns);
        element.style.height = `${Math.min(width < 490 ? 420 : 590, Math.max(300, rows * 150 + 35))}px`;
        const spacing =
          columns === 1 ? 0 : Math.min(230, (width - 146) / (columns - 1));
        const offset = (width - spacing * (columns - 1)) / 2;
        orderedNodeIds.forEach((id, index) => {
          const row = Math.floor(index / columns);
          const column =
            row % 2 ? columns - 1 - (index % columns) : index % columns;
          core
            .getElementById(id)
            .position({ x: offset + column * spacing, y: 75 + row * 150 });
        });
        const others = core
          .nodes()
          .filter((node) => !orderedNodeIds.includes(node.id()));
        others.forEach((node, index) => {
          node.position({
            x: 80 + (index % 4) * 170,
            y: 90 + rows * 150 + Math.floor(index / 4) * 130,
          });
        });
        core.resize();
        core.fit(core.elements(), 25);
        if (core.zoom() < 0.7) {
          core.zoom(0.7);
          core.pan({ x: width / 2 - offset * 0.7, y: 35 });
        }
      } else {
        core
          .layout({
            name: "breadthfirst",
            directed: true,
            spacingFactor: 1.6,
            padding: 35,
            nodeDimensionsIncludeLabels: true,
            animate: false,
          })
          .run();
      }
    }
    layout();
    let previousWidth = element.clientWidth;
    const observer = new ResizeObserver(() => {
      if (Math.abs(element.clientWidth - previousWidth) > 5) {
        previousWidth = element.clientWidth;
        layout();
      }
    });
    observer.observe(element);
    core.on("tap", "node", (event) => onNodeSelected(event.target.id()));
    onReady?.(core);
    return () => {
      observer.disconnect();
      core.destroy();
      engine.current = null;
    };
  }, [
    nodes,
    relationships,
    highlightedRelationships,
    orderedNodeIds,
    onNodeSelected,
    onReady,
  ]);
  return (
    <div
      className="graph-canvas"
      ref={container}
      role="img"
      aria-label="Interactive privilege relationship graph"
    />
  );
}
