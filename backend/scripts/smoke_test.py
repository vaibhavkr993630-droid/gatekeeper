"""End-to-end smoke test against a running (usually deployed) GateKeeper.

Registers a fresh tenant, points a service at a public echo backend, mints a
key, fires a burst through the gateway, and asserts the rate limiter actually
kicked in (some 200s, some 429s) — the whole pipeline, live.

    python -m scripts.smoke_test https://gatekeeper.up.railway.app
    python -m scripts.smoke_test                      # defaults to http://localhost:8080
"""
import sys
import time
import uuid

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
UPSTREAM = "https://httpbin.org"
LIMIT = 5
BURST = 20


def _check(cond: bool, msg: str) -> None:
    mark = "ok  " if cond else "FAIL"
    print(f"  [{mark}] {msg}")
    if not cond:
        sys.exit(1)


def main() -> None:
    email = f"smoke-{uuid.uuid4().hex[:10]}@example.com"
    print(f"target: {BASE}")

    with httpx.Client(base_url=BASE, timeout=30.0) as c:
        r = c.get("/health")
        _check(r.status_code == 200 and r.json().get("redis") is True, f"health: {r.json()}")

        r = c.post(
            "/api/auth/register",
            json={"tenant_name": "smoke", "email": email, "password": "smoke-password-123"},
        )
        _check(r.status_code == 201, f"register tenant ({r.status_code})")
        token = r.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        r = c.post(
            "/api/services",
            json={
                "name": "smoke-svc",
                "upstream_url": UPSTREAM,
                "rule": {"algorithm": "token_bucket", "limit": LIMIT, "window_seconds": 60},
            },
            headers=auth,
        )
        _check(r.status_code == 201, f"create service ({r.status_code})")
        public_id = r.json()["public_id"]

        r = c.post(f"/api/services/{r.json()['id']}/keys", json={}, headers=auth)
        _check(r.status_code == 201, f"mint API key ({r.status_code})")
        api_key = r.json()["api_key"]

        print(f"  ... firing {BURST} requests through /gw/{public_id} (limit {LIMIT}/60s)")
        codes = []
        for _ in range(BURST):
            resp = c.get(f"/gw/{public_id}/get", headers={"X-API-Key": api_key})
            codes.append(resp.status_code)
        allowed = codes.count(200)
        blocked = codes.count(429)
        print(f"  ... {allowed} x 200, {blocked} x 429  ({codes})")
        _check(allowed == LIMIT, f"exactly {LIMIT} requests allowed")
        _check(blocked == BURST - LIMIT, f"the other {BURST - LIMIT} rate-limited (429)")

        r = c.get("/api/auth/me", headers=auth)
        _check(r.status_code == 200, "token still valid after the burst")

        time.sleep(13)  # token bucket refills at limit/window = 5/60 ≈ 1 per 12s
        r = c.get(f"/gw/{public_id}/get", headers={"X-API-Key": api_key})
        _check(r.status_code == 200, "a request is allowed again after the bucket refills")

    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    main()
