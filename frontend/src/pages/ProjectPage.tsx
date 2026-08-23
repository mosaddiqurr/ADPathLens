import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, useParams } from "react-router-dom";

import { api, jsonBody } from "../api/client";
import { Button, Empty, ErrorNotice, Field, Panel, Status } from "../components/Ui";
import type {
  Finding,
  FindingEvidence,
  FindingHistory,
  FindingNote,
  ImportedRequest,
  Job,
  Project,
  Report,
  RequestCollection,
  Run,
  RunDetail,
  Target,
  TestCase,
  TestSession,
} from "../types";

const AUTH_ACK =
  "I confirm that I own this target or have explicit authorization to test it.";
const LAB_ACK =
  "I confirm this private or loopback destination is an authorized local laboratory.";
const sections = [
  ["targets", "Targets"],
  ["profiles", "Profiles"],
  ["requests", "Requests"],
  ["comparisons", "Comparisons"],
  ["findings", "Findings"],
  ["reports", "Reports"],
  ["demo", "Guided demo"],
] as const;

function formText(data: FormData, name: string, fallback = ""): string {
  const value = data.get(name);
  return typeof value === "string" ? value : fallback;
}

function StructuredData({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null || value === undefined) return <span>Not recorded</span>;
  if (typeof value === "string") return <code>{value}</code>;
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return <code>{value.toString()}</code>;
  }
  if (typeof value !== "object") return <span>Unsupported value</span>;
  if (depth >= 5) return <span>Additional nested data omitted</span>;
  if (Array.isArray(value)) {
    const items = value as unknown[];
    if (!items.length) return <span>None</span>;
    return (
      <ul className="structured-list">
        {items.slice(0, 100).map((item, index) => (
          <li key={index}><StructuredData value={item} depth={depth + 1} /></li>
        ))}
      </ul>
    );
  }
  const entries = Object.entries(value as Record<string, unknown>);
  if (!entries.length) return <span>None</span>;
  return (
    <dl className="structured-data">
      {entries.slice(0, 100).map(([key, item]) => (
        <div key={key}>
          <dt>{key.replaceAll("_", " ")}</dt>
          <dd><StructuredData value={item} depth={depth + 1} /></dd>
        </div>
      ))}
    </dl>
  );
}

function useWorkspace(projectId: string) {
  return {
    project: useQuery({
      queryKey: ["project", projectId],
      queryFn: () => api<Project>(`/projects/${projectId}`),
    }),
    targets: useQuery({
      queryKey: ["targets", projectId],
      queryFn: () => api<Target[]>(`/projects/${projectId}/targets`),
    }),
    profiles: useQuery({
      queryKey: ["profiles", projectId],
      queryFn: () => api<TestSession[]>(`/projects/${projectId}/sessions`),
    }),
    collections: useQuery({
      queryKey: ["collections", projectId],
      queryFn: () => api<RequestCollection[]>(`/projects/${projectId}/request-collections`),
    }),
    requests: useQuery({
      queryKey: ["requests", projectId],
      queryFn: () => api<ImportedRequest[]>(`/projects/${projectId}/requests`),
    }),
    cases: useQuery({
      queryKey: ["test-cases", projectId],
      queryFn: () => api<TestCase[]>(`/projects/${projectId}/test-cases`),
    }),
    runs: useQuery({
      queryKey: ["runs", projectId],
      queryFn: () => api<Run[]>(`/projects/${projectId}/runs`),
      refetchInterval: (query) =>
        query.state.data?.some((run) =>
          ["queued", "claimed", "running", "cancelling"].includes(run.status)
        )
          ? 1000
          : false,
    }),
    findings: useQuery({
      queryKey: ["findings", projectId],
      queryFn: () => api<Finding[]>(`/projects/${projectId}/findings`),
    }),
    reports: useQuery({
      queryKey: ["reports", projectId],
      queryFn: () => api<Report[]>(`/projects/${projectId}/reports`),
    }),
  };
}

