FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts
COPY docker-entrypoint.sh ./

RUN pip install --no-cache-dir . && chmod +x docker-entrypoint.sh

# PORT is injected by most PaaS (Railway, Render, ...); defaults to 8000 locally.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD curl -sf "http://localhost:${PORT}/health" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
# --proxy-headers + --forwarded-allow-ips: trust X-Forwarded-Proto/-For from the
# platform's edge proxy so redirects use https and the logged scheme is right.
CMD uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
