"""Structured logging + request-id correlation."""
import json
import logging

import pytest
from httpx import AsyncClient

from app.core.logging import JsonFormatter
from app.core.request_context import RequestIdLogFilter, request_id_var


def _make_record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="gatekeeper.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="something happened",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_produces_valid_json_with_expected_keys():
    record = _make_record(service_id=7)
    RequestIdLogFilter().filter(record)  # attaches request_id, "-" outside a request

    line = JsonFormatter().format(record)
    payload = json.loads(line)

    assert payload["message"] == "something happened"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "gatekeeper.test"
    assert payload["request_id"] == "-"
    assert payload["service_id"] == 7  # extra fields pass through
    assert "timestamp" in payload


def test_json_formatter_includes_exception_traceback():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _make_record()
        record.exc_info = sys.exc_info()

    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exception"]


def test_request_id_filter_reads_the_contextvar():
    token = request_id_var.set("abc-123")
    try:
        record = _make_record()
        RequestIdLogFilter().filter(record)
        assert record.request_id == "abc-123"
    finally:
        request_id_var.reset(token)


@pytest.mark.asyncio
async def test_every_response_carries_a_request_id_header(client: AsyncClient):
    res = await client.get("/health")
    assert res.headers["x-request-id"]


@pytest.mark.asyncio
async def test_client_supplied_request_id_is_echoed_back(client: AsyncClient):
    res = await client.get("/health", headers={"X-Request-ID": "caller-supplied-id"})
    assert res.headers["x-request-id"] == "caller-supplied-id"
