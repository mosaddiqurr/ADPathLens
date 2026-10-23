import { LogOut, Menu, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { NetworkBackdrop } from "../components/visual/NetworkBackdrop";
import { AppearanceControls } from "../components/visual/AppearanceControls";
import { motion } from "motion/react";
import { useAppearance } from "../features/appearance/AppearanceContext";
const links = [
  ["/", "Home"],
  ["/analyze", "Analyze"],
  ["/results", "Results"],
  ["/about", "About"],
] as const;
export function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, localMode, signOut } = useAuth();
  const { reduceMotion } = useAppearance();
  const [menuOpen, setMenuOpen] = useState(false);
  const menu = useRef<HTMLButtonElement>(null);
  const location = useLocation();
  useEffect(() => {
    setMenuOpen(false);
    window.scrollTo(0, 0);
    const label =
      links.find(([url]) => url === location.pathname)?.[1] ?? "ADPathLens";
    document.title = `${label} · ADPathLens`;
  }, [location.pathname]);
  useEffect(() => {
    if (!menuOpen) return;
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuOpen(false);
        menu.current?.focus();
      }
    }
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [menuOpen]);
  return (
    <div className="product-shell">
      <NetworkBackdrop />
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="product-header">
        <div className="header-inner">
          <NavLink exact to="/" className="product-brand">
            <img src="/logo.png" alt="" width="34" height="34" />
            <span>ADPathLens</span>
          </NavLink>
          <button
            ref={menu}
            className="menu-toggle"
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            aria-controls="primary-navigation"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? <X size={21} /> : <Menu size={21} />}
          </button>
          <nav
            id="primary-navigation"
            className={`header-nav ${menuOpen ? "is-open" : ""}`}
            aria-label="Primary navigation"
          >
            {links.map(([to, label]) => (
              <NavLink exact to={to} key={to}>
                {label}
                {location.pathname === to && (
                  <motion.span
                    className="nav-active-marker"
                    layoutId="active-navigation"
                    transition={{
                      duration: reduceMotion ? 0 : 0.28,
                      ease: [0.22, 1, 0.36, 1],
                    }}
                  />
                )}
              </NavLink>
            ))}
          </nav>
          <AppearanceControls />
          {user && !localMode && (
            <button
              className="icon-button"
              aria-label="Sign out"
              onClick={() => void signOut()}
            >
              <LogOut size={16} />
            </button>
          )}
        </div>
      </header>
      <main id="main-content" tabIndex={-1}>
        <motion.div
          key={location.pathname}
          className="route-content"
          initial={reduceMotion ? false : { opacity: 0, y: 9 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        >
          {children}
        </motion.div>
      </main>
      <footer className="product-footer">
        <span className="footer-brand">
          ADPathLens <span>Understand access. Reduce exposure.</span>
        </span>
        <NavLink to="/about">Methodology & limitations</NavLink>
      </footer>
    </div>
  );
}
