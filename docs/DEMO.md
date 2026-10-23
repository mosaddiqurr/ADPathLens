# NORTHBRIDGE demo

Start the app using [../RUN_LOCAL.md](../RUN_LOCAL.md), open Home, and click **Load demo**. The application establishes a development-only loopback session, loads the fictional directory, and opens Analyze. Keep **Domain Admins** as the target and click **Run analysis**.

On shared hosting, sign in first, then choose **Load demo** on Home. Local access stays disabled. The fixture lives in the backend package; `DEMO_MODE=false` does not disable authenticated synthetic imports. The downloadable JSON is served from the frontend's production assets.

Results ranks possible privilege chains. Start with the selected highest-priority path, then choose the Mina Rahman path to explain a longer membership → local administration → session → privileged membership chain. Use zoom/fit, inspect nearby relationships, expand Source evidence, and review Break this path. Filters match names, severity, object types, and relationship types. Export PDF for a narrative and JSON for the complete returned evidence.

For alternate routes select Mina Rahman as Starting identity, open Analysis limits & options, and choose multiple paths or a lowest-cost/shortest-hop query. Rerun and inspect the resulting scope. No operation contacts or changes Active Directory.

The downloadable example JSON uses the same small synthetic fixture. All names, objects, sessions, permissions, and evidence are fictional. `python scripts/adpathlens.py seed` loads it idempotently; `demo-reset` deliberately deletes that demo collection's datasets/history before reloading, so use the reset command only when intended.

The app restores the selected collection, snapshot, and latest completed analysis on reload. Its focused navigation is Home, Analyze, Results, and About.
