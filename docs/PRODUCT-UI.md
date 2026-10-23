# Product UI

The primary workflow is Import → Analyze → Results → Evidence/remediation → Export. Navigation contains exactly Home, Analyze, Results, and About.

Home explains the purpose, shows an illustrative privilege chain with User A and User B, and offers Analyze AD data and Load demo. Analyze accepts ADPathLens JSON, a CSV pair, or a ZIP with the two CSV files. Validation, authorization, and warning acknowledgement precede import. A focused form shows the target and starting identity; data collection, snapshot, depth, confidence, and algorithm are available under Analysis limits & options. The target selector also includes other directory objects. Bounded reverse search is the default when no starting identity is chosen.

Results provides the returned path count, critical/high totals, affected objects, and snapshot/analysis scope. Paths are ranked by score. Filters match entity names, object types, severity, and relationship types. Selecting a path reveals a structured graph, priority explanation, confidence, ordered relationship cards with source evidence, scoring details, and the three highest-coverage relationship fixes. PDF/JSON export stays on the same screen and refers to the selected analysis.

The interface uses a graphite-and-amber visual system with a complete light theme, locally hosted Space Grotesk display type and Manrope body type. Centered containers reach 1440px. Home introduces the product through a vector topology with an amber signal moving along four access relationships toward Domain Admins. The illustrative graphic is separate from imported analysis data. Analyze uses one focal form, compact controls, and secondary guidance alongside it; Results pairs a ranked path index with the graph, evidence, remediation, and exports.

The header provides a persistent theme switch. Animations start automatically; the retired header motion control and its old storage settings are no longer used. About → Accessibility preferences includes an optional Reduce animations setting that stops decorative motion and transitions and persists in this browser. Ambient topology, route transitions, scroll reveals, and interaction feedback share that setting. Background drawing runs outside React's render cycle, suspends during scrolling, and stops when the page is hidden. The hero suspends when it leaves view; its animated signals are isolated from the static network drawing. The graph updates its theme without resetting the user's pan or zoom.

The Results export format uses a native, keyboard-accessible selector with a reserved arrow area. It has its own border and spacing from the export action; the controls wrap on narrow screens without overlapping.

On mobile the navigation becomes a menu with Escape/focus handling. Forms and result columns stack. The graph supports fit/zoom/pan, with readable text steps below it. Severity appears in text as well as color. Skip navigation, labelled controls, focus styles, live status messages, and accessible empty/failure states support keyboard use.

Advanced findings, simulations, comparisons, and administration remain available through compatibility APIs. Their separate screens are outside the four primary product routes.

See [TESTING.md](TESTING.md) for checks and [../README.md](../README.md) for screenshots and local instructions.
