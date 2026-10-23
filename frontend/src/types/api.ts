export type User = {
  id: string;
  email: string;
  display_name: string;
  role: "administrator" | "analyst" | "viewer";
  is_active: boolean;
};

export type Workspace = {
  id: string;
  name: string;
  description: string;
};

export type Project = {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  status: string;
};

export type ProjectStatistics = {
  project_id: string;
  latest_import_at: string | null;
  import_count: number;
  snapshot_count: number;
  node_count: number;
  relationship_count: number;
  finding_count: number;
  path_count: number;
  remediation_plan_count: number;
  comparison_count: number;
  report_count: number;
  recent_activity: Array<{
    id: string;
    action: string;
    summary: string;
    outcome: string;
    created_at: string;
  }>;
};

export type Dataset = {
  id: string;
  project_id: string;
  name: string;
  source_type: string;
  import_status: string;
  progress_percent: number;
  node_count: number;
  relationship_count: number;
  warning_count: number;
  rejected_record_count: number;
  data_hash: string;
};

export type Snapshot = {
  id: string;
  project_id: string;
  dataset_id: string | null;
  parent_snapshot_id: string | null;
  name: string;
  snapshot_type: string;
  version: number;
  revision: number;
  created_at: string;
};

export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type DirectoryNode = {
  id: string;
  snapshot_id: string;
  external_id: string;
  node_type: string;
  name: string;
  display_name: string;
  description: string;
  domain_name: string | null;
  enabled: boolean;
  high_value: boolean;
  privileged: boolean;
  risk_level: string;
  stable_fingerprint: string;
  first_seen_at: string;
  last_seen_at: string;
};

export type DirectoryRelationship = {
  id: string;
  snapshot_id: string;
  external_id: string;
  source_node_id: string;
  target_node_id: string;
  relationship_type: string;
  active: boolean;
  inherited: boolean;
  confidence: string;
  risk_weight: number;
  description: string;
  stable_fingerprint: string;
  first_seen_at: string;
  last_seen_at: string;
};

export type GraphPayload = {
  nodes: DirectoryNode[];
  relationships: DirectoryRelationship[];
  truncated: boolean;
  rendered_node_count: number;
  rendered_relationship_count: number;
};

export type PathStep = {
  position: number;
  source_node_id: string;
  source_name: string;
  source_type: string;
  relationship_id: string;
  relationship_type: string;
  target_node_id: string;
  target_name: string;
  target_type: string;
  step_explanation: string;
  remediation_summary: string;
  confidence: string;
  risk_weight: number;
  evidence: Record<string, unknown>;
};

export type PathResult = {
  id: string;
  rank: number;
  total_weight: number;
  hop_count: number;
  risk_score: number;
  severity: string;
  scoring_components: Record<string, unknown>;
  confidence: string;
  explanation: string;
  limitations: string;
  steps: PathStep[];
};

export type Analysis = {
  id: string;
  snapshot_id: string;
  algorithm: string;
  start_node_id?: string;
  target_node_id?: string | null;
  maximum_depth?: number;
  request_parameters?: Record<string, unknown>;
  status: string;
  path_count: number;
  truncated: boolean;
  paths: PathResult[];
};

export type Finding = {
  id: string;
  project_id: string;
  snapshot_id: string;
  title: string;
  category: string;
  severity: string;
  confidence: string;
  internal_score: number;
  priority: string;
  status: string;
  description: string;
  technical_explanation: string;
  impact: string;
  evidence: Record<string, unknown>;
  contributing_signals: string[];
  reducing_signals: string[];
  remediation: string;
  validation_steps: string[];
  limitations: string;
  reviewer_notes: string;
  stable_fingerprint: string;
  first_seen_at: string;
  last_seen_at: string;
  recurrence_count: number;
};

export type RemediationPlan = {
  id: string;
  project_id: string;
  source_snapshot_id: string;
  name: string;
  description: string;
  status: string;
};

export type Comparison = {
  id: string;
  project_id: string;
  before_snapshot_id: string;
  after_snapshot_id: string;
  nodes_added: number;
  nodes_removed: number;
  nodes_changed: number;
  nodes_unchanged: number;
  relationships_added: number;
  relationships_removed: number;
  relationships_changed: number;
  relationships_unchanged: number;
  paths_added: number;
  paths_removed: number;
  paths_unchanged: number;
  findings_added: number;
  findings_resolved: number;
  findings_reopened: number;
  severity_changes: number;
  status: string;
  remediation_outcomes: Record<string, unknown>;
  risk_score_before: number;
  risk_score_after: number;
};

export type Report = {
  id: string;
  project_id: string;
  snapshot_id: string | null;
  comparison_id: string | null;
  report_type: string;
  format: string;
  status: string;
  file_name: string;
  file_hash: string;
  size_bytes: number;
  generated_at: string;
};
