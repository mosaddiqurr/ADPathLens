FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup --system authzdiff && adduser --system --ingroup authzdiff authzdiff
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
RUN mkdir -p /reports && chown -R authzdiff:authzdiff /app /reports
USER authzdiff
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=127.0.0.1"]
