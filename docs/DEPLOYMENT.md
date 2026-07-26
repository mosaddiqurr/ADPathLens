# Deployment

PostgreSQL 16 is the recommended database. Configure secrets through the environment, enable secure
cookies behind HTTPS, set an explicit frontend origin allow-list, and mount a writable report
directory. Run `python -m alembic upgrade head` before serving.

Docker Compose defines PostgreSQL, the FastAPI container, Nginx/Vite frontend build, health checks,
named database storage, and report storage. Runtime Docker validation was unavailable on the
2026-07-26 Windows host because Docker was not installed; only configuration inspection and native
runtime validation were performed.

The v1 analysis limiter is process-local. Do not horizontally scale backend workers without a
coordinated external job/limit mechanism.
