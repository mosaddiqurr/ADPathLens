import { ArrowRight, RotateCcw } from "lucide-react";
import { useRef, useState } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import beforeExample from "../../examples/snapshot-before.json";
import afterExample from "../../examples/snapshot-after.json";
import { compareInputs, exportReport, inspectInput, UserError, userMessage } from "./api/client";
import { Results } from "./components/Results";
import { UploadPanel } from "./components/UploadPanel";
import { AppLayout } from "./layouts/AppLayout";
import { About } from "./pages/About";
import { Home } from "./pages/Home";
import type { ComparisonResult, ExportFormat, InputData, InputSlot } from "./types";

const emptySlot = (): InputSlot => ({ data: null, summary: null, pending: false, error: null });
type Side = "before" | "after";

export function App() {
  const [before, setBefore] = useState<InputSlot>(emptySlot);
  const [after, setAfter] = useState<InputSlot>(emptySlot);
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const versions = useRef({ before: 0, after: 0 });
  const controllers = useRef<Partial<Record<Side, AbortController>>>({});
  const comparisonController = useRef<AbortController | null>(null);
  const resultHeading = useRef<HTMLDivElement>(null);
  const locked = busy || exporting !== null;

  function invalidate(side: Side) {
    controllers.current[side]?.abort();
    versions.current[side] += 1;
    comparisonController.current?.abort();
    setResult(null); setError(null);
    return versions.current[side];
  }
  function clear(side: Side) {
    invalidate(side);
    (side === "before" ? setBefore : setAfter)(emptySlot());
  }
  async function validate(side: Side, data: InputData, version: number) {
    if (versions.current[side] !== version) return;
    const setSlot = side === "before" ? setBefore : setAfter;
    const controller = new AbortController();
    controllers.current[side] = controller;
    try {
      const summary = await inspectInput(data, AbortSignal.any([controller.signal, AbortSignal.timeout(60_000)]));
      if (versions.current[side] === version) setSlot({ data, summary, pending: false, error: null });
    } catch (caught) {
      if (versions.current[side] !== version) return;
      const fallback = `The ${side === "before" ? "Before" : "After"} dataset could not be parsed.`;
      const message = userMessage(caught, fallback).replace("The input dataset", `The ${side === "before" ? "Before" : "After"} dataset`);
      setSlot({ data: null, summary: null, pending: false, error: message });
    }
  }
  async function pick(side: Side, file: File) {
    const version = invalidate(side);
    const setSlot = side === "before" ? setBefore : setAfter;
    setSlot({ data: { filename: file.name, content: "" }, summary: null, pending: true, error: null });
    try {
      if (file.size > 5 * 1024 * 1024) throw new UserError("Each input must be 5 MB or smaller.");
      if (!/\.(json|csv|har)$/i.test(file.name)) throw new UserError("This file format is not supported.");
      const content = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      if (versions.current[side] !== version) return;
      await validate(side, { filename: file.name, content }, version);
    } catch (caught) {
      if (versions.current[side] === version) setSlot({ ...emptySlot(), error: userMessage(caught, `The ${side === "before" ? "Before" : "After"} dataset could not be parsed.`) });
    }
  }
  async function loadExample() {
    const first = { filename: "snapshot-before.json", content: JSON.stringify(beforeExample) };
    const second = { filename: "snapshot-after.json", content: JSON.stringify(afterExample) };
    const beforeVersion = invalidate("before"); const afterVersion = invalidate("after");
    setBefore({ data: first, summary: null, pending: true, error: null });
    setAfter({ data: second, summary: null, pending: true, error: null });
    await validate("before", first, beforeVersion);
    await validate("after", second, afterVersion);
  }
  async function runComparison() {
    if (!before.data || !after.data || !before.summary || !after.summary) return;
    setBusy(true); setError(null); setResult(null);
    const controller = new AbortController();
    comparisonController.current = controller;
    try {
      const comparison = await compareInputs({ before: before.data, after: after.data },
        AbortSignal.any([controller.signal, AbortSignal.timeout(60_000)]));
      if (controller.signal.aborted) return;
      setResult(comparison);
      window.setTimeout(() => {
        document.getElementById("results-heading")?.focus({ preventScroll: true });
        resultHeading.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 50);
    } catch (caught) { if (!controller.signal.aborted) setError(userMessage(caught)); }
    finally { setBusy(false); }
  }
  async function download(format: ExportFormat) {
    if (!before.data || !after.data || !result) return;
    setExporting(format); setError(null);
    try { await exportReport({ before: before.data, after: after.data }, format); }
    catch (caught) { setError(userMessage(caught, "The report could not be generated.")); }
    finally { setExporting(null); }
  }
  const comparePage = <main id="main-content" className="workspace compare-page">
    <div className="page-heading"><div><p className="eyebrow">Before → After</p><h1>Compare authorization</h1>
      <p className="page-description">Add two inputs to see what access changed.</p></div>
      <button className="button text-button" disabled={locked || before.pending || after.pending} onClick={() => void loadExample()}>Load example</button></div>
    <div className="inputs-grid">
      <UploadPanel side="Before" slot={before} disabled={locked} onPick={file => void pick("before", file)} onClear={() => { clear("before"); }} />
      <UploadPanel side="After" slot={after} disabled={locked} onPick={file => void pick("after", file)} onClear={() => { clear("after"); }} />
    </div>
    <div className="compare-actions">
      <button className="button primary" disabled={locked || !before.summary || !after.summary || before.pending || after.pending}
        onClick={() => void runComparison()}>{busy ? "Comparing…" : "Compare authorization"}<ArrowRight size={16} aria-hidden="true" /></button>
      {(before.data || after.data || before.error || after.error) && <button className="button text-button" disabled={locked}
        onClick={() => { clear("before"); clear("after"); }}><RotateCcw size={14} aria-hidden="true" />Clear comparison</button>}
      <span className="privacy-note">Processed in memory. Never saved.</span>
    </div>
    {error && <p className="error-banner" role="alert">{error}</p>}
    <div ref={resultHeading} className="results-anchor">{result && <Results result={result} exporting={exporting} onExport={format => void download(format)} />}</div>
    {!result && !busy && <details className="input-help"><summary>Supported inputs</summary>
      <p>Explicit access snapshots in JSON or CSV, or paired HAR captures. Use the same kind of input on both sides. <Link to="/about">Format details</Link>.</p></details>}
  </main>;
  return <BrowserRouter><Routes><Route element={<AppLayout />}>
    <Route index element={<Home />} /><Route path="/compare" element={comparePage} /><Route path="/about" element={<About />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route></Routes></BrowserRouter>;
}
