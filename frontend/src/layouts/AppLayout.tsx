import {
  Activity,
  BookOpenCheck,
  FileText,
  FolderKanban,
  LogOut,
  Network,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth();
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <span className="brand-icon" aria-hidden="true">
            <Network size={21} />
          </span>
          <span>ADPathLens</span>
        </NavLink>
        <nav aria-label="Primary navigation">
          <NavLink to="/"><Activity size={18} />Dashboard</NavLink>
          <NavLink to="/workspaces"><FolderKanban size={18} />Workspaces</NavLink>
          <NavLink to="/demo"><BookOpenCheck size={18} />Guided demo</NavLink>
          {user?.role === "administrator" && (
            <>
              <NavLink to="/admin/audit"><FileText size={18} />Audit</NavLink>
              <NavLink to="/admin/settings"><Settings size={18} />Settings</NavLink>
            </>
          )}
        </nav>
        <div className="sidebar-footer">
          <div>
            <strong>{user?.display_name}</strong>
            <span>{user?.role}</span>
          </div>
          <button className="icon-button" onClick={() => void signOut()} aria-label="Sign out">
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span><ShieldCheck size={17} />Defensive analysis workspace</span>
          <span className="authorized-pill">Synthetic or authorized data only</span>
        </header>
        <main id="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
