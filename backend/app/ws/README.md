# ws/

Dashboard live feed. `ws://<host>/ws/feed?token=<tenant JWT>`.

- `manager.py` — `ConnectionManager`, `{tenant_id: {sockets}}`. `publish(tenant_id, msg)`
  reaches only that tenant's sockets.
- `router.py` — the endpoint. Verifies the JWT, takes `tenant_id` **from the token**
  (never from the client), sends a snapshot of recent activity, then streams live
  events. There is no "subscribe" message — a client cannot ask for anything but
  its own tenant's feed.
- `broadcast.py` — `broadcast_request(record)`, called by the gateway as a
  BackgroundTask after each proxied request (independent of the RequestLog write).
- `events.py` — event payload shape.

## Isolation
Enforced structurally: a socket is filed under the tenant id from its verified
token; `publish` is per-tenant. `test_ws_feed.py` proves tenant A never sees
tenant B's traffic.

## Single process only
This is in-process fan-out. Two uvicorn workers → a client connected to worker A
misses events the gateway handled on worker B. At scale: each gateway node
`PUBLISH`es to Redis pub/sub (or Kafka/NATS), each dashboard node `SUBSCRIBE`s and
re-fans-out locally. The `ConnectionManager` interface doesn't change — only where
`publish` is fed from.
