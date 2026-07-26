import { AlertTriangle, CheckCircle2, FlaskConical, Plus, Wrench } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { api, errorMessage } from "../api/client";
import { ProjectNav } from "../components/common/ProjectNav";
import { StatusMessage } from "../components/common/StatusMessage";
import { useProjectData } from "../hooks/useProjectData";
import type { DirectoryRelationship, Page, RemediationPlan } from "../types/api";

type Action = {
  id: string;
  action_type: string;
  target_relationship_id: string | null;
  description: string;
  priority: string;
  status: string;
};
type Preview = {
  source_node_count: number;
  preview_node_count: number;
  source_relationship_count: number;
  preview_relationship_count: number;
  actions_applied: number;
  warnings: string[];
};

export function RemediationPage() {
  const { projectId = "" } = useParams<{ projectId: string }>();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const { project, snapshots, reload } = useProjectData(projectId);
  const [plans, setPlans] = useState<RemediationPlan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState("");
  const [sourceSnapshot, setSourceSnapshot] = useState("");
  const [name, setName] = useState("Reduce modeled privilege exposure");
  const [relationships, setRelationships] = useState<DirectoryRelationship[]>([]);
  const [relationshipId, setRelationshipId] = useState("");
  const [actionType, setActionType] = useState("remove_relationship");
  const [actions, setActions] = useState<Action[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [derivedId, setDerivedId] = useState("");
  const [message, setMessage] = useState("");

  async function loadPlans(selectPlan?: string) {
    try {
      const data = await api<RemediationPlan[]>(`/projects/${projectId}/remediation-plans`);
      setPlans(data);
      const next = selectPlan || selectedPlan || data[0]?.id || "";
      if (next) setSelectedPlan(next);
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  useEffect(() => {
    setSourceSnapshot((current) => current || snapshots[0]?.id || "");
  }, [snapshots]);
  useEffect(() => {
    void loadPlans();
    // load only when the project changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    const plan = plans.find((item) => item.id === selectedPlan);
    if (!plan) return;
    Promise.all([
      api<Action[]>(`/remediation-plans/${plan.id}/actions`),
      api<Page<DirectoryRelationship>>(`/snapshots/${plan.source_snapshot_id}/relationships?page_size=100`),
    ])
      .then(([actionData, relationshipPage]) => {
        setActions(actionData);
        setRelationships(relationshipPage.items);
        setRelationshipId((current) => current || relationshipPage.items[0]?.id || "");
      })
      .catch((reason) => setMessage(errorMessage(reason)));
  }, [plans, selectedPlan]);

  async function createPlan(event: FormEvent) {
    event.preventDefault();
    try {
      const plan = await api<RemediationPlan>(`/projects/${projectId}/remediation-plans`, {
        method: "POST",
        json: { source_snapshot_id: sourceSnapshot, name, description: "Simulation only; no directory changes are executed." },
      });
      setMessage("Remediation plan created.");
      await loadPlans(plan.id);
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  async function addAction(event: FormEvent) {
    event.preventDefault();
    if (!selectedPlan) return;
    try {
      await api<Action>(`/remediation-plans/${selectedPlan}/actions`, {
        method: "POST",
        json: {
          finding_id: searchParams.get("finding"),
          action_type: actionType,
          target_relationship_id: relationshipId,
          description: "Remove or disable the selected unnecessary modeled permission.",
          proposed_change: { active: false },
          priority: "high",
        },
      });
      setMessage("Simulation action added.");
      const data = await api<Action[]>(`/remediation-plans/${selectedPlan}/actions`);
      setActions(data);
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  async function previewPlan() {
    try {
      const data = await api<Preview>(`/remediation-plans/${selectedPlan}/preview`, { method: "POST" });
      setPreview(data);
      setMessage("Simulation preview is ready.");
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  async function createSnapshot() {
    try {
      const data = await api<{ id: string; name: string }>(`/remediation-plans/${selectedPlan}/create-snapshot`, { method: "POST" });
      setDerivedId(data.id);
      setMessage(`Created immutable derived snapshot: ${data.name}`);
      await reload();
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  async function retest() {
    if (!derivedId) return;
    try {
      const result = await api<{ total: number }>(`/snapshots/${derivedId}/risk-scan`, { method: "POST" });
      setMessage(`Retest completed with ${result.total} draft finding(s) on the derived snapshot.`);
    } catch (reason) {
      setMessage(errorMessage(reason));
    }
  }

  const selectedPlanRecord = plans.find((item) => item.id === selectedPlan);
  return (
    <div className="page">
      <div className="page-heading"><div><p className="eyebrow">Defensive simulation</p><h1>{project?.name ?? "Project"} remediation</h1><p>Proposals create previews and immutable derived snapshots. They never make Active Directory changes.</p></div><FlaskConical size={34} /></div>
      <ProjectNav projectId={projectId} snapshotId={snapshots[0]?.id} />
      <div className="notice notice-warning" role="note"><AlertTriangle /> <strong>Simulation only. No changes have been made to Active Directory.</strong></div>
      <StatusMessage message={message} tone={message.includes("Created") || message.includes("ready") ? "success" : "info"} />
      <div className="three-column">
        <section className="panel">
          <div className="panel-heading"><h2>1 · Plan</h2><Plus /></div>
          <form className="form-stack" onSubmit={(event) => void createPlan(event)}>
            <label>Source snapshot<select value={sourceSnapshot} onChange={(event) => setSourceSnapshot(event.target.value)}>{snapshots.map((snapshot) => <option key={snapshot.id} value={snapshot.id}>{snapshot.name} · v{snapshot.version}</option>)}</select></label>
            <label>Plan name<input value={name} onChange={(event) => setName(event.target.value)} minLength={3} required /></label>
            <button className="secondary-button">Create plan</button>
          </form>
          {plans.length > 0 && <label>Active plan<select value={selectedPlan} onChange={(event) => { setSelectedPlan(event.target.value); setRelationshipId(""); setPreview(null); }}>{plans.map((plan) => <option value={plan.id} key={plan.id}>{plan.name}</option>)}</select></label>}
        </section>
        <section className="panel">
          <div className="panel-heading"><h2>2 · Actions</h2><Wrench /></div>
          {selectedPlanRecord ? <form className="form-stack" onSubmit={(event) => void addAction(event)}>
            <label>Typed change<select value={actionType} onChange={(event) => setActionType(event.target.value)}><option value="remove_relationship">Remove relationship</option><option value="disable_relationship">Disable relationship</option><option value="remove_password_reset">Remove password reset right</option><option value="remove_local_admin">Remove local admin</option><option value="remove_gpo_control">Remove GPO control</option><option value="remove_privileged_session">Remove stale session evidence</option></select></label>
            <label>Stored relationship<select value={relationshipId} onChange={(event) => setRelationshipId(event.target.value)}>{relationships.map((relationship) => <option value={relationship.id} key={relationship.id}>{relationship.external_id} · {relationship.relationship_type}</option>)}</select></label>
            <button className="secondary-button" disabled={!relationshipId}>Add simulated action</button>
          </form> : <p className="empty-state">Create a plan first.</p>}
          <ol className="action-list">{actions.map((action) => <li key={action.id}><strong>{action.action_type}</strong><p>{action.description}</p><small>{action.status} · {action.priority}</small></li>)}</ol>
        </section>
        <section className="panel">
          <div className="panel-heading"><h2>3 · Preview</h2><CheckCircle2 /></div>
          <button className="secondary-button" disabled={!actions.length} onClick={() => void previewPlan()}>Preview graph changes</button>
          {preview && <div className="preview-metrics"><div><span>Nodes</span><strong>{preview.source_node_count} → {preview.preview_node_count}</strong></div><div><span>Relationships</span><strong>{preview.source_relationship_count} → {preview.preview_relationship_count}</strong></div><div><span>Actions</span><strong>{preview.actions_applied}</strong></div></div>}
          <button className="primary-button" disabled={!preview} onClick={() => void createSnapshot()}>Create derived snapshot</button>
          {derivedId && <div className="form-stack"><button className="secondary-button" onClick={() => void retest()}>Retest derived snapshot</button><Link className="text-link" to={`/projects/${projectId}/comparisons`}>Compare remediation outcome →</Link></div>}
        </section>
      </div>
    </div>
  );
}
