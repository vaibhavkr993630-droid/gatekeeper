"""Pure proxy helpers — no DB, no Redis, no network."""
import pytest

from app.gateway.http_util import (
    build_upstream_url,
    client_ip_from,
    extract_api_key,
    filter_request_headers,
    filter_response_headers,
)
from app.rate_limit.base import RateLimitResult


@pytest.mark.parametrize(
    ("base", "path", "query", "expected"),
    [
        ("https://api.example.com", "v1/users", "", "https://api.example.com/v1/users"),
        ("https://api.example.com/", "v1/users", "a=1", "https://api.example.com/v1/users?a=1"),
        ("https://api.example.com/prefix", "users", "", "https://api.example.com/prefix/users"),
        ("https://api.example.com/prefix/", "", "", "https://api.example.com/prefix/"),
        ("http://10.0.0.5:8080", "/health", "", "http://10.0.0.5:8080/health"),
    ],
)
def test_build_upstream_url(base, path, query, expected):
    assert build_upstream_url(base, path, query) == expected


def test_filter_request_headers_strips_and_forwards():
    headers = [
        ("host", "gatekeeper.io"),
        ("content-length", "12"),
        ("connection", "keep-alive"),
        ("authorization", "Bearer gk_secret"),
        ("x-api-key", "gk_secret"),
        ("user-agent", "curl/8"),
        ("x-forwarded-for", "203.0.113.9"),
    ]
    out = dict(filter_request_headers(headers, client_ip="198.51.100.7", forwarded_host="gatekeeper.io"))

    assert "host" not in out
    assert "content-length" not in out
    assert "connection" not in out
    assert "authorization" not in out  # gateway credential, not forwarded upstream
    assert "x-api-key" not in out
    assert out["user-agent"] == "curl/8"
    assert out["x-forwarded-for"] == "203.0.113.9, 198.51.100.7"  # appended, not replaced
    assert out["x-forwarded-host"] == "gatekeeper.io"


def test_filter_request_headers_adds_xff_when_absent():
    out = dict(filter_request_headers([("accept", "*/*")], client_ip="1.2.3.4", forwarded_host=None))
    assert out["x-forwarded-for"] == "1.2.3.4"
    assert "x-forwarded-host" not in out


def test_filter_response_headers():
    out = dict(
        filter_response_headers(
            [
                ("content-type", "application/json"),
                ("content-length", "40"),
                ("transfer-encoding", "chunked"),
                ("connection", "close"),
            ]
        )
    )
    assert out["content-type"] == "application/json"
    assert out["content-length"] == "40"  # kept: we stream raw bytes
    assert "transfer-encoding" not in out
    assert "connection" not in out


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"authorization": "Bearer gk_abc"}, "gk_abc"),
        ({"Authorization": "bearer gk_abc"}, "gk_abc"),
        ({"x-api-key": "gk_xyz"}, "gk_xyz"),
        ({"X-API-Key": "  gk_xyz  "}, "gk_xyz"),
        ({"authorization": "Basic zzz"}, None),
        ({}, None),
    ],
)
def test_extract_api_key(headers, expected):
    assert extract_api_key(headers) == expected


@pytest.mark.parametrize(
    ("xff", "peer", "trust", "expected"),
    [
        ("203.0.113.1, 10.0.0.1", "10.0.0.1", True, "203.0.113.1"),
        ("203.0.113.1", "10.0.0.1", False, "10.0.0.1"),  # header ignored when not trusted
        (None, "10.0.0.1", True, "10.0.0.1"),
        (None, None, True, "unknown"),
    ],
)
def test_client_ip_from(xff, peer, trust, expected):
    assert client_ip_from(forwarded_for=xff, peer=peer, trust_forwarded=trust) == expected


def test_rate_limit_headers_ceil_retry_after():
    from app.gateway.router import _rate_limit_headers

    blocked = RateLimitResult(allowed=False, limit=100, remaining=0, retry_after=0.2)
    headers = _rate_limit_headers(blocked)
    assert headers["X-RateLimit-Limit"] == "100"
    assert headers["Retry-After"] == "1"  # ceil, min 1

    allowed = RateLimitResult(allowed=True, limit=100, remaining=42, retry_after=0.0)
    assert "Retry-After" not in _rate_limit_headers(allowed)
