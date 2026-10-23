import { useState } from "react";
import { api, errorMessage } from "../api/client";
import { StatusMessage } from "./common/StatusMessage";
import type { Snapshot } from "../types/api";
type Validation = {
  valid: boolean;
  digest: string;
  node_count: number;
  relationship_count: number;
  messages: Array<{
    level: string;
    code: string;
    message: string;
    location: string;
  }>;
};
export function ImportPanel({
  projectId = "",
  onImported,
  prepareProject,
}: {
  projectId?: string;
  onImported?: (id: string, collectionId: string) => Promise<void>;
  prepareProject?: () => Promise<string>;
}) {
  const [authorized, setAuthorized] = useState(false);
  const [mode, setMode] = useState<"json" | "csv" | "zip">("json");
  const [file, setFile] = useState<File | null>(null);
  const [relationshipsFile, setRelationshipsFile] = useState<File | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [acknowledged, setAcknowledged] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState<"info" | "success" | "danger">(
    "info",
  );
  const [busy, setBusy] = useState(false);
  const [validatedProjectId, setValidatedProjectId] = useState("");
  function formData() {
    const form = new FormData();
    if (file)
      form.append(
        mode === "json" ? "file" : mode === "zip" ? "zip_file" : "nodes_file",
        file,
      );
    if (mode === "csv" && relationshipsFile)
      form.append("relationships_file", relationshipsFile);
    return form;
  }
  async function validate() {
    setBusy(true);
    setMessage("");
    setValidation(null);
    setAcknowledged([]);
    try {
      const activeProjectId = projectId || (await prepareProject?.());
      if (!activeProjectId)
        throw new Error("Open an analysis session before importing data.");
      setValidatedProjectId(activeProjectId);
      const result = await api<Validation>(
        `/projects/${activeProjectId}/datasets/${mode === "json" ? "validate-json" : "validate-csv"}`,
        { method: "POST", body: formData() },
      );
      setValidation(result);
      setMessageTone(result.valid ? "success" : "danger");
      setMessage(
        result.valid
          ? "Dataset checked. Review any warnings, then load your data."
          : "This dataset has errors. Correct them before loading.",
      );
    } catch (e) {
      setMessageTone("danger");
      setMessage(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function load() {
    if (!validation?.valid || !authorized || !file) return;
    setBusy(true);
    setMessage("");
    try {
      const form = formData();
      form.append("validation_digest", validation.digest);
      form.append("authorization_confirmed", "true");
      form.append("acknowledged_warnings", acknowledged.join(","));
      form.append("name", file.name);
      const snapshot = await api<Snapshot>(
        `/projects/${validatedProjectId || projectId}/datasets/${mode === "json" ? "import-json" : "import-csv"}`,
        { method: "POST", body: form },
      );
      setMessage(`Imported ${snapshot.name}.`);
      setMessageTone("success");
      setFile(null);
      setRelationshipsFile(null);
      setValidation(null);
      await onImported?.(snapshot.id, validatedProjectId || projectId);
    } catch (e) {
      setMessageTone("danger");
      setMessage(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  function changeFile(value: File | null, second = false) {
    if (second) setRelationshipsFile(value);
    else setFile(value);
    setValidation(null);
    setAcknowledged([]);
    setMessage("");
  }
  const warnings =
    validation?.messages
      .filter((m) => m.level === "warning")
      .map((m) => m.code) ?? [];
  return (
    <div className="import-embedded">
      <StatusMessage message={message} tone={messageTone} />
      <div className="form-stack">
        <fieldset disabled={busy}>
          <legend>Dataset format</legend>
          <div className="format-grid">
            {(["json", "csv", "zip"] as const).map((m) => (
              <label key={m} className={m === mode ? "selected" : ""}>
                <input
                  type="radio"
                  name="source-mode"
                  checked={mode === m}
                  onChange={() => {
                    setMode(m);
                    setFile(null);
                    setRelationshipsFile(null);
                    setValidation(null);
                    setAcknowledged([]);
                    setMessage("");
                  }}
                />
                {m.toUpperCase()}
              </label>
            ))}
          </div>
        </fieldset>
        <p>
          {mode === "json"
            ? "One ADPathLens JSON file containing nodes and relationships."
            : mode === "csv"
              ? "Select both files: nodes.csv contains directory objects; relationships.csv contains their connections."
              : "A ZIP with nodes.csv and relationships.csv at its root. Nested folders are not supported."}
        </p>
        <label className="file-upload">
          {mode === "csv"
            ? "nodes.csv"
            : mode === "zip"
              ? "CSV ZIP"
              : "JSON dataset"}
          <input
            key={`${mode}-nodes`}
            type="file"
            accept={
              mode === "json" ? ".json" : mode === "zip" ? ".zip" : ".csv"
            }
            disabled={busy}
            onChange={(e) => changeFile(e.target.files?.[0] ?? null)}
          />
        </label>
        {mode === "csv" && (
          <label className="file-upload">
            relationships.csv
            <input
              type="file"
              accept=".csv"
              disabled={busy}
              onChange={(e) => changeFile(e.target.files?.[0] ?? null, true)}
            />
          </label>
        )}
        <details className="advanced">
          <summary>File structure</summary>
          {mode === "json" ? (
            <pre>
              {
                '{"metadata":{},"nodes":[{"id":"user-1","type":"User","name":"Example user"}],"relationships":[]}'
              }
            </pre>
          ) : (
            <p>
              CSV columns must match the documented ADPathLens format. A
              directory collector’s output may need conversion before import.
            </p>
          )}
        </details>
        <button
          className="secondary-button"
          disabled={busy || !file || (mode === "csv" && !relationshipsFile)}
          onClick={() => void validate()}
        >
          {busy ? "Checking dataset…" : "Validate dataset"}
        </button>
        <label className="authorization-box">
          <input
            type="checkbox"
            checked={authorized}
            onChange={(e) => setAuthorized(e.target.checked)}
          />
          <span>
            <strong>Authorized-use confirmation</strong>I am using synthetic
            data or information from systems I own or am explicitly authorized
            to assess.
          </span>
        </label>
        {validation && (
          <div className="validation-results">
            <strong>
              {validation.valid ? "Ready to load" : "Needs correction"} ·{" "}
              {validation.node_count} directory objects ·{" "}
              {validation.relationship_count} relationships
            </strong>
            {validation.messages.map((m, i) => (
              <div
                className={`validation-item ${m.level}`}
                key={`${m.code}-${i}`}
              >
                <span>{m.level}</span>
                <div>
                  <p>{m.message}</p>
                  <details>
                    <summary>Technical details</summary>
                    <small>
                      {m.code} · {m.location}
                    </small>
                  </details>
                </div>
                {m.level === "warning" && (
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={acknowledged.includes(m.code)}
                      onChange={(e) =>
                        setAcknowledged((current) =>
                          e.target.checked
                            ? [...new Set([...current, m.code])]
                            : current.filter((code) => code !== m.code),
                        )
                      }
                    />
                    Acknowledge
                  </label>
                )}
              </div>
            ))}
            <button
              className="primary-button"
              disabled={
                busy ||
                !authorized ||
                !validation.valid ||
                !warnings.every((code) => acknowledged.includes(code))
              }
              onClick={() => void load()}
            >
              {busy ? "Importing dataset…" : "Import dataset"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
