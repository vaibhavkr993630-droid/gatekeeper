# GateKeeper

Multi-tenant API rate-limiting gateway — tenants register a backend, configure a
rate-limit policy (token bucket / sliding window counter), and route traffic through
GateKeeper, which enforces the limit atomically via Redis and forwards allowed
requests to their real backend.

This is a learning-focused infrastructure project. See `GATEKEEPER_BRIEF.md` for the
full product vision and `PROGRESS.md` for current build status.

## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic, Pydantic v2
- Rate-limit core: Redis + Lua scripting (atomic check-and-increment)
- Reverse proxy: httpx (async, streaming)
- Real-time: FastAPI WebSockets (per-tenant scoped)
- Frontend: React + TypeScript, TanStack Query, Tailwind, Recharts
- Infra: Docker Compose, GitHub Actions CI

## Two auth concerns (kept separate on purpose)
1. **Dashboard auth** — JWT. Tenant users log in to manage their services.
2. **Gateway auth** — per-service API keys authenticating traffic through the proxy.

## Local dev

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d db redis        # from repo root
alembic upgrade head
uvicorn app.main:app --reload
pytest
```

## Scaling notes (what would change at real scale)
- Redis colocated with gateway nodes; tuned connection pools.
- Postgres read replicas for dashboard/analytics queries.
- RequestLog moved to a TSDB / short-retention store, not the primary DB.
- Multi-region gateway with regional Redis (out of scope for v1).
