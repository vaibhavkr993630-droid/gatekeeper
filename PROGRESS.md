# PROGRESS — GateKeeper

Distributed rate-limiting & API gateway platform. See `GATEKEEPER_BRIEF.md` for full vision.

## Active phase
Phase 1 — Foundation (COMPLETE, pending review)

## Phase status
- [x] Phase 1 — Foundation: Tenant model, JWT auth (register/login), dashboard shell, Alembic, pytest
- [ ] Phase 2 — Service registration & policy config
- [ ] Phase 3 — Rate limiting core (token bucket + sliding window counter, Redis Lua)
- [ ] Phase 4 — Gateway/proxy layer
- [ ] Phase 5 — Real-time tenant dashboard (WebSocket)
- [ ] Phase 6 — Platform admin view
- [ ] Phase 7 — Hardening (Docker Compose, CI, Sentry, tests)
- [ ] Phase 8 — Deploy

## Phase 1 — what was built and why

### Structure
Layered backend under `backend/app/` per the brief: `api/routers`, `core`, `models`,
`schemas`, `crud`, `db`. `gateway/`, `rate_limit/`, `ws/`, `services/` are stubbed with
READMEs so the shape is visible from day one but not yet implemented.

### Auth model (important distinction, carried through the whole project)
Two *separate* auth concerns, deliberately not merged:
1. **Tenant dashboard auth** — JWT bearer tokens. A `TenantUser` (email + password)
   logs in, receives a short-lived access token, and uses it to manage their tenant's
   resources. Implemented this phase.
2. **Gateway traffic auth** — per-service API keys. Used later (Phase 2+) to authenticate
   *requests flowing through* the proxy. NOT a JWT. Different lifecycle, different threat
   model (long-lived, machine-to-machine, scoped to one service).

### Entities this phase
- `Tenant` — a company/developer account. Owns services (later) and users.
- `TenantUser` — a login identity belonging to a tenant. Multiple users per tenant
  supported from the start (cheap now, expensive to retrofit).

### Password + token security
- Passwords hashed with bcrypt via `passlib`.
- JWT signed HS256 with `SECRET_KEY` from env; `sub` claim = TenantUser id, plus
  `tid` (tenant id) so downstream authz checks never need a DB hit just to scope.

### DB
- SQLAlchemy 2.0 async (`asyncpg` in prod, `aiosqlite` in tests).
- Alembic configured from day one. Initial migration creates `tenants` + `tenant_users`.

### Tests
- `pytest` + `pytest-asyncio` + `httpx.AsyncClient` against an in-memory SQLite DB.
- Covers: register creates tenant+user, duplicate email rejected, login returns token,
  bad password rejected, `/me` requires a valid token and returns the caller's tenant.

## Known simplifications (demo-scale vs production)
- Single Postgres, single Redis (later) — no HA/replication.
- Access tokens only, no refresh-token rotation.
- SECRET_KEY from a single env var, no key rotation / JWKS.
- Frontend dashboard shell is intentionally near-empty this phase.

## Key decisions log
- 2026-08-31: `TenantUser` separate from `Tenant` (multi-user tenants from v1).
- 2026-08-31: JWT carries `tid` to avoid a DB lookup for tenant-scoping on every request.
- 2026-08-31: API-key auth explicitly deferred to Phase 2 — it belongs with Service.