function TargetSection({
  projectId,
  targets,
}: {
  projectId: string;
  targets: Target[];
}) {
  const client = useQueryClient();
  const [selected, setSelected] = useState<string>();
  const chosen = targets.find((target) => target.id === selected);
  const invalidate = () => client.invalidateQueries({ queryKey: ["targets", projectId] });
  const create = useMutation({
    mutationFn: (payload: object) =>
      api<Target>(`/projects/${projectId}/targets`, {
        method: "POST",
        ...jsonBody(payload),
      }),
    onSuccess: async (target) => {
      setSelected(target.id);
      await invalidate();
    },
  });
  const action = useMutation({
    mutationFn: ({ path, payload, method = "POST" }: { path: string; payload: object; method?: string }) =>
      api<unknown>(path, { method, ...jsonBody(payload) }),
    onSuccess: async (value) => {
      if (value && typeof value === "object" && "id" in value) {
        const returned = value as Target;
        client.setQueryData<Target[]>(["targets", projectId], (current = []) =>
          current.map((item) => item.id === returned.id ? returned : item),
        );
      }
      await invalidate();
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const methods = formText(data, "methods", "GET,HEAD")
      .split(",")
      .map((value) => value.trim().toUpperCase())
      .filter(Boolean);
    create.mutate({
      name: data.get("name"),
      base_url: data.get("base_url"),
      allowed_path_prefixes: formText(data, "paths", "/")
        .split(",")
        .map((value) => value.trim()),
      allowed_methods: methods,
      local_test_target: data.get("local_test_target") === "on",
      state_changes_enabled: methods.some((method) =>
        ["POST", "PUT", "PATCH", "DELETE"].includes(method),
      ),
      request_budget: Number(data.get("budget") || 25),
      concurrency_limit: 2,
      timeout_seconds: 10,
      per_run_timeout_seconds: 60,
      follow_redirects: false,
      maximum_redirects: 3,
      tls_policy: "strict",
    });
  }

  function allowlist(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosen) return;
    const data = new FormData(event.currentTarget);
    action.mutate({
      path: `/targets/${chosen.id}/allowlist`,
      payload: {
        entry_type: data.get("entry_type"),
        value: data.get("value"),
        allowed_port: Number(data.get("port")),
        notes: "Added through the explicit target-policy workflow.",
      },
    });
  }

  function updatePolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosen) return;
    const data = new FormData(event.currentTarget);
    action.mutate({
      path: `/targets/${chosen.id}`,
      method: "PATCH",
      payload: {
        allowed_methods: formText(data, "methods")
          .split(",")
          .map((value) => value.trim().toUpperCase())
          .filter(Boolean),
        allowed_path_prefixes: formText(data, "paths")
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        request_budget: Number(data.get("budget")),
        maximum_response_bytes: Number(data.get("maximum_response_bytes")),
        tls_policy: formText(data, "tls_policy"),
        authorization_expires_at: formText(data, "expires_at")
          ? new Date(formText(data, "expires_at")).toISOString()
          : null,
      },
    });
  }

  return (
    <>
      <ErrorNotice error={create.error ?? action.error} />
      <Panel title="Create target" description="Targets begin inactive. Authorization and an exact allowlist are separate required steps.">
        <form className="form-grid columns-2" onSubmit={submit}>
          <Field label="Target name"><input name="name" required /></Field>
          <Field label="Origin URL" hint="HTTPS, except the explicit local synthetic target.">
            <input name="base_url" type="url" placeholder="https://application.example" required />
          </Field>
          <Field label="Allowed path prefixes"><input name="paths" defaultValue="/" required /></Field>
          <Field label="Allowed methods"><input name="methods" defaultValue="GET,HEAD" required /></Field>
          <Field label="Per-run request budget"><input name="budget" type="number" min={1} max={500} defaultValue={25} /></Field>
          <label className="checkbox"><input name="local_test_target" type="checkbox" /> This is the bundled local synthetic target</label>
          <Button type="submit" disabled={create.isPending}>Create inactive target</Button>
        </form>
      </Panel>
      <Panel title="Configured targets">
        {targets.length ? (
          <div className="resource-list">
            {targets.map((target) => (
              <button
                className={target.id === selected ? "resource selected" : "resource"}
                key={target.id}
                onClick={() => { setSelected(target.id); }}
              >
                <span><strong>{target.name}</strong><small>{target.base_url}</small></span>
                <Status value={target.is_active ? "active" : "inactive"} />
              </button>
            ))}
          </div>
        ) : <Empty>No targets configured.</Empty>}
      </Panel>
      {chosen && (
        <Panel title={`Policy: ${chosen.name}`} description="Activation remains blocked until every required policy fact is present.">
          <dl className="facts">
            <div><dt>Authorization</dt><dd>{chosen.authorization_confirmed ? "confirmed" : "not confirmed"}</dd></div>
            <div><dt>Private lab</dt><dd>{chosen.lab_network_confirmed ? "confirmed" : "not enabled"}</dd></div>
            <div><dt>Methods</dt><dd>{chosen.allowed_methods.join(", ")}</dd></div>
            <div><dt>Paths</dt><dd>{chosen.allowed_path_prefixes.join(", ")}</dd></div>
            <div><dt>Budget</dt><dd>{chosen.request_count_used} of {chosen.request_budget} reserved</dd></div>
            <div><dt>Response limit</dt><dd>{chosen.maximum_response_bytes.toLocaleString()} bytes</dd></div>
            <div><dt>Authorization expiry</dt><dd>{chosen.authorization_expires_at ? new Date(chosen.authorization_expires_at).toLocaleString() : "No expiry configured"}</dd></div>
          </dl>
          <div className="button-row">
            <Button disabled={action.isPending}
              variant="secondary"
              onClick={() => { action.mutate({ path: `/targets/${chosen.id}/confirm-authorization`, payload: { acknowledgement: AUTH_ACK } }); }}
            >Confirm authorization</Button>
            {chosen.local_test_target && (
              <Button disabled={action.isPending}
                variant="secondary"
                onClick={() => { action.mutate({ path: `/targets/${chosen.id}/confirm-lab`, payload: { acknowledgement: LAB_ACK, allow_private_networks: true } }); }}
              >Confirm private lab</Button>
            )}
            <Button disabled={action.isPending}
              variant="secondary"
              onClick={() => { action.mutate({ path: `/targets/${chosen.id}/validate`, payload: {} }); }}
            >Validate DNS and policy</Button>
            <Button disabled={action.isPending}
              onClick={() => { action.mutate({ path: `/targets/${chosen.id}`, method: "PATCH", payload: { is_active: true } }); }}
            >Activate target</Button>
            <Button
              variant="danger"
              disabled={!chosen.is_active || action.isPending}
              onClick={() => { action.mutate({ path: `/targets/${chosen.id}`, method: "PATCH", payload: { is_active: false } }); }}
            >Disable target</Button>
          </div>
          <form className="form-grid columns-2" onSubmit={updatePolicy}>
            <Field label="Allowed methods"><input name="methods" defaultValue={chosen.allowed_methods.join(",")} required /></Field>
            <Field label="Allowed path prefixes"><input name="paths" defaultValue={chosen.allowed_path_prefixes.join(",")} required /></Field>
            <Field label="Lifetime request budget"><input name="budget" type="number" min={chosen.request_count_used || 1} max={500} defaultValue={chosen.request_budget} required /></Field>
            <Field label="Maximum response bytes"><input name="maximum_response_bytes" type="number" min={1024} max={10 * 1024 * 1024} defaultValue={chosen.maximum_response_bytes} required /></Field>
            <Field label="TLS policy"><select name="tls_policy" defaultValue={chosen.tls_policy}><option value="strict">Strict system trust</option><option value="custom_ca">Configured custom CA</option></select></Field>
            <Field label="Authorization expiry"><input name="expires_at" type="datetime-local" /></Field>
            <Button disabled={action.isPending} type="submit" variant="secondary">Save policy changes</Button>
          </form>
          <form className="inline-form" onSubmit={allowlist}>
            <select name="entry_type" aria-label="Allowlist entry type">
              <option value="hostname">Hostname</option>
              <option value="ip">IP address</option>
              <option value="cidr">CIDR</option>
            </select>
            <input name="value" aria-label="Allowlist value" defaultValue={chosen.hostname} required />
            <input name="port" aria-label="Allowed port" type="number" defaultValue={chosen.port} required />
            <Button disabled={action.isPending} type="submit" variant="secondary">Add exact allowlist entry</Button>
          </form>
        </Panel>
      )}
    </>
  );
}

