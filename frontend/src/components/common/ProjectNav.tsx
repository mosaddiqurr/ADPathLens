import { BarChart3, FileDown, GitCompare, Network, Route, ShieldAlert, Wrench } from "lucide-react";
import { NavLink } from "react-router-dom";

export function ProjectNav({ projectId, snapshotId }: { projectId: string; snapshotId?: string }) {
  return (
    <nav className="project-nav" aria-label="Project sections">
      <NavLink exact to={`/projects/${projectId}`}><BarChart3 size={16} />Overview</NavLink>
      <NavLink to={`/projects/${projectId}/imports`}><FileDown size={16} />Imports</NavLink>
      {snapshotId && <NavLink to={`/snapshots/${snapshotId}/graph`}><Network size={16} />Graph</NavLink>}
      {snapshotId && <NavLink to={`/snapshots/${snapshotId}/paths`}><Route size={16} />Paths</NavLink>}
      <NavLink to={`/projects/${projectId}/findings`}><ShieldAlert size={16} />Findings</NavLink>
      <NavLink to={`/projects/${projectId}/remediation`}><Wrench size={16} />Remediation</NavLink>
      <NavLink to={`/projects/${projectId}/comparisons`}><GitCompare size={16} />Compare</NavLink>
      <NavLink to={`/projects/${projectId}/reports`}><FileDown size={16} />Reports</NavLink>
    </nav>
  );
}
