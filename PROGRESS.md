# PROGRESS — GateKeeper

Distributed rate-limiting & API gateway platform. See `GATEKEEPER_BRIEF.md` for full vision.

## Active phase
Phase 7 — Hardening (COMPLETE, pending review — NOT committed)

## Phase status
- [x] Phase 1 — Foundation: Tenant model, JWT auth (register/login), dashboard shell, Alembic, pytest
- [x] Phase 2 — Service registration, per-service rate-limit policy, API keys, CRUD + RBAC
- [x] Phase 3 — Token bucket + sliding window counter on Redis via Lua; concurrency tests
- [x] Phase 4 — Reverse-proxy gateway: API-key auth → rate check → httpx forward / 429; RequestLog
- [x] Phase 5 — Per-tenant WebSocket live feed + usage charts (stats endpoint)
- [x] Phase 6 — Platform admin auth + system-wide overview; frontend design-system pass
- [x] Phase 7 — Full-stack Docker, structured logging, Sentry, SSRF guard, CI expansion, more tests
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

## Phase 4 — what was built and why

### The request path (`app/gateway/`)
`{ANY} /gw/{public_id}/{path}` — one catch-all route:

1. **Client IP** — `X-Forwarded-For` first hop if `trust_forwarded_for` (default on;
   only safe behind an ingress that overwrites the header), else the socket peer.
2. **Identify** (`identity.resolve_target`) — `X-API-Key` or `Authorization: Bearer`
   → SHA-256 → **one** indexed lookup on `api_keys.key_hash`, eager-loading the
   service + rule. The URL's `public_id` is confirmed against the key's service
   (mismatch → 404, as if the route doesn't exist). Inactive key → 401, disabled
   service → 403. Auth failures are **not** logged to RequestLog (no tenant to
   attribute them to).
3. **Rate check** — `get_rate_limiter(rule, redis).check(make_key(public_id, ip))`.
   One Redis round-trip. Over limit → `429` + `Retry-After` + `X-RateLimit-*`.
4. **Forward** (`forwarder.forward`) — shared pooled `httpx.AsyncClient`, method +
   path + query + body to `upstream_url`. Strips hop-by-hop headers and the
   gateway's own `Authorization`/`X-API-Key` (the tenant's backend shouldn't see
   them); adds `X-Forwarded-For`/`-Host`. **Streams the raw response back**
   (`aiter_raw`), closing the upstream connection via background task. Upstream
   timeout → `504`, connection error → `502`.
