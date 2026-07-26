import { ArrowRight, Database, Network, ShieldAlert } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { ProjectNav } from "../components/common/ProjectNav";
import { StatusMessage } from "../components/common/StatusMessage";
import { useProjectData } from "../hooks/useProjectData";

export function ProjectPage() {
  const { projectId = "" } = useParams<{ projectId: string }>();
  const { project, snapshots, datasets, error } = useProjectData(projectId);
  const latest = snapshots[0];
  return (
    <div className="page">
      <div className="page-heading">
        <div><p className="eyebrow">Project</p><h1>{project?.name ?? "Loading…"}</h1><p>{project?.description}</p></div>
        <span className="summary-badge">{project?.status}</span>
      </div>
      <ProjectNav projectId={projectId} snapshotId={latest?.id} />
      <StatusMessage message={error} tone="danger" />
      <div className="metric-grid">
        <article className="metric-card"><span>Datasets</span><strong>{datasets.length}</strong><Database /></article>
        <article className="metric-card"><span>Snapshots</span><strong>{snapshots.length}</strong><Network /></article>
        <article className="metric-card"><span>Latest revision</span><strong>{latest?.revision ?? "—"}</strong><ShieldAlert /></article>
      </div>
      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><h2>Snapshots</h2><Link className="text-link" to={`/projects/${projectId}/imports`}>Import data</Link></div>
          <div className="card-list">
            {snapshots.map((snapshot) => (
              <Link className="project-card" to={`/snapshots/${snapshot.id}/graph`} key={snapshot.id}>
                <div><strong>{snapshot.name}</strong><p>Version {snapshot.version} · {snapshot.snapshot_type}</p></div><ArrowRight />
              </Link>
            ))}
            {!snapshots.length && <p className="empty-state">Import the fictional demo or authorized data to create a snapshot.</p>}
          </div>
        </section>
        <section className="panel callout-panel">
          <p className="eyebrow">Interpretation boundary</p>
          <h2>Modeled paths require review</h2>
          <p>ADPathLens describes possible privilege relationships from imported evidence. It does not prove compromise, exploitation, or intent.</p>
          {latest && <Link className="primary-button inline-button" to={`/snapshots/${latest.id}/paths`}>Run bounded analysis <ArrowRight size={16} /></Link>}
        </section>
      </div>
    </div>
  );
}