function ProfileSection({
  projectId,
  targets,
  profiles,
}: {
  projectId: string;
  targets: Target[];
  profiles: TestSession[];
}) {
  const client = useQueryClient();
  const [selectedProfile, setSelectedProfile] = useState<string>();
  const chosenProfile = profiles.find((profile) => profile.id === selectedProfile);
  const mutation = useMutation({
    mutationFn: ({ path, payload, method = "POST" }: { path: string; payload: object; method?: string }) =>
      api<TestSession | undefined>(path, { method, ...jsonBody(payload) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["profiles", projectId] }),
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      path: `/projects/${projectId}/sessions`,
      payload: {
        target_id: data.get("target_id"),
        name: data.get("name"),
        role_label: data.get("role_label"),
        description: data.get("description"),
        is_anonymous: data.get("is_anonymous") === "on",
        authorization_header: data.get("authorization_header") || null,
        cookie_header: data.get("cookie_header") || null,
        custom_headers: [],
      },
    });
    event.currentTarget.reset();
  }
  function replaceSecret(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosenProfile) return;
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      path: `/sessions/${chosenProfile.id}/replace-secret`,
      payload: {
        authorization_header: data.get("authorization_header") || null,
        cookie_header: data.get("cookie_header") || null,
        custom_headers: [],
      },
    });
    event.currentTarget.reset();
  }
  function deleteProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosenProfile) return;
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      path: `/sessions/${chosenProfile.id}`,
      method: "DELETE",
      payload: { confirmation: data.get("confirmation") },
    });
  }
  return (
    <>
      <ErrorNotice error={mutation.error} />
      <Panel title="Create test profile" description="Credential fields are write-only. Only a keyed fingerprint is returned after creation.">
        <form className="form-grid columns-2" onSubmit={submit}>
          <Field label="Target"><select name="target_id" required>{targets.map((target) => <option value={target.id} key={target.id}>{target.name}</option>)}</select></Field>
          <Field label="Profile name"><input name="name" required /></Field>
          <Field label="Role label"><input name="role_label" placeholder="standard-user" required /></Field>
          <Field label="Description"><input name="description" /></Field>
          <Field label="Authorization value" hint="Enter once. Use a synthetic demo bearer token for the local fixture.">
            <input name="authorization_header" type="password" autoComplete="off" />
          </Field>
          <Field label="Cookie header"><input name="cookie_header" type="password" autoComplete="off" /></Field>
          <label className="checkbox"><input name="is_anonymous" type="checkbox" /> Anonymous profile (no credentials)</label>
          <Button type="submit">Store encrypted profile</Button>
        </form>
      </Panel>
      <Panel title="Masked profiles">
        {profiles.length ? <div className="table-wrap"><table><thead><tr><th>Name</th><th>Role</th><th>Fingerprint</th><th>Version</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>{profiles.map((profile) => <tr key={profile.id}><td>{profile.name}</td><td>{profile.role_label}</td><td><code>{profile.secret_fingerprint}</code></td><td>{profile.credential_version}</td><td><Status value={profile.is_active ? "active" : "revoked"} /></td><td><div className="button-row"><Button variant="secondary" onClick={() => { setSelectedProfile(profile.id); }}>Manage</Button><Button variant="danger" disabled={!profile.is_active} onClick={() => { mutation.mutate({ path: `/sessions/${profile.id}`, method: "PATCH", payload: { is_active: false } }); }}>Revoke</Button></div></td></tr>)}</tbody>
        </table></div> : <Empty>No profiles configured.</Empty>}
      </Panel>
      {chosenProfile && (
        <Panel title={`Manage ${chosenProfile.name}`} description="Existing credential values can never be revealed. Replacing them increments the credential version.">
          {!chosenProfile.is_anonymous && (
            <form className="form-grid columns-2" onSubmit={replaceSecret}>
              <Field label="Replacement authorization value"><input name="authorization_header" type="password" autoComplete="off" /></Field>
              <Field label="Replacement cookie header"><input name="cookie_header" type="password" autoComplete="off" /></Field>
              <Button type="submit">Replace secret material</Button>
            </form>
          )}
          <form className="inline-form" onSubmit={deleteProfile}>
            <input name="confirmation" aria-label={`Type ${chosenProfile.name} to confirm deletion`} placeholder={`Type ${chosenProfile.name}`} required />
            <Button type="submit" variant="danger">Delete profile</Button>
          </form>
        </Panel>
      )}
    </>
  );
}

