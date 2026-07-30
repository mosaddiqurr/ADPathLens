export interface User {
  id: string;
  email: string;
  display_name: string;
  role: "administrator" | "analyst";
  is_active: boolean;
  must_change_password: boolean;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Target {
  id: string;
  project_id: string;
  name: string;
  base_url: string;
  hostname: string;
  port: number;
  authorization_confirmed: boolean;
  lab_network_confirmed: boolean;
  allow_private_networks: boolean;
  allowed_path_prefixes: string[];
  allowed_methods: string[];
  request_budget: number;
  request_count_used: number;
  maximum_response_bytes: number;
  last_execution_at: string | null;
  concurrency_limit: number;
  authorization_expires_at: string | null;
  tls_policy: string;
  state_changes_enabled: boolean;
  local_test_target: boolean;
  is_active: boolean;
}

export interface TestSession {
  id: string;
  project_id: string;
  target_id: string;
  name: string;
  role_label: string;
  description: string;
  secret_fingerprint: string;
  is_anonymous: boolean;
  is_active: boolean;
  credential_version: number;
  expires_at: string | null;
}

export interface RequestCollection {
  id: string;
  target_id: string;
  name: string;
  description: string;
}

export interface ImportedRequest {
  id: string;
  target_id: string;
  collection_id: string;
  name: string;
  method: string;
  path: string;
  body_template: string;
  is_state_changing: boolean;
  approved_state_change: boolean;
  sensitivity: string;
}

export interface TestCase {
  id: string;
  name: string;
  target_id: string;
  imported_request_id: string;
  high_privilege_session_id: string;
  low_privilege_session_id: string;
  expected_behaviour: string;
  approved_state_change: boolean;
}

export interface Run {
  id: string;
  test_case_id: string;
  status: string;
  automated_classification: string | null;
  confidence: string | null;
  explanation: string | null;
  progress_completed: number;
  progress_total: number;
  started_at: string | null;
}

export interface Job {
  id: string;
  comparison_run_id: string;
  status: string;
  completed_count: number;
  request_count: number;
}

export interface Observation {
  id: string;
  session_id: string;
  status_code: number | null;
  content_type: string | null;
  response_length: number;
  duration_ms: number;
  access_denied_marker: boolean;
  auth_challenge: boolean;
  object_existence_marker: boolean;
  sanitized_body_hash: string | null;
  sanitized_excerpt: string | null;
  body_truncated: boolean;
  is_binary: boolean;
  error_category: string | null;
}

export interface RunDetail {
  run: Run;
  job: Job | null;
  observations: Observation[];
  difference: Record<string, unknown> | null;
  context: Record<string, unknown>;
}

export interface Finding {
  id: string;
  title: string;
  category: string;
  severity: string;
  confidence: string;
  status: string;
  priority: string;
  tags: string[];
  description: string;
  remediation: string;
  limitations: string;
  endpoint_snapshot: string;
  impact: string;
  observed_behaviour: string;
  first_seen_at: string;
  last_seen_at: string;
  recurrence_count: number;
  fingerprint: string;
}

export interface FindingEvidence {
  id: string;
  evidence_type: string;
  sanitized_excerpt: string;
  excerpt_hash: string;
  safe_metadata: Record<string, unknown>;
  created_at: string;
}

export interface FindingHistory {
  id: string;
  from_status: string | null;
  to_status: string;
  changed_by: string;
  note: string;
  created_at: string;
}

export interface FindingNote {
  id: string;
  author_id: string;
  body: string;
  created_at: string;
}

export interface Report {
  id: string;
  format: string;
  status: string;
  file_name: string;
  file_hash: string | null;
  generated_at: string;
}

export interface AuditEvent {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  user_id: string | null;
  outcome: string;
  correlation_id: string | null;
  summary: string;
  created_at: string;
}
