# gateway/

The hot path. `POST /gw/{public_id}/{path}` (any method):

1. **Identify** — `X-API-Key` / `Authorization: Bearer` header → SHA-256 → one
   indexed lookup (`identity.resolve_target`) loading the service + its rule.
   The URL's `public_id` is confirmed against the key (mismatch → 404).
2. **Rate check** — `factory.get_rate_limiter(rule, redis).check(key)` where
   `key = make_key(service.public_id, client_ip)`. One Redis round-trip.
   Over the limit → `429` with `Retry-After` + `X-RateLimit-*`.
   Redis down → fail-open (configurable) with `X-RateLimit-Bypassed: true`.
3. **Forward** — `forwarder.forward` sends the request through the shared pooled
   `httpx.AsyncClient` to `service.upstream_url` + path + query, strips hop-by-hop
   and the gateway's own credentials, adds `X-Forwarded-For/-Host`, and streams
   the raw response back. Upstream timeout → `504`, unreachable → `502`.
4. **Record** — `recorder.record_request` writes one `RequestLog` row and touches
   `api_key.last_used_at`, as a background task *after* the response — the caller
   never waits on the DB.

## Not the management API
`api/routers/services.py` is CRUD for tenants configuring their services (JWT).
This is the separate data-plane that tenant *traffic* flows through (API key).

## What'd change at real scale
- Colocate Redis with gateway nodes; tune the httpx pool to worker concurrency.
- Cache the API-key → service lookup in-process (short TTL, invalidate on revoke).
- Batch `RequestLog` writes / move them to a short-retention store, not Postgres.
- Only trust `X-Forwarded-For` from known ingress IPs.
- Stream the *request* body too (v1 buffers it).
