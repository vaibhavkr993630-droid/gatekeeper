# Project Brief: GateKeeper — Distributed Rate Limiting & API Gateway Platform

## How to use this document
Read this fully before writing code. Create a `PROGRESS.md` in the repo root
at the start and keep it updated after every milestone — what's done, what's
next, key decisions, deviations from this brief with reasons, and current
active phase. Read `PROGRESS.md` first in any new session before touching code.

Work through phases in order. Do not start a phase before the previous one
is functionally complete and understood — this is a learning project, not
just a delivery. After each phase, summarize what was built, why key
decisions were made (especially around concurrency/atomicity), and what
the user should understand before moving on.

---

## Product Vision & Mental Model

GateKeeper is a **multi-tenant API rate-limiting gateway**, similar in spirit
to how Kong, Cloudflare, or AWS API Gateway offer rate limiting as a service.

**Who uses it and how:**

1. **The platform (GateKeeper itself)** — the underlying infrastructure
   that companies sign up to use.
2. **Tenants (companies/developers)** — they register on GateKeeper, create
   one or more "services" (representing their own API or a specific
   endpoint they want protected), configure a rate-limit policy for it
   (e.g., 100 requests/minute using sliding window), and receive a unique
   **gateway endpoint + API key**. They then point their own application's
   traffic through that gateway endpoint instead of hitting their backend
   directly. GateKeeper enforces the limit and forwards allowed requests
   to their real backend URL.
3. **Requests flowing through** — every incoming request to a tenant's
   gateway endpoint is checked against their configured limit; it's either
   forwarded (allowed) or rejected with `429 Too Many Requests` (blocked).

**Visibility model:**
- **Tenants** log into their own dashboard and see **only their own
  service(s)**: live request feed (allowed/blocked, timestamp, source IP,
  which limit rule triggered), usage graphs, remaining quota, and their
  service configuration. They cannot see any other tenant's data.
- **Platform admin** logs into a separate admin view and sees **system-wide
  operational health**, not per-request business detail of each tenant's
  traffic: total registered tenants, total request volume across the
  platform, system load/latency, Redis health, which tenants are near/over
  their plan limits, error rates. "Site reliability view," not "snoop on
  tenant traffic."

---

## Explicit Scope Boundaries

**In scope:**
- Tenant auth (JWT), tenant registration, service registration under a tenant
- Rate-limit policy configuration per service: algorithm choice (token
  bucket / sliding window log / sliding window counter), limit + window
- Reverse-proxy request forwarding: gateway receives request → checks
  limit → forwards to tenant's real backend URL if allowed → streams
  response back; rejects with 429 if not
- Distributed, atomic rate-limit enforcement via Redis (Lua scripting or
  `INCR`+`EXPIRE` patterns for atomicity)
- Live traffic feed per tenant service via WebSocket
- Usage dashboards (requests/min, block rate, quota remaining), tenant-scoped
- Platform admin dashboard: system-wide metrics only
- API key management per tenant service
- Request logging (short retention is fine)
- Docker Compose, Alembic migrations, pytest, GitHub Actions CI
- Deployed publicly

**Out of scope for v1:**
- Billing/payment integration — plan tiers can be simple config values
- Geographic/multi-region gateway distribution
- Full observability stack (Prometheus/Grafana)
- WAF / security rule features beyond rate limiting
- Protocols other than HTTP

---

## Tech Stack

**Backend:** Python 3.12+, FastAPI, PostgreSQL, SQLAlchemy 2.0 (async),
Pydantic v2, Alembic

**Rate limiting core:** Redis — used for **atomic distributed counters**.
Use Redis Lua scripting (`EVAL`) to make check-and-increment operations
atomic. Implement and compare at least two algorithms: token bucket and
sliding window counter.

**Reverse proxy layer:** `httpx` (async client) to forward allowed
requests and stream the response back

**Real-time:** FastAPI WebSockets, scoped per tenant

**Auth:** JWT for tenant dashboard login; separate API key mechanism for
gateway traffic authentication

**Frontend:** React + TypeScript, TanStack Query, Tailwind CSS, Recharts,
native WebSocket client

**Testing:** pytest, pytest-asyncio, httpx.AsyncClient; include concurrency
tests that fire simultaneous requests at a rate-limited endpoint

**DevOps:** Docker + Docker Compose, GitHub Actions CI, structured logging,
`/health` endpoint, Sentry (free tier)

---

## Architecture Requirements

```
app/
  api/routers/     # tenant auth, service management, admin routes
  gateway/         # the actual proxy/forwarding logic — the hot path
  rate_limit/      # algorithm implementations, pluggable, same interface
  core/            # config, security, dependencies
  models/          # SQLAlchemy models
  schemas/         # Pydantic schemas
  services/        # business logic
  crud/            # data access
  ws/              # WebSocket connection manager (per-tenant scoping)
  db/              # session, base, migrations
tests/
```

Key entities: Tenant, TenantUser, Service, APIKey, RequestLog, RateLimitRule.

The rate-limiting algorithms must share a common interface
(`RateLimiter.check(key) -> (allowed: bool, remaining: int)`) so a
service's configured algorithm can be swapped without touching the gateway
forwarding logic.

The gateway request path should be kept as lean/fast as reasonably possible.

---

## Build Order (phases)

**Phase 1 — Foundation:** Tenant model, JWT auth (register/login), tenant
dashboard shell, Alembic from day one, basic pytest on auth.

**Phase 2 — Service Registration & Policy Config:** Service model, API key
generation per service, CRUD endpoints, RBAC.

**Phase 3 — Rate Limiting Core:** Token bucket and sliding window counter
against Redis with Lua scripting. Concurrency tests first.

**Phase 4 — Gateway/Proxy Layer:** Wire rate limiter into request-forwarding
path. Log every request.

**Phase 5 — Real-Time Tenant Dashboard:** Per-tenant WebSocket manager, live
feed, usage charts.

**Phase 6 — Platform Admin View:** Separate admin auth/role, system-wide
metrics only.

**Phase 7 — Hardening:** Docker Compose full stack, CI, structured logging,
Sentry, expand tests (concurrency + tenant isolation), README.

**Phase 8 — Deploy:** Deploy backend/DB/Redis and frontend, smoke test.

---

## Working Style
- Explain *why*, not just *what* — especially rate-limiting tradeoffs,
  Redis + Lua atomicity, WebSocket tenant isolation.
- Before each phase, restate scope and confirm before starting.
- Flag demo-scale simplifications vs. production in `PROGRESS.md`.
- Keep `PROGRESS.md` granular.
