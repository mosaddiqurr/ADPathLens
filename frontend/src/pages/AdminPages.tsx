import { FileDown, Settings, Shield, UserPlus } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { api, errorMessage } from "../api/client";
import { StatusMessage } from "../components/common/StatusMessage";
import type { Page, User } from "../types/api";

type AuditEvent = {
  id: string;
  created_at: string;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  summary: string;
  source_ip: string | null;
};

export function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [action, setAction] = useState("");
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    try {
      const query = action ? `?page_size=200&action=${encodeURIComponent(action)}` : "?page_size=200";
      setEvents((await api<Page<AuditEvent>>(`/audit/events${query}`)).items);
    } catch (reason) { setMessage(errorMessage(reason)); }
  }, [action]);
  useEffect(() => { void load(); }, [load]);
  return <div className="page"><div className="page-heading"><div><p className="eyebrow">Append-only accountability</p><h1>Audit events</h1><p>Sanitized security and lifecycle events. Raw uploads, cookies, passwords, and sensitive metadata are excluded.</p></div><Shield size={34} /></div><StatusMessage message={message} tone="danger" /><div className="filter-bar"><label>Exact action<input value={action} onChange={(event) => setAction(event.target.value)} placeholder="report.generated" /></label><a className="secondary-button inline-button" href="/api/v1/audit/events/export"><FileDown size={16} />Safe CSV export</a></div><section className="panel"><div className="table-wrap"><table><thead><tr><th>Time</th><th>Action</th><th>Entity</th><th>Summary</th><th>Source</th></tr></thead><tbody>{events.map((event) => <tr key={event.id}><td>{new Date(event.created_at).toLocaleString()}</td><td><code>{event.action}</code></td><td>{event.entity_type}<small>{event.entity_id ?? "—"}</small></td><td>{event.summary}</td><td>{event.source_ip ?? "—"}</td></tr>)}</tbody></table></div></section></div>;
}

type SettingRecord = { key: string; value: string | number | boolean | null; configured: boolean };
type RuleRecord = { rule_id: string; title: string; enabled: boolean; configuration_version: number };

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingRecord[]>([]);
  const [rules, setRules] = useState<RuleRecord[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("viewer");
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    try {
      const [settingData, ruleData, userData] = await Promise.all([
        api<SettingRecord[]>("/settings"),
        api<RuleRecord[]>("/risk/rules"),
        api<User[]>("/users"),
      ]);
      setSettings(settingData); setRules(ruleData); setUsers(userData);
    } catch (reason) { setMessage(errorMessage(reason)); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function createUser(event: FormEvent) {
    event.preventDefault();
    try {
      await api<User>("/users", { method: "POST", json: { email, display_name: displayName, password, role } });
      setEmail(""); setDisplayName(""); setPassword(""); setMessage("User created."); await load();
    } catch (reason) { setMessage(errorMessage(reason)); }
  }
  async function toggleRule(rule: RuleRecord) {
    try {
      await api(`/risk/rules/${rule.rule_id}/configuration`, { method: "POST", json: { enabled: !rule.enabled, relationship_weights: {}, scoring_overrides: {} } });
      setMessage(`${rule.rule_id} configuration version created.`); await load();
    } catch (reason) { setMessage(errorMessage(reason)); }
  }
  return <div className="page"><div className="page-heading"><div><p className="eyebrow">Administration</p><h1>Users, rules & settings</h1><p>Secret values remain environment-controlled. Changes are versioned and audited.</p></div><Settings size={34} /></div><StatusMessage message={message} tone={message.includes("created") ? "success" : "info"} /><div className="two-column"><section className="panel"><div className="panel-heading"><h2>User administration</h2><UserPlus /></div><form className="form-stack" onSubmit={(event) => void createUser(event)}><label>Display name<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required /></label><label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Temporary password<input type="password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required /></label><label>Global role<select value={role} onChange={(event) => setRole(event.target.value)}><option value="viewer">Viewer</option><option value="analyst">Analyst</option><option value="administrator">Administrator</option></select></label><button className="secondary-button">Create user</button></form><ul className="compact-list">{users.map((user) => <li key={user.id}><span><strong>{user.display_name}</strong><small>{user.email}</small></span><span className="status-chip">{user.role}</span></li>)}</ul></section><section className="panel"><h2>Allow-listed settings</h2><ul className="compact-list">{settings.map((setting) => <li key={setting.key}><span><strong>{setting.key}</strong><small>{setting.configured ? String(setting.value) : "Default"}</small></span></li>)}</ul></section></div><section className="panel"><div className="panel-heading"><h2>Versioned deterministic rules</h2><span>{rules.length} rules</span></div><div className="rule-grid">{rules.map((rule) => <article key={rule.rule_id}><span className="rule-id">{rule.rule_id}</span><strong>{rule.title}</strong><small>Configuration v{rule.configuration_version}</small><button className={rule.enabled ? "danger-link" : "text-link"} onClick={() => void toggleRule(rule)}>{rule.enabled ? "Disable for new scans" : "Enable for new scans"}</button></article>)}</div></section></div>;
}

