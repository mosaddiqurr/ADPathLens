# Reporting

Export the current comparison from Compare. Reports use the same inputs and comparison engine;
visible filters never discard evidence from an export. There are no saved report jobs, history,
report IDs, or report files on the server.

- PDF: concise summary, prioritized risky changes, ordinary access gains/losses, recommendations,
  Before/After source states, capture-entry references where available, technical notes, and limitations.
  It includes at most the first 100 changes in risk order and explicitly states any truncation.
  Risky gain/loss entries appear once under Risky Changes; the summary still counts their direction.
- JSON: all changes, counts, versioned normalized model, source summaries, redacted evidence, and UTC generation time.
- CSV: all changes as a flat table, with spreadsheet formula protection.

All exports are generated in memory. Download filenames are fixed, not derived from upload paths.
Technical evidence is sanitized before reporting; raw request credentials and bodies are excluded.
Review before sharing: private resource labels and business data may remain.

PDF uses ReportLab's bundled Vera font. Complex scripts/right-to-left shaping are not guaranteed;
JSON preserves full Unicode evidence. PDF size is limited through its change cap, not silent evidence loss.
