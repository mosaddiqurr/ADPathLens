import { memo, useEffect, useRef } from "react";
import { useAppearance } from "../../features/appearance/AppearanceContext";

/** Ambient topology; all drawing stays outside React's render cycle. */
export const NetworkBackdrop = memo(function NetworkBackdrop() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const { theme, reduceMotion } = useAppearance();
  useEffect(() => {
    if (!canvas.current || typeof CanvasRenderingContext2D === "undefined")
      return;
    const element = canvas.current;
    const context = element.getContext("2d");
    if (!context) return;
    let frame = 0;
    let width = 0;
    let height = 0;
    let last = 0;
    let time = 0;
    let scrollTimer = 0;
    let scrolling = false;
    const interval = 1000 / 24;
    const root = document.documentElement;
    const dark = theme === "dark";
    const nodes = Array.from(
      { length: window.innerWidth < 768 ? 20 : 32 },
      (_, index) => ({
        x: ((index * 137.508 + 53) % 997) / 997,
        y: ((index * 233.231 + 101) % 991) / 991,
        phase: index * 1.71,
      }),
    );
    const points = nodes.map(() => ({ x: 0, y: 0 }));
    function paint() {
      if (!context) return;
      context.clearRect(0, 0, width, height);
      nodes.forEach((node, index) => {
        points[index].x =
          node.x * width + Math.sin(time * 0.13 + node.phase) * 24;
        points[index].y =
          node.y * height + Math.cos(time * 0.11 + node.phase) * 19;
      });
      const reach = Math.min(width * 0.23, 270);
      const reachSquared = reach * reach;
      for (let i = 0; i < points.length; i++) {
        const point = points[i];
        for (let j = i + 1; j < points.length; j++) {
          const other = points[j];
          const dx = point.x - other.x;
          const dy = point.y - other.y;
          const distanceSquared = dx * dx + dy * dy;
          if (distanceSquared > reachSquared) continue;
          const distance = Math.sqrt(distanceSquared);
          context.strokeStyle = dark
            ? `rgba(155,161,171,${(1 - distance / reach) * 0.15})`
            : `rgba(85,90,99,${(1 - distance / reach) * 0.12})`;
          context.lineWidth = 0.65;
          context.beginPath();
          context.moveTo(point.x, point.y);
          context.lineTo(other.x, other.y);
          context.stroke();
          if (i % 9 === 0 && j % 4 === 0) {
            const progress = (time * 0.055 + i * 0.13) % 1;
            context.fillStyle = dark
              ? "rgba(224,180,105,.48)"
              : "rgba(151,96,24,.3)";
            context.beginPath();
            context.arc(
              point.x + (other.x - point.x) * progress,
              point.y + (other.y - point.y) * progress,
              1.8,
              0,
              Math.PI * 2,
            );
            context.fill();
          }
        }
        context.fillStyle = dark
          ? "rgba(188,194,204,.2)"
          : "rgba(79,88,105,.2)";
        context.beginPath();
        context.arc(point.x, point.y, 1.4, 0, Math.PI * 2);
        context.fill();
      }
    }
    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      const ratio = Math.min(
        window.devicePixelRatio || 1,
        width < 768 ? 1 : 1.25,
      );
      element.width = width * ratio;
      element.height = height * ratio;
      context?.setTransform(ratio, 0, 0, ratio, 0, 0);
      paint();
    }
    function draw(now: number) {
      const elapsed = now - last;
      if (elapsed >= interval) {
        time += Math.min(elapsed / 1000, 0.1);
        last = now - (elapsed % interval);
        paint();
      }
      frame = requestAnimationFrame(draw);
    }
    function visibility() {
      cancelAnimationFrame(frame);
      frame = 0;
      const running = !document.hidden && !reduceMotion && !scrolling;
      element.dataset.animation = reduceMotion
        ? "static"
        : running
          ? "running"
          : "suspended";
      if (running) {
        last = performance.now();
        frame = requestAnimationFrame(draw);
      }
    }
    function scroll() {
      if (reduceMotion) return;
      if (!scrolling) {
        scrolling = true;
        root.dataset.scrolling = "true";
        visibility();
      }
      window.clearTimeout(scrollTimer);
      scrollTimer = window.setTimeout(() => {
        scrolling = false;
        delete root.dataset.scrolling;
        visibility();
      }, 160);
    }
    resize();
    visibility();
    window.addEventListener("resize", resize);
    window.addEventListener("scroll", scroll, { passive: true });
    document.addEventListener("visibilitychange", visibility);
    return () => {
      cancelAnimationFrame(frame);
      window.clearTimeout(scrollTimer);
      delete root.dataset.scrolling;
      window.removeEventListener("resize", resize);
      window.removeEventListener("scroll", scroll);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [theme, reduceMotion]);
  return (
    <canvas ref={canvas} className="network-backdrop" aria-hidden="true" />
  );
});
