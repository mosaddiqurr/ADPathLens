import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import { Button, Empty, ErrorNotice, Panel, Status } from "../components/Ui";
import type { AuditEvent } from "../types";

export function AuditPage() {
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [outcome, setOutcome] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [offset, setOffset] = useState(0);
  const parameters = new URLSearchParams({ limit: "50", offset: String(offset) });
  if (action) parameters.set("action", action);
  if (actor) parameters.set("user_id", actor);
  if (outcome) parameters.set("outcome", outcome);
  if (dateFrom) parameters.set("date_from", new Date(dateFrom).toISOString());
  const events = useQuery({
    queryKey: ["audit-events", action, actor, outcome, dateFrom, offset],
    queryFn: () => api<AuditEvent[]>(`/audit-events?${parameters.toString()}`),
  });
  return (
    <main id="main-content" className="page">
      <div className="page-title">
        <div>
          <p className="eyebrow">Administrator</p>
          <h1>Audit events</h1>
          <p>Sanitized security-relevant actions recorded by the application.</p>
        </div>
        <a className="button button-secondary" href="/api/v1/audit-events/export">
          Export CSV
        </a>
      </div>
      <ErrorNotice error={events.error} />
      <Panel title="Audit filters" description="Filters are evaluated by the administrator-only API. Actor values use the immutable user identifier.">
        <div className="filter-grid">
          <input aria-label="Actor ID filter" placeholder="Actor user ID" value={actor} onChange={(event) => { setActor(event.target.value); setOffset(0); }} />
          <input aria-label="Action filter" placeholder="Exact action" value={action} onChange={(event) => { setAction(event.target.value); setOffset(0); }} />
          <select aria-label="Outcome filter" value={outcome} onChange={(event) => { setOutcome(event.target.value); setOffset(0); }}><option value="">All outcomes</option><option value="success">Success</option><option value="denied">Denied</option><option value="failed">Failed</option></select>
          <input aria-label="Events after date" type="datetime-local" value={dateFrom} onChange={(event) => { setDateFrom(event.target.value); setOffset(0); }} />
        </div>
      </Panel>
      <Panel title="Recent events">
        {events.data?.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Action</th>
                  <th>Outcome</th>
                  <th>Actor</th>
                  <th>Entity</th>
                  <th>Correlation</th>
                  <th>Summary</th>
                </tr>
              </thead>
              <tbody>
                {events.data.map((event) => (
                  <tr key={event.id}>
                    <td>{new Date(event.created_at).toLocaleString()}</td>
                    <td><code>{event.action}</code></td>
                    <td><Status value={event.outcome} /></td>
                    <td><code>{event.user_id?.slice(0, 8) ?? "system"}</code></td>
                    <td>{event.entity_type}<br /><code>{event.entity_id?.slice(0, 8) ?? "none"}</code></td>
                    <td><code>{event.correlation_id?.slice(0, 12) ?? "none"}</code></td>
                    <td>{event.summary}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>No audit events are available.</Empty>
        )}
        <div className="button-row">
          <Button variant="secondary" disabled={offset === 0} onClick={() => { setOffset(Math.max(0, offset - 50)); }}>Previous</Button>
          <Button variant="secondary" disabled={(events.data?.length ?? 0) < 50} onClick={() => { setOffset(offset + 50); }}>Next</Button>
        </div>
      </Panel>
    </main>
  );
}
