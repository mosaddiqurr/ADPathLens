import { motion } from "motion/react";
import type { ReactNode } from "react";
import { useAppearance } from "../../features/appearance/AppearanceContext";

export function Reveal({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const { reduceMotion } = useAppearance();
  const instant = reduceMotion || typeof IntersectionObserver === "undefined";
  if (instant) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={instant ? false : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.08 }}
      transition={{
        duration: instant ? 0 : 0.65,
        delay,
        ease: [0.22, 1, 0.36, 1],
      }}
    >
      {children}
    </motion.div>
  );
}