5. **Record** (`recorder.record_request`) — one `RequestLog` row + `api_key.last_used_at`
   touch, as a FastAPI **BackgroundTask after the response**. The caller never
   waits on the DB. Uses its own session (the request's is already closed).

### Hot-path budget (per request)
1 indexed DB read · 1 Redis EVALSHA · 1 pooled upstream call. Everything else is
in-memory. Logging + key-touch are off-path. Documented scale changes in
`app/gateway/README.md` (colocate Redis, cache the key lookup, batch RequestLog).

### Fail-open vs fail-closed
`rate_limit_fail_open` (default **True**). Redis down → request is allowed through
with `X-RateLimit-Bypassed: true` and a WARNING log; set False to return `503`
instead. A limiter outage shouldn't take down every tenant's traffic — but the
choice is a config knob, not baked in.

### Two planes, still separate
`/api/services/*` = management (JWT, tenant configures). `/gw/*` = data plane
(API key, tenant *traffic*). Different routers, different auth, different concerns.

### Entities
- `RequestLog` — tenant_id (denormalised from service so the feed query needs no
  join), service_id, created_at (all indexed), allowed, status_code, method, path,
  client_ip, rule_algorithm, latency_ms (upstream TTFB; null for blocked/failed).
  Migration `0003_request_logs`.

### Tests
- Unit (`test_gateway_unit.py`, no I/O): URL building, header filtering (strip +
  XFF append), API-key extraction, client-IP resolution, Retry-After ceil.
- Integration (`test_gateway.py`, real PG + Redis + a real echo upstream on an
  ephemeral port): allowed request forwarded with fidelity + headers stripped,
  limit enforced (both algorithms), every request recorded, missing/bad key,
  wrong `public_id` → 404, disabled service → 403, upstream status passthrough,
  upstream down → 502. `gateway_client` fixture uses a real committing session
  (background tasks commit) and truncates after.
- Full suite: **55 passing** at end of Phase 4. Verified `alembic upgrade head` +
  `alembic check` against Postgres 16 (migration 0003 in sync).

## Phase 5 — what was built and why

### Live feed (`app/ws/`)
`ws://<host>/ws/feed?token=<tenant JWT>`.

- **`ConnectionManager`** (`manager.py`) — `{tenant_id: {sockets}}`. `publish(tenant_id, msg)`
  can only reach sockets filed under that tenant. Broken sockets are evicted, not
  retried, and don't block siblings.
- **Isolation is structural** — the endpoint (`router.py`) verifies the JWT and
  takes `tenant_id` *from the token*, never from the client. There is no
  "subscribe" message; a client cannot ask for anything but its own feed.
  `test_ws_feed.py::test_gateway_request_reaches_only_the_owning_tenant` fires a
  request for tenant A and asserts tenant B's socket stays empty.
- On connect: a snapshot of the tenant's last 50 requests, then live events.
- The gateway publishes via **`broadcast.broadcast_request`**, a BackgroundTask
  added alongside `record_request` — independent (either can fail alone), off the
  hot path, and skipped entirely when the tenant has no sockets connected.

### Why in-process, not Redis pub/sub
The brief scopes Redis to atomic counters. The feed uses in-process fan-out.
Trade-off (documented in `app/ws/README.md`): two uvicorn workers → a client on
worker A misses events the gateway handled on worker B. At scale each gateway
node PUBLISHes to Redis pub/sub (or Kafka/NATS) and each dashboard node
SUBSCRIBEs; the `ConnectionManager` interface is unchanged, only its feed source.

### WebSocket auth
JWT in the query string (`?token=`) — browsers can't set headers on `WebSocket`.
Noted risk: tokens in URLs can end up in logs; first-message auth would avoid it.
Bad/expired token → close code `4401` before `accept()`.

### Usage stats — `GET /api/services/{id}/stats?minutes=N`
Behind `OwnedService` (same RBAC as the rest of `/api/services`). Postgres
`date_trunc('minute', ...)` with a `count(*) FILTER (WHERE NOT allowed)` for the
per-minute series + totals + block rate. Frontend polls every 5s and renders
requests/min (stacked area) + blocked/min (bar) with Recharts; "quota" shown as
the rule's `limit / window` per client IP.

### DB engine refactored to lazy + resettable
`app/db/session.py` — `SessionLocal()` now resolves a lazily-built engine on
first use, with `reset_db_engine()`. Fixes "Future attached to a different loop"
across pytest's function-scoped loops (the background-task session was a process
global). An autouse fixture resets the engine + httpx client around every
integration test; the earlier per-fixture monkeypatch hack is gone.

### Tests — 64 total (was 55)
`test_ws_unit.py` (ConnectionManager isolation / cleanup / dead-socket) +
`test_ws_feed.py` (gateway→feed isolation, blocked events broadcast, token
reject, snapshot) + `test_stats.py` (aggregates reflect traffic, tenant-scoped).

## Phase 6 — what was built and why

### Two auth planes, cryptographically separate
`AdminUser` is a standalone entity — not a tenant, not linked to one. Admin JWTs
are signed with `ADMIN_SECRET_KEY`, a **different key** from tenant tokens
(`SECRET_KEY`). This isn't "check a different claim" — a tenant token cannot be
turned into an admin token even if an attacker controls the claims, because the
signature won't verify against the admin key, and vice versa.
`test_tenant_token_is_rejected_on_admin_routes` / the reverse prove it end to end.

### No public admin signup
Admins are platform operators, not customers. `scripts/create_admin.py` is a CLI
(`python -m scripts.create_admin --email ... `) that inserts directly via the
app's session — mirrors how real platforms provision the first ops account.
`test_no_public_admin_registration_endpoint` checks `/api/admin/auth/register`
is a plain 404.

### `GET /api/admin/overview` — aggregates only
Tenants/services totals, requests/blocked/error-rate/avg-latency over the last
24h, Redis + DB health, a 60-minute platform-wide requests series, and tenants
at ≥80% of their **plan's daily request quota** (`app/core/plans.py` — a plain
dict, not a billing system, per the brief). Every field is a count or an
average; no route in `app/api/routers/admin.py` can return a path, client IP,
or any other per-request detail — `test_overview_reflects_traffic_with_no_per_request_detail`
asserts the seeded upstream path never appears in the response body. The
endpoint degrades (`db_ok`/`redis_ok: false`) instead of 500ing when a backend
is unhealthy, so the ops view itself stays up during partial outages.

