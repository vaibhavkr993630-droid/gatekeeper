"""ConnectionManager — per-tenant fan-out and isolation. No real sockets."""
import pytest

from app.ws.manager import ConnectionManager

pytestmark = pytest.mark.asyncio


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


class BrokenWS:
    async def send_json(self, message: dict) -> None:
        raise RuntimeError("socket already closed")


async def test_publish_reaches_only_the_target_tenant():
    m = ConnectionManager()
    a1, a2, b1 = FakeWS(), FakeWS(), FakeWS()
    await m.register(1, a1)
    await m.register(1, a2)
    await m.register(2, b1)

    await m.publish(1, {"type": "request", "n": 1})

    assert a1.sent == [{"type": "request", "n": 1}]
    assert a2.sent == [{"type": "request", "n": 1}]
    assert b1.sent == []  # tenant 2 sees nothing


async def test_unregister_and_empty_tenant_cleanup():
    m = ConnectionManager()
    ws = FakeWS()
    await m.register(7, ws)
    assert m.connection_count(7) == 1
    await m.unregister(7, ws)
    assert m.connection_count(7) == 0
    assert 7 not in m._by_tenant


async def test_broken_socket_is_dropped_and_does_not_block_others():
    m = ConnectionManager()
    good, bad = FakeWS(), BrokenWS()
    await m.register(1, bad)
    await m.register(1, good)

    await m.publish(1, {"ok": True})

    assert good.sent == [{"ok": True}]
    assert m.connection_count(1) == 1  # the broken one was evicted
