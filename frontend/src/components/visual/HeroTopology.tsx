import { Crown, Network, Server, UserRound, Users } from "lucide-react";
import { useEffect, useId, useRef } from "react";

// A deterministic, projected network keeps the decorative mesh stable on render.
const mesh = Array.from({ length: 72 }, (_, index) => {
  const ring = ((index % 24) / 24) * Math.PI * 2;
  const tube = (Math.floor(index / 24) / 3) * Math.PI * 2 + ring * 2;
  const radius = 196 + Math.cos(tube) * 47;
  const x = Math.cos(ring) * radius;
  const y = Math.sin(ring) * radius * 0.62;
  const z = Math.sin(tube) * 48;
  return { x: 312 + x * 0.89 + y * 0.45, y: 240 - x * 0.44 + y * 0.89 + z };
});
const connections = mesh.flatMap((point, index) =>
  [1, 24, 25].map((offset) => ({
    from: point,
    to: mesh[(index + offset) % mesh.length],
  })),
);
const stops = [
  { x: 86, y: 332, name: "User A", type: "Starting identity", Icon: UserRound },
  { x: 191, y: 253, name: "Helpdesk", type: "Group", Icon: Users },
  { x: 315, y: 305, name: "NB-HELPDESK-01", type: "Computer", Icon: Server },
  { x: 428, y: 197, name: "User B", type: "Privileged user", Icon: UserRound },
  { x: 532, y: 116, name: "Domain Admins", type: "Target", Icon: Crown },
];
const route = stops
  .map(({ x, y }, index) => `${index ? "L" : "M"}${x},${y}`)
  .join(" ");

export function HeroTopology() {
  const id = useId().replace(/:/g, "");
  const figure = useRef<HTMLElement>(null);
  useEffect(() => {
    const element = figure.current;
    if (!element) return;
    let inView = true;
    const update = () => {
      element.dataset.active = String(inView && !document.hidden);
    };
    const observer =
      typeof IntersectionObserver === "undefined"
        ? null
        : new IntersectionObserver(([entry]) => {
            inView = entry.isIntersecting;
            update();
          });
    observer?.observe(element);
    document.addEventListener("visibilitychange", update);
    update();
    return () => {
      observer?.disconnect();
      document.removeEventListener("visibilitychange", update);
    };
  }, []);
  return (
    <figure
      ref={figure}
      className="hero-topology"
      aria-label="Illustrative access path from User A through Helpdesk, a computer, and User B to Domain Admins. Moving amber signals follow the direction of access."
    >
      <div className="topology-overline">
        <span>
          <Network size={13} /> Directory relationships
        </span>
        <span>Illustrative route</span>
      </div>
      <div className="hero-topology-stage">
        <svg viewBox="0 0 640 470" role="img" aria-labelledby={`${id}-title`}>
          <title id={`${id}-title`}>
            A connected directory, with one path to privileged access
          </title>
          <defs>
            <radialGradient id={`${id}-glow`}>
              <stop stopColor="var(--brand)" stopOpacity="0.12" />
              <stop offset="1" stopColor="var(--brand)" stopOpacity="0" />
            </radialGradient>
          </defs>
          <ellipse
            cx="320"
            cy="235"
            rx="300"
            ry="210"
            fill={`url(#${id}-glow)`}
          />
          <g className="topology-mesh" aria-hidden="true">
            {connections.map(({ from, to }, index) => (
              <line key={index} x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
            ))}
            {mesh.map(({ x, y }, index) => (
              <circle key={index} cx={x} cy={y} r={index % 5 ? 2 : 3.5} />
            ))}
          </g>
          <path className="hero-route-shadow" d={route} />
          <path className="hero-route" d={route} pathLength="100" />
          {stops.map(({ x, y, name, type, Icon }, index) => (
            <g
              key={name}
              className={`hero-route-stop ${index === 4 ? "route-target" : ""}`}
            >
              <circle className="route-node-halo" cx={x} cy={y} r="29" />
              <circle className="route-node-disc" cx={x} cy={y} r="20" />
              <Icon
                x={x - 9}
                y={y - 9}
                width="18"
                height="18"
                strokeWidth="1.5"
              />
              <text
                x={x}
                y={y + 43}
                textAnchor="middle"
                className="route-node-name"
              >
                {name}
              </text>
              <text
                x={x}
                y={y + 60}
                textAnchor="middle"
                className="route-node-type"
              >
                {type}
              </text>
            </g>
          ))}
          <g className="route-edge-labels" aria-hidden="true">
            <text x="125" y="273" transform="rotate(-37 125 273)">
              Member of
            </text>
            <text x="248" y="253" transform="rotate(23 248 253)">
              Local admin
            </text>
            <text x="359" y="238" transform="rotate(-43 359 238)">
              Has session
            </text>
            <text x="466" y="141" transform="rotate(-38 466 141)">
              Member of
            </text>
          </g>
        </svg>
        <svg
          className="topology-signal-layer"
          viewBox="0 0 640 470"
          aria-hidden="true"
        >
          <path className="hero-signal" d={route} pathLength="100" />
          {stops.map(({ x, y, name }, index) => (
            <circle
              key={name}
              className="route-node-pulse"
              cx={x}
              cy={y}
              r="29"
              style={{ "--stop": index } as React.CSSProperties}
            />
          ))}
        </svg>
      </div>
      <figcaption className="hero-route-key">
        <span className="route-key-line" />
        One connected path. Four access relationships.
      </figcaption>
    </figure>
  );
}
