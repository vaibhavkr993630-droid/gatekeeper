# PROGRESS — GateKeeper

Distributed rate-limiting & API gateway platform. See `GATEKEEPER_BRIEF.md` for full vision.

## Active phase
Phase 2 — Service Registration & Policy Config (COMPLETE, pending review — NOT committed)

## Phase status
- [x] Phase 1 — Foundation: Tenant model, JWT auth (register/login), dashboard shell, Alembic, pytest
- [x] Phase 2 — Service registration, per-service rate-limit policy, API keys, CRUD + RBAC
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
- Unit: `pytest` + `pytest-asyncio` + `httpx.AsyncClient` against in-memory SQLite.
  Covers register / duplicate-email / login / bad-password / token-protected `/me`.
- Integration (`tests/integration/`): same auth flow against the **real Postgres** from
  docker-compose — each test runs in a transaction rolled back afterward; auto-skips
  when the DB is unreachable. Verified `alembic upgrade head` + `alembic check` (models
  and migration are in sync) against Postgres 16.
- CI now spins up Postgres + Redis service containers and runs migrate + check + pytest.

## Phase 2 — what was built and why

### Entities
- `Service` — a tenant's registered backend. `upstream_url` (where allowed traffic is
  forwarded, Phase 4) + `public_id` (opaque 24-char hex, the gateway routing key —
  safe to expose, unlike the numeric PK). `tenant_id` FK with `ON DELETE CASCADE`.
- `RateLimitRule` — the policy, its **own table** (1:1 with Service in v1) rather than
  columns on Service, so per-method / per-path rules can be added later without a
  Service-table migration. Fields: `algorithm` (enum: token_bucket /
  sliding_window_counter), `limit`, `window_seconds`, `burst` (nullable; token-bucket
  capacity, defaults to `limit`).
- `ApiKey` — authenticates gateway traffic for one service. **Only a SHA-256 hash is
  stored** (`key_hash`, unique-indexed for O(1) lookup in Phase 4) plus `prefix`
  (`gk_` + 8 chars, safe to show) and `last_four`. Plaintext (`gk_<43url-safe>`) is
  returned exactly once, at creation.

### RBAC — tenant isolation
Every service-scoped route goes through the `get_owned_service` dependency: it loads
the service filtered by BOTH id AND `current_user.tenant_id`. A service owned by
another tenant returns **404, not 403**, so cross-tenant existence isn't leaked.
`list_services` is tenant-filtered at the query. Nested key routes inherit the same
gate (they depend on `OwnedService`).

### Endpoints (all under `/api/services`, JWT-protected)
`GET /` · `POST /` (creates service + rule atomically) · `GET /{id}` · `PATCH /{id}`
(name / upstream_url / is_active) · `PUT /{id}/rule` (replace policy) · `DELETE /{id}`
· `GET /{id}/keys` · `POST /{id}/keys` (→ one-time plaintext) · `DELETE /{id}/keys/{key_id}`.

### Validation
Pydantic: `limit` 1..1e6, `window_seconds` 1..86400, `burst >= limit` (model validator),
`upstream_url` must be `AnyHttpUrl`.

### Migration
`0002_services.py` — hand-cleaned from `--autogenerate` (ruff-clean, style matches
0001). `alembic upgrade head` + `alembic check` verified against Postgres 16.

### Tests
- Unit (SQLite): create/get, RBAC isolation (B can't GET/DELETE A's service → 404),
  patch service + replace rule, invalid rule (window 0, burst < limit) → 422, API key
  lifecycle (plaintext once, never in list, revoke), auth required.
- Integration (Postgres): service + key persist; `ON DELETE CASCADE` drops keys when
  the service is deleted.
- Total suite: 12 passing.

### Frontend
`ServicesPanel` on the dashboard: list, create form (name / URL / algorithm / limit /
window), delete, mint API key (one-time reveal banner). TanStack Query for cache.

## Known simplifications (demo-scale vs production)
- `ApiKey.is_active` / `last_used_at` columns exist but aren't enforced/updated yet —
  Phase 4 (gateway) wires them. Revoke currently hard-deletes.
- One rule per service enforced only by the unique index on `rate_limit_rules.service_id`.
- `upstream_url` isn't validated against SSRF (private IPs, localhost) — noted for Phase 4/7.
- Single Postgres, single Redis (later) — no HA/replication.
- Access tokens only, no refresh-token rotation.
- SECRET_KEY from a single env var, no key rotation / JWKS.
- Frontend dashboard shell is intentionally near-empty this phase.

## Key decisions log
- 2026-08-31: `TenantUser` separate from `Tenant` (multi-user tenants from v1).
- 2026-08-31: JWT carries `tid` to avoid a DB lookup for tenant-scoping on every request.
- 2026-08-31: API-key auth explicitly deferred to Phase 2 — it belongs with Service.
