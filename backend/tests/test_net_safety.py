"""SSRF guard — pure logic, no network for the literal-IP cases."""
import pytest

from app.core.net_safety import UnsafeUpstreamError, assert_public_upstream


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8080",
        "http://127.0.0.1",
        "http://localhost",
        "http://LOCALHOST:9000",
        "http://10.0.0.5",
        "http://192.168.1.1",
        "http://172.16.0.1",
        "http://169.254.169.254",  # cloud metadata endpoint — the classic SSRF target
        "http://0.0.0.0",
        "http://[::1]",  # IPv6 loopback
    ],
)
def test_rejects_non_routable_targets(url):
    with pytest.raises(UnsafeUpstreamError):
        assert_public_upstream(url)


@pytest.mark.parametrize("url", ["http://8.8.8.8", "https://1.1.1.1:443"])
def test_allows_public_literal_ips(url):
    assert_public_upstream(url)  # does not raise


def test_rejects_url_with_no_host():
    with pytest.raises(UnsafeUpstreamError):
        assert_public_upstream("not-a-url")


def test_rejects_unresolvable_hostname():
    # .invalid is reserved by RFC 2606 — guaranteed to never resolve
    with pytest.raises(UnsafeUpstreamError, match="could not resolve"):
        assert_public_upstream("http://this-does-not-exist.invalid")
