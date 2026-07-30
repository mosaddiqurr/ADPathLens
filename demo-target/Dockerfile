FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /demo
RUN addgroup --system demo && adduser --system --ingroup demo demo
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY app ./app
USER demo
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