function RequestSection({
  projectId,
  targets,
  collections,
  requests,
}: {
  projectId: string;
  targets: Target[];
  collections: RequestCollection[];
  requests: ImportedRequest[];
}) {
  const client = useQueryClient();
  const mutate = useMutation({
    mutationFn: ({ path, payload }: { path: string; payload: object }) =>
      api<unknown>(path, { method: "POST", ...jsonBody(payload) }),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["collections", projectId] }),
        client.invalidateQueries({ queryKey: ["requests", projectId] }),
      ]);
    },
  });
  function collection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    mutate.mutate({ path: `/projects/${projectId}/request-collections`, payload: { target_id: data.get("target_id"), name: data.get("name"), description: "" } });
  }
  function request(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const method = formText(data, "method");
    mutate.mutate({
      path: `/projects/${projectId}/requests/manual`,
      payload: {
        collection_id: data.get("collection_id"),
        target_id: data.get("target_id"),
        name: data.get("name"),
        method,
        path: data.get("path"),
        query_parameters: [],
        headers: [],
        body: data.get("body"),
        content_type: data.get("content_type") || null,
        approved_state_change: data.get("approved") === "on",
        expected_markers: [],
        tags: [],
        sensitivity: "internal",
      },
    });
  }
  function importCurl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    mutate.mutate({
      path: `/projects/${projectId}/requests/import-curl`,
      payload: {
        collection_id: data.get("collection_id"),
        target_id: data.get("target_id"),
        name: data.get("name"),
        command: data.get("command"),
        approved_state_change: false,
      },
    });
  }
  return (
    <>
      <ErrorNotice error={mutate.error} />
      <Panel title="Request collection">
        <form className="inline-form" onSubmit={collection}>
          <select name="target_id" aria-label="Collection target" required>{targets.map((target) => <option value={target.id} key={target.id}>{target.name}</option>)}</select>
          <input name="name" aria-label="Collection name" placeholder="Core authorization checks" required />
          <Button type="submit">Create collection</Button>
        </form>
      </Panel>
      <Panel title="Safe cURL import" description="The command is parsed as text and never executed. Shell operators, files, proxies, certificates, uploads, and host escapes are rejected.">
        <form className="form-grid columns-2" onSubmit={importCurl}>
          <Field label="Collection"><select name="collection_id" required>{collections.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></Field>
          <Field label="Target"><select name="target_id" required>{targets.map((target) => <option value={target.id} key={target.id}>{target.name}</option>)}</select></Field>
          <Field label="Request name"><input name="name" required /></Field>
          <Field label="cURL command"><textarea name="command" rows={5} placeholder="curl 'http://127.0.0.1:8021/secure/authenticated'" required /></Field>
          <Button type="submit">Parse and save safe cURL</Button>
        </form>
      </Panel>
      <Panel title="Request editor" description="Only relative paths are accepted. Host, proxy, connection, and reusable auth headers are rejected or separated.">
        <form className="form-grid columns-2" onSubmit={request}>
          <Field label="Collection"><select name="collection_id" required>{collections.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></Field>
          <Field label="Target"><select name="target_id" required>{targets.map((target) => <option value={target.id} key={target.id}>{target.name}</option>)}</select></Field>
          <Field label="Request name"><input name="name" required /></Field>
          <Field label="Method"><select name="method"><option>GET</option><option>POST</option><option>PATCH</option><option>DELETE</option></select></Field>
          <Field label="Relative path"><input name="path" defaultValue="/" required /></Field>
          <Field label="Content type"><input name="content_type" placeholder="application/json" /></Field>
          <Field label="Body template"><textarea name="body" rows={5} /></Field>
          <label className="checkbox"><input name="approved" type="checkbox" /> Approve this saved state-changing request</label>
          <Button type="submit">Save request definition</Button>
        </form>
      </Panel>
      <Panel title="Saved request definitions">
        {requests.length ? <div className="table-wrap"><table><thead><tr><th>Name</th><th>Method</th><th>Path</th><th>State change</th><th>Sensitivity</th></tr></thead><tbody>{requests.map((item) => <tr key={item.id}><td>{item.name}</td><td><code>{item.method}</code></td><td><code>{item.path}</code></td><td>{item.is_state_changing ? "Yes" : "No"}</td><td>{item.sensitivity}</td></tr>)}</tbody></table></div> : <Empty>No requests saved.</Empty>}
      </Panel>
    </>
  );
}

function ComparisonSection({
  projectId,
  targets,
  profiles,
  requests,
  cases,
  runs,
}: {
  projectId: string;
  targets: Target[];
  profiles: TestSession[];
  requests: ImportedRequest[];
  cases: TestCase[];
  runs: Run[];
}) {
  const client = useQueryClient();
  const [selectedCase, setSelectedCase] = useState<string>();
  const [selectedRun, setSelectedRun] = useState<string>();
  const preview = useQuery({
    queryKey: ["preview", selectedCase],
    queryFn: () =>
      api<Record<string, unknown>>(`/test-cases/${String(selectedCase)}/preview`),
    enabled: Boolean(selectedCase),
  });
  const detail = useQuery({
    queryKey: ["run", selectedRun],
    queryFn: () => api<RunDetail>(`/runs/${String(selectedRun)}`),
    enabled: Boolean(selectedRun),
    refetchInterval: (query) =>
      ["queued", "running", "cancelling"].includes(query.state.data?.run.status ?? "")
        ? 750
        : false,
  });
  useEffect(() => {
    if (!detail.data || !["completed", "failed", "cancelled"].includes(detail.data.run.status)) {
      return;
    }
    void Promise.all([
      client.invalidateQueries({ queryKey: ["runs", projectId] }),
      client.invalidateQueries({ queryKey: ["findings", projectId] }),
    ]);
  }, [client, detail.data, projectId]);
  const mutation = useMutation({
    mutationFn: ({ path, payload }: { path: string; payload: object }) =>
      api<TestCase | Job>(path, { method: "POST", ...jsonBody(payload) }),
    onSuccess: async (value) => {
      if ("comparison_run_id" in value) setSelectedRun(value.comparison_run_id);
      if ("expected_behaviour" in value) setSelectedCase(value.id);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["test-cases", projectId] }),
        client.invalidateQueries({ queryKey: ["runs", projectId] }),
      ]);
    },
  });
  function createCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const request = requests.find((item) => item.id === data.get("imported_request_id"));
    mutation.mutate({
      path: `/projects/${projectId}/test-cases`,
      payload: {
        target_id: data.get("target_id"),
        imported_request_id: data.get("imported_request_id"),
        name: data.get("name"),
        description: "",
        high_privilege_session_id: data.get("high_session"),
        low_privilege_session_id: data.get("low_session"),
        expected_behaviour: data.get("expectation"),
        custom_expectation: "",
        approved_state_change: Boolean(request?.is_state_changing && data.get("approved")),
        variables: [],
        ignored_json_paths: [],
        unordered_json_paths: [],
        ignored_headers: [],
        ignored_text_patterns: [],
      },
    });
  }
  const selectedDefinition = requests.find(
    (request) => request.id === cases.find((item) => item.id === selectedCase)?.imported_request_id,
  );
  return (
    <>
      <ErrorNotice error={mutation.error ?? preview.error ?? detail.error} />
      <Panel title="Comparison setup" description="Choose exactly two project-owned profiles. Requests run higher profile first, then lower profile.">
        <form className="form-grid columns-2" onSubmit={createCase}>
          <Field label="Comparison name"><input name="name" required /></Field>
          <Field label="Target"><select name="target_id" required>{targets.map((target) => <option value={target.id} key={target.id}>{target.name}</option>)}</select></Field>
          <Field label="Request"><select name="imported_request_id" required>{requests.map((item) => <option value={item.id} key={item.id}>{item.method} {item.path}</option>)}</select></Field>
          <Field label="Expected behavior"><select name="expectation"><option value="lower_denied">Lower profile denied</option><option value="authenticated_only">Anonymous denied</option><option value="ownership_separation">Ownership separation</option><option value="tenant_separation">Project or tenant separation</option><option value="limited_fields">Limited fields</option><option value="sensitive_fields_limited">Sensitive fields limited</option><option value="method_protection">Consistent method protection</option><option value="object_existence_indistinguishable">Object existence hidden</option><option value="baseline_consistency">Baseline behavior preserved</option><option value="different_records">Different records</option></select></Field>
          <Field label="Higher-privilege profile"><select name="high_session" required>{profiles.filter((item) => item.is_active).map((item) => <option value={item.id} key={item.id}>{item.name} - {item.role_label}</option>)}</select></Field>
          <Field label="Lower-privilege profile"><select name="low_session" required>{profiles.filter((item) => item.is_active).map((item) => <option value={item.id} key={item.id}>{item.name} - {item.role_label}</option>)}</select></Field>
          <label className="checkbox"><input name="approved" type="checkbox" value="yes" /> Approve the saved state-changing test case</label>
          <Button type="submit">Save comparison</Button>
        </form>
      </Panel>
      <Panel title="Outbound-data review" description="This factual review is loaded from the backend before execution.">
        <select aria-label="Saved comparison" value={selectedCase ?? ""} onChange={(event) => { setSelectedCase(event.target.value); }}>
          <option value="">Select a comparison</option>{cases.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        {preview.data && (
          <section className="evidence-card" aria-label="Outbound data review">
            <StructuredData value={preview.data} />
          </section>
        )}
        {selectedCase && preview.data && (
          <div className="button-row">
            <Button onClick={() => { mutation.mutate({ path: `/test-cases/${selectedCase}/run`, payload: {
              authorization_confirmed: true,
              test_data_confirmed: Boolean(selectedDefinition?.is_state_changing),
              typed_confirmation: selectedDefinition?.is_state_changing ? "AUTHORIZE CHANGE" : "",
            } }); }}>Start controlled comparison</Button>
          </div>
        )}
      </Panel>
      <Panel title="Run history">
        {runs.length ? <div className="resource-list">{runs.map((run) => <button className="resource" key={run.id} onClick={() => { setSelectedRun(run.id); }}><span><strong>{run.automated_classification || "Comparison pending"}</strong><small>{run.explanation || run.id}</small></span><Status value={run.status} /></button>)}</div> : <Empty>No runs recorded.</Empty>}
      </Panel>
      {detail.data && (
        <Panel title="Observation matrix" description="Evidence is normalized, bounded, escaped, and profile-linked.">
          <div
            className="progress"
            role="progressbar"
            aria-label="Run progress"
            aria-valuemin={0}
            aria-valuemax={detail.data.run.progress_total}
            aria-valuenow={detail.data.run.progress_completed}
          >
            <span style={{ width: `${String((detail.data.run.progress_completed / Math.max(detail.data.run.progress_total, 1)) * 100)}%` }} />
          </div>
          {["queued", "running"].includes(detail.data.run.status) && <Button variant="danger" onClick={() => { mutation.mutate({ path: `/runs/${detail.data.run.id}/cancel`, payload: {} }); }}>Cancel run</Button>}
          <div className="table-wrap"><table><thead><tr><th>Profile reference</th><th>Status</th><th>Type</th><th>Bytes</th><th>Duration</th><th>Markers</th></tr></thead><tbody>{detail.data.observations.map((item) => <tr key={item.id}><td><code>{item.session_id.slice(0, 8)}</code></td><td>{item.status_code ?? item.error_category}</td><td>{item.content_type || (item.is_binary ? "binary hash only" : "unknown")}</td><td>{item.response_length}</td><td>{item.duration_ms} ms</td><td>{[item.auth_challenge && "challenge", item.access_denied_marker && "denied", item.object_existence_marker && "not-found", item.is_binary && "raw binary omitted"].filter(Boolean).join(", ") || "none"}</td></tr>)}</tbody></table></div>
          {detail.data.observations.map((item) => (
            <section className="evidence-card" key={`${item.id}-evidence`}>
              <h3>Sanitized evidence - profile {item.session_id.slice(0, 8)}</h3>
              <dl className="facts">
                <div><dt>Body hash</dt><dd><code>{item.sanitized_body_hash ?? "not available"}</code></dd></div>
                <div><dt>Capture</dt><dd>{item.is_binary ? "Binary hash and metadata only" : item.sanitized_excerpt ? "Bounded and sanitized" : "No body retained"}</dd></div>
              </dl>
              {item.sanitized_excerpt && <pre className="evidence" tabIndex={0}>{item.sanitized_excerpt}</pre>}
            </section>
          ))}
          <h3>Compared request and profiles</h3>
          <section className="evidence-card"><StructuredData value={detail.data.context} /></section>
          <h3>Normalized differences</h3>
          {detail.data.difference
            ? <section className="evidence-card"><StructuredData value={detail.data.difference} /></section>
            : <Empty>No normalized differences are available for this run.</Empty>}
        </Panel>
      )}
    </>
  );
}

