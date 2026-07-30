# AuthZDiff demo target

This service is deliberately vulnerable and contains fictional, resettable data. It exists only
to validate AuthZDiff in an isolated local lab. Never expose it to an untrusted network.

Synthetic bearer tokens:

- `demo-admin-token`
- `demo-user-a-token`
- `demo-user-b-token`

Run locally on loopback:

```powershell
..\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Reset in-process fixtures with `python -m app.reset`. The HTTP reset endpoint requires the
`DEMO_RESET_TOKEN` environment value in `X-Demo-Reset-Token`.
