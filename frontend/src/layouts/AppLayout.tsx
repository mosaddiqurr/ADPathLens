import { ArrowLeftRight, Home, Info } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import logo from "../../../assets/logo-authzdiff.png";

export function AppLayout() {
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <aside className="sidebar">
      <NavLink className="brand" to="/" aria-label="AuthZDiff home">
        <img src={logo} alt="" /><span>AuthZDiff<small>Authorization comparison</small></span>
      </NavLink>
      <nav aria-label="Primary navigation">
        <NavLink end to="/"><Home size={17} aria-hidden="true" />Home</NavLink>
        <NavLink to="/compare"><ArrowLeftRight size={17} aria-hidden="true" />Compare</NavLink>
        <NavLink to="/about"><Info size={17} aria-hidden="true" />About</NavLink>
      </nav>
      <div className="sidebar-footer"><span>Before + After</span><small>Understand access changes.</small></div>
    </aside>
    <div className="main-area"><Outlet /></div>
  </div>;
}
