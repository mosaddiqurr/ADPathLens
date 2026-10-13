export function About() {
  return <main id="main-content" className="workspace about-page">
    <p className="eyebrow">About the tool</p><h1>What changed, and why it matters.</h1>
    <p className="page-description">AuthZDiff compares two authorization states and highlights access changes worth reviewing.</p>
    <section className="about-section"><h2>One comparison, two inputs</h2>
      <p>Load a Before baseline and an After candidate. Review access gained, access lost, and risky changes, then export the current comparison.</p></section>
    <section className="about-section"><h2>Supported inputs</h2>
      <dl className="format-list"><div><dt>JSON / CSV</dt><dd>Explicit access records: principal, resource, action, and allow or deny. Role and sensitivity labels are optional.</dd></div>
        <div><dt>HAR</dt><dd>Captured HTTP requests and responses. Access transitions need matching identity and authorization context; status changes alone remain review items.</dd></div></dl>
      <details className="about-details"><summary>Input format &amp; HAR context</summary>
        <p>JSON accepts an array of records or a wrapper with <code>schema: "authzdiff/snapshot-v1"</code> and <code>records</code>.</p>
        <pre tabIndex={0} role="region" aria-label="Snapshot input example">{'{"principal":"Alice","resource":"Billing","action":"Read","effect":"allow","role":"Viewer"}'}</pre>
        <p>CSV uses the same field names as column headers. Each principal/resource/action tuple must appear once. JSON and CSV snapshots can be compared to each other.</p>
        <p>HAR annotations go in <code>log._authzdiff</code> or an entry&apos;s <code>_authzdiff</code>: <code>principal</code>, <code>access</code> (allowed, denied, or unknown), and optional <code>sensitive</code>. A response must corroborate the annotation. Repeated identical requests are rejected as ambiguous.</p>
        <p>Each file is limited to 5 MB, 2,000 snapshot records or 500 HAR entries.</p>
      </details></section>
    <section className="about-section"><h2>Risk means review priority</h2>
      <p>Public access, administrator access, broader wildcards, sensitive resources, and removed explicit denials receive higher review priority. Ordinary grants are informational.</p></section>
    <section className="about-section"><h2>Your data stays with your instance</h2>
      <p>Files are processed in memory by this instance&apos;s Python backend. No uploads are saved, no requests are replayed, and no analytics receive your data. Running locally keeps processing on your computer.</p>
      <p>The browser holds only the current comparison in memory. Clear it or reload to start again. Exports are saved only when you download them.</p></section>
    <details className="about-details"><summary>Limitations</summary>
      <p>Snapshots describe listed access, not full IAM policy semantics. AuthZDiff does not resolve inheritance, conditions, or wildcard coverage. Missing records do not prove that live access is blocked.</p>
      <p>Only Viewer/Reader, Developer/Editor, and Admin/Administrator/Owner have a recognized role ordering. Other role labels need review.</p>
      <p>HAR captures cannot prove exploitability. Redaction is best effort; review evidence before sharing. PDF reports prioritize the first 100 changes; JSON contains all evidence.</p></details>
    <footer className="creator"><span>Designed and built by</span>
      <a href="https://www.linkedin.com/in/mosaddiqur/" target="_blank" rel="noreferrer">Mosaddiqur Rahman ↗</a></footer>
  </main>;
}
