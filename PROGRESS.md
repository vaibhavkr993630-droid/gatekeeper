# PROGRESS — GateKeeper

Distributed rate-limiting & API gateway platform. See `GATEKEEPER_BRIEF.md` for full vision.

## Active phase
Phase 3 — Rate Limiting Core (COMPLETE, pending review — NOT committed)

## Phase status
- [x] Phase 1 — Foundation: Tenant model, JWT auth (register/login), dashboard shell, Alembic, pytest
- [x] Phase 2 — Service registration, per-service rate-limit policy, API keys, CRUD + RBAC
- [x] Phase 3 — Token bucket + sliding window counter on Redis via Lua; concurrency tests
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

## Phase 3 — what was built and why

### The problem this phase solves
A naive limiter does `GET count` → decide in Python → `INCR`. Under concurrent load
two requests both read count=99 (limit 100), both decide "allowed", both increment →
101. Classic check-then-act (TOCTOU) race. `test_naive_check_then_incr_over_admits`
demonstrates it empirically (250 concurrent → >100 admitted).

### The fix: one Lua script per check
Redis executes a Lua script as a single indivisible unit — no other command
interleaves. The read-decide-write happens atomically server-side, so the count is
always exact. Scripts are loaded once and invoked by SHA via `EVALSHA`
(redis-py's `register_script`, with automatic `EVAL` fallback on `NOSCRIPT`).
`test_token_bucket_exact_under_concurrency` / `..._sliding_window_...` fire 250
concurrent `check()` calls and assert **exactly 100** admitted.

### Time is an argument, not `redis.call('TIME')`
`check(key, *, now=None)` — `now` defaults to wall clock but tests pass explicit
values. Keeps each script a pure function of its inputs: deterministic (safe under
any Redis replication mode) and testable without `sleep()` — window rollover and
bucket refill are tested by advancing `now`.

### Common interface (pluggable strategy)
`app/rate_limit/base.py`: `RateLimiter.check(key, *, cost=1, now=None) -> RateLimitResult`
(`allowed`, `limit`, `remaining`, `retry_after`). `factory.get_rate_limiter(rule, redis)`
maps a stored policy to an implementation; the gateway (Phase 4) calls it and never
branches on the algorithm.

### Algorithms
- **Token bucket** (`scripts/token_bucket.lua`) — HASH `{tokens, ts}`; refill for
  elapsed time then consume `cost`. `capacity` = `burst or limit`, `rate` =
  `limit / window_seconds`. Burst-friendly; long-run average held at `rate`.
- **Sliding window counter** (`scripts/sliding_window.lua`) — two fixed sub-window
  counters; `estimate = prev * (1 - elapsed_fraction) + cur`. O(1) memory vs. the
  sliding-window *log* (which stores every timestamp in a ZSET). Bounded
  approximation error near boundaries; `test_sliding_window_smooths_the_boundary`
  shows it stops the "double quota across the boundary" that a fixed window allows.

### Keys
`make_key(scope, identifier)` → `rl:{scope}:identifier`. `{scope}` is a Redis Cluster
hash tag so the sliding-window limiter's multiple sub-keys stay on one slot.
Harmless on a single node.

### Redis client
`app/core/redis.py` — lazy shared async client, `decode_responses=True` (Lua string
returns arrive as `str`). Closed on app shutdown (lifespan). `/health` now pings it.

### Tests — 26 total (was 12)
Concurrency (the headline proof), refill-over-time, capacity cap, retry_after
sanity, window rollover, boundary smoothing, key isolation, factory mapping,
config validation, and the naive-race counter-example. Integration tests use a
**bounded** `BlockingConnectionPool` so hundreds of concurrent checks queue on a
connection (as a real service would) rather than opening a socket per task.

## Known simplifications (demo-scale vs production)
- `ApiKey.is_active` / `last_used_at` columns exist but aren't enforced/updated yet —
  Phase 4 (gateway) wires them. Revoke currently hard-deletes.
- One rule per service enforced only by the unique index on `rate_limit_rules.service_id`.
- `upstream_url` isn't validated against SSRF (private IPs, localhost) — noted for Phase 4/7.
- App Redis client uses redis-py's default (unbounded) connection pool. Production
  should set an explicit bounded pool sized to the worker's concurrency.
- Sliding-window-counter `retry_after` is an approximation (documented in the .lua).
- Redis is a single instance — no HA. A Redis failure currently means the limiter
  errors; Phase 4 must decide fail-open vs. fail-closed for the gateway.
- Single Postgres, single Redis (later) — no HA/replication.
- Access tokens only, no refresh-token rotation.
- SECRET_KEY from a single env var, no key rotation / JWKS.
- Frontend dashboard shell is intentionally near-empty this phase.

## Key decisions log
- 2026-08-31: `TenantUser` separate from `Tenant` (multi-user tenants from v1).
- 2026-08-31: JWT carries `tid` to avoid a DB lookup for tenant-scoping on every request.
- 2026-08-31: API-key auth explicitly deferred to Phase 2 — it belongs with Service.
