"""Live-feed WebSocket: tenant isolation end-to-end, auth, snapshot.

The gateway -> broadcast -> manager -> socket path is exercised with real Postgres
and Redis; the WebSocket handshake itself is driven with a fake server socket so
the test stays on one event loop.
"""
import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.security import generate_api_key
from app.models.service import ApiKey, RateLimitRule, Service
from app.models.tenant import Tenant
from app.ws.manager import manager
from app.ws.router import feed

pytestmark = pytest.mark.asyncio


class FakeServerWS:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self.close_code: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)

    async def receive_text(self) -> str:
        raise WebSocketDisconnect(code=1000)  # client "goes away" immediately

    async def close(self, code: int = 1000) -> None:
        self.close_code = code


@pytest.fixture(autouse=True)
def _clear_manager():
    manager._by_tenant.clear()
    yield
    manager._by_tenant.clear()


async def _seed(maker, *, upstream: str, algorithm="token_bucket", limit=10) -> tuple[str, str, int]:
    generated = generate_api_key()
    async with maker() as db:
        tenant = Tenant(name="Acme")
        db.add(tenant)
        await db.flush()
        service = Service(
            tenant_id=tenant.id,
            name="Acme API",
            upstream_url=upstream,
            rule=RateLimitRule(algorithm=algorithm, limit=limit, window_seconds=60, burst=None),
        )
        db.add(service)
        await db.flush()
        db.add(
            ApiKey(
                service_id=service.id,
                key_hash=generated.key_hash,
                prefix=generated.prefix,
                last_four=generated.last_four,
            )
        )
        await db.commit()
        return generated.plaintext, service.public_id, tenant.id


async def test_gateway_request_reaches_only_the_owning_tenant(gateway_client, stub_upstream):
    client, maker = gateway_client
    key_a, pid_a, tid_a = await _seed(maker, upstream=stub_upstream)
    _key_b, _pid_b, tid_b = await _seed(maker, upstream=stub_upstream)

    ws_a, ws_b = FakeServerWS(), FakeServerWS()
    await manager.register(tid_a, ws_a)
    await manager.register(tid_b, ws_b)

    await client.get(f"/gw/{pid_a}/ping", headers={"X-API-Key": key_a})

    assert len(ws_a.sent) == 1
    event = ws_a.sent[0]
    assert event["type"] == "request"
    assert event["path"] == "/ping" and event["method"] == "GET" and event["allowed"] is True
    assert ws_b.sent == []  # tenant B's feed is untouched


async def test_blocked_requests_are_broadcast_too(gateway_client, stub_upstream):
    client, maker = gateway_client
    key, pid, tid = await _seed(maker, upstream=stub_upstream, limit=1)
    ws = FakeServerWS()
    await manager.register(tid, ws)

    await client.get(f"/gw/{pid}/x", headers={"X-API-Key": key})  # allowed
    await client.get(f"/gw/{pid}/x", headers={"X-API-Key": key})  # blocked

    assert [e["allowed"] for e in ws.sent] == [True, False]
    assert ws.sent[1]["status_code"] == 429


async def test_feed_rejects_bad_token():
    ws = FakeServerWS()
    await feed(ws, token="not-a-jwt")
    assert ws.close_code == 4401
    assert ws.accepted is False


async def test_feed_accepts_valid_token_and_sends_snapshot(gateway_client, stub_upstream):
    client, maker = gateway_client
    await _seed(maker, upstream=stub_upstream)
    reg = await client.post(
        "/api/auth/register",
        json={"tenant_name": "Acme", "email": "feed@example.com", "password": "supersecret1"},
    )
    # that new tenant has no traffic; snapshot should be empty for it
    empty_ws = FakeServerWS()
    await feed(empty_ws, token=reg.json()["access_token"])
    assert empty_ws.accepted
    assert empty_ws.sent[0] == {"type": "snapshot", "events": []}