import { LogOut, ShieldCheck } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import type { User } from "../types";
import { Button } from "../components/Ui";

export function AppLayout({
  user,
  onLogout,
}: {
  user: User;
  onLogout: () => Promise<void>;
}) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="topbar">
        <NavLink className="brand" to="/">
          <ShieldCheck aria-hidden="true" />
          <span>
            <strong>AuthZDiff</strong>
            <small>Authorization comparison</small>
          </span>
        </NavLink>
        <nav aria-label="Primary navigation">
          <NavLink to="/">Dashboard</NavLink>
          {user.role === "administrator" && <NavLink to="/audit">Audit</NavLink>}
        </nav>
        <div className="account">
          <span>
            <strong>{user.display_name}</strong>
            <small>{user.role}</small>
          </span>
          <Button variant="secondary" onClick={() => void onLogout()} aria-label="Sign out">
            <LogOut aria-hidden="true" size={16} /> Sign out
          </Button>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
