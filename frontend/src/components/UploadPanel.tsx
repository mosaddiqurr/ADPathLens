import { Check, FileText, Upload, X } from "lucide-react";
import { useRef } from "react";

import type { InputSlot } from "../types";

export function UploadPanel({ side, slot, disabled, onPick, onClear }: {
  side: "Before" | "After";
  slot: InputSlot;
  disabled: boolean;
  onPick: (file: File) => void;
  onClear: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <section className={`input-panel ${slot.summary ? "input-ready" : ""}`} aria-labelledby={`${side}-heading`}>
      <div className="input-heading">
        <h2 id={`${side}-heading`}>{side}</h2>
        <span className="input-purpose">{side === "Before" ? "Baseline" : "Candidate"}</span>
      </div>
      <div className="upload-area" aria-busy={slot.pending}>
        <div className="upload-icon">{slot.summary ? <FileText size={24} aria-hidden="true" /> : <Upload size={24} aria-hidden="true" />}</div>
        <p className="upload-filename">{slot.summary?.filename ?? (slot.pending ? "Validating file…" : `Add ${side.toLowerCase()} authorization data`)}</p>
        {slot.summary ? (
          <div className="input-meta">
            <span>{slot.summary.format_label}</span>
            <span>{slot.summary.record_count} {slot.summary.record_count === 1 ? "record" : "records"}</span>
          </div>
        ) : <p className="subtle">JSON, CSV, or HAR · up to 5 MB</p>}
        <div className="upload-actions">
          <input ref={input} className="visually-hidden" type="file" accept=".json,.csv,.har" tabIndex={-1}
            aria-label={`${side} file`} disabled={disabled}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onPick(file);
              event.target.value = "";
            }} />
          <button className="button secondary" type="button" disabled={disabled || slot.pending}
            onClick={() => input.current?.click()}>
            {slot.pending ? "Validating…" : slot.data ? "Replace file" : "Upload file"}
          </button>
          {slot.data && <button className="icon-button" type="button" aria-label={`Remove ${side} file`}
            disabled={disabled} onClick={onClear}><X size={16} aria-hidden="true" /></button>}
        </div>
      </div>
      {slot.summary && <p className="validation-state"><Check size={14} aria-hidden="true" /> Ready to compare</p>}
      {slot.error && <p className="error-message" role="alert">{slot.error}</p>}
    </section>
  );
}
