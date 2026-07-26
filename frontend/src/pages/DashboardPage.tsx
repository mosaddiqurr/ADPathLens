import { ArrowRight, Database, FolderKanban, Network, Plus } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, errorMessage } from "../api/client";
import { StatusMessage } from "../components/common/StatusMessage";
import { useAuth } from "../features/auth/AuthContext";
import type { Project, Workspace } from "../types/api";

export function DashboardPage({ workspaceOnly = false }: { workspaceOnly?: boolean }) {
  const { user } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [workspaceName, setWorkspaceName] = useState("");
  const [projectName, setProjectName] = useState("");
  const [workspaceId, setWorkspaceId] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const [workspaceData, projectData] = await Promise.all([
        api<Workspace[]>("/workspaces"),
        api<Project[]>("/projects"),
      ]);
      setWorkspaces(workspaceData);
      setProjects(projectData);
      setWorkspaceId((current) => current || workspaceData[0]?.id || "");
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createWorkspace(event: FormEvent) {
    event.preventDefault();
    try {
      await api<Workspace>("/workspaces", {
        method: "POST",
        json: { name: workspaceName, description: "Defensive AD analysis workspace" },
      });
      setWorkspaceName("");
      setMessage("Workspace created.");
      await load();
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  async function createProject(event: FormEvent) {
    event.preventDefault();
    try {
      await api<Project>("/projects", {
        method: "POST",
        json: {
          workspace_id: workspaceId,
          name: projectName,
          description: "Synthetic or explicitly authorized assessment",
        },
      });
      setProjectName("");
      setMessage("Project created.");
      await load();
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{workspaceOnly ? "Organization" : "Risk workbench"}</p>
          <h1>{workspaceOnly ? "Workspaces" : `Welcome, ${user?.display_name}`}</h1>
          <p>Every project is isolated by workspace membership and server-side ownership checks.</p>
        </div>
        <div className="summary-badge"><Network size={20} />Local-first</div>
      </div>
      <StatusMessage message={message} tone={message.includes("created") ? "success" : "info"} />
      <div className="metric-grid">
        <article className="metric-card"><span>Workspaces</span><strong>{workspaces.length}</strong><FolderKanban /></article>
        <article className="metric-card"><span>Projects</span><strong>{projects.length}</strong><Database /></article>
        <article className="metric-card"><span>Access</span><strong>{user?.role}</strong><span className="metric-small">RBAC enforced</span></article>
      </div>
      {user?.role !== "viewer" && (
        <div className="two-column">
          <section className="panel">
            <div className="panel-heading"><h2>New workspace</h2><Plus size={19} /></div>
            <form onSubmit={(event) => void createWorkspace(event)} className="form-stack">
              <label>Name<input value={workspaceName} onChange={(event) => setWorkspaceName(event.target.value)} required minLength={2} /></label>
              <button className="secondary-button">Create workspace</button>
            </form>
          </section>
          <section className="panel">
            <div className="panel-heading"><h2>New project</h2><Plus size={19} /></div>
            <form onSubmit={(event) => void createProject(event)} className="form-stack">
              <label>Workspace<select value={workspaceId} onChange={(event) => setWorkspaceId(event.target.value)} required>
                {workspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
              </select></label>
              <label>Name<input value={projectName} onChange={(event) => setProjectName(event.target.value)} required minLength={2} /></label>
              <button className="secondary-button">Create project</button>
            </form>
          </section>
        </div>
      )}
      {!workspaceOnly && (
        <section className="panel">
          <div className="panel-heading"><h2>Recent projects</h2><span>{projects.length} total</span></div>
          <div className="card-list">
            {projects.map((project) => (
              <Link to={`/projects/${project.id}`} className="project-card" key={project.id}>
                <div><strong>{project.name}</strong><p>{project.description || "No description"}</p></div>
                <ArrowRight />
              </Link>
            ))}
            {!projects.length && <p className="empty-state">Create a project to begin an authorized import.</p>}
          </div>
        </section>
      )}
    </div>
  );
}