### Frontend: a real design system, not just "make it pretty"
Added `components/ui/` (Button, Card, Badge, StatTile, StatusPill, Skeleton,
EmptyState, Toast, CopyButton) and a `tailwind.config.js` token layer (brand
palette, shadows, motion). Applied consistently across both the tenant
dashboard (revamped: collapsible create-service form, service cards with
copy-to-clipboard gateway id, inline delete confirmation, toasts instead of
silent failures, skeleton loading states) and the new admin dashboard, so the
two feel like one product rather than a bolted-on internal tool. Admin has its
own token (`gk_admin_token`, separate from the tenant's `gk_token`) and its own
visually distinct login screen — deliberately, so a tenant user is never
confused about which account they're using.

### Real end-to-end verification (not just unit tests)
Got a real headless Chromium working (extracted `libnspr4`/`libnss3`/`libasound2`
from `.deb` packages with `dpkg -x` — no root needed — since the sandboxed
Playwright install lacked them) and drove the actual running app: registered a
tenant, created a service pointed at `https://httpbin.org`, minted a key, sent
real requests through `/gw/{public_id}/...`, and watched them land in the live
WebSocket feed and the usage chart *in the same session*, then confirmed the
same 6 requests rolled up correctly into the platform admin's 24h totals and
60-minute series — proving the gateway → rate-limiter → RequestLog → WS
broadcast → tenant dashboard → admin aggregate pipeline end to end, live.

This surfaced one real UX bug (below) and confirmed one apparent bug was in
fact deliberate: a login attempt with a never-registered email returns the
same "Invalid email or password" as a wrong password for an existing one —
this is intentional (prevents user/email enumeration), not a malfunction.
But the page gave a new visitor no clear path to "I don't have an account yet,"
so:
- `LoginPage` now uses a two-tab **Sign in / Create account** switcher instead
  of a small footnote link, and shows an inline "New here? Create an account"
  hint directly under a login error.
- Switching tabs now clears the password field (was previously carried over).
- The "new API key" reveal banner's amber tone was too pale to read as urgent;
  strengthened it.

## Phase 7 — what was built and why

### Full-stack Docker
`backend/Dockerfile` (python:3.12-slim + curl for the `HEALTHCHECK`) and
`frontend/Dockerfile` (multi-stage: `node:20-alpine` build → `nginx:1.27-alpine`
serving the static bundle). `frontend/nginx.conf` reverse-proxies `/api`, `/gw`,
and `/ws` (with the `Upgrade`/`Connection` headers a WebSocket needs) to the
backend container — the browser only ever talks to one origin, so the
containerized deployment needs **no CORS** at all (CORS only matters for the
`vite`-dev-server-on-a-different-port workflow). `docker-entrypoint.sh` runs
`alembic upgrade head` before `uvicorn` starts. `docker-compose.yml` now brings
up the whole stack (`docker compose up -d --build`); `docker compose up -d db
redis` (unchanged) still works for the hot-reload local-dev loop.

### Structured logging + request correlation
`app/core/logging.py` — plain text locally (readable in a terminal, the
default), one JSON object per line when `LOG_JSON=true` (the container
default; verified live in `docker compose logs backend` — see below).
`app/core/request_context.py` — a `ContextVar`-backed middleware gives every
request a `request_id` (reuses an inbound `X-Request-ID` if the caller sent
one) and echoes it in the response header; a logging `Filter` stamps it onto
any log record emitted *during* that request's handling. Caveat found by
actually reading the container logs: uvicorn's own access-log line is written
by the ASGI server after the middleware's `finally` already reset the
context var, so it always shows `request_id: "-"` — only *our* application/
gateway log calls made while handling the request carry the real id. Good
enough for its purpose (tracing one request through our own logic) but worth
knowing precisely why, not just that it "mostly works".

### Sentry — opt-in, not on by default
`app/core/sentry.py::init_sentry()` is a no-op unless `SENTRY_DSN` is set, so
local dev and CI never need a Sentry account or a network call to Sentry at
startup. `sentry-sdk`'s auto-instrumentation picks up the ASGI app once
initialized before the app is constructed.

### SSRF guard on `upstream_url`
`app/core/net_safety.py::assert_public_upstream` — rejects loopback, private
(`10.x`/`172.16-31.x`/`192.168.x`), link-local (`169.254.x` — the cloud
metadata-endpoint range, the single most common real-world SSRF target),
reserved, and multicast targets. Literal IPs are checked purely computationally
(no I/O); hostnames are resolved via `socket.getaddrinfo` off the event loop
(`asyncio.to_thread`, since DNS resolution is blocking) and every returned
address is checked. Wired into `POST/PATCH /services` behind
`settings.block_private_upstreams` — **off by default**, because a demo/local
upstream is very often loopback (the whole test suite's stub servers, for a
start) and this project's pattern throughout has been "safe default for a real
deployment, explicit opt-in flag, tested when the flag is on" (see
`rate_limit_fail_open`, `trust_forwarded_for`). Documented as best-effort: it
checks at creation time, so a hostname that later re-resolves to a private
address ("DNS rebinding") isn't caught — a production version would pin the
resolved IP at connection time instead of trusting a one-time hostname check.