function FindingSection({ projectId, findings }: { projectId: string; findings: Finding[] }) {
  const client = useQueryClient();
  const [selected, setSelected] = useState<string>();
  const [severity, setSeverity] = useState("");
  const [confidence, setConfidence] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const chosen = findings.find((finding) => finding.id === selected);
  const filtered = findings.filter((finding) =>
    (!severity || finding.severity === severity)
    && (!confidence || finding.confidence === confidence)
    && (!category || finding.category === category)
    && (!status || finding.status === status),
  );
  const evidence = useQuery({
    queryKey: ["finding-evidence", selected],
    queryFn: () => api<FindingEvidence[]>(`/findings/${String(selected)}/evidence`),
    enabled: Boolean(selected),
  });
  const history = useQuery({
    queryKey: ["finding-history", selected],
    queryFn: () => api<FindingHistory[]>(`/findings/${String(selected)}/status-history`),
    enabled: Boolean(selected),
  });
  const notes = useQuery({
    queryKey: ["finding-notes", selected],
    queryFn: () => api<FindingNote[]>(`/findings/${String(selected)}/notes`),
    enabled: Boolean(selected),
  });
  const update = useMutation({
    mutationFn: ({ path, payload }: { path: string; payload: object }) =>
      api<unknown>(path, { method: path.endsWith("/notes") ? "POST" : "PATCH", ...jsonBody(payload) }),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["findings", projectId] }),
        client.invalidateQueries({ queryKey: ["finding-history", selected] }),
        client.invalidateQueries({ queryKey: ["finding-notes", selected] }),
      ]);
    },
  });
  function note(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosen) return;
    const data = new FormData(event.currentTarget);
    update.mutate({ path: `/findings/${chosen.id}/notes`, payload: { body: data.get("body") } });
    event.currentTarget.reset();
  }
  return (
    <>
      <ErrorNotice error={update.error ?? evidence.error ?? history.error ?? notes.error} />
      <Panel title="Findings" description="Candidates remain reviewer-controlled. Critical severity is never assigned automatically.">
        <div className="filter-grid" aria-label="Finding filters">
          <select aria-label="Severity filter" value={severity} onChange={(event) => { setSeverity(event.target.value); }}><option value="">All severities</option>{["informational", "low", "medium", "high", "critical"].map((value) => <option key={value}>{value}</option>)}</select>
          <select aria-label="Confidence filter" value={confidence} onChange={(event) => { setConfidence(event.target.value); }}><option value="">All confidence levels</option>{["low", "medium", "high"].map((value) => <option key={value}>{value}</option>)}</select>
          <select aria-label="Category filter" value={category} onChange={(event) => { setCategory(event.target.value); }}><option value="">All categories</option>{[...new Set(findings.map((finding) => finding.category))].sort().map((value) => <option key={value}>{value}</option>)}</select>
          <select aria-label="Status filter" value={status} onChange={(event) => { setStatus(event.target.value); }}><option value="">All statuses</option>{[...new Set(findings.map((finding) => finding.status))].sort().map((value) => <option key={value}>{value}</option>)}</select>
        </div>
        {filtered.length ? <div className="resource-list">{filtered.map((finding) => <button className="resource" key={finding.id} onClick={() => { setSelected(finding.id); }}><span><strong>{finding.title}</strong><small>{finding.category} - {finding.confidence} confidence</small></span><Status value={finding.status} /></button>)}</div> : <Empty>No findings match these filters.</Empty>}
      </Panel>
      {chosen && <Panel title={chosen.title} description={chosen.limitations}>
        <dl className="facts"><div><dt>Severity</dt><dd>{chosen.severity}</dd></div><div><dt>Confidence</dt><dd>{chosen.confidence}</dd></div><div><dt>Priority</dt><dd>{chosen.priority}</dd></div><div><dt>Endpoint</dt><dd><code>{chosen.endpoint_snapshot}</code></dd></div><div><dt>First seen</dt><dd>{new Date(chosen.first_seen_at).toLocaleString()}</dd></div><div><dt>Last seen</dt><dd>{new Date(chosen.last_seen_at).toLocaleString()}</dd></div><div><dt>Recurrences</dt><dd>{chosen.recurrence_count}</dd></div></dl>
        <h3>Observed behavior</h3><p>{chosen.observed_behaviour}</p>
        <h3>Potential impact</h3><p>{chosen.impact || "Impact requires reviewer assessment."}</p>
        <h3>Defensive remediation</h3><p>{chosen.remediation || "Manual remediation guidance has not been added."}</p>
        <div className="button-row">{["triaged", "in_progress", "confirmed", "false_positive", "accepted_risk", "resolved"].map((nextStatus) => <Button variant="secondary" key={nextStatus} onClick={() => { update.mutate({ path: `/findings/${chosen.id}`, payload: { status: nextStatus, status_note: `Changed to ${nextStatus} by reviewer.` } }); }}>{nextStatus.replaceAll("_", " ")}</Button>)}</div>
        <form className="inline-form" onSubmit={note}><input name="body" aria-label="Finding note" placeholder="Add reviewer note" required /><Button type="submit">Add note</Button></form>
        <h3>Safe evidence</h3>
        {evidence.data?.length ? evidence.data.map((item) => <article className="evidence-card" key={item.id}><p><strong>{item.evidence_type.replaceAll("_", " ")}</strong> - <code>{item.excerpt_hash.slice(0, 16)}</code></p><StructuredData value={item.safe_metadata} /><pre className="evidence" tabIndex={0}>{item.sanitized_excerpt}</pre></article>) : <Empty>No evidence references are linked.</Empty>}
        <h3>Lifecycle history</h3>
        {history.data?.length ? <ol className="timeline">{history.data.map((item) => <li key={item.id}><strong>{item.from_status ?? "created"} to {item.to_status}</strong><span>{new Date(item.created_at).toLocaleString()}</span><p>{item.note}</p></li>)}</ol> : <Empty>No status changes recorded.</Empty>}
        <h3>Reviewer notes</h3>
        {notes.data?.length ? <ol className="timeline">{notes.data.map((item) => <li key={item.id}><span>{new Date(item.created_at).toLocaleString()}</span><p>{item.body}</p></li>)}</ol> : <Empty>No reviewer notes recorded.</Empty>}
      </Panel>}
    </>
  );
}

