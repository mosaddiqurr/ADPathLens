import cytoscape, { Core } from "cytoscape";
import { useEffect, useRef } from "react";

type Element = { data: Record<string, string | number | boolean | null> };

export function GraphCanvas({
  nodes,
  relationships,
  highlightedRelationships = [],
  onNodeSelected,
  onReady,
}: {
  nodes: Element[];
  relationships: Element[];
  highlightedRelationships?: string[];
  onNodeSelected: (nodeId: string) => void;
  onReady?: (core: Core) => void;
}) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    const core = cytoscape({
      container: container.current,
      elements: [...nodes, ...relationships],
      layout: { name: "cose", animate: false, nodeRepulsion: () => 7200 },
      minZoom: 0.2,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            color: "#dbeafe",
            "font-size": 10,
            "text-valign": "bottom",
            "text-margin-y": 7,
            "background-color": "#36c4b5",
            "border-width": 2,
            "border-color": "#07101d",
            width: 28,
            height: 28,
          },
        },
        {
          selector: 'node[high_value = "true"], node[high_value = true]',
          style: { shape: "diamond", "background-color": "#f59e0b", width: 38, height: 38 },
        },
        {
          selector: 'node[privileged = "true"], node[privileged = true]',
          style: { shape: "hexagon", "border-color": "#fb7185", "border-width": 4 },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#54708c",
            "target-arrow-color": "#54708c",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            opacity: 0.75,
          },
        },
        {
          selector: ".path-focus",
          style: { "line-color": "#fb7185", "target-arrow-color": "#fb7185", width: 5, opacity: 1 },
        },
        { selector: "node:selected", style: { "overlay-color": "#65e8d8", "overlay-opacity": 0.25 } },
      ],
    });
    highlightedRelationships.forEach((id) => core.getElementById(id).addClass("path-focus"));
    core.on("tap", "node", (event) => onNodeSelected(event.target.id()));
    onReady?.(core);
    return () => core.destroy();
  }, [highlightedRelationships, nodes, onNodeSelected, onReady, relationships]);

  return <div className="graph-canvas" ref={container} role="img" aria-label="Interactive privilege relationship graph" />;
}