### CI expanded
Added a `frontend` job (`npm ci && npm run build`, which is `tsc -b && vite
build` — typecheck and build in one) and a `docker` job that builds both
Dockerfiles, gated on both other jobs passing. CI now proves the containers
this README tells you to run actually build, not just that the source compiles.

### Tests — 96 total (was 73)
`test_net_safety.py` (SSRF logic, network-free for every literal-IP case),
`test_ssrf_guard.py` (the guard wired into the API, on vs. off), `test_logging.py`
(JSON formatter shape + exception formatting + request-id header on every
response, including echoing a caller-supplied one). Concurrency and tenant
data-isolation coverage the brief calls out for this phase was already in place
from earlier phases — `tests/integration/test_rate_limit.py` (250-way concurrent
checks land exactly on the limit) and `tests/integration/test_ws_feed.py`
(`test_gateway_request_reaches_only_the_owning_tenant` — tenant B's socket gets
zero events from tenant A's traffic) — noted here rather than duplicated.

### Verified live: `docker compose up -d --build`, not just `docker build`
Ran the actual full stack, not only confirmed the images build. Found and fixed
a real bug this way: the frontend container reported unhealthy even though
`curl http://localhost:8080/` worked fine from the host. Cause — Alpine/musl
resolves `localhost` to `::1` first, nginx's config here only binds IPv4 `:80`,
so the container's *own* healthcheck (`wget http://localhost/`, running inside
the container) hit "connection refused" while every *external* request (through
the published port, arriving as IPv4) worked. Fixed by pointing the healthcheck
at `127.0.0.1` explicitly. Confirmed after the fix: all four containers
`healthy`; migrations ran automatically on backend boot (`alembic.runtime
.migration` log lines before the app started); backend logs are valid JSON
per line with `LOG_JSON=true`; `curl :8080/api/services` (no token) correctly
reverse-proxied to the backend and got `401`, proving the nginx → backend path
works end to end.

## Known simplifications (demo-scale vs production)
- SSRF guard is best-effort (no DNS-rebinding protection) and off by default —
  set `BLOCK_PRIVATE_UPSTREAMS=true` for a real deployment.
- Structured logs go to stdout only; no shipping to a log platform configured
  (that's the "bring your own aggregator" half of structured logging).
- `docker-entrypoint.sh` runs migrations on every container boot — fine for one
  instance, would race across N replicas booting together in production.
- Sentry integration is wired but never exercised against a live DSN in this
  environment (no Sentry account here) — it's a no-op until one is provided.
- Admin overview recomputes every field on each request (no caching) — fine at
  this data volume; would want a short cache or pre-aggregation at real scale.
- Plan quotas are a static in-code dict, not stored per-tenant or editable via API.
- Live feed is in-process fan-out — single uvicorn worker only (see above).
- WebSocket JWT is passed in the query string.
- Stats query scans `request_logs` per call — fine at short retention; at scale
  pre-aggregate into rollup rows or a TSDB.
- Rate limit is keyed per (service, client IP). Per-API-key or per-custom-header
  is a natural extension.
- `latency_ms` is upstream time-to-first-byte, not full transfer (we return the
  streaming response before the body finishes).
- Request body is buffered, not streamed (fine for API payloads; note for large uploads).
- `api_key.last_used_at` is touched on every request — production should throttle
  (skip when recent) to avoid a write per request.
- `RequestLog` has no retention/cleanup job yet — no phase currently scheduled
  for it; would be a cron/scheduled task deleting rows past a retention window.
- `upstream_url` SSRF validation exists (`net_safety.py`, Phase 7) but is off by
  default — see the Phase 7 known-simplifications entries above.
- One rule per service enforced only by the unique index on `rate_limit_rules.service_id`.
- App Redis client uses redis-py's default (unbounded) connection pool. Production
  should set an explicit bounded pool sized to the worker's concurrency.
- Sliding-window-counter `retry_after` is an approximation (documented in the .lua).
- Redis / Postgres are single instances — no HA/replication.
- Access tokens only, no refresh-token rotation.
- SECRET_KEY from a single env var, no key rotation / JWKS.
- Frontend dashboard shell is intentionally near-empty this phase.

## Key decisions log
- 2026-08-31: `TenantUser` separate from `Tenant` (multi-user tenants from v1).
- 2026-08-31: JWT carries `tid` to avoid a DB lookup for tenant-scoping on every request.
- 2026-08-31: API-key auth explicitly deferred to Phase 2 — it belongs with Service.