function ReportSection({ projectId, reports }: { projectId: string; reports: Report[] }) {
  const client = useQueryClient();
  const create = useMutation({
    mutationFn: (format: string) => api<Report>(`/projects/${projectId}/reports`, { method: "POST", ...jsonBody({ format }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["reports", projectId] }),
  });
  return <>
    <ErrorNotice error={create.error} />
    <Panel title="Generate redacted report" description="Exports enforce project ownership and exclude reusable credentials.">
      <div className="button-row">{["json", "csv", "html", "pdf"].map((format) => <Button key={format} variant="secondary" onClick={() => { create.mutate(format); }}>{format.toUpperCase()}</Button>)}</div>
    </Panel>
    <Panel title="Reports">{reports.length ? <div className="table-wrap"><table><thead><tr><th>Generated</th><th>Format</th><th>Status</th><th>Hash</th><th>Download</th></tr></thead><tbody>{reports.map((report) => <tr key={report.id}><td>{new Date(report.generated_at).toLocaleString()}</td><td>{report.format.toUpperCase()}</td><td><Status value={report.status} /></td><td><code>{report.file_hash?.slice(0, 16) || "pending"}</code></td><td>{report.status === "completed" && <a href={`/api/v1/reports/${report.id}/download`}>Download</a>}</td></tr>)}</tbody></table></div> : <Empty>No reports generated.</Empty>}</Panel>
  </>;
}

function DemoSection({ projectId }: { projectId: string }) {
  const reset = useMutation({
    mutationFn: () =>
      api<{ status: string }>("/demo/reset", {
        method: "POST",
        ...jsonBody({ project_id: projectId }),
      }),
  });
  return (
    <>
      <ErrorNotice error={reset.error} />
      <Panel title="Guided deterministic demo" description="Use only the bundled fictional target and synthetic bearer tokens. Reset is available only when the backend explicitly enables demo mode.">
        <ol className="timeline">
          <li><strong>1. Target policy</strong><p>Create <code>http://127.0.0.1:8021</code> as a local synthetic target, confirm authorization and the private lab, add exact IP <code>127.0.0.1:8021</code>, then activate it.</p></li>
          <li><strong>2. Profiles</strong><p>Create Administrator, User A, User B, and Anonymous profiles. Use synthetic bearer values <code>demo-admin-token</code>, <code>demo-user-a-token</code>, and <code>demo-user-b-token</code>.</p></li>
          <li><strong>3. Requests</strong><p>Save secure and vulnerable relative paths such as <code>/secure/admin/users</code> and <code>/vulnerable/admin/users</code>.</p></li>
          <li><strong>4. Comparisons</strong><p>Compare administrator to User A for vertical access, and User A to User B for ownership checks. Review the outbound-data summary before queueing.</p></li>
          <li><strong>5. Evidence and reports</strong><p>Inspect bounded observations, review generated candidates, update lifecycle state, and generate redacted reports.</p></li>
        </ol>
        <div className="button-row">
          <Button disabled={reset.isPending} onClick={() => { reset.mutate(); }}>
            {reset.isPending ? "Resetting fixture..." : "Reset synthetic fixture"}
          </Button>
          {reset.data && <span role="status">Fixture reset completed.</span>}
        </div>
      </Panel>
    </>
  );
}

export function ProjectPage() {
  const { projectId = "", section = "targets" } = useParams();
  const workspace = useWorkspace(projectId);
  const loading = Object.values(workspace).some((query) => query.isLoading);
  const error = Object.values(workspace).map((query) => query.error).find(Boolean);
  const title = useMemo(() => workspace.project.data?.name ?? "Project workspace", [workspace.project.data]);
  return (
    <main id="main-content" className="page">
      <div className="breadcrumbs"><Link to="/">Projects</Link><span aria-hidden="true">/</span><span>{title}</span></div>
      <div className="page-title"><div><p className="eyebrow">Project-scoped workspace</p><h1>{title}</h1><p>{workspace.project.data?.description}</p></div></div>
      <nav className="tabs" aria-label="Project sections">{sections.map(([path, label]) => <NavLink key={path} to={`/projects/${projectId}/${path}`}>{label}</NavLink>)}</nav>
      <ErrorNotice error={error} />
      {loading && <p role="status">Loading project resources...</p>}
      {!loading && section === "targets" && <TargetSection projectId={projectId} targets={workspace.targets.data ?? []} />}
      {!loading && section === "profiles" && <ProfileSection projectId={projectId} targets={workspace.targets.data ?? []} profiles={workspace.profiles.data ?? []} />}
      {!loading && section === "requests" && <RequestSection projectId={projectId} targets={workspace.targets.data ?? []} collections={workspace.collections.data ?? []} requests={workspace.requests.data ?? []} />}
      {!loading && section === "comparisons" && <ComparisonSection projectId={projectId} targets={workspace.targets.data ?? []} profiles={workspace.profiles.data ?? []} requests={workspace.requests.data ?? []} cases={workspace.cases.data ?? []} runs={workspace.runs.data ?? []} />}
      {!loading && section === "findings" && <FindingSection projectId={projectId} findings={workspace.findings.data ?? []} />}
      {!loading && section === "reports" && <ReportSection projectId={projectId} reports={workspace.reports.data ?? []} />}
      {!loading && section === "demo" && <DemoSection projectId={projectId} />}
    </main>
  );
}
